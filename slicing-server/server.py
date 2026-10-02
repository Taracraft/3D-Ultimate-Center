#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import sys

VERSION = "0.1.0-alpha5"
API_VERSION = 2
CONFIG_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/var/lib/homeassistant/3d-printer-slicing-server/config.json")
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
BASE = Path(CONFIG.get("base_dir", "/var/lib/homeassistant/3d-printer-slicing-server"))
DATA = BASE / "data"
API = BASE / "api"
WEB = BASE / "web"
UPLOADS = DATA / "uploads"
JOBS = DATA / "jobs"
OUTPUT = DATA / "output"
RUN = BASE / "run"
PROFILES = BASE / "profiles" / "printers"
BAMBU_PROFILE_ROOT = BASE / "engines" / "bambu-studio" / "squashfs-root" / "resources" / "profiles"
TOKEN = str(CONFIG.get("token", ""))
MAX_UPLOAD_BYTES = int(CONFIG.get("max_upload_bytes", 512 * 1024 * 1024))
ALLOWED_EXTENSIONS = {".stl", ".3mf", ".obj", ".amf"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
STARTED = datetime.now(timezone.utc)
A1_NOZZLE_CONTRACTS = {
    .2: {
        "machine": "BBL/machine/Bambu Lab A1 0.2 nozzle.json",
        "process": "BBL/process/0.10mm Standard @BBL A1 0.2 nozzle.json",
        "min_layer": .04,
        "max_layer": .14,
    },
    .4: {
        "machine": "BBL/machine/Bambu Lab A1 0.4 nozzle.json",
        "process": "BBL/process/0.20mm Standard @BBL A1.json",
        "min_layer": .08,
        "max_layer": .28,
    },
    .6: {
        "machine": "BBL/machine/Bambu Lab A1 0.6 nozzle.json",
        "process": "BBL/process/0.30mm Strength @BBL A1 0.6 nozzle.json",
        "min_layer": .12,
        "max_layer": .42,
    },
    .8: {
        "machine": "BBL/machine/Bambu Lab A1 0.8 nozzle.json",
        "process": "BBL/process/0.40mm Standard @BBL A1 0.8 nozzle.json",
        "min_layer": .16,
        "max_layer": .56,
    },
}

for directory in (DATA, API, WEB, UPLOADS, JOBS, OUTPUT, RUN, PROFILES):
    directory.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def safe_filename(value: str) -> str | None:
    name = Path(value).name
    if name != value or not SAFE_NAME.fullmatch(name):
        return None
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        return None
    return name


def safe_job_id(value: str | None) -> str:
    if value and SAFE_NAME.fullmatch(value) and "." not in value:
        return value
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"job-{timestamp}-{secrets.token_hex(4)}"


def result_file(job_id: str) -> Path | None:
    directory = OUTPUT / job_id
    if not directory.is_dir():
        return None
    candidates = [item for item in directory.iterdir() if item.is_file() and item.suffix.lower() in {".gcode", ".3mf"}]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _scalar(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _number(value):
    value = _scalar(value)
    try:
        text = str(value).replace(",", ".").strip()
        if text.endswith("%"):
            text = text[:-1].strip()
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _a1_nozzle_job_contract(target_printer: dict, process_overrides: dict):
    model = re.sub(
        r"[^a-z0-9]+",
        "",
        str(target_printer.get("model") or target_printer.get("name") or "").casefold(),
    )
    if "a1mini" in model or "a1m" in model or "a1" not in model:
        return None, "invalid_a1_nozzle_target"
    diameter = _number(target_printer.get("nozzle_diameter_mm"))
    contract = next(
        (
            value
            for key, value in A1_NOZZLE_CONTRACTS.items()
            if diameter is not None and abs(key - diameter) < 1e-6
        ),
        None,
    )
    if contract is None:
        return None, "unsupported_a1_nozzle_diameter"
    if target_printer.get("native_machine_profile") != contract["machine"]:
        return None, "invalid_native_machine_profile"
    if target_printer.get("native_process_profile") != contract["process"]:
        return None, "invalid_native_process_profile"
    for key in ("machine", "process"):
        path = (BAMBU_PROFILE_ROOT / str(contract[key])).resolve()
        try:
            path.relative_to(BAMBU_PROFILE_ROOT.resolve())
        except ValueError:
            return None, f"invalid_native_{key}_profile"
        if not path.is_file():
            return None, f"native_{key}_profile_not_found"
    support_mode = str(process_overrides.get("support_mode") or "off").strip().casefold()
    if support_mode not in {"off", "normal", "tree"}:
        return None, "invalid_support_mode"
    support_style = str(process_overrides.get("support_style") or "standard").strip().casefold()
    if support_style not in {"standard", "tree_slim", "tree_strong", "tree_hybrid", "tree_organic"}:
        return None, "invalid_support_style"
    support_angle = process_overrides.get("support_threshold_angle")
    if support_angle is not None:
        value = _number(support_angle)
        if value is None or not 0 <= value <= 89:
            return None, "invalid_support_threshold_angle"
    layer = process_overrides.get("layer_height_mm")
    if layer is not None:
        value = _number(layer)
        if value is None or not contract["min_layer"] <= value <= contract["max_layer"]:
            return None, "invalid_layer_height_for_nozzle"
    for key in ("outer_wall_speed_mm_s", "inner_wall_speed_mm_s"):
        speed = process_overrides.get(key)
        if speed is None:
            continue
        value = _number(speed)
        if value is None or not 1 <= value <= 500:
            return None, f"invalid_{key}"
    return contract, None


def _boolean(value):
    value = _scalar(value)
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return None


def _runtime_summary(job_id: str) -> dict:
    materials = read_json(RUN / f"{job_id}-materials.json", {})
    process = read_json(RUN / f"{job_id}-process.json", {})
    machine = read_json(RUN / f"{job_id}-machine.json", {})
    filament_items = []
    raw_filaments = materials.get("filaments") if isinstance(materials, dict) else None
    if isinstance(raw_filaments, list):
        for item in raw_filaments[:32]:
            if not isinstance(item, dict):
                continue
            filament_items.append({
                key: item.get(key)
                for key in (
                    "channel", "name", "setting_id", "filament_id", "color", "material",
                    "ams_slot", "selected_profile_id", "selected_profile_name",
                    "nozzle_temperature", "nozzle_temperature_initial_layer",
                    "filament_flow_ratio", "filament_max_volumetric_speed",
                )
                if item.get(key) is not None
            })
    purge = materials.get("purge_tower") if isinstance(materials, dict) else None
    purge_summary = None
    if isinstance(purge, dict):
        purge_summary = {
            key: purge.get(key)
            for key in (
                "enabled", "plate_index", "plate_width_mm", "plate_depth_mm", "width_mm",
                "brim_width_mm", "position_x", "position_y", "clamped", "bounds",
            )
            if purge.get(key) is not None
        }
    process_summary = {
        "layer_height_mm": _number(process.get("layer_height")),
        "initial_layer_height_mm": _number(process.get("initial_layer_print_height")),
        "wall_loops": _number(process.get("wall_loops")),
        "top_shell_layers": _number(process.get("top_shell_layers")),
        "bottom_shell_layers": _number(process.get("bottom_shell_layers")),
        "sparse_infill_density_percent": _number(process.get("sparse_infill_density")),
        "sparse_infill_pattern": _scalar(process.get("sparse_infill_pattern")),
        "brim_type": _scalar(process.get("brim_type")),
        "brim_width_mm": _number(process.get("brim_width")),
        "raft_layers": _number(process.get("raft_layers")),
        "support_enabled": _boolean(process.get("enable_support")),
        "support_type": _scalar(process.get("support_type")),
        "support_build_plate_only": _boolean(process.get("support_on_build_plate_only")),
        "support_threshold_angle": _number(process.get("support_threshold_angle")),
        "bed_type": _scalar(process.get("curr_bed_type")),
        "outer_wall_speed_mm_s": _number(process.get("outer_wall_speed")),
        "inner_wall_speed_mm_s": _number(process.get("inner_wall_speed")),
        "sparse_infill_speed_mm_s": _number(process.get("sparse_infill_speed")),
        "bridge_speed_mm_s": _number(process.get("bridge_speed")),
        "travel_speed_mm_s": _number(process.get("travel_speed")),
        "initial_layer_speed_mm_s": _number(process.get("initial_layer_speed")),
        "default_acceleration_mm_s2": _number(process.get("default_acceleration")),
    }
    process_summary = {key: value for key, value in process_summary.items() if value is not None}
    machine_summary = {
        "nozzle_diameter_mm": _number(machine.get("nozzle_diameter")),
        "printable_height_mm": _number(machine.get("printable_height")),
        "printer_model": _scalar(machine.get("printer_model")),
        "printer_variant": _scalar(machine.get("printer_variant")),
    }
    machine_summary = {key: value for key, value in machine_summary.items() if value is not None}
    result = {
        "schema_version": materials.get("schema_version") if isinstance(materials, dict) else None,
        "model": materials.get("model") if isinstance(materials, dict) else None,
        "triangle_count": materials.get("triangle_count") if isinstance(materials, dict) else None,
        "physical_extruder_count": materials.get("physical_extruder_count") if isinstance(materials, dict) else None,
        "material_channel_count": materials.get("material_channel_count") if isinstance(materials, dict) else None,
        "requested_plate_index": materials.get("requested_plate_index") if isinstance(materials, dict) else None,
        "selected_process_profile": (
            materials.get("selected_process_profile")
            if isinstance(materials, dict)
            and isinstance(materials.get("selected_process_profile"), dict)
            else None
        ),
        "process_settings": (
            materials.get("process_settings")
            if isinstance(materials, dict)
            and isinstance(materials.get("process_settings"), dict)
            else None
        ),
        "purge_tower": purge_summary,
        "filaments": filament_items,
        "process": process_summary,
        "machine": machine_summary,
    }
    return {key: value for key, value in result.items() if value not in (None, [], {})}


def _progress_state(job_id: str) -> dict:
    payload = read_json(OUTPUT / f"{job_id}.progress.json", {})
    return payload if isinstance(payload, dict) else {}


def _engine_result(job_id: str) -> dict:
    payload = read_json(OUTPUT / job_id / "result.json", {})
    return payload if isinstance(payload, dict) else {}


def job_state(job_id: str) -> dict:
    payload = {}
    state = "not_found"
    state_path = None
    for current in ("queued", "slicing", "completed", "failed", "cancelled"):
        path = JOBS / f"{job_id}.{current}.json"
        if path.is_file():
            payload = read_json(path, {})
            state = current
            state_path = path
            break
    result_path = OUTPUT / f"{job_id}.result.json"
    progress_path = OUTPUT / f"{job_id}.progress.json"
    result = read_json(result_path, {})
    if state == "not_found" and result:
        state = result.get("status", "unknown")
    download = result_file(job_id)
    progress = _progress_state(job_id)
    runtime = _runtime_summary(job_id)
    engine_result = _engine_result(job_id)
    state_timestamp_paths = [state_path] if state_path is not None else []
    if state in {"completed", "failed", "cancelled"}:
        state_timestamp_paths.extend(
            path
            for path in (result_path, progress_path)
            if path.is_file()
        )
    state_updated_at = None
    if state_timestamp_paths:
        state_updated_at = datetime.fromtimestamp(
            max(path.stat().st_mtime for path in state_timestamp_paths),
            timezone.utc,
        ).isoformat()
    return {
        "job_id": job_id,
        "status": state,
        "status_updated_at": state_updated_at,
        "job": payload,
        "result": result,
        "progress": progress,
        "runtime": runtime,
        "engine_result": engine_result,
        "download_url": f"/api/v1/jobs/{job_id}/download" if download else None,
        "download_name": download.name if download else None,
        "download_size": download.stat().st_size if download else None,
    }


def list_jobs() -> list[dict]:
    ids: dict[str, float] = {}
    for item in JOBS.glob("*.json"):
        parts = item.name.rsplit(".", 2)
        if len(parts) == 3:
            ids[parts[0]] = max(ids.get(parts[0], 0), item.stat().st_mtime)
    for item in OUTPUT.glob("*.result.json"):
        job_id = item.name.removesuffix(".result.json")
        ids[job_id] = max(ids.get(job_id, 0), item.stat().st_mtime)
    jobs = []
    for job_id, modified in sorted(ids.items(), key=lambda pair: pair[1], reverse=True)[:100]:
        current = job_state(job_id)
        job = current.get("job", {})
        result = current.get("result", {})
        progress = current.get("progress", {}) if isinstance(current.get("progress"), dict) else {}
        jobs.append({
            "job_id": job_id,
            "status": current["status"],
            "modified": modified,
            "printer_profile": job.get("printer_profile"),
            "input_file": job.get("input_file"),
            "engine": result.get("engine") or job.get("engine"),
            "output_format": result.get("output_format") or job.get("output_format"),
            "download_url": current.get("download_url"),
            "download_name": current.get("download_name"),
            "download_size": current.get("download_size"),
            "progress": {
                key: progress.get(key)
                for key in (
                    "source", "active", "plate_index", "plate_count", "plate_percent",
                    "total_percent", "message", "warning", "updated_at", "elapsed_seconds",
                    "eta_seconds", "eta_confidence",
                )
                if progress.get(key) is not None
            },
            "engine_result_available": bool(current.get("engine_result")),
            "status_updated_at": current.get("status_updated_at"),
            "job": job,
            "result": result,
            "runtime": current.get("runtime") or {},
            "engine_result": current.get("engine_result") or {},
        })
    return jobs


def _remove_path(path: Path) -> bool:
    if path.is_dir():
        shutil.rmtree(path)
        return True
    if path.is_file():
        path.unlink()
        return True
    return False


def _upload_is_referenced(filename: str) -> bool:
    for state_file in JOBS.glob("*.json"):
        payload = read_json(state_file, {})
        if (
            isinstance(payload, dict)
            and payload.get("input_file") == filename
        ):
            return True
    return False


def delete_job(job_id: str) -> dict:
    current = job_state(job_id)
    status = str(current.get("status") or "not_found")
    if status == "not_found":
        return {"error": "job_not_found", "status": 404}
    if status not in {"completed", "failed", "cancelled"}:
        return {
            "error": "job_not_terminal",
            "job_status": status,
            "status": 409,
        }

    job = current.get("job") if isinstance(current.get("job"), dict) else {}
    input_file = safe_filename(str(job.get("input_file") or ""))
    removed_paths = 0

    for state_file in JOBS.glob(f"{job_id}.*.json"):
        removed_paths += int(_remove_path(state_file))
    for output_file in (
        OUTPUT / f"{job_id}.result.json",
        OUTPUT / f"{job_id}.progress.json",
        OUTPUT / job_id,
    ):
        removed_paths += int(_remove_path(output_file))
    for runtime_file in RUN.glob(f"{job_id}-*"):
        removed_paths += int(_remove_path(runtime_file))

    input_file_deleted = False
    if input_file and not _upload_is_referenced(input_file):
        input_file_deleted = _remove_path(UPLOADS / input_file)

    return {
        "deleted": True,
        "job_id": job_id,
        "previous_status": status,
        "removed_paths": removed_paths,
        "input_file_deleted": input_file_deleted,
    }


def release_job(job_id: str) -> dict:
    """Mark one manually held queued job for the dispatcher to process."""
    current = job_state(job_id)
    status = str(current.get("status") or "not_found")
    if status == "not_found":
        return {"error": "job_not_found", "status": 404}
    if status != "queued":
        return {
            "error": "job_not_queued",
            "job_status": status,
            "status": 409,
        }

    queued_path = JOBS / f"{job_id}.queued.json"
    payload = read_json(queued_path, None)
    if not isinstance(payload, dict):
        return {"error": "invalid_job_json", "status": 500}
    if payload.get("manual_release") is False:
        return {
            "error": "job_not_manually_held",
            "status": 409,
        }
    if str(payload.get("released_at") or "").strip():
        return {
            "released": True,
            "job_id": job_id,
            "status": "queued",
            "already_released": True,
        }

    payload["released_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(queued_path, payload)
    return {
        "released": True,
        "job_id": job_id,
        "status": "queued",
    }


def list_files() -> list[dict]:
    files = []
    for item in sorted(UPLOADS.iterdir(), key=lambda value: value.stat().st_mtime, reverse=True):
        if item.is_file() and item.suffix.lower() in ALLOWED_EXTENSIONS and not item.name.startswith("."):
            stat = item.stat()
            files.append({"filename": item.name, "size": stat.st_size, "modified": stat.st_mtime})
    return files


def list_printers() -> list[dict]:
    printers = []
    for path in sorted(PROFILES.glob("*.json")):
        profile = read_json(path, {})
        printers.append({
            "id": path.stem,
            "name": profile.get("name") or profile.get("display_name") or path.stem,
            "engine": profile.get("engine", "auto"),
            "vendor": profile.get("vendor"),
            "model": profile.get("model"),
        })
    return printers


class Handler(BaseHTTPRequestHandler):
    server_version = f"3DPrinterSlicingServer/{VERSION}"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def common_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'")

    def send_bytes(self, status: int, body: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.common_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload) -> None:
        self.send_bytes(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def authorized(self) -> bool:
        if not TOKEN:
            return True
        supplied = self.headers.get("X-API-Token", "")
        authorization = self.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
        return secrets.compare_digest(supplied, TOKEN)

    def require_authorization(self) -> bool:
        if self.authorized():
            return True
        self.send_json(401, {"error": "unauthorized"})
        return False

    def read_body(self, maximum: int) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "invalid_content_length"})
            return None
        if length <= 0 or length > maximum:
            self.send_json(413, {"error": "invalid_body_size", "maximum": maximum})
            return None
        return self.rfile.read(length)

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path in {"/", "/index.html"}:
            page = WEB / "index.html"
            if not page.is_file():
                self.send_json(503, {"error": "ui_not_installed"})
                return
            self.send_bytes(200, page.read_bytes(), "text/html; charset=utf-8")
            return

        if path.startswith("/assets/"):
            relative = Path(unquote(path.removeprefix("/assets/"))).name
            asset = WEB / relative
            if not asset.is_file():
                self.send_json(404, {"error": "not_found"})
                return
            content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            self.send_bytes(200, asset.read_bytes(), content_type)
            return

        if path in {"/api/v1/health", "/health.json"}:
            health = read_json(API / "health.json", {"status": "starting"})
            health["version"] = VERSION
            health["api_version"] = API_VERSION
            health["uptime_seconds"] = int((datetime.now(timezone.utc) - STARTED).total_seconds())
            self.send_json(200, health)
            return

        if not self.require_authorization():
            return

        protected_files = {
            "/api/v1/info": "info.json",
            "/api/v1/status": "status.json",
            "/api/v1/engines": "engines.json",
            "/api/v1/capabilities": "capabilities.json",
            "/api/v1/diagnostics": "diagnostics.json",
            "/info.json": "info.json",
            "/status.json": "status.json",
            "/engines.json": "engines.json",
            "/capabilities.json": "capabilities.json",
            "/diagnostics.json": "diagnostics.json",
        }
        if path in protected_files:
            payload = read_json(API / protected_files[path], {})
            if path in {"/api/v1/info", "/info.json"}:
                payload["version"] = VERSION
                payload["api_version"] = API_VERSION
            self.send_json(200, payload)
            return

        if path in {"/api/v1/printers", "/printers.json"}:
            self.send_json(200, {"printers": list_printers()})
            return

        if path == "/api/v1/files":
            self.send_json(200, {"files": list_files()})
            return

        if path == "/api/v1/jobs":
            self.send_json(200, {"jobs": list_jobs()})
            return

        if path.startswith("/api/v1/jobs/") and path.endswith("/download"):
            job_id = unquote(path.removeprefix("/api/v1/jobs/").removesuffix("/download").rstrip("/"))
            if not SAFE_NAME.fullmatch(job_id) or "." in job_id:
                self.send_json(400, {"error": "invalid_job_id"})
                return
            download = result_file(job_id)
            if download is None:
                self.send_json(404, {"error": "output_not_found"})
                return
            content_type = "application/octet-stream"
            self.send_bytes(200, download.read_bytes(), content_type, download.name)
            return

        if path.startswith("/api/v1/jobs/"):
            job_id = unquote(path.removeprefix("/api/v1/jobs/"))
            if not SAFE_NAME.fullmatch(job_id) or "." in job_id:
                self.send_json(400, {"error": "invalid_job_id"})
                return
            payload = job_state(job_id)
            self.send_json(404 if payload["status"] == "not_found" else 200, payload)
            return

        self.send_json(404, {"error": "not_found"})


    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if not self.require_authorization():
            return

        if path.startswith("/api/v1/jobs/"):
            job_id = unquote(path.removeprefix("/api/v1/jobs/"))
            if not SAFE_NAME.fullmatch(job_id) or "." in job_id:
                self.send_json(400, {"error": "invalid_job_id"})
                return
            result = delete_job(job_id)
            status = int(result.pop("status", 200))
            self.send_json(status, result)
            return

        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self.require_authorization():
            return

        if path.startswith("/api/v1/jobs/") and path.endswith("/release"):
            job_id = unquote(
                path.removeprefix("/api/v1/jobs/").removesuffix("/release").rstrip("/")
            )
            if not SAFE_NAME.fullmatch(job_id) or "." in job_id:
                self.send_json(400, {"error": "invalid_job_id"})
                return
            result = release_job(job_id)
            # Job state ("queued") and numeric HTTP error status are separate contracts.
            status = result.get("status", 200)
            if isinstance(status, int):
                result.pop("status", None)
            else:
                status = 200
            self.send_json(status, result)
            return

        if path.startswith("/api/v1/files/"):
            filename = safe_filename(unquote(path.removeprefix("/api/v1/files/")))
            if filename is None:
                self.send_json(400, {"error": "invalid_filename", "allowed_extensions": sorted(ALLOWED_EXTENSIONS)})
                return
            body = self.read_body(MAX_UPLOAD_BYTES)
            if body is None:
                return
            temporary = UPLOADS / f".{filename}.uploading"
            destination = UPLOADS / filename
            temporary.write_bytes(body)
            os.replace(temporary, destination)
            self.send_json(201, {"filename": filename, "size": destination.stat().st_size})
            return

        if path == "/api/v1/jobs":
            body = self.read_body(1024 * 1024)
            if body is None:
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_json(400, {"error": "invalid_json"})
                return
            if not isinstance(payload, dict):
                self.send_json(400, {"error": "job_must_be_object"})
                return

            filename = safe_filename(str(payload.get("input_file", "")))
            printer_profile = str(payload.get("printer_profile", "")).strip()
            engine = str(payload.get("engine", "auto")).strip() or "auto"
            output_format = str(payload.get("output_format", "gcode")).strip() or "gcode"

            native_multimaterial = payload.get("native_multimaterial", False)
            manual_release = payload.get("manual_release", False)
            material_plan = payload.get("material_plan", {})
            target_printer = payload.get("target_printer", {})
            process_overrides = payload.get("process_overrides", {})

            if not isinstance(native_multimaterial, bool):
                self.send_json(400, {"error": "invalid_native_multimaterial"})
                return
            if not isinstance(manual_release, bool):
                self.send_json(400, {"error": "invalid_manual_release"})
                return

            if material_plan is None:
                material_plan = {}
            if target_printer is None:
                target_printer = {}
            if process_overrides is None:
                process_overrides = {}

            if not isinstance(material_plan, dict):
                self.send_json(400, {"error": "invalid_material_plan"})
                return
            if not isinstance(target_printer, dict):
                self.send_json(400, {"error": "invalid_target_printer"})
                return
            if not isinstance(process_overrides, dict):
                self.send_json(400, {"error": "invalid_process_overrides"})
                return

            nozzle_contract = None
            if printer_profile == "bambu_lab_a1_04":
                nozzle_contract, nozzle_error = _a1_nozzle_job_contract(
                    target_printer,
                    process_overrides,
                )
                if nozzle_error:
                    self.send_json(400, {"error": nozzle_error})
                    return

            assignments = material_plan.get("assignments")
            filaments = material_plan.get("filaments")

            if assignments is not None and not isinstance(assignments, dict):
                self.send_json(400, {"error": "invalid_material_assignments"})
                return
            if filaments is not None and not isinstance(filaments, list):
                self.send_json(400, {"error": "invalid_material_filaments"})
                return

            # Ein Filamentkanal ist ausdrücklich gültig.
            # Der native Materialisierungspfad unterstützt ein- und mehrfarbige Modelle.

            if filename is None:
                self.send_json(400, {"error": "invalid_input_file"})
                return
            if not (UPLOADS / filename).is_file():
                self.send_json(404, {"error": "input_file_not_found", "filename": filename})
                return
            if not SAFE_NAME.fullmatch(printer_profile):
                self.send_json(400, {"error": "invalid_printer_profile"})
                return
            if not (PROFILES / f"{printer_profile}.json").is_file():
                self.send_json(404, {"error": "printer_profile_not_found", "printer_profile": printer_profile})
                return
            if engine not in {"auto", "bambu_studio", "prusaslicer", "curaengine"}:
                self.send_json(400, {"error": "invalid_engine"})
                return
            if output_format not in {"gcode", "3mf"}:
                self.send_json(400, {"error": "invalid_output_format"})
                return

            job_id = safe_job_id(payload.get("job_id"))
            if any(JOBS.glob(f"{job_id}.*.json")) or (OUTPUT / f"{job_id}.result.json").exists():
                self.send_json(409, {"error": "job_id_exists", "job_id": job_id})
                return

            job = {
                "job_id": job_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "printer_profile": printer_profile,
                "engine": engine,
                "input_file": filename,
                "process_profile": str(payload.get("process_profile", "default")),
                "filament_profile": str(payload.get("filament_profile", "default")),
                "output_format": output_format,
                "native_multimaterial": native_multimaterial,
                "manual_release": manual_release,
                "material_plan": material_plan,
                "target_printer": target_printer,
                "process_overrides": process_overrides,
            }
            if not manual_release:
                job["released_at"] = job["created_at"]
            if nozzle_contract is not None:
                job.update({
                    "nozzle_diameter_mm": target_printer["nozzle_diameter_mm"],
                    "native_machine_profile": nozzle_contract["machine"],
                    "native_process_profile": nozzle_contract["process"],
                })
            atomic_json(JOBS / f"{job_id}.queued.json", job)
            self.send_json(202, {"job_id": job_id, "status": "queued"})
            return

        self.send_json(404, {"error": "not_found"})


host = str(CONFIG.get("host", "127.0.0.1"))
port = int(CONFIG.get("port", 8099))
print(f"3D-Printer Slicing Server {VERSION} listening on {host}:{port}", flush=True)
ThreadingHTTPServer((host, port), Handler).serve_forever()