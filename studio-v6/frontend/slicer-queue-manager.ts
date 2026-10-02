import "./v6-action-dialog.js";
import { errorMessage } from "./ha-api-transport.js";
import {
  getQueueStatus,
  batchCreateJobs,
  releaseQueueJob,
  releaseAllQueuedJobs,
  type SliceJob,
  type SlicerQueueStatus,
} from "./slicing-api.js";
import { listNativeSliceJobs } from "./slicer-job-list-api.js";
import { deleteTerminalSliceJob } from "./slicer-job-delete-api.js";
import { getBatchQueueContext, loadSliceProcessOverrides } from "./plate-slice-api.js";

import type { V6ActionDialog } from "./v6-action-dialog.js";

const ACTIVE = new Set(["queued", "running", "cancelling"]);
const TERMINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);
const QUEUED = new Set(["queued"]);

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function dateLabel(value: unknown): string {
  const date = new Date(String(value || ""));
  return Number.isNaN(date.getTime()) ? "–" : date.toLocaleString("de-DE");
}

function sizeLabel(value: unknown): string {
  const size = Number(value);
  if (!Number.isFinite(size) || size <= 0) return "–";
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 ** 2).toFixed(1)} MB`;
}

function timeLabel(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return "–";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function signature(jobs: readonly SliceJob[]): string {
  return JSON.stringify(jobs.map((job) => [
    job.id,
    job.status,
    job.model_file,
    job.output_size_bytes,
    job.created_at,
  ]));
}

export class Ultimate3DSlicerQueueManager extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #jobs: SliceJob[] = [];
  #queueStatus: SlicerQueueStatus | null = null;
  #timer: number | null = null;
  #signature = "";
  #busy = false;
  #dialogActive = false;

  connectedCallback(): void {
    if (!this.#root.childElementCount) this.#mount();
    void this.#refresh();
    if (this.#timer === null) {
      this.#timer = window.setInterval(() => void this.#refresh(true), 5000);
    }
  }

  disconnectedCallback(): void {
    if (this.#timer !== null) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  #mount(): void {
    this.#root.innerHTML = `<style>
      :host{display:block;height:100%;min-height:0;color:#eef5ff;background:#08101a}*{box-sizing:border-box}.panel{display:grid;grid-template-rows:auto auto minmax(0,1fr);height:100%;min-height:0;border:1px solid #26384f;border-radius:12px;background:#0e1824;overflow:hidden}.head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:11px 13px;border-bottom:1px solid #26384f}.head h2{margin:0;font-size:15px}.head small{color:#8298ae}.actions{display:flex;gap:7px;flex-wrap:wrap}button{min-height:35px;padding:7px 10px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}button:disabled{opacity:.4;cursor:not-allowed}.primary{border-color:#4a9eff;background:#1a3a5c}.primary:hover{background:#245078}.success{border-color:#27734c;background:#1a3a2a}.success:hover{background:#245036}.warning{border-color:#d4a017;background:#3a2e10}.warning:hover{background:#4a3a15}.danger{border-color:#8f3f4b;background:#3a171d}.danger:hover{background:#4a1f25}.notice{display:none;margin:9px 10px 0;padding:9px;border:1px solid #2a3c53;border-radius:8px;background:#101c29}.notice.visible{display:block}.notice.ok{border-color:#27734c;color:#8ff0b5}.notice.error{border-color:#8f3f4b;color:#ffd7dc}.jobs{min-height:0;overflow:auto;padding:10px;scrollbar-gutter:stable}.job{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;margin-bottom:8px;padding:10px;border:1px solid #26384f;border-radius:9px;background:#0a141f}.job:last-child{margin-bottom:0}.job strong,.job small{display:block}.job small{margin-top:3px;color:#8298ae;overflow-wrap:anywhere}.buttons{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.status{display:inline-block;margin-top:6px;padding:3px 7px;border-radius:999px;background:#203348;color:#b9c9d8;font-size:10px;text-transform:uppercase}.status.queued{background:#3a2e10;color:#d4a017}.status.running{background:#1a3a5c;color:#4a9eff}.status.succeeded{background:#17482c;color:#94e7ae}.status.failed,.status.interrupted{background:#4a2027;color:#ffc0c6}.status.cancelled{background:#4b3916;color:#ffd78b}.status.long-print{border-color:#e74c3c;background:#4a1a1a;animation:pulse 2s infinite}.status.long-print::after{content:" ⚠️"}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}.empty{display:grid;place-items:center;min-height:190px;color:#8298ae}.summary{color:#8da3b9;font-size:11px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:9px 10px;padding:9px;border:1px solid #26384f;border-radius:8px;background:#0a141f}.stat{text-align:center}.stat-value{font-size:18px;font-weight:700;color:#4a9eff}.stat-label{font-size:10px;color:#8298ae;margin-top:2px}@media(max-width:720px){.head,.job{display:block}.actions,.buttons{margin-top:8px}.buttons button,.actions button{flex:1}.stats{grid-template-columns:repeat(2,1fr)}}
    </style><section class="panel"><header class="head"><div><h2>Slicing-Warteschlange</h2><small id="summary">Lädt...</small></div><div class="actions"><button id="refresh">Aktualisieren</button><button id="batch" class="primary">Batch-Import</button><button id="release-all" class="success" disabled>Alle freigeben</button><button class="danger" id="clear" disabled>Abgeschlossene löschen</button></div></header><div class="notice" id="notice"></div><div class="stats" id="stats"><div class="stat"><div class="stat-value" id="stat-total">0</div><div class="stat-label">Gesamt</div></div><div class="stat"><div class="stat-value" id="stat-queued">0</div><div class="stat-label">Warteschlange</div></div><div class="stat"><div class="stat-value" id="stat-running">0</div><div class="stat-label">Läuft</div></div><div class="stat"><div class="stat-value" id="stat-completed">0</div><div class="stat-label">Erledigt</div></div></div><div class="jobs" id="jobs"><div class="empty">Sliceraufträge werden geladen...</div></div><v6-action-dialog></v6-action-dialog></section>`;
    
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refresh());
    this.#root.querySelector<HTMLButtonElement>("#batch")?.addEventListener("click", () => void this.#batchUpload());
    this.#root.querySelector<HTMLButtonElement>("#release-all")?.addEventListener("click", () => void this.#releaseAll());
    this.#root.querySelector<HTMLButtonElement>("#clear")?.addEventListener("click", () => void this.#removeAllTerminal());
  }

  #dialog(): V6ActionDialog | null {
    return this.#root.querySelector<V6ActionDialog>("v6-action-dialog");
  }

  async #confirm(options: Parameters<V6ActionDialog["confirm"]>[0]): Promise<boolean> {
    const dialog = this.#dialog();
    if (!dialog) return false;
    this.#dialogActive = true;
    try {
      return await dialog.confirm(options);
    } finally {
      this.#dialogActive = false;
    }
  }

  async #refresh(silent = false): Promise<void> {
    if (this.#busy || this.#dialogActive) return;
    try {
      const [jobs, status] = await Promise.all([
        listNativeSliceJobs(),
        getQueueStatus(),
      ]);
      this.#jobs = jobs;
      this.#queueStatus = status;
      const next = signature(jobs);
      if (next !== this.#signature) {
        this.#signature = next;
        this.#renderRows();
        this.#setSummary();
        this.#updateStats();
        this.#updateControls();
      }
    } catch (error) {
      if (!silent) this.#notice(errorMessage(error), true);
    }
  }

  async #batchUpload(): Promise<void> {
    const batchContext = getBatchQueueContext();
    if (!batchContext) {
      this.#notice("Bitte im Studio zuerst einen Ziel-Drucker, Profile und eine vollständige Materialzuordnung auswählen. Die Auswahl muss aktuell (maximal 30 Minuten alt) sein.", true);
      return;
    }
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.accept = ".3mf";
    input.click();
    
    return new Promise<void>((resolve) => {
      input.addEventListener("change", async (e) => {
        const files = Array.from((e.target as HTMLInputElement).files || []);
        if (files.length === 0) {
          resolve();
          return;
        }
        
        const confirmed = await this.#confirm({
          title: "Batch-Import",
          message: `${files.length} 3MF-Dateien mit der aktuellen Studio-, Drucker-, Material- und Prozessauswahl vorprüfen und manuell gehalten zur Warteschlange hinzufügen?`,
          confirmLabel: "Hinzufügen",
          cancelLabel: "Abbrechen",
          danger: false,
        });
        
        if (!confirmed) {
          resolve();
          return;
        }
        
        await this.#run(async () => {
          const result = await batchCreateJobs(files, 0, batchContext, loadSliceProcessOverrides());
          if (result.errors.length > 0) {
            throw new Error(result.errors.join("\n"));
          }
          return `${result.created} Aufgabe(n) zur Warteschlange hinzugefügt`;
        });
        
        resolve();
      });
    });
  }

  async #releaseJob(jobId: string): Promise<void> {
    if (this.#busy) return;
    
    const confirmed = await this.#confirm({
      title: "Freigeben",
      message: "Auftrag jetzt starten?",
      confirmLabel: "Starten",
      cancelLabel: "Abbrechen",
      danger: false,
    });
    
    if (!confirmed) return;
    
    await this.#run(async () => {
      const result = await releaseQueueJob(jobId);
      if (!result.released) {
        throw new Error("Freigabe fehlgeschlagen");
      }
      return "Auftrag gestartet";
    });
  }

  async #releaseAll(): Promise<void> {
    if (this.#busy) return;
    
    const queuedJobs = this.#jobs.filter((j) => QUEUED.has(j.status));
    if (queuedJobs.length === 0) return;
    
    const confirmed = await this.#confirm({
      title: "Alle freigeben",
      message: `${queuedJobs.length} Auftrag(e) jetzt starten?`,
      confirmLabel: "Alle starten",
      cancelLabel: "Abbrechen",
      danger: true,
    });
    
    if (!confirmed) return;
    
    await this.#run(async () => {
      const result = await releaseAllQueuedJobs();
      return `${result.released} Auftrag(e) gestartet`;
    });
  }

  async #remove(job: SliceJob): Promise<void> {
    if (this.#busy || !TERMINAL.has(job.status)) return;
    
    const confirmed = await this.#confirm({
      title: "Löschen",
      message: `${job.model_file || job.id} löschen?`,
      confirmLabel: "Löschen",
      cancelLabel: "Abbrechen",
      danger: true,
    });
    
    if (!confirmed) return;
    
    await this.#run(async () => {
      await deleteTerminalSliceJob(job.id);
      return "Auftrag gelöscht";
    });
  }

  async #removeAllTerminal(): Promise<void> {
    const terminalJobs = this.#jobs.filter((job) => TERMINAL.has(job.status));
    if (terminalJobs.length === 0) return;
    
    const confirmed = await this.#confirm({
      title: "Abgeschlossene löschen",
      message: `${terminalJobs.length} abgeschlossene Auftrag(e) löschen?`,
      confirmLabel: "Alle löschen",
      cancelLabel: "Abbrechen",
      danger: true,
    });
    
    if (!confirmed) return;

    this.#busy = true;
    this.#updateControls();
    let deleted = 0;
    const failures: string[] = [];
    
    for (const job of terminalJobs) {
      try {
        await deleteTerminalSliceJob(job.id);
        deleted += 1;
      } catch (error) {
        failures.push(`${job.model_file || job.id}: ${errorMessage(error)}`);
      }
    }
    
    this.#busy = false;
    await this.#reloadAfterMutation();
    
    if (failures.length) {
      this.#notice(`${deleted} gelöscht, ${failures.length} fehlerhaft. ${failures.join(" | ")}`, true);
    } else {
      this.#notice(`${deleted} abgeschlossene Aufträge gelöscht`, false);
    }
  }

  async #download(job: SliceJob): Promise<void> {
    if (job.status !== "succeeded" || this.#busy) return;
    
    const { downloadSliceArtifact } = await import("./slicing-api.js");
    try {
      const artifact = await downloadSliceArtifact(job.id);
      const url = URL.createObjectURL(artifact.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = artifact.filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.#notice(`${artifact.filename} heruntergeladen`, false);
    } catch (error) {
      this.#notice(errorMessage(error), true);
    }
  }

  async #run(operation: () => Promise<string>): Promise<void> {
    if (this.#busy) return;
    this.#busy = true;
    this.#updateControls();
    try {
      const message = await operation();
      await this.#reloadAfterMutation();
      this.#notice(message, false);
    } catch (error) {
      this.#notice(errorMessage(error), true);
    } finally {
      this.#busy = false;
      this.#updateControls();
    }
  }

  async #reloadAfterMutation(): Promise<void> {
    const [jobs, status] = await Promise.all([
      listNativeSliceJobs(),
      getQueueStatus(),
    ]);
    this.#jobs = jobs;
    this.#queueStatus = status;
    this.#signature = signature(jobs);
    this.#renderRows();
    this.#setSummary();
    this.#updateStats();
    this.#updateControls();
  }

  #renderRows(): void {
    const host = this.#root.querySelector<HTMLElement>("#jobs");
    if (!host) return;
    const scrollTop = host.scrollTop;
    host.innerHTML = this.#jobs.length
      ? this.#jobs.map((job) => this.#jobMarkup(job)).join("")
      : '<div class="empty">Keine Sliceraufträge vorhanden</div>';
    host.scrollTop = Math.min(scrollTop, host.scrollHeight);
    
    host.querySelectorAll<HTMLButtonElement>("[data-delete]").forEach((button) => button.addEventListener("click", () => {
      const job = this.#jobs.find((item) => item.id === button.dataset.delete);
      if (job) void this.#remove(job);
    }));
    
    host.querySelectorAll<HTMLButtonElement>("[data-download]").forEach((button) => button.addEventListener("click", () => {
      const job = this.#jobs.find((item) => item.id === button.dataset.download);
      if (job) void this.#download(job);
    }));
    
    host.querySelectorAll<HTMLButtonElement>("[data-release]").forEach((button) => button.addEventListener("click", () => {
      const job = this.#jobs.find((item) => item.id === button.dataset.release);
      if (job) void this.#releaseJob(job.id);
    }));
    
    this.#updateControls();
  }

  #setSummary(): void {
    const summary = this.#root.querySelector<HTMLElement>("#summary");
    if (!summary) return;
    const active = this.#jobs.filter((job) => ACTIVE.has(job.status)).length;
    const terminal = this.#jobs.filter((job) => TERMINAL.has(job.status)).length;
    const queued = this.#jobs.filter((job) => QUEUED.has(job.status)).length;
    summary.textContent = `${active} aktiv · ${queued} in Warteschlange · ${terminal} erledigt · Alle 5s aktualisieren`;
  }

  #updateStats(): void {
    const total = this.#root.querySelector<HTMLElement>("#stat-total");
    const queued = this.#root.querySelector<HTMLElement>("#stat-queued");
    const running = this.#root.querySelector<HTMLElement>("#stat-running");
    const completed = this.#root.querySelector<HTMLElement>("#stat-completed");
    
    if (total) total.textContent = String(this.#jobs.length);
    if (queued) queued.textContent = String(this.#jobs.filter((j) => QUEUED.has(j.status)).length);
    if (running) running.textContent = String(this.#jobs.filter((j) => j.status === "running").length);
    if (completed) completed.textContent = String(this.#jobs.filter((j) => j.status === "succeeded").length);
  }

  #updateControls(): void {
    const terminalCount = this.#jobs.filter((job) => TERMINAL.has(job.status)).length;
    const queuedCount = this.#jobs.filter((job) => QUEUED.has(job.status)).length;
    const refresh = this.#root.querySelector<HTMLButtonElement>("#refresh");
    const clear = this.#root.querySelector<HTMLButtonElement>("#clear");
    const releaseAll = this.#root.querySelector<HTMLButtonElement>("#release-all");
    
    if (refresh) refresh.disabled = this.#busy;
    if (clear) clear.disabled = this.#busy || terminalCount === 0;
    if (releaseAll) releaseAll.disabled = this.#busy || queuedCount === 0;
    
    this.#root.querySelectorAll<HTMLButtonElement>("#jobs button").forEach((button) => {
      button.disabled = this.#busy;
    });
  }

  #notice(message: string, error: boolean): void {
    const notice = this.#root.querySelector<HTMLElement>("#notice");
    if (!notice) return;
    notice.textContent = message;
    notice.className = `notice visible ${error ? "error" : "ok"}`;
  }

  #jobMarkup(job: SliceJob): string {
    const terminal = TERMINAL.has(job.status);
    const queued = QUEUED.has(job.status);
    const printTime = (job as any).print_time_seconds ?? (job as any).model_time_seconds;
    const isLongPrint = printTime != null && printTime > 86400;
    
    return `<article class="job"><div>
      <strong>${esc(job.model_file || job.id)}</strong>
      <small>${esc(job.id)}<br>
        ${dateLabel(job.created_at)} · 
        Artefakt ${sizeLabel(job.output_size_bytes)} · 
        ${isLongPrint ? '<span style="color:#e74c3c;font-weight:bold">>1 Tag Druckzeit</span>' : 'Druckzeit ' + timeLabel(printTime)}
      </small>
      <span class="status ${esc(job.status)}${isLongPrint ? ' long-print' : ''}">${esc(job.status)}</span>
      ${job.error ? `<small>${esc(job.error)}</small>` : ""}
    </div>
    <div class="buttons">
      ${job.status === "succeeded" ? `<button data-download="${esc(job.id)}">GCode laden</button>` : ""}
      ${queued ? `<button data-release="${esc(job.id)}" class="primary">Freigeben</button>` : ""}
      ${terminal ? `<button class="danger" data-delete="${esc(job.id)}">Löschen</button>` : ""}
    </div></article>`;
  }
}

if (!customElements.get("ultimate-3d-slicer-queue-manager")) {
  customElements.define("ultimate-3d-slicer-queue-manager", Ultimate3DSlicerQueueManager);
}
