"""Binary sensor platform for Rockcore Solar integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SENSORS, DOMAIN
from .util import parse_value, parse_frequency

BINARY_SENSOR_DESCRIPTIONS: list[BinarySensorEntityDescription] = [
    BinarySensorEntityDescription(
        key="inverter_status",
        translation_key="inverter_status",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="grid_connected",
        translation_key="grid_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="production_active",
        translation_key="production_active",
        device_class=BinarySensorDeviceClass.POWER,
    ),
    BinarySensorEntityDescription(
        key="temperature_alert",
        translation_key="temperature_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="grid_frequency_ok",
        translation_key="grid_frequency_ok",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for station_id in coordinator.station_ids:
        for description in BINARY_SENSOR_DESCRIPTIONS:
            entities.append(RockcoreBinarySensor(coordinator, station_id, description))

    async_add_entities(entities, True)


class RockcoreBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Rockcore binary sensor."""

    def __init__(self, coordinator, station_id: int, description: BinarySensorEntityDescription):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.station_id = station_id
        self.entity_description = description
        self._attr_unique_id = f"rockcore_{station_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        data = self.coordinator.data.get(self.station_id, {})

        if self.entity_description.key == "inverter_status":
            # status "0" means OK/running
            status = data.get("status")
            if status is not None:
                return str(status) == "0"
            return None

        elif self.entity_description.key == "grid_connected":
            # Grid connected if voltage > 0
            grid_voltage = parse_value(data.get("gridvolc"))
            if grid_voltage is not None:
                return grid_voltage > 0
            return None

        elif self.entity_description.key == "production_active":
            # Production active if total power > 0
            power_total = data.get("power_total")
            if power_total is not None:
                return power_total > 0
            return None

        elif self.entity_description.key == "temperature_alert":
            # Alert if temperature > 60°C
            temp = parse_value(data.get("temp"))
            if temp is not None:
                return temp > 60
            return None

        elif self.entity_description.key == "grid_frequency_ok":
            # Frequency should be between 49-51Hz for normal operation
            freq_hz = parse_frequency(data.get("gridseq"))
            if freq_hz is not None:
                return 49 <= freq_hz <= 51
            return None

        return None

    @property
    def device_info(self):
        """Return device info."""
        station_name = self.coordinator.station_names.get(
            self.station_id, f"Station {self.station_id}"
        )
        return {
            "identifiers": {(DOMAIN, self.station_id)},
            "name": f"Rockcore {station_name}",
            "manufacturer": "Rockcore Energy",
            "model": "Solar Inverter",
            "sw_version": "1.1.0",
        }