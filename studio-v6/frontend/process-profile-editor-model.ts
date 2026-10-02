import { nozzleProcessContract } from "./nozzle-process-contract.js";

export const PROCESS_EDITOR_FIELDS = [
  { key: "layer_height_mm", label: "Schichthöhe", unit: "mm", min: 0.04, step: "any" },
  { key: "first_layer_height_mm", label: "Erste Schicht", unit: "mm", min: 0.04, step: "any" },
  { key: "walls", label: "Wandlinien", unit: "Linien", min: 0, step: "1" },
  { key: "top_shell_layers", label: "Deckschichten", unit: "Schichten", min: 0, step: "1" },
  { key: "bottom_shell_layers", label: "Bodenschichten", unit: "Schichten", min: 0, step: "1" },
  { key: "infill_percent", label: "Füllgrad", unit: "%", min: 0, step: "any" },
  { key: "outer_wall_speed_mm_s", label: "Außenwandgeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "inner_wall_speed_mm_s", label: "Innenwandgeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "travel_speed_mm_s", label: "Verfahrgeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "line_width_mm", label: "Linienbreite", unit: "mm", min: 0.01, step: "any" },
  { key: "outer_wall_line_width_mm", label: "Außenwand-Linienbreite", unit: "mm", min: 0.01, step: "any" },
  { key: "inner_wall_line_width_mm", label: "Innenwand-Linienbreite", unit: "mm", min: 0.01, step: "any" },
  { key: "top_surface_line_width_mm", label: "Deckflächen-Linienbreite", unit: "mm", min: 0.01, step: "any" },
  { key: "support_line_width_mm", label: "Support-Linienbreite", unit: "mm", min: 0.01, step: "any" },
  { key: "sparse_infill_speed_mm_s", label: "Infillgeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "internal_solid_infill_speed_mm_s", label: "Massivfüllung-Geschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "top_surface_speed_mm_s", label: "Deckflächengeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "initial_layer_speed_mm_s", label: "Geschwindigkeit erste Schicht", unit: "mm/s", min: 1, step: "any" },
  { key: "bridge_speed_mm_s", label: "Brückengeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "gap_infill_speed_mm_s", label: "Lückenfüllung-Geschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "solid_infill_speed_mm_s", label: "Solide Füllung-Geschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "ironing_speed_mm_s", label: "Bügelgeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "support_speed_mm_s", label: "Supportgeschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "support_interface_speed_mm_s", label: "Support-Interface-Geschwindigkeit", unit: "mm/s", min: 1, step: "any" },
  { key: "bridge_flow_ratio", label: "Brückenfluss", unit: "Faktor", min: 0, step: "any" },
  { key: "support_top_z_distance_mm", label: "Supportabstand oben", unit: "mm", min: 0, step: "any" },
  { key: "support_bottom_z_distance_mm", label: "Supportabstand unten", unit: "mm", min: 0, step: "any" },
  { key: "support_object_xy_distance_mm", label: "Supportabstand seitlich", unit: "mm", min: 0, step: "any" },
  { key: "support_interface_spacing_mm", label: "Support-Interface-Abstand", unit: "mm", min: 0, step: "any" },
  { key: "support_interface_top_layers", label: "Support-Interfaceschichten oben", unit: "Schichten", min: 0, step: "1" },
  { key: "support_interface_bottom_layers", label: "Support-Interfaceschichten unten", unit: "Schichten", min: 0, step: "1" },
] as const;

export function processFieldBounds(key: string, diameter: unknown): { min: number; max?: number } {
  const field = PROCESS_EDITOR_FIELDS.find((item) => item.key === key);
  const nozzle = nozzleProcessContract(diameter);
  if (key === "layer_height_mm" || key === "first_layer_height_mm") {
    return { min: nozzle?.min_layer_height_mm ?? .04, max: nozzle?.max_layer_height_mm ?? .56 };
  }
  if (key === "infill_percent") return { min: 0, max: 100 };
  if (key === "outer_wall_speed_mm_s" || key === "inner_wall_speed_mm_s") return { min: 1, max: nozzle?.max_wall_speed_mm_s ?? 500 };
  return { min: field?.min ?? 0 };
}

export function validateProcessEditor(payload: Readonly<Record<string, unknown>>, diameter: unknown): Map<string, string> {
  const errors = new Map<string, string>();
  const nozzle = nozzleProcessContract(diameter);
  for (const field of PROCESS_EDITOR_FIELDS) {
    if (!Object.prototype.hasOwnProperty.call(payload, field.key)) continue;
    const raw = payload[field.key];
    const value = typeof raw === "number" || (typeof raw === "string" && raw.trim() !== "") ? Number(raw) : NaN;
    const bounds = processFieldBounds(field.key, diameter);
    if (!Number.isFinite(value) || value < bounds.min || (bounds.max !== undefined && value > bounds.max) || (field.step === "1" && !Number.isInteger(value))) {
      errors.set(field.key, `${field.label}: ${field.step === "1" ? "ganze Zahl" : "Zahl"} ab ${bounds.min}${bounds.max !== undefined ? ` bis ${bounds.max}` : ""} ${field.unit} eingeben.`);
    } else if ((field.key === "layer_height_mm" || field.key === "first_layer_height_mm") && !nozzle) {
      errors.set(field.key, "Zuerst eine validierte A1-Düse auswählen.");
    }
  }
  if (!PROCESS_EDITOR_FIELDS.some((field) => Object.prototype.hasOwnProperty.call(payload, field.key))) {
    errors.set("_process", "Mindestens einen Prozesswert angeben; ein leeres Prozessprofil kann noch nicht angewandt werden.");
  }
  const declared = payload.nozzle_diameter_mm;
  if (declared !== undefined && (!nozzle || typeof declared === "boolean" || !Number.isFinite(Number(declared)) || Math.abs(Number(declared) - nozzle.diameter_mm) > .000001)) {
    errors.set("nozzle_diameter_mm", "Prozessprofil und ausgewählte Düse stimmen nicht überein.");
  }
  return errors;
}

export function processProfileChanges(before: Readonly<Record<string, unknown>>, after: Readonly<Record<string, unknown>>): Array<{ key: string; before: unknown; after: unknown }> {
  return [...new Set([...Object.keys(before), ...Object.keys(after)])].sort().filter((key) => JSON.stringify(before[key]) !== JSON.stringify(after[key])).map((key) => ({ key, before: before[key], after: after[key] }));
}

