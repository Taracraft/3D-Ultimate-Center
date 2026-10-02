import { fetchDetailedDirectPrintStatus, type DetailedAmsSlot } from "./direct-print-status-api.js";
import type {
  SliceModelInspection,
  SliceModelObject,
  SliceModelPart,
  SliceProjectFilament,
  SlicePurgeTower,
} from "./slicing-api.js";
import type { SliceMaterialPlan } from "./plate-slice-api.js";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

export type MultimaterialState = {
  assignments: Record<string, number>;
  filaments: SliceProjectFilament[];
  purgeTower: SlicePurgeTower;
  amsSlots: DetailedAmsSlot[];
  printerName: string;
  loading: boolean;
  error: string;
};

function walkParts(item: SliceModelPart): SliceModelPart[] {
  return [item, ...item.parts.flatMap(walkParts)];
}

export function createMultimaterialState(inspection: SliceModelInspection | null): MultimaterialState {
  const assignments: Record<string, number> = {};
  for (const object of inspection?.objects ?? []) {
    for (const item of walkParts(object)) {
      if (item.object_id && Number.isInteger(item.extruder) && Number(item.extruder) > 0) {
        assignments[item.object_id] = Number(item.extruder);
      }
    }
  }
  return {
    assignments,
    filaments: [...(inspection?.filaments ?? [])],
    purgeTower: { ...(inspection?.purge_tower ?? {}) },
    amsSlots: [],
    printerName: "",
    loading: false,
    error: "",
  };
}

export async function loadAmsIntoState(state: MultimaterialState): Promise<void> {
  state.loading = true;
  state.error = "";
  try {
    const status = await fetchDetailedDirectPrintStatus();
    const printer = status.items.find((item) => item.ams.available && item.ams.slots.some((slot) => slot.present))
      ?? status.items.find((item) => item.ams.available);
    state.amsSlots = printer?.ams.slots.filter((slot) => slot.present) ?? [];
    state.printerName = printer?.name ?? "";
    if (!state.filaments.length && state.amsSlots.length) {
      state.filaments = state.amsSlots.map((slot, index) => ({
        extruder: index + 1,
        name: slot.sub_brand || slot.material || `AMS ${slot.display_slot}`,
        material: slot.material || "unknown",
        color: slot.color,
      }));
    }
  } catch (error) {
    state.error = error instanceof Error ? error.message : String(error);
  } finally {
    state.loading = false;
  }
}

function colorForExtruder(state: MultimaterialState, extruder: number | null): string {
  return state.filaments.find((item) => item.extruder === extruder)?.color
    ?? state.amsSlots.find((slot) => slot.display_slot === extruder)?.color
    ?? "#6B7785";
}

function filamentOptions(state: MultimaterialState, selected: number | null): string {
  const known = new Map<number, { name: string; material: string; color: string | null }>();
  for (const item of state.filaments) {
    known.set(item.extruder, { name: item.name, material: item.material, color: item.color });
  }
  state.amsSlots.forEach((slot, index) => {
    const extruder = index + 1;
    known.set(extruder, {
      name: `AMS ${slot.display_slot}: ${slot.sub_brand || slot.material || "Filament"}`,
      material: slot.material,
      color: slot.color,
    });
  });
  return [...known.entries()].map(([extruder, item]) => `
    <option value="${extruder}" ${selected === extruder ? "selected" : ""}>
      ${esc(item.name)} · ${esc(item.material)}
    </option>`).join("");
}

function objectRow(item: SliceModelPart, state: MultimaterialState, depth: number): string {
  const selected = state.assignments[item.object_id] ?? item.extruder ?? 1;
  const parts = item.parts.map((part) => objectRow(part, state, depth + 1)).join("");
  return `<div class="material-node" style="--depth:${depth}">
    <div class="material-row">
      <span class="material-color" style="background:${esc(colorForExtruder(state, selected))}"></span>
      <span class="material-name"><b>${esc(item.name)}</b><small>${esc(item.type)} · ID ${esc(item.object_id)}</small></span>
      <select data-material-object="${esc(item.object_id)}">${filamentOptions(state, selected)}</select>
    </div>
    ${parts}
  </div>`;
}

export function renderMultimaterialPanel(inspection: SliceModelInspection | null, state: MultimaterialState): string {
  if (!inspection) return '<div class="loading">3MF wird analysiert …</div>';
  if (inspection.format !== "3mf") return '<div class="loading">Mehrmaterial-Zuordnung ist für Projekt-3MF verfügbar.</div>';
  const objects = inspection.objects.filter((item) => item.plate_index === null || item.plate_index >= 0);
  const used = new Set(Object.values(state.assignments));
  const purgeEnabled = used.size > 1;
  const slots = state.amsSlots.map((slot, index) => `
    <div class="ams-slot">
      <span class="material-color" style="background:${esc(slot.color || "#6B7785")}"></span>
      <b>AMS ${slot.display_slot}</b>
      <small>${esc(slot.sub_brand || slot.material)}${slot.remaining_percent === null ? "" : ` · ${slot.remaining_percent}%`}</small>
      <span>Extruder ${index + 1}</span>
    </div>`).join("");
  return `<div class="multimaterial-panel">
    <div class="mm-head"><div><b>Mehrmaterial & AMS</b><small>${state.printerName ? esc(state.printerName) : "Projektfilamente"}</small></div><button type="button" data-action="reload-ams">AMS aktualisieren</button></div>
    ${state.error ? `<div class="error">${esc(state.error)}</div>` : ""}
    <div class="ams-grid">${slots || '<span class="loading">Keine belegten AMS-Slots erkannt.</span>'}</div>
    <div class="object-tree">${objects.map((item) => objectRow(item, state, 0)).join("") || '<span class="loading">Kein Bambu-Objektbaum in dieser 3MF gefunden.</span>'}</div>
    <div class="purge-card">
      <label><input type="checkbox" data-purge-enabled ${purgeEnabled ? "checked" : ""}> Reinigungsturm verwenden</label>
      <div><span>Verwendete Filamente</span><b>${used.size || 1}</b></div>
      <div><span>Breite</span><input data-purge-width type="number" min="10" max="80" step="1" value="${Number(state.purgeTower.width_mm ?? 35)}"></div>
      <div><span>Flush-Multiplikator</span><input data-flush-multiplier type="number" min="0.1" max="3" step="0.05" value="${Number(state.purgeTower.flush_multiplier ?? 1)}"></div>
    </div>
  </div>`;
}

export function bindMultimaterialPanel(
  root: ParentNode,
  state: MultimaterialState,
  onChange: () => void,
  onReload: () => Promise<void>,
): void {
  root.querySelectorAll<HTMLSelectElement>("[data-material-object]").forEach((select) => {
    select.addEventListener("change", () => {
      const objectId = select.dataset.materialObject || "";
      if (objectId) state.assignments[objectId] = Number(select.value);
      const used = new Set(Object.values(state.assignments));
      state.purgeTower = { ...state.purgeTower, enabled: used.size > 1 };
      onChange();
    });
  });
  root.querySelector<HTMLButtonElement>('[data-action="reload-ams"]')?.addEventListener("click", () => void onReload());
  root.querySelector<HTMLInputElement>("[data-purge-enabled]")?.addEventListener("change", (event) => {
    state.purgeTower = { ...state.purgeTower, enabled: (event.currentTarget as HTMLInputElement).checked };
    onChange();
  });
  root.querySelector<HTMLInputElement>("[data-purge-width]")?.addEventListener("change", (event) => {
    state.purgeTower = { ...state.purgeTower, width_mm: Number((event.currentTarget as HTMLInputElement).value) };
    onChange();
  });
  root.querySelector<HTMLInputElement>("[data-flush-multiplier]")?.addEventListener("change", (event) => {
    state.purgeTower = { ...state.purgeTower, flush_multiplier: Number((event.currentTarget as HTMLInputElement).value) };
    onChange();
  });
}

export function materialPlan(state: MultimaterialState): SliceMaterialPlan {
  return {
    assignments: { ...state.assignments },
    filaments: [...state.filaments],
    purge_tower: { ...state.purgeTower },
  };
}