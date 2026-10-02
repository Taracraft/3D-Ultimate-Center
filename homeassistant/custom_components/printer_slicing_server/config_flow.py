from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SlicingServerApi, SlicingServerApiError
from .const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)


class SlicingServerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate_and_create(self, data: dict[str, Any]):
        host = str(data.get(CONF_HOST, DEFAULT_HOST)).strip()
        port = int(data.get(CONF_PORT, DEFAULT_PORT))
        token = str(data.get(CONF_API_TOKEN, "")).strip()
        api = SlicingServerApi(
            async_get_clientsession(self.hass),
            host,
            port,
            token,
        )
        health = await api.health()
        await api.info()
        await self.async_set_unique_id(f"{host}:{port}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=health.get("application", "3D-Printer Slicing Server"),
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_API_TOKEN: token,
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]):
        try:
            return await self._validate_and_create(import_data)
        except SlicingServerApiError:
            return self.async_abort(reason="cannot_connect")

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                return await self._validate_and_create(user_input)
            except SlicingServerApiError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_API_TOKEN, default=""): str,
                }
            ),
            errors=errors,
        )