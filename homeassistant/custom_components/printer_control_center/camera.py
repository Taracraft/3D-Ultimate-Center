"""Native Home Assistant camera platform."""
from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capabilities import external_camera_entity, external_camera_url, rtsps_url
from .const import (
    CAMERA_MODE_CHAMBER_IMAGE_6000,
    CAMERA_MODE_EXTERNAL_ENTITY,
    CAMERA_MODE_EXTERNAL_URL,
    CAMERA_MODE_RTSPS_322,
    CONF_ACCESS_CODE,
    CONF_PRINTER_NAME,
    CONF_SERIAL,
    DOMAIN,
)
from .coordinator import PrinterControlCenterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Expose one capability-aware camera per printer."""
    coordinator: PrinterControlCenterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PrinterControlCenterCamera(coordinator, entry)])


class PrinterControlCenterCamera(Camera):
    """Expose a model-aware Bambu camera through Home Assistant.

    A1/P1/A2 families use the native Chamber Image / TCP 6000 reader.
    X1/H2/P2/X2 families expose a RTSPS stream source on TCP 322.
    Optional external HA camera entities and external URLs remain explicit fallbacks.
    """

    _attr_has_entity_name = True
    _attr_name = "Live camera"
    _attr_icon = "mdi:camera"
    _attr_brand = "3D-Printer Control Center"
    _attr_model = "Bambu camera capability router"
    _attr_frame_interval = 0.8
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: PrinterControlCenterCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__()
        self.coordinator = coordinator
        self.entry = entry
        self.serial = str(entry.data[CONF_SERIAL])
        self._attr_unique_id = f"{self.serial}_native_live_camera"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=str(self.entry.data.get(CONF_PRINTER_NAME) or self.serial),
            manufacturer="Bambu Lab compatible",
            model=getattr(self.coordinator.snapshot, "printer_model", "") or "3D Printer",
            configuration_url="https://github.com/Taracraft/3D-Printer-Control-Center",
        )

    @property
    def available(self) -> bool:
        status = self.coordinator.camera_status()
        mode = status.get("camera_mode")
        if mode == CAMERA_MODE_CHAMBER_IMAGE_6000:
            return self.coordinator.camera_client is not None
        if mode == CAMERA_MODE_RTSPS_322:
            return bool(status.get("camera_available"))
        if mode == CAMERA_MODE_EXTERNAL_ENTITY:
            entity_id = external_camera_entity(self.coordinator.config)
            return bool(entity_id and self.hass.states.get(entity_id))
        if mode == CAMERA_MODE_EXTERNAL_URL:
            return bool(external_camera_url(self.coordinator.config))
        return False

    @property
    def is_streaming(self) -> bool:
        mode = self.coordinator.camera_status().get("camera_mode")
        if mode == CAMERA_MODE_CHAMBER_IMAGE_6000:
            client = self.coordinator.camera_client
            return bool(client and client.connected)
        return self.available

    @property
    def extra_state_attributes(self):
        status = dict(self.coordinator.camera_status())
        mode = status.get("camera_mode")
        if mode == CAMERA_MODE_RTSPS_322:
            status.update(
                {
                    "rtsp_transport": "rtsps",
                    "rtsp_port": 322,
                    "rtsp_path": "/streaming/live/1",
                    "requires_lan_liveview": True,
                    "credential_user": "bblp",
                }
            )
        elif mode == CAMERA_MODE_CHAMBER_IMAGE_6000 and self.coordinator.camera_client is not None:
            runtime = self.coordinator.camera_client.runtime_status()
            status.update(
                {
                    "native_transport": "tls-jpeg",
                    "native_host": runtime.host,
                    "native_port": runtime.port,
                    "native_connected": runtime.connected,
                    "native_frames_received": runtime.frames_received,
                    "native_sequence": runtime.sequence,
                    "native_last_frame_at": runtime.last_frame_at,
                    "native_last_error": runtime.last_error,
                }
            )
        elif mode == CAMERA_MODE_EXTERNAL_ENTITY:
            status["external_camera_entity"] = external_camera_entity(self.coordinator.config)
        elif mode == CAMERA_MODE_EXTERNAL_URL:
            status["external_url_configured"] = bool(external_camera_url(self.coordinator.config))
        return status

    async def async_added_to_hass(self) -> None:
        """Forward coordinator changes into the HA state machine."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def stream_source(self) -> str | None:
        """Return a stream URL for RTSPS/external camera modes."""
        mode = self.coordinator.camera_status().get("camera_mode")
        if mode == CAMERA_MODE_RTSPS_322:
            return rtsps_url(
                self.coordinator.camera_host,
                str(self.coordinator.config.get(CONF_ACCESS_CODE, "")),
            )
        if mode == CAMERA_MODE_EXTERNAL_URL:
            return external_camera_url(self.coordinator.config) or None
        if mode == CAMERA_MODE_EXTERNAL_ENTITY:
            entity_id = external_camera_entity(self.coordinator.config)
            state = self.hass.states.get(entity_id) if entity_id else None
            access_token = (state.attributes or {}).get("access_token") if state else None
            if entity_id and access_token:
                return f"/api/camera_proxy_stream/{entity_id}?token={access_token}"
        return None

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return the most recent native JPEG frame for TCP-6000 cameras."""
        mode = self.coordinator.camera_status().get("camera_mode")
        if mode != CAMERA_MODE_CHAMBER_IMAGE_6000:
            return None

        client = self.coordinator.camera_client
        if client is None:
            return None

        frame = client.latest_frame
        if frame is not None:
            return frame

        frame, _sequence = await self.hass.async_add_executor_job(
            client.wait_for_frame,
            None,
            8.0,
        )
        return frame