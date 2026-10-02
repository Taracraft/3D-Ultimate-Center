"""Home Assistant HTTP adapters for persistent slicing jobs."""

from __future__ import annotations

from dataclasses import asdict

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .slicing_application import V1SlicingApplication


def _json_response(response) -> web.Response:
    status = 200
    if response.error is not None:
        status = {
            "not_found": 404,
            "validation_failed": 400,
            "internal_error": 500,
        }.get(response.error.code, 500)
    return web.json_response(asdict(response), status=status)


class _SlicingView(HomeAssistantView):
    requires_auth = True

    def __init__(self, hass: HomeAssistant, application: V1SlicingApplication) -> None:
        self._hass = hass
        self._application = application


class V1SliceJobsView(_SlicingView):
    url = "/api/printer_control_center/v1/slicing/jobs"
    name = "api:printer_control_center:v1:slice_jobs"

    async def post(self, request: web.Request) -> web.Response:
        payload = await request.json()
        response = await self._hass.async_add_executor_job(
            self._application.create_job,
            payload,
        )
        return _json_response(response)


class V1SliceJobView(_SlicingView):
    url = "/api/printer_control_center/v1/slicing/jobs/{job_id}"
    name = "api:printer_control_center:v1:slice_job"

    async def get(self, request: web.Request, job_id: str) -> web.Response:
        response = await self._hass.async_add_executor_job(
            self._application.get_job,
            job_id,
        )
        return _json_response(response)


class V1SliceJobRunView(_SlicingView):
    url = "/api/printer_control_center/v1/slicing/jobs/{job_id}/run"
    name = "api:printer_control_center:v1:slice_job_run"

    async def post(self, request: web.Request, job_id: str) -> web.Response:
        response = await self._application.run_job(job_id)
        return _json_response(response)


class V1SliceJobCancelView(_SlicingView):
    url = "/api/printer_control_center/v1/slicing/jobs/{job_id}/cancel"
    name = "api:printer_control_center:v1:slice_job_cancel"

    async def post(self, request: web.Request, job_id: str) -> web.Response:
        response = await self._application.cancel_job(job_id)
        return _json_response(response)


def register_v1_slicing_views(
    hass: HomeAssistant,
    application: V1SlicingApplication,
) -> None:
    for view_type in (
        V1SliceJobsView,
        V1SliceJobView,
        V1SliceJobRunView,
        V1SliceJobCancelView,
    ):
        hass.http.register_view(view_type(hass, application))
