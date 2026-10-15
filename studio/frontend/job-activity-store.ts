import {
  fetchSliceJob,
  type SliceJob,
} from "./slicing-api.js";
import { hasHomeAssistantApi, writeFrontendAudit } from "./ha-api-transport.js";
import { issueSignature, printerIssues } from "./printer-issues.js";
import {
  studioApi,
  type StudioCommandCapability,
  type StudioHealth,
  type StudioJob,
  type StudioJobs,
  type StudioPrinter,
} from "./studio-api.js";

export type JobActivitySnapshot = Readonly<{
  health: StudioHealth | null;
  slicer: SliceJob | null;
  jobs: StudioJobs;
  printJobs: readonly StudioJob[];
  printers: readonly StudioPrinter[];
  capabilities: readonly StudioCommandCapability[];
  updatedAt: number;
  error: string;
}>;

type Listener = (snapshot: JobActivitySnapshot) => void;
type SliceJobCreatedDetail = Readonly<{ job?: SliceJob }>;

const STORAGE_KEY = "ultimate-3d-studio:active-slicer-job";
const POLL_INTERVAL_MS = 2_500;
const ACTIVE_SLICE_STATES = new Set(["queued", "running", "cancelling"]);
const TERMINAL_SLICE_STATES = new Set(["succeeded", "failed", "cancelled", "interrupted"]);
const ACTIVE_PRINT_STATES = new Set(["running", "printing", "pause", "paused", "prepare", "preparing", "starting"]);
const INACTIVE_CONNECTION_STATES = new Set(["offline", "disconnected", "unavailable", "unknown", "failed", "error"]);

export function activePrintJobs(jobs: StudioJobs, printers: readonly StudioPrinter[]): StudioJob[] {
  const current = (jobs.current || []).filter((job) => {
    const jobState = String(job.status || "").trim().toLowerCase();
    if (jobState && !ACTIVE_PRINT_STATES.has(jobState)) return false;

    const printerId = String(job.printer_id || "").trim();
    const printer = printers.find((item) => String(item.printer_id || "").trim() === printerId)
      ?? (!printerId && printers.length === 1 ? printers[0] : null);
    if (!printer) return false;

    const printerState = String(printer.printer_state || "").trim().toLowerCase();
    if (!ACTIVE_PRINT_STATES.has(printerState)) return false;

    const connectionState = String(printer.connection_state || "").trim().toLowerCase();
    if (connectionState && INACTIVE_CONNECTION_STATES.has(connectionState)) return false;
    return true;
  });
  return [...current, ...(jobs.queue || [])];
}

const AUTH_ERROR_PATTERN = /(?:401|403|unauthori[sz]ed|forbidden|authentication|authentifizierung|zugriffstoken|access token)/i;

class JobActivityStore {
  readonly #listeners = new Set<Listener>();
  #timer: number | null = null;
  #refreshing = false;
  #authenticationBlocked = false;
  #slicerJobId = "";
  #restoredSlicerJobId = "";
  #slicerRevision = 0;
  #lastAuditFingerprint = "";
  #snapshot: JobActivitySnapshot = {
    health: null,
    slicer: null,
    jobs: {},
    printJobs: [],
    printers: [],
    capabilities: [],
    updatedAt: 0,
    error: "",
  };

  constructor() {
    try {
      this.#slicerJobId = globalThis.localStorage?.getItem(STORAGE_KEY) || "";
      this.#restoredSlicerJobId = this.#slicerJobId;
    } catch {
      this.#slicerJobId = "";
      this.#restoredSlicerJobId = "";
    }
    globalThis.addEventListener?.("ultimate-3d-ha-api-ready", this.#apiReady);
    globalThis.addEventListener?.("ultimate-3d-slice-job-created", this.#sliceJobCreated as EventListener);
  }

  get snapshot(): JobActivitySnapshot {
    return this.#snapshot;
  }

  subscribe(listener: Listener): () => void {
    this.#listeners.add(listener);
    listener(this.#snapshot);
    this.start();
    return () => {
      this.#listeners.delete(listener);
      if (!this.#listeners.size) this.stop();
    };
  }

  registerSlicerJob(job: SliceJob | null): void {
    this.#slicerRevision += 1;
    this.#restoredSlicerJobId = "";
    this.#slicerJobId = job?.id || "";
    this.#persistActiveSlicerJob(job && ACTIVE_SLICE_STATES.has(job.status) ? job.id : "");
    this.#snapshot = { ...this.#snapshot, slicer: job };
    this.#emit();
    if (job && ACTIVE_SLICE_STATES.has(job.status)) {
      this.start();
      void this.refresh();
    }
  }

  dismissSlicerJob(jobId?: string): void {
    const currentId = this.#snapshot.slicer?.id || this.#slicerJobId;
    if (jobId && currentId && jobId !== currentId) return;
    this.#slicerRevision += 1;
    this.#slicerJobId = "";
    this.#restoredSlicerJobId = "";
    this.#persistActiveSlicerJob("");
    this.#snapshot = { ...this.#snapshot, slicer: null };
    this.#emit();
  }

  start(): void {
    if (this.#timer !== null || this.#authenticationBlocked || !hasHomeAssistantApi()) return;
    void this.refresh();
    this.#timer = window.setInterval(() => void this.refresh(), POLL_INTERVAL_MS);
  }

  stop(): void {
    if (this.#timer !== null) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  async refresh(): Promise<void> {
    if (this.#refreshing || this.#authenticationBlocked || !hasHomeAssistantApi()) return;
    this.#refreshing = true;
    const slicerRevision = this.#slicerRevision;
    try {
      const [health, jobs, printers, capabilities, slicer] = await Promise.all([
        studioApi.getHealth(),
        studioApi.getJobs(),
        studioApi.getPrinters(),
        studioApi.getCapabilities(),
        this.#fetchSlicer(),
      ]);
      this.#snapshot = {
        health,
        slicer: slicerRevision === this.#slicerRevision ? slicer : this.#snapshot.slicer,
        jobs,
        printJobs: activePrintJobs(jobs, printers),
        printers,
        capabilities,
        updatedAt: Date.now(),
        error: "",
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (AUTH_ERROR_PATTERN.test(message)) {
        this.#authenticationBlocked = true;
        this.stop();
      }
      this.#snapshot = { ...this.#snapshot, error: message };
    } finally {
      this.#refreshing = false;
    }
    this.#emit();
  }

  readonly #apiReady = (): void => {
    this.#authenticationBlocked = false;
    if (this.#listeners.size || this.#slicerJobId) this.start();
  };

  readonly #sliceJobCreated = (event: CustomEvent<SliceJobCreatedDetail>): void => {
    const job = event.detail?.job;
    if (job?.id) this.registerSlicerJob(job);
  };

  async #fetchSlicer(): Promise<SliceJob | null> {
    const requestedJobId = this.#slicerJobId;
    if (!requestedJobId) return null;
    try {
      const job = await fetchSliceJob(requestedJobId);
      if (this.#slicerJobId !== requestedJobId) return null;
      if (ACTIVE_SLICE_STATES.has(job.status)) {
        this.#restoredSlicerJobId = "";
        this.#persistActiveSlicerJob(job.id);
        return job;
      }
      if (TERMINAL_SLICE_STATES.has(job.status)) {
        this.#persistActiveSlicerJob("");
        if (this.#restoredSlicerJobId === requestedJobId) {
          this.#slicerJobId = "";
          this.#restoredSlicerJobId = "";
          return null;
        }
        return job;
      }
      this.#slicerJobId = "";
      this.#restoredSlicerJobId = "";
      this.#persistActiveSlicerJob("");
      return null;
    } catch (error) {
      if (this.#slicerJobId !== requestedJobId) return null;
      // Preserve the complete last successful snapshot and its timestamp in
      // refresh(). An unavailable slicer must not turn cached progress fresh.
      throw error;
    }
  }

  #persistActiveSlicerJob(jobId: string): void {
    try {
      if (jobId) globalThis.localStorage?.setItem(STORAGE_KEY, jobId);
      else globalThis.localStorage?.removeItem(STORAGE_KEY);
    } catch {}
  }

  #auditSnapshot(): void {
    const printer = this.#snapshot.printers[0];
    const issues = printerIssues(printer);
    const slicer = this.#snapshot.slicer;
    const printJob = this.#snapshot.printJobs[0];
    const fingerprint = JSON.stringify({
      error: this.#snapshot.error,
      slicer: slicer ? [slicer.id, slicer.status, slicer.error] : null,
      print: printJob ? [printJob.id, printJob.status, printJob.progress, printJob.current_layer] : null,
      printer: printer ? [
        printer.printer_id,
        printer.connection_state,
        printer.printer_state,
        printer.print_stage,
        printer.progress,
        issueSignature(printer),
      ] : null,
      queue: this.#snapshot.jobs.queue?.length ?? 0,
    });
    if (fingerprint === this.#lastAuditFingerprint) return;
    this.#lastAuditFingerprint = fingerprint;
    writeFrontendAudit({
      category: issues.length ? "Druck" : slicer ? "Slicer" : printJob ? "Druck" : "System",
      component: "job-activity-store",
      event: issues.length ? "printer_issue_state_changed" : "runtime_state_changed",
      status: this.#snapshot.error || issues.some((issue) => issue.severity === "error") ? "error" : issues.length ? "warning" : "info",
      job_id: String(slicer?.id || printJob?.id || "") || undefined,
      printer_id: String(printer?.printer_id || "") || undefined,
      details: {
        error: this.#snapshot.error || null,
        slicer_status: slicer?.status || null,
        slicer_error: slicer?.error || null,
        print_status: printJob?.status || null,
        print_progress: printJob?.progress ?? null,
        print_stage: printer?.print_stage || null,
        printer_state: printer?.printer_state || null,
        connection_state: printer?.connection_state || null,
        active_issue_count: issues.length,
        active_issues: issues,
        queue_count: this.#snapshot.jobs.queue?.length ?? 0,
      },
    });
  }

  #emit(): void {
    this.#auditSnapshot();
    for (const listener of this.#listeners) listener(this.#snapshot);
  }
}

export const jobActivityStore = new JobActivityStore();
