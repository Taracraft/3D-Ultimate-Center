"""Camera recording switches."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PrinterControlCenterPrinterEntity


@dataclass(frozen=True)
class CameraSwitchDescription:
    key: str
    name: str
    command: str
    state_key: str
    icon: str


SWITCHES = (
    CameraSwitchDescription(
        "print_recording",
        "Print recording",
        "ipcam_record_set",
        "ipcam_record",
        "mdi:record-rec",
    ),
    CameraSwitchDescription(
        "timelapse_recording",
        "Timelapse recording",
        "ipcam_timelapse",
        "timelapse",
        "mdi:camera-timer",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PrinterControlCenterCameraRecordingSwitch(coordinator, entry, description)
            for description in SWITCHES
        ]
    )


class PrinterControlCenterCameraRecordingSwitch(PrinterControlCenterPrinterEntity, SwitchEntity):
    def __init__(self, coordinator, entry, description: CameraSwitchDescription) -> None:
        super().__init__(coordinator, entry)
        self.description = description
        self._attr_unique_id = f"{self.serial}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon

    @property
    def is_on(self) -> bool:
        ipcam = self.coordinator.snapshot.value("ipcam", default={})
        if not isinstance(ipcam, dict):
            return False
        return str(ipcam.get(self.description.state_key, "disable")).lower() == "enable"

    async def _async_set(self, enabled: bool) -> None:
        payload = {
            "camera": {
                "sequence_id": "0",
                "command": self.description.command,
                "control": "enable" if enabled else "disable",
            }
        }
        await self.hass.async_add_executor_job(self.coordinator.publish, payload)

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set(False)