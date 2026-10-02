"""Home Assistant HTTP adapters for the V6 application facade."""

from __future__ import annotations

from dataclasses import asdict

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from core.post_upload_pipeline import PostUploadPipeline

from .application import V1Application


def _json_response(response) -> web.Response:
    status = 200
    if response.error is not None:
        status = {
            "not_found": 404,
            "validation_failed": 400,
            "internal_error": 500,
        }.get(response.error.code, 500)
    return web.json_response(asdict(response), status=status)


class _V1View(HomeAssistantView):
    requires_auth = True

    def __init__(
        self,
        hass: HomeAssistant,
        application: V1Application,
        post_upload_pipeline: PostUploadPipeline | None = None,
    ) -> None:
        self._hass = hass
        self._application = application
        self._post_upload_pipeline = post_upload_pipeline

    async def _run(self, function, *args):
        return await self._hass.async_add_executor_job(function, *args)


class V1UploadsView(_V1View):
    url = "/api/printer_control_center/v1/assets/uploads"
    name = "api:printer_control_center:v1:uploads"

    async def post(self, request: web.Request) -> web.Response:
        payload = await request.json()
        response = await self._run(self._application.create_upload, payload)
        return _json_response(response)


class V1UploadChunkView(_V1View):
    url = "/api/printer_control_center/v1/assets/uploads/{upload_id}/chunks"
    name = "api:printer_control_center:v1:upload_chunk"

    async def post(self, request: web.Request, upload_id: str) -> web.Response:
        try:
            offset = int(request.query.get("offset", "0"))
        except ValueError:
            return web.json_response(
                {
                    "data": None,
                    "error": {
                        "code": "validation_failed",
                        "message": "offset must be an integer",
                    },
                    "version": "v1",
                },
                status=400,
            )
        chunk = await request.read()
        response = await self._run(
            self._application.write_upload_chunk,
            upload_id,
            offset,
            chunk,
        )
        return _json_response(response)


class V1UploadCompleteView(_V1View):
    url = "/api/printer_control_center/v1/assets/uploads/{upload_id}/complete"
    name = "api:printer_control_center:v1:upload_complete"

    async def post(self, request: web.Request, upload_id: str) -> web.Response:
        response = await self._run(self._application.finalize_upload, upload_id)
        if response.error is None and self._post_upload_pipeline is not None:
            asset_id = response.data["asset"]["id"]
            await self._post_upload_pipeline.schedule(asset_id)
        return _json_response(response)


class V1ProjectsView(_V1View):
    url = "/api/printer_control_center/v1/projects"
    name = "api:printer_control_center:v1:projects"

    async def post(self, request: web.Request) -> web.Response:
        payload = await request.json()
        response = await self._run(self._application.create_project, payload)
        return _json_response(response)


class V1ProjectView(_V1View):
    url = "/api/printer_control_center/v1/projects/{project_id}"
    name = "api:printer_control_center:v1:project"

    async def get(self, request: web.Request, project_id: str) -> web.Response:
        response = await self._run(self._application.get_project, project_id)
        return _json_response(response)


class V1ProjectCommandView(_V1View):
    url = "/api/printer_control_center/v1/projects/{project_id}/commands"
    name = "api:printer_control_center:v1:project_commands"

    async def post(self, request: web.Request, project_id: str) -> web.Response:
        payload = await request.json()
        response = await self._run(
            self._application.execute_scene_command,
            project_id,
            payload,
        )
        return _json_response(response)


class V1ProjectUndoView(_V1View):
    url = "/api/printer_control_center/v1/projects/{project_id}/undo"
    name = "api:printer_control_center:v1:project_undo"

    async def post(self, request: web.Request, project_id: str) -> web.Response:
        response = await self._run(self._application.undo_project, project_id)
        return _json_response(response)


class V1ProjectRedoView(_V1View):
    url = "/api/printer_control_center/v1/projects/{project_id}/redo"
    name = "api:printer_control_center:v1:project_redo"

    async def post(self, request: web.Request, project_id: str) -> web.Response:
        response = await self._run(self._application.redo_project, project_id)
        return _json_response(response)


def register_v1_views(
    hass: HomeAssistant,
    application: V1Application,
    post_upload_pipeline: PostUploadPipeline | None = None,
) -> None:
    for view_type in (
        V1UploadsView,
        V1UploadChunkView,
        V1UploadCompleteView,
        V1ProjectsView,
        V1ProjectView,
        V1ProjectCommandView,
        V1ProjectUndoView,
        V1ProjectRedoView,
    ):
        hass.http.register_view(
            view_type(hass, application, post_upload_pipeline)
        )
