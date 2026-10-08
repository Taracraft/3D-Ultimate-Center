import type { StudioJob, StudioPrinter } from "./studio-api.js";
import { resolveTrackedPrintPhaseProgress, type TrackedPrintPhaseProgress } from "./print-phase-progress.js";

export type PrintSpeedLevel = 1 | 2 | 3 | 4;

export const PRINT_SPEED_MODES: readonly Readonly<{
  level: PrintSpeedLevel;
  percent: number;
  label: string;
}>[] = [
  { level: 1, percent: 50, label: "50 %" },
  { level: 2, percent: 100, label: "100 %" },
  { level: 3, percent: 125, label: "125 %" },
  { level: 4, percent: 166, label: "166 %" },
] as const;

type PrintStageHistoryEntry = Readonly<{
  key: string;
  at: string;
}>;

const finite = (value: unknown): number | null => {
  const parsed = Number(value);
  return value === null || value === undefined || value === "" || !Number.isFinite(parsed)
    ? null
    : parsed;
};

export function printSpeedLevel(printer: StudioPrinter | null | undefined): PrintSpeedLevel | null {
  const level = finite(printer?.speed_level);
  return level === 1 || level === 2 || level === 3 || level === 4 ? level : null;
}

export function printSpeedPercent(printer: StudioPrinter | null | undefined): number | null {
  const level = printSpeedLevel(printer);
  if (level === null) return null;
  return PRINT_SPEED_MODES.find((item) => item.level === level)?.percent ?? null;
}

export function printSpeedLabel(printer: StudioPrinter | null | undefined): string {
  const value = printSpeedPercent(printer);
  return value === null ? "Geschwindigkeit unbekannt" : `${value} %`;
}

export function printLayerValues(
  job: StudioJob | null | undefined,
  printer: StudioPrinter | null | undefined,
): Readonly<{ current: number | null; total: number | null }> {
  const currentRaw = finite(job?.current_layer ?? printer?.current_layer);
  const totalRaw = finite(job?.total_layers ?? printer?.total_layers);
  return {
    current: currentRaw !== null && currentRaw >= 0 ? Math.trunc(currentRaw) : null,
    total: totalRaw !== null && totalRaw > 0 ? Math.trunc(totalRaw) : null,
  };
}

export function printLayerLabel(
  job: StudioJob | null | undefined,
  printer: StudioPrinter | null | undefined,
): string {
  const { current, total } = printLayerValues(job, printer);
  if (current === null && total === null) return "Layer –";
  if (total === null) return `Layer ${current ?? "–"}`;
  return `Layer ${current ?? "–"} / ${total}`;
}

function printStageHistoryEntries(
  printer: StudioPrinter | null | undefined,
): PrintStageHistoryEntry[] {
  const history = Array.isArray(printer?.print_stage_history)
    ? printer.print_stage_history
    : [];
  return history
    .map((item): PrintStageHistoryEntry | null => {
      if (!item || typeof item !== "object") return null;
      const record = item as Record<string, unknown>;
      const key = String(record.key || "").trim();
      if (!key) return null;
      return { key, at: String(record.at || "").trim() };
    })
    .filter((item): item is PrintStageHistoryEntry => item !== null);
}

export function printStageHistoryKeys(printer: StudioPrinter | null | undefined): string[] {
  return printStageHistoryEntries(printer).map((item) => item.key);
}

export function hasConfirmedModelPhase(
  printer: StudioPrinter | null | undefined,
): boolean {
  return printStageHistoryKeys(printer).includes("printing_model");
}

export function hasModelStarted(
  job: StudioJob | null | undefined,
  printer: StudioPrinter | null | undefined,
): boolean {
  const jobProgress = finite(job?.progress);
  const printerProgress = finite(printer?.progress);
  const layer = printLayerValues(job, printer).current;
  return (jobProgress !== null && jobProgress > 0)
    || (printerProgress !== null && printerProgress > 0)
    || (layer !== null && layer > 0);
}

export function resolveLivePrintPhase(
  job: StudioJob | null | undefined,
  printer: StudioPrinter | null | undefined,
  additionalSeen: readonly string[] = [],
): TrackedPrintPhaseProgress {
  const seen = [...new Set([
    ...printStageHistoryKeys(printer),
    ...additionalSeen,
  ])];
  return resolveTrackedPrintPhaseProgress(
    String(printer?.print_stage_key || ""),
    seen,
    hasModelStarted(job, printer),
    String(printer?.print_stage_label || job?.status || "Druckstatus wird ermittelt"),
    String(printer?.print_stage_detail || "Der nächste Druckerschritt wird erwartet."),
  );
}
