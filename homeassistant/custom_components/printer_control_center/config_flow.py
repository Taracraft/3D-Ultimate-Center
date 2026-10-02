"""Config flow for the 3D-Printer Control Center integration."""
from __future__ import annotations

DISPLAY_NAME_HINT = "Wichtiger Hinweis: Dieser Name wird im Dashboard angezeigt, falls kein Modellname automatisch erkannt wird. Verwende einen sprechenden Namen, z. B. Bambu Lab A1, Werkstatt X1 Carbon oder Drucker Büro."
from functools import partial
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .cloud_api import BambuCloudApi, CloudApiError, VerificationCodeRequired
from .const import (
    AMS_AUTO,
    AMS_OPTIONS,
    AMS_OPTIONS_EN,
    CAMERA_MODE_AUTO,
    CAMERA_MODE_OPTIONS,
    CAMERA_MODE_OPTIONS_EN,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_MODE,
    CONF_CAMERA_URL,
    CONF_ACCESS_CODE,
    CONF_ACCESS_TOKEN,
    CONF_AMS_TYPE,
    CONF_AUTO_CREATE_DASHBOARDS,
    CONF_AUTO_DISCOVER_IP,
    CONF_CLOUD_UID,
    CONF_DISCOVERY_HOSTS,
    CONF_DISCOVERY_PORTS,
    CONF_DISCOVERY_SUBNETS,
    CONF_EMAIL,
    CONF_HOST,
    CONF_MODE,
    CONF_PRINTER_NAME,
    CONF_RESCAN_ON_DISCONNECT,
    CONF_REFRESH_TOKEN,
    CONF_REGION,
    CONF_SCAN_BROADCAST,
    CONF_SCAN_CONNECTIONS,
    CONF_SCAN_MAX_HOSTS,
    CONF_SCAN_NEIGHBORS,
    CONF_SCAN_PROFILE,
    CONF_SCAN_ROUTES,
    CONF_SCAN_TIMEOUT_MS,
    CONF_SCAN_WORKERS,
    CONF_SERIAL,
    CONF_SHOW_MANUAL_FW_BUTTON,
    CONF_TLS_INSECURE,
    CONF_UI_LANGUAGE,
    DOMAIN,
    MODE_CLOUD,
    MODE_HYBRID,
    MODE_LAN,
    REGION_GLOBAL,
    SCAN_BALANCED,
    UI_LANGUAGE_AUTO,
    UI_LANGUAGE_OPTIONS,
)
from .discovery import DiscoveryCandidate, advanced_scan

_LOGGER = logging.getLogger(__name__)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any, default: bool = False) -> bool:
    return default if value is None else bool(value)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _effective_language(configured: Any, hass_language: Any = "en") -> str:
    """Return the language used for integration-owned dynamic choice labels."""
    choice = _clean(configured).lower()
    if choice in {"de", "en"}:
        return choice
    return "de" if _clean(hass_language).lower().startswith("de") else "en"



def _camera_mode_options(configured: Any, hass_language: Any = "en") -> dict[str, str]:
    """Return translated camera mode labels without changing persisted values."""
    return CAMERA_MODE_OPTIONS if _effective_language(configured, hass_language) == "de" else CAMERA_MODE_OPTIONS_EN

def _ams_options(configured: Any, hass_language: Any = "en") -> dict[str, str]:
    """Return translated AMS choice labels without changing persisted values."""
    return AMS_OPTIONS if _effective_language(configured, hass_language) == "de" else AMS_OPTIONS_EN


class PrinterControlCenterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._email = ""
        self._cloud_devices: list[dict[str, Any]] = []
        self._discovered: list[DiscoveryCandidate] = []

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._data[CONF_MODE] = user_input[CONF_MODE]
            self._data[CONF_UI_LANGUAGE] = user_input.get(CONF_UI_LANGUAGE, UI_LANGUAGE_AUTO)
            self._data[CONF_AUTO_CREATE_DASHBOARDS] = _bool(user_input.get(CONF_AUTO_CREATE_DASHBOARDS), True)
            if user_input[CONF_MODE] == MODE_LAN:
                return await self.async_step_lan()
            return await self.async_step_cloud_login()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE, default=MODE_HYBRID): vol.In(
                        {
                            MODE_LAN: "LAN only / Nur LAN",
                            MODE_CLOUD: "Bambu Cloud only / Nur Bambu Cloud",
                            MODE_HYBRID: "Hybrid: Cloud + LAN",
                        }
                    ),
                    vol.Required(CONF_UI_LANGUAGE, default=UI_LANGUAGE_AUTO): vol.In(UI_LANGUAGE_OPTIONS),
                    vol.Optional(CONF_AUTO_CREATE_DASHBOARDS, default=True): bool,
                }
            ),
        )

    async def async_step_cloud_login(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = _clean(user_input.get(CONF_EMAIL))
            region = _clean(user_input.get(CONF_REGION)) or REGION_GLOBAL
            api = BambuCloudApi(async_get_clientsession(self.hass), region)

            try:
                tokens = await api.login_password(
                    self._email,
                    _clean(user_input.get(CONF_PASSWORD)),
                )
            except VerificationCodeRequired:
                self._data[CONF_REGION] = region
                self._data[CONF_EMAIL] = self._email
                return await self.async_step_cloud_code()
            except CloudApiError:
                _LOGGER.exception("Cloud login failed")
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected Cloud login error")
                errors["base"] = "unknown"
            else:
                self._data.update(
                    {
                        CONF_REGION: region,
                        CONF_EMAIL: self._email,
                        CONF_ACCESS_TOKEN: tokens.access_token,
                        CONF_REFRESH_TOKEN: tokens.refresh_token,
                        CONF_CLOUD_UID: tokens.uid,
                    }
                )
                return await self._load_cloud_devices()

        return self.async_show_form(
            step_id="cloud_login",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION, default=REGION_GLOBAL): vol.In(
                        {"global": "Global / Europa", "china": "China"}
                    ),
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={"display_name_hint": DISPLAY_NAME_HINT},
        )

    async def async_step_cloud_code(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            api = BambuCloudApi(
                async_get_clientsession(self.hass),
                _clean(self._data.get(CONF_REGION)) or REGION_GLOBAL,
            )
            try:
                tokens = await api.login_code(self._email, _clean(user_input.get("code")))
            except CloudApiError:
                _LOGGER.exception("Cloud verification-code login failed")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected Cloud verification-code login error")
                errors["base"] = "unknown"
            else:
                self._data.update(
                    {
                        CONF_ACCESS_TOKEN: tokens.access_token,
                        CONF_REFRESH_TOKEN: tokens.refresh_token,
                        CONF_CLOUD_UID: tokens.uid,
                    }
                )
                return await self._load_cloud_devices()

        return self.async_show_form(
            step_id="cloud_code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
        )

    async def _load_cloud_devices(self):
        api = BambuCloudApi(
            async_get_clientsession(self.hass),
            _clean(self._data.get(CONF_REGION)) or REGION_GLOBAL,
        )

        try:
            self._cloud_devices = await api.get_devices(_clean(self._data.get(CONF_ACCESS_TOKEN)))
        except CloudApiError:
            _LOGGER.exception("Unable to load Cloud printers")
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected error while loading Cloud printers")
            return self.async_abort(reason="cannot_connect")

        if not self._cloud_devices:
            return self.async_abort(reason="no_printers")

        return await self.async_step_cloud_device()

    async def async_step_cloud_device(self, user_input=None):
        choices: dict[str, str] = {}
        by_serial: dict[str, dict[str, Any]] = {}

        for device in self._cloud_devices:
            serial = _clean(device.get("dev_id") or device.get("serial"))
            if not serial:
                continue
            name = _clean(
                device.get("name")
                or device.get("dev_product_name")
                or device.get("dev_name")
                or serial
            )
            choices[serial] = f"{name} · {serial}"
            by_serial[serial] = device

        if not choices:
            return self.async_abort(reason="no_printers")

        if user_input is not None:
            serial = _clean(user_input.get(CONF_SERIAL))
            selected = by_serial.get(serial, {})
            self._data.update(
                {
                    CONF_SERIAL: serial,
                    CONF_PRINTER_NAME: _clean(
                        selected.get("name")
                        or selected.get("dev_product_name")
                        or selected.get("dev_name")
                        or serial
                    ),
                }
            )

            if self._data.get(CONF_MODE) == MODE_HYBRID:
                return await self.async_step_lan()

            return await self.async_step_finish()

        return self.async_show_form(
            step_id="cloud_device",
            data_schema=vol.Schema({vol.Required(CONF_SERIAL): vol.In(choices)}),
        )

    def _scan_kwargs(self, user_input: dict[str, Any], serial: str) -> dict[str, Any]:
        return {
            "serial": serial,
            "configured_host": _clean(user_input.get(CONF_HOST)),
            "explicit_hosts": _clean(user_input.get(CONF_DISCOVERY_HOSTS)),
            "subnet_cidrs": _clean(user_input.get(CONF_DISCOVERY_SUBNETS)),
            "custom_ports": _clean(user_input.get(CONF_DISCOVERY_PORTS)),
            "profile": _clean(user_input.get(CONF_SCAN_PROFILE)) or SCAN_BALANCED,
            "timeout_ms": _int(user_input.get(CONF_SCAN_TIMEOUT_MS), 300),
            "workers": _int(user_input.get(CONF_SCAN_WORKERS), 128),
            "max_hosts": _int(user_input.get(CONF_SCAN_MAX_HOSTS), 2048),
            "include_broadcast": _bool(user_input.get(CONF_SCAN_BROADCAST), True),
            "include_neighbors": _bool(user_input.get(CONF_SCAN_NEIGHBORS), True),
            "include_connections": _bool(user_input.get(CONF_SCAN_CONNECTIONS), True),
            "include_routes": _bool(user_input.get(CONF_SCAN_ROUTES), True),
        }

    async def async_step_lan(self, user_input=None):
        errors: dict[str, str] = {}
        cloud_serial = _clean(self._data.get(CONF_SERIAL))
        cloud_name = _clean(self._data.get(CONF_PRINTER_NAME))

        if user_input is not None:
            serial = cloud_serial or _clean(user_input.get(CONF_SERIAL))
            host = _clean(user_input.get(CONF_HOST))
            access_code = _clean(user_input.get(CONF_ACCESS_CODE))
            printer_name = _clean(user_input.get(CONF_PRINTER_NAME)) or cloud_name or serial
            auto_discover = _bool(user_input.get(CONF_AUTO_DISCOVER_IP), True)

            if not serial:
                errors[CONF_SERIAL] = "required"
            if not access_code:
                errors[CONF_ACCESS_CODE] = "required"

            if not errors and auto_discover and not host:
                try:
                    report = await self.hass.async_add_executor_job(
                        partial(advanced_scan, **self._scan_kwargs(user_input, serial))
                    )
                except ValueError:
                    _LOGGER.exception("Invalid advanced network scan settings")
                    errors["base"] = "invalid_scan_settings"
                except Exception:
                    _LOGGER.exception("Advanced endpoint discovery failed")
                    errors["base"] = "discovery_failed"
                else:
                    self._discovered = report.candidates
                    if report.selected_host:
                        host = report.selected_host
                    elif len([item for item in report.candidates if item.mqtt_ready]) > 1:
                        self._data.update(
                            self._lan_values(user_input, serial, access_code, printer_name, host)
                        )
                        return await self.async_step_choose_discovered_host()
                    elif not host:
                        errors[CONF_HOST] = "discovery_failed"

            if not errors and not host:
                errors[CONF_HOST] = "required"

            if not errors:
                self._data.update(
                    self._lan_values(user_input, serial, access_code, printer_name, host)
                )
                return await self.async_step_finish()

        return self.async_show_form(
            step_id="lan",
            data_schema=self._lan_schema(cloud_serial, cloud_name),
            errors=errors,
        )

    def _lan_values(
        self,
        user_input: dict[str, Any],
        serial: str,
        access_code: str,
        printer_name: str,
        host: str,
    ) -> dict[str, Any]:
        return {
            CONF_HOST: host,
            CONF_SERIAL: serial,
            CONF_ACCESS_CODE: access_code,
            CONF_PRINTER_NAME: printer_name,
            CONF_TLS_INSECURE: _bool(user_input.get(CONF_TLS_INSECURE), True),
            CONF_AUTO_DISCOVER_IP: _bool(user_input.get(CONF_AUTO_DISCOVER_IP), False),
            CONF_DISCOVERY_SUBNETS: _clean(user_input.get(CONF_DISCOVERY_SUBNETS)),
            CONF_DISCOVERY_HOSTS: _clean(user_input.get(CONF_DISCOVERY_HOSTS)),
            CONF_DISCOVERY_PORTS: _clean(user_input.get(CONF_DISCOVERY_PORTS)),
            CONF_SCAN_PROFILE: _clean(user_input.get(CONF_SCAN_PROFILE)) or SCAN_BALANCED,
            CONF_SCAN_TIMEOUT_MS: _int(user_input.get(CONF_SCAN_TIMEOUT_MS), 300),
            CONF_SCAN_WORKERS: _int(user_input.get(CONF_SCAN_WORKERS), 128),
            CONF_SCAN_MAX_HOSTS: _int(user_input.get(CONF_SCAN_MAX_HOSTS), 2048),
            CONF_SCAN_BROADCAST: _bool(user_input.get(CONF_SCAN_BROADCAST), True),
            CONF_SCAN_NEIGHBORS: _bool(user_input.get(CONF_SCAN_NEIGHBORS), True),
            CONF_SCAN_CONNECTIONS: _bool(user_input.get(CONF_SCAN_CONNECTIONS), True),
            CONF_SCAN_ROUTES: _bool(user_input.get(CONF_SCAN_ROUTES), True),
            CONF_RESCAN_ON_DISCONNECT: _bool(user_input.get(CONF_RESCAN_ON_DISCONNECT), True),
        }

    def _lan_schema(self, cloud_serial: str, cloud_name: str) -> vol.Schema:
        values: dict[Any, Any] = {
            vol.Optional(CONF_HOST, default=_clean(self._data.get(CONF_HOST))): str,
            vol.Required(CONF_ACCESS_CODE): str,
            vol.Optional(
                CONF_PRINTER_NAME,
                default=cloud_name or _clean(self._data.get(CONF_PRINTER_NAME)) or "Bambu Lab printer",
            ): str,
            vol.Optional(CONF_AUTO_DISCOVER_IP, default=False): bool,
            vol.Optional(CONF_DISCOVERY_HOSTS, default=""): str,
            vol.Optional(CONF_DISCOVERY_SUBNETS, default=""): str,
            vol.Optional(CONF_SCAN_PROFILE, default=SCAN_BALANCED): vol.In(
                {"quick": "Quick", "balanced": "Balanced", "deep": "Deep"}
            ),
            vol.Optional(CONF_DISCOVERY_PORTS, default=""): str,
            vol.Optional(CONF_SCAN_TIMEOUT_MS, default=300): vol.Coerce(int),
            vol.Optional(CONF_SCAN_WORKERS, default=128): vol.Coerce(int),
            vol.Optional(CONF_SCAN_MAX_HOSTS, default=2048): vol.Coerce(int),
            vol.Optional(CONF_SCAN_BROADCAST, default=True): bool,
            vol.Optional(CONF_SCAN_NEIGHBORS, default=True): bool,
            vol.Optional(CONF_SCAN_CONNECTIONS, default=True): bool,
            vol.Optional(CONF_SCAN_ROUTES, default=True): bool,
            vol.Optional(CONF_RESCAN_ON_DISCONNECT, default=True): bool,
            vol.Optional(CONF_TLS_INSECURE, default=True): bool,
        }

        if not cloud_serial:
            values[vol.Required(CONF_SERIAL, default=_clean(self._data.get(CONF_SERIAL)))] = str

        return vol.Schema(values)

    async def async_step_choose_discovered_host(self, user_input=None):
        mqtt_candidates = [item for item in self._discovered if item.mqtt_ready]
        choices = {candidate.host: candidate.label for candidate in mqtt_candidates}

        if user_input is not None:
            self._data[CONF_HOST] = _clean(user_input.get(CONF_HOST))
            return await self.async_step_finish()

        return self.async_show_form(
            step_id="choose_discovered_host",
            data_schema=vol.Schema({vol.Required(CONF_HOST): vol.In(choices)}),
        )

    async def async_step_finish(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            serial = _clean(self._data.get(CONF_SERIAL))

            if not serial:
                return self.async_abort(reason="missing_serial")

            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=_clean(self._data.get(CONF_PRINTER_NAME)) or serial,
                data=self._data,
            )

        return self.async_show_form(
            step_id="finish",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AMS_TYPE, default=AMS_AUTO): vol.In(
                        _ams_options(self._data.get(CONF_UI_LANGUAGE), self.hass.config.language)
                    ),
                    vol.Required(CONF_CAMERA_MODE, default=CAMERA_MODE_AUTO): vol.In(
                        _camera_mode_options(self._data.get(CONF_UI_LANGUAGE), self.hass.config.language)
                    ),
                    vol.Optional(CONF_CAMERA_ENTITY, default=""): str,
                    vol.Optional(CONF_CAMERA_URL, default=""): str,
                    vol.Optional(CONF_SHOW_MANUAL_FW_BUTTON, default=False): bool,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Create options flow using HA's injected self.config_entry property."""
        return PrinterControlCenterOptionsFlow()


class PrinterControlCenterOptionsFlow(config_entries.OptionsFlow):
    """Advanced settings flow."""

    async def async_step_init(self, user_input=None):
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UI_LANGUAGE, default=current.get(CONF_UI_LANGUAGE, UI_LANGUAGE_AUTO)): vol.In(UI_LANGUAGE_OPTIONS),
                    vol.Optional(CONF_AUTO_CREATE_DASHBOARDS, default=_bool(current.get(CONF_AUTO_CREATE_DASHBOARDS), True)): bool,
                    vol.Required(CONF_AMS_TYPE, default=current.get(CONF_AMS_TYPE, AMS_AUTO)): vol.In(
                        _ams_options(current.get(CONF_UI_LANGUAGE), self.hass.config.language)
                    ),
                    vol.Required(CONF_CAMERA_MODE, default=current.get(CONF_CAMERA_MODE, CAMERA_MODE_AUTO)): vol.In(
                        _camera_mode_options(current.get(CONF_UI_LANGUAGE), self.hass.config.language)
                    ),
                    vol.Optional(CONF_CAMERA_ENTITY, default=_clean(current.get(CONF_CAMERA_ENTITY))): str,
                    vol.Optional(CONF_CAMERA_URL, default=_clean(current.get(CONF_CAMERA_URL))): str,
                    vol.Optional(CONF_SHOW_MANUAL_FW_BUTTON, default=_bool(current.get(CONF_SHOW_MANUAL_FW_BUTTON), False)): bool,
                    vol.Optional(CONF_HOST, default=_clean(current.get(CONF_HOST))): str,
                    vol.Optional(CONF_AUTO_DISCOVER_IP, default=_bool(current.get(CONF_AUTO_DISCOVER_IP), False)): bool,
                    vol.Optional(CONF_DISCOVERY_HOSTS, default=_clean(current.get(CONF_DISCOVERY_HOSTS))): str,
                    vol.Optional(CONF_DISCOVERY_SUBNETS, default=_clean(current.get(CONF_DISCOVERY_SUBNETS))): str,
                    vol.Optional(CONF_SCAN_PROFILE, default=_clean(current.get(CONF_SCAN_PROFILE)) or SCAN_BALANCED): vol.In(
                        {"quick": "Quick", "balanced": "Balanced", "deep": "Deep"}
                    ),
                    vol.Optional(CONF_DISCOVERY_PORTS, default=_clean(current.get(CONF_DISCOVERY_PORTS))): str,
                    vol.Optional(CONF_SCAN_TIMEOUT_MS, default=_int(current.get(CONF_SCAN_TIMEOUT_MS), 300)): vol.Coerce(int),
                    vol.Optional(CONF_SCAN_WORKERS, default=_int(current.get(CONF_SCAN_WORKERS), 128)): vol.Coerce(int),
                    vol.Optional(CONF_SCAN_MAX_HOSTS, default=_int(current.get(CONF_SCAN_MAX_HOSTS), 2048)): vol.Coerce(int),
                    vol.Optional(CONF_SCAN_BROADCAST, default=_bool(current.get(CONF_SCAN_BROADCAST), True)): bool,
                    vol.Optional(CONF_SCAN_NEIGHBORS, default=_bool(current.get(CONF_SCAN_NEIGHBORS), True)): bool,
                    vol.Optional(CONF_SCAN_CONNECTIONS, default=_bool(current.get(CONF_SCAN_CONNECTIONS), True)): bool,
                    vol.Optional(CONF_SCAN_ROUTES, default=_bool(current.get(CONF_SCAN_ROUTES), True)): bool,
                    vol.Optional(CONF_RESCAN_ON_DISCONNECT, default=_bool(current.get(CONF_RESCAN_ON_DISCONNECT), True)): bool,
                }
            ),
        )