from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_RUNTIMES, DOMAIN, NAME, VERSION
from .models import PrinterSnapshot
from .runtime import Ultimate3DStudioRuntime

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime: Ultimate3DStudioRuntime = hass.data[DOMAIN][DATA_RUNTIMES][entry.entry_id]
    async_add_entities(
        [
            Ultimate3DStudioConnectionBinarySensor(runtime, entry),
            Ultimate3DStudioProblemBinarySensor(runtime, entry),
        ],
        update_before_add=True,
    )


class Ultimate3DStudioBaseBinarySensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(self, runtime: Ultimate3DStudioRuntime, entry: ConfigEntry) -> None:
        self._runtime = runtime
        self._entry = entry
        self._snapshot: PrinterSnapshot | None = None

    async def async_update(self) -> None:
        snapshots = await self._runtime.async_printers()
        self._snapshot = snapshots[0] if snapshots else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title or NAME,
            manufacturer="Ultimate 3D Studio",
            model="V6 Standalone Bambu LAN Runtime",
            sw_version=VERSION,
        )


class Ultimate3DStudioConnectionBinarySensor(Ultimate3DStudioBaseBinarySensor):
    _attr_name = "Druckerverbindung"
    _attr_icon = "mdi:lan-connect"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, runtime: Ultimate3DStudioRuntime, entry: ConfigEntry) -> None:
        super().__init__(runtime, entry)
        self._attr_unique_id = f"{entry.entry_id}_printer_connection"

    @property
    def is_on(self) -> bool:
        return self._snapshot is not None and self._snapshot.connection_state == "connected"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._snapshot is None:
            return None
        return {
            "printer_id": self._snapshot.printer_id,
            "printer_name": self._snapshot.name,
            "provider": self._snapshot.provider,
            "host": self._snapshot.host,
            "updated_at": self._snapshot.updated_at,
        }


class Ultimate3DStudioProblemBinarySensor(Ultimate3DStudioBaseBinarySensor):
    _attr_name = "Druckerstörung"
    _attr_icon = "mdi:alert-octagon"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, runtime: Ultimate3DStudioRuntime, entry: ConfigEntry) -> None:
        super().__init__(runtime, entry)
        self._attr_unique_id = f"{entry.entry_id}_printer_problem"

    @property
    def is_on(self) -> bool:
        return self._snapshot is not None and bool(self._snapshot.issues)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._snapshot is None:
            return None
        primary = self._snapshot.issues[0] if self._snapshot.issues else {}
        return {
            "printer_id": self._snapshot.printer_id,
            "printer_name": self._snapshot.name,
            "printer_state": self._snapshot.printer_state,
            "error_code": self._snapshot.error_code,
            "error_message": self._snapshot.error_message,
            "issue_count": len(self._snapshot.issues),
            "primary_issue_code": primary.get("code"),
            "primary_issue_message": primary.get("message"),
            "help_url": primary.get("help_url"),
            "qr_url": primary.get("qr_url"),
            "issues": self._snapshot.issues,
            "resume_available": self._snapshot.printer_state in {"pause", "paused"},
            "updated_at": self._snapshot.updated_at,
        }
