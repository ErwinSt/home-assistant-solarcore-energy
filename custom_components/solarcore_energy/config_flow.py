import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGIN_ENDPOINT


class RockcoreConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

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
                    data = await resp.json()
                    _ = data["data"]["token"]
            except (aiohttp.ClientError, KeyError, ValueError):
                errors["base"] = "auth"
            else:
                return self.async_create_entry(
                    title="Rockcore Solar", data=user_input
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
                "info": "Entrez vos identifiants Rockcore"
            },
        )

