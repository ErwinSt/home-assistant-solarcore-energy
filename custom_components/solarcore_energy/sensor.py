import logging
from datetime import timedelta

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_PASSWORD,
    CONF_SENSORS,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGIN_ENDPOINT,
    REALTIME_POWER_ENDPOINT,
    STATION_INFO_ENDPOINT,
    STATION_LIST_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

MAX_ENERGY_JUMP_KWH = 5

SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="power_total",
        translation_key="power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power1",
        translation_key="power1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power2",
        translation_key="power2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="vol1",
        translation_key="vol1",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="vol2",
        translation_key="vol2",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current1",
        translation_key="current1",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement="A",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current2",
        translation_key="current2",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement="A",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="gridseq",
        translation_key="gridseq",
        native_unit_of_measurement="Hz",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="gridvolc",
        translation_key="gridvolc",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="V",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp",
        translation_key="temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="today_energy",
        translation_key="today_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="Wh",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    options = entry.options
    coordinator = RockcoreDataUpdateCoordinator(hass, entry.data, options)
    await coordinator.async_config_entry_first_refresh()

    enabled_sensors = options.get(
        CONF_SENSORS, [desc.key for desc in SENSOR_DESCRIPTIONS]
    )
    entities = []
    for station_id in coordinator.station_ids:
        inverter = coordinator.data.get(station_id, {})
        for description in SENSOR_DESCRIPTIONS:
            if description.key in enabled_sensors and description.key in inverter:
                entities.append(RockcoreSensor(coordinator, station_id, description))

    async_add_entities(entities, True)


class RockcoreSensor(CoordinatorEntity, SensorEntity):
    def __init__(
        self,
        coordinator: "RockcoreDataUpdateCoordinator",
        station_id: int,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.station_id = station_id
        self.key = description.key
        self.entity_description = description
        self._attr_unique_id = f"rockcore_{station_id}_{description.key}"
        self._attr_has_entity_name = True

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
    def __init__(self, hass, config, options):
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.station_ids = []
        self.sensors = options.get(
            CONF_SENSORS, [desc.key for desc in SENSOR_DESCRIPTIONS]
        )
        self.session = async_get_clientsession(hass)
        update_seconds = options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_seconds),
        )

    async def _async_update_data(self):
        try:
            session = self.session
            token = await self._login(session, self.username, self.password)
            station_ids = await self._get_station_id(session, token)
            self.station_ids = station_ids
            data = {}
            for station_id in station_ids:
                power_data = await self._get_power(session, token, station_id)
                energy = await self._get_total_energy(session, token, station_id)
                energy = {k: v for k, v in energy.items() if k in self.sensors}

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

                inverter = power_data.get(station_id, {})
                inverter.update(energy)
                data[station_id] = inverter

            return data
        except Exception as err:
            raise UpdateFailed(f"Error updating data: {err}")

    async def _login(self, session, username, password):
        url = LOGIN_ENDPOINT
        payload = {"loginType": "1", "loginName": username, "password": password}
        async with session.post(url, json=payload) as resp:
            try:
                resp.raise_for_status()
            except aiohttp.ClientError as err:
                _LOGGER.error("Login request failed: %s", err)
                raise UpdateFailed(f"Login request failed: {err}") from err
            data = await resp.json()
            if "data" not in data or "token" not in data["data"]:
                _LOGGER.error("Login response missing required fields: %s", data)
                raise UpdateFailed("Missing token in login response")
            return data["data"]["token"]

    async def _get_station_id(self, session, token):
        url = STATION_LIST_ENDPOINT
        headers = {"Authorization": token}
        async with session.post(url, headers=headers, json={}) as resp:
            try:
                resp.raise_for_status()
            except aiohttp.ClientError as err:
                _LOGGER.error("Fetching station list failed: %s", err)
                raise UpdateFailed(f"Fetching station list failed: {err}") from err
            data = await resp.json()
            stations = data.get("data")
            if not stations:
                _LOGGER.error("Station list response missing 'data': %s", data)
                raise UpdateFailed("Missing stationId in station list response")
            ids = [s.get("stationId") for s in stations if s.get("stationId") is not None]
            if not ids:
                _LOGGER.error("Station list response missing 'stationId': %s", data)
                raise UpdateFailed("Missing stationId in station list response")
            return ids

    async def _get_power(self, session, token, station_id):
        url = REALTIME_POWER_ENDPOINT
        headers = {"Authorization": token}
        payload = {"stationId": station_id}
        async with session.post(url, headers=headers, json=payload) as resp:
            try:
                resp.raise_for_status()
            except aiohttp.ClientError as err:
                _LOGGER.error("Fetching power data failed: %s", err)
                raise UpdateFailed(f"Fetching power data failed: {err}") from err
            data = await resp.json()
            inverters = data.get("data")
            if inverters is None:
                _LOGGER.error("Power data response missing 'data': %s", data)
                raise UpdateFailed("Missing data in power response")
            result = {}
            if not inverters:
                return {station_id: result}
            inv = inverters[0]
            result = {
                desc.key: inv.get(desc.key, "0")
                for desc in SENSOR_DESCRIPTIONS
                if desc.key in inv and desc.key in self.sensors
            }
            if "power_total" in self.sensors:
                result["power_total"] = sum(
                    int(inv.get(k, "0W").replace("W", ""))
                    if inv.get(k, "0W").replace("W", "").isdigit()
                    else 0
                    for k in ["power1", "power2"]
                )
            return {station_id: result}

    async def _get_total_energy(self, session, token, station_id):
        url = STATION_INFO_ENDPOINT
        headers = {"Authorization": token}
        payload = {"stationId": station_id}
        async with session.post(url, headers=headers, json=payload) as resp:
            try:
                resp.raise_for_status()
            except aiohttp.ClientError as err:
                _LOGGER.error("Fetching energy data failed: %s", err)
                raise UpdateFailed(f"Fetching energy data failed: {err}") from err
            data = await resp.json()
            info = data.get("data")
            if info is None:
                _LOGGER.error("Energy data response missing 'data': %s", data)
                raise UpdateFailed("Missing data in energy response")
            return {
                "total_energy": float(info.get("totalEnergy", "0") or 0),
                "today_energy": float(info.get("todayEnergy", "0") or 0),
            }
