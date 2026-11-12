# osm_fix.py – eigener User-Agent für OSM-Kachelabrufe (Tile Usage Policy)
import requests
import tkintermapview.map_widget as _mw

USER_AGENT = "AMWaveSynthPropagationSimulator/1.0 (https://github.com/radiolab81/AMWaveSynthPropagationSimulator)"

class _RequestsShim:
    """Reicht alles an requests weiter, setzt aber bei get() den User-Agent."""
    def __getattr__(self, name):
        return getattr(requests, name)

    @staticmethod
    def get(url, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        headers["User-Agent"] = USER_AGENT
        return requests.get(url, headers=headers, **kwargs)

_mw.requests = _RequestsShim()