from __future__ import annotations

import base64
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

REGISTERED_KEY = "_websocket_registered"


def _coordinator(hass: HomeAssistant):
    entries = hass.data.get(DOMAIN, {})
    for value in entries.values():
        if hasattr(value, "api"):
            return value
    raise RuntimeError("3D-Printer Slicing Server is not loaded")


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(REGISTERED_KEY):
        return
    websocket_api.async_register_command(hass, ws_overview)
    websocket_api.async_register_command(hass, ws_job)
    websocket_api.async_register_command(hass, ws_upload)
    websocket_api.async_register_command(hass, ws_create_job)
    websocket_api.async_register_command(hass, ws_download)
    websocket_api.async_register_command(hass, ws_delete_job)
    domain_data[REGISTERED_KEY] = True


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/overview"})
@websocket_api.async_response
async def ws_overview(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    api = coordinator.api
    info, status, engines, printers, files, jobs, capabilities, diagnostics = await api.overview()
    connection.send_result(msg["id"], {
        "info": info,
        "status": status,
        "engines": engines,
        "printers": printers,
        "files": files,
        "jobs": jobs,
        "capabilities": capabilities,
        "diagnostics": diagnostics,
    })


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/job", vol.Required("job_id"): str})
@websocket_api.async_response
async def ws_job(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    try:
        result = await coordinator.api.job(msg["job_id"])
    except Exception as exc:
        connection.send_error(msg["id"], "job_lookup_failed", str(exc))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/upload", vol.Required("filename"): str, vol.Required("content_base64"): str})
@websocket_api.async_response
async def ws_upload(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    try:
        content = base64.b64decode(msg["content_base64"], validate=True)
    except ValueError as exc:
        connection.send_error(msg["id"], "invalid_base64", str(exc))
        return
    if len(content) > 32 * 1024 * 1024:
        connection.send_error(msg["id"], "file_too_large", "Maximum panel upload size is 32 MiB")
        return
    result = await coordinator.api.upload_file(msg["filename"], content)
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/create_job", vol.Required("payload"): dict})
@websocket_api.async_response
async def ws_create_job(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    result = await coordinator.api.create_job(msg["payload"])
    await coordinator.async_request_refresh()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/download", vol.Required("job_id"): str})
@websocket_api.async_response
async def ws_download(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    filename, content = await coordinator.api.download_job(msg["job_id"])
    if len(content) > 64 * 1024 * 1024:
        connection.send_error(msg["id"], "file_too_large", "Maximum panel download size is 64 MiB")
        return
    connection.send_result(msg["id"], {"filename": filename, "content_base64": base64.b64encode(content).decode("ascii"), "size": len(content)})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/delete_job", vol.Required("job_id"): str})
@websocket_api.async_response
async def ws_delete_job(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    coordinator = _coordinator(hass)
    try:
        result = await coordinator.api.delete_job(msg["job_id"])
        await coordinator.async_request_refresh()
        connection.send_result(msg["id"], result)
    except Exception as exc:
        connection.send_error(msg["id"], "job_delete_failed", str(exc))
