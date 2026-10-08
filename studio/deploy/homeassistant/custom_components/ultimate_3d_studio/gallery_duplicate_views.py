"""Authenticated, on-demand and read-only gallery duplicate inspection."""
from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path
import threading

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import API_BASE, DOMAIN
from .gallery_duplicate_scan import DuplicateScanError, scan_gallery_duplicates
from .gallery_management_views_v2 import _DATA_REPOSITORY, _error, _success

_DATA_SCAN = "gallery_duplicate_scan_task"
_DATA_VIEWS = "gallery_duplicate_scan_registered"
_MESSAGES = {
    "invalid_folder": "Ungültiger Galerieordner.",
    "unsafe_folder": "Verknüpfte Ordner werden nicht durchsucht.",
    "folder_not_found": "Der Galerieordner wurde nicht gefunden.",
    "library_changed": "Die Galerie wurde während der Prüfung verändert. Bitte erneut prüfen.",
    "scan_entry_limit": "Zu viele Einträge. Bitte einen kleineren Unterordner auswählen.",
    "scan_byte_limit": "Die Vergleichsdaten überschreiten 2 GiB. Bitte einen kleineren Unterordner auswählen.",
    "scan_depth_limit": "Die zulässige Ordnertiefe wurde überschritten.",
    "scan_time_limit": "Die Prüfzeit wurde überschritten. Bitte einen kleineren Unterordner auswählen.",
    "scan_cancelled": "Die Duplikatprüfung wurde abgebrochen.",
    "scan_io_error": "Nicht alle Modelldateien konnten sicher gelesen werden.",
}


def _gallery_root(hass):
    # Do not instantiate the repository just to inspect it: its constructor
    # creates directories. Respect its existing root, or use the same configured
    # archive path without mkdir; a missing library must remain a read failure.
    repository = hass.data.get(DOMAIN, {}).get(_DATA_REPOSITORY)
    if repository is not None:
        return Path(repository.root)
    return Path(hass.config.path("printer_control_center", "archive"))


def _consume_task(data, task):
    # Cancellation of an HTTP request must not release the single-flight guard
    # while its executor thread is still using disk resources.
    if data.get(_DATA_SCAN) is task:
        data.pop(_DATA_SCAN, None)
    if not task.cancelled():
        task.exception()


class GalleryDuplicatesView(HomeAssistantView):
    url = f"{API_BASE}/gallery/duplicates"
    name = f"api:{DOMAIN}:gallery:duplicates"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app["hass"]
        data = hass.data.setdefault(DOMAIN, {})
        previous = data.get(_DATA_SCAN)
        if previous is not None and not previous.done():
            response = _error(409, "gallery_duplicate_scan_busy", "Eine Duplikatprüfung läuft bereits.")
            response.headers["Cache-Control"] = "no-store"
            return response
        cancel = threading.Event()
        # No await between checking and publishing the task: these operations
        # run on the same event loop, so two requests cannot start two scanners.
        task = asyncio.ensure_future(hass.async_add_executor_job(partial(
            scan_gallery_duplicates, _gallery_root(hass),
            request.query.get("folder", ""), cancel=cancel,
        )))
        data[_DATA_SCAN] = task
        task.add_done_callback(partial(_consume_task, data))
        try:
            result = await asyncio.shield(task)
        except asyncio.CancelledError:
            cancel.set()
            raise
        except DuplicateScanError as exc:
            code = str(exc)
            status = (404 if code == "folder_not_found" else 409 if code == "library_changed"
                      else 400 if code in {"invalid_folder", "unsafe_folder"} else 422)
            response = _error(status, code, _MESSAGES.get(code, "Die Duplikatprüfung konnte nicht abgeschlossen werden."))
        except Exception:
            response = _error(500, "gallery_duplicate_scan_failed", "Die Duplikatprüfung ist fehlgeschlagen.")
        else:
            response = _success(result, count=result["duplicate_groups"])
        response.headers["Cache-Control"] = "no-store"
        return response


def async_register_gallery_duplicate_views(hass) -> None:
    data = hass.data.setdefault(DOMAIN, {})
    if not data.get(_DATA_VIEWS):
        hass.http.register_view(GalleryDuplicatesView())
        data[_DATA_VIEWS] = True
