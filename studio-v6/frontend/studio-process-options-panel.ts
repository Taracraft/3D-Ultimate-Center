import {
  DEFAULT_SLICE_PROCESS_OVERRIDES,
  SLICER_PROCESS_OPTIONS_KEY,
  loadSliceProcessOverrides,
  saveSliceProcessOverrides,
  type AdhesionMode,
  type LayerHeightRange,
  type SliceProcessOverrides,
  type SupportMode,
  type SupportStyle,
} from "./plate-slice-api.js";
import { nozzleProcessContract } from "./nozzle-process-contract.js";
import { PROCESS_EDITOR_FIELDS, processFieldBounds } from "./process-profile-editor-model.js";
import { loadPlatePurgeTower, savePlatePurgeTower } from "./purge-tower-state.js";
import type { SlicePurgeTower } from "./slicing-api.js";

const PLATE_KEY_PREFIX = "ultimate-3d-studio-v6:slicer-process-options:plate:";

function clamp(value: unknown, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(minimum, Math.min(maximum, parsed)) : fallback;
}

function optionalNumber(value: unknown, minimum: number, maximum: number): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : null;
}

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"\']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function processEditorFieldsFromStored(value: Readonly<Record<string, unknown>>, diameter: unknown): Partial<Record<string, number | null>> {
  const result: Partial<Record<string, number | null>> = {};
  for (const field of PROCESS_EDITOR_FIELDS) {
    if (!Object.prototype.hasOwnProperty.call(value, field.key)) continue;
    const raw = value[field.key];
    if (raw === null || raw === undefined || raw === "") {
      result[field.key] = null;
      continue;
    }
    const parsed = Number(raw);
    const bounds = processFieldBounds(field.key, diameter);
    if (!Number.isFinite(parsed) || parsed < bounds.min || (bounds.max !== undefined && parsed > bounds.max)) continue;
    if (field.step === "1" && !Number.isInteger(parsed)) continue;
    result[field.key] = parsed;
  }
  return result;
}

function processEditorRows(value: SliceProcessOverrides, diameter: unknown): string {
  return PROCESS_EDITOR_FIELDS.map((field) => {
    const bounds = processFieldBounds(field.key, diameter);
    const current = value[field.key as keyof SliceProcessOverrides] as number | null | undefined;
    const max = bounds.max === undefined ? "" : " max=\"" + bounds.max + "\"";
    const fieldValue = current === null || current === undefined ? "" : esc(current);
    return "<label><span>" + esc(field.label) + "</span><input data-process-editor-field=\"" + esc(field.key) + "\" type=\"number\" inputmode=\"decimal\" min=\"" + bounds.min + "\"" + max + " step=\"" + esc(field.step) + "\" value=\"" + fieldValue + "\" placeholder=\"Standard\"><small>" + esc(field.unit) + "</small></label>";
  }).join("");
}
function normalizeLayerHeightRanges(value: unknown): LayerHeightRange[] {
  if (!Array.isArray(value)) return [];
  const ranges: LayerHeightRange[] = [];
  let previousMax = 0;
  for (const item of value.slice(0, 32)) {
    const row = item as Record<string, unknown>;
    const min = Number(row.min_z_mm ?? row.min_z);
    const max = Number(row.max_z_mm ?? row.max_z);
    const height = Number(row.layer_height_mm ?? row.layer_height);
    if (!Number.isFinite(min) || !Number.isFinite(max) || !Number.isFinite(height)) continue;
    if (min < 0 || max <= min || max > 256 || min < previousMax) continue;
    if (height < .04 || height > .56) continue;
    ranges.push({ min_z_mm: min, max_z_mm: max, layer_height_mm: height });
    previousMax = max;
  }
  return ranges;
}

function parseStored(raw: string | null): SliceProcessOverrides | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<SliceProcessOverrides>;
    return {
      adhesion_mode: ["none", "brim", "raft"].includes(String(value.adhesion_mode)) ? value.adhesion_mode as AdhesionMode : "none",
      brim_width_mm: clamp(value.brim_width_mm, 5, 1, 30),
      raft_layers: Math.round(clamp(value.raft_layers, 2, 1, 10)),
      support_mode: ["off", "normal", "tree"].includes(String(value.support_mode)) ? value.support_mode as SupportMode : "off",
      support_style: ["standard", "tree_slim", "tree_strong", "tree_hybrid", "tree_organic"].includes(String(value.support_style)) ? value.support_style as SupportStyle : "standard",
      support_build_plate_only: value.support_build_plate_only !== false,
      support_threshold_angle: Math.round(clamp(value.support_threshold_angle, 30, 0, 89)),
      layer_height_mm: optionalNumber(value.layer_height_mm, .04, .56),
      outer_wall_speed_mm_s: optionalNumber(value.outer_wall_speed_mm_s, 1, 500),
      inner_wall_speed_mm_s: optionalNumber(value.inner_wall_speed_mm_s, 1, 500),
      layer_height_ranges: normalizeLayerHeightRanges(value.layer_height_ranges),
      ...processEditorFieldsFromStored(value as Record<string, unknown>, (value as Record<string, unknown>).nozzle_diameter_mm),
    };
  } catch {
    return null;
  }
}



function layerHeightFromCurvePointer(event: PointerEvent, element: HTMLElement, ranges: readonly LayerHeightRange[], presets: readonly number[] = []): { index: number; height: number } | null {
  if (!ranges.length) return null;
  const rect = element.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return null;
  const maxZ = Math.max(1, ...ranges.map((range) => range.max_z_mm));
  const z = Math.max(0, Math.min(maxZ, (event.clientX - rect.left) / rect.width * maxZ));
  const index = ranges.findIndex((range, at) => z >= range.min_z_mm && (z < range.max_z_mm || at === ranges.length - 1 && z <= range.max_z_mm));
  if (index < 0) return null;
  const top = Math.max(0, Math.min(1, (event.clientY - rect.top - 6) / Math.max(1, rect.height - 24)));
  const height = Math.round((.56 - top * (.56 - .04)) * 100) / 100;
  const clamped = Math.max(.04, Math.min(.56, height));
  const snapped = nearestLayerHeightPreset(clamped, presets);
  return { index, height: snapped };
}

function formatRangeNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function nozzleLayerHeightBounds(diameterMm: string | null): { minimum: number; maximum: number; fallback: number; label: string } {
  const contract = nozzleProcessContract(diameterMm);
  return {
    minimum: contract?.min_layer_height_mm ?? .04,
    maximum: contract?.max_layer_height_mm ?? .56,
    fallback: contract?.default_layer_height_mm ?? .2,
    label: contract ? `${formatRangeNumber(contract.diameter_mm)} mm Duese` : "Allgemeiner Bereich",
  };
}

function nozzleLayerHeightPresetValues(diameterMm: string | null): number[] {
  const { minimum, maximum, fallback } = nozzleLayerHeightBounds(diameterMm);
  const values: number[] = [];
  for (let index = 0; index <= 5; index += 1) {
    values.push(Math.round((minimum + (maximum - minimum) * index / 5) * 100) / 100);
  }
  values.push(Math.round(fallback * 100) / 100);
  return [...new Set(values)]
    .filter((value) => value >= minimum && value <= maximum)
    .sort((left, right) => left - right);
}

function nearestLayerHeightPreset(height: number, presets: readonly number[]): number {
  if (!presets.length) return height;
  return presets.reduce((best, value) => Math.abs(value - height) < Math.abs(best - height) ? value : best, presets[0]!);
}

function layerHeightPresetHtml(diameterMm: string | null, disabled: boolean): string {
  const presets = nozzleLayerHeightPresetValues(diameterMm);
  const bounds = nozzleLayerHeightBounds(diameterMm);
  const label = `${bounds.label} · ${formatRangeNumber(bounds.minimum)}-${formatRangeNumber(bounds.maximum)} mm`;
  return `<div class="range-presets" aria-label="Schichthoehen-Presets"><span>${label}</span>${presets.map((value) => `<button type="button" data-layer-height-preset="${value}" ${disabled ? "disabled" : ""}>${formatRangeNumber(value)}</button>`).join("")}</div>`;
}

function layerHeightCurveHtml(ranges: readonly LayerHeightRange[], previewZ: number | null): string {
  if (!ranges.length) return "";
  const maxZ = Math.max(1, ...ranges.map((range) => range.max_z_mm));
  const activeIndex = previewZ === null ? -1 : ranges.findIndex((range, at) => previewZ >= range.min_z_mm && (previewZ < range.max_z_mm || at === ranges.length - 1 && previewZ <= range.max_z_mm));
  const heights = ranges.map((range) => range.layer_height_mm);
  const minHeight = Math.min(...heights);
  const maxHeight = Math.max(...heights);
  const span = Math.max(.001, maxHeight - minHeight);
  const bars = ranges.map((range, index) => {
    const left = Math.max(0, Math.min(100, range.min_z_mm / maxZ * 100));
    const width = Math.max(2, Math.min(100 - left, (range.max_z_mm - range.min_z_mm) / maxZ * 100));
    const barHeight = 18 + (range.layer_height_mm - minHeight) / span * 28;
    const label = `${formatRangeNumber(range.min_z_mm)}-${formatRangeNumber(range.max_z_mm)} mm · ${formatRangeNumber(range.layer_height_mm)} mm`;
    return `<span class="range-curve-bar ${index === activeIndex ? "active" : ""}" data-range-curve="${index}" title="${label}" style="left:${left.toFixed(2)}%;width:${width.toFixed(2)}%;height:${barHeight.toFixed(2)}px"><b>${formatRangeNumber(range.layer_height_mm)}</b><i></i></span>`;
  }).join("");
  return `<div class="range-curve" role="img" aria-label="Variable Schichthoehen von 0 bis ${formatRangeNumber(maxZ)} Millimeter">${bars}<span class="range-curve-axis">0 mm</span><span class="range-curve-axis end">${formatRangeNumber(maxZ)} mm</span></div>`;
}

function rangeRows(ranges: readonly LayerHeightRange[], diameterMm: string | null): string {
  const bounds = nozzleLayerHeightBounds(diameterMm);
  return ranges.map((range, index) => (
    `<div class="range-row" data-range="${index}">
      <label>Von Z<input data-range-field="min_z_mm" type="number" min="0" max="256" step="0.1" value="${range.min_z_mm}"></label>
      <label>Bis Z<input data-range-field="max_z_mm" type="number" min="0" max="256" step="0.1" value="${range.max_z_mm}"></label>
      <label>Layer<input data-range-field="layer_height_mm" type="number" min="${bounds.minimum}" max="${bounds.maximum}" step="0.01" value="${range.layer_height_mm}"></label>
      <button type="button" data-split-range="${index}" title="Bereich teilen">↕</button>
      <button type="button" data-merge-range="${index}" ${index === 0 ? "disabled" : ""} title="Mit vorigem Bereich verbinden">⇤</button>
      <button type="button" data-remove-range="${index}" title="Bereich entfernen">×</button>
    </div>`
  )).join("");
}

export class StudioProcessOptionsPanel extends HTMLElement {
  static get observedAttributes(): string[] { return ["plate-id", "nozzle-diameter", "preview-z-mm"]; }

  readonly #root = this.attachShadow({ mode: "open" });
  #value: SliceProcessOverrides = DEFAULT_SLICE_PROCESS_OVERRIDES;
  #purge: SlicePurgeTower = {};
  #studioRoot: ShadowRoot | null = null;
  #activeLayerHeightRangeIndex = 0;

  connectedCallback(): void {
    this.#load();
    this.#studioRoot = this.getRootNode() instanceof ShadowRoot ? this.getRootNode() as ShadowRoot : null;
    this.#studioRoot?.addEventListener("change", this.#studioChanged);
    this.#studioRoot?.addEventListener("click", this.#studioChanged);
    this.#render();
  }

  disconnectedCallback(): void {
    this.#studioRoot?.removeEventListener("change", this.#studioChanged);
    this.#studioRoot?.removeEventListener("click", this.#studioChanged);
    this.#studioRoot = null;
  }

  attributeChangedCallback(): void {
    if (!this.isConnected) return;
    this.#load();
    this.#render();
  }

  readonly #studioChanged = (event: Event): void => {
    if (event.composedPath().includes(this)) return;
    this.#render();
  };

  setSupportMode(mode: SupportMode): void {
    this.#saveProcess({ ...this.#value, support_mode: mode });
    requestAnimationFrame(() => this.#root.querySelector<HTMLSelectElement>("#support-mode")?.focus());
  }
  getProcessOverrides(): SliceProcessOverrides {
    return this.#value;
  }


  #addLayerHeightRange(): void {
    const ranges = normalizeLayerHeightRanges(this.#value.layer_height_ranges);
    this.#activeLayerHeightRangeIndex = ranges.length;
    const start = ranges.at(-1)?.max_z_mm ?? 0;
    const end = Math.min(256, start + 10);
    if (ranges.length >= 32 || end <= start) return;
    this.#saveProcess({
      ...this.#value,
      layer_height_ranges: normalizeLayerHeightRanges([
        ...ranges,
        { min_z_mm: start, max_z_mm: end, layer_height_mm: this.#value.layer_height_mm ?? nozzleLayerHeightBounds(this.getAttribute("nozzle-diameter")).fallback },
      ]),
    });
  }


  #updateLayerHeightFromCurve(event: PointerEvent): void {
    const curve = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
    if (!curve) return;
    const apply = (nextEvent: PointerEvent, focus: boolean): boolean => {
      const ranges = normalizeLayerHeightRanges(this.#value.layer_height_ranges);
      const point = layerHeightFromCurvePointer(nextEvent, curve, ranges, nozzleLayerHeightPresetValues(this.getAttribute("nozzle-diameter")));
      if (!point) return false;
      this.#activeLayerHeightRangeIndex = point.index;
      const next = ranges.map((range, index) => index === point.index ? { ...range, layer_height_mm: point.height } : range);
      this.#saveProcess({ ...this.#value, layer_height_ranges: normalizeLayerHeightRanges(next) });
      if (focus) requestAnimationFrame(() => this.#root.querySelector<HTMLInputElement>(`[data-range="${point.index}"] [data-range-field="layer_height_mm"]`)?.focus());
      return true;
    };
    if (!apply(event, true)) return;
    event.preventDefault();
    const pointerId = event.pointerId;
    try { curve.setPointerCapture(pointerId); } catch {}
    const move = (nextEvent: PointerEvent): void => {
      if (nextEvent.pointerId !== pointerId) return;
      if (nextEvent.buttons === 0) {
        cleanup();
        return;
      }
      nextEvent.preventDefault();
      apply(nextEvent, false);
    };
    const up = (nextEvent: PointerEvent): void => {
      if (nextEvent.pointerId !== pointerId) return;
      cleanup();
    };
    const cleanup = (): void => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      try { curve.releasePointerCapture(pointerId); } catch {}
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
    window.addEventListener("pointercancel", up, { once: true });
  }

  #updateLayerHeightRange(index: number, field: keyof LayerHeightRange, raw: string): void {
    const ranges = normalizeLayerHeightRanges(this.#value.layer_height_ranges);
    const current = ranges[index];
    if (!current) return;
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    const input = this.#root.querySelector<HTMLInputElement>(`[data-range="${index}"] [data-range-field="${field}"]`);
    if (field === "layer_height_mm") {
      const bounds = nozzleLayerHeightBounds(this.getAttribute("nozzle-diameter"));
      if (value < bounds.minimum || value > bounds.maximum) {
        input?.setCustomValidity(`Schichthoehe fuer ${bounds.label} muss zwischen ${formatRangeNumber(bounds.minimum)} und ${formatRangeNumber(bounds.maximum)} mm liegen.`);
        input?.reportValidity();
        return;
      }
    }
    const next = ranges.map((range, at) => at === index ? { ...range, [field]: value } : range);
    const normalized = normalizeLayerHeightRanges(next);
    if (normalized.length !== next.length) {
      input?.setCustomValidity("Bereich muss geordnet, ohne Überlappung und innerhalb 0–256 mm liegen.");
      input?.reportValidity();
      return;
    }
    input?.setCustomValidity("");
    this.#saveProcess({ ...this.#value, layer_height_ranges: normalized });
  }


  #applyLayerHeightPreset(raw: string | undefined): void {
    const ranges = normalizeLayerHeightRanges(this.#value.layer_height_ranges);
    if (!ranges.length) return;
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    const index = Math.max(0, Math.min(ranges.length - 1, this.#activeLayerHeightRangeIndex));
    const next = ranges.map((range, at) => at === index ? { ...range, layer_height_mm: value } : range);
    this.#saveProcess({ ...this.#value, layer_height_ranges: normalizeLayerHeightRanges(next) });
    requestAnimationFrame(() => this.#root.querySelector<HTMLInputElement>(`[data-range="${index}"] [data-range-field="layer_height_mm"]`)?.focus());
  }

  #splitLayerHeightRange(index: number): void {
    const ranges = normalizeLayerHeightRanges(this.#value.layer_height_ranges);
    const current = ranges[index];
    if (!current || ranges.length >= 32) return;
    this.#activeLayerHeightRangeIndex = index + 1;
    const middle = Math.round((current.min_z_mm + current.max_z_mm) / 2 * 100) / 100;
    if (middle <= current.min_z_mm || middle >= current.max_z_mm) return;
    this.#saveProcess({
      ...this.#value,
      layer_height_ranges: normalizeLayerHeightRanges([
        ...ranges.slice(0, index),
        { ...current, max_z_mm: middle },
        { ...current, min_z_mm: middle },
        ...ranges.slice(index + 1),
      ]),
    });
  }

  #mergeLayerHeightRange(index: number): void {
    const ranges = normalizeLayerHeightRanges(this.#value.layer_height_ranges);
    if (index <= 0 || index >= ranges.length) return;
    const previous = ranges[index - 1];
    const current = ranges[index];
    if (!previous || !current) return;
    this.#activeLayerHeightRangeIndex = index - 1;
    this.#saveProcess({
      ...this.#value,
      layer_height_ranges: normalizeLayerHeightRanges([
        ...ranges.slice(0, index - 1),
        { min_z_mm: previous.min_z_mm, max_z_mm: current.max_z_mm, layer_height_mm: current.layer_height_mm },
        ...ranges.slice(index + 1),
      ]),
    });
  }

  #removeLayerHeightRange(index: number): void {
    const ranges = normalizeLayerHeightRanges(this.#value.layer_height_ranges).filter((_, at) => at !== index);
    this.#activeLayerHeightRangeIndex = Math.max(0, Math.min(ranges.length - 1, index));
    this.#saveProcess({ ...this.#value, layer_height_ranges: ranges });
  }

  #updateProcessEditorField(key: string, raw: string): void {
    const field = PROCESS_EDITOR_FIELDS.find((item) => item.key === key);
    if (!field) return;
    if (!raw.trim()) {
      this.#saveProcess({ ...this.#value, [key]: null });
      return;
    }
    const input = this.#root.querySelector<HTMLInputElement>("[data-process-editor-field=\"" + CSS.escape(key) + "\"]");
    const parsed = Number(raw);
    const bounds = processFieldBounds(key, this.getAttribute("nozzle-diameter"));
    if (!Number.isFinite(parsed) || parsed < bounds.min || (bounds.max !== undefined && parsed > bounds.max) || (field.step === "1" && !Number.isInteger(parsed))) {
      input?.setCustomValidity(field.label + ": gültige " + (field.step === "1" ? "ganze " : "") + "Zahl ab " + bounds.min + (bounds.max === undefined ? "" : " bis " + bounds.max) + " " + field.unit + " eingeben.");
      input?.reportValidity();
      return;
    }
    input?.setCustomValidity("");
    this.#saveProcess({ ...this.#value, [key]: parsed });
  }
  get #plateId(): string { return this.getAttribute("plate-id") || "0"; }
  get #plateKey(): string { return `${PLATE_KEY_PREFIX}${this.#plateId}`; }

  #load(): void {
    this.#value = parseStored(localStorage.getItem(this.#plateKey)) ?? loadSliceProcessOverrides();
    this.#purge = loadPlatePurgeTower(this.#plateId);
    saveSliceProcessOverrides(this.#value);
  }

  #colorCount(): number {
    const colors = new Set<string>();
    this.#studioRoot?.querySelectorAll<HTMLElement>(".object .swatch").forEach((swatch) => {
      const color = swatch.style.backgroundColor || swatch.style.background;
      if (color) colors.add(color.toLowerCase());
    });
    return colors.size;
  }

  #saveProcess(next: SliceProcessOverrides): void {
    this.#value = next;
    localStorage.setItem(this.#plateKey, JSON.stringify(next));
    localStorage.setItem(SLICER_PROCESS_OPTIONS_KEY, JSON.stringify(next));
    saveSliceProcessOverrides(next);
    this.#emitChange();
    this.#render();
  }

  #savePurge(next: SlicePurgeTower): void {
    this.#purge = next;
    savePlatePurgeTower(this.#plateId, next);
    this.#emitChange();
    this.#render();
  }

  #emitChange(): void {
    this.dispatchEvent(new CustomEvent("studio-process-options-changed", {
      detail: { plateId: this.#plateId, value: this.#value, purgeTower: this.#purge },
      bubbles: true,
      composed: true,
    }));
  }

  #render(): void {
    const value = this.#value;
    const multicolor = this.#colorCount() > 1;
    const ranges = normalizeLayerHeightRanges(value.layer_height_ranges);
    this.#activeLayerHeightRangeIndex = Math.max(0, Math.min(Math.max(0, ranges.length - 1), this.#activeLayerHeightRangeIndex));
    const nozzleDiameter = this.getAttribute("nozzle-diameter");
    const previewZ = optionalNumber(this.getAttribute("preview-z-mm"), 0, 256);
    this.#root.innerHTML = `<style>
      :host{display:block;width:100%;color:#eef6ff;font:11px/1.25 Inter,Segoe UI,sans-serif}*{box-sizing:border-box}.panel{display:grid;gap:8px}.group{display:grid;gap:5px;padding:8px;border:1px solid #29445c;border-radius:5px;background:#0b1824}.title{font-size:10px;font-weight:800;color:#9ab1c5;text-transform:uppercase;letter-spacing:.04em}.choices{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}.choices.two{grid-template-columns:repeat(2,minmax(0,1fr))}.choice,select,input{min-height:30px;padding:4px 6px;border:1px solid #31506e;border-radius:3px;background:#102335;color:#eef6ff;font-weight:700;font-size:10px}.choice.active{border-color:#54d66c;background:#12391f}label{display:grid;gap:3px;color:#8da4b8}.row{display:grid;grid-template-columns:1fr auto;gap:5px;align-items:center}.row input{width:76px}.check{display:flex;align-items:center;gap:6px}.check input{width:auto;min-height:0}.range-curve{position:relative;height:58px;margin:1px 0 4px;border:1px solid #29445c;border-radius:4px;background:linear-gradient(180deg,#0d1f2d,#08131e);overflow:hidden;cursor:crosshair;touch-action:none}.range-curve:before{content:"";position:absolute;left:0;right:0;bottom:17px;border-top:1px solid rgba(127,210,246,.28)}.range-curve-bar{position:absolute;bottom:18px;display:flex;align-items:flex-start;justify-content:center;min-width:18px;border:1px solid #54d66c;border-radius:3px 3px 0 0;background:linear-gradient(180deg,rgba(84,214,108,.88),rgba(84,214,108,.28));color:#06160a;font-size:9px;font-weight:900;overflow:hidden}.range-curve-bar.active{border-color:#7fd2f6;background:linear-gradient(180deg,rgba(127,210,246,.95),rgba(84,214,108,.34));box-shadow:0 0 0 1px #7fd2f6,0 0 12px rgba(127,210,246,.45)}.range-curve-bar b{padding-top:2px}.range-curve-bar i{position:absolute;left:50%;top:0;width:8px;height:8px;transform:translate(-50%,-50%);border-radius:50%;background:#eef6ff;box-shadow:0 0 0 1px #12391f}.range-curve-axis{position:absolute;left:5px;bottom:3px;color:#7fd2f6;font-size:9px}.range-curve-axis.end{left:auto;right:5px}.range-presets{display:flex;flex-wrap:wrap;align-items:center;gap:4px;margin:1px 0 4px}.range-presets span{margin-right:auto;color:#7fd2f6;font-size:9px}.range-presets button{min-height:24px;padding:3px 6px;border:1px solid #31506e;border-radius:3px;background:#102335;color:#eef6ff;font-size:9px;font-weight:800}.range-presets button:disabled{opacity:.35;cursor:not-allowed}.range-list{display:grid;gap:5px}.range-row{display:grid;grid-template-columns:1fr 1fr 1fr 28px 28px 28px;gap:4px;align-items:end}.range-row input{width:100%;min-width:0}.range-row button{min-height:30px;border:1px solid #31506e;border-radius:3px;background:#102335;color:#7fd2f6;font-weight:900}.range-row button[data-remove-range]{border-color:#5e3141;background:#2a1118;color:#ffc4cf}.range-row button:disabled{opacity:.35;cursor:not-allowed}.range-actions{display:flex;justify-content:flex-end}.process-editor-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.process-editor-grid label{grid-template-columns:minmax(0,1fr) 76px auto;align-items:center}.process-editor-grid label span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.process-editor-grid small{color:#7fd2f6;font-size:9px}.summary{padding:7px;border:1px solid #29445c;border-radius:4px;background:#08131e;color:#7fd2f6;font-size:10px}
    </style><section class="panel">
      <div class="group"><span class="title">Slicer</span><div class="summary">Nativer Linux-Slicing-Server</div></div>
      <div class="group"><span class="title">Druckbetthaftung</span><div class="choices"><button class="choice ${value.adhesion_mode === "none" ? "active" : ""}" data-adhesion="none">Aus</button><button class="choice ${value.adhesion_mode === "brim" ? "active" : ""}" data-adhesion="brim">Brim</button><button class="choice ${value.adhesion_mode === "raft" ? "active" : ""}" data-adhesion="raft">Raft</button></div>${value.adhesion_mode === "brim" ? `<label class="row">Breite <input id="brim-width" type="number" min="1" max="30" step="0.5" value="${value.brim_width_mm}"></label>` : ""}${value.adhesion_mode === "raft" ? `<label class="row">Schichten <input id="raft-layers" type="number" min="1" max="10" step="1" value="${value.raft_layers}"></label>` : ""}</div>
      <div class="group"><span class="title">Stützstrukturen</span><label>Typ<select id="support-mode"><option value="off" ${value.support_mode === "off" ? "selected" : ""}>Aus</option><option value="normal" ${value.support_mode === "normal" ? "selected" : ""}>Normal (auto)</option><option value="tree" ${value.support_mode === "tree" ? "selected" : ""}>Baum (auto)</option></select></label>${value.support_mode !== "off" ? `<label>Stil<select id="support-style"><option value="standard" ${value.support_style === "standard" ? "selected" : ""}>Standard</option><option value="tree_slim" ${value.support_style === "tree_slim" ? "selected" : ""}>Baum schlank</option><option value="tree_strong" ${value.support_style === "tree_strong" ? "selected" : ""}>Baum stark</option><option value="tree_hybrid" ${value.support_style === "tree_hybrid" ? "selected" : ""}>Baum-Hybrid</option><option value="tree_organic" ${value.support_style === "tree_organic" ? "selected" : ""}>Baum Organisch</option></select></label><label class="row">Grenzwinkel <input id="support-angle" type="number" min="0" max="89" step="1" value="${value.support_threshold_angle}"></label><label class="check"><input id="plate-only" type="checkbox" ${value.support_build_plate_only ? "checked" : ""}>Nur vom Druckbett</label><div class="summary">${value.support_build_plate_only ? "Support startet nur auf der Druckplatte." : "Support darf direkt auf Modellflächen starten."}</div>` : ""}</div>
      <div class="group"><span class="title">Variable Schichthöhen</span>${layerHeightPresetHtml(nozzleDiameter, !ranges.length)}${layerHeightCurveHtml(ranges, previewZ)}<div class="range-list">${ranges.length ? rangeRows(ranges, nozzleDiameter) : `<div class="summary">Keine Bereiche aktiv</div>`}</div><div class="range-actions"><button class="choice" id="add-layer-range" type="button">Bereich hinzufügen</button></div></div>
      <div class="group"><span class="title">Prozesswerte</span><div class="process-editor-grid">${processEditorRows(value, nozzleDiameter)}</div><div class="summary">Leere Felder verwenden das gewählte Bambu-Prozessprofil.</div></div>
      ${multicolor ? `<div class="group"><span class="title">Reinigungsturm</span><label class="check"><input id="purge-enabled" type="checkbox" ${this.#purge.enabled !== false ? "checked" : ""}>Aktiv</label></div>` : ""}
      <div class="summary">Slicing Server · ${value.adhesion_mode === "none" ? "Haftung aus" : value.adhesion_mode === "brim" ? `Brim ${value.brim_width_mm} mm` : `Raft ${value.raft_layers}`} · ${value.support_mode === "off" ? "Support aus" : value.support_mode === "tree" ? `Baum-Support / ${value.support_style}` : `Normal-Support / ${value.support_style}`} · ${value.support_build_plate_only ? "nur Druckplatte" : "Modellkontakt erlaubt"} · ${ranges.length ? `${ranges.length} variable Layerbereich(e)` : "Standard-Layerhöhe"}</div>
    </section>`;
    this.#bind(multicolor);
  }

  #bind(multicolor: boolean): void {
    this.#root.querySelectorAll<HTMLButtonElement>("[data-adhesion]").forEach((button) => button.addEventListener("click", () => this.#saveProcess({ ...this.#value, adhesion_mode: button.dataset.adhesion as AdhesionMode })));
    this.#root.querySelector<HTMLSelectElement>("#support-mode")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, support_mode: (event.currentTarget as HTMLSelectElement).value as SupportMode }));
    this.#root.querySelector<HTMLSelectElement>("#support-style")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, support_style: (event.currentTarget as HTMLSelectElement).value as SupportStyle }));
    this.#root.querySelector<HTMLInputElement>("#brim-width")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, brim_width_mm: clamp((event.currentTarget as HTMLInputElement).value, 5, 1, 30) }));
    this.#root.querySelector<HTMLInputElement>("#raft-layers")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, raft_layers: Math.round(clamp((event.currentTarget as HTMLInputElement).value, 2, 1, 10)) }));
    this.#root.querySelector<HTMLInputElement>("#support-angle")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, support_threshold_angle: Math.round(clamp((event.currentTarget as HTMLInputElement).value, 30, 0, 89)) }));
    this.#root.querySelector<HTMLInputElement>("#plate-only")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, support_build_plate_only: (event.currentTarget as HTMLInputElement).checked }));
    this.#root.querySelector<HTMLButtonElement>("#add-layer-range")?.addEventListener("click", () => this.#addLayerHeightRange());
    this.#root.querySelector<HTMLElement>(".range-curve")?.addEventListener("pointerdown", (event) => this.#updateLayerHeightFromCurve(event));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-layer-height-preset]").forEach((button) => {
      button.addEventListener("click", () => this.#applyLayerHeightPreset(button.dataset.layerHeightPreset));
    });
    this.#root.querySelectorAll<HTMLInputElement>("[data-range-field]").forEach((input) => {
      input.addEventListener("focus", () => {
        const row = input.closest<HTMLElement>("[data-range]");
        this.#activeLayerHeightRangeIndex = Number(row?.dataset.range) || 0;
      });
      input.addEventListener("change", () => {
        const row = input.closest<HTMLElement>("[data-range]");
        this.#activeLayerHeightRangeIndex = Number(row?.dataset.range) || 0;
        this.#updateLayerHeightRange(Number(row?.dataset.range), input.dataset.rangeField as keyof LayerHeightRange, input.value);
      });
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-split-range]").forEach((button) => {
      button.addEventListener("click", () => this.#splitLayerHeightRange(Number(button.dataset.splitRange)));
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-merge-range]").forEach((button) => {
      button.addEventListener("click", () => this.#mergeLayerHeightRange(Number(button.dataset.mergeRange)));
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-remove-range]").forEach((button) => {
      button.addEventListener("click", () => this.#removeLayerHeightRange(Number(button.dataset.removeRange)));
    });
    this.#root.querySelectorAll<HTMLInputElement>("[data-process-editor-field]").forEach((input) => {
      input.addEventListener("change", () => this.#updateProcessEditorField(input.dataset.processEditorField || "", input.value));
    });
    if (multicolor) this.#root.querySelector<HTMLInputElement>("#purge-enabled")?.addEventListener("change", (event) => this.#savePurge({ ...this.#purge, enabled: (event.currentTarget as HTMLInputElement).checked }));
  }
}

if (!customElements.get("studio-process-options-panel")) {
  customElements.define("studio-process-options-panel", StudioProcessOptionsPanel);
}
