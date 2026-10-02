from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SlicingServerApi, SlicingServerApiError

_LOGGER = logging.getLogger(__name__)


class SlicingServerCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass, api: SlicingServerApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="3D-Printer Slicing Server",
            update_interval=timedelta(seconds=15),
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            return {
                "info": await self.api.info(),
                "status": await self.api.status(),
                "diagnostics": await self.api.diagnostics(),
            }
        except SlicingServerApiError as exc:
            raise UpdateFailed(str(exc)) from exc