"""Native read-only camera platform for Ultimate 3D Studio."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .camera_native import NativePrinterCameraClient
from .const import (
    CONF_ACCESS_CODE,
    CONF_HOST,
    CONF_PRINTER_NAME,
    CONF_TLS_INSECURE,
    DEFAULT_PRINTER_NAME,
    DEFAULT_TLS_INSECURE,
    DOMAIN,
    NAME,
    VERSION,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = {**entry.data, **entry.options}
    host = str(config.get(CONF_HOST) or "").strip()
    access_code = str(config.get(CONF_ACCESS_CODE) or "").strip()
    if not host or not access_code:
        return
    async_add_entities(
        [
            Ultimate3DStudioCamera(
                entry=entry,
                host=host,
                access_code=access_code,
                printer_name=str(config.get(CONF_PRINTER_NAME) or DEFAULT_PRINTER_NAME),
                tls_insecure=bool(config.get(CONF_TLS_INSECURE, DEFAULT_TLS_INSECURE)),
            )
        ]
    )


class Ultimate3DStudioCamera(Camera):
    _attr_has_entity_name = True
    _attr_name = "Kamera"
    _attr_content_type = "image/jpeg"
    _attr_should_poll = False

    def __init__(
        self,
        *,
        entry: ConfigEntry,
        host: str,
        access_code: str,
        printer_name: str,
        tls_insecure: bool,
    ) -> None:
        super().__init__()
        self._entry = entry
        self._host = host
        self._printer_name = printer_name
        self._client = NativePrinterCameraClient(
            host=host,
            access_code=access_code,
            tls_insecure=tls_insecure,
            on_state_change=self._camera_state_changed,
        )
        self._attr_unique_id = f"{entry.entry_id}_native_camera"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self.hass.async_add_executor_job(self._client.start)

    async def async_will_remove_from_hass(self) -> None:
        await self.hass.async_add_executor_job(self._client.stop)
        await super().async_will_remove_from_hass()

    @callback
    def _write_camera_state(self) -> None:
        if self.hass is not None:
            self.async_write_ha_state()

    def _camera_state_changed(self) -> None:
        if self.hass is not None:
            self.hass.loop.call_soon_threadsafe(self._write_camera_state)

    @property
    def available(self) -> bool:
        return self._client.latest_frame is not None or self._client.connected

    @property
    def is_streaming(self) -> bool:
        return self._client.connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = asdict(self._client.runtime_status())
        status.update(
            {
                "provider": "bambu_native_tls_jpeg",
                "transport": "tls_tcp_6000",
                "read_only": True,
                "printer_name": self._printer_name,
            }
        )
        return status

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        return self._client.latest_frame

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title or NAME,
            manufacturer="Ultimate 3D Studio",
            model="Standalone Bambu LAN Runtime",
            sw_version=VERSION,
        )
