"""FastAPI REST API for the AI Supply Chain Control Tower."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from controltower.agents import (
    EscalationAgent,
    ForecastingAgent,
    InventoryAgent,
    RiskAgent,
    RouteAgent,
)
from controltower.data_store import DataStore
from controltower.decision_engine import DecisionEngine
from controltower.event_layer import EventLayer
from controltower.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Forecast,
    HealthResponse,
    Inventory,
    OperationalEvent,
    Recommendation,
    Route,
    Shipment,
    ShipmentStatus,
)

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

_store: DataStore | None = None
_engine: DecisionEngine | None = None
_event_layer: EventLayer | None = None


def _get_store() -> DataStore:
    assert _store is not None
    return _store


def _get_engine() -> DecisionEngine:
    assert _engine is not None
    return _engine


def _get_event_layer() -> EventLayer:
    assert _event_layer is not None
    return _event_layer


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    global _store, _engine, _event_layer  # noqa: PLW0603
    db_path = os.environ.get("CONTROLTOWER_DB", "controltower.db")
    _store = DataStore(db_path)
    _store.connect()

    _engine = DecisionEngine([
        ForecastingAgent(),
        RiskAgent(),
        RouteAgent(),
        InventoryAgent(),
        EscalationAgent(),
    ])

    _event_layer = EventLayer(_store)
    yield
    _store.close()


app = FastAPI(
    title="AI Supply Chain Control Tower",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@app.get("/health/agents")
async def agent_health() -> dict[str, bool]:
    return _get_engine().health()


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------

@app.post("/shipments", response_model=Shipment, status_code=201)
async def create_shipment(shipment: Shipment) -> Shipment:
    return _get_store().upsert_shipment(shipment)


@app.get("/shipments", response_model=list[Shipment])
async def list_shipments(
    status: ShipmentStatus | None = Query(default=None),
) -> list[Shipment]:
    return _get_store().list_shipments(status=status)


@app.get("/shipments/{shipment_id}", response_model=Shipment)
async def get_shipment(shipment_id: str) -> Shipment:
    s = _get_store().get_shipment(shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return s


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@app.post("/inventory", response_model=Inventory, status_code=201)
async def create_inventory(item: Inventory) -> Inventory:
    return _get_store().upsert_inventory(item)


@app.get("/inventory", response_model=list[Inventory])
async def list_inventory(
    warehouse: str | None = Query(default=None),
) -> list[Inventory]:
    return _get_store().list_inventory(warehouse=warehouse)


@app.get("/inventory/{item_id}", response_model=Inventory)
async def get_inventory(item_id: str) -> Inventory:
    inv = _get_store().get_inventory(item_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return inv


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/routes", response_model=Route, status_code=201)
async def create_route(route: Route) -> Route:
    return _get_store().upsert_route(route)


@app.get("/routes", response_model=list[Route])
async def list_routes(
    active_only: bool = Query(default=False),
) -> list[Route]:
    return _get_store().list_routes(active_only=active_only)


@app.get("/routes/{route_id}", response_model=Route)
async def get_route(route_id: str) -> Route:
    r = _get_store().get_route(route_id)
    if not r:
        raise HTTPException(status_code=404, detail="Route not found")
    return r


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.post("/alerts", response_model=Alert, status_code=201)
async def create_alert(alert: Alert) -> Alert:
    return _get_store().upsert_alert(alert)


@app.get("/alerts", response_model=list[Alert])
async def list_alerts(
    status: AlertStatus | None = Query(default=None),
    severity: AlertSeverity | None = Query(default=None),
) -> list[Alert]:
    return _get_store().list_alerts(status=status, severity=severity)


# ---------------------------------------------------------------------------
# Forecasts
# ---------------------------------------------------------------------------

@app.post("/forecasts", response_model=Forecast, status_code=201)
async def create_forecast(forecast: Forecast) -> Forecast:
    return _get_store().upsert_forecast(forecast)


@app.get("/forecasts", response_model=list[Forecast])
async def list_forecasts(
    target: str | None = Query(default=None),
) -> list[Forecast]:
    return _get_store().list_forecasts(target=target)


@app.post("/forecasts/generate", response_model=Forecast)
async def generate_forecast(
    historical_demand: list[float],
    horizon: int = Query(default=7, ge=1, le=90),
) -> Forecast:
    agent = ForecastingAgent()
    return agent.forecast_demand(historical_demand, horizon=horizon)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.post("/events", status_code=202)
async def ingest_event(event: OperationalEvent) -> dict[str, str]:
    _get_event_layer().process(event)
    return {"status": "accepted"}


@app.post("/events/batch", status_code=202)
async def ingest_events(events: list[OperationalEvent]) -> dict[str, Any]:
    count = _get_event_layer().process_batch(events)
    return {"status": "accepted", "processed": count, "total": len(events)}


# ---------------------------------------------------------------------------
# Decision engine
# ---------------------------------------------------------------------------

@app.post("/decide", response_model=list[Recommendation])
async def decide(context: dict[str, Any]) -> list[Recommendation]:
    return _get_engine().decide(context)


@app.get("/recommendations", response_model=list[Recommendation])
async def get_recommendations() -> list[Recommendation]:
    """Generate recommendations based on current data."""
    store = _get_store()
    context: dict[str, Any] = {
        "shipments": store.list_shipments(),
        "inventory": store.list_inventory(),
        "routes": store.list_routes(),
        "alerts": store.list_alerts(),
    }
    return _get_engine().decide(context)
