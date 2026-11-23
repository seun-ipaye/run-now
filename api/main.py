"""RunNow API.

Run from the repo root:  .venv/bin/uvicorn api.main:app --reload
Then open http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from api.graph import load_graph
from api.routing import find_loop

state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["graph"] = load_graph()
    yield
    state.clear()


app = FastAPI(title="RunNow", lifespan=lifespan)


@app.get("/loop")
def loop(
    lat: float = Query(..., ge=43.5, le=43.9, description="Start latitude (Toronto)"),
    lon: float = Query(..., ge=-79.7, le=-79.1, description="Start longitude (Toronto)"),
    km: float = Query(..., gt=0.5, le=30, description="Target loop distance in km"),
):
    g = state["graph"]
    result = find_loop(g, lat, lon, km * 1000)
    if result is None:
        raise HTTPException(404, "No loop found from this start point.")
    coords = [[g.nodes[n]["lon"], g.nodes[n]["lat"]] for n in result.nodes]
    # One point per signal: the first place the route reaches it.
    first_hit = {}
    for n in result.nodes:
        sid = g.nodes[n]["signal_id"]
        if sid in result.signal_ids and sid not in first_hit:
            first_hit[sid] = [g.nodes[n]["lon"], g.nodes[n]["lat"]]
    signal_points = list(first_hit.values())
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": {
            "distance_km": round(result.length_m / 1000, 2),
            "target_km": km,
            "signals": result.signals,
            "signal_locations": signal_points,
            "repeated_km": round(result.overlap_m / 1000, 2),
        },
    }
