import pytest
from fastapi.testclient import TestClient

import api.main
from tests.conftest import grid, node_latlon


@pytest.fixture
def client(monkeypatch):
    g = grid(signals={(10, 12): 1})
    monkeypatch.setattr(api.main, "load_graph", lambda: g)
    with TestClient(api.main.app) as c:
        c.graph = g
        yield c


def test_loop_returns_geojson(client):
    lat, lon = node_latlon(client.graph, 10010)
    res = client.get("/loop", params={"lat": lat, "lon": lon, "km": 1.5})
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "Feature"
    coords = body["geometry"]["coordinates"]
    assert coords[0] == coords[-1]  # a loop ends where it starts
    props = body["properties"]
    assert props["target_km"] == 1.5
    assert len(props["signal_locations"]) == props["signals"]


def test_start_outside_toronto_is_rejected(client):
    res = client.get("/loop", params={"lat": 45.0, "lon": -79.4, "km": 5})
    assert res.status_code == 422


def test_distance_out_of_range_is_rejected(client):
    lat, lon = node_latlon(client.graph, 10010)
    assert client.get("/loop", params={"lat": lat, "lon": lon, "km": 100}).status_code == 422


def test_map_page_is_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "RunNow" in res.text


def test_health_reports_the_loaded_network(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "nodes": client.graph.number_of_nodes()}
