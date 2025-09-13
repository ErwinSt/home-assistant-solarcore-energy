"""Solar production forecast helpers."""

from __future__ import annotations

from typing import Dict


async def async_calculate_forecast(data: Dict[str, float], cost_per_kwh: float) -> Dict[str, float]:
    """Return a simple energy forecast and estimated savings.

    The forecast uses today's energy production as the prediction for
    the next period. Estimated savings are calculated by multiplying the
    forecast energy by the configured cost per kWh.
    """
    today_energy = data.get("today_energy")
    if today_energy is None:
        return {}

    forecast_energy = today_energy
    estimated_savings = forecast_energy * cost_per_kwh
    return {
        "forecast_energy": forecast_energy,
        "estimated_savings": round(estimated_savings, 2),
    }
