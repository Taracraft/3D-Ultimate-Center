"""Shared limits and errors for the native Linux slicing server."""
from __future__ import annotations

import re

SLICER_API_PROTOCOL = 2
SLICER_CANCELLATION_CONTRACT = 1
_SERVER_VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,59}\Z")

MAX_MODEL_BYTES = 300_000_000


class SlicerServerError(RuntimeError):
    """Base error raised by the native slicing server integration."""


class SlicerServerConfigurationError(SlicerServerError):
    """The native slicing server or requested profile is unavailable."""

class SlicerServerCompatibilityError(SlicerServerError):
    """The server metadata does not match the supported protocol."""


class SlicerServerAuthenticationError(SlicerServerError):
    """The server rejected authentication."""


def validate_slicer_server_info(info: object) -> dict:
    """Validate readiness metadata without trusting remote transport flags."""
    if not isinstance(info, dict):
        raise SlicerServerCompatibilityError("Invalid slicing server metadata.")
    version = info.get("version")
    if not isinstance(version, str) or not _SERVER_VERSION_PATTERN.fullmatch(version):
        raise SlicerServerCompatibilityError("Invalid slicing server version.")
    protocol = info.get("api_version")
    if type(protocol) is not int or protocol != SLICER_API_PROTOCOL:
        raise SlicerServerCompatibilityError("Unsupported slicing server protocol.")
    if not isinstance(info.get("capabilities"), dict):
        raise SlicerServerCompatibilityError("Invalid slicing server capabilities.")
    status = info.get("status")
    if not isinstance(status, str) or status not in {"ready", "starting", "degraded"}:
        raise SlicerServerCompatibilityError("Invalid slicing server readiness status.")
    return dict(info)
