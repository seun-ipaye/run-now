"""Load City of Toronto traffic signals into dbo.TrafficSignal.

Source: Toronto Open Data, "Traffic Signals Tabular" (WGS84 CSV).
Re-running updates existing signals (matched on the city's PX number)
and adds new ones. Signals no longer in the file are left in place.

The download is cached in data/raw/. Pass --refresh to fetch a fresh copy.

Run from the repo root:  .venv/bin/python -m etl.load_signals [--refresh]
"""
import json
import sys
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import text

from etl.db import get_engine

SOURCE_URL = (
    "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    "1a106e88-f734-4179-b3fe-d690a6187a71/resource/"
    "aeda8fd7-e1d6-4d34-b62a-a7d6be10cc96/download/traffic-signal-4326.csv"
)

CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "raw" / "traffic-signal-4326.csv"

UPSERT = text("""
MERGE dbo.TrafficSignal AS t
USING (SELECT :source_id AS SourceId) AS s ON t.SourceId = s.SourceId
WHEN MATCHED THEN UPDATE SET
    SignalType = :signal_type, MainStreet = :main, CrossStreet = :cross,
    Location = geography::Point(:lat, :lon, 4326), LoadedAt = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (SourceId, SignalType, MainStreet, CrossStreet, Location)
    VALUES (:source_id, :signal_type, :main, :cross, geography::Point(:lat, :lon, 4326));
""")


def clean(value):
    """The city file writes missing values as the text 'None'."""
    if pd.isna(value) or str(value).strip() in ("", "None"):
        return None
    return str(value).strip()


def to_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for rec in df.itertuples(index=False):
        coords = json.loads(rec.geometry)["coordinates"]
        lon, lat = coords[0] if coords and isinstance(coords[0], list) else coords
        midblock = clean(rec.MIDBLOCK_ROUTE)
        rows.append({
            "source_id": str(rec.PX).strip(),
            "signal_type": "Midblock" if midblock else "Intersection",
            "main": clean(rec.MAIN_STREET),
            "cross": midblock or clean(rec.SIDE1_STREET),
            "lat": float(lat),
            "lon": float(lon),
        })
    return rows


def download(refresh: bool) -> Path:
    """Fetch the city file, showing progress. The city server can be slow."""
    if CACHE_FILE.exists() and not refresh:
        print(f"Using cached file {CACHE_FILE.relative_to(Path.cwd())} (pass --refresh to re-download)")
        return CACHE_FILE
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading traffic signals from Toronto Open Data...", flush=True)
    partial = CACHE_FILE.with_suffix(".part")
    with requests.get(SOURCE_URL, stream=True, timeout=(10, 60)) as resp:
        resp.raise_for_status()
        done = 0
        with open(partial, "wb") as f:
            for chunk in resp.iter_content(64 * 1024):
                f.write(chunk)
                done += len(chunk)
                print(f"\r  {done / 1e6:.1f} MB", end="", flush=True)
    print()
    partial.replace(CACHE_FILE)  # only keep complete downloads
    return CACHE_FILE


def main() -> None:
    path = download(refresh="--refresh" in sys.argv)
    df = pd.read_csv(path, dtype={"PX": str})
    print(f"Writing {len(df)} signals to the database...", flush=True)
    rows = to_rows(df)

    # Sanity check: every point should fall inside the Toronto area.
    bad = [r for r in rows if not (43.5 < r["lat"] < 43.9 and -79.7 < r["lon"] < -79.1)]
    if bad:
        raise SystemExit(f"{len(bad)} signals fall outside Toronto, e.g. {bad[0]}")

    with get_engine().begin() as conn:
        conn.execute(UPSERT, rows)
        total = conn.execute(text("SELECT COUNT(*) FROM dbo.TrafficSignal")).scalar()
    print(f"Loaded {len(rows)} signals from the city file. Table now holds {total}.")


if __name__ == "__main__":
    main()
