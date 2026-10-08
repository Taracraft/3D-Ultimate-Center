"""Authenticated Studio model inspection and plate preview endpoints."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath
import zipfile

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .gallery_management_views_v2 import gallery_repository
from .request_body import RequestBodyTooLarge, async_read_limited_body
from .slicer_native_contract import (
    MAX_MODEL_BYTES,
    SlicerServerConfigurationError,
    SlicerServerError,
)
from .three_mf_inspector_compat import inspect_model

API_PREFIX = "/api/ultimate_3d_studio/v1/slicer"
_ALLOWED_SUFFIXES = {".stl", ".3mf"}
_PREVIEW_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _safe_filename(value: str, fallback: str = "scene.3mf") -> str:
    raw = Path(value or fallback).name.strip()
    cleaned = "".join(
        character if character.isalnum() or character in "-_. " else "_"
        for character in raw
    ).strip(" .")
    return (cleaned or fallback)[:180]


async def _read_model(request: web.Request) -> tuple[str, bytes] | web.Response:
    gallery_asset_id = request.query.get("gallery_asset_id", "").strip()
    if gallery_asset_id:
        hass: HomeAssistant = request.app["hass"]
        try:
            model, source_filename = await hass.async_add_executor_job(
                gallery_repository(hass).download,
                gallery_asset_id,
            )
        except FileNotFoundError:
            return web.json_response({"error": "gallery model was not found"}, status=404)
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        filename = _safe_filename(source_filename)
        if Path(filename).suffix.casefold() not in _ALLOWED_SUFFIXES:
            return web.json_response({"error": "only STL or 3MF models are supported"}, status=400)
        if len(model) > MAX_MODEL_BYTES:
            return web.json_response({"error": "model exceeds 300 MB"}, status=413)
        if not model:
            return web.json_response({"error": "gallery model is empty"}, status=400)
        return filename, model

    filename = _safe_filename(request.query.get("filename", "scene.3mf"))
    if Path(filename).suffix.casefold() not in _ALLOWED_SUFFIXES:
        return web.json_response({"error": "only STL or 3MF models are supported"}, status=400)
    try:
        model = await async_read_limited_body(request, MAX_MODEL_BYTES)
    except RequestBodyTooLarge:
        return web.json_response({"error": "model exceeds 300 MB"}, status=413)
    if not model:
        return web.json_response({"error": "model body is empty"}, status=400)
    return filename, model


def _server_error(exc: Exception) -> web.Response:
    status = 503 if isinstance(exc, SlicerServerConfigurationError) else 502
    return web.json_response({"error": str(exc)}, status=status)


def _preview_content_type(filename: str) -> str:
    suffix = PurePosixPath(filename).suffix.casefold()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")


def _read_plate_preview(model: bytes, plate_index: int) -> tuple[bytes, str, str] | None:
    try:
        with zipfile.ZipFile(BytesIO(model)) as archive:
            inspection = inspect_model("scene.3mf", model)
            plate = next(
                (
                    item
                    for item in inspection.get("plates", [])
                    if isinstance(item, dict) and int(item.get("plate_index", -1)) == plate_index
                ),
                None,
            )
            preferred = str(plate.get("thumbnail_path") or "") if plate else ""
            candidates: list[str] = []
            if preferred:
                candidates.append(preferred)
            number = plate_index + 1
            for info in archive.infolist():
                path = PurePosixPath(info.filename)
                lowered = info.filename.casefold()
                if path.suffix.casefold() not in _PREVIEW_SUFFIXES:
                    continue
                if f"plate_{number}" in lowered or f"plate-{number}" in lowered:
                    candidates.append(info.filename)
            for filename in dict.fromkeys(candidates):
                try:
                    data = archive.read(filename)
                except KeyError:
                    continue
                if data:
                    return data, _preview_content_type(filename), PurePosixPath(filename).name
    except (ValueError, OSError, zipfile.BadZipFile):
        return None
    return None


class SlicerModelInspectView(HomeAssistantView):
    """Inspect one uploaded STL/3MF without storing it."""

    url = f"{API_PREFIX}/inspect"
    name = "api:ultimate_3d_studio:slicer_model_inspect"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        loaded = await _read_model(request)
        if isinstance(loaded, web.Response):
            return loaded
        filename, model = loaded
        try:
            inspection = await request.app["hass"].async_add_executor_job(
                inspect_model,
                filename,
                model,
            )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response({"data": {"filename": filename, **inspection}})


class SlicerModelPreviewView(HomeAssistantView):
    """Return an embedded thumbnail for one uploaded 3MF plate."""

    url = f"{API_PREFIX}/preview"
    name = "api:ultimate_3d_studio:slicer_model_preview"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        loaded = await _read_model(request)
        if isinstance(loaded, web.Response):
            return loaded
        filename, model = loaded
        if not filename.casefold().endswith(".3mf"):
            return web.json_response({"error": "preview is only available for 3MF models"}, status=404)
        try:
            plate_index = int(request.query.get("plate_index", "0"))
        except ValueError:
            return web.json_response({"error": "plate_index must be numeric"}, status=400)
        if plate_index < 0 or plate_index > 255:
            return web.json_response({"error": "plate_index is out of range"}, status=400)
        preview = await request.app["hass"].async_add_executor_job(
            _read_plate_preview,
            model,
            plate_index,
        )
        if preview is None:
            return web.json_response({"error": "plate preview not found"}, status=404)
        data, content_type, preview_name = preview
        return web.Response(
            body=data,
            content_type=content_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": f'inline; filename="{preview_name}"',
            },
        )


def async_register_slicer_plate_views(hass: HomeAssistant) -> None:
    """Register model inspection and preview routes."""
    for view in (SlicerModelInspectView(), SlicerModelPreviewView()):
        hass.http.register_view(view)
