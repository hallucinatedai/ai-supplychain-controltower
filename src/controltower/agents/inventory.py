"""Inventory optimization agent."""

from __future__ import annotations

from typing import Any

from controltower.agents.base import BaseAgent
from controltower.models import Inventory, Recommendation


class InventoryAgent(BaseAgent):
    """Monitors stock levels, predicts stockouts, suggests reorder points."""

    @property
    def name(self) -> str:
        return "inventory"

    def analyze(self, context: dict[str, Any]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        items: list[Inventory] = context.get("inventory", [])
        avg_daily_demand: dict[str, float] = context.get("avg_daily_demand", {})

        for item in items:
            if self.is_below_reorder(item):
                recommendations.append(
                    Recommendation(
                        agent=self.name,
                        priority=1,
                        title=f"Reorder needed: {item.sku} @ {item.warehouse}",
                        description=(
                            f"Current qty {item.quantity} is at or below "
                            f"reorder point {item.reorder_point}"
                        ),
                        action=f"Order {item.reorder_qty} units of {item.sku}",
                        confidence=0.95,
                    )
                )

            demand = avg_daily_demand.get(item.sku, 0.0)
            if demand > 0:
                days_left = self.days_until_stockout(item, demand)
                if days_left <= 3:
                    recommendations.append(
                        Recommendation(
                            agent=self.name,
                            priority=1,
                            title=f"Stockout imminent: {item.sku}",
                            description=f"Estimated {days_left:.1f} days of stock remaining",
                            action="Expedite replenishment order",
                            confidence=0.9,
                        )
                    )
                elif days_left <= 7:
                    recommendations.append(
                        Recommendation(
                            agent=self.name,
                            priority=2,
                            title=f"Low stock warning: {item.sku}",
                            description=f"Estimated {days_left:.1f} days of stock remaining",
                            action="Plan replenishment",
                            confidence=0.85,
                        )
                    )

        return recommendations

    @staticmethod
    def is_below_reorder(item: Inventory) -> bool:
        return item.quantity <= item.reorder_point and item.reorder_point > 0

    @staticmethod
    def days_until_stockout(item: Inventory, avg_daily_demand: float) -> float:
        if avg_daily_demand <= 0:
            return float("inf")
        return item.quantity / avg_daily_demand

    @staticmethod
    def suggest_reorder_point(
        avg_daily_demand: float,
        lead_time_days: float,
        safety_factor: float = 1.5,
    ) -> int:
        """Calculate a suggested reorder point."""
        return max(1, int(avg_daily_demand * lead_time_days * safety_factor))

    @staticmethod
    def suggest_reorder_qty(
        avg_daily_demand: float,
        order_cycle_days: float = 30.0,
    ) -> int:
        """Calculate economic order quantity approximation."""
        return max(1, int(avg_daily_demand * order_cycle_days))
