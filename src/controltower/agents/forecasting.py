"""Demand and delay forecasting agent using simple statistical methods."""

from __future__ import annotations

from typing import Any

import numpy as np

from controltower.agents.base import BaseAgent
from controltower.models import Forecast, Recommendation


class ForecastingAgent(BaseAgent):
    """Generates demand and delay forecasts using moving averages and trends."""

    @property
    def name(self) -> str:
        return "forecasting"

    def analyze(self, context: dict[str, Any]) -> list[Recommendation]:
        recommendations: list[Recommendation] = []
        historical: list[float] = context.get("historical_demand", [])
        if not historical:
            return recommendations

        forecast = self.forecast_demand(historical)
        mean_forecast = float(np.mean(forecast.values)) if forecast.values else 0.0
        mean_historical = float(np.mean(historical)) if historical else 0.0

        if mean_historical > 0 and mean_forecast > mean_historical * 1.2:
            recommendations.append(
                Recommendation(
                    agent=self.name,
                    priority=1,
                    title="Demand surge predicted",
                    description=(
                        f"Forecasted demand ({mean_forecast:.1f}) is "
                        f"{((mean_forecast / mean_historical) - 1) * 100:.0f}% "
                        f"above historical average ({mean_historical:.1f})"
                    ),
                    action="Increase safety stock and notify procurement",
                    confidence=forecast.confidence,
                )
            )

        if mean_historical > 0 and mean_forecast < mean_historical * 0.8:
            recommendations.append(
                Recommendation(
                    agent=self.name,
                    priority=2,
                    title="Demand decline predicted",
                    description=(
                        f"Forecasted demand ({mean_forecast:.1f}) is below "
                        f"historical average ({mean_historical:.1f})"
                    ),
                    action="Review inventory levels and reduce replenishment",
                    confidence=forecast.confidence,
                )
            )

        return recommendations

    def forecast_demand(
        self,
        historical: list[float],
        horizon: int = 7,
        window: int = 5,
    ) -> Forecast:
        """Produce a simple forecast using weighted moving average + linear trend."""
        arr = np.array(historical, dtype=np.float64)
        if len(arr) < 2:
            return Forecast(
                target="demand",
                metric="units",
                horizon_days=horizon,
                values=list(arr) * horizon if len(arr) else [0.0] * horizon,
                confidence=0.1,
            )

        # weighted moving average
        w = min(window, len(arr))
        weights = np.arange(1, w + 1, dtype=np.float64)
        wma = float(np.average(arr[-w:], weights=weights))

        # linear trend via least-squares
        x = np.arange(len(arr), dtype=np.float64)
        coeffs = np.polyfit(x, arr, 1)
        slope = float(coeffs[0])

        forecasted: list[float] = []
        for i in range(1, horizon + 1):
            value = wma + slope * i
            forecasted.append(max(value, 0.0))

        # simple confidence based on coefficient of variation
        cv = float(np.std(arr) / np.mean(arr)) if np.mean(arr) != 0 else 1.0
        confidence = max(0.0, min(1.0, 1.0 - cv))

        return Forecast(
            target="demand",
            metric="units",
            horizon_days=horizon,
            values=forecasted,
            confidence=round(confidence, 3),
        )

    def forecast_delay(
        self,
        delay_history: list[float],
        horizon: int = 7,
    ) -> Forecast:
        """Forecast expected shipment delays in hours."""
        arr = np.array(delay_history, dtype=np.float64)
        if len(arr) < 2:
            mean_val = float(np.mean(arr)) if len(arr) else 0.0
            return Forecast(
                target="delay",
                metric="hours",
                horizon_days=horizon,
                values=[mean_val] * horizon,
                confidence=0.1,
            )

        mean_delay = float(np.mean(arr))
        std_delay = float(np.std(arr))
        forecasted = [round(mean_delay, 2)] * horizon
        confidence = max(0.0, min(1.0, 1.0 - (std_delay / mean_delay))) if mean_delay else 0.5

        return Forecast(
            target="delay",
            metric="hours",
            horizon_days=horizon,
            values=forecasted,
            confidence=round(confidence, 3),
        )
