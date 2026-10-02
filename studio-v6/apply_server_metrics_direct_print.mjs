import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));

async function patch(relativePath, replacements) {
  const target = path.join(root, relativePath);
  let text = await readFile(target, "utf8");
  for (const [before, after] of replacements) {
    if (text.includes(after)) continue;
    if (!text.includes(before)) throw new Error(`Marker fehlt in ${relativePath}: ${before.slice(0, 120)}`);
    text = text.replace(before, after);
  }
  await writeFile(target, text, "utf8");
}

await patch("deploy/homeassistant/custom_components/ultimate_3d_studio_v6/slicer_backend_router.py", [
  [
    "from pathlib import Path\nfrom typing import Any\nfrom uuid import uuid4",
    "from hashlib import sha256\nfrom io import BytesIO\nfrom pathlib import Path\nfrom typing import Any\nfrom uuid import uuid4\nimport re\nimport zipfile",
  ],
  [
    "def _server_job(payload: dict[str, Any]) -> dict[str, Any]:",
    `def _parse_duration(value: str) -> int | None:\n    hours = re.search(r"(\\d+)h", value)\n    minutes = re.search(r"(\\d+)m", value)\n    seconds = re.search(r"(\\d+)s", value)\n    if not any((hours, minutes, seconds)):\n        return None\n    return (int(hours.group(1)) if hours else 0) * 3600 + (int(minutes.group(1)) if minutes else 0) * 60 + (int(seconds.group(1)) if seconds else 0)\n\n\ndef _gcode_metadata(data: bytes) -> dict[str, Any]:\n    text = data.decode("utf-8", errors="ignore")\n    def number(pattern: str) -> float | None:\n        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)\n        return float(match.group(1)) if match else None\n    def string(pattern: str) -> str | None:\n        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)\n        return match.group(1).strip().strip('"') if match else None\n    duration_match = re.search(r"total estimated time:\\s*([^\\r\\n]+)", text, re.IGNORECASE)\n    return {\n        "print_time_seconds": _parse_duration(duration_match.group(1)) if duration_match else None,\n        "filament_used_g": number(r"^;\\s*total filament weight \\[g\\]\\s*:\\s*([0-9.]+)"),\n        "filament_length_mm": number(r"^;\\s*total filament length \\[mm\\]\\s*:\\s*([0-9.]+)"),\n        "filament_volume_cm3": number(r"^;\\s*total filament volume \\[cm\\^3\\]\\s*:\\s*([0-9.]+)"),\n        "layer_count": int(number(r"^;\\s*total layer number\\s*:\\s*([0-9.]+)") or 0) or None,\n        "filament_profile": string(r"^;\\s*default_filament_profile\\s*=\\s*(.+)$"),\n        "printer_model": string(r"^;\\s*printer_model\\s*=\\s*(.+)$"),\n        "nozzle_diameter": number(r"^;\\s*nozzle_diameter\\s*=\\s*([0-9.]+)"),\n    }\n\n\ndef _server_gcode_3mf(job_id: str, filename: str, data: bytes) -> tuple[bytes, str, str]:\n    output = BytesIO()\n    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:\n        archive.writestr("Metadata/plate_1.gcode", data)\n    content = output.getvalue()\n    safe_stem = Path(filename).stem or job_id\n    artifact_name = f"{safe_stem}.gcode.3mf"\n    return content, artifact_name, sha256(content).hexdigest()\n\n\ndef _server_job(payload: dict[str, Any], metadata: dict[str, Any] | None = None, artifact_name: str | None = None, artifact_size: int | None = None, artifact_digest: str | None = None) -> dict[str, Any]:`,
  ],
  [
    `        "output_size_bytes": payload.get("download_size"),\n        "output_filename": payload.get("download_name"),\n        "slice_result": {\n            "print_time_seconds": None,\n            "filament_used_g": None,\n            "engine": result.get("engine") or job.get("engine"),\n            "output_format": result.get("output_format") or job.get("output_format"),\n        },`,
    `        "output_size_bytes": artifact_size or payload.get("download_size"),\n        "output_filename": artifact_name or payload.get("download_name"),\n        "output_file": artifact_name or payload.get("download_name"),\n        "output_sha256": artifact_digest,\n        "profiles": {\n            "machine": job.get("printer_profile"),\n            "process": job.get("process_profile"),\n            "filaments": [metadata.get("filament_profile")] if metadata and metadata.get("filament_profile") else [],\n            "source": "native_slicing_server",\n        },\n        "slice_result": {\n            "print_time_seconds": metadata.get("print_time_seconds") if metadata else None,\n            "filament_used_g": metadata.get("filament_used_g") if metadata else None,\n            "filament_length_mm": metadata.get("filament_length_mm") if metadata else None,\n            "filament_volume_cm3": metadata.get("filament_volume_cm3") if metadata else None,\n            "layer_count": metadata.get("layer_count") if metadata else None,\n            "filament_profile": metadata.get("filament_profile") if metadata else None,\n            "printer_model": metadata.get("printer_model") if metadata else None,\n            "nozzle_diameter": metadata.get("nozzle_diameter") if metadata else None,\n            "engine": result.get("engine") or job.get("engine"),\n            "output_format": "gcode_3mf" if artifact_name else (result.get("output_format") or job.get("output_format")),\n        },`,
  ],
  [
    `                "gcode_3mf_artifact": False,\n                "job_cancellation": False,\n                "direct_print": False,`,
    `                "gcode_3mf_artifact": ready,\n                "job_cancellation": False,\n                "direct_print": ready,`,
  ],
  [
    `                return _server_job(await response.json(content_type=None))`,
    `                payload = await response.json(content_type=None)\n            if str(payload.get("status")) == "completed":\n                data, filename, digest, _content_type = await self.async_artifact(SERVER_PREFIX + raw_id)\n                metadata = _gcode_metadata(await self._server_raw_artifact(raw_id))\n                return _server_job(payload, metadata, filename, len(data), digest)\n            return _server_job(payload)`,
  ],
  [
    `    async def async_artifact(self, job_id: str) -> tuple[bytes, str, str | None, str]:`,
    `    async def _server_raw_artifact(self, raw_id: str) -> bytes:\n        try:\n            async with self.session.get(f"{SERVER_ENDPOINT}/api/v1/jobs/{raw_id}/download", timeout=ClientTimeout(total=300)) as response:\n                if response.status >= 400:\n                    raise SlicerWorkerError(f"Server-Download HTTP {response.status}")\n                return await response.read()\n        except (ClientError, TimeoutError) as exc:\n            raise SlicerWorkerError(f"Slicing Server nicht erreichbar: {exc}") from exc\n\n    async def async_artifact(self, job_id: str) -> tuple[bytes, str, str | None, str]:`,
  ],
  [
    `        try:\n            async with self.session.get(f"{SERVER_ENDPOINT}/api/v1/jobs/{raw_id}/download", timeout=ClientTimeout(total=300)) as response:\n                if response.status >= 400:\n                    raise SlicerWorkerError(f"Server-Download HTTP {response.status}")\n                disposition = response.headers.get("Content-Disposition", "")\n                filename = f"{raw_id}.gcode"\n                if 'filename="' in disposition:\n                    filename = disposition.split('filename="', 1)[1].split('"', 1)[0]\n                return await response.read(), filename, None, "application/octet-stream"\n        except (ClientError, TimeoutError) as exc:\n            raise SlicerWorkerError(f"Slicing Server nicht erreichbar: {exc}") from exc`,
    `        raw = await self._server_raw_artifact(raw_id)\n        content, filename, digest = _server_gcode_3mf(raw_id, raw_id, raw)\n        return content, filename, digest, "model/3mf"`,
  ],
]);

await patch("deploy/homeassistant/custom_components/ultimate_3d_studio_v6/direct_print_views.py", [
  [
    `from .slicer_worker_client import (\n    SlicerWorkerClient,\n    SlicerWorkerConfigurationError,\n    SlicerWorkerError,\n)`,
    `from .slicer_backend_router import V6SlicerBackendRouter\nfrom .slicer_worker_client import (\n    SlicerWorkerConfigurationError,\n    SlicerWorkerError,\n)`,
  ],
  [
    `        client = SlicerWorkerClient(hass)\n        uploaded = None\n        try:\n            job = await client.async_get_job(job_id)`,
    `        router = V6SlicerBackendRouter(hass)\n        uploaded = None\n        try:\n            job = await router.async_get_job(job_id)`,
  ],
  [
    `            data, filename, worker_digest = await client.async_artifact(job_id)`,
    `            data, filename, worker_digest, _content_type = await router.async_artifact(job_id)`,
  ],
]);

await patch("frontend/slicer-workspace-v4.ts", [
  [
    `        ${this.#job?.status === "succeeded" && this.#backend === "pc" ? '<section class="direct-print"><ultimate-3d-direct-print-panel id="direct-print-panel"></ultimate-3d-direct-print-panel></section>' : ""}`,
    `        ${this.#job?.status === "succeeded" ? '<section class="direct-print"><ultimate-3d-direct-print-panel id="direct-print-panel"></ultimate-3d-direct-print-panel></section>' : ""}`,
  ],
  [
    `${this.#backend === "pc" ? "G-Code-3MF" : "G-Code"} herunterladen`,
    `G-Code-3MF herunterladen`,
  ],
]);

console.log("Server metrics and direct print patch: OK");