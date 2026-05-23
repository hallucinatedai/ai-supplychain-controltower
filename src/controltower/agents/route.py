"""Route intelligence agent for optimization and recommendations."""

from __future__ import annotations

from typing import Any

from controltower.agents.base import BaseAgent
from controltower.models import Recommendation, Route


class RouteAgent(BaseAgent):
    """Optimizes and recommends routes based on constraints."""

    @property
    def name(self) -> str:
        return "route"

    def analyze(self, context: dict[str, Any]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        routes: list[Route] = context.get("routes", [])
        origin: str = context.get("origin", "")
        destination: str = context.get("destination", "")

        if origin and destination and routes:
            best = self.recommend_route(routes, origin, destination)
            if best:
                recommendations.append(
                    Recommendation(
                        agent=self.name,
                        priority=1,
                        title=f"Recommended route: {best.id}",
                        description=(
                            f"{best.origin} → {best.destination} "
                            f"({best.distance_km:.0f} km, "
                            f"{best.estimated_hours:.1f} h, "
                            f"risk {best.risk_score:.2f})"
                        ),
                        action=f"Use route {best.id}",
                        confidence=max(0.0, 1.0 - best.risk_score),
                    )
                )

        for route in routes:
            if route.risk_score >= 0.7:
                recommendations.append(
                    Recommendation(
                        agent=self.name,
                        priority=2,
                        title=f"High-risk route: {route.id}",
                        description=(
                            f"Route {route.origin} → {route.destination} "
                            f"has risk score {route.risk_score:.2f}"
                        ),
                        action="Consider alternative routes",
                        confidence=0.8,
                    )
                )

        return recommendations

    def recommend_route(
        self,
        routes: list[Route],
        origin: str,
        destination: str,
        max_risk: float = 0.6,
    ) -> Route | None:
        """Select the best route matching origin/destination under risk threshold."""
        candidates = [
            r
            for r in routes
            if r.origin == origin
            and r.destination == destination
            and r.is_active
            and r.risk_score <= max_risk
        ]
        if not candidates:
            # fall back: any active route for origin/destination
            candidates = [
                r
                for r in routes
                if r.origin == origin and r.destination == destination and r.is_active
            ]
        if not candidates:
            return None

        return min(candidates, key=lambda r: self._route_score(r))

    @staticmethod
    def _route_score(route: Route) -> float:
        """Lower is better. Combines cost, time, and risk."""
        return route.cost * 0.3 + route.estimated_hours * 0.3 + route.risk_score * 100 * 0.4

    def rank_routes(self, routes: list[Route]) -> list[Route]:
        """Return routes sorted best-first."""
        return sorted(routes, key=lambda r: RouteAgent._route_score(r))
