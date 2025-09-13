from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN

PLATFORMS = ["sensor"]

SERVICE_STATION_EVENT = "station_event"
STATION_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required("station_id"): cv.string,
        vol.Required("type"): cv.string,
    }
)

async def async_setup(hass: HomeAssistant, config: dict):
    async def handle_station_event(call: ServiceCall):
        hass.bus.async_fire(
            f"{DOMAIN}_{SERVICE_STATION_EVENT}",
            {
                "station_id": call.data["station_id"],
                "type": call.data["type"],
            },
        )

    hass.services.async_register(
        DOMAIN, SERVICE_STATION_EVENT, handle_station_event, STATION_EVENT_SCHEMA
    )

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "data": entry.data,
        "options": entry.options,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
