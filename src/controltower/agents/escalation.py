"""Escalation management agent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from controltower.agents.base import BaseAgent
from controltower.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Recommendation,
    Shipment,
    ShipmentStatus,
)


_DELAY_HOURS_THRESHOLD = 24
_CRITICAL_DELAY_HOURS = 48


class EscalationAgent(BaseAgent):
    """Detects anomalies, triggers alerts, manages escalation chains."""

    @property
    def name(self) -> str:
        return "escalation"

    def analyze(self, context: dict[str, Any]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        shipments: list[Shipment] = context.get("shipments", [])
        alerts: list[Alert] = context.get("alerts", [])

        # check for delayed shipments needing escalation
        for shipment in shipments:
            alert = self.check_shipment_escalation(shipment)
            if alert:
                severity_label = alert.severity.value
                recommendations.append(
                    Recommendation(
                        agent=self.name,
                        priority=1 if alert.severity in (
                            AlertSeverity.CRITICAL, AlertSeverity.HIGH
                        ) else 2,
                        title=alert.title,
                        description=alert.description,
                        action=alert.recommended_action,
                        confidence=0.9,
                        metadata={"severity": severity_label, "shipment_id": shipment.id},
                    )
                )

        # check for stale open alerts
        for alert in alerts:
            rec = self.check_stale_alert(alert)
            if rec:
                recommendations.append(rec)

        return recommendations

    def check_shipment_escalation(self, shipment: Shipment) -> Alert | None:
        """Check whether a shipment needs escalation and return an alert if so."""
        if shipment.status != ShipmentStatus.DELAYED:
            return None

        if not shipment.estimated_arrival:
            return Alert(
                title=f"Delayed shipment without ETA: {shipment.id}",
                description=f"Shipment {shipment.origin} → {shipment.destination} is delayed with no ETA",
                severity=AlertSeverity.HIGH,
                source_agent=self.name,
                related_entity_id=shipment.id,
                recommended_action="Contact carrier for updated ETA",
            )

        now = datetime.now(UTC)
        overdue = now - shipment.estimated_arrival
        overdue_hours = overdue.total_seconds() / 3600

        if overdue_hours >= _CRITICAL_DELAY_HOURS:
            return Alert(
                title=f"Critical delay: {shipment.id}",
                description=f"Shipment is {overdue_hours:.0f}h overdue",
                severity=AlertSeverity.CRITICAL,
                source_agent=self.name,
                related_entity_id=shipment.id,
                recommended_action="Escalate to senior management and activate contingency plan",
            )
        if overdue_hours >= _DELAY_HOURS_THRESHOLD:
            return Alert(
                title=f"Significant delay: {shipment.id}",
                description=f"Shipment is {overdue_hours:.0f}h overdue",
                severity=AlertSeverity.HIGH,
                source_agent=self.name,
                related_entity_id=shipment.id,
                recommended_action="Notify customer and explore alternative delivery options",
            )
        if overdue_hours > 0:
            return Alert(
                title=f"Minor delay: {shipment.id}",
                description=f"Shipment is {overdue_hours:.0f}h overdue",
                severity=AlertSeverity.MEDIUM,
                source_agent=self.name,
                related_entity_id=shipment.id,
                recommended_action="Monitor and prepare escalation if delay worsens",
            )

        return None

    def check_stale_alert(
        self,
        alert: Alert,
        stale_hours: float = 24.0,
    ) -> Recommendation | None:
        """Return a recommendation if the alert is open and unattended too long."""
        if alert.status not in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED):
            return None

        age = datetime.now(UTC) - alert.created_at
        if age > timedelta(hours=stale_hours):
            return Recommendation(
                agent=self.name,
                priority=1,
                title=f"Stale alert: {alert.title}",
                description=f"Alert has been {alert.status.value} for {age.total_seconds() / 3600:.0f}h",
                action="Review and resolve or escalate",
                confidence=0.85,
                metadata={"alert_id": alert.id},
            )
        return None
