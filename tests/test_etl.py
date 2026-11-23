import json

import pandas as pd
import pytest

from etl.load_signals import clean, to_rows
from etl.load_streets import is_indoor


def signal_row(**overrides):
    row = {
        "PX": "0003", "MAIN_STREET": "KING ST E", "MIDBLOCK_ROUTE": "None",
        "SIDE1_STREET": "JARVIS ST",
        "geometry": json.dumps({"type": "MultiPoint", "coordinates": [[-79.3719, 43.6505]]}),
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize("value", ["None", "", "  ", None, float("nan")])
def test_clean_treats_city_placeholders_as_missing(value):
    assert clean(value) is None


def test_clean_trims_text():
    assert clean("  KING ST E ") == "KING ST E"


def test_to_rows_reads_an_intersection_signal():
    [row] = to_rows(pd.DataFrame([signal_row()]))
    assert row == {
        "source_id": "0003", "signal_type": "Intersection",
        "main": "KING ST E", "cross": "JARVIS ST", "lat": 43.6505, "lon": -79.3719,
    }


def test_to_rows_marks_midblock_signals():
    [row] = to_rows(pd.DataFrame([signal_row(MIDBLOCK_ROUTE="E OF JARVIS ST")]))
    assert row["signal_type"] == "Midblock"
    assert row["cross"] == "E OF JARVIS ST"


def test_to_rows_reads_plain_point_geometry():
    geom = json.dumps({"type": "Point", "coordinates": [-79.3719, 43.6505]})
    [row] = to_rows(pd.DataFrame([signal_row(geometry=geom)]))
    assert (row["lat"], row["lon"]) == (43.6505, -79.3719)


@pytest.mark.parametrize("tags", [
    {"highway": "footway", "tunnel": "yes"},
    {"highway": ["steps", "footway"], "tunnel": ["building_passage", "yes"]},
    {"highway": "footway", "indoor": "yes"},
    {"highway": "footway", "indoor": "corridor"},
    {"highway": "corridor"},
    {"highway": ["corridor", "footway"]},
    {"highway": "elevator"},
    {"highway": "footway", "level": "-1"},
    {"highway": "footway", "level": "-2;-1"},
])
def test_is_indoor_drops_indoor_and_underground(tags):
    assert is_indoor(tags)


@pytest.mark.parametrize("tags", [
    {"highway": "residential"},
    {"highway": "footway", "tunnel": "building_passage"},
    {"highway": "footway", "indoor": "no"},
    {"highway": "footway", "level": "0"},
    {"highway": "footway", "level": "1"},
    {"highway": "path", "level": "ground"},
    {"highway": "footway", "bridge": "yes"},
])
def test_is_indoor_keeps_outdoor_routes(tags):
    assert not is_indoor(tags)
