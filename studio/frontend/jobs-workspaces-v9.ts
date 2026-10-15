import "./printer-command-store.js";
import "./studio-action-dialog.js";
import { errorMessage } from "./ha-api-transport.js";
import { lookupHistoryStorageFile } from "./history-storage-api.js";
import {
  jobActivityStore,
  type JobActivitySnapshot,
} from "./job-activity-store.js";
import {
  isQueuedJob,
  printStatusLabel,
  resolvePrinterForJob,
} from "./printer-command-policy.js";
import { remainingTimeLabel } from "./print-remaining-time.js";
import { PrinterStorageApi } from "./printer-storage-api.js";
import type { Ultimate3DPrinterActions } from "./printer-command-store.js";
import type { StudioActionDialog } from "./studio-action-dialog.js";
import { parseRoute } from "./router.js";
import { studioApi, type StudioJob } from "./studio-api.js";
import { profileApplicationSummary } from "./profile-application-status.js";

type Mode = "tasks" | "history";

const esc = (value: unknown): string => String(value ?? "").replace(
  /[&<>"']/g,
  (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char] || char),
);

function jobId(job: StudioJob): string {
  return String(job.job_id || job.id || "");
}

function jobFile(job: StudioJob): string {
  return String(job.file || job.model_name || "Unbenanntes Modell");
}

function dateLabel(value: unknown): string {
  const date = new Date(String(value || ""));
  return Number.isNaN(date.getTime()) ? "–" : date.toLocaleString("de-DE");
}

function durationLabel(value: unknown): string {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "–";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = Math.floor(seconds % 60);
  return hours
    ? `${hours} h ${minutes} min`
    : minutes
      ? `${minutes} min ${rest} s`
      : `${rest} s`;
}

abstract class JobsWorkspaceV9 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #storage = new PrinterStorageApi();
  #state: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #busy = "";
  #dialogActive = false;
  #lastFocusedJobId = "";
  protected abstract readonly mode: Mode;

  connectedCallback(): void {
    if (this.#unsubscribe) return;
    this.#mount();
    this.#unsubscribe = jobActivityStore.subscribe((state) => {
      this.#state = state;
      if (!this.#dialogActive) this.#renderData();
    });
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  #dialog(): StudioActionDialog | null {
    return this.#root.querySelector<StudioActionDialog>("studio-action-dialog");
  }

  async #confirm(
    request: Parameters<StudioActionDialog["confirm"]>[0],
  ): Promise<boolean> {
    const dialog = this.#dialog();
    if (!dialog) return false;
    this.#dialogActive = true;
    try {
      return await dialog.confirm(request);
    } finally {
      this.#dialogActive = false;
    }
  }

  #mount(): void {
    const title = this.mode === "tasks" ? "Aufgaben" : "Verlauf";
    const description = this.mode === "tasks"
      ? "Aktive, pausierte und wartende Druck- und Sliceraufträge."
      : "Druckhistorie und zugehörige Dateien auf der Drucker-SD-Karte.";
    this.#root.innerHTML = `<style>
      :host{display:block;height:100%;min-height:0;background:#08101a;color:#eef5ff}*{box-sizing:border-box}.page{display:grid;grid-template-rows:auto auto minmax(0,1fr);height:100%;min-height:620px;padding:16px}.head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding-bottom:12px}.head h1{margin:0}.head p{margin:5px 0 0;color:#91a5bb}.head-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.count{min-width:38px;padding:8px;border:1px solid #31506e;border-radius:999px;text-align:center}.notice{display:none;margin-bottom:10px;padding:10px;border:1px solid #27734c;border-radius:9px;background:#102b1d;color:#8ff0b5}.notice.visible{display:block}.notice.error{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}.list{min-height:0;overflow:auto;scrollbar-gutter:stable;padding-right:3px}.row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;margin-bottom:9px;padding:12px;border:1px solid #2a3c53;border-radius:11px;background:#111b29}.row:last-child{margin-bottom:0}.row.slicer{border-color:#31566f}.row.selected{border-color:#42c8ff;background:#10283a;box-shadow:0 0 0 1px #42c8ff55,0 10px 28px #0005}.row strong,.row small{display:block}.row small{margin-top:5px;color:#8fa4bc;overflow-wrap:anywhere}.bar{display:block;height:5px;margin-top:8px;overflow:hidden;border-radius:999px;background:#26394c}.bar i{display:block;height:100%;background:#54d776}.actions{display:flex;justify-content:flex-end;gap:7px;flex-wrap:wrap;max-width:560px}button{min-height:36px;padding:7px 10px;border:1px solid #32658b;border-radius:8px;background:#14324b;color:#eef5ff;font-weight:700;cursor:pointer}button.secondary{border-color:#566d82;background:#162331}button.danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}button:disabled{opacity:.4;cursor:not-allowed}.empty{display:grid;place-items:center;min-height:220px;border:1px dashed #2a3c53;border-radius:11px;color:#8298ae}@media(max-width:900px){.row{grid-template-columns:1fr}.actions{justify-content:flex-start;max-width:none}}@media(max-width:620px){.page{padding:9px}.head{display:block}.head-actions{margin-top:9px}.actions{display:grid;grid-template-columns:1fr 1fr}.actions button{width:100%}}
    </style><section class="page"><header class="head"><div><h1>${title}</h1><p>${description}</p></div><div class="head-actions">${this.mode === "history" ? '<button class="danger" id="clear-history">Verlauf vollständig leeren</button>' : ""}<button id="refresh">Aktualisieren</button><strong class="count" id="count">0</strong></div></header><div class="notice" id="notice"></div><main class="list" id="list"></main><studio-action-dialog></studio-action-dialog></section>`;
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener(
      "click",
      () => void this.#refresh(),
    );
    this.#root.querySelector<HTMLButtonElement>("#clear-history")?.addEventListener(
      "click",
      () => void this.#clearHistory(),
    );
    this.#renderData();
  }

  #jobs(): StudioJob[] {
    return this.mode === "history"
      ? this.#state.jobs.history || []
      : [
          ...(this.#state.jobs.current || []),
          ...(this.#state.jobs.queue || []),
        ];
  }

  #routeJobId(): string {
    if (this.mode !== "tasks") return "";
    const route = parseRoute(globalThis.location?.hash || "#/aufgaben");
    return route.name === "aufgaben" ? String(route.jobId || "") : "";
  }

  #renderData(): void {
    const host = this.#root.querySelector<HTMLElement>("#list");
    const count = this.#root.querySelector<HTMLElement>("#count");
    if (!host || !count) return;
    const jobs = this.#jobs();
    const scrollTop = host.scrollTop;
    const focusedJobId = this.#routeJobId();
    const slicer = this.mode === "tasks" ? this.#slicerMarkup() : "";
    host.innerHTML = `${slicer}${jobs.map((job) => this.#rowMarkup(job, focusedJobId)).join("")}`;
    if (!slicer && !jobs.length) {
      host.innerHTML = '<div class="empty">Keine Einträge vorhanden.</div>';
    }
    host.scrollTop = Math.min(scrollTop, host.scrollHeight);
    count.textContent = String(
      jobs.length + (this.mode === "tasks" && this.#state.slicer ? 1 : 0),
    );
    this.#bindRows(jobs);
    this.#updateControls();
    if (focusedJobId && focusedJobId !== this.#lastFocusedJobId) {
      this.#lastFocusedJobId = focusedJobId;
      queueMicrotask(() => {
        const row = [...this.#root.querySelectorAll<HTMLElement>("[data-job-row]")]
          .find((item) => item.dataset.jobRow === focusedJobId);
        row?.scrollIntoView({ block: "center", behavior: "smooth" });
      });
    } else if (!focusedJobId) {
      this.#lastFocusedJobId = "";
    }
  }

  #rowMarkup(job: StudioJob, focusedJobId = ""): string {
    const rawId = jobId(job);
    const id = esc(rawId);
    const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
    const queued = isQueuedJob(job);
    if (this.mode === "history") {
      return `<article class="row"><div><strong>${esc(jobFile(job))}</strong><small>${esc(job.printer_name || job.printer_id || "Drucker")} · ${esc(printStatusLabel(job.status))}<br>${dateLabel(job.completed_at || job.updated_at || job.started_at)} · ${durationLabel(job.duration_seconds)}</small><span class="bar"><i style="width:${progress}%"></i></span></div><div class="actions"><button data-repeat="${id}">Erneut einreihen</button><button class="secondary" data-download="${id}">SD-Datei herunterladen</button><button class="danger" data-delete-storage="${id}">SD-Datei löschen</button><button class="danger" data-remove-history="${id}">Verlauf entfernen</button></div></article>`;
    }
    const printer = resolvePrinterForJob(job, this.#state.printers);
    const remaining = remainingTimeLabel(job, printer);
    const actions = queued
      ? `<button class="danger" data-remove-queue="${id}">Aus Warteschlange</button>`
      : `<ultimate-3d-printer-actions data-job="${id}"></ultimate-3d-printer-actions>`;
    const timing = queued ? "Start ausstehend" : `Restzeit ${remaining}`;
    const selected = Boolean(rawId && rawId === focusedJobId);
    return `<article class="row${selected ? " selected" : ""}" data-job-row="${id}"><div><strong>${esc(jobFile(job))}</strong><small>${esc(job.printer_name || job.printer_id || "Drucker")} · ${esc(printStatusLabel(job.status))} · ${progress}% · ${esc(timing)}</small><span class="bar"><i style="width:${progress}%"></i></span></div><div class="actions">${actions}</div></article>`;
  }

  #slicerMarkup(): string {
    const job = this.#state.slicer;
    if (!job) return "";
    return `<article class="row slicer"><div><strong>${esc(job.model_file || job.output_file || "Slicer-Auftrag")}</strong><small>Slicer · ${esc(job.status)}<br>${esc(profileApplicationSummary(job.profile_application))}</small></div></article>`;
  }

  #bindRows(jobs: StudioJob[]): void {
    this.#root.querySelectorAll<Ultimate3DPrinterActions>(
      "ultimate-3d-printer-actions[data-job]",
    ).forEach((panel) => {
      const job = jobs.find((item) => jobId(item) === panel.dataset.job) || null;
      panel.job = job;
      panel.printer = resolvePrinterForJob(job, this.#state.printers);
      panel.capabilities = this.#state.capabilities;
    });
    const bind = (
      selector: string,
      handler: (job: StudioJob) => Promise<void>,
      dataKey: string,
    ): void => {
      this.#root.querySelectorAll<HTMLButtonElement>(selector).forEach((button) => {
        button.addEventListener("click", () => {
          const id = button.dataset[dataKey];
          const job = jobs.find((item) => jobId(item) === id);
          if (job) void handler(job);
        });
      });
    };
    bind("[data-repeat]", (job) => this.#repeat(job), "repeat");
    bind("[data-remove-queue]", (job) => this.#removeQueue(job), "removeQueue");
    bind("[data-remove-history]", (job) => this.#removeHistory(job), "removeHistory");
    bind("[data-download]", (job) => this.#downloadStorage(job), "download");
    bind("[data-delete-storage]", (job) => this.#deleteStorage(job), "deleteStorage");
  }

  async #repeat(job: StudioJob): Promise<void> {
    const id = jobId(job);
    if (!id || this.#busy) return;
    const confirmed = await this.#confirm({
      title: "Druck erneut einreihen",
      message: "Diesen Auftrag erneut in die Warteschlange übernehmen?",
      detail: `${jobFile(job)}\nDer Druck startet nicht automatisch.`,
      confirmLabel: "Einreihen",
    });
    if (!confirmed) return;
    await this.#run(id, async () => {
      await studioApi.repeatJob(id);
      return "Auftrag wurde erneut eingereiht.";
    });
  }

  async #removeQueue(job: StudioJob): Promise<void> {
    const id = jobId(job);
    if (!id || this.#busy) return;
    const confirmed = await this.#confirm({
      title: "Aus Warteschlange entfernen",
      message: "Diesen wartenden Auftrag entfernen?",
      detail: jobFile(job),
      confirmLabel: "Entfernen",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run(id, async () => {
      await studioApi.removeQueuedJob(id);
      return "Auftrag wurde aus der Warteschlange entfernt.";
    });
  }

  async #removeHistory(job: StudioJob): Promise<void> {
    const id = jobId(job);
    if (!id || this.#busy) return;
    const confirmed = await this.#confirm({
      title: "Verlaufseintrag entfernen",
      message: "Nur diesen lokalen Verlaufseintrag entfernen?",
      detail: `${jobFile(job)}\nEine vorhandene SD-Datei bleibt erhalten.`,
      confirmLabel: "Verlauf entfernen",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run(id, async () => {
      await studioApi.removeHistoryJob(id);
      return "Verlaufseintrag wurde entfernt.";
    });
  }

  async #clearHistory(): Promise<void> {
    const jobs = this.#jobs();
    if (!jobs.length || this.#busy) return;
    const confirmed = await this.#confirm({
      title: "Verlauf vollständig leeren",
      message: `${jobs.length} lokale Verlaufseinträge dauerhaft entfernen?`,
      detail: "Dateien auf der Drucker-SD-Karte werden dabei nicht gelöscht.",
      confirmLabel: "Verlauf leeren",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run("clear-history", async () => {
      const result = await studioApi.clearHistory();
      return `${result.removed} Verlaufseinträge wurden entfernt.`;
    });
  }

  async #storageItem(job: StudioJob) {
    const printerId = String(job.printer_id || "").trim();
    const filename = jobFile(job).trim();
    if (!printerId || !filename) return null;
    return await lookupHistoryStorageFile(printerId, filename);
  }

  async #downloadStorage(job: StudioJob): Promise<void> {
    const id = jobId(job);
    if (!id || this.#busy) return;
    await this.#run(id, async () => {
      const item = await this.#storageItem(job);
      if (!item) {
        throw new Error(
          "Die zugehörige Datei ist nicht mehr auf der Drucker-SD-Karte vorhanden.",
        );
      }
      const file = await this.#storage.download(String(job.printer_id), item);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      return `${file.name} wurde heruntergeladen.`;
    }, false);
  }

  async #deleteStorage(job: StudioJob): Promise<void> {
    const id = jobId(job);
    if (!id || this.#busy) return;
    const item = await this.#storageItem(job).catch((error) => {
      this.#notice(errorMessage(error), true);
      return null;
    });
    if (!item) {
      this.#notice(
        "Die zugehörige Datei ist nicht mehr auf der Drucker-SD-Karte vorhanden.",
        true,
      );
      return;
    }
    const confirmed = await this.#confirm({
      title: "Datei vom Drucker löschen",
      message: "Diese Datei dauerhaft von der Drucker-SD-Karte löschen?",
      detail: item.path,
      confirmLabel: "SD-Datei löschen",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run(id, async () => {
      await this.#storage.action(
        String(job.printer_id),
        "delete",
        { path: item.path },
      );
      return "Datei wurde von der Drucker-SD-Karte gelöscht.";
    }, false);
  }


  async #refresh(): Promise<void> {
    if (this.#busy) return;
    try {
      await jobActivityStore.refresh();
      this.#notice("Daten wurden aktualisiert.", false);
    } catch (error) {
      this.#notice(errorMessage(error), true);
    }
  }

  async #run(
    busyId: string,
    operation: () => Promise<string>,
    refresh = true,
  ): Promise<void> {
    if (this.#busy) return;
    this.#busy = busyId;
    this.#updateControls();
    try {
      const message = await operation();
      if (refresh) await jobActivityStore.refresh();
      this.#notice(message, false);
    } catch (error) {
      this.#notice(errorMessage(error), true);
    } finally {
      this.#busy = "";
      this.#renderData();
    }
  }

  #updateControls(): void {
    this.#root.querySelectorAll<HTMLButtonElement>("button").forEach((button) => {
      if (!button.closest("studio-action-dialog")) button.disabled = Boolean(this.#busy);
    });
  }

  #notice(message: string, error: boolean): void {
    const notice = this.#root.querySelector<HTMLElement>("#notice");
    if (!notice) return;
    notice.textContent = message;
    notice.className = `notice visible${error ? " error" : ""}`;
  }
}

class Ultimate3DTasksWorkspaceV9 extends JobsWorkspaceV9 {
  protected readonly mode: Mode = "tasks";
}

class Ultimate3DHistoryWorkspaceV9 extends JobsWorkspaceV9 {
  protected readonly mode: Mode = "history";
}

if (!customElements.get("ultimate-3d-aufgaben-workspace")) {
  customElements.define(
    "ultimate-3d-aufgaben-workspace",
    Ultimate3DTasksWorkspaceV9,
  );
}
if (!customElements.get("ultimate-3d-verlauf-workspace")) {
  customElements.define(
    "ultimate-3d-verlauf-workspace",
    Ultimate3DHistoryWorkspaceV9,
  );
}
