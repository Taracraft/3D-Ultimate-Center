"""Shared limits and errors for the native Linux slicing server."""
from __future__ import annotations

MAX_MODEL_BYTES = 300_000_000


class SlicerServerError(RuntimeError):
    """Base error raised by the native slicing server integration."""


class SlicerServerConfigurationError(SlicerServerError):
    """The native slicing server or requested profile is unavailable."""
