from api.graph import SIGNAL_PENALTY_M
from tests.conftest import grid


def test_entering_a_signal_costs_the_penalty():
    g = grid(size=3, signals={(1, 1): 7})
    assert g[1000][1001]["weight"] == 100 + SIGNAL_PENALTY_M


def test_leaving_a_signal_is_free():
    g = grid(size=3, signals={(1, 1): 7})
    assert g[1001][1002]["weight"] == 100


def test_moving_within_one_signalized_intersection_is_not_charged_again():
    # Two points of the same intersection, e.g. a sidewalk and a crosswalk.
    g = grid(size=3, signals={(1, 1): 7, (1, 2): 7})
    assert g[1001][1002]["weight"] == 100


def test_moving_between_two_different_signals_is_charged():
    g = grid(size=3, signals={(1, 1): 7, (1, 2): 8})
    assert g[1001][1002]["weight"] == 100 + SIGNAL_PENALTY_M
