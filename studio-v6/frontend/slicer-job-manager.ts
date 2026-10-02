import "./v6-action-dialog.js";
import { errorMessage } from "./ha-api-transport.js";
import {
  downloadSliceArtifact,
  type SliceJob,
} from "./slicing-api.js";
import { deleteTerminalSliceJob } from "./slicer-job-delete-api.js";
import { listNativeSliceJobs } from "./slicer-job-list-api.js";
import type { V6ActionDialog } from "./v6-action-dialog.js";

const ACTIVE = new Set(["queued", "running", "cancelling"]);
const TERMINAL = new Set(["succeeded", "failed", "cancelled", "interrupted"]);

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

function signature(jobs: readonly SliceJob[]): string {
  return JSON.stringify(jobs.map((job) => [
    job.id,
    job.status,
    job.model_file,
    job.output_file,
    job.output_size_bytes,
    job.error,
    job.updated_at,
  ]));
}

export class Ultimate3DSlicerJobManager extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #jobs: SliceJob[] = [];
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
      :host{display:block;height:100%;min-height:0;color:#eef5ff;background:#08101a}*{box-sizing:border-box}.panel{display:grid;grid-template-rows:auto auto minmax(0,1fr);height:100%;min-height:0;border:1px solid #26384f;border-radius:12px;background:#0e1824;overflow:hidden}.head{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:11px 13px;border-bottom:1px solid #26384f}.head h2{margin:0;font-size:15px}.head small{color:#8298ae}.actions{display:flex;gap:7px;flex-wrap:wrap}button{min-height:35px;padding:7px 10px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}button:disabled{opacity:.4;cursor:not-allowed}.danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}.notice{display:none;margin:9px 10px 0;padding:9px;border:1px solid #2a3c53;border-radius:8px;background:#101c29}.notice.visible{display:block}.notice.ok{border-color:#27734c;color:#8ff0b5}.notice.error{border-color:#8f3f4b;color:#ffd7dc}.jobs{min-height:0;overflow:auto;padding:10px;scrollbar-gutter:stable}.job{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;margin-bottom:8px;padding:10px;border:1px solid #26384f;border-radius:9px;background:#0a141f}.job:last-child{margin-bottom:0}.job strong,.job small{display:block}.job small{margin-top:3px;color:#8298ae;overflow-wrap:anywhere}.buttons{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.status{display:inline-block;margin-top:6px;padding:3px 7px;border-radius:999px;background:#203348;color:#b9c9d8;font-size:10px;text-transform:uppercase}.status.succeeded{background:#17482c;color:#94e7ae}.status.failed,.status.interrupted{background:#4a2027;color:#ffc0c6}.status.cancelled{background:#4b3916;color:#ffd78b}.empty{display:grid;place-items:center;min-height:190px;color:#8298ae}.summary{color:#8da3b9;font-size:11px}@media(max-width:720px){.head,.job{display:block}.actions,.buttons{margin-top:8px}.buttons button{flex:1}}
    </style><section class="panel"><header class="head"><div><h2>Sliceraufträge und GCode-Artefakte</h2><small id="summary">Wird geladen …</small></div><div class="actions"><button id="refresh">Aktualisieren</button><button class="danger" id="clear" disabled>Alle abgeschlossenen entfernen</button></div></header><div class="notice" id="notice"></div><div class="jobs" id="jobs"><div class="empty">Sliceraufträge werden geladen …</div></div><v6-action-dialog></v6-action-dialog></section>`;
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refresh());
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
      const jobs = await listNativeSliceJobs();
      const next = signature(jobs);
      this.#jobs = jobs;
      if (next !== this.#signature) {
        this.#signature = next;
        this.#renderRows();
      }
      this.#setSummary();
      if (!silent) this.#notice("Sliceraufträge wurden aktualisiert.", false);
    } catch (error) {
      this.#notice(errorMessage(error), true);
    }
  }

  async #remove(job: SliceJob): Promise<void> {
    if (!TERMINAL.has(job.status) || this.#busy) return;
    const confirmed = await this.#confirm({
      title: job.status === "succeeded"
        ? "Slicerauftrag und GCode löschen"
        : "Slicerauftrag bereinigen",
      message: job.status === "succeeded"
        ? "Auftrag, Quelldatei, Protokolle und erzeugtes GCode-3MF dauerhaft löschen?"
        : "Auftrag, Quelldatei und Protokolle dauerhaft löschen?",
      detail: `${job.model_file || job.id}\n${job.id}`,
      confirmLabel: "Dauerhaft löschen",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run(async () => {
      await deleteTerminalSliceJob(job.id);
      return "Slicerauftrag und vorhandenes GCode-Artefakt wurden gelöscht.";
    });
  }

  async #removeAllTerminal(): Promise<void> {
    const jobs = this.#jobs.filter((job) => TERMINAL.has(job.status));
    if (!jobs.length || this.#busy) return;
    const confirmed = await this.#confirm({
      title: "Alle abgeschlossenen Sliceraufträge entfernen",
      message: `${jobs.length} abgeschlossene Aufträge samt vorhandenen GCode-Artefakten dauerhaft löschen?`,
      detail: jobs.map((job) => `${job.status}: ${job.model_file || job.id}`).join("\n"),
      confirmLabel: "Alle dauerhaft löschen",
      danger: true,
    });
    if (!confirmed) return;

    this.#busy = true;
    this.#updateControls();
    let deleted = 0;
    const failures: string[] = [];
    for (const job of jobs) {
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
      this.#notice(`${deleted} gelöscht, ${failures.length} fehlgeschlagen. ${failures.join(" | ")}`, true);
    } else {
      this.#notice(`${deleted} abgeschlossene Sliceraufträge wurden vollständig gelöscht.`, false);
    }
  }

  async #download(job: SliceJob): Promise<void> {
    if (job.status !== "succeeded" || this.#busy) return;
    try {
      const artifact = await downloadSliceArtifact(job.id);
      const url = URL.createObjectURL(artifact.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = artifact.filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.#notice(`${artifact.filename} wurde heruntergeladen.`, false);
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
    const jobs = await listNativeSliceJobs();
    this.#jobs = jobs;
    this.#signature = signature(jobs);
    this.#renderRows();
    this.#setSummary();
  }

  #renderRows(): void {
    const host = this.#root.querySelector<HTMLElement>("#jobs");
    if (!host) return;
    const scrollTop = host.scrollTop;
    host.innerHTML = this.#jobs.length
      ? this.#jobs.map((job) => this.#jobMarkup(job)).join("")
      : '<div class="empty">Keine Sliceraufträge oder GCode-Artefakte vorhanden.</div>';
    host.scrollTop = Math.min(scrollTop, host.scrollHeight);
    host.querySelectorAll<HTMLButtonElement>("[data-delete]").forEach((button) => button.addEventListener("click", () => {
      const job = this.#jobs.find((item) => item.id === button.dataset.delete);
      if (job) void this.#remove(job);
    }));
    host.querySelectorAll<HTMLButtonElement>("[data-download]").forEach((button) => button.addEventListener("click", () => {
      const job = this.#jobs.find((item) => item.id === button.dataset.download);
      if (job) void this.#download(job);
    }));
    this.#updateControls();
  }

  #setSummary(): void {
    const summary = this.#root.querySelector<HTMLElement>("#summary");
    if (!summary) return;
    const active = this.#jobs.filter((job) => ACTIVE.has(job.status)).length;
    const terminal = this.#jobs.filter((job) => TERMINAL.has(job.status)).length;
    summary.textContent = `${active} aktiv · ${terminal} abgeschlossen · Live alle 5 s`;
  }

  #updateControls(): void {
    const terminalCount = this.#jobs.filter((job) => TERMINAL.has(job.status)).length;
    const refresh = this.#root.querySelector<HTMLButtonElement>("#refresh");
    const clear = this.#root.querySelector<HTMLButtonElement>("#clear");
    if (refresh) refresh.disabled = this.#busy;
    if (clear) clear.disabled = this.#busy || terminalCount === 0;
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
    return `<article class="job"><div><strong>${esc(job.model_file || job.id)}</strong><small>${esc(job.id)}<br>${dateLabel(job.created_at)} · Artefakt ${sizeLabel(job.output_size_bytes)}</small><span class="status ${esc(job.status)}">${esc(job.status)}</span>${job.error ? `<small>${esc(job.error)}</small>` : ""}</div><div class="buttons">${job.status === "succeeded" ? `<button data-download="${esc(job.id)}">GCode-3MF herunterladen</button>` : ""}${terminal ? `<button class="danger" data-delete="${esc(job.id)}">Auftrag löschen</button>` : ""}</div></article>`;
  }
}

if (!customElements.get("ultimate-3d-slicer-job-manager")) {
  customElements.define("ultimate-3d-slicer-job-manager", Ultimate3DSlicerJobManager);
}
