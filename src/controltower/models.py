"""Pydantic models for the AI Supply Chain Control Tower."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _default_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ShipmentStatus(str, Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------

class Shipment(BaseModel):
    id: str = Field(default_factory=_default_id)
    origin: str
    destination: str
    status: ShipmentStatus = ShipmentStatus.PENDING
    carrier: str = ""
    weight_kg: float = 0.0
    estimated_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    route_id: str | None = None
    risk_score: float = 0.0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Inventory(BaseModel):
    id: str = Field(default_factory=_default_id)
    sku: str
    warehouse: str
    quantity: int = 0
    reorder_point: int = 0
    reorder_qty: int = 0
    unit_cost: float = 0.0
    last_replenished: datetime | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Route(BaseModel):
    id: str = Field(default_factory=_default_id)
    origin: str
    destination: str
    waypoints: list[str] = Field(default_factory=list)
    distance_km: float = 0.0
    estimated_hours: float = 0.0
    cost: float = 0.0
    risk_score: float = 0.0
    is_active: bool = True
    created_at: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Alert(BaseModel):
    id: str = Field(default_factory=_default_id)
    title: str
    description: str = ""
    severity: AlertSeverity = AlertSeverity.MEDIUM
    status: AlertStatus = AlertStatus.OPEN
    source_agent: str = ""
    related_entity_id: str | None = None
    recommended_action: str = ""
    created_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Forecast(BaseModel):
    id: str = Field(default_factory=_default_id)
    target: str
    metric: str
    horizon_days: int = 7
    values: list[float] = Field(default_factory=list)
    confidence: float = 0.0
    generated_at: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# API request / response helpers
# ---------------------------------------------------------------------------

class OperationalEvent(BaseModel):
    event_type: str
    entity_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_now)


class Recommendation(BaseModel):
    id: str = Field(default_factory=_default_id)
    agent: str
    priority: int = 0
    title: str
    description: str = ""
    action: str = ""
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=_now)
