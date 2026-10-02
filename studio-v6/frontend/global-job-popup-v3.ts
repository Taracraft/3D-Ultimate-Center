import "./printer-camera-panel.js";
import "./printer-command-store.js";
import { Ultimate3DPrintSpeedControl } from "./print-speed-control.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import type { PrinterCameraPanel } from "./printer-camera-panel.js";
import type { Ultimate3DPrinterActions } from "./printer-command-store.js";
import {
  issueMarkup,
  issueSignature,
  PRINTER_ISSUE_STYLES,
  primaryPrinterIssue,
  printerIssues,
} from "./printer-issues.js";
import { remainingTimeLabel, remainingTimeMinutes } from "./print-remaining-time.js";
import type { SliceJob } from "./slicing-api.js";
import { profileApplicationSummary, processValueProofMarkup, PROCESS_VALUE_PROOF_STYLES } from "./profile-application-status.js";
import { nativeSlicerProgress, slicerActivityLabel, slicerEtaSeconds, slicerProgressPercent } from "./slicer-telemetry.js";
import type { V6Job, V6Printer } from "./v6-api.js";
import { PRINT_PHASES } from "./print-phase-progress.js";
import { printLayerLabel, printSpeedLabel, resolveLivePrintPhase } from "./print-live-telemetry.js";
import { SLICE_ACTIVITY_EVENT, type SliceActivityDetail, type SliceActivityStatus } from "./slice-activity-events.js";
import { STUDIO_OPERATION_EVENT, type StudioOperationDetail, type StudioOperationKind, type StudioOperationStatus } from "./studio-operation-events.js";
import { DIRECT_PRINT_TRANSFER_EVENT, type DirectPrintTransferDetail } from "./direct-print-transfer-events.js";

type HassLike = Readonly<{ states: Readonly<Record<string, unknown>> }>;
type SlicePreparationDetail = Readonly<{
  active: boolean;
  id: string;
  fileName: string;
  plateName: string;
  phase: string;
  progress: number;
}>;
type SliceActivityEntry = Readonly<{
  at: string;
  code: string;
  label: string;
  detail: string;
  progress: number | null;
  status: SliceActivityStatus;
  metrics?: SliceActivityDetail["metrics"];
}>;
type SliceActivityTrace = {
  traceId: string;
  jobId: string;
  fileName: string;
  plateName: string;
  active: boolean;
  entries: SliceActivityEntry[];
};
type StudioOperationEntry = Readonly<{
  at: string;
  code: string;
  label: string;
  detail: string;
  progress: number | null;
  status: StudioOperationStatus;
  metrics?: StudioOperationDetail["metrics"];
}>;
type StudioOperationTrace = {
  traceId: string;
  kind: StudioOperationKind;
  fileName: string;
  source: string;
  active: boolean;
  entries: StudioOperationEntry[];
};
const ACTIVE = new Set(["queued", "running", "cancelling"]);
const DISMISSED_KEY = "ultimate-3d-studio-v6:job-popup-dismissed";
const DISMISSED_ITEMS_KEY = "ultimate-3d-studio-v6:job-popup-dismissed-items-v1";
const SLICE_ACTIVITY_STORAGE_KEY = "ultimate-3d-studio-v6:slice-activity-trace-v1";
const STUDIO_OPERATION_STORAGE_KEY = "ultimate-3d-studio-v6:studio-operation-trace-v1";
const DIRECT_PRINT_TRANSFER_STORAGE_KEY = "ultimate-3d-studio-v6:direct-print-transfer-v1";
const esc = (value: unknown): string => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char] || char));
const percent = (value: unknown): number => Math.max(0, Math.min(100, Number(value) || 0));
const idOf = (job: V6Job): string => String(job.job_id || job.id || "");
const timeLabel = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "--:--:--" : date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};
const formatBytes = (value: unknown): string => {
  const bytes = Math.max(0, Number(value) || 0);
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  let amount = bytes;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  const digits = index === 0 ? 0 : amount >= 100 ? 0 : amount >= 10 ? 1 : 2;
  return `${amount.toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits })} ${units[index]}`;
};
const formatRate = (value: unknown): string => `${formatBytes(value)}/s`;
const formatDuration = (value: unknown): string => {
  const seconds = Math.max(0, Number(value) || 0);
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes} min ${rest.toString().padStart(2, "0")} s`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${(minutes % 60).toString().padStart(2, "0")} min`;
};
const PREVIEW_CODES = new Set([
  "toolpath_parse_started",
  "toolpath_summary_ready",
  "preview_chunk_loaded",
  "render_data_ready",
  "preview_ready",
  "slice_pipeline_failed",
]);

function positive(value: unknown): number | null {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : null;
}

function nonNegative(value: unknown): number | null {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue >= 0 ? numberValue : null;
}

function previewProgress(detail: Pick<SliceActivityEntry, "code" | "metrics">): number | null {
  if (detail.code === "render_data_ready" || detail.code === "preview_ready") return 100;
  if (detail.code === "toolpath_summary_ready") return 0;
  if (detail.code !== "preview_chunk_loaded") return null;
  const loadedLayers = nonNegative(detail.metrics?.loadedLayers);
  const layerCount = positive(detail.metrics?.layerCount);
  if (loadedLayers !== null && layerCount !== null) {
    return Math.min(100, Math.max(0, (loadedLayers / layerCount) * 100));
  }
  const loadedSegments = nonNegative(detail.metrics?.loadedSegmentCount);
  const segmentCount = positive(detail.metrics?.segmentCount);
  if (loadedSegments !== null && segmentCount !== null) {
    return Math.min(100, Math.max(0, (loadedSegments / segmentCount) * 100));
  }
  return null;
}

function remainingSeconds(metrics?: SliceActivityEntry["metrics"]): number | null {
  const reportedEta = positive(metrics?.etaSeconds);
  if (reportedEta !== null) return reportedEta;

  const segmentCount = positive(metrics?.segmentCount);
  const loadedSegments = nonNegative(metrics?.loadedSegmentCount);
  const segmentRate = positive(metrics?.segmentRatePerSecond);
  if (segmentCount !== null && loadedSegments !== null && segmentRate !== null) {
    return Math.max(0, (segmentCount - loadedSegments) / segmentRate);
  }

  const layerCount = positive(metrics?.layerCount);
  const loadedLayers = nonNegative(metrics?.loadedLayers);
  const layerRate = positive(metrics?.layerRatePerSecond);
  if (layerCount !== null && loadedLayers !== null && layerRate !== null) {
    return Math.max(0, (layerCount - loadedLayers) / layerRate);
  }
  return null;
}

function metricText(detail: Pick<SliceActivityEntry, "code" | "metrics">): string {
  const metrics = detail.metrics;
  const parts: string[] = [];
  const loadedLayers = nonNegative(metrics?.loadedLayers);
  const layerCount = positive(metrics?.layerCount);
  if (loadedLayers !== null && layerCount !== null) {
    parts.push(`${Math.min(loadedLayers, layerCount).toLocaleString("de-DE")} / ${layerCount.toLocaleString("de-DE")} Layer`);
  } else if (layerCount !== null) {
    parts.push(`${layerCount.toLocaleString("de-DE")} Layer erkannt`);
  }
  const loadedSegments = nonNegative(metrics?.loadedSegmentCount);
  const segmentCount = positive(metrics?.segmentCount);
  if (loadedSegments !== null && segmentCount !== null) {
    parts.push(`${Math.min(loadedSegments, segmentCount).toLocaleString("de-DE")} / ${segmentCount.toLocaleString("de-DE")} Bahnen`);
  } else if (segmentCount !== null) {
    parts.push(`${segmentCount.toLocaleString("de-DE")} Bahnen erkannt`);
  }
  return parts.join(" · ");
}

function rateText(metrics?: SliceActivityEntry["metrics"]): string {
  const parts: string[] = [];
  const layerRate = positive(metrics?.layerRatePerSecond);
  const segmentRate = positive(metrics?.segmentRatePerSecond);
  const elapsed = nonNegative(metrics?.elapsedSeconds);
  if (layerRate !== null) parts.push(`${layerRate.toLocaleString("de-DE", { maximumFractionDigits: 1 })} Layer/s`);
  if (segmentRate !== null) parts.push(`${Math.round(segmentRate).toLocaleString("de-DE")} Bahnen/s`);
  if (elapsed !== null) parts.push(`Laufzeit ${formatDuration(elapsed)}`);
  return parts.join(" · ");
}

type TraceEtaEntry = Readonly<{ at: string; progress: number | null }>;
const estimatedOverallEta = (entries: readonly TraceEtaEntry[], active: boolean): number | null => {
  if (!active || entries.length < 2) return null;
  const samples = entries
    .map((entry) => ({ at: new Date(entry.at).getTime(), progress: entry.progress }))
    .filter((entry): entry is { at: number; progress: number } => Number.isFinite(entry.at) && entry.progress !== null && Number.isFinite(entry.progress));
  if (samples.length < 2) return null;
  const first = samples[0]!;
  const current = samples[samples.length - 1]!;
  if (current.progress >= 100 || current.progress <= first.progress) return null;
  const elapsedSeconds = (current.at - first.at) / 1000;
  const progressed = current.progress - first.progress;
  if (!Number.isFinite(elapsedSeconds) || elapsedSeconds < 1 || progressed < 2) return null;
  const progressPerSecond = progressed / elapsedSeconds;
  const remaining = (100 - current.progress) / progressPerSecond;
  if (!Number.isFinite(remaining) || remaining <= 0 || remaining > 24 * 60 * 60) return null;
  return remaining;
};

export class Ultimate3DGlobalJobPopupV3 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #snapshot: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #remainingTimer: number | null = null;
  #expanded = false;
  #cameraVisible = false;
  #collapsed = false;
  #printerHasIssue(): boolean {
    return printerIssues(this.#primaryPrinter()).length > 0;
  }
  #dismissedSignature = "";
  #dismissedItems = new Set<string>();
  #lastSignature = "";
  #hass: HassLike | null = null;
  #phaseSeen = new Map<string, Set<string>>();
  #preparation: SlicePreparationDetail | null = null;
  #sliceTrace: SliceActivityTrace | null = null;
  #studioTrace: StudioOperationTrace | null = null;
  #directPrintTransfer: DirectPrintTransferDetail | null = null;

  set hass(value: HassLike | null) {
    this.#hass = value;
    this.#forwardHass();
  }

  connectedCallback(): void {
    if (!this.#root.childElementCount) this.#mount();
    if (!this.#sliceTrace) this.#restoreSliceTrace();
    if (!this.#studioTrace) this.#restoreStudioTrace();
    if (!this.#directPrintTransfer) this.#restoreDirectPrintTransfer();
    globalThis.addEventListener("ultimate-3d-slice-preparation", this.#slicePreparation as EventListener);
    globalThis.addEventListener(SLICE_ACTIVITY_EVENT, this.#sliceActivity as EventListener);
    globalThis.addEventListener(STUDIO_OPERATION_EVENT, this.#studioOperation as EventListener);
    globalThis.addEventListener(DIRECT_PRINT_TRANSFER_EVENT, this.#directPrintTransferEvent as EventListener);
    if (!this.#unsubscribe) {
      this.#unsubscribe = jobActivityStore.subscribe((snapshot) => {
        this.#snapshot = snapshot;
        this.#update();
      });
    }
    if (this.#remainingTimer === null) {
      this.#remainingTimer = window.setInterval(() => this.#updateRemainingLabels(), 1000);
    }
  }

  disconnectedCallback(): void {
    globalThis.removeEventListener("ultimate-3d-slice-preparation", this.#slicePreparation as EventListener);
    globalThis.removeEventListener(SLICE_ACTIVITY_EVENT, this.#sliceActivity as EventListener);
    globalThis.removeEventListener(STUDIO_OPERATION_EVENT, this.#studioOperation as EventListener);
    globalThis.removeEventListener(DIRECT_PRINT_TRANSFER_EVENT, this.#directPrintTransferEvent as EventListener);
    this.#unsubscribe?.();
    this.#unsubscribe = null;
    if (this.#remainingTimer !== null) window.clearInterval(this.#remainingTimer);
    this.#remainingTimer = null;
  }

  readonly #slicePreparation = (event: CustomEvent<SlicePreparationDetail>): void => {
    const detail = event.detail;
    if (!detail?.active) {
      if (!this.#preparation || !detail?.id || this.#preparation.id === detail.id) this.#preparation = null;
    } else {
      this.#preparation = { ...detail, progress: percent(detail.progress) };
    }
    this.#update();
  };
  readonly #sliceActivity = (event: CustomEvent<SliceActivityDetail>): void => {
    const detail = event.detail;
    if (!detail?.traceId || !detail.label) return;
    const entry: SliceActivityEntry = {
      at: detail.at || new Date().toISOString(),
      code: detail.code || "slice_activity",
      label: detail.label,
      detail: detail.detail || "",
      progress: detail.progress === null || detail.progress === undefined ? null : percent(detail.progress),
      status: detail.status || "info",
      metrics: detail.metrics,
    };
    const current = this.#sliceTrace;
    const trace: SliceActivityTrace = !current || current.traceId !== detail.traceId
      ? {
          traceId: detail.traceId,
          jobId: detail.jobId || "",
          fileName: detail.fileName || detail.plateName || "Slicerauftrag",
          plateName: detail.plateName || "Druckplatte",
          active: detail.active,
          entries: [],
        }
      : current;
    const last = trace.entries[trace.entries.length - 1];
    const entries = last?.code === entry.code
      ? [...trace.entries.slice(0, -1), entry]
      : [...trace.entries, entry].slice(-160);
    this.#sliceTrace = {
      ...trace,
      jobId: detail.jobId || trace.jobId,
      fileName: detail.fileName || trace.fileName,
      plateName: detail.plateName || trace.plateName,
      active: detail.active,
      entries,
    };
    this.#persistSliceTrace();
    this.#update();
  };

  readonly #studioOperation = (event: CustomEvent<StudioOperationDetail>): void => {
    const detail = event.detail;
    if (!detail?.traceId || !detail.label) return;
    const entry: StudioOperationEntry = {
      at: detail.at || new Date().toISOString(),
      code: detail.code || "studio_operation",
      label: detail.label,
      detail: detail.detail || "",
      progress: detail.progress === null || detail.progress === undefined ? null : percent(detail.progress),
      status: detail.status,
      metrics: detail.metrics,
    };
    const current = this.#studioTrace;
    const trace: StudioOperationTrace = !current || current.traceId !== detail.traceId
      ? {
          traceId: detail.traceId,
          kind: detail.kind,
          fileName: detail.fileName || "Studio-Vorgang",
          source: detail.source || "",
          active: detail.active,
          entries: [],
        }
      : current;
    const last = trace.entries[trace.entries.length - 1];
    const entries = last?.code === entry.code
      ? [...trace.entries.slice(0, -1), entry]
      : [...trace.entries, entry].slice(-240);
    this.#studioTrace = {
      ...trace,
      kind: detail.kind,
      fileName: detail.fileName || trace.fileName,
      source: detail.source || trace.source,
      active: detail.active,
      entries,
    };
    this.#persistStudioTrace();
    this.#update();
  };

  readonly #directPrintTransferEvent = (event: CustomEvent<DirectPrintTransferDetail>): void => {
    const detail = event.detail;
    if (!detail?.traceId || !detail.jobId || !detail.printerId) return;
    const previous = this.#directPrintTransfer?.traceId === detail.traceId
      ? this.#directPrintTransfer
      : null;
    const totalBytes = Math.max(0, Number(detail.totalBytes) || 0);
    const loadedBytes = Math.max(
      previous?.loadedBytes || 0,
      Math.min(totalBytes || Number(detail.loadedBytes) || 0, Number(detail.loadedBytes) || 0),
    );
    const progressValue = detail.status === "success"
      ? 100
      : Math.max(previous?.progress || 0, percent(detail.progress));
    this.#directPrintTransfer = {
      ...detail,
      loadedBytes,
      totalBytes: Math.max(previous?.totalBytes || 0, totalBytes),
      progress: progressValue,
      rateBytesPerSecond: Math.max(0, Number(detail.rateBytesPerSecond) || 0),
    };
    this.#persistDirectPrintTransfer();
    this.#update();
  };

  #restoreDirectPrintTransfer(): void {
    try {
      const raw = sessionStorage.getItem(DIRECT_PRINT_TRANSFER_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as DirectPrintTransferDetail;
      const updatedAt = new Date(String(parsed?.at || "")).getTime();
      if (!parsed?.traceId || !parsed.jobId || !Number.isFinite(updatedAt) || Date.now() - updatedAt > 60 * 60 * 1000) {
        sessionStorage.removeItem(DIRECT_PRINT_TRANSFER_STORAGE_KEY);
        return;
      }
      this.#directPrintTransfer = parsed;
    } catch {
      this.#directPrintTransfer = null;
    }
  }

  #persistDirectPrintTransfer(): void {
    try {
      if (this.#directPrintTransfer) sessionStorage.setItem(DIRECT_PRINT_TRANSFER_STORAGE_KEY, JSON.stringify(this.#directPrintTransfer));
      else sessionStorage.removeItem(DIRECT_PRINT_TRANSFER_STORAGE_KEY);
    } catch {}
  }

  #restoreStudioTrace(): void {
    try {
      const raw = sessionStorage.getItem(STUDIO_OPERATION_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as StudioOperationTrace;
      const last = Array.isArray(parsed?.entries) ? parsed.entries[parsed.entries.length - 1] : null;
      const lastAt = new Date(String(last?.at || "")).getTime();
      if (!parsed?.traceId || !Array.isArray(parsed.entries) || !Number.isFinite(lastAt) || Date.now() - lastAt > 6 * 60 * 60 * 1000) {
        sessionStorage.removeItem(STUDIO_OPERATION_STORAGE_KEY);
        return;
      }
      this.#studioTrace = { ...parsed, entries: parsed.entries.slice(-240) };
    } catch {
      this.#studioTrace = null;
    }
  }

  #persistStudioTrace(): void {
    try {
      if (this.#studioTrace) sessionStorage.setItem(STUDIO_OPERATION_STORAGE_KEY, JSON.stringify(this.#studioTrace));
      else sessionStorage.removeItem(STUDIO_OPERATION_STORAGE_KEY);
    } catch {}
  }

  #studioTraceCurrent(): StudioOperationEntry | null {
    const trace = this.#studioTrace;
    return trace?.entries.length ? trace.entries[trace.entries.length - 1] ?? null : null;
  }

  #studioTraceMarkup(): string {
    const trace = this.#studioTrace;
    if (!trace?.entries.length) return "";
    const startedAt = new Date(trace.entries[0]!.at).getTime();
    const current = trace.entries[trace.entries.length - 1]!;
    const entries = trace.entries.map((entry, index) => {
      const elapsedMs = new Date(entry.at).getTime() - startedAt;
      const elapsed = Number.isFinite(elapsedMs) && elapsedMs >= 0 ? `+${(elapsedMs / 1000).toFixed(1)} s` : "";
      const state = entry.status === "error" ? "error" : index === trace.entries.length - 1 && trace.active ? "running" : "done";
      const icon = state === "error" ? "×" : state === "running" ? "●" : "✓";
      const metrics: string[] = [];
      if (Number(entry.metrics?.loadedPlates) >= 0 && Number(entry.metrics?.plateCount) > 0) metrics.push(`${Number(entry.metrics?.loadedPlates).toLocaleString("de-DE")} / ${Number(entry.metrics?.plateCount).toLocaleString("de-DE")} Platten`);
      if (Number(entry.metrics?.loadedObjects) > 0 && Number(entry.metrics?.objectCount) > 0) metrics.push(`${Number(entry.metrics?.loadedObjects).toLocaleString("de-DE")} / ${Number(entry.metrics?.objectCount).toLocaleString("de-DE")} Objekte/Teile`);
      else if (Number(entry.metrics?.objectCount) > 0) metrics.push(`${Number(entry.metrics?.objectCount).toLocaleString("de-DE")} Objekte/Teile`);
      if (Number(entry.metrics?.triangleCount) > 0) metrics.push(`${Number(entry.metrics?.triangleCount).toLocaleString("de-DE")} Dreiecke`);
      if (Number(entry.metrics?.materialCount) > 0) metrics.push(`${Number(entry.metrics?.materialCount).toLocaleString("de-DE")} Materialien`);
      if (Number(entry.metrics?.inputSizeBytes) > 0) metrics.push(`Eingabe ${formatBytes(entry.metrics?.inputSizeBytes)}`);
      if (Number(entry.metrics?.outputSizeBytes) > 0) metrics.push(`Ausgabe ${formatBytes(entry.metrics?.outputSizeBytes)}`);
      return `<li class="trace-${state}"><time>${esc(timeLabel(entry.at))}<small>${esc(elapsed)}</small></time><span class="trace-dot">${icon}</span><div><b>${esc(entry.label)}</b>${entry.detail ? `<small>${esc(entry.detail)}</small>` : ""}${metrics.length ? `<em>${esc(metrics.join(" · "))}</em>` : ""}</div>${entry.progress !== null ? `<strong>${Math.round(entry.progress)} %</strong>` : ""}</li>`;
    }).join("");
    const title = trace.kind === "import" ? "Importprotokoll" : "Exportprotokoll";
    const source = trace.source ? ` · ${trace.source}` : "";
    const state = current.status === "error" ? "error" : trace.active ? "running" : "done";
    const overallEta = estimatedOverallEta(trace.entries, trace.active);
    const overallEtaText = overallEta !== null ? ` · Gesamt-ETA ~ ${formatDuration(overallEta)}` : "";
    return `<div class="slice-trace-head"><div><b>${title}</b><small>${esc(trace.fileName)}${esc(source)}</small></div><span class="trace-current ${state}">${trace.active ? `LÄUFT${esc(overallEtaText)}` : current.status === "error" ? "FEHLER" : "FERTIG"}</span></div><ol class="slice-trace-list">${entries}</ol>`;
  }

  #restoreSliceTrace(): void {
    try {
      const raw = sessionStorage.getItem(SLICE_ACTIVITY_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as SliceActivityTrace;
      const last = Array.isArray(parsed?.entries) ? parsed.entries[parsed.entries.length - 1] : null;
      const lastAt = new Date(String(last?.at || "")).getTime();
      if (!parsed?.traceId || !Array.isArray(parsed.entries) || !Number.isFinite(lastAt) || Date.now() - lastAt > 6 * 60 * 60 * 1000) {
        sessionStorage.removeItem(SLICE_ACTIVITY_STORAGE_KEY);
        return;
      }
      this.#sliceTrace = { ...parsed, entries: parsed.entries.slice(-160) };
    } catch {
      this.#sliceTrace = null;
    }
  }

  #persistSliceTrace(): void {
    try {
      if (this.#sliceTrace) sessionStorage.setItem(SLICE_ACTIVITY_STORAGE_KEY, JSON.stringify(this.#sliceTrace));
      else sessionStorage.removeItem(SLICE_ACTIVITY_STORAGE_KEY);
    } catch {}
  }

  #sliceActivityCurrent(job: SliceJob | null): SliceActivityEntry | null {
    const trace = this.#sliceTrace;
    if (!trace?.entries.length) return null;
    if (job && trace.jobId && trace.jobId !== job.id) return null;
    return trace.entries[trace.entries.length - 1] ?? null;
  }

  #previewActivityCurrent(): SliceActivityEntry | null {
    const trace = this.#sliceTrace;
    if (!trace?.entries.some((entry) => entry.code === "toolpath_parse_started")) return null;
    const current = trace.entries[trace.entries.length - 1] ?? null;
    return current && PREVIEW_CODES.has(current.code) ? current : null;
  }

  #previewWorkflowKey(): string {
    return this.#sliceTrace?.traceId ? `preview:${this.#sliceTrace.traceId}` : "";
  }

  #sliceTraceMarkup(): string {
    const trace = this.#sliceTrace;
    if (!trace?.entries.length) return "";
    const startedAt = new Date(trace.entries[0]!.at).getTime();
    const current = trace.entries[trace.entries.length - 1]!;
    const entries = trace.entries.map((entry, index) => {
      const elapsedMs = new Date(entry.at).getTime() - startedAt;
      const elapsed = Number.isFinite(elapsedMs) && elapsedMs >= 0 ? `+${(elapsedMs / 1000).toFixed(1)} s` : "";
      const state = entry.status === "error" ? "error" : index === trace.entries.length - 1 && trace.active ? "running" : "done";
      const icon = state === "error" ? "×" : state === "running" ? "●" : "✓";
      const metrics: string[] = [];
      if (Number(entry.metrics?.loadedLayers) > 0 && Number(entry.metrics?.layerCount) > 0) metrics.push(`${Number(entry.metrics?.loadedLayers).toLocaleString("de-DE")} / ${Number(entry.metrics?.layerCount).toLocaleString("de-DE")} Layer`);
      else if (Number(entry.metrics?.layerCount) > 0) metrics.push(`${Number(entry.metrics?.layerCount).toLocaleString("de-DE")} Layer`);
      if (Number(entry.metrics?.loadedSegmentCount) > 0 && Number(entry.metrics?.segmentCount) > 0) metrics.push(`${Number(entry.metrics?.loadedSegmentCount).toLocaleString("de-DE")} / ${Number(entry.metrics?.segmentCount).toLocaleString("de-DE")} Bahnen`);
      else if (Number(entry.metrics?.segmentCount) > 0) metrics.push(`${Number(entry.metrics?.segmentCount).toLocaleString("de-DE")} Bahnen`);
      if (Number(entry.metrics?.materialCount) > 0) metrics.push(`${Number(entry.metrics?.materialCount).toLocaleString("de-DE")} Materialkanal/-kanäle`);
      const processedBytes = Number(entry.metrics?.processedBytes) || 0;
      const totalBytes = Number(entry.metrics?.totalBytes) || 0;
      if (processedBytes > 0 && totalBytes > 0) metrics.push(`${formatBytes(processedBytes)} / ${formatBytes(totalBytes)}`);
      else if (totalBytes > 0) metrics.push(`${formatBytes(totalBytes)} gesamt`);
      if (Number(entry.metrics?.outputSizeBytes) > 0) metrics.push(`Ausgabe ${formatBytes(entry.metrics?.outputSizeBytes)}`);
      if (Number(entry.metrics?.rateBytesPerSecond) > 0) metrics.push(formatRate(entry.metrics?.rateBytesPerSecond));
      if (Number(entry.metrics?.layerRatePerSecond) > 0) metrics.push(`${Number(entry.metrics?.layerRatePerSecond).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Layer/s`);
      if (Number(entry.metrics?.segmentRatePerSecond) > 0) metrics.push(`${Math.round(Number(entry.metrics?.segmentRatePerSecond)).toLocaleString("de-DE")} Bahnen/s`);
      if (Number(entry.metrics?.elapsedSeconds) > 0) metrics.push(`${formatDuration(entry.metrics?.elapsedSeconds)} Laufzeit`);
      if (Number(entry.metrics?.etaSeconds) > 0) metrics.push(`ETA ${formatDuration(entry.metrics?.etaSeconds)}`);
      return `<li class="trace-${state}"><time>${esc(timeLabel(entry.at))}<small>${esc(elapsed)}</small></time><span class="trace-dot">${icon}</span><div><b>${esc(entry.label)}</b>${entry.detail ? `<small>${esc(entry.detail)}</small>` : ""}${metrics.length ? `<em>${esc(metrics.join(" · "))}</em>` : ""}</div>${entry.progress !== null ? `<strong>${Math.round(entry.progress)} %</strong>` : ""}</li>`;
    }).join("");
    const job = trace.jobId ? ` · Job ${trace.jobId}` : "";
    const state = current.status === "error" ? "error" : trace.active ? "running" : "done";
    const overallEta = estimatedOverallEta(trace.entries, trace.active);
    const overallEtaText = overallEta !== null ? ` · Gesamt-ETA ~ ${formatDuration(overallEta)}` : "";
    return `<div class="slice-trace-head"><div><b>Slice- und Renderprotokoll</b><small>${esc(trace.fileName || trace.plateName)}${esc(job)}</small></div><span class="trace-current ${state}">${trace.active ? `LÄUFT${esc(overallEtaText)}` : current.status === "error" ? "FEHLER" : "FERTIG"}</span></div><ol class="slice-trace-list">${entries}</ol>`;
  }

  #restoreDismissedItems(): void {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(DISMISSED_ITEMS_KEY) || "[]") as unknown;
      this.#dismissedItems = new Set(Array.isArray(parsed) ? parsed.map((item) => String(item)).filter(Boolean).slice(-240) : []);
    } catch {
      this.#dismissedItems.clear();
    }
  }

  #persistDismissedItems(): void {
    try {
      if (this.#dismissedItems.size) sessionStorage.setItem(DISMISSED_ITEMS_KEY, JSON.stringify([...this.#dismissedItems].slice(-240)));
      else sessionStorage.removeItem(DISMISSED_ITEMS_KEY);
    } catch {}
  }

  #dismissItem(key: string): void {
    const normalized = String(key || "").trim();
    if (!normalized) return;
    this.#dismissedItems.add(normalized);
    this.#persistDismissedItems();
    this.#update();
  }

  #sliceWorkflowKey(job: SliceJob | null = null): string {
    const trace = this.#sliceTrace;
    if (trace?.traceId && (!job || !trace.jobId || trace.jobId === job.id)) return `slice:${trace.traceId}`;
    if (this.#preparation?.id) return `slice:${this.#preparation.id}`;
    if (job?.id) return `slicer:${job.id}`;
    return trace?.traceId ? `slice:${trace.traceId}` : "";
  }

  #studioWorkflowKey(): string {
    return this.#studioTrace?.traceId ? `studio:${this.#studioTrace.traceId}` : "";
  }

  #directPrintTransferWorkflowKey(): string {
    return this.#directPrintTransfer?.traceId ? `transfer:${this.#directPrintTransfer.traceId}` : "";
  }

  #printWorkflowKey(job: V6Job): string {
    const id = idOf(job);
    return id ? `print:${id}` : "";
  }

  #dismissButton(key: string, label: unknown): string {
    if (!key) return "";
    return `<button class="job-dismiss" type="button" data-dismiss-item="${esc(key)}" title="Nur aus diesem Popup entfernen" aria-label="${esc(label)} aus dem Popup entfernen">×</button>`;
  }

  #mount(): void {
    try { this.#dismissedSignature = sessionStorage.getItem(DISMISSED_KEY) || ""; } catch {}
    this.#restoreDismissedItems();
    this.#root.innerHTML = `<style>${PRINTER_ISSUE_STYLES}${PROCESS_VALUE_PROOF_STYLES}
      :host{position:fixed;right:18px;bottom:18px;z-index:2147483000;display:block;width:600px;max-width:calc(100vw - 36px);color:#eef8ff;font:600 13px/1.35 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;filter:drop-shadow(0 16px 40px rgba(0,0,0,.42));contain:layout paint}:host([hidden]){display:none}*{box-sizing:border-box}.popup{display:flex;max-height:calc(100vh - 36px);overflow:hidden;flex-direction:column;border:1px solid rgba(44,188,255,.55);border-radius:14px;background:linear-gradient(155deg,rgba(7,28,43,.98),rgba(5,17,29,.98));box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}.head{position:sticky;top:0;z-index:20;display:flex;flex:0 0 auto;align-items:flex-start;gap:8px;min-height:47px;padding:14px 14px 11px;background:transparent}.heading{min-width:0;flex:1}.eyebrow{color:#66d1ff;font-size:10px;letter-spacing:.13em;text-transform:uppercase}.head strong{display:block;margin-top:3px;overflow:hidden;color:#f5fbff;font-size:16px;line-height:1.2;text-overflow:ellipsis;white-space:nowrap}.head button,.cancel,.job-dismiss{appearance:none;border:1px solid rgba(133,205,236,.26);border-radius:8px;background:rgba(12,43,62,.72);color:#dff5ff;cursor:pointer;font:inherit}.head button{padding:6px 8px;white-space:nowrap}.head button:hover{border-color:rgba(102,209,255,.72)}.head .close{width:31px;padding-inline:0}.jobs{display:grid;flex:0 1 auto;min-height:0;gap:8px;overflow-y:auto;padding:0 14px 14px;overscroll-behavior:contain}.jobs:empty{display:none}.jobs.collapsed{display:none}.job{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:7px;overflow:hidden;padding:0;border:1px solid rgba(44,188,255,.32);border-radius:10px;background:rgba(12,43,62,.48);color:#eef8ff;text-align:left}.job-main{display:grid;gap:5px;width:100%;min-height:88px;padding:10px;appearance:none;border:0;border-radius:0;background:transparent;color:inherit;font:inherit;text-align:left;cursor:pointer}.job-actions{display:flex;flex-direction:column;align-items:stretch;justify-content:center;gap:6px;padding:7px 7px 7px 0}.job.current-print{position:sticky;bottom:0;z-index:2;border-color:rgba(54,215,132,.58);background:linear-gradient(155deg,rgba(9,45,31,.98),rgba(5,26,20,.98));box-shadow:0 -8px 18px #07120dcc}.job.current-print .job-main{background:transparent}.job.current-print:hover{border-color:#63e398;background:linear-gradient(155deg,rgba(14,57,40,.98),rgba(7,35,26,.98))}.job.preview-ready{border-color:rgba(54,215,132,.58);background:linear-gradient(155deg,rgba(9,45,31,.82),rgba(5,26,20,.82))}.job.preview-error{border-color:rgba(255,91,104,.72);background:linear-gradient(155deg,rgba(58,20,28,.88),rgba(31,10,17,.88))}.preview-metrics{color:#a8c9da!important}.job span{font-size:9px;color:#7e96ad}.job small{color:#91a5b9}.job-id{font-family:Consolas,monospace;font-size:9px!important}.job-meta{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}.job-rest{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #2e7650;border-radius:999px;background:#0b1d14;color:#9af1bd!important;font-size:10px!important;white-space:nowrap}.job-rest strong{color:#d9ffe7;font-size:11px}.progress{position:relative;height:8px;overflow:hidden;border-radius:999px;background:rgba(126,177,202,.16)}.progress u{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#19aee7,#55e3bd);transition:width .22s ease}.progress.moving u{background:linear-gradient(90deg,#19aee7,#55e3bd,#19aee7);background-size:200% 100%;animation:move 1.2s linear infinite}.progress.calculating u{width:100%!important;transform-origin:left;animation:calculate 1.15s linear infinite}.preview-error .progress u{background:#ff6572}.cancel{margin:0;padding:7px 9px;border-color:#8b4148;background:#3a1a20}.job-dismiss{display:grid;place-items:center;width:30px;min-width:30px;height:30px;padding:0;border-color:#49647c;background:#102131;color:#a9bed0;font-size:18px;line-height:1}.job-dismiss:hover{border-color:#7f9bb2;background:#193047;color:#fff}.details{display:none;flex:1 1 auto;min-height:0;grid-template-columns:1fr;gap:10px;overflow:auto;padding:0 10px 10px;overscroll-behavior:contain}.details.visible{display:grid}.details.with-camera{grid-template-columns:1.2fr .8fr}.summary{padding:10px;border:1px solid #294159;border-radius:10px;background:#0d1a26}.slice-activity{grid-column:1/-1;padding:10px;border:1px solid #294159;border-radius:10px;background:#0d1a26}.slice-activity[hidden]{display:none}.slice-trace-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}.slice-trace-head b,.slice-trace-head small{display:block}.slice-trace-head small{margin-top:2px;color:#8298ae;font:9px Consolas,monospace;overflow-wrap:anywhere}.trace-current{padding:4px 7px;border:1px solid #31506d;border-radius:999px;background:#132438;color:#a9c3d8;font-size:9px;font-weight:900;letter-spacing:.06em}.trace-current.done{border-color:#27734c;background:#102b1d;color:#8ff0b5}.trace-current.running{border-color:#2e6687;background:#10263a;color:#9edfff}.trace-current.error{border-color:#8f3f4b;background:#31171c;color:#ffd7dc}.slice-trace-list{display:grid;gap:4px;margin:0;padding:0;list-style:none}.slice-trace-list li{display:grid;grid-template-columns:74px 20px minmax(0,1fr) auto;gap:7px;align-items:start;padding:6px 7px;border:1px solid #26384f;border-radius:7px;background:#091520}.slice-trace-list time{color:#a8bfd2;font:10px Consolas,monospace;white-space:nowrap}.slice-trace-list time small{display:block;margin-top:2px;color:#60778c;font-size:8px}.trace-dot{display:grid;place-items:center;width:18px;height:18px;border-radius:50%;background:#173049;color:#7dd9ff;font-weight:900}.slice-trace-list li.trace-done .trace-dot{background:#153e29;color:#8ff0b5}.slice-trace-list li.trace-running .trace-dot{background:#173049;color:#7dd9ff}.slice-trace-list li.trace-error .trace-dot{background:#4a2027;color:#ffd7dc}.slice-trace-list li>div b,.slice-trace-list li>div small,.slice-trace-list li>div em{display:block}.slice-trace-list li>div b{color:#eef7ff;font-size:11px}.slice-trace-list li>div small{margin-top:2px;color:#91a5b9;font-size:9px;line-height:1.35}.slice-trace-list li>div em{margin-top:3px;color:#70bce0;font-size:8px;font-style:normal}.slice-trace-list li>strong{color:#b7d8ea;font:9px Consolas,monospace;white-space:nowrap}.trace-separator{height:1px;margin:10px 0;background:#294159}.phase-head{display:grid;grid-template-columns:minmax(0,1fr) minmax(190px,.48fr);gap:8px}.current{padding:9px;border:1px solid #2e6687;border-radius:8px;background:#10263a}.current b,.current small{display:block}.current small{margin-top:4px;color:#9eb1c2}.remaining-card{display:grid;align-content:center;min-width:0;padding:9px 11px;border:1px solid #2f8055;border-radius:8px;background:linear-gradient(145deg,#102b1d,#0b2016)}.remaining-card small,.remaining-card strong{display:block}.remaining-card small{color:#78ca98;font-size:9px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.remaining-card strong{margin-top:5px;color:#caffe0;font-size:17px;line-height:1.15}.summary ol{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin:8px 0 0;padding:0;list-style:none}.summary li{display:flex;gap:5px;padding:6px;border:1px solid #26384f;border-radius:7px;color:#8195aa;font-size:10px}.summary li.active{border-color:#42c8ff;background:#12314a;color:#eefaff}.summary li.visited{border-color:#2e6687;background:#10263a;color:#9edfff}.summary li.done{border-color:#27734c;background:#102b1d;color:#8ff0b5}.error{flex:0 0 auto;margin:0 10px 10px;padding:8px;border:1px solid #8f3f4b;border-radius:8px;background:#31171c;color:#ffd7dc}.issue-host{display:grid;flex:0 1 auto;min-height:0;gap:8px;max-height:72vh;overflow:auto;padding:10px;border-bottom:1px solid #253b51}.issue-host[hidden]{display:none}.issue-list{display:grid;gap:8px}.issue-actions{padding:9px;border:1px solid #31506d;border-radius:9px;background:#0d1a26}.issue-note{margin:0;color:#ffd7dc;font-weight:700}.camera[hidden]{display:none}@keyframes move{from{background-position:0 0}to{background-position:200% 0}}@keyframes calculate{from{transform:scaleX(0)}to{transform:scaleX(1)}}@media(max-width:620px){:host{right:8px;bottom:8px;width:calc(100vw - 16px)}.popup{max-height:calc(100vh - 16px)}.details.with-camera{grid-template-columns:1fr}.phase-head{grid-template-columns:1fr}.summary ol{grid-template-columns:repeat(2,1fr)}}
    </style><section class="popup" aria-live="polite"><header class="head"><div class="heading"><div class="eyebrow">Vorgänge</div><strong id="title">Vorgang</strong></div><button id="collapse" type="button">Minimieren</button><button id="camera-toggle" type="button">Kamera ein</button><button id="expand" type="button">Größer</button><button id="close" class="close" type="button" aria-label="Popup schließen">×</button></header><div class="issue-host" id="printer-issue" hidden></div><div class="jobs" id="jobs"></div><div class="details" id="details"><div class="slice-activity" id="slice-activity" hidden></div><div class="summary" id="summary"></div><div class="camera" id="camera" hidden><printer-camera-panel title="Druckerkamera" storage-key="global-job-popup"></printer-camera-panel></div></div></section>`;
    this.#root.querySelector<HTMLButtonElement>("#collapse")?.addEventListener("click", () => {
      if (this.#printerHasIssue()) return;
      this.#collapsed = !this.#collapsed;
      this.#updateVisibility();
    });
    this.#root.querySelector<HTMLButtonElement>("#expand")?.addEventListener("click", () => {
      this.#expanded = !this.#expanded;
      this.#collapsed = false;
      this.#updateVisibility();
    });
    this.#root.querySelector<HTMLButtonElement>("#camera-toggle")?.addEventListener("click", () => {
      this.#cameraVisible = !this.#cameraVisible;
      if (this.#cameraVisible) this.#expanded = true;
      this.#collapsed = false;
      this.#updateVisibility();
      this.#forwardHass();
    });
    this.#root.querySelector<HTMLButtonElement>("#close")?.addEventListener("click", () => {
      this.#dismissedSignature = this.#lastSignature;
      try {
        if (this.#dismissedSignature) sessionStorage.setItem(DISMISSED_KEY, this.#dismissedSignature);
        else sessionStorage.removeItem(DISMISSED_KEY);
      } catch {}
      this.hidden = true;
    });
  }

  #primaryPrinter(): V6Printer | null {
    return this.#snapshot.printers[0] ?? null;
  }

  #signature(): string {
    const preparationId = this.#preparation?.id || "";
    const slicerId = this.#snapshot.slicer?.id || "";
    const printIds = this.#snapshot.printJobs.map((job) => idOf(job)).filter(Boolean).sort().join("|");
    const issue = issueSignature(this.#primaryPrinter());
    const traceId = this.#sliceTrace?.traceId || "";
    const studioTraceId = this.#studioTrace?.traceId || "";
    const transferTraceId = this.#directPrintTransfer?.traceId || "";
    return `prepare:${preparationId}|slicer:${slicerId}|trace:${traceId}|studio:${studioTraceId}|transfer:${transferTraceId}|print:${printIds}|issue:${issue}`;
  }

  #navigate(name: "slicer" | "aufgaben", id?: string): void {
    this.dispatchEvent(new CustomEvent("v6-job-navigate", { bubbles: true, composed: true, detail: { name, id: id || null } }));
  }

  #forwardHass(): void {
    const camera = this.#root.querySelector<PrinterCameraPanel>("printer-camera-panel");
    if (camera) camera.hass = this.#hass;
  }

  #printer(job: V6Job): V6Printer | null {
    const printerId = String(job.printer_id || "");
    return this.#snapshot.printers.find((item) => String(item.printer_id || "") === printerId)
      || this.#snapshot.printers[0]
      || null;
  }

  #currentPrintIds(): Set<string> {
    return new Set((this.#snapshot.jobs.current || []).map((job) => idOf(job)).filter(Boolean));
  }

  #orderedPrintJobs(jobs: readonly V6Job[]): V6Job[] {
    const currentIds = this.#currentPrintIds();
    const other: V6Job[] = [];
    const current: V6Job[] = [];
    for (const job of jobs) {
      (currentIds.has(idOf(job)) ? current : other).push(job);
    }
    return [...other, ...current];
  }

  #phaseState(job: V6Job, printer: V6Printer | null): ReturnType<typeof resolveLivePrintPhase> {
    const jobId = idOf(job) || String(printer?.printer_id || "");
    const localSeen = jobId ? [...(this.#phaseSeen.get(jobId) ?? new Set<string>())] : [];
    const progress = resolveLivePrintPhase(job, printer, localSeen);
    if (jobId) this.#phaseSeen.set(jobId, new Set(progress.seenKeys));
    return progress;
  }

  #phases(job: V6Job, printer: V6Printer | null): string {
    if (!printer) return "Klick auf einen Vorgang öffnet den passenden Arbeitsbereich.";
    const progress = this.#phaseState(job, printer);
    const remaining = remainingTimeLabel(job, printer);
    const seen = new Set(progress.seenKeys);
    const state = String(job.status || "").toLowerCase();
    const jobEnded = ["completed", "complete", "finished", "finish"].includes(state) || percent(job.progress) >= 100;
    const phaseItems = PRINT_PHASES.map((phase, itemIndex) => {
      const active = itemIndex === progress.activeIndex;
      const observed = seen.has(phase.key);
      const done = observed && !active && (!phase.doneOnlyWhenJobEnds || jobEnded);
      const visited = observed && !active && !done;
      const unreported = !active && !observed && progress.activeIndex > itemIndex;
      const className = active ? "active" : done ? "done" : visited ? "visited" : unreported ? "unreported" : "";
      const icon = active ? "●" : done ? "✓" : visited ? "◐" : unreported ? "–" : "○";
      const title = unreported ? ' title="Vom Drucker nicht als eigener Status gemeldet"' : "";
      return `<li class="${className}"${title}><span>${icon}</span>${esc(phase.label)}</li>`;
    }).join("");
    return `<div class="phase-head"><div class="current"><b>${esc(progress.currentLabel)}</b><small>${esc(progress.detail)}<br>${esc(printLayerLabel(job, printer))} · Tempo ${esc(printSpeedLabel(printer))}</small></div><article class="remaining-card"><small>Verbleibende Druckzeit</small><strong id="remaining-time-value">${esc(remaining)}</strong></article></div><div style="margin-top:9px"><ultimate-3d-print-speed-control id="popup-speed"></ultimate-3d-print-speed-control></div><ol>${phaseItems}</ol>`;
  }

  #renderIssue(printer: V6Printer | null, job: V6Job | null): void {
    const host = this.#root.querySelector<HTMLElement>("#printer-issue");
    if (!host) return;
    const issues = printerIssues(printer);
    const primary = issues[0] ?? null;
    host.hidden = issues.length === 0;
    if (!issues.length || !primary) {
      host.innerHTML = "";
      return;
    }
    if (!host.querySelector("#issue-actions")) {
      host.innerHTML = `<div class="issue-list"></div><p class="issue-note">Alle angezeigten Ursachen am Drucker beheben. Danach den Druck ausdrücklich fortsetzen.</p><div class="issue-actions"><ultimate-3d-printer-actions id="issue-actions"></ultimate-3d-printer-actions></div>`;
    }
    const list = host.querySelector<HTMLElement>(".issue-list");
    const markup = issues.map((issue) => issueMarkup(issue, true)).join("");
    if (list && list.innerHTML !== markup) list.innerHTML = markup;
    const actions = host.querySelector<Ultimate3DPrinterActions>("#issue-actions");
    if (actions) {
      actions.printer = printer;
      actions.job = job;
      actions.issue = primary;
      actions.issueMode = true;
      actions.capabilities = this.#snapshot.capabilities;
    }
  }

  #updateRemainingLabels(): void {
    if (!this.isConnected || this.hidden) return;
    for (const job of this.#snapshot.printJobs) {
      const jobId = idOf(job);
      if (!jobId) continue;
      const label = remainingTimeLabel(job, this.#printer(job));
      this.#root.querySelectorAll<HTMLElement>(`[data-remaining-id="${CSS.escape(jobId)}"]`).forEach((node) => {
        if (node.textContent !== label) node.textContent = label;
      });
    }
    const slicerJob = this.#snapshot.slicer;
    const slicerEtaNode = this.#root.querySelector<HTMLElement>("[data-slicer-eta]");
    if (slicerEtaNode && slicerJob && nativeSlicerProgress(slicerJob)) {
      const eta = slicerEtaSeconds(slicerJob);
      slicerEtaNode.textContent = eta !== null && eta > 0 ? `ETA ~ ${formatDuration(eta)}` : "ETA wird berechnet";
    }
    const firstPrintJob = this.#snapshot.printJobs[0] ?? null;
    const summaryRemaining = this.#root.querySelector<HTMLElement>("#remaining-time-value");
    if (summaryRemaining && firstPrintJob) {
      const label = remainingTimeLabel(firstPrintJob, this.#printer(firstPrintJob));
      if (summaryRemaining.textContent !== label) summaryRemaining.textContent = label;
    }
  }

  #update(): void {
    if (!this.isConnected) return;
    const slicer = this.#snapshot.slicer;
    const printJobs = this.#snapshot.printJobs;
    const sliceWorkflowKey = this.#sliceWorkflowKey(slicer);
    const previewWorkflowKey = this.#previewWorkflowKey();
    const studioWorkflowKey = this.#studioWorkflowKey();
    const transferWorkflowKey = this.#directPrintTransferWorkflowKey();
    const previewActivity = this.#previewActivityCurrent();
    const visiblePreparation = this.#preparation && !this.#dismissedItems.has(sliceWorkflowKey) ? this.#preparation : null;
    const visibleSlicer = slicer && !this.#dismissedItems.has(sliceWorkflowKey) ? slicer : null;
    const visibleSliceDetails = Boolean(this.#sliceTrace?.entries.length && !this.#dismissedItems.has(sliceWorkflowKey));
    const visibleTraceCard = Boolean(visibleSliceDetails && !previewActivity);
    const visiblePreview = Boolean(previewActivity && previewWorkflowKey && !this.#dismissedItems.has(previewWorkflowKey));
    const visibleStudioTrace = Boolean(this.#studioTrace?.entries.length && !this.#dismissedItems.has(studioWorkflowKey));
    const visibleTransfer = this.#directPrintTransfer && transferWorkflowKey && !this.#dismissedItems.has(transferWorkflowKey)
      ? this.#directPrintTransfer
      : null;
    const visiblePrintJobs = printJobs.filter((job) => !this.#dismissedItems.has(this.#printWorkflowKey(job)));
    const orderedPrintJobs = this.#orderedPrintJobs(visiblePrintJobs);
    const currentIds = this.#currentPrintIds();
    const printer = this.#primaryPrinter();
    const activeIssues = printerIssues(printer);
    const primaryIssue = activeIssues[0] ?? null;
    const activePhaseIds = new Set(printJobs.map((job) => idOf(job)).filter(Boolean));
    for (const key of this.#phaseSeen.keys()) {
      if (!activePhaseIds.has(key)) this.#phaseSeen.delete(key);
    }
    const visible = Boolean(visiblePreparation || visibleSlicer || visiblePrintJobs.length || primaryIssue || visibleTraceCard || visiblePreview || visibleStudioTrace || visibleTransfer);
    const signature = this.#signature();
    if (signature !== this.#lastSignature) {
      if (this.#dismissedSignature && signature !== this.#dismissedSignature) {
        this.#dismissedSignature = "";
        try { sessionStorage.removeItem(DISMISSED_KEY); } catch {}
      }
      this.#lastSignature = signature;
    }
    this.hidden = !visible || (this.#dismissedSignature === signature && Boolean(signature));
    if (!visible) return;

    const activeSlicer = Boolean(visibleSlicer && ACTIVE.has(visibleSlicer.status));
    const previewActive = Boolean(visiblePreview && this.#sliceTrace?.active && previewActivity?.status !== "error");
    const traceOnlyActive = Boolean(this.#sliceTrace?.active && !visiblePreparation && !visibleSlicer && visibleTraceCard);
    const studioTraceActive = Boolean(this.#studioTrace?.active && visibleStudioTrace);
    const transferActive = Boolean(visibleTransfer?.active);
    const activeCount = visiblePrintJobs.length + (activeSlicer ? 1 : 0) + (visiblePreparation ? 1 : 0) + (previewActive ? 1 : 0) + (traceOnlyActive ? 1 : 0) + (studioTraceActive ? 1 : 0) + (transferActive ? 1 : 0);
    const title = this.#root.querySelector<HTMLElement>("#title");
    if (title) title.textContent = primaryIssue
      ? `${activeIssues.length} Druckerstörung${activeIssues.length === 1 ? "" : "en"} – Eingriff erforderlich`
      : activeCount ? `${activeCount} aktiver Vorgang${activeCount === 1 ? "" : "e"}` : "Vorgang abgeschlossen";

    const jobs = this.#root.querySelector<HTMLElement>("#jobs");
    if (jobs) {
      const preparation = visiblePreparation;
      const preparationCard = preparation ? `<article class="job preparing"><div class="job-main"><span>SLICER · VORBEREITUNG</span><b>${esc(preparation.fileName || preparation.plateName || "Druckplatte")}</b><small>${esc(preparation.phase || "Slicerauftrag wird vorbereitet")}</small><small class="job-id">${esc(preparation.plateName || "Studio")}</small><i class="progress moving"><u style="width:${percent(preparation.progress)}%"></u></i></div><div class="job-actions">${this.#dismissButton(sliceWorkflowKey, preparation.fileName || preparation.plateName || "Slicer-Vorbereitung")}</div></article>` : "";
      const currentActivity = this.#sliceActivityCurrent(visibleSlicer);
      const nativeProgress = visibleSlicer ? nativeSlicerProgress(visibleSlicer) : null;
      const slicerActivityText = visibleSlicer
        ? nativeProgress
          ? slicerActivityLabel(visibleSlicer)
          : currentActivity
            ? `${timeLabel(currentActivity.at)} · ${currentActivity.label}${currentActivity.detail ? ` · ${currentActivity.detail}` : ""}`
            : slicerActivityLabel(visibleSlicer)
        : "";
      const slicerProgressValue = visibleSlicer ? slicerProgressPercent(visibleSlicer) : 0;
      const slicerEta = visibleSlicer ? slicerEtaSeconds(visibleSlicer) : null;
      const slicerMeta: string[] = [];
      if (nativeProgress?.plate_count) slicerMeta.push(`Platte ${Math.max(1, Number(nativeProgress.plate_index) || 1)} / ${nativeProgress.plate_count}`);
      if (Number(nativeProgress?.elapsed_seconds) > 0) slicerMeta.push(`Laufzeit ${formatDuration(nativeProgress?.elapsed_seconds)}`);
      const slicerMetaText = slicerMeta.length ? ` · ${slicerMeta.join(" · ")}` : "";
      const slicerEtaText = nativeProgress && activeSlicer ? (slicerEta !== null && slicerEta > 0 ? `ETA ~ ${formatDuration(slicerEta)}` : "ETA wird berechnet") : "";
      const slicerCard = visibleSlicer ? `<article class="job ${esc(visibleSlicer.status)}"><button class="job-main" data-target="slicer" data-id="${esc(visibleSlicer.id)}"><span>SLICER · ${esc(visibleSlicer.backend_name || "Slicing Server")}</span><b>${esc(visibleSlicer.model_file || visibleSlicer.output_file || "Slicer-Auftrag")}</b><small>${esc(slicerActivityText)}${esc(slicerMetaText)}</small><small>${esc(profileApplicationSummary(visibleSlicer.profile_application))}</small><small class="job-id">Job ${esc(visibleSlicer.id)} · ${Math.round(slicerProgressValue)} %${nativeProgress ? ` · <span data-slicer-eta>${esc(slicerEtaText)}</span>` : ""}</small><i class="progress ${ACTIVE.has(visibleSlicer.status) ? "moving" : ""}"><u style="width:${slicerProgressValue}%"></u></i></button><div class="job-actions">${this.#dismissButton(sliceWorkflowKey, visibleSlicer.model_file || visibleSlicer.output_file || "Slicer-Auftrag")}</div>${processValueProofMarkup(visibleSlicer.profile_application)}</article>` : "";
      const previewFailed = previewActivity?.code === "slice_pipeline_failed" || previewActivity?.status === "error";
      const previewReady = previewActivity?.code === "preview_ready" && !previewFailed;
      const previewProgressValue = previewActivity ? previewProgress(previewActivity) : null;
      const previewEta = previewActivity ? remainingSeconds(previewActivity.metrics) : null;
      const previewTitle = previewFailed ? "Druckvorschau fehlgeschlagen" : previewReady ? "Druckvorschau fertig" : "Druckvorschau wird erzeugt";
      const previewProgressText = previewProgressValue === null ? "Fortschritt wird ermittelt" : `${Math.round(previewProgressValue)} %`;
      const previewEtaText = previewFailed
        ? "Abgebrochen"
        : previewReady
          ? "Fertig"
          : previewEta !== null
            ? `Noch ca. ${formatDuration(previewEta)}`
            : "ETA wird nach dem ersten Datenblock berechnet";
      const previewMetrics = previewActivity ? [metricText(previewActivity), rateText(previewActivity.metrics)].filter(Boolean).join(" · ") : "";
      const previewProgressClass = previewProgressValue === null && !previewFailed && !previewReady ? "calculating" : this.#sliceTrace?.active ? "moving" : "";
      const previewMain = previewActivity && this.#sliceTrace?.jobId
        ? `<button class="job-main" data-target="slicer" data-id="${esc(this.#sliceTrace.jobId)}"><span>LAYERANSICHT</span><b>${esc(previewTitle)}</b><small>${esc([this.#sliceTrace.fileName, this.#sliceTrace.plateName].filter(Boolean).join(" · ") || "Aktuelle Druckplatte")}</small><small>${esc(previewActivity.label)}${previewActivity.detail ? ` · ${esc(previewActivity.detail)}` : ""}</small><small class="job-id">${esc(previewProgressText)} · ${esc(previewEtaText)}</small>${previewMetrics ? `<small class="preview-metrics">${esc(previewMetrics)}</small>` : ""}<i class="progress ${previewProgressClass}"><u style="width:${previewProgressValue === null ? 100 : previewProgressValue}%"></u></i></button>`
        : previewActivity && this.#sliceTrace
          ? `<div class="job-main"><span>LAYERANSICHT</span><b>${esc(previewTitle)}</b><small>${esc([this.#sliceTrace.fileName, this.#sliceTrace.plateName].filter(Boolean).join(" · ") || "Aktuelle Druckplatte")}</small><small>${esc(previewActivity.label)}${previewActivity.detail ? ` · ${esc(previewActivity.detail)}` : ""}</small><small class="job-id">${esc(previewProgressText)} · ${esc(previewEtaText)}</small>${previewMetrics ? `<small class="preview-metrics">${esc(previewMetrics)}</small>` : ""}<i class="progress ${previewProgressClass}"><u style="width:${previewProgressValue === null ? 100 : previewProgressValue}%"></u></i></div>`
          : "";
      const previewCard = visiblePreview && previewActivity && this.#sliceTrace
        ? `<article class="job preview-job ${previewFailed ? "preview-error" : previewReady ? "preview-ready" : ""}">${previewMain}<div class="job-actions">${this.#dismissButton(previewWorkflowKey, previewTitle)}</div></article>`
        : "";
      const traceCurrent = this.#sliceActivityCurrent(null);
      const traceProgressClass = traceCurrent?.progress === null && this.#sliceTrace?.active ? "calculating" : this.#sliceTrace?.active ? "moving" : "";
      const traceProgressValue = traceCurrent?.progress ?? 100;
      const traceMain = this.#sliceTrace?.jobId
        ? `<button class="job-main" data-target="slicer" data-id="${esc(this.#sliceTrace.jobId)}"><span>SLICER · PROTOKOLL</span><b>${esc(this.#sliceTrace.fileName || this.#sliceTrace.plateName)}</b><small>${esc(timeLabel(traceCurrent?.at || ""))} · ${esc(traceCurrent?.label || "")}${traceCurrent?.detail ? ` · ${esc(traceCurrent.detail)}` : ""}</small><small class="job-id">Job ${esc(this.#sliceTrace.jobId)}</small><i class="progress ${traceProgressClass}"><u style="width:${traceProgressValue}%"></u></i></button>`
        : this.#sliceTrace && traceCurrent ? `<div class="job-main"><span>SLICER · PROTOKOLL</span><b>${esc(this.#sliceTrace.fileName || this.#sliceTrace.plateName)}</b><small>${esc(timeLabel(traceCurrent.at))} · ${esc(traceCurrent.label)}${traceCurrent.detail ? ` · ${esc(traceCurrent.detail)}` : ""}</small><small class="job-id">${esc(this.#sliceTrace.plateName)}</small><i class="progress ${traceProgressClass}"><u style="width:${traceProgressValue}%"></u></i></div>` : "";
      const traceCard = !preparation && !visibleSlicer && visibleTraceCard && this.#sliceTrace && traceCurrent ? `<article class="job">${traceMain}<div class="job-actions">${this.#dismissButton(sliceWorkflowKey, this.#sliceTrace.fileName || this.#sliceTrace.plateName)}</div></article>` : "";
      const studioCurrent = this.#studioTraceCurrent();
      const studioProgressClass = studioCurrent?.progress === null && this.#studioTrace?.active ? "calculating" : this.#studioTrace?.active ? "moving" : "";
      const studioProgressValue = studioCurrent?.progress ?? 100;
      const studioCard = visibleStudioTrace && this.#studioTrace && studioCurrent ? `<article class="job"><div class="job-main"><span>${this.#studioTrace.kind === "import" ? "IMPORT" : "EXPORT"} · PROTOKOLL</span><b>${esc(this.#studioTrace.fileName)}</b><small>${esc(timeLabel(studioCurrent.at))} · ${esc(studioCurrent.label)}${studioCurrent.detail ? ` · ${esc(studioCurrent.detail)}` : ""}</small><small class="job-id">${esc(this.#studioTrace.source || "3D-Studio")}</small><i class="progress ${studioProgressClass}"><u style="width:${studioProgressValue}%"></u></i></div><div class="job-actions">${this.#dismissButton(studioWorkflowKey, this.#studioTrace.fileName)}</div></article>` : "";

      const transferProgress = visibleTransfer ? percent(visibleTransfer.progress) : 0;
      const transferFailed = visibleTransfer?.status === "error";
      const transferComplete = visibleTransfer?.status === "success";
      const transferTitle = transferFailed
        ? "Druckjob-Übertragung fehlgeschlagen"
        : transferComplete
          ? "Druckjob vollständig übertragen"
          : "Druckjob wird an den Drucker übertragen";
      const transferMetrics = visibleTransfer
        ? [
            visibleTransfer.totalBytes > 0
              ? `${formatBytes(visibleTransfer.loadedBytes)} / ${formatBytes(visibleTransfer.totalBytes)}`
              : "Dateigröße wird ermittelt",
            visibleTransfer.rateBytesPerSecond > 0 ? formatRate(visibleTransfer.rateBytesPerSecond) : "",
            visibleTransfer.active && Number(visibleTransfer.etaSeconds) >= 0
              ? `ETA ${formatDuration(visibleTransfer.etaSeconds)}`
              : transferComplete ? "ETA 0 s" : "",
            Number(visibleTransfer.elapsedSeconds) >= 0
              ? `Laufzeit ${formatDuration(visibleTransfer.elapsedSeconds)}`
              : "",
          ].filter(Boolean).join(" · ")
        : "";
      const transferCard = visibleTransfer
        ? `<article class="job transfer-job ${transferFailed ? "preview-error" : transferComplete ? "preview-ready" : ""}"><button class="job-main" data-target="slicer" data-id="${esc(visibleTransfer.jobId)}"><span>DRUCKER · ÜBERTRAGUNG</span><b>${esc(transferTitle)}</b><small>${esc(visibleTransfer.fileName)} · ${esc(visibleTransfer.printerName)}</small><small>${esc(visibleTransfer.message)}</small><small class="job-id">${Math.round(transferProgress)} % · ${esc(transferMetrics)}</small><i class="progress"><u style="width:${transferProgress}%"></u></i></button><div class="job-actions">${this.#dismissButton(transferWorkflowKey, transferTitle)}</div></article>`
        : "";

      const printCards = orderedPrintJobs.map((job) => {
        const itemPrinter = this.#printer(job);
        const phase = this.#phaseState(job, itemPrinter);
        const remaining = remainingTimeLabel(job, itemPrinter);
        const jobId = idOf(job);
        const current = currentIds.has(jobId);
        const remainingKnown = remainingTimeMinutes(job, itemPrinter) !== null;
        const dismissKey = this.#printWorkflowKey(job);
        return `<article class="job ${current ? "current-print" : "queued-print"}"><button class="job-main" data-target="aufgaben" data-id="${esc(jobId)}"><span>${current ? "AKTUELLER DRUCK" : "DRUCKAUFTRAG"}</span><b>${esc(job.file || job.model_name || "Druckauftrag")}</b><div class="job-meta"><small>${esc(phase.currentLabel)} · ${percent(job.progress)}% · ${esc(printLayerLabel(job, itemPrinter))} · Tempo ${esc(printSpeedLabel(itemPrinter))}</small>${remainingKnown ? `<span class="job-rest">Restzeit <strong data-remaining-id="${esc(jobId)}">${esc(remaining)}</strong></span>` : ""}</div><i class="progress"><u style="width:${percent(job.progress)}%"></u></i></button><div class="job-actions">${this.#dismissButton(dismissKey, job.file || job.model_name || "Druckauftrag")}</div></article>`;
      }).join("");
      const previousJobsScrollTop = jobs.scrollTop;
      const jobsMarkup = preparationCard + slicerCard + previewCard + transferCard + printCards + traceCard + studioCard;
      if (jobs.innerHTML !== jobsMarkup) {
        jobs.innerHTML = jobsMarkup;
        jobs.scrollTop = previousJobsScrollTop;
      }
      jobs.querySelectorAll<HTMLButtonElement>("[data-dismiss-item]").forEach((button) => button.addEventListener("click", (event) => {
        event.stopPropagation();
        this.#dismissItem(button.dataset.dismissItem || "");
      }));
      jobs.querySelectorAll<HTMLButtonElement>("[data-target]").forEach((button) => button.addEventListener("click", () => this.#navigate(button.dataset.target as "slicer" | "aufgaben", button.dataset.id)));
    }

    const currentPrintId = this.#currentPrintIds().values().next().value as string | undefined;
    const issuePrintJob = (currentPrintId ? printJobs.find((job) => idOf(job) === currentPrintId) : null) ?? printJobs[0] ?? null;
    const firstVisiblePrintJob = (currentPrintId ? visiblePrintJobs.find((job) => idOf(job) === currentPrintId) : null) ?? visiblePrintJobs[0] ?? null;
    this.#renderIssue(printer, issuePrintJob);
    const sliceActivity = this.#root.querySelector<HTMLElement>("#slice-activity");
    if (sliceActivity) {
      const markups = [visibleStudioTrace ? this.#studioTraceMarkup() : "", visibleSliceDetails ? this.#sliceTraceMarkup() : ""].filter(Boolean);
      sliceActivity.hidden = markups.length === 0;
      const previousActivityScrollTop = sliceActivity.scrollTop;
      const activityMarkup = markups.join('<div class="trace-separator"></div>');
      if (sliceActivity.innerHTML !== activityMarkup) {
        sliceActivity.innerHTML = activityMarkup;
        sliceActivity.scrollTop = previousActivityScrollTop;
      }
    }
    const summary = this.#root.querySelector<HTMLElement>("#summary");
    if (summary) {
      if (firstVisiblePrintJob) {
        const summaryPrinter = this.#printer(firstVisiblePrintJob);
        const previousSummaryScrollTop = summary.scrollTop;
        const summaryMarkup = this.#phases(firstVisiblePrintJob, summaryPrinter);
        if (summary.innerHTML !== summaryMarkup) {
          summary.innerHTML = summaryMarkup;
          summary.scrollTop = previousSummaryScrollTop;
        }
        const speed = summary.querySelector<Ultimate3DPrintSpeedControl>("#popup-speed");
        if (speed) {
          speed.printer = summaryPrinter;
          speed.job = firstVisiblePrintJob;
          speed.capabilities = this.#snapshot.capabilities;
        }
      } else {
        if (summary.innerHTML !== "Klick auf einen Vorgang öffnet den passenden Arbeitsbereich.") summary.innerHTML = "Klick auf einen Vorgang öffnet den passenden Arbeitsbereich.";
      }
    }
    this.#updateVisibility();
    this.#updateRemainingLabels();
  }

  #updateVisibility(): void {
    const jobs = this.#root.querySelector<HTMLElement>("#jobs");
    const details = this.#root.querySelector<HTMLElement>("#details");
    const camera = this.#root.querySelector<HTMLElement>("#camera");
    const collapse = this.#root.querySelector<HTMLButtonElement>("#collapse");
    const expand = this.#root.querySelector<HTMLButtonElement>("#expand");
    const cameraToggle = this.#root.querySelector<HTMLButtonElement>("#camera-toggle");
    jobs?.classList.toggle("collapsed", this.#collapsed);
    details?.classList.toggle("visible", this.#expanded && !this.#collapsed);
    details?.classList.toggle("with-camera", this.#cameraVisible);
    if (camera) camera.hidden = !this.#cameraVisible;
    if (collapse) {
      const disabled = this.#printerHasIssue();
      collapse.disabled = disabled;
      collapse.title = disabled ? "Drucker nicht erreichbar - Minimieren deaktiviert" : "Minimieren";
      collapse.textContent = this.#collapsed ? "Einblenden" : "Minimieren";
    }
    if (expand) expand.textContent = this.#expanded ? "Kleiner" : "Größer";
    if (cameraToggle) cameraToggle.textContent = this.#cameraVisible ? "Kamera aus" : "Kamera ein";
  }
}

if (!customElements.get("ultimate-3d-global-job-popup")) {
  customElements.define("ultimate-3d-global-job-popup", Ultimate3DGlobalJobPopupV3);
}
