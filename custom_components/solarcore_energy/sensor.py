import logging
import aiohttp
from datetime import timedelta

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    LOGIN_ENDPOINT,
    STATION_LIST_ENDPOINT,
    REALTIME_POWER_ENDPOINT,
    STATION_INFO_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)
MAX_ENERGY_JUMP_KWH = 5

SENSOR_TYPES = {
    "power_total": ["Total Power", "W", SensorDeviceClass.POWER],
    "power1": ["Power 1", "W", SensorDeviceClass.POWER],
    "power2": ["Power 2", "W", SensorDeviceClass.POWER],
    "vol1": ["Voltage 1", "V", SensorDeviceClass.VOLTAGE],
    "vol2": ["Voltage 2", "V", SensorDeviceClass.VOLTAGE],
    "current1": ["Current 1", "A", SensorDeviceClass.CURRENT],
    "current2": ["Current 2", "A", SensorDeviceClass.CURRENT],
    "gridseq": ["Grid Freq", "Hz", None],
    "gridvolc": ["Grid Voltage", "V", SensorDeviceClass.VOLTAGE],
    "temp": ["Temperature", "°C", SensorDeviceClass.TEMPERATURE],
    "total_energy": ["Total Energy", "kWh", SensorDeviceClass.ENERGY],
    "today_energy": ["Today Energy", "Wh", SensorDeviceClass.ENERGY],
}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    coordinator = RockcoreDataUpdateCoordinator(hass, entry.data)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for station_id, inverter in coordinator.data.items():
        for key, (name, unit, device_class) in SENSOR_TYPES.items():
            if key in inverter:
                entities.append(RockcoreSensor(coordinator, station_id, key, name, unit, device_class))

    async_add_entities(entities, True)


class RockcoreSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, station_id, key, name, unit, device_class):
        super().__init__(coordinator)
        self.station_id = station_id
        self.key = key
        self._attr_name = f"Rockcore {station_id} {name}"
        self._attr_unique_id = f"rockcore_{station_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = None

        if key in ["total_energy", "today_energy"]:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def state(self):
        value = self.coordinator.data.get(self.station_id, {}).get(self.key)
        if isinstance(value, str):
            for suffix in ["W", "V", "A", "Hz", "℃", "°C", "kWh", "Wh"]:
                value = value.replace(suffix, "")
            try:
                return float(value)
            except ValueError:
                return None
        return value

    @property
    def state_class(self):
        """Return the state class of this entity."""
        if self.key in ["total_energy", "today_energy"]:
            return SensorStateClass.TOTAL_INCREASING
        return None
        
    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        attrs = {}
        if self.key in ["total_energy", "today_energy"]:
            attrs["state_class"] = "total_increasing"
        return attrs

    # Removed async_update as it's handled by CoordinatorEntity

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.station_id)},
            "name": f"Rockcore Station {self.station_id}",
            "manufacturer": "Rockcore",
            "model": "Inverter",
        }


class RockcoreDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config):
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        try:
            async with aiohttp.ClientSession() as session:
                token = await self._login(session, self.username, self.password)
                station_id = await self._get_station_id(session, token)
                data = await self._get_power(session, token, station_id)
                energy = await self._get_total_energy(session, token, station_id)

                previous = self.data.get(station_id, {}) if self.data else {}
                for key, new_val in energy.items():
                    prev_val = previous.get(key)
                    if prev_val is None:
                        continue
                    diff = new_val - prev_val
                    if key == "total_energy" and diff < 0:
                        _LOGGER.warning(
                            "Ignoring decrease in %s for station %s: %s -> %s",
                            key,
                            station_id,
                            prev_val,
                            new_val,
                        )
                        energy[key] = prev_val
                    elif diff > MAX_ENERGY_JUMP_KWH:
                        _LOGGER.warning(
                            "Ignoring unrealistic jump in %s for station %s: %s -> %s",
                            key,
                            station_id,
                            prev_val,
                            new_val,
                        )
                        energy[key] = prev_val

                data[station_id].update(energy)
                return data
        except Exception as err:
            raise UpdateFailed(f"Error updating data: {err}")

    async def _login(self, session, username, password):
        url = LOGIN_ENDPOINT
        payload = {"loginType": "1", "loginName": username, "password": password}
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            return data["data"]["token"]

    async def _get_station_id(self, session, token):
        url = STATION_LIST_ENDPOINT
        headers = {"Authorization": token}
        async with session.post(url, headers=headers, json={}) as resp:
            data = await resp.json()
            return data["data"][0]["stationId"]

    async def _get_power(self, session, token, station_id):
        url = REALTIME_POWER_ENDPOINT
        headers = {"Authorization": token}
        payload = {"stationId": station_id}
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            result = {}
            inverters = data.get("data", [])
            if not inverters:
                return {station_id: result}
            inv = inverters[0]
            result = {k: inv.get(k, "0") for k in SENSOR_TYPES.keys() if k in inv}
            result["power_total"] = sum(
                int(inv.get(k, "0W").replace("W", "")) if inv.get(k, "0W").replace("W", "").isdigit() else 0
                for k in ["power1", "power2"]
            )
            return {station_id: result}

    async def _get_total_energy(self, session, token, station_id):
        url = STATION_INFO_ENDPOINT
        headers = {"Authorization": token}
        payload = {"stationId": station_id}
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json()
            info = data.get("data", {})
            return {
                "total_energy": float(info.get("totalEnergy", "0") or 0),
                "today_energy": float(info.get("todayEnergy", "0") or 0),
            }
