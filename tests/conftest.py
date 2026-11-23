"""Small hand-built street networks for tests. No database needed."""
import math

import networkx as nx
import pytest

from api.graph import set_weights

ORIGIN = (43.65, -79.40)  # downtown Toronto
SPACING_M = 100


def grid(size: int = 21, signals: dict[tuple[int, int], int] | None = None) -> nx.DiGraph:
    """A size x size street grid, 100 m between intersections, two-way streets.
    Node ids are row * 1000 + col. `signals` maps (row, col) to a signal id."""
    signals = signals or {}
    g = nx.DiGraph()
    lat0, lon0 = ORIGIN
    dlat = SPACING_M / 111_320
    dlon = SPACING_M / (111_320 * math.cos(math.radians(lat0)))
    for r in range(size):
        for c in range(size):
            g.add_node(r * 1000 + c, lat=lat0 + r * dlat, lon=lon0 + c * dlon,
                       signal_id=signals.get((r, c)))
    for r in range(size):
        for c in range(size):
            for nr, nc in ((r + 1, c), (r, c + 1)):
                if nr < size and nc < size:
                    a, b = r * 1000 + c, nr * 1000 + nc
                    g.add_edge(a, b, length=SPACING_M, name=None)
                    g.add_edge(b, a, length=SPACING_M, name=None)
    set_weights(g)
    return g


def node_latlon(g: nx.DiGraph, node: int) -> tuple[float, float]:
    return g.nodes[node]["lat"], g.nodes[node]["lon"]


@pytest.fixture
def plain_grid() -> nx.DiGraph:
    return grid()
