"""Authenticated two-step direct-print endpoints for Ultimate 3D Studio V6."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .bambu_direct_print import (
    DirectPrintError,
    build_remote_3mf_filename,
)
from .const import DATA_RUNTIMES, DOMAIN
from .direct_print_material_plan import (
    AuthoritativeAmsStart,
    DirectPrintMaterialPlanError,
    derive_authoritative_ams_start,
)
from .direct_print_runtime import DirectPrintAuthorizationError, get_direct_print_runtime
from .runtime import Ultimate3DStudioRuntime
from .slicer_backend_router import V6SlicerBackendRouter
from .slicer_native_contract import (
    SlicerServerConfigurationError,
    SlicerServerError,
)

API_PREFIX = "/api/ultimate_3d_studio_v6/v1/slicer"
_SAFE_START_STATES = {
    "idle",
    "finish",
    "finished",
    "complete",
    "completed",
    "success",
    "ready",
    "standby",
    "failed",
}
_MAX_SNAPSHOT_AGE_SECONDS = 30.0
_MAX_SNAPSHOT_FUTURE_SECONDS = 5.0
_EMPTY_ERROR_CODES = {"", "0", "none", "null", "false"}
_BLOCKING_LEVELS = {"error", "fatal", "critical"}


def _error(
    status: int,
    code: str,
    message: str,
    **details: Any,
) -> web.Response:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return web.json_response({"data": None, "error": error}, status=status)


def _admin_error(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return _error(
            403,
            "admin_required",
            "Administrator access is required",
        )
    return None


async def _json_object(
    request: web.Request,
) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        payload = await request.json()
    except Exception:
        return None, _error(
            400,
            "invalid_json",
            "Request body must contain valid JSON",
        )
    if not isinstance(payload, dict):
        return None, _error(
            400,
            "invalid_json",
            "Request body must contain a JSON object",
        )
    return payload, None


def _runtimes(hass: HomeAssistant) -> list[Ultimate3DStudioRuntime]:
    domain_data = hass.data.get(DOMAIN, {})
    values = (
        domain_data.get(DATA_RUNTIMES, {})
        if isinstance(domain_data, dict)
        else {}
    )
    if not isinstance(values, dict):
        return []
    return [
        item
        for item in values.values()
        if isinstance(item, Ultimate3DStudioRuntime)
    ]


async def _find_runtime_and_printer(
    hass: HomeAssistant,
    printer_id: str,
) -> tuple[Ultimate3DStudioRuntime | None, Any | None]:
    for runtime in _runtimes(hass):
        printer = await runtime.async_printer(printer_id)
        if printer is not None:
            return runtime, printer
    return None, None


def _parse_snapshot_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _active_blocking_issue(printer: Any) -> dict[str, Any] | None:
    for collection_name in ("issues", "hms"):
        collection = getattr(printer, collection_name, None)
        if not isinstance(collection, list):
            continue
        for issue in collection:
            if not isinstance(issue, dict):
                continue
            active = issue.get("active", True) is not False
            level = str(
                issue.get("severity")
                or issue.get("level")
                or ""
            ).strip().casefold()
            blocking = (
                issue.get("blocking") is True
                or level in _BLOCKING_LEVELS
            )
            if active and blocking:
                return issue
    return None


def _printer_ready(
    printer: Any,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    if printer is None:
        return False, "Drucker wurde nicht gefunden."
    if str(printer.connection_state).casefold() != "connected":
        return False, "Drucker ist nicht verbunden."

    snapshot_time = _parse_snapshot_time(
        getattr(printer, "updated_at", None)
    )
    if snapshot_time is None:
        return (
            False,
            "Druckertelemetrie besitzt keinen gültigen Aktualisierungszeitpunkt.",
        )
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    age_seconds = (
        current_time.astimezone(timezone.utc) - snapshot_time
    ).total_seconds()
    if age_seconds > _MAX_SNAPSHOT_AGE_SECONDS:
        return (
            False,
            "Druckertelemetrie ist veraltet. Warte auf eine aktuelle "
            "Druckermeldung und versuche es erneut.",
        )
    if age_seconds < -_MAX_SNAPSHOT_FUTURE_SECONDS:
        return (
            False,
            "Druckertelemetrie besitzt einen unplausiblen Zeitstempel.",
        )

    blocking_issue = _active_blocking_issue(printer)
    if blocking_issue is not None:
        code = str(
            blocking_issue.get("code")
            or blocking_issue.get("raw_code")
            or "unbekannt"
        ).strip()
        return (
            False,
            "Aktive blockierende Druckerstörung: "
            f"{code}. Behebe und bestätige die Störung am Drucker, "
            "bevor ein neuer Auftrag gestartet wird.",
        )

    error_code = getattr(printer, "error_code", None)
    if error_code is not None:
        normalized_error = str(error_code).strip().casefold()
        if normalized_error not in _EMPTY_ERROR_CODES:
            return (
                False,
                "Der Drucker meldet den Fehlercode "
                f"{error_code}. Ein neuer Druckauftrag wird nicht gestartet.",
            )

    state = str(printer.printer_state or "unknown").casefold()
    if state not in _SAFE_START_STATES:
        return (
            False,
            f"Druckerzustand '{state}' erlaubt derzeit keinen neuen Druckauftrag.",
        )
    return True, ""


def _ams_slots(printer: Any) -> list[dict[str, Any]]:
    ams = (
        printer.ams
        if isinstance(getattr(printer, "ams", None), dict)
        else {}
    )
    result: list[dict[str, Any]] = []
    for slot in ams.get("slots", []):
        if not isinstance(slot, dict):
            continue
        result.append({
            "global_id": str(slot.get("global_id", "")),
            "unit_id": str(slot.get("unit_id", "")),
            "slot_index": int(slot.get("slot_index", 0) or 0),
            "display_slot": int(
                slot.get("display_slot", int(slot.get("slot_index", 0) or 0) + 1)
                or int(slot.get("slot_index", 0) or 0) + 1
            ),
            "tray_id": str(slot.get("tray_id", "")),
            "material": str(slot.get("material", "")),
            "sub_brand": str(slot.get("sub_brand", "")),
            "color": slot.get("color"),
            "present": bool(slot.get("present")),
        })
    return result


def _authoritative_ams_start(
    job: dict[str, Any],
    printer: Any,
) -> tuple[AuthoritativeAmsStart | None, web.Response | None]:
    try:
        resolved = derive_authoritative_ams_start(
            job,
            printer_id=str(printer.printer_id),
            printer_slots=_ams_slots(printer),
        )
    except DirectPrintMaterialPlanError as exc:
        return None, _error(
            409,
            "authoritative_ams_plan_invalid",
            str(exc),
        )
    ams = (
        printer.ams
        if isinstance(getattr(printer, "ams", None), dict)
        else {}
    )
    if resolved.use_ams and not bool(ams.get("available")):
        return None, _error(
            409,
            "ams_unavailable",
            "Am Ziel-Drucker wurde kein AMS beziehungsweise AMS Lite erkannt.",
        )
    return resolved, None


def _start_options(
    payload: dict[str, Any],
    resolved: AuthoritativeAmsStart,
) -> dict[str, Any]:
    """Build options from the server plan; browser source values are ignored."""
    return {
        "use_ams": resolved.use_ams,
        "ams_mapping": list(resolved.mapping),
        "bed_leveling": bool(payload.get("bed_leveling", True)),
        "flow_cali": bool(payload.get("flow_cali", False)),
        "vibration_cali": bool(payload.get("vibration_cali", True)),
        "timelapse": bool(payload.get("timelapse", False)),
    }


class DirectPrintStatusView(HomeAssistantView):
    url = f"{API_PREFIX}/direct-print/status"
    name = "api:ultimate_3d_studio_v6:direct_print_status"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        items = []
        for runtime in _runtimes(hass):
            for printer in await runtime.async_printers():
                ready, reason = _printer_ready(printer)
                state = str(printer.printer_state).casefold()
                terminal = state in _SAFE_START_STATES
                items.append({
                    "printer_id": printer.printer_id,
                    "name": printer.name,
                    "provider": printer.provider,
                    "connection_state": printer.connection_state,
                    "printer_state": printer.printer_state,
                    "current_file": None if terminal else printer.current_file,
                    "last_file": printer.current_file if terminal else None,
                    "ready": ready,
                    "reason": reason or None,
                    "ams": {
                        "available": bool(printer.ams.get("available"))
                        if isinstance(printer.ams, dict)
                        else False,
                        "kind": printer.ams.get("kind")
                        if isinstance(printer.ams, dict)
                        else None,
                        "slots": _ams_slots(printer),
                    },
                })
        return web.json_response({
            "data": {
                "items": items,
                "two_step_confirmation": True,
                "one_step_disabled": True,
                "authoritative_material_source_required": True,
                "supported_material_sources": ["ams", "external_spool"],
                "external_spool_fallback": False,
            }
        })


class DirectPrintExecuteView(HomeAssistantView):
    url = f"{API_PREFIX}/jobs/{{job_id}}/print/execute"
    name = "api:ultimate_3d_studio_v6:direct_print_execute"
    requires_auth = True

    async def post(
        self,
        request: web.Request,
        job_id: str,
    ) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        return _error(
            410,
            "one_step_print_disabled",
            "Der Ein-Schritt-Druck ist deaktiviert. Verwende prepare und start.",
            job_id=job_id,
        )


class DirectPrintTransferStatusView(HomeAssistantView):
    url = f"{API_PREFIX}/jobs/{{job_id}}/print/transfer-status"
    name = "api:ultimate_3d_studio_v6:direct_print_transfer_status"
    requires_auth = True

    async def get(
        self,
        request: web.Request,
        job_id: str,
    ) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        printer_id = str(request.query.get("printer_id", "")).strip()
        if not printer_id:
            return _error(400, "printer_required", "printer_id is required")
        status = get_direct_print_runtime(
            request.app["hass"],
        ).transfer_status(
            job_id=job_id,
            printer_id=printer_id,
        )
        if status is None:
            return _error(
                404,
                "transfer_not_found",
                "No transfer state exists for this job and printer",
            )
        return web.json_response({"data": status})


class DirectPrintPrepareView(HomeAssistantView):
    url = f"{API_PREFIX}/jobs/{{job_id}}/print/prepare"
    name = "api:ultimate_3d_studio_v6:direct_print_prepare"
    requires_auth = True

    async def post(
        self,
        request: web.Request,
        job_id: str,
    ) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _json_object(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        if payload.get("confirmed") is not True:
            return _error(
                409,
                "confirmation_required",
                "Upload confirmation is required",
            )
        printer_id = str(payload.get("printer_id", "")).strip()
        if not printer_id:
            return _error(400, "printer_required", "printer_id is required")

        hass: HomeAssistant = request.app["hass"]
        runtime, printer = await _find_runtime_and_printer(hass, printer_id)
        if runtime is None or printer is None:
            return _error(404, "printer_not_found", "Printer was not found")
        ready, reason = _printer_ready(printer)
        if not ready:
            return _error(409, "printer_not_ready", reason)

        router = V6SlicerBackendRouter(hass)
        transfer_runtime = get_direct_print_runtime(hass)
        uploaded = None
        try:
            job = await router.async_get_job(job_id)
            if job.get("status") != "succeeded":
                return _error(
                    409,
                    "artifact_not_ready",
                    "Slicer job has no completed artifact",
                )
            resolved, plan_error = _authoritative_ams_start(job, printer)
            if plan_error is not None:
                return plan_error
            assert resolved is not None

            slice_result = (
                job.get("slice_result")
                if isinstance(job.get("slice_result"), dict)
                else {}
            )
            raw_plate_index = job.get("requested_plate_index")
            if raw_plate_index is None:
                raw_plate_index = slice_result.get("plate_index")
            remote_filename = build_remote_3mf_filename(
                job.get("project_name"),
                raw_plate_index or 0,
            )
            transfer_runtime.begin_transfer(
                job_id=job_id,
                printer_id=printer_id,
                printer_name=printer.name,
                filename=remote_filename,
                total_bytes=int(job.get("output_size_bytes") or 0),
            )
            data, _artifact_filename, worker_digest, _content_type = (
                await router.async_artifact(job_id)
            )
            transfer_runtime.update_transfer(
                job_id=job_id,
                printer_id=printer_id,
                loaded_bytes=0,
                total_bytes=len(data),
                stage="preparing",
            )
            expected_digest = str(
                job.get("output_sha256") or worker_digest or ""
            ).lower()
            if len(expected_digest) != 64:
                transfer_runtime.fail_transfer(
                    job_id=job_id,
                    printer_id=printer_id,
                    error="Das Slicer-Artefakt besitzt keine gültige SHA-256-Prüfsumme.",
                )
                return _error(
                    409,
                    "artifact_digest_missing",
                    "Slicer artifact has no valid SHA-256",
                )

            def _transfer_progress(
                loaded_bytes: int,
                total_bytes: int,
                stage: str,
            ) -> None:
                transfer_runtime.update_transfer(
                    job_id=job_id,
                    printer_id=printer_id,
                    loaded_bytes=loaded_bytes,
                    total_bytes=total_bytes,
                    stage=stage,
                )

            uploaded = await runtime.async_upload_print_artifact(
                printer_id,
                remote_filename,
                data,
                on_progress=_transfer_progress,
            )
        except (
            SlicerServerConfigurationError,
            SlicerServerError,
        ) as exc:
            transfer_runtime.fail_transfer(
                job_id=job_id,
                printer_id=printer_id,
                error=str(exc),
            )
            return _error(502, "slicing_server_error", str(exc))
        except (DirectPrintError, RuntimeError) as exc:
            transfer_runtime.fail_transfer(
                job_id=job_id,
                printer_id=printer_id,
                error=str(exc),
            )
            return _error(502, "printer_upload_error", str(exc))

        if uploaded is None:
            transfer_runtime.fail_transfer(
                job_id=job_id,
                printer_id=printer_id,
                error="Der ausgewählte Drucker unterstützt keinen Upload.",
            )
            return _error(
                409,
                "direct_print_unsupported",
                "Selected printer provider does not support upload",
            )
        if uploaded.sha256.lower() != expected_digest:
            await runtime.async_delete_uploaded_artifact(
                printer_id,
                uploaded.remote_filename,
            )
            transfer_runtime.fail_transfer(
                job_id=job_id,
                printer_id=printer_id,
                error="Die SHA-256-Prüfsumme stimmt nicht mit dem Slicer-Artefakt überein.",
            )
            return _error(
                409,
                "artifact_digest_mismatch",
                "Uploaded artifact SHA-256 does not match slicer result",
            )

        transfer_runtime.complete_transfer(
            job_id=job_id,
            printer_id=printer_id,
        )
        prepared = transfer_runtime.create(
            job_id=job_id,
            printer_id=printer_id,
            uploaded=uploaded,
        )
        return web.json_response({
            "data": prepared.public(
                printer_name=printer.name,
                printer_state=printer.printer_state,
            ) | {
                "ams": {
                    "available": bool(printer.ams.get("available"))
                    if isinstance(printer.ams, dict)
                    else False,
                    "kind": printer.ams.get("kind")
                    if isinstance(printer.ams, dict)
                    else None,
                    "slots": _ams_slots(printer),
                },
                "authoritative_material_source": resolved.as_dict(),
                "final_confirmation_text": "DRUCKEN",
                "print_started": False,
            }
        }, status=201)


class DirectPrintStartView(HomeAssistantView):
    url = f"{API_PREFIX}/jobs/{{job_id}}/print/start"
    name = "api:ultimate_3d_studio_v6:direct_print_start"
    requires_auth = True

    async def post(
        self,
        request: web.Request,
        job_id: str,
    ) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _json_object(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        if (
            payload.get("confirmed") is not True
            or str(payload.get("confirmation_text", "")).strip()
            != "DRUCKEN"
        ):
            return _error(
                409,
                "confirmation_required",
                "Final confirmation text DRUCKEN is required",
            )

        token = str(payload.get("token", "")).strip()
        printer_id = str(payload.get("printer_id", "")).strip()
        artifact_sha256 = str(
            payload.get("artifact_sha256", "")
        ).strip().lower()
        if not token or not printer_id or len(artifact_sha256) != 64:
            return _error(
                400,
                "invalid_request",
                "token, printer_id and artifact_sha256 are required",
            )

        hass: HomeAssistant = request.app["hass"]
        runtime, printer = await _find_runtime_and_printer(hass, printer_id)
        if runtime is None or printer is None:
            return _error(404, "printer_not_found", "Printer was not found")
        ready, reason = _printer_ready(printer)
        if not ready:
            return _error(409, "printer_not_ready", reason)

        router = V6SlicerBackendRouter(hass)
        try:
            job = await router.async_get_job(job_id)
        except (
            SlicerServerConfigurationError,
            SlicerServerError,
        ) as exc:
            return _error(502, "slicing_server_error", str(exc))
        if job.get("status") != "succeeded":
            return _error(
                409,
                "artifact_not_ready",
                "Slicer job has no completed artifact",
            )
        resolved, plan_error = _authoritative_ams_start(job, printer)
        if plan_error is not None:
            return plan_error
        assert resolved is not None
        options = _start_options(payload, resolved)

        try:
            prepared = get_direct_print_runtime(hass).consume(
                token,
                job_id=job_id,
                printer_id=printer_id,
                expected_sha256=artifact_sha256,
            )
            result = await runtime.async_start_uploaded_artifact(
                prepared.uploaded,
                **options,
            )
        except (
            DirectPrintAuthorizationError,
            DirectPrintError,
            RuntimeError,
            ValueError,
        ) as exc:
            return _error(409, "direct_print_rejected", str(exc))
        if result is None:
            return _error(
                409,
                "direct_print_unsupported",
                "Selected printer provider does not support print start",
            )
        return web.json_response({
            "data": result | {
                "use_ams": resolved.use_ams,
                "ams_mapping": list(resolved.mapping),
                "material_source": (
                    "ams" if resolved.use_ams else "external_spool"
                ),
                "material_source_plan": resolved.source,
            }
        }, status=202)


class DirectPrintDiscardView(HomeAssistantView):
    url = f"{API_PREFIX}/jobs/{{job_id}}/print/discard"
    name = "api:ultimate_3d_studio_v6:direct_print_discard"
    requires_auth = True

    async def post(
        self,
        request: web.Request,
        job_id: str,
    ) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _json_object(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        token = str(payload.get("token", "")).strip()
        if payload.get("confirmed") is not True or not token:
            return _error(
                409,
                "confirmation_required",
                "Discard confirmation and token are required",
            )

        hass: HomeAssistant = request.app["hass"]
        prepared = get_direct_print_runtime(hass).discard(token)
        if prepared is None or prepared.job_id != job_id:
            return _error(
                404,
                "prepared_print_not_found",
                "Prepared print was not found",
            )
        runtime, _printer = await _find_runtime_and_printer(
            hass,
            prepared.printer_id,
        )
        deleted = False
        if runtime is not None:
            deleted = bool(await runtime.async_delete_uploaded_artifact(
                prepared.printer_id,
                prepared.uploaded.remote_filename,
            ))
        return web.json_response({
            "data": {
                "discarded": True,
                "remote_deleted": deleted,
            }
        })


def async_register_direct_print_views(hass: HomeAssistant) -> None:
    for view in (
        DirectPrintStatusView(),
        DirectPrintExecuteView(),
        DirectPrintTransferStatusView(),
        DirectPrintPrepareView(),
        DirectPrintStartView(),
        DirectPrintDiscardView(),
    ):
        hass.http.register_view(view)
