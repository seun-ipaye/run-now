import pytest

from api.routing import TOLERANCE, evaluate, find_loop, nearest_node
from tests.conftest import grid, node_latlon


def test_nearest_node_snaps_to_closest_intersection(plain_grid):
    lat, lon = node_latlon(plain_grid, 5005)
    assert nearest_node(plain_grid, lat + 0.0001, lon - 0.0001) == 5005


def test_evaluate_measures_length_and_repeats(plain_grid):
    # Out two blocks and straight back: 400 m, half of it repeated.
    loop = evaluate(plain_grid, [0, 1, 2, 1, 0])
    assert loop.length_m == 400
    assert loop.overlap_m == 200


def test_evaluate_counts_each_signal_once_across_its_points():
    g = grid(size=5, signals={(0, 1): 7, (0, 2): 7})  # one intersection, two points
    loop = evaluate(g, [0, 1, 2, 3, 1003, 1002, 1001, 1000, 0])
    assert loop.signals == 1
    assert loop.signal_ids == [7]


def test_evaluate_counts_a_signal_passed_twice_once():
    g = grid(size=5, signals={(0, 1): 7})
    loop = evaluate(g, [0, 1, 2, 1, 0])
    assert loop.signals == 1


def test_evaluate_ignores_a_signal_at_the_start():
    g = grid(size=5, signals={(0, 0): 7})
    loop = evaluate(g, [0, 1, 1001, 1000, 0])
    assert loop.signals == 0


def test_find_loop_returns_a_closed_loop_near_the_target(plain_grid):
    start = 10010
    loop = find_loop(plain_grid, *node_latlon(plain_grid, start), 1600)
    assert loop is not None
    assert loop.nodes[0] == loop.nodes[-1] == start
    assert all(plain_grid.has_edge(u, v) for u, v in zip(loop.nodes, loop.nodes[1:]))
    assert abs(loop.length_m - 1600) <= TOLERANCE * 1600


def test_find_loop_avoids_signals_when_it_can():
    # Every intersection in the east half has a light; the west half has none.
    signals = {(r, c): r * 100 + c for r in range(21) for c in range(12, 21)}
    g = grid(signals=signals)
    loop = find_loop(g, *node_latlon(g, 10006), 1600)
    assert loop.signals == 0


def test_find_loop_avoids_doubling_back(plain_grid):
    loop = find_loop(plain_grid, *node_latlon(plain_grid, 10010), 2000)
    assert loop.overlap_m <= 0.15 * loop.length_m


@pytest.mark.parametrize("km", [1, 2, 3])
def test_find_loop_handles_several_distances(plain_grid, km):
    loop = find_loop(plain_grid, *node_latlon(plain_grid, 10010), km * 1000)
    assert loop is not None
    assert abs(loop.length_m - km * 1000) <= TOLERANCE * km * 1000


def test_avoid_makes_used_streets_more_expensive_both_ways(plain_grid):
    from api.routing import REUSE_PENALTY, avoid, edges_of
    weight = avoid(edges_of([0, 1]))
    assert weight(0, 1, plain_grid[0][1]) == 100 + REUSE_PENALTY * 100
    assert weight(1, 0, plain_grid[1][0]) == 100 + REUSE_PENALTY * 100  # same street, other way
    assert weight(1, 2, plain_grid[1][2]) == 100


def test_return_leg_takes_a_new_street_over_a_slightly_shorter_used_one():
    import networkx as nx
    from api.routing import avoid, edges_of
    from api.graph import set_weights
    # Two ways from B (2) back to the start (0): the direct street the loop
    # came out on (200 m), or a detour on new streets (240 m).
    g = nx.DiGraph()
    for n in range(4):
        g.add_node(n, lat=0, lon=0, signal_id=None)
    for u, v, length in [(0, 1, 100), (1, 2, 100), (2, 3, 120), (3, 0, 120)]:
        g.add_edge(u, v, length=length, name=None)
        g.add_edge(v, u, length=length, name=None)
    set_weights(g)
    out = [0, 1, 2]
    assert nx.dijkstra_path(g, 2, 0, weight=avoid(edges_of(out))) == [2, 3, 0]
