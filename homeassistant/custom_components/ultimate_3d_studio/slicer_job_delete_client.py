"""Delete terminal jobs on the fixed native Linux slicing server."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .slicer_backend_router import StudioSlicerBackendRouter


async def async_delete_slicer_job(
    hass: HomeAssistant,
    job_id: str,
) -> dict[str, Any]:
    return await StudioSlicerBackendRouter(hass).async_delete_job(job_id)
