"""Sensor entities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AMS_AUTO,
    AMS_BMCU_370,
    AMS_4_SLOT_COMPATIBLE,
    AMS_OPTIONS,
    AMS_OPTIONS_EN,
    CONF_AMS_TYPE,
    CONF_AUTO_DISCOVER_IP,
    CONF_DISCOVERY_HOSTS,
    CONF_DISCOVERY_PORTS,
    CONF_DISCOVERY_SUBNETS,
    CONF_HOST,
    CONF_MODE,
    CONF_PRINTER_NAME,
    CONF_SCAN_PROFILE,
    CONF_SERIAL,
    CONF_UI_LANGUAGE,
    DOMAIN,
)
from .coordinator import PrinterControlCenterCoordinator
from .entity import PrinterControlCenterPrinterEntity
from .models import normalize_tray, safe_state


def _ams_labels(coordinator: PrinterControlCenterCoordinator) -> dict[str, str]:
    """Return AMS labels using the configured dashboard language."""
    language = str(coordinator.config.get(CONF_UI_LANGUAGE, "auto") or "auto").lower()
    if language == "auto":
        language = "de" if str(getattr(coordinator.hass.config, "language", "en") or "en").lower().startswith("de") else "en"
    return AMS_OPTIONS if language == "de" else AMS_OPTIONS_EN


def _ams_label(coordinator: PrinterControlCenterCoordinator, value: str) -> str:
    return _ams_labels(coordinator).get(value, value)


def _configured_ams_type(coordinator: PrinterControlCenterCoordinator) -> str:
    data_value = str(coordinator.entry.data.get(CONF_AMS_TYPE, AMS_AUTO))
    options_value = str(coordinator.entry.options.get(CONF_AMS_TYPE, ""))

    # If BMCU/BCMU-370 was selected in the setup wizard, keep that manual choice
    # stable. BMCU controllers can emulate official AMS identifiers, so automatic
    # detection remains diagnostic only in this case.
    if data_value == AMS_BMCU_370:
        return AMS_BMCU_370

    return options_value or data_value or AMS_AUTO


def _ams_display_label(coordinator: PrinterControlCenterCoordinator) -> str:
    configured = _configured_ams_type(coordinator)
    if configured and configured != AMS_AUTO:
        return _ams_label(coordinator, configured)

    detected = coordinator.snapshot.detected_ams_type
    if detected == AMS_BMCU_370:
        return _ams_label(coordinator, AMS_4_SLOT_COMPATIBLE)
    return _ams_label(coordinator, detected)


@dataclass(frozen=True)
class SensorDescription:
    key: str
    name: str
    value: Callable[[PrinterControlCenterCoordinator], Any]
    unit: str | None = None


DESCRIPTIONS = [
    SensorDescription("print_status", "Print status", lambda c: safe_state(c.snapshot.value("gcode_state", default="unknown"))),
    SensorDescription("progress", "Print progress", lambda c: c.snapshot.value("mc_percent", default=0), "%"),
    SensorDescription("current_layer", "Current layer", lambda c: c.snapshot.value("layer_num", default=0)),
    SensorDescription("total_layers", "Total layers", lambda c: c.snapshot.value("total_layer_num", default=0)),
    SensorDescription("remaining_time", "Remaining time", lambda c: c.snapshot.value("mc_remaining_time", default=0), "min"),
    SensorDescription("task_name", "Task name", lambda c: safe_state(c.snapshot.value("subtask_name", "gcode_file", default=""))),
    SensorDescription("nozzle_temperature", "Nozzle temperature", lambda c: c.snapshot.value("nozzle_temper", default=0), "°C"),
    SensorDescription("bed_temperature", "Bed temperature", lambda c: c.snapshot.value("bed_temper", default=0), "°C"),
    SensorDescription("wifi_signal", "Wi-Fi signal", lambda c: safe_state(c.snapshot.value("wifi_signal", default="unknown"))),
    SensorDescription("printer_model", "Printer model", lambda c: safe_state(getattr(c.snapshot, "printer_model", ""), default="Bambu Lab 3D Printer")),
    SensorDescription("speed_profile", "Speed profile", lambda c: safe_state(c.snapshot.value("spd_lvl", default="2"))),
    SensorDescription("camera_available", "Camera available", lambda c: str(bool(c.camera_status().get("camera_available"))).lower()),
    SensorDescription("camera_transport", "Camera transport", lambda c: safe_state(c.camera_status().get("camera_label", "disabled"))),
    SensorDescription("camera_port", "Camera port", lambda c: safe_state(c.camera_status().get("camera_port", ""), default="none")),
    SensorDescription("camera_last_error", "Camera last error", lambda c: safe_state(c.camera_status().get("camera_last_error", ""), default="none", limit=160)),
    SensorDescription("active_ams_slot", "Active AMS slot", lambda c: safe_state((c.snapshot.value("ams", default={}) or {}).get("tray_now", "unknown") if isinstance(c.snapshot.value("ams", default={}), dict) else "unknown")),
    SensorDescription("ams_slot_count", "AMS slot count", lambda c: sum(1 for slot in c.snapshot.ams_slots() if normalize_tray(slot).get("normalized_loaded"))),
    SensorDescription("connection_mode", "Active connection mode", lambda c: safe_state(c.snapshot.transport)),
    SensorDescription("ams_display_name", "AMS display name", lambda c: _ams_display_label(c)),
    SensorDescription("detected_ams_type", "Detected AMS type", lambda c: _ams_label(c, c.snapshot.detected_ams_type)),
    SensorDescription("ams_detection_confidence", "AMS detection confidence", lambda c: safe_state(c.snapshot.detection_confidence)),
    SensorDescription("firmware_status", "Firmware status", lambda c: c.snapshot.firmware_state()),
    SensorDescription("serial_number", "Serial number", lambda c: c.serial),
    SensorDescription("configured_host", "Configured printer IP", lambda c: safe_state(c.config.get(CONF_HOST, ""))),
    SensorDescription("active_host", "Active printer IP", lambda c: safe_state(c.active_host)),
    SensorDescription("configured_connection_mode", "Configured connection mode", lambda c: safe_state(c.config.get(CONF_MODE, ""))),
    SensorDescription("auto_discover_ip", "Automatic IP discovery", lambda c: str(bool(c.config.get(CONF_AUTO_DISCOVER_IP, False))).lower()),
    SensorDescription("discovery_subnets", "VLAN discovery subnets", lambda c: safe_state(c.config.get(CONF_DISCOVERY_SUBNETS, ""), default="none")),
    SensorDescription("discovery_hosts", "Seed endpoints", lambda c: safe_state(c.config.get(CONF_DISCOVERY_HOSTS, ""), default="none")),
    SensorDescription("discovery_ports", "Discovery TCP ports", lambda c: safe_state(c.config.get(CONF_DISCOVERY_PORTS, ""), default="profile-default")),
    SensorDescription("scan_profile", "Network scan profile", lambda c: safe_state(c.config.get(CONF_SCAN_PROFILE, "balanced"))),
    SensorDescription("ui_language", "Dashboard language", lambda c: safe_state(c.config.get(CONF_UI_LANGUAGE, "auto"))),
    SensorDescription("network_scan_summary", "Network scan summary", lambda c: safe_state(c.last_scan_report.summary if c.last_scan_report else "not-run")),
    SensorDescription("network_scan_candidates", "Network scan candidates", lambda c: len(c.last_scan_report.candidates) if c.last_scan_report else 0),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: PrinterControlCenterCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        PrinterControlCenterPrinterSensor(coordinator, entry, description)
        for description in DESCRIPTIONS
    ]

    entities.append(PrinterControlCenterFirmwareSensor(coordinator, entry))
    entities.append(PrinterControlCenterNetworkScanDetailsSensor(coordinator, entry))
    entities.append(PrinterControlCenterConfiguredAmsSensor(coordinator, entry))

    for index in range(4):
        entities.append(PrinterControlCenterAmsSlotSensor(coordinator, entry, index))

    entities.append(PrinterControlCenterExternalSpoolSensor(coordinator, entry))
    async_add_entities(entities)


class PrinterControlCenterPrinterSensor(PrinterControlCenterPrinterEntity, SensorEntity):
    def __init__(self, coordinator, entry, description: SensorDescription) -> None:
        super().__init__(coordinator, entry)
        self.description = description
        self._attr_unique_id = f"{self.serial}_{description.key}"
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.unit

    @property
    def native_value(self):
        return self.description.value(self.coordinator)


class PrinterControlCenterFirmwareSensor(PrinterControlCenterPrinterEntity, SensorEntity):
    _attr_name = "Firmware details"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_firmware_details"

    @property
    def native_value(self):
        return self.coordinator.snapshot.firmware_state()

    @property
    def extra_state_attributes(self):
        return self.coordinator.snapshot.firmware_attributes()


class PrinterControlCenterNetworkScanDetailsSensor(PrinterControlCenterPrinterEntity, SensorEntity):
    _attr_name = "Network scan details"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_network_scan_details"

    @property
    def native_value(self):
        report = self.coordinator.last_scan_report
        return safe_state(report.summary if report else "not-run")

    @property
    def extra_state_attributes(self):
        report = self.coordinator.last_scan_report
        if report is None:
            return {}

        return {
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            "profile": report.profile,
            "scanned_hosts": report.scanned_hosts,
            "selected_host": report.selected_host,
            "selected_source": report.selected_source,
            "error": report.error,
            "candidates": [
                {
                    "host": candidate.host,
                    "serial": candidate.serial,
                    "name": candidate.name,
                    "model": candidate.model,
                    "sources": sorted(candidate.sources),
                    "open_ports": sorted(candidate.open_ports),
                    "mqtt_ready": candidate.mqtt_ready,
                }
                for candidate in report.candidates
            ],
        }


class PrinterControlCenterConfiguredAmsSensor(PrinterControlCenterPrinterEntity, SensorEntity):
    _attr_name = "Configured AMS type"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_configured_ams_type"

    @property
    def native_value(self):
        value = _configured_ams_type(self.coordinator)
        return _ams_label(self.coordinator, value)


class PrinterControlCenterAmsSlotSensor(PrinterControlCenterPrinterEntity, SensorEntity):
    @property
    def device_info(self) -> DeviceInfo:
        configured = str({**self.entry.data, **self.entry.options}.get(CONF_AMS_TYPE, AMS_AUTO))
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.serial}_ams")},
            name=f"{self.serial} AMS",
            manufacturer="Bambu Lab compatible",
            model=_ams_label(self.coordinator, configured),
            via_device=(DOMAIN, self.serial),
            configuration_url="https://github.com/Taracraft/3D-Printer-Control-Center",
        )

    def __init__(self, coordinator, entry, index: int) -> None:
        super().__init__(coordinator, entry)
        self.index = index
        self._attr_unique_id = f"{self.serial}_ams_slot_{index + 1}"
        self._attr_name = f"AMS slot {index + 1}"

    @property
    def native_value(self):
        slots = self.coordinator.snapshot.ams_slots()
        if self.index >= len(slots):
            return "empty"
        slot = normalize_tray(slots[self.index])
        return safe_state(
            slot.get("normalized_material")
            or slot.get("tray_type")
            or slot.get("type")
            or slot.get("tray_info_idx")
            or "loaded"
        )

    @property
    def extra_state_attributes(self):
        slots = self.coordinator.snapshot.ams_slots()
        return normalize_tray(slots[self.index]) if self.index < len(slots) else {
            "normalized_material": "empty",
            "normalized_brand": "",
            "normalized_color": "#4A5568",
            "normalized_remaining": None,
            "normalized_loaded": False,
        }


class PrinterControlCenterExternalSpoolSensor(PrinterControlCenterPrinterEntity, SensorEntity):
    _attr_name = "External spool"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.serial}_external_spool")},
            name=f"{self.serial} External spool",
            manufacturer="Bambu Lab compatible",
            model="External spool",
            via_device=(DOMAIN, self.serial),
            configuration_url="https://github.com/Taracraft/3D-Printer-Control-Center",
        )

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_external_spool"

    @property
    def native_value(self):
        spool = normalize_tray(self.coordinator.snapshot.external_spool())
        return safe_state(
            spool.get("normalized_material")
            or spool.get("tray_type")
            or spool.get("type")
            or spool.get("tray_info_idx")
            or "unknown"
        )

    @property
    def extra_state_attributes(self):
        return normalize_tray(self.coordinator.snapshot.external_spool())