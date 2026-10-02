"""Printer light zones."""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import time

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import PrinterControlCenterPrinterEntity


@dataclass(frozen=True)
class LightDescription:
    key: str
    name: str
    node: str
    icon: str


LIGHTS = (
    LightDescription("chamber_light", "Chamber light", "chamber_light", "mdi:lightbulb"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [PrinterControlCenterPrinterLight(coordinator, entry, description) for description in LIGHTS]
    )


class PrinterControlCenterPrinterLight(PrinterControlCenterPrinterEntity, LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator, entry, description: LightDescription) -> None:
        super().__init__(coordinator, entry)
        self.description = description
        self._attr_unique_id = f"{self.serial}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._optimistic_mode: str | None = None
        self._optimistic_until = 0.0

    def _reported_mode(self) -> str:
        lights = self.coordinator.snapshot.value("lights_report", default=[])
        if isinstance(lights, list):
            for item in lights:
                if isinstance(item, dict) and item.get("node") == self.description.node:
                    return str(item.get("mode", "off"))
        return "off"

    @property
    def is_on(self) -> bool:
        if self._optimistic_mode is not None and time.monotonic() < self._optimistic_until:
            return self._optimistic_mode in {"on", "flashing"}
        return self._reported_mode() in {"on", "flashing"}

    @property
    def extra_state_attributes(self):
        return {
            "led_node": self.description.node,
            "reported_mode": self._reported_mode(),
        }

    async def _async_set(self, mode: str) -> None:
        self._optimistic_mode = mode
        self._optimistic_until = time.monotonic() + 2.5
        self.async_write_ha_state()

        payload = {
            "system": {
                "sequence_id": "0",
                "command": "ledctrl",
                "led_node": self.description.node,
                "led_mode": mode,
                "led_on_time": 500,
                "led_off_time": 500,
                "loop_times": 1,
                "interval_time": 1000,
            }
        }
        try:
            await self.hass.async_add_executor_job(self.coordinator.publish, payload)
            await asyncio.sleep(0.8)
            await self.hass.async_add_executor_job(self.coordinator.request_full_status)
        finally:
            self._optimistic_until = time.monotonic() + 1.2
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set("on")

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set("off")