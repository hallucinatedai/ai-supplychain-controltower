"""Tests for the FastAPI REST API."""

import pytest
from fastapi.testclient import TestClient

from controltower.api import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CONTROLTOWER_DB", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    def test_health(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"

    def test_agent_health(self, client: TestClient) -> None:
        resp = client.get("/health/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert all(v is True for v in data.values())


class TestShipmentEndpoints:
    def test_create_and_get_shipment(self, client: TestClient) -> None:
        payload = {
            "origin": "Shanghai",
            "destination": "Hamburg",
            "carrier": "Maersk",
            "weight_kg": 5000,
        }
        resp = client.post("/shipments", json=payload)
        assert resp.status_code == 201
        shipment = resp.json()
        assert shipment["origin"] == "Shanghai"
        sid = shipment["id"]

        resp = client.get(f"/shipments/{sid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sid

    def test_list_shipments(self, client: TestClient) -> None:
        client.post("/shipments", json={"origin": "A", "destination": "B"})
        client.post("/shipments", json={"origin": "C", "destination": "D"})
        resp = client.get("/shipments")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_shipment_not_found(self, client: TestClient) -> None:
        resp = client.get("/shipments/nonexistent")
        assert resp.status_code == 404


class TestInventoryEndpoints:
    def test_create_and_get_inventory(self, client: TestClient) -> None:
        payload = {"sku": "WIDGET-X", "warehouse": "W1", "quantity": 100}
        resp = client.post("/inventory", json=payload)
        assert resp.status_code == 201
        item = resp.json()
        iid = item["id"]

        resp = client.get(f"/inventory/{iid}")
        assert resp.status_code == 200

    def test_list_inventory(self, client: TestClient) -> None:
        client.post("/inventory", json={"sku": "A", "warehouse": "W1", "quantity": 10})
        resp = client.get("/inventory")
        assert resp.status_code == 200

    def test_get_inventory_not_found(self, client: TestClient) -> None:
        resp = client.get("/inventory/nonexistent")
        assert resp.status_code == 404


class TestRouteEndpoints:
    def test_create_and_get_route(self, client: TestClient) -> None:
        payload = {
            "origin": "A",
            "destination": "B",
            "distance_km": 500,
            "estimated_hours": 8,
            "cost": 1200,
        }
        resp = client.post("/routes", json=payload)
        assert resp.status_code == 201
        rid = resp.json()["id"]

        resp = client.get(f"/routes/{rid}")
        assert resp.status_code == 200

    def test_list_routes(self, client: TestClient) -> None:
        client.post("/routes", json={"origin": "X", "destination": "Y"})
        resp = client.get("/routes")
        assert resp.status_code == 200

    def test_get_route_not_found(self, client: TestClient) -> None:
        resp = client.get("/routes/nonexistent")
        assert resp.status_code == 404


class TestAlertEndpoints:
    def test_create_and_list_alerts(self, client: TestClient) -> None:
        payload = {"title": "Test Alert", "severity": "high"}
        resp = client.post("/alerts", json=payload)
        assert resp.status_code == 201

        resp = client.get("/alerts")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_filter_alerts_by_severity(self, client: TestClient) -> None:
        client.post("/alerts", json={"title": "Low", "severity": "low"})
        client.post("/alerts", json={"title": "High", "severity": "high"})
        resp = client.get("/alerts?severity=high")
        assert resp.status_code == 200
        alerts = resp.json()
        assert all(a["severity"] == "high" for a in alerts)


class TestForecastEndpoints:
    def test_create_and_list_forecasts(self, client: TestClient) -> None:
        payload = {
            "target": "demand",
            "metric": "units",
            "horizon_days": 7,
            "values": [100, 105, 110, 115, 120, 125, 130],
            "confidence": 0.85,
        }
        resp = client.post("/forecasts", json=payload)
        assert resp.status_code == 201

        resp = client.get("/forecasts")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestEventEndpoints:
    def test_ingest_event(self, client: TestClient) -> None:
        # create a shipment first
        client.post("/shipments", json={"id": "ev-ship", "origin": "A", "destination": "B"})
        event = {
            "event_type": "shipment_update",
            "entity_id": "ev-ship",
            "payload": {"status": "in_transit"},
        }
        resp = client.post("/events", json=event)
        assert resp.status_code == 202

    def test_ingest_batch(self, client: TestClient) -> None:
        events = [
            {
                "event_type": "shipment_created",
                "entity_id": f"batch-{i}",
                "payload": {"origin": "A", "destination": "B"},
            }
            for i in range(3)
        ]
        resp = client.post("/events/batch", json=events)
        assert resp.status_code == 202
        data = resp.json()
        assert data["processed"] == 3


class TestDecisionEndpoints:
    def test_decide(self, client: TestClient) -> None:
        resp = client.post("/decide", json={})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_recommendations(self, client: TestClient) -> None:
        resp = client.get("/recommendations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
