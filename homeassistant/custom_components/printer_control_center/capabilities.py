"""Printer model and camera capability helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    CAMERA_MODE_AUTO,
    CAMERA_MODE_CHAMBER_IMAGE_6000,
    CAMERA_MODE_DISABLED,
    CAMERA_MODE_EXTERNAL_ENTITY,
    CAMERA_MODE_EXTERNAL_URL,
    CAMERA_MODE_RTSPS_322,
    CONF_CAMERA_ENTITY,
    CONF_CAMERA_MODE,
    CONF_CAMERA_URL,
)


@dataclass(frozen=True)
class CameraCapability:
    transport: str
    port: int | None
    label: str
    requires_lan_liveview: bool = False
    requires_camera_enabled: bool = False
    supports_native_snapshot: bool = False
    supports_stream_source: bool = False


def _token(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def camera_transport_for_model(model: Any) -> str:
    token = _token(model)
    if not token or token in {"bambulab3dprinter", "3dprinter"}:
        return CAMERA_MODE_AUTO

    # X/H/P2 class: Bambu exposes a RTSPS stream on TCP 322.
    if any(part in token for part in ("x1carbon", "x1c", "x1e", "x1", "h2d", "h2s", "h2", "p2s", "p2", "x2d", "x2")):
        return CAMERA_MODE_RTSPS_322

    # A/P1/A2 class: Chamber Image / TLS JPEG on TCP 6000.
    if any(part in token for part in ("a1mini", "a1", "a2l", "a2", "p1p", "p1s", "p1")):
        return CAMERA_MODE_CHAMBER_IMAGE_6000

    return CAMERA_MODE_AUTO


def configured_camera_mode(config: dict[str, Any]) -> str:
    mode = str(config.get(CONF_CAMERA_MODE, CAMERA_MODE_AUTO) or CAMERA_MODE_AUTO)
    allowed = {
        CAMERA_MODE_AUTO,
        CAMERA_MODE_DISABLED,
        CAMERA_MODE_CHAMBER_IMAGE_6000,
        CAMERA_MODE_RTSPS_322,
        CAMERA_MODE_EXTERNAL_ENTITY,
        CAMERA_MODE_EXTERNAL_URL,
    }
    return mode if mode in allowed else CAMERA_MODE_AUTO


def effective_camera_mode(config: dict[str, Any], model: Any) -> str:
    configured = configured_camera_mode(config)
    if configured != CAMERA_MODE_AUTO:
        return configured
    detected = camera_transport_for_model(model)
    if detected != CAMERA_MODE_AUTO:
        return detected
    return CAMERA_MODE_DISABLED


def camera_capability(mode: str) -> CameraCapability:
    if mode == CAMERA_MODE_CHAMBER_IMAGE_6000:
        return CameraCapability(
            transport=mode,
            port=6000,
            label="Chamber Image / TCP 6000",
            requires_camera_enabled=True,
            supports_native_snapshot=True,
        )
    if mode == CAMERA_MODE_RTSPS_322:
        return CameraCapability(
            transport=mode,
            port=322,
            label="RTSPS / TCP 322",
            requires_lan_liveview=True,
            supports_stream_source=True,
        )
    if mode == CAMERA_MODE_EXTERNAL_ENTITY:
        return CameraCapability(mode, None, "External HA camera entity", supports_stream_source=True)
    if mode == CAMERA_MODE_EXTERNAL_URL:
        return CameraCapability(mode, None, "External MJPEG/proxy URL", supports_stream_source=True)
    return CameraCapability(CAMERA_MODE_DISABLED, None, "Disabled")


def rtsps_url(host: str, access_code: str) -> str:
    host = str(host or "").strip()
    code = str(access_code or "").strip()
    if not host or not code:
        return ""
    return f"rtsps://bblp:{code}@{host}:322/streaming/live/1"


def external_camera_entity(config: dict[str, Any]) -> str:
    return str(config.get(CONF_CAMERA_ENTITY, "") or "").strip()


def external_camera_url(config: dict[str, Any]) -> str:
    return str(config.get(CONF_CAMERA_URL, "") or "").strip()