"""Authenticated HTTP endpoints for SD card templates."""
from __future__ import annotations

from functools import partial
import base64
import hashlib
import hmac
import logging
import re
from pathlib import Path, PurePosixPath
import secrets
import time
from urllib.parse import quote

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_CODE, DOMAIN
from .coordinator import PrinterControlCenterCoordinator
from .template_browser import SdTemplateBrowser
from .archive_browser import LocalArchiveRepository
from .model_export import export_binary_stl, export_geometry_only_3mf

_LOGGER = logging.getLogger(__name__)

_DATA_HTTP_REGISTERED = "_http_registered"
_DATA_BROWSERS = "_template_browsers"
_DATA_ARCHIVE = "_local_archive"
_DATA_SIGNING_SECRET = "_download_signing_secret"


_SLICER_UNSAFE_FILENAME = re.compile(r"[/\\?#]")


def _slicer_filename(filename: str, *, suffix: str = ".3mf") -> str:
    """Build a URL-safe slicer filename whose path visibly ends in suffix."""
    safe = _SLICER_UNSAFE_FILENAME.sub("_", str(filename or "model"))
    if not safe.lower().endswith(suffix.lower()):
        safe = f"{safe.rsplit('.', 1)[0] if '.' in safe else safe}{suffix}"
    return safe


def _path_token(path: str) -> str:
    """Encode the original archive path as one URL-safe route segment."""
    return base64.urlsafe_b64encode(str(path).encode("utf-8")).decode("ascii").rstrip("=")


def _path_from_token(token: str) -> str:
    """Decode an original archive path from one URL-safe route segment."""
    try:
        padding = "=" * (-len(token) % 4)
        return base64.urlsafe_b64decode(f"{token}{padding}".encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise web.HTTPForbidden(text="Invalid signed path") from exc


def _find_coordinator(hass: HomeAssistant, serial: str) -> PrinterControlCenterCoordinator:
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, PrinterControlCenterCoordinator) and value.serial == serial:
            return value
    raise web.HTTPNotFound(text="Unknown printer")


def _browser(hass: HomeAssistant, coordinator: PrinterControlCenterCoordinator) -> SdTemplateBrowser:
    browsers = hass.data.setdefault(DOMAIN, {}).setdefault(_DATA_BROWSERS, {})
    endpoint_host = coordinator.manual_host or coordinator.active_host
    key = (coordinator.serial, endpoint_host, str(coordinator.config.get(CONF_ACCESS_CODE, "")))

    browser = browsers.get(key)
    if browser is None:
        browser = SdTemplateBrowser(
            host=endpoint_host,
            access_code=str(coordinator.config[CONF_ACCESS_CODE]),
        )
        browsers.clear()
        browsers[key] = browser

    return browser


def _archive(hass: HomeAssistant) -> LocalArchiveRepository:
    domain_data = hass.data.setdefault(DOMAIN, {})
    repository = domain_data.get(_DATA_ARCHIVE)
    if repository is None:
        repository = LocalArchiveRepository(Path(hass.config.path(DOMAIN, "archive")))
        domain_data[_DATA_ARCHIVE] = repository
    return repository


def _signing_secret(hass: HomeAssistant) -> bytes:
    domain_data = hass.data.setdefault(DOMAIN, {})
    secret = domain_data.get(_DATA_SIGNING_SECRET)
    if secret is None:
        secret = secrets.token_bytes(32)
        domain_data[_DATA_SIGNING_SECRET] = secret
    return secret


def _signature(hass: HomeAssistant, serial: str, source: str, path: str, expires: int) -> str:
    value = f"{serial}\n{source}\n{path}\n{expires}".encode("utf-8")
    return hmac.new(_signing_secret(hass), value, hashlib.sha256).hexdigest()


def _validate_upload_body(body: dict) -> tuple[str, bytes]:
    filename = str(body.get("filename", "")).strip()
    content_base64 = str(body.get("content_base64", "")).strip()
    if not filename or not content_base64:
        raise web.HTTPBadRequest(text="filename and content_base64 are required")
    try:
        payload = base64.b64decode(content_base64, validate=True)
    except Exception as exc:
        raise web.HTTPBadRequest(text="Invalid base64 upload") from exc
    return filename, payload


class PrinterControlCenterTemplateListView(HomeAssistantView):
    url = "/api/printer_control_center/templates/{serial}"
    name = "api:printer_control_center:templates"
    requires_auth = True

    async def get(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        coordinator = _find_coordinator(hass, serial)
        force = request.query.get("force", "0") in {"1", "true", "yes"}

        try:
            items = await hass.async_add_executor_job(
                partial(_browser(hass, coordinator).list_templates, force)
            )
        except Exception as exc:
            _LOGGER.exception("Unable to list SD-card templates for %s", serial)
            return self.json(
                {
                    "serial": serial,
                    "host": coordinator.active_host,
                    "items": [],
                    "error": str(exc),
                },
                status_code=502,
            )

        return self.json(
            {
                "serial": serial,
                "host": coordinator.active_host,
                "items": items,
                "error": "",
            }
        )

    async def post(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        coordinator = _find_coordinator(hass, serial)
        body = await request.json()
        filename, payload = _validate_upload_body(body)
        folder = str(body.get("folder", "/") or "/")
        try:
            item = await hass.async_add_executor_job(
                _browser(hass, coordinator).upload,
                filename,
                payload,
                folder,
            )
        except Exception as exc:
            _LOGGER.exception("Unable to upload SD-card template %s", filename)
            raise web.HTTPBadGateway(text=str(exc)) from exc
        return self.json({"item": item, "error": ""})


class PrinterControlCenterTemplateDownloadView(HomeAssistantView):
    url = "/api/printer_control_center/download/{serial}"
    name = "api:printer_control_center:download"
    requires_auth = True

    async def get(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        coordinator = _find_coordinator(hass, serial)
        path = request.query.get("path", "")

        if not path:
            raise web.HTTPBadRequest(text="Missing SD-card path")

        try:
            payload = await hass.async_add_executor_job(
                _browser(hass, coordinator).download,
                path,
            )
        except Exception as exc:
            _LOGGER.exception("Unable to download SD-card template %s", path)
            raise web.HTTPBadGateway(text=str(exc)) from exc

        filename = PurePosixPath(path).name or "project.3mf"
        return web.Response(
            body=payload,
            content_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )



class PrinterControlCenterArchiveView(HomeAssistantView):
    url = "/api/printer_control_center/archive/{serial}"
    name = "api:printer_control_center:archive"
    requires_auth = True

    async def get(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        _find_coordinator(hass, serial)
        items = await hass.async_add_executor_job(_archive(hass).list_items)
        return self.json({"serial": serial, "items": items, "error": ""})

    async def post(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        _find_coordinator(hass, serial)
        body = await request.json()
        filename, payload = _validate_upload_body(body)
        item = await hass.async_add_executor_job(_archive(hass).upload, filename, payload)
        return self.json({"item": item, "error": ""})


class PrinterControlCenterArchiveExportView(HomeAssistantView):
    """Download a complete gallery ZIP backup including subfolders."""

    url = "/api/printer_control_center/archive_export/{serial}"
    name = "api:printer_control_center:archive_export"
    requires_auth = True

    async def get(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        _find_coordinator(hass, serial)
        payload = await hass.async_add_executor_job(_archive(hass).export_zip)
        filename = f"3d-printer-control-center-gallery-{int(time.time())}.zip"
        return web.Response(
            body=payload,
            content_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )


class PrinterControlCenterArchiveDownloadView(HomeAssistantView):
    url = "/api/printer_control_center/archive_download/{serial}"
    name = "api:printer_control_center:archive_download"
    requires_auth = True

    async def get(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        _find_coordinator(hass, serial)
        path = request.query.get("path", "")
        payload = await hass.async_add_executor_job(_archive(hass).download, path)
        return web.Response(
            body=payload,
            content_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{PurePosixPath(path).name}"',
                "Cache-Control": "no-store",
            },
        )


class PrinterControlCenterStudioLinkView(HomeAssistantView):
    url = "/api/printer_control_center/studio_link/{serial}"
    name = "api:printer_control_center:studio_link"
    requires_auth = True

    async def post(self, request: web.Request, serial: str):
        hass: HomeAssistant = request.app["hass"]
        _find_coordinator(hass, serial)
        body = await request.json()
        source = str(body.get("source", "")).strip()
        path = str(body.get("path", "")).strip()
        if source not in {"archive", "sd"} or not path:
            raise web.HTTPBadRequest(text="source must be archive or sd and path is required")
        export_format = str(body.get("format", "3mf")).strip().lower()
        if export_format not in {"3mf", "stl"}:
            raise web.HTTPBadRequest(text="format must be 3mf or stl")
        source_suffix = "model_3mf" if export_format == "3mf" else "model_stl"
        model_source = f"{source}_{source_suffix}"
        expires = int(time.time()) + 300
        token = _signature(hass, serial, model_source, path, expires)
        original_name = PurePosixPath(path).name or "model.3mf"
        filename = (
            _slicer_filename(original_name, suffix=".3mf")
            if export_format == "3mf"
            else _slicer_filename(original_name, suffix=".stl")
        )
        relative = (
            f"/api/printer_control_center/public_download/"
            f"{quote(serial, safe='')}/{quote(model_source, safe='')}/{expires}/{token}/"
            f"{quote(_path_token(path), safe='')}/{quote(filename, safe='')}"
        )
        absolute = f"{request.scheme}://{request.host}{relative}"
        return self.json(
            {
                "download_url": relative,
                "absolute_download_url": absolute,
                "bambustudio_url": f"bambustudio://open?file={quote(absolute, safe='')}",
                "mode": f"model_only_{export_format}",
                "expires": expires,
            }
        )


class PrinterControlCenterSignedDownloadView(HomeAssistantView):
    # Keep every parameter before filename: Bambu Studio expects the complete URI
    # supplied through bambustudio://open?file=... to end visibly in .3mf.
    url = "/api/printer_control_center/public_download/{serial}/{source}/{expires}/{token}/{path_token}/{filename}"
    name = "api:printer_control_center:public_download"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        serial: str,
        source: str,
        expires: str,
        token: str,
        path_token: str,
        filename: str,
    ):
        hass: HomeAssistant = request.app["hass"]
        coordinator = _find_coordinator(hass, serial)
        path = _path_from_token(path_token)
        original_filename = PurePosixPath(path).name or "project.3mf"
        model_only_3mf = source in {"archive_model_3mf", "sd_model_3mf"}
        model_only_stl = source in {"archive_model_stl", "sd_model_stl", "archive_model", "sd_model"}
        model_only = model_only_3mf or model_only_stl
        if model_only_3mf:
            base_source = source.removesuffix("_model_3mf")
            actual_filename = _slicer_filename(original_filename, suffix=".3mf")
        elif model_only_stl:
            base_source = source.removesuffix("_model_stl").removesuffix("_model")
            actual_filename = _slicer_filename(original_filename, suffix=".stl")
        else:
            base_source = source
            actual_filename = _slicer_filename(original_filename, suffix=".3mf")

        if filename != actual_filename:
            raise web.HTTPForbidden(text="Signed filename mismatch")
        try:
            expires = int(expires)
        except ValueError as exc:
            raise web.HTTPForbidden(text="Invalid expiry") from exc
        if expires < int(time.time()) or expires > int(time.time()) + 360:
            raise web.HTTPForbidden(text="Expired signed URL")
        expected = _signature(hass, serial, source, path, expires)
        if not hmac.compare_digest(token, expected):
            raise web.HTTPForbidden(text="Invalid signature")

        if base_source == "archive":
            payload = await hass.async_add_executor_job(_archive(hass).download, path)
        elif base_source == "sd":
            payload = await hass.async_add_executor_job(_browser(hass, coordinator).download, path)
        else:
            raise web.HTTPBadRequest(text="Unknown source")

        if model_only_3mf:
            payload = await hass.async_add_executor_job(
                partial(
                    export_geometry_only_3mf,
                    payload,
                    label=f"3D-Printer Control Center {PurePosixPath(original_filename).stem}",
                )
            )
        elif model_only_stl:
            payload = await hass.async_add_executor_job(
                partial(
                    export_binary_stl,
                    payload,
                    label=f"3D-Printer Control Center {PurePosixPath(original_filename).stem}",
                )
            )

        return web.Response(
            body=payload,
            content_type=(
                "model/stl"
                if model_only_stl
                else (
                    "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"
                    if model_only_3mf
                    else "application/octet-stream"
                )
            ),
            headers={
                "Content-Disposition": f'attachment; filename="{actual_filename}"',
                "Cache-Control": "no-store",
            },
        )


async def async_register_http_views(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_DATA_HTTP_REGISTERED):
        return

    hass.http.register_view(PrinterControlCenterTemplateListView())
    hass.http.register_view(PrinterControlCenterTemplateDownloadView())
    hass.http.register_view(PrinterControlCenterArchiveView())
    hass.http.register_view(PrinterControlCenterArchiveDownloadView())
    hass.http.register_view(PrinterControlCenterArchiveExportView())
    hass.http.register_view(PrinterControlCenterStudioLinkView())
    hass.http.register_view(PrinterControlCenterSignedDownloadView())
    domain_data[_DATA_HTTP_REGISTERED] = True