"""Utility helpers for Solarcore Energy integration."""
from __future__ import annotations

from typing import Any, Optional


def parse_value(value: Any) -> Optional[float]:
    """Parse a numeric value from API strings.

    The Rockcore API often returns values as strings with units such as
    ``"0.5kW"`` or ``"500Wh"``. This helper converts those strings to floats
    expressed in the integration's native units:

    * Power values are returned in watts.
    * Energy values are returned in kilowatt-hours.
    * Other units like ``V``, ``A``, ``Hz`` and ``°C`` are stripped.
    """

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()

    multipliers = {
        "kw": 1000.0,  # kilowatts -> watts
        "w": 1.0,      # watts
        "kwh": 1.0,    # kilowatt-hours
        "wh": 0.001,   # watt-hours -> kilowatt-hours
    }
    for unit, multiplier in multipliers.items():
        if text.endswith(unit):
            text = text[:-len(unit)]
            try:
                return float(text) * multiplier
            except (TypeError, ValueError):
                return None

    for suffix in ["v", "a", "hz", "℃", "°c"]:
        text = text.replace(suffix, "")

    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_frequency(value: Any) -> Optional[float]:
    """Parse frequency value from API.

    The Rockcore API returns frequency in 1/100 Hz format.
    For example: 5003 means 50.03 Hz
    """
    if value is None:
        return None

    # First parse as normal value
    freq_raw = parse_value(value)
    if freq_raw is None:
        return None

    # Convert from 1/100 Hz to Hz
    return freq_raw / 100.0
