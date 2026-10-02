import type { V6Job, V6Printer } from "./v6-api.js";

export type LivePrintPhase = Readonly<{
  currentKey: string;
  currentLabel: string;
  detail: string;
  activeIndex: number;
  seenKeys: readonly string[];
  phases: readonly Readonly<{ key: string; label: string; state: "done" | "current" | "pending" | "error" }>[];
}>;

function numberValue(value: unknown): number | null {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function hasModelStarted(job: V6Job | null | undefined, printer: V6Printer | null | undefined): boolean {
  const progress = numberValue(job?.progress) ?? numberValue((printer as unknown as Readonly<Record<string, unknown>> | null | undefined)?.progress) ?? 0;
  const layer = numberValue((job as unknown as Readonly<Record<string, unknown>> | null | undefined)?.current_layer) ?? numberValue((printer as unknown as Readonly<Record<string, unknown>> | null | undefined)?.current_layer) ?? 0;
  return progress > 0 || layer > 0;
}

export function printLayerLabel(job: V6Job | null | undefined, printer: V6Printer | null | undefined): string {
  const source = { ...(printer as unknown as Record<string, unknown> | null || {}), ...(job as unknown as Record<string, unknown> | null || {}) };
  const current = numberValue(source.current_layer ?? source.layer_current ?? source.layer);
  const total = numberValue(source.total_layers ?? source.layer_total ?? source.layers_total);
  if (current !== null && total !== null && total > 0) return `Layer ${Math.max(0, Math.round(current))} / ${Math.round(total)}`;
  if (current !== null) return `Layer ${Math.max(0, Math.round(current))}`;
  return "Layer unbekannt";
}

export function printSpeedLabel(printer: V6Printer | null | undefined): string {
  const raw = printer as unknown as Readonly<Record<string, unknown>> | null | undefined;
  const speed = numberValue(raw?.speed_percent ?? raw?.speed_percentage ?? raw?.print_speed_percent);
  if (speed !== null && speed > 0) return `${Math.round(speed)} %`;
  const profile = String(raw?.speed_profile || raw?.printing_speed || "").trim();
  return profile || "Standard";
}

export function resolveLivePrintPhase(job: V6Job, printer: V6Printer | null, localSeen: ReadonlySet<string> = new Set()): LivePrintPhase {
  const status = String(job.status || (printer as unknown as Readonly<Record<string, unknown>> | null)?.state || "").toLowerCase();
  const started = hasModelStarted(job, printer);
  const error = ["failed", "error", "cancelled"].includes(status);
  const currentKey = error ? "error" : started ? "printing_model" : status.includes("pause") ? "printing_model" : "homing";
  const order = ["bed_heating", "homing", "filament_loading", "flow_calibration", "mechanical_check", "nozzle_cleaning_after", "bed_leveling", "printing_model", "completed"];
  const labels: Record<string, string> = {
    bed_heating: "Bett heizt",
    homing: "Homing",
    filament_loading: "Filament wird geladen",
    flow_calibration: "Flow-Kalibrierung",
    mechanical_check: "Mechanikprüfung",
    nozzle_cleaning_after: "Düse reinigen",
    bed_leveling: "Auto-Leveling",
    printing_model: "Modell wird gedruckt",
    completed: "Abgeschlossen",
    error: "Drucker meldet Fehler",
  };
  const activeIndex = Math.max(0, order.indexOf(currentKey));
  const seen = new Set(localSeen);
  if (!error) {
    for (let index = 0; index <= activeIndex; index += 1) seen.add(order[index]!);
  }
  const phases = order.map((key, index) => ({
    key,
    label: labels[key] || key,
    state: error ? "error" as const : index === activeIndex ? "current" as const : seen.has(key) || index < activeIndex ? "done" as const : "pending" as const,
  }));
  return {
    currentKey,
    currentLabel: labels[currentKey] || "Druckstatus",
    detail: status ? `Status: ${status}` : "Live-Telemetrie wird empfangen",
    activeIndex,
    seenKeys: [...seen],
    phases,
  };
}