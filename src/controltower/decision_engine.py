"""Decision recommendation engine aggregating agent outputs."""

from __future__ import annotations

import logging
from typing import Any

from controltower.agents.base import BaseAgent
from controltower.models import Recommendation

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Aggregates recommendations from all agents into prioritized action items."""

    def __init__(self, agents: list[BaseAgent] | None = None) -> None:
        self._agents: list[BaseAgent] = agents or []

    def register_agent(self, agent: BaseAgent) -> None:
        self._agents.append(agent)

    @property
    def agents(self) -> list[BaseAgent]:
        return list(self._agents)

    def gather_recommendations(self, context: dict[str, Any]) -> list[Recommendation]:
        """Run all agents and collect recommendations."""
        all_recs: list[Recommendation] = []
        for agent in self._agents:
            try:
                recs = agent.analyze(context)
                all_recs.extend(recs)
            except Exception:
                logger.exception("Agent %s failed during analysis", agent.name)
        return all_recs

    def prioritize(
        self,
        recommendations: list[Recommendation],
        limit: int = 20,
    ) -> list[Recommendation]:
        """Return recommendations sorted by priority (ascending) then confidence (descending)."""
        sorted_recs = sorted(
            recommendations,
            key=lambda r: (r.priority, -r.confidence),
        )
        return sorted_recs[:limit]

    def decide(
        self,
        context: dict[str, Any],
        limit: int = 20,
    ) -> list[Recommendation]:
        """End-to-end: gather, deduplicate, and prioritize recommendations."""
        recs = self.gather_recommendations(context)
        unique = self._deduplicate(recs)
        return self.prioritize(unique, limit=limit)

    @staticmethod
    def _deduplicate(recs: list[Recommendation]) -> list[Recommendation]:
        """Remove recommendations with duplicate titles, keeping highest confidence."""
        seen: dict[str, Recommendation] = {}
        for rec in recs:
            existing = seen.get(rec.title)
            if existing is None or rec.confidence > existing.confidence:
                seen[rec.title] = rec
        return list(seen.values())

    def health(self) -> dict[str, bool]:
        """Return health status for every registered agent."""
        return {agent.name: agent.health_check() for agent in self._agents}
