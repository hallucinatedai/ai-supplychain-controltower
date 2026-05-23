"""Tests for the event processing layer."""

from pathlib import Path

from controltower.data_store import DataStore
from controltower.event_layer import EventLayer
from controltower.models import (
    OperationalEvent,
    Shipment,
    ShipmentStatus,
)


def _make_store(tmp_path: str) -> DataStore:
    store = DataStore(str(Path(tmp_path) / "test.db"))
    store.connect()
    return store


class TestEventLayer:
    def test_process_shipment_created(self, tmp_path: Path) -> None:
        store = _make_store(str(tmp_path))
        layer = EventLayer(store)

        event = OperationalEvent(
            event_type="shipment_created",
            entity_id="ship-001",
            payload={
                "origin": "Shanghai",
                "destination": "Hamburg",
                "carrier": "MaerskLine",
                "weight_kg": 5000,
            },
        )
        layer.process(event)

        shipment = store.get_shipment("ship-001")
        assert shipment is not None
        assert shipment.origin == "Shanghai"
        assert shipment.destination == "Hamburg"
        assert shipment.carrier == "MaerskLine"
        store.close()

    def test_process_shipment_update(self, tmp_path: Path) -> None:
        store = _make_store(str(tmp_path))
        layer = EventLayer(store)

        # seed a shipment
        store.upsert_shipment(Shipment(id="ship-002", origin="A", destination="B"))

        event = OperationalEvent(
            event_type="shipment_update",
            entity_id="ship-002",
            payload={"status": "in_transit"},
        )
        layer.process(event)

        updated = store.get_shipment("ship-002")
        assert updated is not None
        assert updated.status == ShipmentStatus.IN_TRANSIT
        store.close()

    def test_process_delay_reported(self, tmp_path: Path) -> None:
        store = _make_store(str(tmp_path))
        layer = EventLayer(store)

        store.upsert_shipment(Shipment(id="ship-003", origin="A", destination="B"))

        event = OperationalEvent(
            event_type="delay_reported",
            entity_id="ship-003",
            payload={"estimated_arrival": "2025-06-15T12:00:00"},
        )
        layer.process(event)

        s = store.get_shipment("ship-003")
        assert s is not None
        assert s.status == ShipmentStatus.DELAYED
        assert s.estimated_arrival is not None
        store.close()

    def test_process_inventory_update_new(self, tmp_path: Path) -> None:
        store = _make_store(str(tmp_path))
        layer = EventLayer(store)

        event = OperationalEvent(
            event_type="inventory_update",
            entity_id="inv-001",
            payload={"sku": "WIDGET-X", "warehouse": "W1", "quantity": 500},
        )
        layer.process(event)

        inv = store.get_inventory("inv-001")
        assert inv is not None
        assert inv.sku == "WIDGET-X"
        assert inv.quantity == 500
        store.close()

    def test_process_batch(self, tmp_path: Path) -> None:
        store = _make_store(str(tmp_path))
        layer = EventLayer(store)

        events = [
            OperationalEvent(
                event_type="shipment_created",
                entity_id=f"batch-{i}",
                payload={"origin": "A", "destination": "B"},
            )
            for i in range(5)
        ]
        count = layer.process_batch(events)
        assert count == 5
        assert len(layer.event_log) == 5
        store.close()

    def test_unknown_event_type(self, tmp_path: Path) -> None:
        store = _make_store(str(tmp_path))
        layer = EventLayer(store)

        event = OperationalEvent(
            event_type="unknown_event",
            entity_id="x",
        )
        layer.process(event)  # should not raise
        assert len(layer.event_log) == 1
        store.close()

    def test_register_custom_handler(self, tmp_path: Path) -> None:
        store = _make_store(str(tmp_path))
        layer = EventLayer(store)

        called_with: list[str] = []

        def custom_handler(event: OperationalEvent, s: DataStore) -> None:
            called_with.append(event.entity_id)

        layer.register("custom", custom_handler)
        layer.process(OperationalEvent(event_type="custom", entity_id="c1"))
        assert called_with == ["c1"]
        store.close()
