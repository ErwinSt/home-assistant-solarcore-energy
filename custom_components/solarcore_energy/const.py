DOMAIN = "solarcore_energy"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

CONF_UPDATE_INTERVAL = "update_interval"
CONF_SENSORS = "sensors"
DEFAULT_UPDATE_INTERVAL = 30

CONF_COST_PER_KWH = "cost_per_kwh"
DEFAULT_COST_PER_KWH = 0.2

# Sensor keys used by config and options flow
SENSOR_KEYS = [
    "power_total",
    "power1",
    "power2",
    "vol1",
    "vol2",
    "current1",
    "current2",
    "gridseq",
    "gridvolc",
    "temp",
    "total_energy",
    "today_energy",
    "forecast_energy",
    "estimated_savings",
    "station_capacity",
    "component_count",
    "inverter_efficiency",
    "power_imbalance",
    "last_update_time",
]

BASE_URL = "http://gf.rockcore-energy.com:9721/rcmi-manager"
LOGIN_ENDPOINT = f"{BASE_URL}/client/login"
STATION_LIST_ENDPOINT = f"{BASE_URL}/station/queryStationInfoList"
REALTIME_POWER_ENDPOINT = f"{BASE_URL}/inverter/queryInverterRealInfoList"
STATION_INFO_ENDPOINT = f"{BASE_URL}/station/queryStationInfo"

