"""Automatic Home Assistant, state and Python-log ingestion for the V6 audit log."""
from __future__ import annotations

import logging
import re
from typing import Any, Callable

from homeassistant.const import EVENT_CALL_SERVICE, EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .audit_log import get_audit_log
from .audit_safety import safe_audit_attributes
from .const import DOMAIN

DATA_AUDIT_RUNTIME = "audit_runtime_ingestion"
LOGGER_NAMES = (
    "custom_components.ultimate_3d_studio_v6",
    "custom_components.printer_slicing_server",
)
ENTITY_PLATFORMS = frozenset({
    "ultimate_3d_studio_v6",
    "printer_slicing_server",
})
SERVICE_DOMAINS = ENTITY_PLATFORMS



def _category(value: str) -> str:
    terms = set(re.findall(r"[a-z0-9]+", value.casefold()))
    if "makerworld" in terms:
        return "MakerWorld"
    if "gallery" in terms or "galerie" in terms:
        return "Galerie"
    if "profile" in terms or "profil" in terms:
        return "Profile"
    if "camera" in terms or "kamera" in terms:
        return "Kamera"
    if "ams" in terms or "filament" in terms:
        return "AMS"
    if ("slicing" in terms and "server" in terms) or "worker" in terms:
        return "Slicing-Server"
    if "slicer" in terms or "slice" in terms or "gcode" in terms:
        return "Slicer"
    if "print" in terms or "druck" in terms or "printer" in terms:
        return "Druck"
    if "studio" in terms or "scene" in terms or "model" in terms:
        return "Studio"
    return "System"


def _status(level: int) -> str:
    if level >= logging.ERROR:
        return "error"
    if level >= logging.WARNING:
        return "warning"
    return "info"


def _owned_entity(hass: HomeAssistant, entity_id: str) -> bool:
    entry = er.async_get(hass).async_get(entity_id)
    return entry is not None and entry.platform in ENTITY_PLATFORMS


def _attributes(state: Any) -> dict[str, Any]:
    return safe_audit_attributes(getattr(state, "attributes", {}) or {})



class V6AuditLoggingHandler(logging.Handler):
    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(logging.INFO)
        self.hass = hass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            details: dict[str, Any] = {
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "message": message,
            }
            if record.exc_info:
                details["exception"] = logging.Formatter().formatException(record.exc_info)
            self.hass.loop.call_soon_threadsafe(
                self.hass.async_create_task,
                get_audit_log(self.hass).async_append(
                    category=_category(record.name + " " + message),
                    component=record.name,
                    event="python_log",
                    status=_status(record.levelno),
                    source="home_assistant_log",
                    details=details,
                ),
            )
        except Exception:
            self.handleError(record)


async def async_start_audit_runtime(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if DATA_AUDIT_RUNTIME in data:
        return
    handler = V6AuditLoggingHandler(hass)
    loggers = [logging.getLogger(name) for name in LOGGER_NAMES]
    for logger in loggers:
        logger.addHandler(handler)
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)

    @callback
    def state_changed(event: Event) -> None:
        entity_id = str(event.data.get("entity_id") or "")
        if not entity_id or not _owned_entity(hass, entity_id):
            return
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        old_value = getattr(old_state, "state", None)
        new_value = getattr(new_state, "state", None)
        old_attributes = _attributes(old_state)
        new_attributes = _attributes(new_state)
        if old_value == new_value and old_attributes == new_attributes:
            return
        hass.async_create_task(get_audit_log(hass).async_append(
            category=_category(entity_id),
            component=entity_id,
            event="entity_state_changed",
            status="warning" if str(new_value).casefold() in {"unknown", "unavailable", "error", "failed"} else "info",
            source="home_assistant_state",
            details={
                "old_state": old_value,
                "new_state": new_value,
                "old_attributes": old_attributes,
                "new_attributes": new_attributes,
            },
        ))

    @callback
    def service_called(event: Event) -> None:
        domain = str(event.data.get("domain") or "")
        service = str(event.data.get("service") or "")
        service_data = event.data.get("service_data") or {}
        if domain not in SERVICE_DOMAINS:
            return
        combined = f"{domain}.{service} {service_data}"
        hass.async_create_task(get_audit_log(hass).async_append(
            category=_category(combined),
            component=f"service.{domain}",
            event=service,
            status="info",
            source="home_assistant_service",
            details={"service_data": service_data},
        ))

    unsubscribers: list[Callable[[], None]] = [
        hass.bus.async_listen(EVENT_STATE_CHANGED, state_changed),
        hass.bus.async_listen(EVENT_CALL_SERVICE, service_called),
    ]
    data[DATA_AUDIT_RUNTIME] = {
        "handler": handler,
        "loggers": loggers,
        "unsubscribers": unsubscribers,
    }
    await get_audit_log(hass).async_append(
        category="System",
        component="audit_runtime",
        event="audit_runtime_started",
        status="success",
        source="backend",
        details={"logger_names": list(LOGGER_NAMES)},
    )


async def async_stop_audit_runtime(hass: HomeAssistant) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    runtime = data.pop(DATA_AUDIT_RUNTIME, None)
    if not isinstance(runtime, dict):
        return
    for unsubscribe in runtime.get("unsubscribers", []):
        try:
            unsubscribe()
        except Exception:
            pass
    handler = runtime.get("handler")
    if isinstance(handler, logging.Handler):
        for logger in runtime.get("loggers", []):
            try:
                logger.removeHandler(handler)
            except Exception:
                pass
        handler.close()
