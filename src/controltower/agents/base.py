"""Base agent interface for all supply chain intelligence agents."""

from __future__ import annotations

import abc
from typing import Any

from controltower.models import Recommendation


class BaseAgent(abc.ABC):
    """Abstract base class for supply chain agents."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""

    @abc.abstractmethod
    def analyze(self, context: dict[str, Any]) -> list[Recommendation]:
        """Analyze the given context and return prioritized recommendations."""

    def health_check(self) -> bool:
        """Return ``True`` if the agent is operational."""
        return True
