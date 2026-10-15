import { transferMatchesAttempt } from "./transfer-attempt.js";
import { DIRECT_PRINT_PANEL_STYLES } from "./direct-print-panel-styles.js";
import {
  dispatchDirectPrintTransfer,
  type DirectPrintTransferDetail,
} from "./direct-print-transfer-events.js";
import {
  fetchDetailedDirectPrintStatus,
  type DetailedDirectPrintPrinter,
  type DetailedDirectPrintStatus,
} from "./direct-print-status-api.js";
import {
  discardPreparedPrint,
  fetchDirectPrintTransferStatus,
  fetchDirectPrintTransferBaseline,
  prepareDirectPrint,
  startDirectPrint,
  type DirectPrintResult,
  type DirectPrintStartOptions,
  type DirectPrintTransferStatus,
  type PreparedDirectPrint,
  type SliceJob,
} from "./slicing-api.js";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function valueLabel(value: number | null | undefined, suffix: string): string {
  return Number.isFinite(value) ? `${Number(value).toFixed(0)}${suffix}` : "–";
}

function lanConnectionLabel(printer: DetailedDirectPrintPrinter): string {
  return String(printer.connection_state || "").toLowerCase() === "connected" ? "LAN verbunden" : "LAN getrennt";
}

function printerReadyTitle(printer: DetailedDirectPrintPrinter | null): string {
  if (!printer) return "Kein Drucker ausgewählt";
  if (printer.ready) return "LAN-Direktdruck bereit";
  if (String(printer.connection_state || "").toLowerCase() !== "connected") return "LAN-Direktdruck nicht erreichbar";
  return "Drucker nicht bereit";
}

function printerReadyDetail(printer: DetailedDirectPrintPrinter | null): string {
  if (!printer) return "Kein Drucker ausgewählt";
  if (String(printer.connection_state || "").toLowerCase() !== "connected") {
    return "Lokaler MQTT/FTPS-Direktdruckkanal ist getrennt. Cloud/App-Verbindung kann trotzdem online sein.";
  }
  return printer.reason || printer.printer_state || "Druckerstatus wird ermittelt";
}

type AmsPlanFilament = Readonly<{
  extruder?: number;
  slot_index?: number;
  display_slot?: number;
  name?: string;
  source?: string;
}>;

type AuthoritativeAmsPlan = Readonly<{
  source?: string;
  target_printer_id?: string;
  filaments?: readonly AmsPlanFilament[];
}>;

type SliceJobWithAmsPlan = SliceJob & Readonly<{
  ams_material_plan?: AuthoritativeAmsPlan;
  material_source_plan?: AuthoritativeAmsPlan;
  target_printer?: Readonly<{ printer_id?: string }>;
}>;

type MaterialSourceSelection = Readonly<{
  useAms: boolean;
  mapping: number[];
  labels: string[];
  source: "ams" | "external_spool";
}>; 

export class Ultimate3DDirectPrintPanelNext extends HTMLElement {
  #job: SliceJob | null = null;
  #enabled = false;
  #status: DetailedDirectPrintStatus | null = null;
  #printerId = "";
  #prepared: PreparedDirectPrint | null = null;
  #result: DirectPrintResult | null = null;
  #busy = "";
  #error = "";
  #message = "";
  #bedLeveling = true;
  #flowCalibration = true;
  #vibrationCalibration = true;
  #timelapse = false;
  #lastRefreshAt = 0;
  #transferTimer: number | null = null;
  #transferPolling = false;
  #transferFinished = false;
  #transferTraceId = "";
  #previousTransferStartedAt = "";
  #lastTransfer: DirectPrintTransferDetail | null = null;

  set job(value: SliceJob | null) {
    const changed = value?.id !== this.#job?.id;
    this.#job = value;
    if (changed) {
      this.#prepared = null;
      this.#result = null;
      this.#error = "";
      this.#message = "";
    }
    if (!this.isConnected) return;
    this.#render();
    if (changed && value) void this.#refresh();
  }

  get job(): SliceJob | null { return this.#job; }
  set enabled(value: boolean) { this.#enabled = Boolean(value); if (this.isConnected) this.#render(); }
  get enabled(): boolean { return this.#enabled; }

  connectedCallback(): void {
    this.#render();
    if (this.#job && (!this.#status || Date.now() - this.#lastRefreshAt > 60_000)) void this.#refresh();
  }

  disconnectedCallback(): void {
    this.#stopTransferPolling();
  }

  #printer(): DetailedDirectPrintPrinter | null {
    return this.#status?.items.find((item) => item.printer_id === this.#printerId) ?? null;
  }

  #materialSelection(): MaterialSourceSelection {
    const job = this.#job as SliceJobWithAmsPlan | null;
    const printer = this.#printer();
    if (!job) throw new Error("Kein gesliceter Auftrag verfügbar.");
    if (!printer) throw new Error("Kein Ziel-Drucker ausgewählt.");
    const plan = job.material_source_plan ?? job.ams_material_plan;
    if (!plan || !["authoritative_ams_runtime", "authoritative_external_spool_runtime"].includes(String(plan.source))) {
      throw new Error("Der Slicerauftrag enthält keinen autoritativen Materialquellenplan.");
    }
    const targetPrinterId = String(plan.target_printer_id || job.target_printer?.printer_id || "").trim();
    if (targetPrinterId && targetPrinterId !== printer.printer_id) {
      throw new Error("Der Materialquellenplan gehört zu einem anderen Drucker. Bitte mit dem ausgewählten Drucker neu slicen.");
    }

    const filaments = Array.isArray(plan.filaments) ? [...plan.filaments] : [];
    if (!filaments.length) throw new Error("Der Materialquellenplan enthält kein Filament.");
    filaments.sort((left, right) => Number(left.extruder) - Number(right.extruder));

    if (plan.source === "authoritative_external_spool_runtime") {
      const filament = filaments[0];
      if (filaments.length !== 1 || Number(filament?.extruder) !== 1 || filament?.source !== "external_spool") {
        throw new Error("Die externe Spule benötigt genau einen gültigen Materialkanal.");
      }
      const name = String(filament.name || "Externes Filament").replace(/^Externe Spule:\s*/i, "");
      return { useAms: false, mapping: [], labels: [`Externe Spule: ${name}`], source: "external_spool" };
    }
    if (!printer.ams.available) throw new Error("Am Ziel-Drucker wurde kein AMS beziehungsweise AMS Lite erkannt.");

    const presentSlots = new Set(
      printer.ams.slots.filter((slot) => slot.present).map((slot) => Number(slot.slot_index)),
    );
    const mapping: number[] = [];
    const labels: string[] = [];
    const seenExtruders = new Set<number>();
    for (let index = 0; index < filaments.length; index += 1) {
      const filament = filaments[index]!;
      const extruder = Number(filament.extruder);
      const slotIndex = Number(filament.slot_index);
      if (!Number.isInteger(extruder) || extruder !== index + 1 || seenExtruders.has(extruder)) {
        throw new Error("Der AMS-Materialplan enthält keine lückenlose Extruderreihenfolge.");
      }
      if (!Number.isInteger(slotIndex) || slotIndex < 0 || slotIndex > 255) {
        throw new Error("Der AMS-Materialplan enthält einen ungültigen Slot.");
      }
      if (!presentSlots.has(slotIndex)) {
        throw new Error(`Der vorgesehene AMS-Slot ${slotIndex + 1} ist leer oder nicht verfügbar.`);
      }
      seenExtruders.add(extruder);
      mapping.push(slotIndex);
      labels.push(`AMS ${Number(filament.display_slot) || slotIndex + 1}: ${String(filament.name || `Filament ${extruder}`)}`);
    }
    if (mapping.length > 4) throw new Error("Mehr als vier AMS-Materialkanäle werden für diesen Drucker nicht freigegeben.");
    return { useAms: true, mapping, labels, source: "ams" };
  }

  #startOptions(selection: MaterialSourceSelection): DirectPrintStartOptions {
    return {
      use_ams: selection.useAms,
      ams_mapping: [...selection.mapping],
      bed_leveling: this.#bedLeveling,
      flow_cali: this.#flowCalibration,
      vibration_cali: this.#vibrationCalibration,
      timelapse: this.#timelapse,
    };
  }

  #selectionOrNull(): MaterialSourceSelection | null {
    try { return this.#materialSelection(); } catch { return null; }
  }

  #selectionError(): string {
    try { this.#materialSelection(); return ""; } catch (error) { return error instanceof Error ? error.message : String(error); }
  }

  async #refresh(): Promise<void> {
    if (this.#busy || !this.#job) return;
    this.#busy = "refresh";
    this.#render();
    try {
      this.#status = await fetchDetailedDirectPrintStatus();
      this.#lastRefreshAt = Date.now();
      if (!this.#status.items.some((item) => item.printer_id === this.#printerId)) {
        this.#printerId = this.#status.items.find((item) => item.ready)?.printer_id
          ?? this.#status.items[0]?.printer_id
          ?? "";
      }
      this.#error = "";
    } catch (error) {
      this.#status = null;
      this.#error = error instanceof Error ? error.message : String(error);
    } finally {
      this.#busy = "";
      this.#render();
    }
  }

  #stopTransferPolling(): void {
    if (this.#transferTimer !== null) window.clearInterval(this.#transferTimer);
    this.#transferTimer = null;
  }

  #dispatchTransfer(detail: DirectPrintTransferDetail): void {
    this.#lastTransfer = detail;
    dispatchDirectPrintTransfer(detail);
  }

  #beginTransfer(job: SliceJob, printer: DetailedDirectPrintPrinter): void {
    this.#stopTransferPolling();
    this.#transferFinished = false;
    this.#transferTraceId = `${job.id}:${printer.printer_id}:${Date.now()}`;
    const totalBytes = Math.max(0, Number(job.output_size_bytes) || 0);
    this.#dispatchTransfer({
      traceId: this.#transferTraceId,
      jobId: job.id,
      printerId: printer.printer_id,
      printerName: printer.name,
      fileName: job.output_filename || job.output_file || job.model_file || "Druckauftrag.gcode.3mf",
      stage: "preparing",
      message: "Druckdatei wird für die sichere Bambu-LAN-Übertragung vorbereitet",
      active: true,
      status: "running",
      progress: 0,
      loadedBytes: 0,
      totalBytes,
      rateBytesPerSecond: 0,
      at: new Date().toISOString(),
    });

  }

  #transferDetail(status: DirectPrintTransferStatus): DirectPrintTransferDetail {
    const totalBytes = Math.max(0, Number(status.total_bytes) || 0);
    const loadedBytes = Math.max(0, Math.min(totalBytes || Number(status.loaded_bytes) || 0, Number(status.loaded_bytes) || 0));
    return {
      traceId: this.#transferTraceId,
      jobId: status.job_id,
      printerId: status.printer_id,
      printerName: status.printer_name,
      fileName: status.filename,
      stage: status.stage,
      message: status.error || status.stage_label,
      active: Boolean(status.active),
      status: status.status,
      progress: Math.max(0, Math.min(100, Number(status.progress) || 0)),
      loadedBytes,
      totalBytes,
      rateBytesPerSecond: Math.max(0, Number(status.rate_bytes_per_second) || 0),
      etaSeconds: status.eta_seconds !== null && status.eta_seconds !== undefined && Number(status.eta_seconds) >= 0
        ? Number(status.eta_seconds)
        : undefined,
      elapsedSeconds: status.elapsed_seconds !== null && status.elapsed_seconds !== undefined && Number(status.elapsed_seconds) >= 0
        ? Number(status.elapsed_seconds)
        : undefined,
      at: status.updated_at || new Date().toISOString(),
    };
  }

  async #pollTransfer(): Promise<void> {
    const job = this.#job;
    const printer = this.#printer();
    if (!this.#transferTraceId || this.#transferFinished || !job || !printer || this.#transferPolling) return;
    const requestedTrace = this.#transferTraceId;
    this.#transferPolling = true;
    try {
      const status = await fetchDirectPrintTransferStatus(job.id, printer.printer_id);
      if (this.#transferFinished || status.job_id !== job.id || status.printer_id !== printer.printer_id
        || !transferMatchesAttempt(status.started_at, this.#previousTransferStartedAt, requestedTrace, this.#transferTraceId)) return;
      this.#dispatchTransfer(this.#transferDetail(status));
    } catch {
      // Der Status kann beim ersten Poll noch nicht angelegt sein.
    } finally {
      this.#transferPolling = false;
    }
  }

  #finishTransfer(prepared: PreparedDirectPrint): void {
    this.#transferFinished = true;
    const previous = this.#lastTransfer;
    this.#dispatchTransfer({
      traceId: this.#transferTraceId,
      jobId: prepared.job_id,
      printerId: prepared.printer_id,
      printerName: prepared.printer_name,
      fileName: prepared.remote_filename,
      stage: "completed",
      message: "Druckjob vollständig übertragen und per Dateigröße sowie SHA-256 verifiziert",
      active: false,
      status: "success",
      progress: 100,
      loadedBytes: prepared.size_bytes,
      totalBytes: prepared.size_bytes,
      rateBytesPerSecond: previous?.rateBytesPerSecond || 0,
      etaSeconds: 0,
      elapsedSeconds: previous?.elapsedSeconds,
      at: new Date().toISOString(),
    });
  }

  #failTransfer(message: string): void {
    this.#transferFinished = true;
    const previous = this.#lastTransfer;
    if (!this.#transferTraceId || !previous) return;
    this.#dispatchTransfer({
      ...previous,
      stage: "error",
      message,
      active: false,
      status: "error",
      etaSeconds: undefined,
      at: new Date().toISOString(),
    });
  }

  async #prepare(): Promise<void> {
    const job = this.#job;
    const printer = this.#printer();
    if (!this.#enabled || !job || job.status !== "succeeded" || !printer?.ready || this.#busy) return;
    let selection: MaterialSourceSelection;
    try { selection = this.#materialSelection(); } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#render();
      return;
    }
    this.#busy = "prepare";
    this.#error = "";
    this.#message = "Druckjob wird übertragen und verifiziert …";
    this.#beginTransfer(job, printer);
    this.#prepared = null;
    this.#result = null;
    this.#render();
    try {
      this.#previousTransferStartedAt = await fetchDirectPrintTransferBaseline(job.id, printer.printer_id);
      this.#transferTimer = window.setInterval(() => void this.#pollTransfer(), 350);
      const prepared = await prepareDirectPrint(job.id, printer.printer_id);
      if (job.output_sha256 && prepared.sha256.toLowerCase() !== job.output_sha256.toLowerCase()) {
        await discardPreparedPrint(prepared);
        throw new Error("Die SHA-256-Prüfsumme des Drucker-Uploads stimmt nicht mit dem Slicer-Ergebnis überein.");
      }
      await this.#pollTransfer();
      this.#finishTransfer(prepared);
      this.#prepared = prepared;
      this.#message = `Druckjob vollständig bereit · ${selection.labels.join(" · ")}`;
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#message = "";
      this.#failTransfer(this.#error);
    } finally {
      this.#stopTransferPolling();
      this.#busy = "";
      this.#render();
    }
  }

  async #start(): Promise<void> {
    const prepared = this.#prepared;
    const printer = this.#printer();
    if (!prepared || !printer?.ready || this.#busy) return;
    let selection: MaterialSourceSelection;
    try { selection = this.#materialSelection(); } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#render();
      return;
    }
    const confirmation = prepared.final_confirmation_text;

    this.#busy = "start";
    this.#error = "";
    this.#message = `Verifizierter Druckjob wird über ${selection.source === "ams" ? "AMS Lite" : "die externe Spule"} gestartet …`;
    this.#render();
    try {
      this.#result = await startDirectPrint(
        prepared,
        this.#startOptions(selection),
        prepared.final_confirmation_text,
      );
      this.#message = selection.useAms
        ? `Druckauftrag angenommen · AMS-Mapping [${selection.mapping.join(", ")}] · Sequenz ${this.#result.sequence_id}`
        : `Druckauftrag angenommen · Externe Spule · Sequenz ${this.#result.sequence_id}`;
      this.#prepared = null;
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#message = "";
    } finally {
      this.#busy = "";
      this.#render();
    }
    if (this.#result) void this.#refresh();
  }

  async #discard(): Promise<void> {
    const prepared = this.#prepared;
    if (!prepared || this.#busy) return;
    if (!window.confirm(`Vorbereiteten Druckjob verwerfen und vom Drucker löschen?\n\n${prepared.remote_filename}`)) return;
    this.#busy = "discard";
    this.#error = "";
    this.#render();
    try {
      await discardPreparedPrint(prepared);
      this.#prepared = null;
      this.#message = "Vorbereiteter Druckjob wurde verworfen.";
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    } finally {
      this.#busy = "";
      this.#render();
    }
  }

  #option(id: string, title: string, description: string, checked: boolean, disabled = false): string {
    return `<label class="dp-check"><input id="${id}" type="checkbox" ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}><span class="dp-check-copy"><strong>${esc(title)}</strong><span>${esc(description)}</span></span></label>`;
  }

  #render(): void {
    if (!this.isConnected) return;
    const job = this.#job;
    const printers = this.#status?.items ?? [];
    const printer = this.#printer();
    const selection = this.#selectionOrNull();
    const selectionError = job && this.#status ? this.#selectionError() : "";
    const canPrepare = Boolean(this.#enabled && job?.status === "succeeded" && printer?.ready && selection && !this.#busy && !this.#prepared);
    const canStart = Boolean(this.#prepared && printer?.ready && selection && !this.#busy);
    const busyLabel = this.#busy === "prepare"
      ? "Druckjob wird übertragen und vollständig geprüft …"
      : this.#busy === "start"
        ? "Druckauftrag wird gestartet …"
        : this.#busy === "discard"
          ? "Vorbereiteter Druckjob wird verworfen …"
          : "Status wird aktualisiert …";

    const preparedCard = this.#prepared
      ? `<div class="dp-success dp-result"><strong>Bereit zum Drucken</strong><span>${esc(this.#prepared.remote_filename)} · ${valueLabel(this.#prepared.size_bytes, " Bytes")}</span><span>${esc(selection?.labels.join(" · ") || "AMS-Zuordnung wird geprüft")}</span><span class="dp-mono">SHA-256: ${esc(this.#prepared.sha256)}</span></div>`
      : "";
    const materialCard = selection
      ? `<div class="dp-success dp-result"><strong>Autoritative Materialquelle · ${selection.useAms ? "AMS Lite" : "Externe Spule"}</strong><span>${esc(selection.labels.join(" · "))}</span><span class="dp-mono">use_ams=${selection.useAms ? "true" : "false"}${selection.useAms ? ` · ams_mapping=[${esc(selection.mapping.join(", "))}]` : " · kein AMS-Mapping"}</span></div>`
      : selectionError ? `<div class="dp-error">${esc(selectionError)}</div>` : "";

    const content = !job || job.status !== "succeeded"
      ? '<div class="dp-empty">Druckjob-Vorbereitung wird nach einem erfolgreichen G-Code-Slice verfügbar.</div>'
      : `<div class="dp-printer-grid">
          <label class="dp-field"><span>Drucker auswählen</span><select class="dp-select" id="dp-printer" ${this.#prepared ? "disabled" : ""}>${printers.map((item) => `<option value="${esc(item.printer_id)}" ${item.printer_id === this.#printerId ? "selected" : ""}>${esc(item.name)} · ${esc(lanConnectionLabel(item))} · Status ${esc(item.printer_state)}${item.ready ? "" : " · nicht druckbereit"}</option>`).join("") || '<option value="">Kein Drucker verfügbar</option>'}</select></label>
          <div class="dp-ready-card ${printer?.ready ? "" : "blocked"}"><span class="dp-ready-dot"></span><span class="dp-ready-copy"><strong>${esc(printerReadyTitle(printer))}</strong><span>${esc(printerReadyDetail(printer))}</span></span></div>
        </div>
        ${materialCard}${preparedCard}
        <section class="dp-section"><div class="dp-section-head"><h4>Fünf Vorabprüfungen</h4><span>Materialquelle und Filament stammen unveränderlich aus dem geslicten Projekt</span></div><div class="dp-options">
          ${this.#option("dp-integrity", "Druckdatei verifizieren", "SHA-256-Abgleich zwischen Slicer-Artefakt und Drucker-Upload", true, true)}
          ${this.#option("dp-bed", "Druckbett nivellieren", "Automatische Bettvermessung vor dem Druck", this.#bedLeveling)}
          ${this.#option("dp-flow", "Flow-Kalibrierung", "Materialflusskalibrierung vor dem Druck", this.#flowCalibration)}
          ${this.#option("dp-vibration", "Vibrationskalibrierung", "Resonanzprüfung vor dem Druck", this.#vibrationCalibration)}
          ${this.#option("dp-timelapse", "Timelapse", "Zeitrafferaufnahme für diesen Auftrag", this.#timelapse)}
        </div></section>
        <div class="dp-actions">
          <span class="dp-action-note">Ohne gültigen autoritativen Materialquellenplan wird der Start blockiert. Zwischen AMS Lite und externer Spule gibt es keinen automatischen Fallback.</span>
          ${this.#prepared ? `<button class="dp-button" id="dp-discard" type="button" ${this.#busy ? "disabled" : ""}>Verwerfen</button>` : ""}
          <button class="dp-button" id="dp-prepare" type="button" ${canPrepare ? "" : "disabled"}>Druck vorbereiten</button>
          <button class="dp-button dp-primary" id="dp-start" type="button" ${canStart ? "" : "disabled"}>Drucken</button>
        </div>`;

    this.innerHTML = `<style>${DIRECT_PRINT_PANEL_STYLES}</style><div class="dp-root"><section class="dp-panel">
      <header class="dp-head"><div class="dp-title"><span class="dp-kicker">Bambu LAN · Zweistufiger Druck</span><h3>Druckjob vollständig prüfen und starten</h3><p>AMS Lite oder externe Spule sowie das Filament stammen aus dem Slicerauftrag. Hier werden nur die Druckerprüfungen festgelegt.</p></div><div class="dp-head-actions"><span class="dp-mode">Zweischritt-Modus aktiv</span><button class="dp-button" id="dp-refresh" type="button" ${this.#busy ? "disabled" : ""}>Aktualisieren</button></div></header>
      ${this.#busy ? '<div class="dp-progress"><span></span></div>' : ""}
      <div class="dp-body">${this.#busy ? `<div class="dp-success">${esc(busyLabel)}</div>` : ""}${content}${this.#message ? `<div class="dp-success">${esc(this.#message)}</div>` : ""}${this.#error ? `<div class="dp-error">${esc(this.#error)}</div>` : ""}${this.#result ? `<div class="dp-success dp-result"><strong>Druckauftrag angenommen</strong><span>Sequenz ${esc(this.#result.sequence_id)} · ${esc(this.#result.remote_filename)}</span></div>` : ""}</div>
    </section></div>`;
    this.#bind();
  }

  #bind(): void {
    this.querySelector<HTMLButtonElement>("#dp-refresh")?.addEventListener("click", () => void this.#refresh());
    this.querySelector<HTMLButtonElement>("#dp-prepare")?.addEventListener("click", () => void this.#prepare());
    this.querySelector<HTMLButtonElement>("#dp-start")?.addEventListener("click", () => void this.#start());
    this.querySelector<HTMLButtonElement>("#dp-discard")?.addEventListener("click", () => void this.#discard());
    this.querySelector<HTMLSelectElement>("#dp-printer")?.addEventListener("change", (event) => {
      this.#printerId = (event.currentTarget as HTMLSelectElement).value;
      this.#prepared = null;
      this.#render();
    });
    this.querySelector<HTMLInputElement>("#dp-bed")?.addEventListener("change", (event) => { this.#bedLeveling = (event.currentTarget as HTMLInputElement).checked; });
    this.querySelector<HTMLInputElement>("#dp-flow")?.addEventListener("change", (event) => { this.#flowCalibration = (event.currentTarget as HTMLInputElement).checked; });
    this.querySelector<HTMLInputElement>("#dp-vibration")?.addEventListener("change", (event) => { this.#vibrationCalibration = (event.currentTarget as HTMLInputElement).checked; });
    this.querySelector<HTMLInputElement>("#dp-timelapse")?.addEventListener("change", (event) => { this.#timelapse = (event.currentTarget as HTMLInputElement).checked; });
  }
}

if (!customElements.get("ultimate-3d-direct-print-panel")) {
  customElements.define("ultimate-3d-direct-print-panel", Ultimate3DDirectPrintPanelNext);
}
