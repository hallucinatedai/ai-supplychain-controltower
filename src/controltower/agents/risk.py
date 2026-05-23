"""Risk detection and scoring agent."""

from __future__ import annotations

from typing import Any

from controltower.agents.base import BaseAgent
from controltower.models import (
    AlertSeverity,
    Recommendation,
    Shipment,
    ShipmentStatus,
)

_HIGH_RISK_THRESHOLD = 0.7
_MEDIUM_RISK_THRESHOLD = 0.4


class RiskAgent(BaseAgent):
    """Scores shipments and routes for risk based on rules and history."""

    @property
    def name(self) -> str:
        return "risk"

    def analyze(self, context: dict[str, Any]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        shipments: list[Shipment] = context.get("shipments", [])
        delay_rates: dict[str, float] = context.get("delay_rates", {})

        for shipment in shipments:
            score = self.score_shipment(shipment, delay_rates)
            if score >= _HIGH_RISK_THRESHOLD:
                recommendations.append(
                    Recommendation(
                        agent=self.name,
                        priority=1,
                        title=f"High risk shipment: {shipment.id}",
                        description=(
                            f"Risk score {score:.2f} for {shipment.origin} → {shipment.destination}"
                        ),
                        action="Escalate to logistics manager and prepare contingency route",
                        confidence=min(score, 1.0),
                    )
                )
            elif score >= _MEDIUM_RISK_THRESHOLD:
                recommendations.append(
                    Recommendation(
                        agent=self.name,
                        priority=2,
                        title=f"Elevated risk shipment: {shipment.id}",
                        description=f"Risk score {score:.2f}",
                        action="Monitor closely and notify operations team",
                        confidence=min(score, 1.0),
                    )
                )

        return recommendations

    def score_shipment(
        self,
        shipment: Shipment,
        delay_rates: dict[str, float] | None = None,
    ) -> float:
        """Return a risk score in [0, 1] for a shipment."""
        score = 0.0
        delay_rates = delay_rates or {}

        if shipment.status == ShipmentStatus.DELAYED:
            score += 0.4

        route_delay_rate = delay_rates.get(shipment.route_id or "", 0.0)
        score += route_delay_rate * 0.3

        carrier_delay_rate = delay_rates.get(shipment.carrier, 0.0)
        score += carrier_delay_rate * 0.2

        if shipment.weight_kg > 10_000:
            score += 0.1

        return min(round(score, 3), 1.0)

    def classify_severity(self, score: float) -> AlertSeverity:
        if score >= 0.8:
            return AlertSeverity.CRITICAL
        if score >= _HIGH_RISK_THRESHOLD:
            return AlertSeverity.HIGH
        if score >= _MEDIUM_RISK_THRESHOLD:
            return AlertSeverity.MEDIUM
        return AlertSeverity.LOW
