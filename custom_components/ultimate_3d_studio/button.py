from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_RUNTIMES, DOMAIN, NAME, VERSION
from .models import PrinterSnapshot
from .runtime import Ultimate3DStudioRuntime


@dataclass(frozen=True, kw_only=True)
class StudioButtonDescription(ButtonEntityDescription):
    command: str


BUTTONS = (
    StudioButtonDescription(
        key="pause",
        name="Druck pausieren",
        icon="mdi:pause",
        command="pause",
    ),
    StudioButtonDescription(
        key="resume",
        name="Druck fortsetzen",
        icon="mdi:play",
        command="resume",
    ),
    StudioButtonDescription(
        key="retry",
        name="Fehlerbehebung erneut versuchen",
        icon="mdi:reload",
        command="retry",
    ),
    StudioButtonDescription(
        key="stop",
        name="Druck abbrechen",
        icon="mdi:stop",
        command="stop",
    ),
)

_RUNNING_STATES = {"running", "printing", "prepare", "preparing", "starting"}
_PAUSED_STATES = {"pause", "paused"}
_ACTIVE_STATES = _RUNNING_STATES | _PAUSED_STATES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime: Ultimate3DStudioRuntime = hass.data[DOMAIN][DATA_RUNTIMES][entry.entry_id]
    async_add_entities(
        [StudioPrinterButton(runtime, entry, description) for description in BUTTONS],
        update_before_add=True,
    )


class StudioPrinterButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = True
    entity_description: StudioButtonDescription

    def __init__(
        self,
        runtime: Ultimate3DStudioRuntime,
        entry: ConfigEntry,
        description: StudioButtonDescription,
    ) -> None:
        self._runtime = runtime
        self._entry = entry
        self.entity_description = description
        self._snapshot: PrinterSnapshot | None = None
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    async def async_update(self) -> None:
        snapshots = await self._runtime.async_printers()
        self._snapshot = snapshots[0] if snapshots else None

    async def async_press(self) -> None:
        snapshots = await self._runtime.async_printers()
        if not snapshots:
            raise RuntimeError("Printer not found")
        self._snapshot = snapshots[0]
        if not self._command_allowed(self._snapshot.printer_state):
            raise RuntimeError(
                f"Printer command {self.entity_description.command} is not allowed "
                f"while state is {self._snapshot.printer_state}"
            )
        if self.entity_description.command == "retry" and not self._snapshot.issues:
            raise RuntimeError("No active printer issue is available for retry")

        result = await self._runtime.async_command(
            self._snapshot.printer_id,
            self.entity_description.command,
        )
        if result is None or not result.accepted:
            raise RuntimeError("Printer command was not accepted")

    def _command_allowed(self, state: str) -> bool:
        normalized = str(state or "").casefold()
        if self.entity_description.command == "pause":
            return normalized in _RUNNING_STATES
        if self.entity_description.command in {"resume", "retry"}:
            return normalized in _PAUSED_STATES
        return normalized in _ACTIVE_STATES

    @property
    def available(self) -> bool:
        return (
            self._runtime.is_ready
            and self._runtime.provider_count > 0
            and self._snapshot is not None
            and self._snapshot.connection_state == "connected"
            and self._command_allowed(self._snapshot.printer_state)
            and (
                self.entity_description.command != "retry"
                or bool(self._snapshot.issues)
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._snapshot is None:
            return None
        primary = self._snapshot.issues[0] if self._snapshot.issues else {}
        return {
            "printer_id": self._snapshot.printer_id,
            "printer_state": self._snapshot.printer_state,
            "active_issue_count": len(self._snapshot.issues),
            "active_issue_code": primary.get("code"),
            "active_issue_message": primary.get("message"),
            "recommended_action": (
                "retry"
                if self.entity_description.command == "retry"
                else self.entity_description.command
            ),
            "help_url": primary.get("help_url"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title or NAME,
            manufacturer="Ultimate 3D Studio",
            model="Studio Standalone Bambu LAN Runtime",
            sw_version=VERSION,
        )
