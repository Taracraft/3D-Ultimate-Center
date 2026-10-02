"""Diagnostics with secret redaction."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_ACCESS_CODE, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, DOMAIN

TO_REDACT = {CONF_ACCESS_CODE, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry": async_redact_data({**entry.data, **entry.options}, TO_REDACT),
        "snapshot": {
            "online": coordinator.snapshot.online,
            "transport": coordinator.snapshot.transport,
            "detected_ams_type": coordinator.snapshot.detected_ams_type,
            "detection_confidence": coordinator.snapshot.detection_confidence,
            "telemetry": coordinator.snapshot.telemetry,
        },
    }