# RunNow

Running loops in Toronto with the fewest red lights.

Pick a start point and a distance, and RunNow returns a loop that avoids signalized intersections.

## Stack

SQL Server 2022 (spatial data) · Python ETL (Pandas, OSMnx, SQLAlchemy) · NetworkX routing · FastAPI · Leaflet map page (Angular front end planned)

## Layout

```
db/     T-SQL schema and indexes (numbered, applied in order by db/apply.sh)
etl/    one loader per dataset, plus the shared database connection
api/    FastAPI service, routing graph and loop finder
web/    map page served by the API
tests/  pytest suite (no database needed)
data/   downloaded files and caches (git-ignored)
```

## Local setup

Requires Docker Desktop and Python 3.13.

### 1. Database

On Apple Silicon, turn on **Docker Desktop → Settings → General → Use Rosetta for x86_64/amd64 emulation**, because SQL Server has no ARM image.

```bash
cp .env.example .env    # then set a strong MSSQL_SA_PASSWORD
docker compose up -d
docker compose ps       # wait for "healthy"
./db/apply.sh           # creates the RunNow database, tables and indexes
```

`docker-compose.yml` pins SQL Server to `2022-CU14-ubuntu-22.04`. Newer images (`2022-latest`) crash under Rosetta on macOS 15 with "file archive is invalid", and Docker's fallback emulator (Rosetta off) crashes with a segmentation fault. Keep the pin unless you've confirmed a newer image starts.

The container runs SQL Server **Developer Edition**, which is licensed for development and testing only. A public deployment needs a production-licensed database, such as Azure SQL Database.

### 2. Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### 3. Load data

Run the loaders in this order. Signals must exist before streets, because the streets loader links signals to intersections.

```bash
python -m etl.load_signals    # ~30 s
python -m etl.load_streets    # 5-15 min the first time, ~2-4 min after that
```

Both loaders keep their downloads in `data/` and reuse them on later runs. Pass `--refresh` to download fresh data.

### 4. Run

```bash
uvicorn api.main:app --reload
```

Open http://localhost:8000 for the map, or http://localhost:8000/docs for the API. The first start builds the routing graph from the database and caches it in `data/cache/routing-graph.pickle`. **Delete that file after re-running a loader** so the API picks up the new data.

### Tests

```bash
pytest
```

The tests use small hand-built street networks, so they run in about a second with no database or downloads.

## API

`GET /loop?lat=43.6465&lon=-79.4637&km=5` returns a GeoJSON `Feature`: the loop as a `LineString`, plus `distance_km`, `target_km`, `signals` (how many signalized intersections it passes), `signal_locations` and `repeated_km` (distance run twice). Start points must be inside Toronto, and distances between 0.5 and 30 km.

## How routing works

A loop is a rough triangle: out to waypoint A, across to waypoint B, and back to the start. The finder tries 12 directions at three sizes. It routes each leg with a shortest path where every traffic light costs as much as 500 m of extra running, and later legs avoid streets the loop already used. It keeps the loop with the fewest lights that lands within 15% of the requested distance and repeats at most 15% of its length.

## Data

| Dataset | Source | Table |
|---|---|---|
| Traffic signals | [City of Toronto Open Data, Traffic Signals Tabular](https://open.toronto.ca/dataset/traffic-signals-tabular/) | `TrafficSignal` |
| Streets, paths, footways | [OpenStreetMap](https://www.openstreetmap.org/) via OSMnx's `walk` network | `GraphNode`, `GraphEdge` |

## Data limits

- **Only traffic signals count as stops.** Pedestrian crossovers and traffic beacons are not loaded, since drivers stop for runners there. Stop signs are not in the data.
- **A signal covers every street point within 25 m**, so sidewalks and crosswalks at a signalized intersection all count as that one signal. About 60 of 2,564 signals (mostly mid-block crossings) have no street point within 25 m and are never counted.
- **Indoor and underground routes are excluded**: tunnels, indoor corridors, elevators, and anything tagged indoor or below ground level in OpenStreetMap, which removes the PATH, malls and station concourses.
- **Street data is only as good as OpenStreetMap.** Missing or mis-tagged paths change which loops are possible.
- **Loops usually run 5-10% longer than requested**, and in areas where busy roads have signals at every crossing, some lights can't be avoided.
- **Signals the city removes stay in the table**, because the signals loader adds and updates but never deletes. The streets loader replaces the whole network on each run.
