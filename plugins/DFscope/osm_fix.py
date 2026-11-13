# =============================================================================
# osm_fix.py  -  Kartenkacheln (Tiles) fuer tkintermapview, konform zur
#                OSM Tile Usage Policy, mit Cache, Ersatzdienst und Dropdown
# =============================================================================
# Wird als ALLERERSTER Import geladen ("import osm_fix", vor tkintermapview) und
# patcht die Bibliothek beim Import. Danach pro Karte genau EINMAL aufrufen:
#
#       self.map_widget = TkinterMapView(...)
#       self.map_widget.pack(...)
#       osm_fix.setup_map(self.map_widget)
#
# Was das Modul macht
# -------------------
#  1. Eigener User-Agent (die Bibliothek sendet nur "TkinterMapView" - das ist
#     bei OSM unerwuenscht und kann zur Sperre fuehren).
#  2. Festplatten-Cache fuer Kacheln (siehe Abschnitt "CACHE" unten).
#  3. Hoechstens 2 gleichzeitige Downloads (tkintermapview startet sonst 25
#     Loader-Threads; die OSM-Policy erlaubt maximal 2 Verbindungen).
#  4. Prefetch (Vorladen) auf Radius 2 begrenzt (Original: Radius 8 = 17x17 Kacheln).
#  5. Sichtbare Attribution mit Links (Pflicht bei OSM und openmaps.fr).
#  6. Wahl des Kartendienstes per Dropdown (oben rechts in der Karte).
#  7. AUTOMATISCHER ERSATZDIENST: Sperrt der gewaehlte Dienst uns (HTTP 403/429)
#     oder ist er nicht erreichbar, wird auf den anderen Dienst umgeschaltet.
#     Der gewaehlte Dienst wird danach nur selten (1 h, 2 h, 4 h ... max. 24 h)
#     mit EINER Kachel getestet und bei Erfolg wieder verwendet.
#
# Bedingungen der Dienste (Stand 13.11.2026 - bitte gelegentlich pruefen!)
# ------------------------------------------------------------------------
#  OSM:         https://operations.osmfoundation.org/policies/tiles/
#  openmaps.fr: https://openmaps.fr/tile-usage-policy.html
#               (nicht-kommerziell, max. 500.000 Kacheln/Monat, kein API-Key,
#                Attribution inkl. Donation-Link, eigener User-Agent,
#                kein Bulk-Download und keine Prefetch-Funktionen)
# =============================================================================
import io
import json
import os
import re
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk
from datetime import timedelta
from pathlib import Path

import requests
import tkintermapview.map_widget as _mw

# -----------------------------------------------------------------------------
# KONFIGURATION
# -----------------------------------------------------------------------------

# Muss die Anwendung eindeutig identifizieren und eine Kontakt-URL enthalten.
# Nie den Standardwert einer Bibliothek ("python-requests/...") oder einen
# fremden Browser-/App-User-Agent verwenden - das verbieten beide Policies.
USER_AGENT = ("AMWaveSynthPropagationSimulator/1.0 "
              "(+https://github.com/radiolab81/AMWaveSynthPropagationSimulator)")

# Verfuegbare Kartendienste. Der Schluessel (z.B. "osm") ist der interne Name,
# "label" erscheint im Dropdown. Weitere Dienste einfach als neuen Eintrag
# ergaenzen - ABER erst deren Nutzungsbedingungen lesen und die geforderte
# Attribution unter "links" eintragen! Dienste, die einen API-Key brauchen
# (z.B. CARTO, MapTiler), sind hier bewusst nicht enthalten.
PROVIDERS = {
    "osm": {
        "label": "OpenStreetMap",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",   # exakt so laut Policy
        "max_zoom": 19,
        # Attribution: Text + Link, wird unten rechts in der Karte angezeigt.
        "links": [("\u00a9 OpenStreetMap contributors", "https://www.openstreetmap.org/copyright"),
                  ("Report a map issue", "https://www.openstreetmap.org/fixthemap")],
    },
    "topo": {
        "label": "OpenTopoMap (openmaps.fr)",
        "url": "https://tile.openmaps.fr/opentopomap/{z}/{x}/{y}.png",
        "max_zoom": 17,      # Annahme: Der OpenTopoMap-Stil endet bei Zoom 17 (bitte pruefen)
        # openmaps.fr verlangt ausdruecklich: Style-Attribution, Donation-Link, OSM-Attribution.
        "links": [("\u00a9 OpenTopoMap-R", "https://github.com/sletuffe/OpenTopoMap"),
                  ("\u2665 Donation", "https://openmaps.fr/donate"),
                  ("\u00a9 OpenStreetMap", "https://www.openstreetmap.org/copyright")],
    },
}

# Dienst beim allerersten Start. Danach gilt die letzte Auswahl im Dropdown
# (wird in CACHE_DIR/provider.json gespeichert).
DEFAULT_PROVIDER = "osm"

# Welcher Dienst springt ein, wenn der gewaehlte gesperrt/nicht erreichbar ist?
# Bewusst eine feste Zuordnung statt "irgendein anderer": So bleibt nachvollziehbar,
# welcher Anbieter wann Last bekommt. Bei weiteren Diensten hier ergaenzen.
FALLBACK_OF = {"osm": "topo", "topo": "osm"}

# ---- CACHE ------------------------------------------------------------------
# Gecachte Kacheln liegen in einer SQLite-Datei (CACHE_DIR/osm_tiles.sqlite).
# Eine Kachel aus dem Cache kostet den Server nichts - das ist das Ziel der Policy.
#
# Variante A  "Header beachten" (empfohlen, policy-konform, Standard):
#   Der Server sagt per Cache-Control/Expires, wie lange eine Kachel gueltig ist.
#   Danach wird mit ETag nachgefragt; antwortet der Server "304 Not Modified",
#   wird die Kachel NICHT erneut uebertragen (fast keine Last fuer den Server).
#   Schickt ein Server keine Header, gelten die 7 Tage aus CACHE_FALLBACK_DAYS.
#
# Variante B  "Feste Dauer":
#   Header werden ignoriert, jede Kachel gilt CACHE_FIXED_DAYS Tage. Das ist
#   policy-konform, solange es mindestens 7 Tage sind (erzwingt der Code mit max()).
#   Vorteil: weniger Anfragen, Karte offline-tauglicher. Nachteil: Aenderungen in
#   OSM (neue Strassen, Korrekturen) erscheinen bis zu CACHE_FIXED_DAYS Tage spaeter.
CACHE_RESPECT_HEADERS = True     # True = Variante A, False = Variante B
CACHE_FALLBACK_DAYS = 7          # Variante A: Gueltigkeit, wenn der Server keine Header schickt
CACHE_FIXED_DAYS = 30            # Variante B: feste Gueltigkeit (mindestens 7!)

# Zusatz: Abgelaufene Kacheln trotzdem ausliefern, wenn die Neuabfrage scheitert
# (Netzwerkfehler oder Serverfehler). Gut fuer Offline-Betrieb und kurze Ausfaelle.
# Hinweis: Ob requests-cache das auch bei einer 403-Sperre tut, ist ungetestet;
# das Umschalten auf den Ersatzdienst (unten) greift in jedem Fall fuer Kacheln,
# die NICHT im Cache liegen.
CACHE_STALE_IF_ERROR = True

# Aufraeumen: Kacheln, die aelter als N Tage sind, werden beim Start geloescht,
# damit die Datei nicht endlos waechst. 0 = nie aufraeumen. Muss groesser sein als
# die Gueltigkeit oben, sonst gaebe es nie "abgelaufene" Kacheln fuer CACHE_STALE_IF_ERROR.
CACHE_PURGE_OLDER_THAN_DAYS = 90

CACHE_DIR = Path(os.environ.get("AMWAVE_TILE_CACHE",
                 Path.home() / ".cache" / "AMWaveSynthPropagationSimulator"))

# ---- Verbindungen, Prefetch, Timeouts ---------------------------------------
MAX_CONNECTIONS = 2      # OSM-Policy: max. 2 gleichzeitige Download-Verbindungen
PRECACHE_MAX_RADIUS = 2  # tkintermapview-Original: 8 (= 17x17 Kacheln, zu viel)
TIMEOUT = (5, 15)        # (Verbindungsaufbau, Lesen) in Sekunden - verhindert Haenger

# ---- Ersatzdienst-Logik -----------------------------------------------------
BLOCK_STATUS = (403, 429)  # "gesperrt" bzw. "zu viele Anfragen": sofort umschalten
SOFT_FAIL_LIMIT = 3        # Serverfehler (5xx)/Timeouts: erst nach so vielen in Folge
                           # umschalten - und nur, wenn der Ersatzdienst antwortet
RETRY_BASE = 3600          # gewaehlten Dienst nach 1 h mit EINER Kachel testen ...
RETRY_MAX = 24 * 3600      # ... danach Wartezeit verdoppeln, maximal 24 h
POLL_MS = 500              # wie oft der Tk-Hauptthread auf einen Wechsel prueft

_TILE_RE = re.compile(r"/(\d+)/(\d+)/(\d+)\.png")
_PREF_FILE = CACHE_DIR / "provider.json"


# -----------------------------------------------------------------------------
# CACHE / HTTP-SESSION
# -----------------------------------------------------------------------------
def _make_session():
    """Baut die HTTP-Session mit Festplatten-Cache (Varianten siehe oben)."""
    try:
        import requests_cache
    except ImportError:
        print("[osm_fix] WARNUNG: 'requests-cache' fehlt (pip install requests-cache). "
              "Ohne Festplatten-Cache wird die OSM Tile Usage Policy NICHT erfuellt!")
        return requests.Session()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_RESPECT_HEADERS:                      # Variante A
        mode = dict(cache_control=True, expire_after=timedelta(days=max(1, CACHE_FALLBACK_DAYS)))
    else:                                          # Variante B (mind. 7 Tage erzwingen)
        mode = dict(cache_control=False, expire_after=timedelta(days=max(7, CACHE_FIXED_DAYS)))

    common = dict(
        cache_name=str(CACHE_DIR / "osm_tiles"), backend="sqlite",
        allowable_codes=(200,),        # Fehlerseiten (403 ...) werden nie gecacht
        allowable_methods=("GET",),
        **mode)
    try:
        session = requests_cache.CachedSession(stale_if_error=CACHE_STALE_IF_ERROR, **common)
    except TypeError:                  # sehr alte requests-cache-Version ohne stale_if_error
        print("[osm_fix] Hinweis: requests-cache kennt stale_if_error nicht - ohne.")
        session = requests_cache.CachedSession(**common)

    if CACHE_PURGE_OLDER_THAN_DAYS > 0:
        threading.Thread(target=_purge_old_tiles, args=(session,), daemon=True).start()
    return session


def _purge_old_tiles(session):
    """Loescht sehr alte Kacheln (im Hintergrund, damit der Start nicht verzoegert wird)."""
    try:
        session.cache.delete(older_than=timedelta(days=CACHE_PURGE_OLDER_THAN_DAYS))
    except Exception as e:             # API je nach requests-cache-Version verschieden
        print(f"[osm_fix] Cache-Aufraeumen uebersprungen: {e}")


class _Response:
    """Wie requests.Response, aber .raw ist seekbar (PIL.Image.open braucht das)."""
    def __init__(self, resp):
        self._resp = resp
        self.raw = io.BytesIO(resp.content)

    def __getattr__(self, name):
        return getattr(self._resp, name)


# -----------------------------------------------------------------------------
# MANAGER: Zustand + Logik fuer Dienstwahl und Ersatzdienst (eine Instanz pro Prozess)
# -----------------------------------------------------------------------------
class _Manager:
    # Begriffe:
    #   preferred = vom Benutzer im Dropdown gewaehlter Dienst
    #   active    = Dienst, an den gerade tatsaechlich Anfragen gehen
    #               (== preferred im Normalfall, == Ersatzdienst bei Sperre/Ausfall)
    #   pending   = Dienst, den der Tk-Hauptthread anzeigen soll. Die Download-Threads
    #               duerfen die GUI nicht anfassen (Tkinter ist nicht thread-sicher);
    #               sie setzen nur "pending", ein Timer im Hauptthread uebernimmt.

    def __init__(self):
        self.session = _make_session()
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)   # max. 2 Downloads
        self.lock = threading.Lock()
        self.preferred = self._load_preference()
        self.active = self.pending = self.preferred
        self.retry_at = 0.0          # frueheste Zeit fuer den naechsten Test des gewaehlten Dienstes
        self.delay = RETRY_BASE      # aktuelle Wartezeit (verdoppelt sich bei Fehlschlag)
        self.probing = False         # laeuft gerade ein Test? (immer nur einer gleichzeitig)
        self.soft_fails = 0
        self.widgets = []

    # ---------- gespeicherte Auswahl ----------
    @staticmethod
    def _load_preference():
        try:
            name = json.loads(_PREF_FILE.read_text(encoding="utf-8")).get("provider")
            if name in PROVIDERS:
                return name
        except Exception:
            pass
        return DEFAULT_PROVIDER

    def _save_preference(self):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _PREF_FILE.write_text(json.dumps({"provider": self.preferred}), encoding="utf-8")
        except Exception:
            pass

    # ---------- Netzwerk ----------
    def _fetch(self, provider, z, x, y, kwargs):
        """Eine Kachel bei einem bestimmten Dienst holen (max. 2 gleichzeitig)."""
        url = PROVIDERS[provider]["url"].format(z=z, x=x, y=y)
        kw = dict(kwargs)
        kw.pop("stream", None)                       # wir lesen den Inhalt komplett
        headers = dict(kw.pop("headers", None) or {})
        headers["User-Agent"] = USER_AGENT           # ueberschreibt "TkinterMapView"
        kw.setdefault("timeout", TIMEOUT)
        with self.slots:
            return _Response(self.session.get(url, headers=headers, **kw))

    def get(self, url, **kwargs):
        """Ersatz fuer requests.get() in tkintermapview. Entscheidet, welcher Dienst
        die Kachel liefert. Die URL aus der Bibliothek wird nur zum Auslesen von
        z/x/y benutzt; die echte URL baut diese Methode je nach aktivem Dienst."""
        m = _TILE_RE.search(url)
        if not m:                                    # keine Kachel-URL: unveraendert holen
            return _Response(self.session.get(url, headers={"User-Agent": USER_AGENT},
                                              timeout=TIMEOUT))
        z, x, y = m.groups()

        with self.lock:
            preferred, active = self.preferred, self.active
            normal = (active == preferred)
            # Im Ersatzbetrieb: nach Ablauf der Wartezeit EINE Kachel beim gewaehlten
            # Dienst testen. "probing" stellt sicher, dass das nur ein Thread tut.
            probe = (not normal and not self.probing and time.time() >= self.retry_at)
            if probe:
                self.probing = True
        if not (normal or probe):                    # Ersatzbetrieb, noch Wartezeit
            return self._fetch(active, z, x, y, kwargs)

        backup = FALLBACK_OF[preferred]
        err = resp = None
        try:
            resp = self._fetch(preferred, z, x, y, kwargs)
        except requests.exceptions.RequestException as e:
            err = e
        try:
            if resp is not None and resp.status_code in BLOCK_STATUS:
                # Gesperrt / zu viele Anfragen: sofort wechseln und diese Kachel
                # gleich vom Ersatzdienst holen, damit keine Luecke entsteht.
                self._to_fallback(f"{PROVIDERS[preferred]['label']}: HTTP {resp.status_code}", probe)
                return self._fetch(backup, z, x, y, kwargs)
            if err is not None or resp.status_code >= 500:
                # Fehler beim gewaehlten Dienst. Nur wenn der Ersatzdienst antwortet,
                # liegt das Problem beim Dienst; antwortet auch er nicht, ist
                # vermutlich unser Netz weg -> nichts umschalten.
                try:
                    fb = self._fetch(backup, z, x, y, kwargs)
                except requests.exceptions.RequestException:
                    if err is not None:
                        raise err
                    return resp
                self._soft_fail(probe)
                return fb
            # alles in Ordnung
            if probe:
                self._to_preferred()                 # Test erfolgreich: zurueckwechseln
            else:
                self.soft_fails = 0
            return resp
        finally:
            if probe:
                with self.lock:
                    self.probing = False

    # ---------- Zustandswechsel (laufen in Download-Threads) ----------
    def _to_fallback(self, reason, was_probe=False):
        with self.lock:
            if self.active == self.preferred:
                self.delay = RETRY_BASE                              # frischer Ausfall
            elif was_probe:
                self.delay = min(self.delay * 2, RETRY_MAX)          # Test fehlgeschlagen
            self.active = self.pending = FALLBACK_OF[self.preferred]
            self.retry_at = time.time() + self.delay
            self.soft_fails = 0
        print(f"[osm_fix] {reason} -> Ersatzkarte ({PROVIDERS[self.active]['label']}); "
              f"naechster Test in {self.delay // 60} min")

    def _soft_fail(self, was_probe):
        with self.lock:
            self.soft_fails += 1
            switch = self.soft_fails >= SOFT_FAIL_LIMIT or was_probe
        if switch:
            self._to_fallback(f"{PROVIDERS[self.preferred]['label']}: nicht erreichbar/Serverfehler",
                              was_probe)

    def _to_preferred(self):
        with self.lock:
            self.active = self.pending = self.preferred
            self.delay = RETRY_BASE
            self.soft_fails = 0
        print(f"[osm_fix] {PROVIDERS[self.preferred]['label']} wieder erreichbar -> zurueck")

    # ---------- GUI (nur im Tk-Hauptthread!) ----------
    def set_provider(self, name):
        """Vom Dropdown aufgerufen: neuen Kartendienst waehlen. Setzt Sperr-/Fehlerzustand
        zurueck (ein bewusster Wechsel ist ein Neuanfang), speichert die Wahl und
        aktualisiert ALLE Karten (Hauptfenster und DFmap teilen sich die Auswahl)."""
        if name not in PROVIDERS:
            return
        with self.lock:
            self.preferred = self.active = self.pending = name
            self.retry_at, self.delay, self.soft_fails = 0.0, RETRY_BASE, 0
        self._save_preference()
        for w in self.widgets:
            self._apply(w)

    def setup_map(self, map_widget, provider_menu=True):
        """Einmal pro Karte aufrufen (direkt nach TkinterMapView(...))."""
        if hasattr(map_widget, "set_user_agent"):    # tkintermapview >= 1.32 kennt das selbst
            map_widget.set_user_agent(USER_AGENT)
        self.widgets.append(map_widget)
        map_widget._osm_view = None

        if provider_menu:
            labels = [p["label"] for p in PROVIDERS.values()]
            var = tk.StringVar(value=PROVIDERS[self.preferred]["label"])
            combo = ttk.Combobox(map_widget, textvariable=var, values=labels,
                                 state="readonly", width=26)
            combo.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")   # oben rechts
            combo.bind("<<ComboboxSelected>>", lambda _e, v=var, c=combo: self._selected(v, c))
            map_widget._osm_var = var
        else:
            map_widget._osm_var = None

        self._apply(map_widget)
        map_widget.after(POLL_MS, lambda: self._poll(map_widget))
        return map_widget._osm_box

    def _selected(self, var, combo):
        for name, p in PROVIDERS.items():
            if p["label"] == var.get():
                self.set_provider(name)
                break
        combo.selection_clear()                      # Markierung im Feld entfernen

    def _poll(self, w):
        """Laeuft alle POLL_MS im Hauptthread und uebernimmt Wechsel aus den Download-Threads."""
        try:
            if not w.winfo_exists():
                return
            if w._osm_view != (self.pending, self.preferred):
                self._apply(w)
            w.after(POLL_MS, lambda: self._poll(w))
        except tk.TclError:
            pass

    def _apply(self, w):
        """Karte auf den aktuellen Dienst umstellen: Tile-URL, Zoom, Attribution, Hinweis."""
        shown, preferred = self.pending, self.preferred
        prov = PROVIDERS[shown]
        w.set_tile_server(prov["url"], max_zoom=prov["max_zoom"])   # leert auch den Kachel-RAM-Cache
        try:
            if w.zoom > prov["max_zoom"]:            # z.B. Topo endet bei Zoom 17
                w.set_zoom(prov["max_zoom"])
        except Exception:
            pass
        if getattr(w, "_osm_var", None) is not None:
            w._osm_var.set(PROVIDERS[preferred]["label"])

        old = getattr(w, "_osm_box", None)
        if old is not None:
            old.destroy()
        box = tk.Frame(w, bg="#f0f0f0")
        items = []
        if shown != preferred:                       # Ersatzbetrieb: deutlich sichtbarer Hinweis
            items.append((f"Ersatzkarte \u2013 {PROVIDERS[preferred]['label']} nicht verfuegbar", None))
        items += prov["links"]
        for text, url in items:
            lbl = tk.Label(box, text=f" {text} ", bg="#f0f0f0", fg="#000000",
                           font=("Arial", 8), cursor="hand2" if url else "")
            lbl.pack(side="left")
            if url:
                lbl.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
        box.place(relx=1.0, rely=1.0, anchor="se")   # unten rechts
        box.lift()
        w._osm_box = box
        w._osm_view = (shown, preferred)


# -----------------------------------------------------------------------------
# EINBAU IN tkintermapview
# -----------------------------------------------------------------------------
class _RequestsShim:
    """Steht in tkintermapview.map_widget anstelle des Moduls 'requests'. Die Bibliothek
    ruft requests.get(...) auf; hier wird daraus _Manager.get(...). Alles andere
    (z.B. requests.exceptions) reicht __getattr__ an das echte requests durch."""
    def __init__(self, mgr):
        self._mgr = mgr

    def __getattr__(self, name):
        return getattr(requests, name)

    def get(self, url, **kwargs):
        return self._mgr.get(url, **kwargs)


def _pre_cache_limited(self):
    """Kopie von TkinterMapView.pre_cache (v1.29), aber Radius auf PRECACHE_MAX_RADIUS
    begrenzt. Das Original laedt ringweise bis Radius 8 (289 Kacheln) um die Kartenmitte -
    weit mehr als das "moderate Vorladen", das die OSM-Policy erlaubt."""
    last_pos = None
    radius = 1
    zoom = round(self.zoom)
    while self.running:
        if last_pos != self.pre_cache_position:
            last_pos = self.pre_cache_position
            zoom = round(self.zoom)
            radius = 1
        if last_pos is not None and radius <= PRECACHE_MAX_RADIUS:
            cx, cy = last_pos
            for x in range(cx - radius, cx + radius + 1):          # obere/untere Zeile
                for yy in (cy + radius, cy - radius):
                    if f"{zoom}{x}{yy}" not in self.tile_image_cache:
                        self.request_image(zoom, x, yy)
            for y in range(cy - radius, cy + radius + 1):          # linke/rechte Spalte
                for xx in (cx + radius, cx - radius):
                    if f"{zoom}{xx}{y}" not in self.tile_image_cache:
                        self.request_image(zoom, xx, y)
            radius += 1
        else:
            time.sleep(0.1)
        if len(self.tile_image_cache) > 10_000:                    # RAM-Cache wie im Original begrenzen
            for key in list(self.tile_image_cache.keys())[:len(self.tile_image_cache) - 10_000]:
                self.tile_image_cache.pop(key, None)


# Eine gemeinsame Instanz pro Prozess: Hauptprogramm UND DFscope-Plugin teilen sich
# Auswahl und Sperrzustand, auch wenn osm_fix.py zweimal im Projekt liegt.
_mgr = getattr(_mw, "_osm_fix_mgr", None)
if _mgr is None:
    _mgr = _Manager()
    _mw._osm_fix_mgr = _mgr
    _mw.requests = _RequestsShim(_mgr)
    if hasattr(_mw.TkinterMapView, "pre_cache"):
        _mw.TkinterMapView.pre_cache = _pre_cache_limited

setup_map = _mgr.setup_map
set_provider = _mgr.set_provider
