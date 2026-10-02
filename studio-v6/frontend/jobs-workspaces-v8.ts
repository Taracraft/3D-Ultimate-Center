import "./printer-command-store.js";
import { errorMessage } from "./ha-api-transport.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import { isQueuedJob, printStatusLabel, resolvePrinterForJob } from "./printer-command-policy.js";
import type { Ultimate3DPrinterActions } from "./printer-command-store.js";
import { v6Api, type V6Job } from "./v6-api.js";

type Mode = "tasks" | "history";

const esc = (value: unknown): string => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char] || char));

abstract class JobsWorkspaceV8 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #state: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #busy = "";
  #message = "";
  #error = "";
  protected abstract readonly mode: Mode;

  connectedCallback(): void {
    if (this.#unsubscribe) return;
    this.#unsubscribe = jobActivityStore.subscribe((state) => {
      this.#state = state;
      this.#render();
    });
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  #id(job: V6Job): string {
    return String(job.job_id || job.id || "");
  }

  #jobs(): V6Job[] {
    return this.mode === "history"
      ? this.#state.jobs.history || []
      : [...(this.#state.jobs.current || []), ...(this.#state.jobs.queue || [])];
  }

  #row(job: V6Job): string {
    const id = esc(this.#id(job));
    const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
    const queued = isQueuedJob(job);
    const actions = this.mode === "history"
      ? `<button data-repeat="${id}" ${this.#busy ? "disabled" : ""}>Erneut einreihen</button>`
      : queued
        ? `<button class="danger" data-remove="${id}" ${this.#busy ? "disabled" : ""}>Aus Warteschlange</button>`
        : `<ultimate-3d-printer-actions data-job="${id}"></ultimate-3d-printer-actions>`;
    return `<article><div><strong>${esc(job.file || job.model_name || "Unbenanntes Modell")}</strong><small>${esc(job.printer_name || job.printer_id || "Drucker")} · ${esc(printStatusLabel(job.status))} · ${progress}%</small><span class="bar"><i style="width:${progress}%"></i></span></div><div class="actions">${actions}</div></article>`;
  }

  #slicerRow(): string {
    const job = this.#state.slicer;
    if (this.mode !== "tasks" || !job) return "";
    const active = ["queued", "running", "cancelling"].includes(job.status);
    return `<article class="slicer"><div><strong>${esc(job.model_file || job.output_file || "Slicer-Auftrag")}</strong><small>Slicer · ${esc(job.status)}</small></div><div class="actions">${active ? `<button class="danger" data-cancel-slicer ${job.status === "cancelling" ? "disabled" : ""}>${job.status === "cancelling" ? "Wird abgebrochen …" : "Slicing abbrechen"}</button>` : ""}</div></article>`;
  }

  async #repeat(job: V6Job): Promise<void> {
    const id = this.#id(job);
    if (!id || this.#busy || !window.confirm("Druck erneut einreihen? Der Druck startet nicht automatisch.")) return;
    this.#busy = id;
    this.#render();
    try {
      await v6Api.repeatJob(id);
      this.#message = "Auftrag wurde erneut eingereiht.";
      await jobActivityStore.refresh();
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#busy = "";
      this.#render();
    }
  }

  async #remove(job: V6Job): Promise<void> {
    const id = this.#id(job);
    if (!id || this.#busy || !window.confirm("Auftrag aus der Warteschlange entfernen?")) return;
    this.#busy = id;
    this.#render();
    try {
      await v6Api.removeQueuedJob(id);
      this.#message = "Auftrag wurde aus der Warteschlange entfernt.";
      await jobActivityStore.refresh();
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#busy = "";
      this.#render();
    }
  }

  async #cancelSlicer(): Promise<void> {
    const job = this.#state.slicer;
    if (!job || !window.confirm("Slicerauftrag wirklich abbrechen?")) return;
    try {
      await jobActivityStore.cancelActiveSlicerJob(job.id);
      this.#message = "Slicerabbruch wurde angefordert.";
    } catch (error) {
      this.#error = errorMessage(error);
    }
  }

  #render(): void {
    if (!this.isConnected) return;
    const jobs = this.#jobs();
    const title = this.mode === "tasks" ? "Aufgaben" : "Verlauf";
    const description = this.mode === "tasks"
      ? "Slicer-, laufende, pausierte und wartende Aufträge mit direkter Steuerung."
      : "Abgeschlossene, abgebrochene und fehlgeschlagene Drucke.";
    const error = this.#error || this.#state.error;
    this.#root.innerHTML = `<style>
      :host{display:block;min-height:calc(100vh - 156px);background:#08101a;color:#eef5ff}*{box-sizing:border-box}.page{padding:20px}.head{display:flex;justify-content:space-between;gap:14px}.head h1{margin:0}.head p{margin:6px 0 16px;color:#91a5bb}.list{display:grid;gap:10px}article{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;padding:14px;border:1px solid #2a3c53;border-radius:11px;background:#111b29}article.slicer{border-color:#31566f}small{display:block;margin-top:5px;color:#8fa4bc}.bar{display:block;height:5px;margin-top:8px;overflow:hidden;border-radius:999px;background:#26394c}.bar i{display:block;height:100%;background:#54d776}.actions{display:flex;gap:8px;flex-wrap:wrap}button{padding:8px 10px;border:1px solid #32658b;border-radius:8px;background:#14324b;color:#eef5ff;font-weight:700;cursor:pointer}button.danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}button:disabled{opacity:.4}.notice{padding:10px;margin-bottom:10px;border-radius:9px;background:#102b1d;color:#8ff0b5}.notice.error{background:#3a171d;color:#ffd7dc}@media(max-width:760px){article{grid-template-columns:1fr}}
    </style><section class="page"><div class="head"><div><h1>${title}</h1><p>${description}</p></div><strong>${jobs.length + (this.mode === "tasks" && this.#state.slicer ? 1 : 0)}</strong></div>${this.#message ? `<div class="notice">${esc(this.#message)}</div>` : ""}${error ? `<div class="notice error">${esc(error)}</div>` : ""}<div class="list">${this.#slicerRow()}${jobs.map((job) => this.#row(job)).join("") || (this.#state.slicer ? "" : "<article>Keine Einträge vorhanden.</article>")}</div></section>`;

    this.#root.querySelectorAll<Ultimate3DPrinterActions>("ultimate-3d-printer-actions[data-job]").forEach((panel) => {
      const job = jobs.find((item) => this.#id(item) === panel.dataset.job) || null;
      panel.job = job;
      panel.printer = resolvePrinterForJob(job, this.#state.printers);
      panel.capabilities = this.#state.capabilities;
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-repeat]").forEach((button) => button.addEventListener("click", () => {
      const job = jobs.find((item) => this.#id(item) === button.dataset.repeat);
      if (job) void this.#repeat(job);
    }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-remove]").forEach((button) => button.addEventListener("click", () => {
      const job = jobs.find((item) => this.#id(item) === button.dataset.remove);
      if (job) void this.#remove(job);
    }));
    this.#root.querySelector<HTMLButtonElement>("[data-cancel-slicer]")?.addEventListener("click", () => void this.#cancelSlicer());
  }
}

class Ultimate3DTasksWorkspaceV8 extends JobsWorkspaceV8 { protected readonly mode: Mode = "tasks"; }
class Ultimate3DHistoryWorkspaceV8 extends JobsWorkspaceV8 { protected readonly mode: Mode = "history"; }

if (!customElements.get("ultimate-3d-aufgaben-workspace")) customElements.define("ultimate-3d-aufgaben-workspace", Ultimate3DTasksWorkspaceV8);
if (!customElements.get("ultimate-3d-verlauf-workspace")) customElements.define("ultimate-3d-verlauf-workspace", Ultimate3DHistoryWorkspaceV8);