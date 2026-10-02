import type { SliceJob } from "./slicing-api.js";

type NativeProgress = Readonly<{
  progress?: number;
  percent?: number;
  eta_seconds?: number;
  elapsed_seconds?: number;
  plate_index?: number;
  plate_count?: number;
  activity?: string;
  phase?: string;
  stage?: string;
}>;

function numberValue(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function progressSource(job: SliceJob | null | undefined): NativeProgress | null {
  const raw = job as unknown as Readonly<Record<string, unknown>> | null | undefined;
  if (!raw) return null;
  for (const key of ["slicer_progress", "native_progress", "progress_detail", "progress"] as const) {
    const value = raw[key];
    if (value && typeof value === "object") return value as NativeProgress;
  }
  return null;
}

export function nativeSlicerProgress(job: SliceJob | null | undefined): NativeProgress | null {
  return progressSource(job);
}

export function slicerProgressPercent(job: SliceJob | null | undefined): number {
  const raw = job as unknown as Readonly<Record<string, unknown>> | null | undefined;
  const native = progressSource(job);
  const value = numberValue(native?.progress ?? native?.percent ?? raw?.progress_percent ?? raw?.progress);
  if (value === null) {
    const status = String(raw?.status || "").toLowerCase();
    if (status === "completed" || status === "success") return 100;
    if (status === "failed" || status === "error") return 100;
    return status === "running" ? 50 : status === "queued" ? 5 : 0;
  }
  return Math.max(0, Math.min(100, value <= 1 ? value * 100 : value));
}

export function slicerEtaSeconds(job: SliceJob | null | undefined): number | null {
  const native = progressSource(job);
  const value = numberValue(native?.eta_seconds ?? (job as unknown as Readonly<Record<string, unknown>> | null | undefined)?.eta_seconds);
  return value !== null && value > 0 ? value : null;
}

export function slicerActivityLabel(job: SliceJob | null | undefined): string {
  const raw = job as unknown as Readonly<Record<string, unknown>> | null | undefined;
  const native = progressSource(job);
  const label = String(native?.activity || native?.phase || native?.stage || raw?.activity || raw?.status || "").trim();
  if (!label) return "Slicer wartet";
  const normalized = label.toLowerCase();
  if (normalized === "queued") return "Wartet in der Slicing-Warteschlange";
  if (normalized === "running") return "Slicing läuft";
  if (normalized === "completed" || normalized === "success") return "Slicing abgeschlossen";
  if (normalized === "failed" || normalized === "error") return "Slicing fehlgeschlagen";
  return label;
}