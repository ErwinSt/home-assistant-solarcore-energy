from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
):
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")

    last_update = None
    errors = None
    stations = None

    if coordinator:
        stations = coordinator.station_ids
        last_update = getattr(coordinator, "last_update_success_time", None)
        if last_update is not None:
            last_update = last_update.isoformat()
        if not getattr(coordinator, "last_update_success", True):
            err = getattr(coordinator, "last_exception", None)
            errors = str(err) if err else "Unknown error"

    return {
        "stations": stations,
        "last_update": last_update,
        "errors": errors,
    }
