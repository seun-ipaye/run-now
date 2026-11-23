"""Load Toronto's runnable street network from OpenStreetMap into
dbo.GraphNode and dbo.GraphEdge, then match traffic signals to nodes.

Uses OSMnx's "walk" network: streets, paths and footways a runner can use.
Each run replaces the whole network (nodes and edges) with a fresh copy.
Run etl.load_signals first so signals can be matched.

The OSM download is cached in data/cache/. Pass --refresh to fetch a fresh copy.

Run from the repo root:  .venv/bin/python -m etl.load_streets [--refresh]
"""
import csv
import subprocess
import sys
import time
from pathlib import Path

import osmnx as ox
from shapely.geometry import LineString
from sqlalchemy import text

from etl.db import get_engine

PLACE = "Toronto, Ontario, Canada"
ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
GRAPH_FILE = CACHE_DIR / "toronto-walk.graphml"
NODES_CSV = CACHE_DIR / "nodes.csv"
EDGES_CSV = CACHE_DIR / "edges.csv"
CONTAINER = "runnow-sql"
# Every node within this distance of a signal belongs to that signal, so
# sidewalks and crosswalks around a signalized intersection all count.
SIGNAL_MATCH_M = 25

ox.settings.cache_folder = str(CACHE_DIR / "osmnx")
ox.settings.log_console = False
# Keep the tags we need to drop indoor routes (PATH, malls, stations).
ox.settings.useful_tags_way = list(ox.settings.useful_tags_way) + ["indoor", "level"]

INDOOR_HIGHWAYS = {"corridor", "elevator"}


def first(value):
    """OSM tags can hold a list when ways are merged; keep the first."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def is_indoor(d: dict) -> bool:
    """True for segments a runner can't use outdoors: tunnels, indoor
    corridors, mall and station levels, and anything below ground."""
    if any(t == "yes" for t in as_list(d.get("tunnel"))):
        return True
    if any(i not in (None, "no") for i in as_list(d.get("indoor"))):
        return True
    if any(h in INDOOR_HIGHWAYS for h in as_list(d.get("highway"))):
        return True
    for level in as_list(d.get("level")):
        try:
            if float(str(level).split(";")[0]) < 0:
                return True
        except ValueError:
            pass
    return False


def drop_indoor(graph):
    indoor = [(u, v, k) for u, v, k, d in graph.edges(keys=True, data=True) if is_indoor(d)]
    graph.remove_edges_from(indoor)
    graph = ox.truncate.largest_component(graph, strongly=False)
    print(f"  Dropped {len(indoor):,} indoor or underground segments")
    return graph


def get_graph(refresh: bool):
    if GRAPH_FILE.exists() and not refresh:
        print(f"Using cached network {GRAPH_FILE.relative_to(ROOT)} (pass --refresh to re-download)")
        graph = ox.load_graphml(GRAPH_FILE)
    else:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Downloading the walk network for {PLACE} from OpenStreetMap.")
        print("This usually takes 5-15 minutes...", flush=True)
        graph = ox.graph_from_place(PLACE, network_type="walk", simplify=True, retain_all=False)
        ox.save_graphml(graph, GRAPH_FILE)
    return drop_indoor(graph)


def write_csvs(graph) -> tuple[int, int]:
    """Write tab-separated files for SQL Server's BULK INSERT."""
    with open(NODES_CSV, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        for node_id, d in graph.nodes(data=True):
            w.writerow([node_id, d["y"], d["x"], d.get("street_count") or ""])
    n_edges = 0
    with open(EDGES_CSV, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        for u, v, d in graph.edges(data=True):
            geom = d.get("geometry")
            if geom is None:
                a, b = graph.nodes[u], graph.nodes[v]
                geom = LineString([(a["x"], a["y"]), (b["x"], b["y"])])
            name = first(d.get("name")) or ""
            w.writerow([
                u, v, first(d.get("osmid")) or "",
                str(name).replace("\t", " ")[:200],
                first(d.get("highway")) or "",
                round(float(d["length"]), 2),
                geom.wkt,
            ])
            n_edges += 1
    return graph.number_of_nodes(), n_edges


def copy_into_container(path: Path) -> str:
    target = f"/tmp/{path.name}"
    subprocess.run(["docker", "cp", str(path), f"{CONTAINER}:{target}"], check=True)
    return target


LOAD_SQL = """
SET XACT_ABORT ON;
BEGIN TRAN;

CREATE TABLE #Node (NodeId BIGINT, Lat FLOAT, Lon FLOAT, StreetCount TINYINT NULL);
CREATE TABLE #Edge (FromNodeId BIGINT, ToNodeId BIGINT, OsmWayId BIGINT NULL,
                    StreetName VARCHAR(400) COLLATE Latin1_General_100_CI_AS_SC_UTF8 NULL,
                    HighwayType VARCHAR(50) NULL,
                    LengthM FLOAT, Wkt VARCHAR(MAX));

BULK INSERT #Node FROM '{nodes}' WITH (FIELDTERMINATOR = '\\t', ROWTERMINATOR = '0x0a', KEEPNULLS);
BULK INSERT #Edge FROM '{edges}' WITH (FIELDTERMINATOR = '\\t', ROWTERMINATOR = '0x0a', KEEPNULLS);

DELETE FROM dbo.GraphEdge;
DELETE FROM dbo.GraphNode;

INSERT dbo.GraphNode (NodeId, Location, StreetCount)
SELECT NodeId, geography::Point(Lat, Lon, 4326), StreetCount FROM #Node;

INSERT dbo.GraphEdge (FromNodeId, ToNodeId, OsmWayId, StreetName, HighwayType, LengthM, Geometry)
SELECT FromNodeId, ToNodeId, OsmWayId, NULLIF(StreetName, ''), NULLIF(HighwayType, ''), LengthM,
       geography::STGeomFromText(Wkt, 4326).MakeValid()
FROM #Edge;

-- Street names are read as UTF-8 bytes (CODEPAGE is not supported on Linux),
-- and convert to NVARCHAR when inserted above.
-- Attach every node within the match distance to its nearest signal.
UPDATE n SET SignalId = m.SignalId
FROM dbo.GraphNode n
JOIN (
    SELECT g.NodeId, s.SignalId,
           ROW_NUMBER() OVER (PARTITION BY g.NodeId ORDER BY g.Location.STDistance(s.Location)) AS rn
    FROM dbo.TrafficSignal s
    JOIN dbo.GraphNode g WITH (INDEX(SIX_GraphNode_Location))
      ON g.Location.STDistance(s.Location) <= {match_m}
) m ON m.NodeId = n.NodeId AND m.rn = 1;

COMMIT;
"""


def main() -> None:
    start = time.time()
    graph = get_graph(refresh="--refresh" in sys.argv)
    print("Preparing files for the database...", flush=True)
    n_nodes, n_edges = write_csvs(graph)
    del graph
    print(f"  {n_nodes:,} intersections, {n_edges:,} street segments")

    nodes_path = copy_into_container(NODES_CSV)
    edges_path = copy_into_container(EDGES_CSV)
    print("Loading into SQL Server and matching signals (a few minutes)...", flush=True)
    sql = LOAD_SQL.format(nodes=nodes_path, edges=edges_path, match_m=SIGNAL_MATCH_M)
    try:
        with get_engine().begin() as conn:
            conn.exec_driver_sql(sql)
            stats = conn.execute(text("""
                SELECT (SELECT COUNT(*) FROM dbo.GraphNode),
                       (SELECT COUNT(*) FROM dbo.GraphEdge),
                       (SELECT COUNT(DISTINCT SignalId) FROM dbo.GraphNode),
                       (SELECT COUNT(*) FROM dbo.TrafficSignal)
            """)).one()
    finally:  # these files are large; remove them even if the load fails
        subprocess.run(["docker", "exec", "-u", "root", CONTAINER, "rm", "-f", nodes_path, edges_path], check=False)
        NODES_CSV.unlink(missing_ok=True)
        EDGES_CSV.unlink(missing_ok=True)

    nodes, edges, matched, signals = stats
    print(f"Loaded {nodes:,} nodes and {edges:,} edges.")
    print(f"Matched {matched:,} of {signals:,} signals to an intersection (within {SIGNAL_MATCH_M} m).")
    print(f"Done in {(time.time() - start) / 60:.1f} min.")


if __name__ == "__main__":
    main()
