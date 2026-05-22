"""SQLite-based data persistence for the control tower."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from controltower.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Forecast,
    Inventory,
    Route,
    Shipment,
    ShipmentStatus,
)

_DEFAULT_DB = "controltower.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (
    id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    status TEXT NOT NULL,
    carrier TEXT,
    weight_kg REAL,
    estimated_arrival TEXT,
    actual_arrival TEXT,
    route_id TEXT,
    risk_score REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS inventory (
    id TEXT PRIMARY KEY,
    sku TEXT NOT NULL,
    warehouse TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    reorder_point INTEGER,
    reorder_qty INTEGER,
    unit_cost REAL,
    last_replenished TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS routes (
    id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    waypoints TEXT,
    distance_km REAL,
    estimated_hours REAL,
    cost REAL,
    risk_score REAL,
    is_active INTEGER,
    created_at TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    source_agent TEXT,
    related_entity_id TEXT,
    recommended_action TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS forecasts (
    id TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    metric TEXT NOT NULL,
    horizon_days INTEGER,
    values_json TEXT,
    confidence REAL,
    generated_at TEXT NOT NULL,
    metadata TEXT
);
"""


def _dt_to_str(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _str_to_dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class DataStore:
    """Thin wrapper around SQLite for control tower persistence."""

    def __init__(self, db_path: str = _DEFAULT_DB) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    # -- lifecycle -----------------------------------------------------------

    def connect(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        return self._conn

    # -- shipments -----------------------------------------------------------

    def upsert_shipment(self, s: Shipment) -> Shipment:
        self.conn.execute(
            """INSERT OR REPLACE INTO shipments
               (id,origin,destination,status,carrier,weight_kg,
                estimated_arrival,actual_arrival,route_id,risk_score,
                created_at,updated_at,metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                s.id, s.origin, s.destination, s.status.value,
                s.carrier, s.weight_kg,
                _dt_to_str(s.estimated_arrival), _dt_to_str(s.actual_arrival),
                s.route_id, s.risk_score,
                _dt_to_str(s.created_at), _dt_to_str(s.updated_at),
                json.dumps(s.metadata),
            ),
        )
        self.conn.commit()
        return s

    def get_shipment(self, shipment_id: str) -> Shipment | None:
        row = self.conn.execute(
            "SELECT * FROM shipments WHERE id=?", (shipment_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_shipment(row)

    def list_shipments(self, status: ShipmentStatus | None = None) -> list[Shipment]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM shipments WHERE status=? ORDER BY updated_at DESC",
                (status.value,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM shipments ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_shipment(r) for r in rows]

    @staticmethod
    def _row_to_shipment(row: sqlite3.Row) -> Shipment:
        return Shipment(
            id=row["id"],
            origin=row["origin"],
            destination=row["destination"],
            status=ShipmentStatus(row["status"]),
            carrier=row["carrier"] or "",
            weight_kg=row["weight_kg"] or 0.0,
            estimated_arrival=_str_to_dt(row["estimated_arrival"]),
            actual_arrival=_str_to_dt(row["actual_arrival"]),
            route_id=row["route_id"],
            risk_score=row["risk_score"] or 0.0,
            created_at=_str_to_dt(row["created_at"]) or datetime.now(UTC),
            updated_at=_str_to_dt(row["updated_at"]) or datetime.now(UTC),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # -- inventory -----------------------------------------------------------

    def upsert_inventory(self, inv: Inventory) -> Inventory:
        self.conn.execute(
            """INSERT OR REPLACE INTO inventory
               (id,sku,warehouse,quantity,reorder_point,reorder_qty,
                unit_cost,last_replenished,created_at,updated_at,metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                inv.id, inv.sku, inv.warehouse, inv.quantity,
                inv.reorder_point, inv.reorder_qty, inv.unit_cost,
                _dt_to_str(inv.last_replenished),
                _dt_to_str(inv.created_at), _dt_to_str(inv.updated_at),
                json.dumps(inv.metadata),
            ),
        )
        self.conn.commit()
        return inv

    def get_inventory(self, inventory_id: str) -> Inventory | None:
        row = self.conn.execute(
            "SELECT * FROM inventory WHERE id=?", (inventory_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_inventory(row)

    def list_inventory(self, warehouse: str | None = None) -> list[Inventory]:
        if warehouse:
            rows = self.conn.execute(
                "SELECT * FROM inventory WHERE warehouse=? ORDER BY sku",
                (warehouse,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM inventory ORDER BY sku"
            ).fetchall()
        return [self._row_to_inventory(r) for r in rows]

    @staticmethod
    def _row_to_inventory(row: sqlite3.Row) -> Inventory:
        return Inventory(
            id=row["id"],
            sku=row["sku"],
            warehouse=row["warehouse"],
            quantity=row["quantity"],
            reorder_point=row["reorder_point"] or 0,
            reorder_qty=row["reorder_qty"] or 0,
            unit_cost=row["unit_cost"] or 0.0,
            last_replenished=_str_to_dt(row["last_replenished"]),
            created_at=_str_to_dt(row["created_at"]) or datetime.now(UTC),
            updated_at=_str_to_dt(row["updated_at"]) or datetime.now(UTC),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # -- routes --------------------------------------------------------------

    def upsert_route(self, r: Route) -> Route:
        self.conn.execute(
            """INSERT OR REPLACE INTO routes
               (id,origin,destination,waypoints,distance_km,estimated_hours,
                cost,risk_score,is_active,created_at,metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r.id, r.origin, r.destination,
                json.dumps(r.waypoints), r.distance_km,
                r.estimated_hours, r.cost, r.risk_score,
                int(r.is_active), _dt_to_str(r.created_at),
                json.dumps(r.metadata),
            ),
        )
        self.conn.commit()
        return r

    def get_route(self, route_id: str) -> Route | None:
        row = self.conn.execute(
            "SELECT * FROM routes WHERE id=?", (route_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_route(row)

    def list_routes(self, active_only: bool = False) -> list[Route]:
        if active_only:
            rows = self.conn.execute(
                "SELECT * FROM routes WHERE is_active=1 ORDER BY origin"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM routes ORDER BY origin"
            ).fetchall()
        return [self._row_to_route(r) for r in rows]

    @staticmethod
    def _row_to_route(row: sqlite3.Row) -> Route:
        return Route(
            id=row["id"],
            origin=row["origin"],
            destination=row["destination"],
            waypoints=json.loads(row["waypoints"] or "[]"),
            distance_km=row["distance_km"] or 0.0,
            estimated_hours=row["estimated_hours"] or 0.0,
            cost=row["cost"] or 0.0,
            risk_score=row["risk_score"] or 0.0,
            is_active=bool(row["is_active"]),
            created_at=_str_to_dt(row["created_at"]) or datetime.now(UTC),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # -- alerts --------------------------------------------------------------

    def upsert_alert(self, a: Alert) -> Alert:
        self.conn.execute(
            """INSERT OR REPLACE INTO alerts
               (id,title,description,severity,status,source_agent,
                related_entity_id,recommended_action,created_at,
                resolved_at,metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                a.id, a.title, a.description, a.severity.value,
                a.status.value, a.source_agent, a.related_entity_id,
                a.recommended_action, _dt_to_str(a.created_at),
                _dt_to_str(a.resolved_at), json.dumps(a.metadata),
            ),
        )
        self.conn.commit()
        return a

    def list_alerts(
        self,
        status: AlertStatus | None = None,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        query = "SELECT * FROM alerts"
        params: list[Any] = []
        conditions: list[str] = []
        if status:
            conditions.append("status=?")
            params.append(status.value)
        if severity:
            conditions.append("severity=?")
            params.append(severity.value)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_alert(r) for r in rows]

    @staticmethod
    def _row_to_alert(row: sqlite3.Row) -> Alert:
        return Alert(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            severity=AlertSeverity(row["severity"]),
            status=AlertStatus(row["status"]),
            source_agent=row["source_agent"] or "",
            related_entity_id=row["related_entity_id"],
            recommended_action=row["recommended_action"] or "",
            created_at=_str_to_dt(row["created_at"]) or datetime.now(UTC),
            resolved_at=_str_to_dt(row["resolved_at"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # -- forecasts -----------------------------------------------------------

    def upsert_forecast(self, f: Forecast) -> Forecast:
        self.conn.execute(
            """INSERT OR REPLACE INTO forecasts
               (id,target,metric,horizon_days,values_json,confidence,
                generated_at,metadata)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                f.id, f.target, f.metric, f.horizon_days,
                json.dumps(f.values), f.confidence,
                _dt_to_str(f.generated_at), json.dumps(f.metadata),
            ),
        )
        self.conn.commit()
        return f

    def list_forecasts(self, target: str | None = None) -> list[Forecast]:
        if target:
            rows = self.conn.execute(
                "SELECT * FROM forecasts WHERE target=? ORDER BY generated_at DESC",
                (target,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM forecasts ORDER BY generated_at DESC"
            ).fetchall()
        return [self._row_to_forecast(r) for r in rows]

    @staticmethod
    def _row_to_forecast(row: sqlite3.Row) -> Forecast:
        return Forecast(
            id=row["id"],
            target=row["target"],
            metric=row["metric"],
            horizon_days=row["horizon_days"] or 7,
            values=json.loads(row["values_json"] or "[]"),
            confidence=row["confidence"] or 0.0,
            generated_at=_str_to_dt(row["generated_at"]) or datetime.now(UTC),
            metadata=json.loads(row["metadata"] or "{}"),
        )
