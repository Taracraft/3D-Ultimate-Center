import { writeFrontendAudit } from "./ha-api-transport.js";
type HassLike = Readonly<{
  callWS: <T = unknown>(message: Readonly<Record<string, unknown>>) => Promise<T>;
}>;
type DataRecord = Readonly<Record<string, unknown>>;
type SlicingOverview = Readonly<{
  info?: DataRecord;
  status?: DataRecord;
  printers?: Readonly<{ printers?: DataRecord[] }> | DataRecord[];
  files?: Readonly<{ files?: DataRecord[] }> | DataRecord[];
  jobs?: Readonly<{ jobs?: DataRecord[] }> | DataRecord[];
  diagnostics?: DataRecord;
  engines?: DataRecord;
}>;
type JobFilter = "all" | "active" | "failed" | "completed";

function record(value: unknown): DataRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as DataRecord : {};
}
function records(value: unknown): DataRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is DataRecord => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    : [];
}
function nestedRecords(value: unknown, key: string): DataRecord[] {
  if (Array.isArray(value)) return records(value);
  return records(record(value)[key]);
}
function text(value: unknown, fallback = "–"): string {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}
function numberValue(value: unknown): number | null {
  const parsed = Number(value);
  return value === null || value === undefined || value === "" || !Number.isFinite(parsed) ? null : parsed;
}
function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}
function bytes(value: unknown): string {
  const size = numberValue(value);
  if (size === null) return "–";
  if (size >= 1024 * 1024 * 1024) return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${size.toFixed(0)} B`;
}
function dateTime(value: unknown): string {
  const numeric = numberValue(value);
  const date = numeric !== null ? new Date(numeric * 1000) : new Date(String(value || ""));
  return Number.isNaN(date.getTime()) ? "–" : date.toLocaleString("de-DE");
}
function metric(label: string, value: unknown, detail = ""): string {
  return `<article class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong>${detail ? `<span>${esc(detail)}</span>` : ""}</article>`;
}
function stateClass(value: unknown): string {
  const state = String(value || "").toLowerCase();
  if (["completed", "succeeded", "ok", "ready"].includes(state)) return "ok";
  if (["failed", "error", "cancelled", "interrupted"].includes(state)) return "bad";
  if (["queued", "slicing", "running", "cancelling"].includes(state)) return "warn";
  return "";
}

export class Ultimate3DSlicingServerWorkspace extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #hass: HassLike | null = null;
  #mounted = false;
  #server: SlicingOverview | null = null;
  #loading = false;
  #error = "";
  #search = "";
  #jobFilter: JobFilter = "all";
  #selectedModel = "";
  #timer: number | null = null;
  #newJobOpen = false;
  #diagnosticsOpen = false;
  #uploadFile: File | null = null;
  #draftPrinter = "";
  #draftEngine = "auto";
  #draftFormat = "gcode";
  #draftJobId = "";
  #notice = "";
  #noticeError = false;
  #lastAuditFingerprint = "";

  set hass(value: HassLike | null) {
    this.#hass = value;
    if (value && this.#mounted && !this.#server) void this.#load(true);
  }

  connectedCallback(): void {
    if (!this.#mounted) this.#mount();
    if (this.#timer === null) this.#timer = globalThis.setInterval(() => void this.#load(false), 10_000);
    if (this.#hass && !this.#server) void this.#load(true);
  }

  disconnectedCallback(): void {
    if (this.#timer !== null) globalThis.clearInterval(this.#timer);
    this.#timer = null;
  }

  #mount(): void {
    this.#root.innerHTML = `<style>
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff;font:13px/1.4 Segoe UI,sans-serif}*{box-sizing:border-box}.page{padding:18px}.head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.head h1{margin:0}.head p{margin:4px 0 0;color:#91a5bb}.grid{display:grid;grid-template-columns:minmax(330px,.85fr) minmax(0,1.15fr);gap:14px;margin-top:14px}.panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}.panel h2{margin:0;padding:12px 14px;border-bottom:1px solid #26384f;font-size:15px}.body{padding:13px}.wide{grid-column:1/-1}.button{padding:8px 11px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;font-weight:700;cursor:pointer}.button.primary{border-color:#45caff;background:#155b7c}.button:disabled{opacity:.45;cursor:default}.toolbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:12px}.toolbar input,.toolbar select,.form input,.form select{min-height:34px;padding:7px 9px;border:1px solid #31506e;border-radius:7px;background:#0a1722;color:#eef5ff}.toolbar input{min-width:230px;flex:1}.toolbar .button{margin-left:auto}.server-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.metric{min-width:0;padding:9px;border:1px solid #26384f;border-radius:8px;background:#0c1622}.metric small,.metric strong,.metric span{display:block;overflow:hidden;text-overflow:ellipsis}.metric small{color:#8298ae;font-size:10px;text-transform:uppercase}.metric strong{margin-top:3px}.metric span{margin-top:2px;color:#8198ad;font-size:10px}.models{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:9px}.model{overflow:hidden;border:1px solid #26384f;border-radius:9px;background:#0c1622}.model.selected{border-color:#45caff}.preview{display:grid;place-items:center;height:72px;background:radial-gradient(circle at 50% 35%,#35536b,#162635 70%);color:#b9def8;font-size:28px}.model-body{display:grid;gap:5px;padding:9px}.model-name{font-weight:700;overflow-wrap:anywhere}.model-meta{color:#8298ae;font-size:10px}.jobs{overflow:auto;max-height:560px}table{width:100%;border-collapse:collapse}th,td{padding:8px 7px;border-bottom:1px solid #26384f;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#101925;color:#8298ae}.state{font-weight:800}.state.ok{color:#55d98b}.state.warn{color:#ffd166}.state.bad{color:#ff7d88}.mono{font-family:Consolas,monospace;font-size:10px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.form label{display:grid;gap:4px;color:#9bb0c3}.form-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:10px}.raw{max-height:340px;overflow:auto;padding:10px;border:1px solid #26384f;border-radius:8px;background:#07111b;color:#b8c9d8;font:10px/1.4 Consolas,monospace;white-space:pre-wrap}.notice{margin-top:10px;padding:9px;border:1px solid #355773;border-radius:8px;background:#10243a;color:#b9d6ea}.error{margin-top:10px;padding:9px;border:1px solid #8f3f4b;border-radius:8px;background:#351b21;color:#ffd7dc}.empty{padding:18px;color:#8298ae;text-align:center}details>summary{cursor:pointer;font-weight:700}.selected-file{margin-top:7px;color:#9bb0c3;font-size:11px}@media(max-width:1100px){.server-summary{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:850px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}.form-grid{grid-template-columns:1fr 1fr}}@media(max-width:560px){.page{padding:10px}.server-summary,.form-grid{grid-template-columns:1fr}.toolbar input{min-width:100%}}
    </style><section class="page"><header class="head"><div><h1>Slicing-Server</h1><p>Modelle, Warteschlange, Engines, neue Aufträge und Diagnose.</p></div><strong id="server-state">nicht geladen</strong></header><div id="content"></div></section>`;
    this.#mounted = true;
    this.#render();
  }

  async #load(full: boolean): Promise<void> {
    if (!this.#hass || this.#loading) return;
    this.#loading = true;
    this.#error = "";
    if (full) this.#render();
    try {
      this.#server = await this.#hass.callWS<SlicingOverview>({ type: "printer_slicing_server/overview" });
      const auditFingerprint = JSON.stringify({ info: this.#server.info, status: this.#server.status, jobs: nestedRecords(this.#server.jobs, "jobs").map((job) => [job.job_id, job.status, job.modified]) });
      if (auditFingerprint !== this.#lastAuditFingerprint) {
        this.#lastAuditFingerprint = auditFingerprint;
        writeFrontendAudit({ category: "Slicing-Server", component: "slicing-server-workspace", event: "overview_changed", status: "info", details: { info: this.#server.info || {}, status: this.#server.status || {}, job_count: nestedRecords(this.#server.jobs, "jobs").length, file_count: nestedRecords(this.#server.files, "files").length } });
      }
      const files = nestedRecords(this.#server.files, "files");
      if (!files.some((item) => String(item.filename || "") === this.#selectedModel)) {
        this.#selectedModel = String(files[0]?.filename || "");
      }
      const printers = nestedRecords(this.#server.printers, "printers");
      if (!this.#draftPrinter || !printers.some((item) => String(item.id || "") === this.#draftPrinter)) {
        this.#draftPrinter = String(printers[0]?.id || "");
      }
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      writeFrontendAudit({ category: "Slicing-Server", component: "slicing-server-workspace", event: "overview_failed", status: "error", details: { error: this.#error } });
    } finally {
      this.#loading = false;
      this.#render();
    }
  }

  #filteredJobs(jobs: DataRecord[]): DataRecord[] {
    const search = this.#search.trim().toLocaleLowerCase("de-DE");
    return jobs.filter((job) => {
      const state = String(job.status || "").toLowerCase();
      const filterMatches = this.#jobFilter === "all"
        || (this.#jobFilter === "active" && ["queued", "slicing", "running", "cancelling"].includes(state))
        || (this.#jobFilter === "failed" && ["failed", "error", "cancelled", "interrupted"].includes(state))
        || (this.#jobFilter === "completed" && ["completed", "succeeded"].includes(state));
      if (!filterMatches) return false;
      if (!search) return true;
      return [job.job_id, job.input_file, job.download_name, job.engine, job.status]
        .some((value) => String(value || "").toLocaleLowerCase("de-DE").includes(search));
    });
  }

  #render(): void {
    const host = this.#root.querySelector<HTMLElement>("#content");
    if (!host) return;
    const info = record(this.#server?.info);
    const status = record(this.#server?.status);
    const printers = nestedRecords(this.#server?.printers, "printers");
    const files = nestedRecords(this.#server?.files, "files");
    const jobs = nestedRecords(this.#server?.jobs, "jobs");
    const filteredJobs = this.#filteredJobs(jobs).slice(0, 20);
    const search = this.#search.trim().toLocaleLowerCase("de-DE");
    const filteredFiles = files.filter((file) => !search || String(file.filename || "").toLocaleLowerCase("de-DE").includes(search)).slice(0, 12);
    const activeJobs = jobs.filter((job) => ["queued", "slicing", "running", "cancelling"].includes(String(job.status || "").toLowerCase())).length;
    const failedJobs = jobs.filter((job) => ["failed", "error", "cancelled", "interrupted"].includes(String(job.status || "").toLowerCase())).length;
    const state = text(info.status, this.#server ? "unbekannt" : "nicht geladen");
    const stateNode = this.#root.querySelector<HTMLElement>("#server-state");
    if (stateNode) stateNode.textContent = state;

    host.innerHTML = `<div class="grid"><article class="panel wide"><h2>Serverstatus</h2><div class="body"><div class="server-summary">${[
      metric("Status", state), metric("Version", info.version), metric("Engines", info.engine_count),
      metric("Warteschlange", status.queued_jobs ?? activeJobs), metric("Modelle / Jobs", `${files.length} / ${jobs.length}`, `${failedJobs} fehlerhaft`),
    ].join("")}</div>${this.#error ? `<div class="error">${esc(this.#error)}</div>` : ""}<div class="toolbar"><input id="server-search" type="search" placeholder="Modelle und Aufträge durchsuchen" value="${esc(this.#search)}"><select id="job-filter"><option value="all" ${this.#jobFilter === "all" ? "selected" : ""}>Alle Aufträge</option><option value="active" ${this.#jobFilter === "active" ? "selected" : ""}>Aktiv</option><option value="failed" ${this.#jobFilter === "failed" ? "selected" : ""}>Fehler</option><option value="completed" ${this.#jobFilter === "completed" ? "selected" : ""}>Abgeschlossen</option></select><button class="button" id="server-refresh" type="button" ${this.#loading ? "disabled" : ""}>${this.#loading ? "Aktualisierung …" : "Aktualisieren"}</button></div><div class="notice">Automatische Aktualisierung alle 10 Sekunden. Geöffnete Bereiche und Formulare bleiben dabei geöffnet.</div></div></article><article class="panel"><h2>Neuer Auftrag</h2><div class="body form"><details id="new-job" ${this.#newJobOpen ? "open" : ""}><summary>Upload und Slicing</summary><div class="form-grid"><label>Modell hochladen<input id="server-file" type="file" accept=".stl,.3mf,.obj,.amf"></label><label>Ausgewähltes Modell<select id="server-model">${files.length ? files.map((file) => `<option value="${esc(file.filename)}" ${String(file.filename) === this.#selectedModel ? "selected" : ""}>${esc(file.filename)}</option>`).join("") : '<option value="">Keine Modelle</option>'}</select></label><label>Drucker<select id="server-printer">${printers.map((printer) => `<option value="${esc(printer.id)}" ${String(printer.id) === this.#draftPrinter ? "selected" : ""}>${esc(printer.name || printer.id)}</option>`).join("")}</select></label><label>Engine<select id="server-engine"><option value="auto" ${this.#draftEngine === "auto" ? "selected" : ""}>Automatisch</option><option value="bambu_studio" ${this.#draftEngine === "bambu_studio" ? "selected" : ""}>Bambu Studio</option><option value="prusaslicer" ${this.#draftEngine === "prusaslicer" ? "selected" : ""}>PrusaSlicer</option><option value="curaengine" ${this.#draftEngine === "curaengine" ? "selected" : ""}>CuraEngine</option></select></label><label>Ausgabe<select id="server-format"><option value="gcode" ${this.#draftFormat === "gcode" ? "selected" : ""}>G-Code</option><option value="3mf" ${this.#draftFormat === "3mf" ? "selected" : ""}>3MF</option></select></label><label>Job-ID<input id="server-job-id" placeholder="automatisch" value="${esc(this.#draftJobId)}"></label></div>${this.#uploadFile ? `<div class="selected-file">Vorgemerkt: ${esc(this.#uploadFile.name)} · ${bytes(this.#uploadFile.size)}</div>` : ""}<div class="form-actions"><button class="button" id="server-upload" type="button" ${this.#uploadFile ? "" : "disabled"}>Hochladen</button><button class="button primary" id="server-slice" type="button" ${this.#selectedModel ? "" : "disabled"}>Slicing starten</button></div>${this.#notice ? `<div class="${this.#noticeError ? "error" : "notice"}">${esc(this.#notice)}</div>` : ""}</details></div></article><article class="panel"><h2>Modelle</h2><div class="body"><div class="models">${filteredFiles.length ? filteredFiles.map((file) => `<article class="model ${String(file.filename) === this.#selectedModel ? "selected" : ""}"><div class="preview">⬡</div><div class="model-body"><div class="model-name">${esc(file.filename)}</div><div class="model-meta">${bytes(file.size)} · ${dateTime(file.modified)}</div><button class="button choose-model" data-file="${esc(file.filename)}" type="button">Auswählen</button></div></article>`).join("") : '<div class="empty">Keine passenden Modelle.</div>'}</div></div></article><article class="panel wide"><h2>Aufträge</h2><div class="body jobs">${filteredJobs.length ? `<table><thead><tr><th>Job</th><th>Status</th><th>Engine</th><th>Datei</th><th>Geändert</th><th></th></tr></thead><tbody>${filteredJobs.map((job) => `<tr><td class="mono">${esc(job.job_id)}</td><td class="state ${stateClass(job.status)}">${esc(job.status)}</td><td>${esc(job.engine || "–")}</td><td>${esc(job.input_file || job.download_name || "–")}</td><td>${dateTime(job.modified)}</td><td>${job.download_url ? `<button class="button download-job" data-job="${esc(job.job_id)}" type="button">Download</button>` : ""}</td></tr>`).join("")}</tbody></table>` : '<div class="empty">Keine passenden Aufträge.</div>'}</div></article><article class="panel wide"><h2>Serverdiagnose</h2><div class="body"><details id="server-diagnostics" ${this.#diagnosticsOpen ? "open" : ""}><summary>Rohdaten anzeigen</summary><pre class="raw">${esc(JSON.stringify({ info, status, diagnostics: this.#server?.diagnostics, engines: this.#server?.engines }, null, 2))}</pre></details></div></article></div>`;
    this.#bind();
  }

  #bind(): void {
    this.#root.querySelector<HTMLDetailsElement>("#new-job")?.addEventListener("toggle", (event) => {
      this.#newJobOpen = (event.currentTarget as HTMLDetailsElement).open;
    });
    this.#root.querySelector<HTMLDetailsElement>("#server-diagnostics")?.addEventListener("toggle", (event) => {
      this.#diagnosticsOpen = (event.currentTarget as HTMLDetailsElement).open;
    });
    this.#root.querySelector<HTMLInputElement>("#server-search")?.addEventListener("input", (event) => {
      this.#search = (event.currentTarget as HTMLInputElement).value;
      this.#render();
    });
    this.#root.querySelector<HTMLSelectElement>("#job-filter")?.addEventListener("change", (event) => {
      this.#jobFilter = (event.currentTarget as HTMLSelectElement).value as JobFilter;
      this.#render();
    });
    this.#root.querySelector<HTMLInputElement>("#server-file")?.addEventListener("change", (event) => {
      this.#uploadFile = (event.currentTarget as HTMLInputElement).files?.[0] ?? null;
      this.#newJobOpen = true;
      this.#render();
    });
    this.#root.querySelector<HTMLSelectElement>("#server-model")?.addEventListener("change", (event) => {
      this.#selectedModel = (event.currentTarget as HTMLSelectElement).value;
      this.#render();
    });
    this.#root.querySelector<HTMLSelectElement>("#server-printer")?.addEventListener("change", (event) => { this.#draftPrinter = (event.currentTarget as HTMLSelectElement).value; });
    this.#root.querySelector<HTMLSelectElement>("#server-engine")?.addEventListener("change", (event) => { this.#draftEngine = (event.currentTarget as HTMLSelectElement).value; });
    this.#root.querySelector<HTMLSelectElement>("#server-format")?.addEventListener("change", (event) => { this.#draftFormat = (event.currentTarget as HTMLSelectElement).value; });
    this.#root.querySelector<HTMLInputElement>("#server-job-id")?.addEventListener("input", (event) => { this.#draftJobId = (event.currentTarget as HTMLInputElement).value; });
    this.#root.querySelectorAll<HTMLButtonElement>(".choose-model").forEach((button) => button.addEventListener("click", () => {
      this.#selectedModel = button.dataset.file || "";
      this.#render();
    }));
    this.#root.querySelector<HTMLButtonElement>("#server-refresh")?.addEventListener("click", () => void this.#load(true));
    this.#root.querySelector<HTMLButtonElement>("#server-upload")?.addEventListener("click", () => void this.#upload());
    this.#root.querySelector<HTMLButtonElement>("#server-slice")?.addEventListener("click", () => void this.#createJob());
    this.#root.querySelectorAll<HTMLButtonElement>(".download-job").forEach((button) => button.addEventListener("click", () => void this.#download(button.dataset.job || "")));
  }

  async #upload(): Promise<void> {
    if (!this.#hass || !this.#uploadFile) return;
    const file = this.#uploadFile;
    if (file.size > 32 * 1024 * 1024) {
      this.#notice = "Im Home-Assistant-Panel sind maximal 32 MiB pro Upload möglich.";
      this.#noticeError = true;
      this.#render();
      return;
    }
    try {
      const bytesValue = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (let offset = 0; offset < bytesValue.length; offset += 0x8000) binary += String.fromCharCode(...bytesValue.subarray(offset, offset + 0x8000));
      await this.#hass.callWS({ type: "printer_slicing_server/upload", filename: file.name, content_base64: btoa(binary) });
      this.#selectedModel = file.name;
      this.#uploadFile = null;
      this.#notice = "Upload abgeschlossen.";
      this.#noticeError = false;
      writeFrontendAudit({ category: "Slicing-Server", component: "slicing-server-workspace", event: "model_uploaded", status: "success", details: { filename: file.name, size_bytes: file.size } });
      this.#newJobOpen = true;
      await this.#load(true);
    } catch (error) {
      this.#notice = error instanceof Error ? error.message : String(error);
      this.#noticeError = true;
      this.#render();
    }
  }

  async #createJob(): Promise<void> {
    if (!this.#hass || !this.#selectedModel) return;
    const payload: Record<string, unknown> = {
      printer_profile: this.#draftPrinter,
      input_file: this.#selectedModel,
      engine: this.#draftEngine || "auto",
      output_format: this.#draftFormat || "gcode",
      process_profile: "default",
      filament_profile: "default",
    };
    if (this.#draftJobId.trim()) payload.job_id = this.#draftJobId.trim();
    try {
      const result = await this.#hass.callWS<DataRecord>({ type: "printer_slicing_server/create_job", payload });
      this.#notice = `Job ${text(result.job_id)} wurde angelegt.`;
      this.#noticeError = false;
      writeFrontendAudit({ category: "Slicing-Server", component: "slicing-server-workspace", event: "job_created", status: "success", job_id: String(result.job_id || "") || undefined, details: { input_file: this.#selectedModel, printer_profile: this.#draftPrinter, engine: this.#draftEngine, output_format: this.#draftFormat } });
      this.#newJobOpen = true;
      await this.#load(true);
    } catch (error) {
      this.#notice = error instanceof Error ? error.message : String(error);
      this.#noticeError = true;
      this.#render();
    }
  }

  async #download(jobId: string): Promise<void> {
    if (!this.#hass || !jobId) return;
    try {
      const result = await this.#hass.callWS<DataRecord>({ type: "printer_slicing_server/download", job_id: jobId });
      const binary = atob(String(result.content_base64 || ""));
      const bytesValue = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytesValue[index] = binary.charCodeAt(index);
      const url = URL.createObjectURL(new Blob([bytesValue], { type: "application/octet-stream" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = String(result.filename || `${jobId}.gcode`);
      link.click();
      writeFrontendAudit({ category: "Slicing-Server", component: "slicing-server-workspace", event: "artifact_downloaded", status: "success", job_id: jobId, details: { filename: link.download, size_bytes: bytesValue.length } });
      globalThis.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#render();
    }
  }
}

if (!customElements.get("ultimate-3d-slicing-server-workspace")) {
  customElements.define("ultimate-3d-slicing-server-workspace", Ultimate3DSlicingServerWorkspace);
}