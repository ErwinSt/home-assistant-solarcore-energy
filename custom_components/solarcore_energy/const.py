DOMAIN = "solarcore_energy"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

CONF_UPDATE_INTERVAL = "update_interval"
CONF_SENSORS = "sensors"
DEFAULT_UPDATE_INTERVAL = 30

BASE_URL = "http://gf.rockcore-energy.com:9721/rcmi-manager"
LOGIN_ENDPOINT = f"{BASE_URL}/client/login"
STATION_LIST_ENDPOINT = f"{BASE_URL}/station/queryStationInfoList"
REALTIME_POWER_ENDPOINT = f"{BASE_URL}/inverter/queryInverterRealInfoList"
STATION_INFO_ENDPOINT = f"{BASE_URL}/station/queryStationInfo"

