"""The in-memory routing graph.

The graph is built from the RunNow database and saved to data/graph/, which
is committed to git. The deployed API only reads that file, so production
needs no database. After re-running the ETL loaders, rebuild it with:

    python -m api.graph

The graph is a NetworkX DiGraph. Each node has lat, lon and signal_id (None
if no traffic signal is within 25 m); each edge has length (metres), name, and weight = length + a penalty
when the edge enters a signalized intersection. Moving between points of the
same intersection (sidewalk to crosswalk) is not charged again.
"""
import pickle
from pathlib import Path

import networkx as nx

SIGNAL_PENALTY_M = 500  # stopping at a light "costs" as much as 500 m of extra running
GRAPH_FILE = Path(__file__).resolve().parent.parent / "data" / "graph" / "toronto.pickle"


def build_graph() -> nx.DiGraph:
    # Imported here so the deployed API doesn't need the database packages.
    from sqlalchemy import text

    from etl.db import get_engine

    g = nx.DiGraph()
    with get_engine().connect() as conn:
        for node_id, lat, lon, signal_id in conn.execute(text(
            "SELECT NodeId, Location.Lat, Location.Long, SignalId FROM dbo.GraphNode"
        )):
            g.add_node(node_id, lat=lat, lon=lon, signal_id=signal_id)
        for u, v, length, name in conn.execute(text(
            "SELECT FromNodeId, ToNodeId, LengthM, StreetName FROM dbo.GraphEdge"
        )):
            # Keep the shortest edge when two segments join the same nodes.
            if g.has_edge(u, v) and g[u][v]["length"] <= length:
                continue
            g.add_edge(u, v, length=length, name=name)
    set_weights(g)
    return g


def set_weights(g: nx.DiGraph) -> None:
    """Weight = length, plus the signal penalty when an edge enters a signalized
    intersection from outside it."""
    for u, v, d in g.edges(data=True):
        sv = g.nodes[v]["signal_id"]
        enters_signal = sv is not None and sv != g.nodes[u]["signal_id"]
        d["weight"] = d["length"] + (SIGNAL_PENALTY_M if enters_signal else 0)


def load_graph() -> nx.DiGraph:
    if not GRAPH_FILE.exists():
        raise FileNotFoundError(
            f"{GRAPH_FILE} is missing. Load the data, then run: python -m api.graph"
        )
    with open(GRAPH_FILE, "rb") as f:
        return pickle.load(f)


def save_graph(g: nx.DiGraph) -> None:
    GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_FILE, "wb") as f:
        pickle.dump(g, f, protocol=pickle.HIGHEST_PROTOCOL)


if __name__ == "__main__":
    graph = build_graph()
    save_graph(graph)
    size_mb = GRAPH_FILE.stat().st_size / 1e6
    print(f"Saved {graph.number_of_nodes():,} nodes and {graph.number_of_edges():,} edges "
          f"to {GRAPH_FILE.relative_to(Path.cwd())} ({size_mb:.0f} MB). Commit this file to deploy it.")
