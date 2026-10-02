from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .const import API_BASE, DATA_RUNTIMES, DOMAIN, NAME, VERSION
from .models import PrinterSnapshot
from .runtime import Ultimate3DStudioRuntime

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)


class Ultimate3DStudioCoordinator(DataUpdateCoordinator[tuple[PrinterSnapshot, ...]]):
    def __init__(self, hass: HomeAssistant, runtime: Ultimate3DStudioRuntime) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Ultimate 3D Studio V6 printer snapshot",
            update_interval=SCAN_INTERVAL,
        )
        self.runtime = runtime

    async def _async_update_data(self) -> tuple[PrinterSnapshot, ...]:
        try:
            return await self.runtime.async_printers()
        except Exception as exc:
            raise UpdateFailed(f"Printer snapshot failed: {exc}") from exc

    @property
    def printer(self) -> PrinterSnapshot | None:
        return self.data[0] if self.data else None


@dataclass(frozen=True, kw_only=True)
class Ultimate3DStudioSensorDescription(SensorEntityDescription):
    value_fn: Callable[[PrinterSnapshot], Any]


def _primary_issue_code(printer: PrinterSnapshot) -> str:
    if not printer.issues:
        return "none"
    return str(printer.issues[0].get("code") or "unknown")


SENSOR_DESCRIPTIONS: tuple[Ultimate3DStudioSensorDescription, ...] = (
    Ultimate3DStudioSensorDescription(key="printer_state", name="Druckerstatus", icon="mdi:printer-3d-nozzle", value_fn=lambda p: p.printer_state),
    Ultimate3DStudioSensorDescription(key="active_issue", name="Aktive Druckerstörung", icon="mdi:alert-octagon", entity_category=EntityCategory.DIAGNOSTIC, value_fn=_primary_issue_code),
    Ultimate3DStudioSensorDescription(key="active_issue_count", name="Aktive Druckerstörungen", icon="mdi:alert-circle", entity_category=EntityCategory.DIAGNOSTIC, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: len(p.issues)),
    Ultimate3DStudioSensorDescription(key="progress", name="Fortschritt", icon="mdi:progress-clock", native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.progress),
    Ultimate3DStudioSensorDescription(key="nozzle_temperature", name="Düsentemperatur", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.nozzle_temperature),
    Ultimate3DStudioSensorDescription(key="nozzle_target_temperature", name="Düsenzieltemperatur", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.nozzle_target_temperature),
    Ultimate3DStudioSensorDescription(key="bed_temperature", name="Betttemperatur", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.bed_temperature),
    Ultimate3DStudioSensorDescription(key="bed_target_temperature", name="Bettzieltemperatur", device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.bed_target_temperature),
    Ultimate3DStudioSensorDescription(key="remaining_time", name="Restzeit", icon="mdi:timer-sand", device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.MINUTES, state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.remaining_time_minutes),
    Ultimate3DStudioSensorDescription(key="current_layer", name="Aktueller Layer", icon="mdi:layers", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.current_layer),
    Ultimate3DStudioSensorDescription(key="total_layers", name="Layer gesamt", icon="mdi:layers-triple", state_class=SensorStateClass.MEASUREMENT, value_fn=lambda p: p.total_layers),
    Ultimate3DStudioSensorDescription(key="speed_level", name="Geschwindigkeitsstufe", icon="mdi:speedometer", value_fn=lambda p: p.speed_level),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime: Ultimate3DStudioRuntime = hass.data[DOMAIN][DATA_RUNTIMES][entry.entry_id]
    coordinator = Ultimate3DStudioCoordinator(hass, runtime)
    await coordinator.async_config_entry_first_refresh()
    entities: list[SensorEntity] = [Ultimate3DStudioV6StatusSensor(coordinator, runtime, entry)]
    entities.extend(Ultimate3DStudioPrinterSensor(coordinator, entry, description) for description in SENSOR_DESCRIPTIONS)
    async_add_entities(entities)


class Ultimate3DStudioBaseSensor(CoordinatorEntity[Ultimate3DStudioCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: Ultimate3DStudioCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title or NAME,
            manufacturer="Ultimate 3D Studio",
            model="V6 Standalone Bambu LAN Runtime",
            sw_version=VERSION,
        )


class Ultimate3DStudioV6StatusSensor(Ultimate3DStudioBaseSensor):
    _attr_name = "Status"
    _attr_icon = "mdi:printer-3d-nozzle"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Ultimate3DStudioCoordinator, runtime: Ultimate3DStudioRuntime, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._runtime = runtime
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        return "ready" if self._runtime.is_ready else "stopped"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        health = self._runtime.health()
        snapshots = [snapshot.as_dict() for snapshot in (self.coordinator.data or ())]
        jobs = self._runtime.jobs.as_dict()
        latest_history = jobs["history"][0] if jobs["history"] else None
        return {
            "component_version": VERSION,
            "api_base": API_BASE,
            "provider_count": self._runtime.provider_count,
            "providers": health.get("providers", []),
            "printers": snapshots,
            "job_current_count": jobs["current_count"],
            "job_queue_count": jobs["queue_count"],
            "job_history_count": jobs["history_count"],
            "latest_history_job": latest_history,
            "snapshot_error": None if self.coordinator.last_update_success else str(self.coordinator.last_exception),
            "discovery_candidates": health.get("discovery_candidates", []),
            "discovery_error": health.get("discovery_error"),
            "started_at": self._runtime.started_at.isoformat() if self._runtime.started_at else None,
            "isolated_test_domain": DOMAIN,
        }


class Ultimate3DStudioPrinterSensor(Ultimate3DStudioBaseSensor):
    entity_description: Ultimate3DStudioSensorDescription

    def __init__(self, coordinator: Ultimate3DStudioCoordinator, entry: ConfigEntry, description: Ultimate3DStudioSensorDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        printer = self.coordinator.printer
        return self.entity_description.value_fn(printer) if printer is not None else None

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.printer is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        printer = self.coordinator.printer
        if printer is None:
            return None
        attributes: dict[str, Any] = {
            "printer_id": printer.printer_id,
            "printer_name": printer.name,
            "provider": printer.provider,
            "connection_state": printer.connection_state,
            "updated_at": printer.updated_at,
        }
        if self.entity_description.key in {"active_issue", "active_issue_count"}:
            attributes.update({
                "error_code": printer.error_code,
                "error_message": printer.error_message,
                "issue_count": len(printer.issues),
                "issues": printer.issues,
                "hms": printer.hms,
                "resume_available": printer.printer_state in {"pause", "paused"},
            })
        return attributes
