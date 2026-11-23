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


def test_geocode_returns_matches(client, monkeypatch):
    import api.geocode
    monkeypatch.setattr(api.geocode, "_fetch", lambda q: [
        {"display_name": "CN Tower, 290, Bremner Boulevard, Harbourfront-CityPlace, Toronto, Golden Horseshoe, Ontario, M5V 3L9, Canada",
         "lat": "43.6425637", "lon": "-79.3870872"},
    ])
    api.geocode._search_cached.cache_clear()
    res = client.get("/geocode", params={"q": "CN Tower"})
    assert res.status_code == 200
    assert res.json() == {"results": [{
        "name": "CN Tower, 290, Bremner Boulevard, Harbourfront-CityPlace",
        "lat": 43.6425637, "lon": -79.3870872,
    }]}


def test_geocode_caches_repeat_searches(client, monkeypatch):
    import api.geocode
    calls = []
    monkeypatch.setattr(api.geocode, "_fetch", lambda q: calls.append(q) or [])
    api.geocode._search_cached.cache_clear()
    client.get("/geocode", params={"q": "High Park"})
    client.get("/geocode", params={"q": "  high   PARK "})
    assert calls == ["high park"]


def test_geocode_reports_lookup_outage(client, monkeypatch):
    import api.geocode

    def down(q):
        raise OSError("network down")
    monkeypatch.setattr(api.geocode, "_fetch", down)
    api.geocode._search_cached.cache_clear()
    res = client.get("/geocode", params={"q": "Union Station"})
    assert res.status_code == 502


def test_geocode_rejects_short_queries(client):
    assert client.get("/geocode", params={"q": "ab"}).status_code == 422
