"""Button entities."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .entity import PrinterControlCenterPrinterEntity

from .const import (
    CONF_SERIAL,
    CONF_SHOW_MANUAL_FW_BUTTON,
    DOMAIN,
    EVENT_MANUAL_FIRMWARE_UPDATE_REQUESTED,
)
from .coordinator import PrinterControlCenterCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        PrinterControlCenterNetworkScanButton(coordinator, entry),
        PrinterControlCenterCommandButton(coordinator, entry, "refresh", "Refresh data", {"pushing": {"sequence_id": "0", "command": "pushall", "version": 1, "push_target": 1}}),
        PrinterControlCenterCommandButton(coordinator, entry, "pause", "Pause printing", {"print": {"sequence_id": "0", "command": "pause"}}),
        PrinterControlCenterCommandButton(coordinator, entry, "resume", "Resume printing", {"print": {"sequence_id": "0", "command": "resume"}}),
        PrinterControlCenterCommandButton(coordinator, entry, "stop", "Stop printing", {"print": {"sequence_id": "0", "command": "stop"}}),
    ]
    if bool({**entry.data, **entry.options}.get(CONF_SHOW_MANUAL_FW_BUTTON, False)):
        entities.append(PrinterControlCenterManualFirmwareRequestButton(coordinator, entry))
    async_add_entities(entities)


class PrinterControlCenterCommandButton(PrinterControlCenterPrinterEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, payload) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_{key}"
        self._attr_name = name
        self.payload = payload

    async def async_press(self) -> None:
        await self.hass.async_add_executor_job(self.coordinator.publish, self.payload)


class PrinterControlCenterManualFirmwareRequestButton(PrinterControlCenterPrinterEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Request manual firmware update"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_manual_firmware_update_request"

    async def async_press(self) -> None:
        self.hass.bus.async_fire(
            EVENT_MANUAL_FIRMWARE_UPDATE_REQUESTED,
            {
                "serial": str(self.entry.data[CONF_SERIAL]),
                "transport": self.coordinator.snapshot.transport,
                "firmware_status": self.coordinator.snapshot.value(
                    "upgrade_display_state",
                    "upgrade_state",
                    default="unknown",
                ),
                "notice": (
                    "No OTA command was sent. This alpha intentionally exposes "
                    "a manual request event only."
                ),
            },
        )



class PrinterControlCenterNetworkScanButton(PrinterControlCenterPrinterEntity, ButtonEntity):
    _attr_name = "Scan network endpoints"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_scan_network_endpoints"

    async def async_press(self) -> None:
        await self.coordinator.async_scan_and_reload()