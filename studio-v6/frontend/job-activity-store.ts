import {
  cancelSliceJob,
  fetchSliceJob,
  type SliceJob,
} from "./slicing-api.js";
import { hasHomeAssistantApi, writeFrontendAudit } from "./ha-api-transport.js";
import { issueSignature, printerIssues } from "./printer-issues.js";
import {
  v6Api,
  type V6CommandCapability,
  type V6Health,
  type V6Job,
  type V6Jobs,
  type V6Printer,
} from "./v6-api.js";

export type JobActivitySnapshot = Readonly<{
  health: V6Health | null;
  slicer: SliceJob | null;
  jobs: V6Jobs;
  printJobs: readonly V6Job[];
  printers: readonly V6Printer[];
  capabilities: readonly V6CommandCapability[];
  updatedAt: number;
  error: string;
}>;

type Listener = (snapshot: JobActivitySnapshot) => void;
type SliceJobCreatedDetail = Readonly<{ job?: SliceJob }>;

const STORAGE_KEY = "ultimate-3d-studio-v6:active-slicer-job";
const POLL_INTERVAL_MS = 2_500;
const ACTIVE_SLICE_STATES = new Set(["queued", "running", "cancelling"]);
const TERMINAL_SLICE_STATES = new Set(["succeeded", "failed", "cancelled", "interrupted"]);
const ACTIVE_PRINT_STATES = new Set(["running", "printing", "pause", "paused", "prepare", "preparing", "starting"]);
const AUTH_ERROR_PATTERN = /(?:401|403|unauthori[sz]ed|forbidden|authentication|authentifizierung|zugriffstoken|access token)/i;

class JobActivityStore {
  readonly #listeners = new Set<Listener>();
  #timer: number | null = null;
  #refreshing = false;
  #authenticationBlocked = false;
  #slicerJobId = "";
  #restoredSlicerJobId = "";
  #slicerCancelPromise: Promise<SliceJob> | null = null;
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
    this.#restoredSlicerJobId = "";
    this.#slicerJobId = job?.id || "";
    this.#persistActiveSlicerJob(job && ACTIVE_SLICE_STATES.has(job.status) ? job.id : "");
    this.#snapshot = { ...this.#snapshot, slicer: job, updatedAt: Date.now(), error: "" };
    this.#emit();
    if (job && ACTIVE_SLICE_STATES.has(job.status)) {
      this.start();
      void this.refresh();
    }
  }

  dismissSlicerJob(jobId?: string): void {
    const currentId = this.#snapshot.slicer?.id || this.#slicerJobId;
    if (jobId && currentId && jobId !== currentId) return;
    this.#slicerJobId = "";
    this.#restoredSlicerJobId = "";
    this.#persistActiveSlicerJob("");
    this.#snapshot = { ...this.#snapshot, slicer: null, updatedAt: Date.now() };
    this.#emit();
  }

  async cancelActiveSlicerJob(jobId: string): Promise<SliceJob> {
    const slicer = this.#snapshot.slicer;
    if (!slicer || slicer.id !== jobId || !ACTIVE_SLICE_STATES.has(slicer.status)) {
      throw new Error("Der Slicerauftrag ist nicht mehr abbrechbar.");
    }
    if (this.#slicerCancelPromise) return this.#slicerCancelPromise;
    const cancelling: SliceJob = { ...slicer, status: "cancelling", cancel_requested: true };
    this.#snapshot = { ...this.#snapshot, slicer: cancelling, updatedAt: Date.now() };
    this.#emit();
    this.#slicerCancelPromise = cancelSliceJob(jobId);
    try {
      const updated = await this.#slicerCancelPromise;
      if (this.#slicerJobId === jobId) this.registerSlicerJob(updated);
      return updated;
    } catch (error) {
      if (this.#slicerJobId === jobId) this.registerSlicerJob(slicer);
      throw error;
    } finally {
      this.#slicerCancelPromise = null;
    }
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
    try {
      const [health, jobs, printers, capabilities, slicer] = await Promise.all([
        v6Api.getHealth(),
        v6Api.getJobs(),
        v6Api.getPrinters(),
        v6Api.getCapabilities(),
        this.#fetchSlicer(),
      ]);
      this.#snapshot = {
        health,
        slicer,
        jobs,
        printJobs: this.#activePrintJobs(jobs),
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
      this.#snapshot = { ...this.#snapshot, updatedAt: Date.now(), error: message };
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
    } catch {
      if (this.#slicerJobId !== requestedJobId) return null;
      return this.#snapshot.slicer?.id === requestedJobId ? this.#snapshot.slicer : null;
    }
  }

  #persistActiveSlicerJob(jobId: string): void {
    try {
      if (jobId) globalThis.localStorage?.setItem(STORAGE_KEY, jobId);
      else globalThis.localStorage?.removeItem(STORAGE_KEY);
    } catch {}
  }

  #activePrintJobs(jobs: V6Jobs): V6Job[] {
    const current = (jobs.current || []).filter((job) => {
      const state = String(job.status || "").toLowerCase();
      return !state || ACTIVE_PRINT_STATES.has(state);
    });
    return [...current, ...(jobs.queue || [])];
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