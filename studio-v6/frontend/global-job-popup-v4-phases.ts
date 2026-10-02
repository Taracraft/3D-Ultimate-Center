import type { V6Printer } from "./v6-api.js";

const PHASES = [
  ["filament_unloading", "Filament zurückziehen"],
  ["filament_loading", "Filament einziehen"],
  ["filament_purging", "Altes Filament ausspülen"],
  ["nozzle_cleaning", "Druckkopf reinigen"],
  ["flow_calibration", "Fluss kalibrieren"],
  ["bed_leveling", "Druckbett nivellieren"],
  ["test_strip", "Teststreifen drucken"],
  ["printing_model", "Modell drucken"],
  ["completed", "Abschluss"],
] as const;

const esc = (value: unknown): string => String(value ?? "").replace(/[&<>"']/g, (character) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[character] || character));

export function renderPopupPhases(printer: V6Printer | null): string {
  if (!printer) return "";
  const key = String(printer.print_stage_key || "");
  const activeIndex = PHASES.findIndex(([phase]) => phase === key);
  const steps = PHASES.map(([phase, label], index) => {
    const stateClass = phase === key ? "active" : activeIndex >= 0 && index < activeIndex ? "done" : "";
    const marker = phase === key ? "●" : activeIndex >= 0 && index < activeIndex ? "✓" : "○";
    return `<li class="${stateClass}"><span>${marker}</span>${esc(label)}</li>`;
  }).join("");
  return `<div class="current"><b>${esc(printer.print_stage_label || "Druckstatus wird ermittelt")}</b><small>${esc(printer.print_stage_detail || "Der nächste Druckerschritt wird erwartet.")}</small></div><ol>${steps}</ol>`;
}

export { esc };