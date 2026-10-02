"""Shared entity helpers."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PRINTER_NAME, CONF_SERIAL, DOMAIN
from .coordinator import PrinterControlCenterCoordinator


class PrinterControlCenterPrinterEntity(CoordinatorEntity[PrinterControlCenterCoordinator]):
    """Base entity attached to the printer device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PrinterControlCenterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.serial = str(entry.data[CONF_SERIAL])

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=str(self.entry.data.get(CONF_PRINTER_NAME) or self.serial),
            manufacturer="Bambu Lab compatible",
            model=getattr(self.coordinator.snapshot, "printer_model", "") or "3D Printer",
            configuration_url="https://github.com/Taracraft/3D-Printer-Control-Center",
        )