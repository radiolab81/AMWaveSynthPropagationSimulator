# Map tiles: background and configuration

This page explains how the simulator loads its map tiles, why it does it the way it does,
and what you can change in `osm_fix.py`. You do **not** need any of this to use the
simulator: the defaults work out of the box and need no API key.

*Provider conditions below were checked on 13 Nov 2026. They can change at any time, so
please re-read the linked policies now and then.*

## 1. Why there is special tile handling at all

The map widget (`tkintermapview`) downloads small 256x256 px images ("tiles") from a tile
server. The public OpenStreetMap tile servers are run by volunteers and paid by donations.
Everybody may use them, but only under the
[Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/). Apps that ignore
it get blocked, sometimes without warning.

`tkintermapview` 1.29 does several things the policy does not like, so `osm_fix.py` patches
them when it is imported (it must be the first import, before `tkintermapview`):

| Problem in the library | What `osm_fix.py` does |
|---|---|
| Sends the generic User-Agent `TkinterMapView` | Sends its own User-Agent with the project URL |
| Keeps tiles only in RAM, re-downloads after every start | On-disk cache (SQLite) |
| Starts 25 download threads (policy: max. 2 connections) | Limits to 2 simultaneous downloads |
| Prefetches up to radius 8 (17x17 tiles) | Limits prefetch to radius 2 |
| Uses the subdomain `a.tile.openstreetmap.org` | Uses `tile.openstreetmap.org` |
| Shows no attribution | Shows the required attribution with links |

## 2. What you see in the program

* **Drop-down (top right of each map):** *OpenStreetMap* or *OpenTopoMap (openmaps.fr)*.
  The choice applies to all maps (main window and DFscope) and is saved in
  `provider.json` in the cache folder.
* **Attribution (bottom right):** clickable links, as required by the providers.
  For openmaps.fr this includes a donation link.
* **Fallback notice:** if the chosen server cannot be used, the map switches to the other
  one and shows "Ersatzkarte - ... nicht verfuegbar" next to the attribution.

## 3. Automatic fallback

| Situation | Reaction |
|---|---|
| Chosen server answers HTTP 403 or 429 (blocked / too many requests) | Switch to the other provider immediately; the current tile is fetched from it right away |
| HTTP 5xx or timeouts | After 3 failures in a row, **and only if the other provider answers**. If both fail, your internet is probably down and nothing is switched |
| While in fallback mode | No requests to the chosen server for 1 h |
| After the waiting time | **One** tile is requested from the chosen server as a test. Success: switch back. Failure: wait twice as long (2 h, 4 h ... max. 24 h) |
| You pick a provider in the drop-down | Fresh start: the blocked/failed state is reset |

Worker threads never touch the GUI. They only record the wish to switch; a timer in the Tk
main thread (every 500 ms) applies it.

**Test it yourself:** put an invalid path or host into `PROVIDERS["osm"]["url"]` that answers
with an error and watch the map switch. Remember to restore the URL afterwards and, if you
like, delete the cache file so that cached tiles do not hide the effect.

## 4. Provider conditions in short

| | OpenStreetMap | openmaps.fr (OpenTopoMap-R) |
|---|---|---|
| URL | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | `https://tile.openmaps.fr/opentopomap/{z}/{x}/{y}.png` |
| API key | none | none |
| Max. zoom in this project | 19 | 17 (assumption, see section 8) |
| Use | no heavy use; access may be blocked | free for non-commercial projects, **limit 500,000 tiles per month**, best effort, no SLA |
| Attribution | "(c) OpenStreetMap contributors", linked | style attribution, donation link, OpenStreetMap attribution |
| Must | own User-Agent, cache, max. 2 connections | own User-Agent, no bulk download, no prefetch feature |

Policies: [OSM](https://operations.osmfoundation.org/policies/tiles/),
[openmaps.fr](https://openmaps.fr/tile-usage-policy.html).

Why not CARTO, MapTiler, Stadia and others? They need an API key (CARTO now shows a
watermark without one) or are free only for local development. They can be added if you
have a key, see section 7.

## 5. Tile cache

Cached tiles live in `~/.cache/AMWaveSynthPropagationSimulator/osm_tiles.sqlite`
(change the folder with the environment variable `AMWAVE_TILE_CACHE`). A tile from the cache
costs the server nothing, which is the whole point of the policy.

Settings at the top of `osm_fix.py`:

| Setting | Default | Meaning |
|---|---|---|
| `CACHE_RESPECT_HEADERS` | `True` | **Variant A:** the server says how long a tile is valid (`Cache-Control`/`Expires`). After that the program asks again with an ETag; if nothing changed the server answers "304 Not Modified" and the tile is not sent again |
| `CACHE_FALLBACK_DAYS` | `7` | Variant A: validity if the server sends no headers |
| `CACHE_FIXED_DAYS` | `30` | **Variant B** (`CACHE_RESPECT_HEADERS = False`): every tile is valid for this many days, headers are ignored. Fewer requests, but map changes appear later. The code enforces at least 7 days (policy minimum) |
| `CACHE_STALE_IF_ERROR` | `True` | Serve an expired tile if the refresh fails (no network, server error). Whether this also applies to a 403 block depends on the `requests-cache` version and is untested |
| `CACHE_PURGE_OLDER_THAN_DAYS` | `90` | Delete tiles older than this at start so the file does not grow forever (`0` = never) |

Variant A is recommended because it is what the OSM policy prefers. Choose variant B if you
use the simulator mostly at fixed places and want maximum offline comfort.

To start with a clean cache, close the program and delete `osm_tiles.sqlite`.

## 6. Other settings

| Setting | Default | Meaning |
|---|---|---|
| `DEFAULT_PROVIDER` | `"osm"` | Provider on the very first start |
| `FALLBACK_OF` | `osm -> topo`, `topo -> osm` | Which provider takes over if the chosen one fails |
| `MAX_CONNECTIONS` | `2` | Simultaneous downloads (OSM policy maximum) |
| `PRECACHE_MAX_RADIUS` | `2` | Prefetch radius in tiles around the map center (library default: 8) |
| `TIMEOUT` | `(5, 15)` | Connect / read timeout in seconds |
| `SOFT_FAIL_LIMIT` | `3` | Failures in a row before switching (HTTP 5xx / timeouts) |
| `RETRY_BASE`, `RETRY_MAX` | `3600`, `86400` | First and maximum waiting time before the chosen provider is tested again |

## 7. Adding another provider

1. Read its terms of use and note the required attribution.
2. Add an entry to `PROVIDERS` in `osm_fix.py` with `label`, `url`, `max_zoom` and `links`
   (attribution text and URL). If a key is needed, it is part of the URL.
3. Add it to `FALLBACK_OF` if it should act as a fallback.
4. Keep the User-Agent unchanged. Never reuse the User-Agent of another application.


Map data (c) OpenStreetMap contributors, available under the Open Database Licence (ODbL).
