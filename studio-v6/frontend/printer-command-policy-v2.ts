import type { V6CommandCapability, V6Job, V6Printer } from "./v6-api.js";

export type PrinterCommand = "pause" | "resume" | "retry" | "stop";

const RUNNING_STATES = new Set([
  "running",
  "printing",
  "prepare",
  "preparing",
  "starting",
]);
const PAUSED_STATES = new Set(["pause", "paused"]);
const ACTIVE_STATES = new Set([...RUNNING_STATES, ...PAUSED_STATES]);
const TERMINAL_STATES = new Set([
  "finish",
  "finished",
  "complete",
  "completed",
  "failed",
  "error",
  "cancelled",
  "canceled",
  "stopped",
  "replaced",
]);

const LABELS: Readonly<Record<PrinterCommand, string>> = {
  pause: "Pausieren",
  resume: "Fortsetzen",
  retry: "Erneut versuchen",
  stop: "Abbrechen",
};

export function normalizePrintState(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

export function printStatusLabel(value: unknown): string {
  const state = normalizePrintState(value);
  return ({
    idle: "Bereit",
    running: "Druckt",
    printing: "Druckt",
    prepare: "Vorbereitung",
    preparing: "Vorbereitung",
    starting: "Startet",
    pause: "Pausiert",
    paused: "Pausiert",
    finish: "Fertig",
    finished: "Fertig",
    complete: "Fertig",
    completed: "Fertig",
    failed: "Fehlgeschlagen",
    error: "Fehler",
    cancelled: "Abgebrochen",
    canceled: "Abgebrochen",
    stopped: "Gestoppt",
    replaced: "Ersetzt",
    queued: "Warteschlange",
  } as Record<string, string>)[state] || String(value || "Unbekannt");
}

export function commandLabel(command: PrinterCommand): string {
  return LABELS[command];
}

export function isActivePrintState(value: unknown): boolean {
  return ACTIVE_STATES.has(normalizePrintState(value));
}

export function isPausedPrintState(value: unknown): boolean {
  return PAUSED_STATES.has(normalizePrintState(value));
}

export function isTerminalPrintState(value: unknown): boolean {
  return TERMINAL_STATES.has(normalizePrintState(value));
}

export function isQueuedJob(job: V6Job): boolean {
  return normalizePrintState(job.status) === "queued"
    || String(job.job_id || job.id || "").startsWith("queue:");
}

export function effectivePrintState(
  job: V6Job | null | undefined,
  printer: V6Printer | null | undefined,
): string {
  const printerState = normalizePrintState(printer?.printer_state);
  const jobState = normalizePrintState(job?.status);
  if (PAUSED_STATES.has(printerState)) return printerState;
  return jobState || printerState;
}

export function resolvePrinterForJob(
  job: V6Job | null | undefined,
  printers: readonly V6Printer[],
): V6Printer | null {
  const printerId = String(job?.printer_id || "").trim();
  if (printerId) {
    const exact = printers.find(
      (printer) => String(printer.printer_id || "") === printerId,
    );
    if (exact) return exact;
  }
  return printers.length === 1 ? printers[0] ?? null : null;
}

export function capabilityEnabled(
  capabilities: readonly V6CommandCapability[],
  command: PrinterCommand,
): boolean {
  return capabilities.some(
    (item) => item.command === command && item.enabled === true,
  );
}

export function commandAllowedForState(
  command: PrinterCommand,
  state: unknown,
): boolean {
  const normalized = normalizePrintState(state);
  if (command === "pause") return RUNNING_STATES.has(normalized);
  if (command === "resume" || command === "retry") return PAUSED_STATES.has(normalized);
  return ACTIVE_STATES.has(normalized);
}

export function commandAvailable(
  command: PrinterCommand,
  printer: V6Printer | null | undefined,
  capabilities: readonly V6CommandCapability[],
  job?: V6Job | null,
): boolean {
  if (!printer) return false;
  if (normalizePrintState(printer.connection_state) !== "connected") return false;
  if (!capabilityEnabled(capabilities, command)) return false;
  return commandAllowedForState(command, effectivePrintState(job, printer));
}

export function commandConfirmation(
  command: PrinterCommand,
  printer: V6Printer,
  job?: V6Job | null,
): string {
  const printerName = String(printer.name || printer.printer_id || "Drucker");
  const modelName = String(
    job?.file || job?.model_name || printer.current_file || "Aktiver Druckauftrag",
  );
  const warning = command === "stop"
    ? "\n\nDer laufende Druck wird endgültig abgebrochen und nicht automatisch neu gestartet."
    : command === "retry"
      ? "\n\nV6 fordert den Drucker auf, den fehlgeschlagenen AMS-/Filamentvorgang erneut auszuführen."
      : "";
  return `Drucker: ${printerName}\nAuftrag: ${modelName}${warning}`;
}