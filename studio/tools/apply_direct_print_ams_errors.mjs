import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const backend = join(root, "deploy", "homeassistant", "custom_components", "ultimate_3d_studio");
const frontend = join(root, "frontend");

function read(path) {
  return readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
}
function write(path, text) {
  writeFileSync(path, `\uFEFF${text}`, "utf8");
}
function exact(text, oldValue, newValue, label) {
  if (text.includes(newValue)) return text;
  if (!text.includes(oldValue)) throw new Error(`Quellmarker fehlt: ${label}`);
  return text.replace(oldValue, newValue);
}

// ---------------------------------------------------------------------------
// PrinterSnapshot carries normalized printer/HMS errors.
// ---------------------------------------------------------------------------
{
  const path = join(backend, "models.py");
  let text = read(path);
  text = exact(
    text,
    `    print_stage_active: bool = False\n    ams: dict[str, Any] = field(default_factory=dict)\n`,
    `    print_stage_active: bool = False\n    error_code: int | str | None = None\n    error_message: str | None = None\n    hms: list[dict[str, Any]] = field(default_factory=list)\n    ams: dict[str, Any] = field(default_factory=dict)\n`,
    "PrinterSnapshot-Fehlerfelder",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Normalize print_error / mc_print_error_code / HMS telemetry.
// ---------------------------------------------------------------------------
{
  const path = join(backend, "telemetry.py");
  let text = read(path);
  text = exact(
    text,
    `    @property\n    def nozzle_temperature(self) -> float | None:\n        return number(find(self.raw, ("nozzle_temper", "nozzle_temp")))\n`,
    `    @property\n    def error_code(self) -> int | str | None:\n        value = find(self.raw, (\n            "print_error",\n            "mc_print_error_code",\n            "print_error_code",\n            "error_code",\n            "err_code",\n        ))\n        if value in (None, "", 0, "0", "00000000"):\n            return None\n        numeric = number(value)\n        if numeric is not None and numeric.is_integer():\n            return int(numeric)\n        normalized = text(value, "")\n        return normalized or None\n\n    @property\n    def hms(self) -> list[dict[str, Any]]:\n        value = find(self.raw, ("hms", "hms_list", "health_messages"))\n        result: list[dict[str, Any]] = []\n        for item in records(value):\n            code = text(pick(item, "code", "attr", "hms_code", "id"), "")\n            message = text(pick(item, "message", "msg", "text", "description"), "")\n            level = text(pick(item, "level", "severity", "type"), "warning")\n            if code or message:\n                result.append({\n                    "code": code or None,\n                    "message": message or None,\n                    "level": level,\n                })\n        return result\n\n    @property\n    def error_message(self) -> str | None:\n        direct = text(find(self.raw, (\n            "print_error_message",\n            "error_message",\n            "error_msg",\n            "fail_reason",\n            "failure_reason",\n        )), "")\n        if direct and direct.casefold() not in {"ok", "success", "none", "0"}:\n            return direct\n        for item in self.hms:\n            message = text(item.get("message"), "")\n            if message:\n                return message\n        code = self.error_code\n        return f"Druckerfehler {code}" if code is not None else None\n\n    @property\n    def nozzle_temperature(self) -> float | None:\n        return number(find(self.raw, ("nozzle_temper", "nozzle_temp")))\n`,
    "Telemetrie-Fehlernormalisierung",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Populate snapshot errors from telemetry and last command/transport errors.
// ---------------------------------------------------------------------------
{
  const path = join(backend, "provider_bambu_lan.py");
  let text = read(path);
  text = exact(
    text,
    `                bed_temperature=self.telemetry.bed_temperature,\n                ams=self.telemetry.ams,\n`,
    `                bed_temperature=self.telemetry.bed_temperature,\n                error_code=(\n                    self.telemetry.error_code\n                    if self.telemetry.error_code is not None\n                    else (\n                        self.last_command_result.error_code\n                        if self.last_command_result is not None\n                        and not self.last_command_result.printer_accepted\n                        else None\n                    )\n                ),\n                error_message=(\n                    self.telemetry.error_message\n                    or self.last_error\n                    or (\n                        self.last_command_result.reason\n                        if self.last_command_result is not None\n                        and not self.last_command_result.printer_accepted\n                        else None\n                    )\n                ),\n                hms=self.telemetry.hms,\n                ams=self.telemetry.ams,\n`,
    "Provider-Fehlerfelder",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Preserve authoritative material plan in server job responses.
// ---------------------------------------------------------------------------
{
  const path = join(backend, "slicer_backend_router.py");
  let text = read(path);
  text = exact(
    text,
    `        "process_overrides": job.get("process_overrides") or {},\n        "requested_plate_index": 0,\n`,
    `        "process_overrides": job.get("process_overrides") or {},\n        "native_multimaterial": bool(job.get("native_multimaterial")),\n        "material_plan": job.get("material_plan") if isinstance(job.get("material_plan"), dict) else {},\n        "target_printer": job.get("target_printer") if isinstance(job.get("target_printer"), dict) else {},\n        "requested_profiles": job.get("requested_profiles") if isinstance(job.get("requested_profiles"), dict) else {},\n        "requested_plate_index": 0,\n`,
    "Serverjob-Materialplan",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Authoritative AMS mapping, no silent external-spool fallback.
// ---------------------------------------------------------------------------
{
  const path = join(backend, "direct_print_views.py");
  let text = read(path);
  text = exact(
    text,
    `def _printer_ready(printer: Any) -> tuple[bool, str]:\n    if printer is None:\n        return False, "Drucker wurde nicht gefunden."\n    if str(printer.connection_state).casefold() != "connected":\n        return False, "Drucker ist nicht verbunden."\n    state = str(printer.printer_state or "unknown").casefold()\n`,
    `def _printer_error(printer: Any) -> dict[str, Any]:\n    code = getattr(printer, "error_code", None)\n    message = str(getattr(printer, "error_message", None) or "").strip()\n    hms = getattr(printer, "hms", [])\n    if not isinstance(hms, list):\n        hms = []\n    active = bool(code is not None or message or hms)\n    if active and not message:\n        message = f"Druckerfehler {code}" if code is not None else "Der Drucker meldet einen Fehler."\n    return {\n        "active": active,\n        "code": code,\n        "message": message or None,\n        "hms": hms,\n    }\n\n\ndef _printer_ready(printer: Any) -> tuple[bool, str]:\n    if printer is None:\n        return False, "Drucker wurde nicht gefunden."\n    if str(printer.connection_state).casefold() != "connected":\n        return False, "Drucker ist nicht verbunden."\n    printer_error = _printer_error(printer)\n    if printer_error["active"]:\n        return False, str(printer_error["message"] or "Der Drucker meldet einen Fehler.")\n    state = str(printer.printer_state or "unknown").casefold()\n`,
    "Druckerfehler-Bereitschaft",
  );

  text = exact(
    text,
    `def _start_options(\n    payload: dict[str, Any],\n    printer: Any,\n) -> tuple[dict[str, Any] | None, web.Response | None]:\n`,
    `def _job_ams_options(\n    job: dict[str, Any],\n    printer: Any,\n) -> tuple[dict[str, Any] | None, web.Response | None]:\n    plan = job.get("material_plan") if isinstance(job.get("material_plan"), dict) else {}\n    filaments = plan.get("filaments") if isinstance(plan.get("filaments"), list) else []\n    native = bool(job.get("native_multimaterial"))\n    if not filaments:\n        if native:\n            return None, _error(\n                409,\n                "ams_mapping_missing",\n                "Der native Slicejob enthält keine gültige AMS-Zuordnung. Externe Spule wird nicht automatisch verwendet.",\n            )\n        return {"use_ams": False, "ams_mapping": []}, None\n\n    ordered = sorted(\n        (item for item in filaments if isinstance(item, dict)),\n        key=lambda item: int(item.get("extruder", 0) or 0),\n    )\n    mapping: list[int] = []\n    try:\n        for filament in ordered:\n            slot_value = filament.get("slot_index")\n            if slot_value is None:\n                raise ValueError\n            mapping.append(int(slot_value))\n    except (TypeError, ValueError):\n        return None, _error(\n            409,\n            "ams_mapping_invalid",\n            "Der Slicejob enthält eine ungültige AMS-Slotzuordnung. Externe Spule wird nicht verwendet.",\n        )\n\n    present_slots = {\n        int(slot["slot_index"])\n        for slot in _ams_slots(printer)\n        if slot.get("present")\n    }\n    if not mapping or any(value not in present_slots for value in mapping):\n        return None, _error(\n            409,\n            "ams_slot_unavailable",\n            "Ein im Slicejob verwendeter AMS/BMCU-Slot ist leer oder nicht verfügbar.",\n            required_slots=[value + 1 for value in mapping],\n            available_slots=[value + 1 for value in sorted(present_slots)],\n        )\n    return {\n        "use_ams": True,\n        "ams_mapping": mapping,\n        "display_slots": [value + 1 for value in mapping],\n    }, None\n\n\ndef _start_options(\n    payload: dict[str, Any],\n    printer: Any,\n) -> tuple[dict[str, Any] | None, web.Response | None]:\n`,
    "Job-AMS-Optionen",
  );

  text = exact(
    text,
    `                    "reason": reason or None,\n                    "ams": {\n`,
    `                    "reason": reason or None,\n                    "printer_error": _printer_error(printer),\n                    "ams": {\n`,
    "Status-Druckerfehler",
  );

  text = exact(
    text,
    `            job = await router.async_get_job(job_id)\n            if job.get("status") != "succeeded":\n`,
    `            job = await router.async_get_job(job_id)\n            if job.get("status") != "succeeded":\n`,
    "Prepare-Jobmarker",
  );
  text = exact(
    text,
    `            data, filename, worker_digest, _content_type = await router.async_artifact(job_id)\n`,
    `            required_start_options, required_options_error = _job_ams_options(job, printer)\n            if required_options_error is not None:\n                return required_options_error\n            assert required_start_options is not None\n            data, filename, worker_digest, _content_type = await router.async_artifact(job_id)\n`,
    "Prepare-AMS-Validierung",
  );
  text = exact(
    text,
    `                "final_confirmation_text": "DRUCKEN",\n                "print_started": False,\n`,
    `                "final_confirmation_text": "DRUCKEN",\n                "start_options": required_start_options,\n                "printer_error": _printer_error(printer),\n                "print_started": False,\n`,
    "Prepare-Startoptionen",
  );

  text = exact(
    text,
    `        options, options_error = _start_options(payload, printer)\n`,
    `        router = V6SlicerBackendRouter(hass)\n        try:\n            job = await router.async_get_job(job_id)\n        except (SlicerWorkerConfigurationError, SlicerWorkerError) as exc:\n            return _error(502, "slicer_worker_error", str(exc))\n        required_start_options, required_options_error = _job_ams_options(job, printer)\n        if required_options_error is not None:\n            return required_options_error\n        assert required_start_options is not None\n        if required_start_options["use_ams"]:\n            requested_mapping = payload.get("ams_mapping")\n            if requested_mapping not in (None, [], required_start_options["ams_mapping"]):\n                return _error(\n                    409,\n                    "ams_mapping_mismatch",\n                    "Die AMS-Zuordnung des Druckstarts stimmt nicht mit dem Slicejob überein.",\n                )\n            payload = {\n                **payload,\n                "use_ams": True,\n                "ams_mapping": required_start_options["ams_mapping"],\n            }\n        options, options_error = _start_options(payload, printer)\n`,
    "Start-AMS-Erzwingung",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Detailed status also exposes printer errors.
// ---------------------------------------------------------------------------
{
  const path = join(backend, "direct_print_slot_views.py");
  let text = read(path);
  text = exact(
    text,
    `def _printer_ready(printer: Any) -> tuple[bool, str]:\n    if str(printer.connection_state).casefold() != "connected":\n`,
    `def _printer_error(printer: Any) -> dict[str, Any]:\n    code = getattr(printer, "error_code", None)\n    message = str(getattr(printer, "error_message", None) or "").strip()\n    hms = getattr(printer, "hms", [])\n    if not isinstance(hms, list):\n        hms = []\n    active = bool(code is not None or message or hms)\n    if active and not message:\n        message = f"Druckerfehler {code}" if code is not None else "Der Drucker meldet einen Fehler."\n    return {"active": active, "code": code, "message": message or None, "hms": hms}\n\n\ndef _printer_ready(printer: Any) -> tuple[bool, str]:\n    if str(printer.connection_state).casefold() != "connected":\n`,
    "Detailstatus-Fehlerhelfer",
  );
  text = exact(
    text,
    `    state = str(printer.printer_state or "unknown").casefold()\n`,
    `    printer_error = _printer_error(printer)\n    if printer_error["active"]:\n        return False, str(printer_error["message"] or "Der Drucker meldet einen Fehler.")\n    state = str(printer.printer_state or "unknown").casefold()\n`,
    "Detailstatus-Fehlerbereit",
  );
  text = exact(
    text,
    `                    "reason": reason or None,\n                    "ams": {\n`,
    `                    "reason": reason or None,\n                    "printer_error": _printer_error(printer),\n                    "ams": {\n`,
    "Detailstatus-Fehlerfeld",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Frontend contracts and direct-print panel.
// ---------------------------------------------------------------------------
{
  const path = join(frontend, "direct-print-status-api.ts");
  let text = read(path);
  text = exact(
    text,
    `  reason: string | null;\n  ams: Readonly<{\n`,
    `  reason: string | null;\n  printer_error: Readonly<{\n    active: boolean;\n    code: number | string | null;\n    message: string | null;\n    hms: readonly Readonly<{ code: string | null; message: string | null; level: string }>[];\n  }>;\n  ams: Readonly<{\n`,
    "Frontend-Druckerfehlervertrag",
  );
  write(path, text);
}

{
  const path = join(frontend, "slicing-api.ts");
  let text = read(path);
  text = exact(
    text,
    `  requested_profiles?: Readonly<Record<string, unknown>>;\n  slice_result?: SliceResult | null;\n`,
    `  requested_profiles?: Readonly<Record<string, unknown>>;\n  native_multimaterial?: boolean;\n  material_plan?: Readonly<{\n    filaments?: readonly SliceProjectFilament[];\n    assignments?: Readonly<Record<string, number>>;\n    purge_tower?: SlicePurgeTower;\n  }>;\n  target_printer?: Readonly<Record<string, unknown>>;\n  slice_result?: SliceResult | null;\n`,
    "SliceJob-Materialplan",
  );
  text = exact(
    text,
    `  final_confirmation_text: "DRUCKEN";\n  ams: Readonly<{\n`,
    `  final_confirmation_text: "DRUCKEN";\n  start_options: Readonly<{\n    use_ams: boolean;\n    ams_mapping: number[];\n    display_slots?: number[];\n  }>;\n  printer_error?: Readonly<{\n    active: boolean;\n    code: number | string | null;\n    message: string | null;\n  }>;\n  ams: Readonly<{\n`,
    "Prepared-Startoptionen",
  );
  write(path, text);
}

{
  const path = join(frontend, "direct-print-panel-next.ts");
  let text = read(path);
  text = exact(
    text,
    `  #lastRefreshAt = 0;\n`,
    `  #lastRefreshAt = 0;\n  #pollTimer: number | null = null;\n`,
    "Druckerstatus-Polltimer",
  );
  text = exact(
    text,
    `    if (this.#job && (!this.#status || Date.now() - this.#lastRefreshAt > 60_000)) {\n      void this.#refresh();\n    }\n  }\n`,
    `    if (this.#job && (!this.#status || Date.now() - this.#lastRefreshAt > 60_000)) {\n      void this.#refresh();\n    }\n    if (this.#pollTimer === null) {\n      this.#pollTimer = window.setInterval(() => void this.#pollStatus(), 3000);\n    }\n  }\n\n  disconnectedCallback(): void {\n    if (this.#pollTimer !== null) window.clearInterval(this.#pollTimer);\n    this.#pollTimer = null;\n  }\n`,
    "Druckerstatus-Polling",
  );
  text = exact(
    text,
    `  #startOptions(): DirectPrintStartOptions {\n    return {\n      use_ams: false,\n      ams_mapping: [],\n`,
    `  #startOptions(): DirectPrintStartOptions {\n    const required = this.#prepared?.start_options;\n    return {\n      use_ams: Boolean(required?.use_ams),\n      ams_mapping: [...(required?.ams_mapping ?? [])],\n`,
    "Frontend-AMS-Startoptionen",
  );
  text = exact(
    text,
    `  async #refresh(): Promise<void> {\n`,
    `  async #pollStatus(): Promise<void> {\n    if (!this.#job || this.#busy) return;\n    try {\n      this.#status = await fetchDetailedDirectPrintStatus();\n      this.#lastRefreshAt = Date.now();\n      this.#render();\n    } catch (_error) {\n      // Background polling must never replace an actionable foreground error.\n    }\n  }\n\n  async #refresh(): Promise<void> {\n`,
    "Druckerstatus-Hintergrundpoll",
  );
  text = exact(
    text,
    `    const canPrepare = this.#enabled && job?.status === "succeeded" && printer?.ready && !this.#busy && !this.#prepared;\n    const canStart = Boolean(this.#prepared && printer?.ready && !this.#busy);\n`,
    `    const printerError = printer?.printer_error?.active ? printer.printer_error : null;\n    const canPrepare = this.#enabled && job?.status === "succeeded" && printer?.ready && !printerError && !this.#busy && !this.#prepared;\n    const canStart = Boolean(this.#prepared && printer?.ready && !printerError && !this.#busy);\n`,
    "Fehler-sperrt-Druckstart",
  );
  text = exact(
    text,
    `    const preparedCard = this.#prepared\n      ? \`<div class="dp-success dp-result"><strong>Bereit zum Drucken</strong><span>\${esc(this.#prepared.remote_filename)} · \${valueLabel(this.#prepared.size_bytes, " Bytes")}</span><span class="dp-mono">SHA-256: \${esc(this.#prepared.sha256)}</span></div>\`\n      : "";\n`,
    `    const preparedCard = this.#prepared\n      ? \`<div class="dp-success dp-result"><strong>Bereit zum Drucken</strong><span>\${esc(this.#prepared.remote_filename)} · \${valueLabel(this.#prepared.size_bytes, " Bytes")}</span><span>\${this.#prepared.start_options.use_ams ? \`AMS aktiv · Slot \${(this.#prepared.start_options.display_slots ?? this.#prepared.start_options.ams_mapping.map((slot) => slot + 1)).join(" → ")}\` : "Externe Spule"}</span><span class="dp-mono">SHA-256: \${esc(this.#prepared.sha256)}</span></div>\`\n      : "";\n\n    const printerErrorCard = printerError\n      ? \`<div class="dp-error dp-result"><strong>Druckerfehler</strong><span>\${esc(printerError.message || "Der Drucker meldet einen Fehler.")}\${printerError.code !== null ? \` · Code \${esc(printerError.code)}\` : ""}</span></div>\`\n      : "";\n`,
    "Druckerfehlerkarte",
  );
  text = exact(
    text,
    `        \${preparedCard}\n        <section class="dp-section">\n`,
    `        \${printerErrorCard}\n        \${preparedCard}\n        <section class="dp-section">\n`,
    "Druckerfehler-im-Panel",
  );
  write(path, text);
}

console.log("AMS-Druckstart und Druckerfehleranzeige wurden in die kanonischen Quellen übernommen.");
