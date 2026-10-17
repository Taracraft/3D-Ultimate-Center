"""List jobs from the fixed native Linux slicing server."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .slicer_backend_router import StudioSlicerBackendRouter


async def async_list_slicer_jobs(
    hass: HomeAssistant,
) -> list[dict[str, Any]]:
    return await StudioSlicerBackendRouter(hass).async_list_jobs()
