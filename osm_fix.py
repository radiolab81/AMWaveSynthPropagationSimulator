# osm_fix.py - OSM Tile Usage Policy (https://operations.osmfoundation.org/policies/tiles/)
#
# Wird als ALLERERSTER Import geladen (import osm_fix) und sorgt fuer:
#   * eigenen, stabilen User-Agent (statt "TkinterMapView" der Bibliothek)
#   * HTTP-Cache auf Platte (Cache-Control/Expires/ETag, Fallback 7 Tage,
#     Conditional Requests bei abgelaufenen Kacheln) via requests-cache
# und stellt setup_map(map_widget) bereit:
#   * korrekte Tile-URL (https://tile.openstreetmap.org/{z}/{x}/{y}.png)
#   * sichtbare Attribution "(c) OpenStreetMap contributors" + "Report a map issue"
import io
import os
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
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_MAX_ZOOM = 19
ATTRIBUTION = "\u00a9 OpenStreetMap contributors"
COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
FIXTHEMAP_URL = "https://www.openstreetmap.org/fixthemap"
MIN_CACHE = timedelta(days=7)   # Policy: mindestens 7 Tage, falls Header nicht lesbar
MAX_CONNECTIONS = 2             # Policy: max. 2 gleichzeitige Download-Verbindungen
PRECACHE_MAX_RADIUS = 2         # tkintermapview-Original: 8 (=17x17 Kacheln); hier nur moderates Look-ahead

CACHE_DIR = Path(os.environ.get("AMWAVE_TILE_CACHE",
                 Path.home() / ".cache" / "AMWaveSynthPropagationSimulator"))


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
        cache_name=str(CACHE_DIR / "osm_tiles"),
        backend="sqlite",
        cache_control=True,          # Cache-Control / Expires / ETag auswerten
        expire_after=MIN_CACHE,      # Fallback, wenn der Server keine Header liefert
        allowable_codes=(200,),      # Fehlerseiten (403 ...) nie cachen
        allowable_methods=("GET",),
        stale_if_error=False,
    )


_session = _make_session()
_net_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)   # tkintermapview startet 25 Loader-Threads!


class _Response:
    """Wie requests.Response, aber .raw ist seekbar (fuer PIL.Image.open)."""
    def __init__(self, resp):
        self._resp = resp
        self.raw = io.BytesIO(resp.content)

    def __getattr__(self, name):
        return getattr(self._resp, name)


class _RequestsShim:
    """Ersetzt das 'requests'-Modul in tkintermapview.map_widget.
    get() laeuft ueber die gecachte Session und setzt den eigenen User-Agent."""
    def __getattr__(self, name):          # exceptions, codes, ... -> echtes requests
        return getattr(requests, name)

    @staticmethod
    def get(url, **kwargs):
        kwargs.pop("stream", None)
        headers = dict(kwargs.pop("headers", None) or {})
        headers["User-Agent"] = USER_AGENT
        with _net_slots:
            return _Response(_session.get(url, headers=headers, **kwargs))


_mw.requests = _RequestsShim()


def _pre_cache_limited(self):
    """Wie TkinterMapView.pre_cache (v1.29), aber Radius auf PRECACHE_MAX_RADIUS begrenzt
    (Original: 8). Wird vor der Widget-Erzeugung gepatcht; der Thread startet erst im __init__."""
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


if hasattr(_mw.TkinterMapView, "pre_cache"):
    _mw.TkinterMapView.pre_cache = _pre_cache_limited


def _open(url):
    return lambda _e=None: webbrowser.open(url)


def setup_map(map_widget):
    """Nach TkinterMapView(...) aufrufen: Tile-URL + sichtbare Attribution."""
    if hasattr(map_widget, "set_user_agent"):      # tkintermapview >= 1.32
        map_widget.set_user_agent(USER_AGENT)
    map_widget.set_tile_server(TILE_URL, max_zoom=TILE_MAX_ZOOM)

    box = tk.Frame(map_widget, bg="#f0f0f0")
    for text, url in ((ATTRIBUTION, COPYRIGHT_URL), ("Report a map issue", FIXTHEMAP_URL)):
        lbl = tk.Label(box, text=f" {text} ", bg="#f0f0f0", fg="#000000",
                       font=("Arial", 8), cursor="hand2")
        lbl.pack(side="left")
        lbl.bind("<Button-1>", _open(url))
    box.place(relx=1.0, rely=1.0, anchor="se")
    box.lift()
    map_widget._osm_attribution_box = box          # Referenz halten
    return box
