"""List jobs from the fixed native Linux slicing server."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .slicer_backend_router import V6SlicerBackendRouter


async def async_list_slicer_jobs(
    hass: HomeAssistant,
) -> list[dict[str, Any]]:
    return await V6SlicerBackendRouter(hass).async_list_jobs()
