"""Tests for the decision recommendation engine."""

from controltower.agents.forecasting import ForecastingAgent
from controltower.agents.inventory import InventoryAgent
from controltower.agents.risk import RiskAgent
from controltower.decision_engine import DecisionEngine
from controltower.models import Inventory, Recommendation, Shipment, ShipmentStatus


class TestDecisionEngine:
    def setup_method(self) -> None:
        self.engine = DecisionEngine([
            ForecastingAgent(),
            RiskAgent(),
            InventoryAgent(),
        ])

    def test_registered_agents(self) -> None:
        assert len(self.engine.agents) == 3

    def test_register_agent(self) -> None:
        from controltower.agents.route import RouteAgent
        self.engine.register_agent(RouteAgent())
        assert len(self.engine.agents) == 4

    def test_health(self) -> None:
        status = self.engine.health()
        assert all(v is True for v in status.values())

    def test_gather_recommendations_empty_context(self) -> None:
        recs = self.engine.gather_recommendations({})
        assert isinstance(recs, list)

    def test_decide_with_shipments(self) -> None:
        context = {
            "shipments": [
                Shipment(
                    origin="A", destination="B",
                    status=ShipmentStatus.DELAYED,
                    carrier="slow",
                    route_id="risky",
                ),
            ],
            "delay_rates": {"risky": 0.9, "slow": 0.8},
        }
        recs = self.engine.decide(context)
        assert isinstance(recs, list)
        assert all(isinstance(r, Recommendation) for r in recs)

    def test_decide_with_inventory(self) -> None:
        context = {
            "inventory": [
                Inventory(
                    sku="SKU-A", warehouse="W1",
                    quantity=2, reorder_point=10, reorder_qty=50,
                ),
            ],
        }
        recs = self.engine.decide(context)
        assert len(recs) >= 1

    def test_prioritize(self) -> None:
        recs = [
            Recommendation(agent="a", priority=3, title="Low", confidence=0.5),
            Recommendation(agent="b", priority=1, title="High", confidence=0.9),
            Recommendation(agent="c", priority=1, title="High2", confidence=0.7),
        ]
        ordered = self.engine.prioritize(recs)
        assert ordered[0].title == "High"
        assert ordered[1].title == "High2"

    def test_prioritize_limit(self) -> None:
        recs = [
            Recommendation(agent="a", priority=i, title=f"R{i}", confidence=0.5)
            for i in range(10)
        ]
        limited = self.engine.prioritize(recs, limit=3)
        assert len(limited) == 3

    def test_deduplicate(self) -> None:
        recs = [
            Recommendation(agent="a", priority=1, title="Same", confidence=0.5),
            Recommendation(agent="b", priority=1, title="Same", confidence=0.9),
        ]
        unique = DecisionEngine._deduplicate(recs)
        assert len(unique) == 1
        assert unique[0].confidence == 0.9
