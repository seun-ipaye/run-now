"""Find running loops with the fewest traffic signals.

Approach: a loop is a rough triangle start -> A -> B -> start. We try
waypoint pairs in several directions, route each leg with a signal-penalized
shortest path, and keep the loop with the fewest signals whose length is
close to the target. Shortest paths from the start are computed once and
reused for the first and last legs (the walk network runs both ways).
"""
import math
from dataclasses import dataclass

import networkx as nx

BEARINGS = 12            # directions to try for the first waypoint
DETOUR = 1.3             # streets are ~30% longer than a straight line
TOLERANCE = 0.15         # accept loops within 15% of the target distance
REUSE_PENALTY = 3.0      # running a street twice costs 3x its length when routing
MAX_REPEAT = 0.15        # prefer loops that repeat at most 15% of their distance


@dataclass
class Loop:
    nodes: list[int]
    length_m: float
    signals: int
    signal_ids: list[int]
    overlap_m: float     # distance run twice (out-and-back sections)


def nearest_node(g: nx.DiGraph, lat: float, lon: float) -> int:
    # A linear scan is fast enough for ~200k nodes; an index can come later.
    cos = math.cos(math.radians(lat))
    return min(g.nodes, key=lambda n: (g.nodes[n]["lat"] - lat) ** 2
               + ((g.nodes[n]["lon"] - lon) * cos) ** 2)


def offset(lat: float, lon: float, dist_m: float, bearing_deg: float) -> tuple[float, float]:
    b = math.radians(bearing_deg)
    dlat = dist_m * math.cos(b) / 111_320
    dlon = dist_m * math.sin(b) / (111_320 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def evaluate(g: nx.DiGraph, nodes: list[int]) -> Loop:
    length = overlap = 0.0
    seen: set[frozenset] = set()
    for u, v in zip(nodes, nodes[1:]):
        d = g[u][v]["length"]
        length += d
        key = frozenset((u, v))
        if key in seen:
            overlap += d
        seen.add(key)
    # Each signalized intersection counts once, however many of its points we pass.
    ids = list(dict.fromkeys(g.nodes[n]["signal_id"] for n in nodes
                             if g.nodes[n]["signal_id"] is not None))
    start_signal = g.nodes[nodes[0]]["signal_id"]
    ids = [i for i in ids if i != start_signal]  # starting at a light isn't a stop
    return Loop(nodes, length, len(ids), ids, overlap)


def edges_of(path: list[int]) -> set[frozenset]:
    return {frozenset(e) for e in zip(path, path[1:])}


def avoid(used: set[frozenset]):
    """Edge weight that discourages streets already on the loop."""
    def weight(u, v, d):
        if frozenset((u, v)) in used:
            return d["weight"] + REUSE_PENALTY * d["length"]
        return d["weight"]
    return weight


def find_loop(g: nx.DiGraph, lat: float, lon: float, distance_m: float) -> Loop | None:
    start = nearest_node(g, lat, lon)
    s = g.nodes[start]
    radius = distance_m / 3 / DETOUR
    cutoff = distance_m  # no leg should be longer than the whole loop
    dist_from_start, path_from_start = nx.single_source_dijkstra(g, start, cutoff=cutoff, weight="weight")

    # Snap waypoints to reachable nodes only.
    reachable = list(path_from_start)
    cos = math.cos(math.radians(s["lat"]))

    def snap(plat: float, plon: float) -> int:
        return min(reachable, key=lambda n: (g.nodes[n]["lat"] - plat) ** 2
                   + ((g.nodes[n]["lon"] - plon) * cos) ** 2)

    candidates: list[Loop] = []
    for scale in (1.0, 0.8, 1.2):
        r = radius * scale
        for i in range(BEARINGS):
            bearing = i * 360 / BEARINGS
            a = snap(*offset(s["lat"], s["lon"], r, bearing))
            b = snap(*offset(s["lat"], s["lon"], r, bearing + 60))
            if a == start or b == start or a == b:
                continue
            out = path_from_start[a]
            try:
                used = edges_of(out)
                a_to_b = nx.dijkstra_path(g, a, b, weight=avoid(used))
                back = nx.dijkstra_path(g, b, start, weight=avoid(used | edges_of(a_to_b)))
            except nx.NetworkXNoPath:
                continue
            nodes = out + a_to_b[1:] + back[1:]
            if all(g.has_edge(u, v) for u, v in zip(nodes, nodes[1:])):
                candidates.append(evaluate(g, nodes))
        close = [c for c in candidates if abs(c.length_m - distance_m) <= TOLERANCE * distance_m]
        if close:
            break

    if not candidates:
        return None
    pool = close or candidates
    varied = [c for c in pool if c.overlap_m <= MAX_REPEAT * c.length_m]
    return min(varied or pool, key=lambda c: (c.signals, c.overlap_m, abs(c.length_m - distance_m)))
