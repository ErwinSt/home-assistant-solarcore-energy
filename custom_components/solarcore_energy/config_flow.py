import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SENSORS,
    CONF_UPDATE_INTERVAL,
    CONF_COST_PER_KWH,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_COST_PER_KWH,
    DOMAIN,
    LOGIN_ENDPOINT,
    SENSOR_KEYS,
)


class RockcoreConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            payload = {
                "loginType": "1",
                "loginName": user_input[CONF_USERNAME],
                "password": user_input[CONF_PASSWORD],
            }
            try:
                async with session.post(LOGIN_ENDPOINT, json=payload) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    _ = data["data"]["token"]
            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403):
                    errors["base"] = "auth"
                else:
                    errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except (KeyError, ValueError):
                errors["base"] = "auth"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Solarcore Energy", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "info": "Entrez vos identifiants Solarcore"
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return RockcoreOptionsFlow(config_entry)


class RockcoreOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                    ): vol.All(int, vol.Range(min=1)),
                    vol.Required(
                        CONF_COST_PER_KWH,
                        default=options.get(CONF_COST_PER_KWH, DEFAULT_COST_PER_KWH),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_SENSORS,
                        default=options.get(CONF_SENSORS, SENSOR_KEYS),
                    ): cv.multi_select(SENSOR_KEYS),
                }
            ),
        )

