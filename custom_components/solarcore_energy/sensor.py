import logging
from datetime import datetime, timedelta
import asyncio

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import issue_registry as ir
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
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
    CONF_COST_PER_KWH,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_COST_PER_KWH,
    DOMAIN,
    LOGIN_ENDPOINT,
    REALTIME_POWER_ENDPOINT,
    STATION_INFO_ENDPOINT,
    STATION_LIST_ENDPOINT,
)
from .forecast import async_calculate_forecast
from .util import parse_value, parse_frequency

_LOGGER = logging.getLogger(__name__)

MAX_ENERGY_JUMP_KWH = 5
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)

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
        device_class=SensorDeviceClass.FREQUENCY,
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
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
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
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="forecast_energy",
        translation_key="forecast_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kWh",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="estimated_savings",
        translation_key="estimated_savings",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="€",
        state_class=SensorStateClass.TOTAL,
    ),
    # Additional sensors from API data
    SensorEntityDescription(
        key="station_capacity",
        translation_key="station_capacity",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="kW",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="component_count",
        translation_key="component_count",
        native_unit_of_measurement="",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="inverter_efficiency",
        translation_key="inverter_efficiency",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power_imbalance",
        translation_key="power_imbalance",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement="W",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="last_update_time",
        translation_key="last_update_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

SENSOR_TYPES = {desc.key: desc for desc in SENSOR_DESCRIPTIONS}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    options = entry.options
    coordinator = RockcoreDataUpdateCoordinator(hass, entry.data, options)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = coordinator

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
    def native_value(self):
        """Return the value reported by the sensor in its native unit."""

        value = self.coordinator.data.get(self.station_id, {}).get(self.key)

        # Special handling for frequency sensor
        if self.key == "gridseq":
            return parse_frequency(value)

        return parse_value(value)

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        data = self.coordinator.data.get(self.station_id, {})
        attributes = {}

        # Add common attributes for all sensors
        if "time" in data:
            attributes["last_api_update"] = data["time"]

        if "status" in data:
            attributes["inverter_status_code"] = data["status"]

        if "cstatus" in data:
            attributes["connection_status_code"] = data["cstatus"]

        # Add specific attributes based on sensor type
        if self.key in ["power1", "power2", "power_total"]:
            attributes["smu_id"] = data.get("smuId")
            attributes["inverter_model"] = data.get("invModelId")
            attributes["smu_model"] = data.get("smuModelId")

        elif self.key == "temp":
            if "temp" in data:
                temp_val = parse_value(data["temp"])
                if temp_val and temp_val > 60:
                    attributes["temperature_warning"] = "High temperature detected"

        elif self.key in ["total_energy", "today_energy"]:
            attributes["energy_unit"] = "kWh"
            if "capacity" in data:
                attributes["station_capacity_kw"] = parse_value(data["capacity"])

        return attributes

    # Removed async_update as it's handled by CoordinatorEntity

    @property
    def device_info(self):
        station_name = self.coordinator.station_names.get(
            self.station_id, f"Station {self.station_id}"
        )
        return {
            "identifiers": {(DOMAIN, self.station_id)},
            "name": f"Rockcore {station_name}",
            "manufacturer": "Rockcore Energy",
            "model": "Solar Inverter",
            "sw_version": "1.0.0",
        }


class RockcoreDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config, options):
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.station_ids = []
        self.station_names = {}
        self.sensors = options.get(
            CONF_SENSORS, [desc.key for desc in SENSOR_DESCRIPTIONS]
        )
        self.cost_per_kwh = options.get(
            CONF_COST_PER_KWH, DEFAULT_COST_PER_KWH
        )
        self.session = async_get_clientsession(hass)
        update_seconds = options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        self.failed_updates = 0
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
                    if prev_val is None or new_val is None:
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
                    elif key in ["total_energy", "today_energy"] and diff > MAX_ENERGY_JUMP_KWH:
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
                forecast = await async_calculate_forecast(
                    inverter, self.cost_per_kwh
                )
                forecast = {k: v for k, v in forecast.items() if k in self.sensors}
                inverter.update(forecast)

                # Add calculated sensors
                calculated = await self._calculate_derived_sensors(station_id, inverter, energy)
                calculated = {k: v for k, v in calculated.items() if k in self.sensors}
                inverter.update(calculated)

                data[station_id] = inverter

            self.failed_updates = 0
            ir.async_delete_issue(self.hass, DOMAIN, "connection_error")
            return data
        except Exception as err:
            self.failed_updates += 1
            if self.failed_updates >= 3:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    "connection_error",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="connection_error",
                )
            raise UpdateFailed(f"Error updating data: {err}")

    async def _login(self, session, username, password):
        url = LOGIN_ENDPOINT
        payload = {"loginType": "1", "loginName": username, "password": password}
        try:
            async with session.post(url, json=payload, timeout=REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Login request failed: %s", err)
            raise UpdateFailed(f"Login request failed: {err}") from err
        if "data" not in data or "token" not in data["data"]:
            _LOGGER.error("Login response missing required fields: %s", data)
            raise UpdateFailed("Missing token in login response")
        return data["data"]["token"]

    async def _get_station_id(self, session, token):
        url = STATION_LIST_ENDPOINT
        headers = {"Authorization": token}
        try:
            async with session.post(url, headers=headers, json={}, timeout=REQUEST_TIMEOUT) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fetching station list failed: %s", err)
            raise UpdateFailed(f"Fetching station list failed: {err}") from err
        stations = data.get("data")
        if not stations:
            _LOGGER.error("Station list response missing 'data': %s", data)
            raise UpdateFailed("Missing stationId in station list response")
        ids = [s.get("stationId") for s in stations if s.get("stationId") is not None]
        if not ids:
            _LOGGER.error("Station list response missing 'stationId': %s", data)
            raise UpdateFailed("Missing stationId in station list response")

        # Store station names for better device naming
        self.station_names = {
            s.get("stationId"): s.get("stationName", f"Station {s.get('stationId')}")
            for s in stations if s.get("stationId") is not None
        }

        return ids

    async def _get_power(self, session, token, station_id):
        url = REALTIME_POWER_ENDPOINT
        headers = {"Authorization": token}
        payload = {"stationId": station_id}
        try:
            async with session.post(
                url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fetching power data failed: %s", err)
            raise UpdateFailed(f"Fetching power data failed: {err}") from err
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
                parse_value(inv.get(k, "0")) or 0.0 for k in ["power1", "power2"]
            )
        return {station_id: result}

    async def _get_total_energy(self, session, token, station_id):
        url = STATION_INFO_ENDPOINT
        headers = {"Authorization": token}
        payload = {"stationId": station_id}
        try:
            async with session.post(
                url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.error("Fetching energy data failed: %s", err)
            raise UpdateFailed(f"Fetching energy data failed: {err}") from err
        info = data.get("data")
        if info is None:
            _LOGGER.error("Energy data response missing 'data': %s", data)
            raise UpdateFailed("Missing data in energy response")

        return {
            "total_energy": parse_value(info.get("totalEnergy")) or 0.0,
            "today_energy": parse_value(info.get("todayEnergy")) or 0.0,
            "capacity": info.get("capacity"),
            "stationCount": info.get("stationCount"),
        }

    async def _calculate_derived_sensors(self, station_id: int, inverter_data: dict, station_info: dict) -> dict:
        """Calculate derived sensors from API data."""
        calculated = {}

        # Station capacity (from station info API)
        if "capacity" in station_info:
            capacity = parse_value(station_info["capacity"]) or 0.0
            calculated["station_capacity"] = capacity

        # Component count (from inverter API)
        if "cmpCount" in inverter_data:
            calculated["component_count"] = inverter_data.get("cmpCount", 0)

        # Inverter efficiency (current power vs capacity)
        power_total = inverter_data.get("power_total", 0)
        if "capacity" in station_info and power_total:
            capacity = parse_value(station_info["capacity"]) or 0.0
            if capacity > 0:
                # Convert capacity from kW to W for comparison
                capacity_w = capacity * 1000
                efficiency = min((power_total / capacity_w) * 100, 100)
                calculated["inverter_efficiency"] = round(efficiency, 2)

        # Power imbalance (difference between power1 and power2)
        power1 = parse_value(inverter_data.get("power1", "0")) or 0.0
        power2 = parse_value(inverter_data.get("power2", "0")) or 0.0
        calculated["power_imbalance"] = abs(power1 - power2)

        # Last update time (from inverter time field)
        if "time" in inverter_data:
            time_str = inverter_data["time"]
            try:
                # Parse format: "2025-09-13 22:34:10"
                update_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                calculated["last_update_time"] = update_time.isoformat()
            except (ValueError, TypeError):
                pass

        return calculated
