import type { V6Job, V6Printer } from "./v6-api.js";

const ACTIVE_PRINT_STATES = new Set([
  "running",
  "printing",
  "prepare",
  "preparing",
  "starting",
  "pause",
  "paused",
]);

const observations = new Map<string, Readonly<{
  minutes: number;
  observedAt: number;
}>>();

function finiteMinutes(value: unknown): number | null {
  const parsed = Number(value);
  return value === null || value === undefined || value === "" || !Number.isFinite(parsed) || parsed < 0
    ? null
    : Math.max(0, parsed);
}

function observationKey(
  job: V6Job | null | undefined,
  printer: V6Printer | null | undefined,
): string {
  return String(
    job?.job_id
      || job?.id
      || printer?.printer_id
      || printer?.serial
      || "active-print",
  );
}

export function remainingTimeMinutes(
  job: V6Job | null | undefined,
  printer: V6Printer | null | undefined,
): number | null {
  const state = String(job?.status || printer?.printer_state || "").toLowerCase();
  if (state && !ACTIVE_PRINT_STATES.has(state)) return null;
  for (const value of [
    job?.remaining_time_minutes,
    job?.remaining_minutes,
    printer?.remaining_time_minutes,
    printer?.remaining_minutes,
  ]) {
    const minutes = finiteMinutes(value);
    if (minutes !== null) return minutes;
  }
  return null;
}

export function remainingTimeSeconds(
  job: V6Job | null | undefined,
  printer: V6Printer | null | undefined,
): number | null {
  const minutes = remainingTimeMinutes(job, printer);
  const key = observationKey(job, printer);
  if (minutes === null) {
    observations.delete(key);
    return null;
  }
  const now = Date.now();
  const previous = observations.get(key);
  if (!previous || previous.minutes !== minutes) {
    observations.set(key, { minutes, observedAt: now });
    return Math.max(0, Math.round(minutes * 60));
  }
  const elapsedSeconds = Math.max(0, Math.floor((now - previous.observedAt) / 1000));
  return Math.max(0, Math.round(minutes * 60) - elapsedSeconds);
}

function unit(value: number, singular: string, plural: string): string {
  return `${value} ${value === 1 ? singular : plural}`;
}

export function formatRemainingTimeSeconds(seconds: number | null): string {
  if (seconds === null) return "–";
  const safeSeconds = Math.max(0, Math.round(seconds));
  if (safeSeconds < 600) {
    const minutes = Math.floor(safeSeconds / 60);
    const restSeconds = safeSeconds % 60;
    if (!minutes) return unit(restSeconds, "Sekunde", "Sekunden");
    return `${unit(minutes, "Minute", "Minuten")} ${unit(restSeconds, "Sekunde", "Sekunden")}`;
  }
  const totalMinutes = Math.ceil(safeSeconds / 60);
  if (totalMinutes < 60) return unit(totalMinutes, "Minute", "Minuten");
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes
    ? `${unit(hours, "Stunde", "Stunden")} ${unit(minutes, "Minute", "Minuten")}`
    : unit(hours, "Stunde", "Stunden");
}

export function formatRemainingTime(minutes: number | null): string {
  return formatRemainingTimeSeconds(minutes === null ? null : minutes * 60);
}

export function remainingTimeLabel(
  job: V6Job | null | undefined,
  printer: V6Printer | null | undefined,
): string {
  return formatRemainingTimeSeconds(remainingTimeSeconds(job, printer));
}
