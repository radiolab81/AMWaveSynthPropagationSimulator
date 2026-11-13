# osm_fix.py - OSM Tile Usage Policy (https://operations.osmfoundation.org/policies/tiles/)
# plus automatic fallback tile provider (no API key needed).
#
# Wird als ALLERERSTER Import geladen (import osm_fix) und sorgt fuer:
#   * eigenen, stabilen User-Agent (statt "TkinterMapView" der Bibliothek)
#   * HTTP-Cache auf Platte (Cache-Control/Expires/ETag, Fallback 7 Tage) via requests-cache
#   * max. 2 gleichzeitige Download-Verbindungen, begrenztes Prefetch (Radius 2 statt 8)
#   * AUTOMATISCHER FALLBACK: sperrt OSM (HTTP 403/429) oder ist es nicht erreichbar,
#     wird auf openmaps.fr (OpenTopoMap-R, kein API-Key) umgeschaltet. OSM wird
#     danach nur sehr selten (1 h, 2 h, 4 h ... max. 24 h) mit EINER Kachel getestet.
#   * setup_map(map_widget): Tile-URL, sichtbare Attribution, Hinweis bei Fallback
#
# Provider-Bedingungen (Stand 13.11.2026, bitte gelegentlich pruefen):
#   OSM:         https://operations.osmfoundation.org/policies/tiles/
#   openmaps.fr: https://openmaps.fr/tile-usage-policy.html  (nicht-kommerziell,
#                max. 500k Kacheln/Monat, Attribution + Donation-Link, eigener User-Agent,
#                kein Bulk-Download/Prefetch-Feature)
import io
import os
import re
import threading
import time
import webbrowser
import tkinter as tk
from datetime import timedelta
from pathlib import Path

import requests
import tkintermapview.map_widget as _mw

USER_AGENT = ("AMWaveSynthPropagationSimulator/1.0 "
              "(+https://github.com/radiolab81/AMWaveSynthPropagationSimulator)")

PROVIDERS = {
    "primary": {
        "name": "OpenStreetMap",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "max_zoom": 19,
        "links": [("\u00a9 OpenStreetMap contributors", "https://www.openstreetmap.org/copyright"),
                  ("Report a map issue", "https://www.openstreetmap.org/fixthemap")],
        "notice": None,
    },
    "fallback": {
        "name": "openmaps.fr OpenTopoMap-R",
        "url": "https://tile.openmaps.fr/opentopomap/{z}/{x}/{y}.png",
        "max_zoom": 17,   # OpenTopoMap-Stil endet bei Zoom 17 (Annahme, bitte pruefen)
        "links": [("\u00a9 OpenTopoMap-R", "https://github.com/sletuffe/OpenTopoMap"),
                  ("\u2665 Donation", "https://openmaps.fr/donate"),
                  ("\u00a9 OpenStreetMap", "https://www.openstreetmap.org/copyright")],
        "notice": "Ersatzkarte (OSM gesperrt/nicht erreichbar)",
    },
}

MIN_CACHE = timedelta(days=7)    # OSM-Policy: mindestens 7 Tage, falls Header nicht lesbar
MAX_CONNECTIONS = 2              # OSM-Policy: max. 2 gleichzeitige Download-Verbindungen
PRECACHE_MAX_RADIUS = 2          # tkintermapview-Original: 8 (=17x17 Kacheln)
TIMEOUT = (5, 15)                # (connect, read) Sekunden
BLOCK_STATUS = (403, 429)        # sofort auf Fallback wechseln
SOFT_FAIL_LIMIT = 3              # so viele 5xx/Verbindungsfehler (bei funktionierendem Fallback)
RETRY_BASE = 3600                # erster OSM-Wiederholungstest nach 1 h
RETRY_MAX = 24 * 3600            # danach verdoppeln bis max. 24 h
POLL_MS = 500

CACHE_DIR = Path(os.environ.get("AMWAVE_TILE_CACHE",
                 Path.home() / ".cache" / "AMWaveSynthPropagationSimulator"))
_TILE_RE = re.compile(r"/(\d+)/(\d+)/(\d+)\.png")


def _make_session():
    """HTTP-Session mit Disk-Cache, der die Server-Header beachtet."""
    try:
        import requests_cache
    except ImportError:
        print("[osm_fix] WARNUNG: 'requests-cache' fehlt (pip install requests-cache). "
              "Ohne Disk-Cache wird die OSM Tile Usage Policy NICHT erfuellt!")
        return requests.Session()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return requests_cache.CachedSession(
        cache_name=str(CACHE_DIR / "osm_tiles"), backend="sqlite",
        cache_control=True, expire_after=MIN_CACHE,
        allowable_codes=(200,),          # Fehlerseiten (403 ...) nie cachen
        allowable_methods=("GET",), stale_if_error=False)


class _Response:
    """Wie requests.Response, aber .raw ist seekbar (fuer PIL.Image.open)."""
    def __init__(self, resp):
        self._resp = resp
        self.raw = io.BytesIO(resp.content)

    def __getattr__(self, name):
        return getattr(self._resp, name)


class _Manager:
    """Zustand + Logik fuer Primary/Fallback. Eine Instanz pro Prozess."""

    def __init__(self):
        self.session = _make_session()
        self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)  # 25 Loader-Threads!
        self.lock = threading.Lock()
        self.mode = "primary"        # welcher Provider wird aktuell abgefragt
        self.pending = "primary"     # was der Tk-Hauptthread anzeigen soll
        self.retry_at = 0.0
        self.delay = RETRY_BASE
        self.probing = False
        self.soft_fails = 0
        self.widgets = []

    # ---------- Netzwerk ----------
    def _fetch(self, provider, z, x, y, kwargs):
        url = PROVIDERS[provider]["url"].format(z=z, x=x, y=y)
        kw = dict(kwargs)
        kw.pop("stream", None)
        headers = dict(kw.pop("headers", None) or {})
        headers["User-Agent"] = USER_AGENT
        kw.setdefault("timeout", TIMEOUT)
        with self.slots:
            return _Response(self.session.get(url, headers=headers, **kw))

    def get(self, url, **kwargs):
        m = _TILE_RE.search(url)
        if not m:                                   # keine Kachel-URL: unveraendert
            return _Response(self.session.get(url, headers={"User-Agent": USER_AGENT},
                                              timeout=TIMEOUT))
        z, x, y = m.groups()
        with self.lock:
            use_primary = self.mode == "primary"
            probe = (not use_primary and not self.probing and time.time() >= self.retry_at)
            if probe:
                self.probing = True
        if not (use_primary or probe):
            return self._fetch("fallback", z, x, y, kwargs)

        err = resp = None
        try:
            resp = self._fetch("primary", z, x, y, kwargs)
        except requests.exceptions.RequestException as e:
            err = e
        try:
            if resp is not None and resp.status_code in BLOCK_STATUS:
                self._to_fallback(f"HTTP {resp.status_code}", probe)
            elif err is not None or resp.status_code >= 500:
                # OSM-seitiges Problem? Nur wenn der Ersatzdienst antwortet, sonst
                # ist vermutlich das eigene Netz weg -> nichts umschalten.
                try:
                    fb = self._fetch("fallback", z, x, y, kwargs)
                except requests.exceptions.RequestException:
                    if err is not None:
                        raise err
                    return resp
                self._soft_fail(probe)
                return fb
            else:
                if probe:
                    self._to_primary()
                else:
                    self.soft_fails = 0
                return resp
            return self._fetch("fallback", z, x, y, kwargs)   # Fall: gesperrt
        finally:
            if probe:
                with self.lock:
                    self.probing = False

    # ---------- Zustandswechsel ----------
    def _to_fallback(self, reason, was_probe=False):
        with self.lock:
            if self.mode == "primary":
                self.delay = RETRY_BASE
            elif was_probe:
                self.delay = min(self.delay * 2, RETRY_MAX)
            self.mode = "fallback"
            self.retry_at = time.time() + self.delay
            self.pending = "fallback"
            self.soft_fails = 0
        print(f"[osm_fix] OSM-Tiles: {reason} -> Ersatzkarte; naechster OSM-Test in "
              f"{self.delay // 60} min")

    def _soft_fail(self, was_probe):
        with self.lock:
            self.soft_fails += 1
            hit = self.soft_fails >= SOFT_FAIL_LIMIT or was_probe
        if hit:
            self._to_fallback("nicht erreichbar/Serverfehler", was_probe)

    def _to_primary(self):
        with self.lock:
            self.mode = "primary"
            self.pending = "primary"
            self.delay = RETRY_BASE
            self.soft_fails = 0
        print("[osm_fix] OSM-Tiles wieder erreichbar -> zurueck auf OpenStreetMap")

    # ---------- UI (nur im Tk-Hauptthread) ----------
    def setup_map(self, map_widget):
        """Nach TkinterMapView(...) aufrufen."""
        if hasattr(map_widget, "set_user_agent"):      # tkintermapview >= 1.32
            map_widget.set_user_agent(USER_AGENT)
        self.widgets.append(map_widget)
        map_widget._osm_applied = None
        self._apply(map_widget, self.pending)
        map_widget.after(POLL_MS, lambda: self._poll(map_widget))
        return map_widget._osm_box

    def _poll(self, w):
        try:
            if not w.winfo_exists():
                return
            if w._osm_applied != self.pending:
                self._apply(w, self.pending)
            w.after(POLL_MS, lambda: self._poll(w))
        except tk.TclError:
            pass

    def _apply(self, w, which):
        prov = PROVIDERS[which]
        w.set_tile_server(prov["url"], max_zoom=prov["max_zoom"])
        try:
            if w.zoom > prov["max_zoom"]:
                w.set_zoom(prov["max_zoom"])
        except Exception:
            pass
        old = getattr(w, "_osm_box", None)
        if old is not None:
            old.destroy()
        box = tk.Frame(w, bg="#f0f0f0")
        items = ([(prov["notice"], None)] if prov["notice"] else []) + prov["links"]
        for text, url in items:
            lbl = tk.Label(box, text=f" {text} ", bg="#f0f0f0", fg="#000000",
                           font=("Arial", 8), cursor="hand2" if url else "")
            lbl.pack(side="left")
            if url:
                lbl.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
        box.place(relx=1.0, rely=1.0, anchor="se")
        box.lift()
        w._osm_box = box
        w._osm_applied = which


class _RequestsShim:
    """Ersetzt das 'requests'-Modul in tkintermapview.map_widget."""
    def __init__(self, mgr):
        self._mgr = mgr
        self._is_osm_shim = True

    def __getattr__(self, name):          # exceptions, codes, ... -> echtes requests
        return getattr(requests, name)

    def get(self, url, **kwargs):
        return self._mgr.get(url, **kwargs)


def _pre_cache_limited(self):
    """Wie TkinterMapView.pre_cache (v1.29), aber Radius auf PRECACHE_MAX_RADIUS begrenzt."""
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
            for x in range(cx - radius, cx + radius + 1):
                for yy in (cy + radius, cy - radius):
                    if f"{zoom}{x}{yy}" not in self.tile_image_cache:
                        self.request_image(zoom, x, yy)
            for y in range(cy - radius, cy + radius + 1):
                for xx in (cx + radius, cx - radius):
                    if f"{zoom}{xx}{y}" not in self.tile_image_cache:
                        self.request_image(zoom, xx, y)
            radius += 1
        else:
            time.sleep(0.1)
        if len(self.tile_image_cache) > 10_000:      # RAM-Cache begrenzen wie im Original
            for key in list(self.tile_image_cache.keys())[:len(self.tile_image_cache) - 10_000]:
                self.tile_image_cache.pop(key, None)


# Eine gemeinsame Instanz pro Prozess (Hauptprogramm UND DFscope-Plugin teilen sich den
# Zustand, auch wenn osm_fix.py zweimal im Projekt liegt).
_mgr = getattr(_mw, "_osm_fix_mgr", None)
if _mgr is None:
    _mgr = _Manager()
    _mw._osm_fix_mgr = _mgr
    _mw.requests = _RequestsShim(_mgr)
    if hasattr(_mw.TkinterMapView, "pre_cache"):
        _mw.TkinterMapView.pre_cache = _pre_cache_limited

setup_map = _mgr.setup_map
