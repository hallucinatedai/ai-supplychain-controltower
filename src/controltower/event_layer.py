"""Real-time event processing layer for operational events."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from controltower.data_store import DataStore
from controltower.models import (
    Inventory,
    OperationalEvent,
    Shipment,
    ShipmentStatus,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[[OperationalEvent, DataStore], None]


class EventLayer:
    """Processes operational events and dispatches them to handlers."""

    MAX_EVENT_LOG_SIZE = 10_000

    def __init__(self, store: DataStore) -> None:
        self._store = store
        self._handlers: dict[str, list[EventHandler]] = {}
        self._event_log: list[OperationalEvent] = []
        self._register_default_handlers()

    # -- registration --------------------------------------------------------

    def register(self, event_type: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    # -- dispatching ---------------------------------------------------------

    def process(self, event: OperationalEvent) -> bool:
        """Process a single operational event. Returns True if at least one handler succeeded."""
        self._event_log.append(event)
        if len(self._event_log) > self.MAX_EVENT_LOG_SIZE:
            self._event_log = self._event_log[-self.MAX_EVENT_LOG_SIZE:]
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            logger.warning("No handlers for event type: %s", event.event_type)
            return True
        any_succeeded = False
        for handler in handlers:
            try:
                handler(event, self._store)
                any_succeeded = True
            except Exception:
                logger.exception(
                    "Handler failed for event %s", event.event_type
                )
        return any_succeeded

    def process_batch(self, events: list[OperationalEvent]) -> int:
        """Process multiple events. Returns the count of successfully processed events."""
        processed = 0
        for event in events:
            try:
                if self.process(event):
                    processed += 1
            except Exception:
                logger.exception("Failed to process event %s", event.event_type)
        return processed

    @property
    def event_log(self) -> list[OperationalEvent]:
        return list(self._event_log)

    # -- built-in handlers ---------------------------------------------------

    def _register_default_handlers(self) -> None:
        self.register("shipment_update", _handle_shipment_update)
        self.register("shipment_created", _handle_shipment_created)
        self.register("inventory_update", _handle_inventory_update)
        self.register("delay_reported", _handle_delay_reported)


# ---------------------------------------------------------------------------
# Default handler implementations
# ---------------------------------------------------------------------------

def _handle_shipment_update(event: OperationalEvent, store: DataStore) -> None:
    shipment = store.get_shipment(event.entity_id)
    if not shipment:
        logger.warning("Shipment %s not found for update", event.entity_id)
        return
    payload = event.payload
    if "status" in payload:
        shipment.status = ShipmentStatus(payload["status"])
    if "actual_arrival" in payload:
        shipment.actual_arrival = datetime.fromisoformat(payload["actual_arrival"])
    if "risk_score" in payload:
        shipment.risk_score = float(payload["risk_score"])
    shipment.updated_at = datetime.now(UTC)
    store.upsert_shipment(shipment)


def _handle_shipment_created(event: OperationalEvent, store: DataStore) -> None:
    payload = event.payload
    shipment = Shipment(
        id=event.entity_id,
        origin=payload.get("origin", ""),
        destination=payload.get("destination", ""),
        carrier=payload.get("carrier", ""),
        weight_kg=float(payload.get("weight_kg", 0)),
        status=ShipmentStatus(payload.get("status", "pending")),
    )
    store.upsert_shipment(shipment)


def _handle_inventory_update(event: OperationalEvent, store: DataStore) -> None:
    inv = store.get_inventory(event.entity_id)
    if not inv:
        payload = event.payload
        inv = Inventory(
            id=event.entity_id,
            sku=payload.get("sku", event.entity_id),
            warehouse=payload.get("warehouse", "default"),
            quantity=int(payload.get("quantity", 0)),
        )
    else:
        if "quantity" in event.payload:
            inv.quantity = int(event.payload["quantity"])
        if "warehouse" in event.payload:
            inv.warehouse = event.payload["warehouse"]
    inv.updated_at = datetime.now(UTC)
    store.upsert_inventory(inv)


def _handle_delay_reported(event: OperationalEvent, store: DataStore) -> None:
    shipment = store.get_shipment(event.entity_id)
    if not shipment:
        logger.warning("Shipment %s not found for delay report", event.entity_id)
        return
    shipment.status = ShipmentStatus.DELAYED
    if "estimated_arrival" in event.payload:
        shipment.estimated_arrival = datetime.fromisoformat(
            event.payload["estimated_arrival"]
        )
    shipment.updated_at = datetime.now(UTC)
    store.upsert_shipment(shipment)
