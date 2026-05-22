"""Tests for all supply chain intelligence agents."""

from datetime import UTC, datetime, timedelta

from controltower.agents.escalation import EscalationAgent
from controltower.agents.forecasting import ForecastingAgent
from controltower.agents.inventory import InventoryAgent
from controltower.agents.risk import RiskAgent
from controltower.agents.route import RouteAgent
from controltower.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Inventory,
    Route,
    Shipment,
    ShipmentStatus,
)


# ---------------------------------------------------------------------------
# ForecastingAgent
# ---------------------------------------------------------------------------

class TestForecastingAgent:
    def setup_method(self) -> None:
        self.agent = ForecastingAgent()

    def test_name(self) -> None:
        assert self.agent.name == "forecasting"

    def test_health_check(self) -> None:
        assert self.agent.health_check() is True

    def test_forecast_demand_basic(self) -> None:
        historical = [100.0, 110.0, 105.0, 115.0, 120.0, 125.0, 130.0]
        forecast = self.agent.forecast_demand(historical, horizon=5)
        assert forecast.target == "demand"
        assert forecast.metric == "units"
        assert len(forecast.values) == 5
        assert all(v >= 0 for v in forecast.values)
        assert 0 <= forecast.confidence <= 1

    def test_forecast_demand_short_history(self) -> None:
        forecast = self.agent.forecast_demand([50.0], horizon=3)
        assert len(forecast.values) == 3
        assert forecast.confidence == 0.1

    def test_forecast_demand_empty(self) -> None:
        forecast = self.agent.forecast_demand([], horizon=3)
        assert len(forecast.values) == 3

    def test_forecast_delay(self) -> None:
        delays = [2.0, 3.5, 1.0, 4.0, 2.5]
        forecast = self.agent.forecast_delay(delays, horizon=3)
        assert forecast.target == "delay"
        assert forecast.metric == "hours"
        assert len(forecast.values) == 3

    def test_analyze_demand_surge(self) -> None:
        context = {"historical_demand": [10, 10, 10, 10, 30, 30, 30, 30, 30]}
        recs = self.agent.analyze(context)
        assert len(recs) >= 1
        assert any("surge" in r.title.lower() or "decline" in r.title.lower() for r in recs)

    def test_analyze_empty(self) -> None:
        recs = self.agent.analyze({})
        assert recs == []


# ---------------------------------------------------------------------------
# RiskAgent
# ---------------------------------------------------------------------------

class TestRiskAgent:
    def setup_method(self) -> None:
        self.agent = RiskAgent()

    def test_name(self) -> None:
        assert self.agent.name == "risk"

    def test_score_normal_shipment(self) -> None:
        s = Shipment(origin="A", destination="B", status=ShipmentStatus.IN_TRANSIT)
        score = self.agent.score_shipment(s)
        assert 0 <= score <= 1

    def test_score_delayed_shipment(self) -> None:
        s = Shipment(origin="A", destination="B", status=ShipmentStatus.DELAYED)
        score = self.agent.score_shipment(s)
        assert score >= 0.4

    def test_score_heavy_shipment(self) -> None:
        s = Shipment(
            origin="A", destination="B",
            status=ShipmentStatus.IN_TRANSIT,
            weight_kg=15_000,
        )
        score = self.agent.score_shipment(s)
        assert score >= 0.1

    def test_classify_severity(self) -> None:
        assert self.agent.classify_severity(0.9) == AlertSeverity.CRITICAL
        assert self.agent.classify_severity(0.75) == AlertSeverity.HIGH
        assert self.agent.classify_severity(0.5) == AlertSeverity.MEDIUM
        assert self.agent.classify_severity(0.2) == AlertSeverity.LOW

    def test_analyze_high_risk(self) -> None:
        shipments = [
            Shipment(
                origin="A", destination="B",
                status=ShipmentStatus.DELAYED,
                carrier="slow_carrier",
                route_id="risky_route",
            ),
        ]
        context = {
            "shipments": shipments,
            "delay_rates": {"risky_route": 0.8, "slow_carrier": 0.7},
        }
        recs = self.agent.analyze(context)
        assert len(recs) >= 1
        assert recs[0].agent == "risk"


# ---------------------------------------------------------------------------
# RouteAgent
# ---------------------------------------------------------------------------

class TestRouteAgent:
    def setup_method(self) -> None:
        self.agent = RouteAgent()

    def test_name(self) -> None:
        assert self.agent.name == "route"

    def test_recommend_route(self) -> None:
        routes = [
            Route(id="r1", origin="A", destination="B", cost=100, estimated_hours=10, risk_score=0.1),
            Route(id="r2", origin="A", destination="B", cost=200, estimated_hours=5, risk_score=0.3),
            Route(id="r3", origin="A", destination="B", cost=50, estimated_hours=20, risk_score=0.8),
        ]
        best = self.agent.recommend_route(routes, "A", "B")
        assert best is not None
        assert best.id in ("r1", "r2")

    def test_recommend_route_no_match(self) -> None:
        routes = [Route(id="r1", origin="X", destination="Y", cost=100, estimated_hours=5, risk_score=0.1)]
        best = self.agent.recommend_route(routes, "A", "B")
        assert best is None

    def test_rank_routes(self) -> None:
        routes = [
            Route(id="r1", origin="A", destination="B", cost=200, estimated_hours=10, risk_score=0.5),
            Route(id="r2", origin="A", destination="B", cost=50, estimated_hours=5, risk_score=0.1),
        ]
        ranked = self.agent.rank_routes(routes)
        assert ranked[0].id == "r2"

    def test_analyze_with_context(self) -> None:
        routes = [
            Route(id="r1", origin="A", destination="B", cost=100, estimated_hours=5, risk_score=0.2),
        ]
        context = {"routes": routes, "origin": "A", "destination": "B"}
        recs = self.agent.analyze(context)
        assert len(recs) >= 1

    def test_analyze_high_risk_route(self) -> None:
        routes = [
            Route(id="r1", origin="A", destination="B", cost=100, estimated_hours=5, risk_score=0.9),
        ]
        context = {"routes": routes}
        recs = self.agent.analyze(context)
        assert any("high-risk" in r.title.lower() for r in recs)


# ---------------------------------------------------------------------------
# InventoryAgent
# ---------------------------------------------------------------------------

class TestInventoryAgent:
    def setup_method(self) -> None:
        self.agent = InventoryAgent()

    def test_name(self) -> None:
        assert self.agent.name == "inventory"

    def test_is_below_reorder(self) -> None:
        item = Inventory(sku="SKU1", warehouse="W1", quantity=5, reorder_point=10)
        assert self.agent.is_below_reorder(item) is True

    def test_not_below_reorder(self) -> None:
        item = Inventory(sku="SKU1", warehouse="W1", quantity=20, reorder_point=10)
        assert self.agent.is_below_reorder(item) is False

    def test_days_until_stockout(self) -> None:
        item = Inventory(sku="SKU1", warehouse="W1", quantity=100)
        days = self.agent.days_until_stockout(item, avg_daily_demand=10)
        assert days == 10.0

    def test_days_until_stockout_zero_demand(self) -> None:
        item = Inventory(sku="SKU1", warehouse="W1", quantity=100)
        days = self.agent.days_until_stockout(item, avg_daily_demand=0)
        assert days == float("inf")

    def test_suggest_reorder_point(self) -> None:
        rop = self.agent.suggest_reorder_point(avg_daily_demand=10, lead_time_days=5)
        assert rop == 75  # 10 * 5 * 1.5

    def test_suggest_reorder_qty(self) -> None:
        qty = self.agent.suggest_reorder_qty(avg_daily_demand=10, order_cycle_days=30)
        assert qty == 300

    def test_analyze_reorder_needed(self) -> None:
        items = [
            Inventory(sku="SKU1", warehouse="W1", quantity=3, reorder_point=10, reorder_qty=50),
        ]
        context = {"inventory": items}
        recs = self.agent.analyze(context)
        assert len(recs) >= 1
        assert "reorder" in recs[0].title.lower()

    def test_analyze_stockout_imminent(self) -> None:
        items = [
            Inventory(sku="SKU1", warehouse="W1", quantity=20, reorder_point=5),
        ]
        context = {"inventory": items, "avg_daily_demand": {"SKU1": 10.0}}
        recs = self.agent.analyze(context)
        assert any("stockout" in r.title.lower() for r in recs)


# ---------------------------------------------------------------------------
# EscalationAgent
# ---------------------------------------------------------------------------

class TestEscalationAgent:
    def setup_method(self) -> None:
        self.agent = EscalationAgent()

    def test_name(self) -> None:
        assert self.agent.name == "escalation"

    def test_no_escalation_for_on_time(self) -> None:
        s = Shipment(origin="A", destination="B", status=ShipmentStatus.IN_TRANSIT)
        alert = self.agent.check_shipment_escalation(s)
        assert alert is None

    def test_escalation_delayed_no_eta(self) -> None:
        s = Shipment(origin="A", destination="B", status=ShipmentStatus.DELAYED)
        alert = self.agent.check_shipment_escalation(s)
        assert alert is not None
        assert alert.severity == AlertSeverity.HIGH

    def test_critical_escalation(self) -> None:
        s = Shipment(
            origin="A", destination="B",
            status=ShipmentStatus.DELAYED,
            estimated_arrival=datetime.now(UTC) - timedelta(hours=50),
        )
        alert = self.agent.check_shipment_escalation(s)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_stale_alert(self) -> None:
        old_alert = Alert(
            title="Test alert",
            status=AlertStatus.OPEN,
            created_at=datetime.now(UTC) - timedelta(hours=30),
        )
        rec = self.agent.check_stale_alert(old_alert)
        assert rec is not None
        assert "stale" in rec.title.lower()

    def test_fresh_alert_no_escalation(self) -> None:
        fresh = Alert(
            title="Test alert",
            status=AlertStatus.OPEN,
            created_at=datetime.now(UTC),
        )
        rec = self.agent.check_stale_alert(fresh)
        assert rec is None

    def test_analyze(self) -> None:
        shipments = [
            Shipment(
                origin="A", destination="B",
                status=ShipmentStatus.DELAYED,
                estimated_arrival=datetime.now(UTC) - timedelta(hours=30),
            ),
        ]
        context = {"shipments": shipments, "alerts": []}
        recs = self.agent.analyze(context)
        assert len(recs) >= 1
