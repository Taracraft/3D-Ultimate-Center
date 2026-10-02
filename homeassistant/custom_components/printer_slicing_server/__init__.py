from __future__ import annotations

from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SlicingServerApi
from .const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)
from .coordinator import SlicingServerCoordinator
from .frontend import async_register_frontend
from .websocket_api import async_register_websocket

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
SERVICE_UPLOAD_MODEL = "upload_model"
SERVICE_CREATE_JOB = "create_job"
EVENT_MODEL_UPLOADED = f"{DOMAIN}_model_uploaded"
EVENT_JOB_CREATED = f"{DOMAIN}_job_created"

UPLOAD_SCHEMA = vol.Schema({vol.Required("source_path"): cv.string, vol.Optional("target_filename"): cv.string})
CREATE_JOB_SCHEMA = vol.Schema({
    vol.Required("printer_profile"): cv.string,
    vol.Required("input_file"): cv.string,
    vol.Optional("engine", default="auto"): vol.In(["auto", "bambu_studio", "prusaslicer", "curaengine"]),
    vol.Optional("process_profile", default="default"): cv.string,
    vol.Optional("filament_profile", default="default"): cv.string,
    vol.Optional("output_format", default="gcode"): vol.In(["gcode", "3mf"]),
    vol.Optional("job_id"): cv.string,
})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if DOMAIN not in config:
        return True
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: DEFAULT_HOST, CONF_PORT: DEFAULT_PORT, CONF_API_TOKEN: ""},
        ))
    return True


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_CREATE_JOB):
        return

    def coordinator():
        for value in hass.data.get(DOMAIN, {}).values():
            if hasattr(value, "api"):
                return value
        raise RuntimeError("3D-Printer Slicing Server is not loaded")

    async def async_create_job(call: ServiceCall) -> None:
        current = coordinator()
        result = await current.api.create_job(dict(call.data))
        hass.bus.async_fire(EVENT_JOB_CREATED, result)
        await current.async_request_refresh()

    async def async_upload_model(call: ServiceCall) -> None:
        current = coordinator()
        source = Path(call.data["source_path"]).expanduser().resolve()
        allowed_root = Path(hass.config.path("3d-printer-slicing-server", "uploads")).resolve()
        await hass.async_add_executor_job(allowed_root.mkdir, 0o755, True, True)
        if source != allowed_root and allowed_root not in source.parents:
            raise ValueError(f"source_path must be below {allowed_root}")
        if not source.is_file():
            raise ValueError(f"Source file does not exist: {source}")
        target_filename = call.data.get("target_filename") or source.name
        content = await hass.async_add_executor_job(source.read_bytes)
        result = await current.api.upload_file(target_filename, content)
        hass.bus.async_fire(EVENT_MODEL_UPLOADED, result)

    hass.services.async_register(DOMAIN, SERVICE_CREATE_JOB, async_create_job, schema=CREATE_JOB_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_UPLOAD_MODEL, async_upload_model, schema=UPLOAD_SCHEMA)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = SlicingServerApi(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data.get(CONF_API_TOKEN, ""),
    )
    coordinator = SlicingServerCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await _async_register_services(hass)
    async_register_websocket(hass)
    await async_register_frontend(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not any(hasattr(value, "api") for value in hass.data.get(DOMAIN, {}).values()):
            if hass.services.has_service(DOMAIN, SERVICE_CREATE_JOB):
                hass.services.async_remove(DOMAIN, SERVICE_CREATE_JOB)
            if hass.services.has_service(DOMAIN, SERVICE_UPLOAD_MODEL):
                hass.services.async_remove(DOMAIN, SERVICE_UPLOAD_MODEL)
    return unloaded
