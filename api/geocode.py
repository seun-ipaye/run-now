"""Turn an address into a start point, using OpenStreetMap's Nominatim service.

Nominatim's usage policy allows at most one request per second and asks for
an identifying User-Agent, so lookups go through this server (never straight
from browsers), are rate-limited, and repeated searches are served from memory.
Results are limited to Toronto.
"""
import json
import threading
import time
import urllib.parse
import urllib.request
from functools import lru_cache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "RunNow/1.0 (running loop planner)"
# Toronto's bounding box: west, north, east, south.
TORONTO_VIEWBOX = "-79.64,43.86,-79.11,43.58"
MAX_RESULTS = 5

_lock = threading.Lock()
_last_request = 0.0


def _fetch(query: str) -> list[dict]:
    global _last_request
    params = urllib.parse.urlencode({
        "q": query, "format": "jsonv2", "limit": MAX_RESULTS,
        "countrycodes": "ca", "viewbox": TORONTO_VIEWBOX, "bounded": 1,
    })
    req = urllib.request.Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT})
    with _lock:  # one request per second, across all users
        wait = 1.0 - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.load(resp)
        finally:
            _last_request = time.monotonic()


@lru_cache(maxsize=1000)
def _search_cached(query: str) -> tuple[tuple[str, float, float], ...]:
    return tuple((r["display_name"], float(r["lat"]), float(r["lon"])) for r in _fetch(query))


def search(query: str) -> list[dict]:
    """Up to five matching places in Toronto: {"name", "lat", "lon"}."""
    key = " ".join(query.lower().split())
    return [{"name": short_name(name), "lat": lat, "lon": lon}
            for name, lat, lon in _search_cached(key)]


def short_name(display_name: str) -> str:
    """Nominatim names run long ('100, Queen Street West, ..., Ontario, M5H 2N2,
    Canada'); keep the first few parts, which are the useful ones."""
    parts = [p.strip() for p in display_name.split(",")]
    drop = {"Canada", "Ontario", "Golden Horseshoe", "Toronto"}
    kept = [p for p in parts if p not in drop]
    return ", ".join(kept[:4])
