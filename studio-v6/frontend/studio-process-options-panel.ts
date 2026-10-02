import {
  DEFAULT_SLICE_PROCESS_OVERRIDES,
  SLICER_PROCESS_OPTIONS_KEY,
  loadSliceProcessOverrides,
  saveSliceProcessOverrides,
  type AdhesionMode,
  type SliceProcessOverrides,
  type SupportMode,
} from "./plate-slice-api.js";
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

function supportTargetLabel(value: SliceProcessOverrides): string {
  if (value.support_mode === "off") return "Support aus";
  const mode = value.support_mode === "tree" ? "Baum-Support" : "Normal-Support";
  const target = value.support_build_plate_only ? "nur Druckplatte" : "auf Modell erlaubt";
  return `${mode} · ${target} · ${value.support_threshold_angle}°`;
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
      support_build_plate_only: value.support_build_plate_only !== false,
      support_threshold_angle: Math.round(clamp(value.support_threshold_angle, 30, 0, 89)),
      layer_height_mm: optionalNumber(value.layer_height_mm, .04, .56),
      outer_wall_speed_mm_s: optionalNumber(value.outer_wall_speed_mm_s, 1, 500),
      inner_wall_speed_mm_s: optionalNumber(value.inner_wall_speed_mm_s, 1, 500),
    };
  } catch {
    return null;
  }
}

export class StudioProcessOptionsPanel extends HTMLElement {
  static get observedAttributes(): string[] { return ["plate-id"]; }

  readonly #root = this.attachShadow({ mode: "open" });
  #value: SliceProcessOverrides = DEFAULT_SLICE_PROCESS_OVERRIDES;
  #purge: SlicePurgeTower = {};
  #studioRoot: ShadowRoot | null = null;

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

  applySupportPreset(preset: Readonly<{
    mode?: SupportMode;
    buildPlateOnly?: boolean;
    thresholdAngle?: number;
  }>): void {
    const mode = ["normal", "tree", "off"].includes(String(preset.mode))
      ? preset.mode as SupportMode
      : "normal";
    this.#saveProcess({
      ...this.#value,
      support_mode: mode,
      support_build_plate_only: preset.buildPlateOnly !== false,
      support_threshold_angle: Math.round(clamp(preset.thresholdAngle, 30, 0, 89)),
    });
    requestAnimationFrame(() => this.#root.querySelector<HTMLSelectElement>("#support-mode")?.focus());
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
    this.#root.innerHTML = `<style>
      :host{display:block;width:100%;color:#eef6ff;font:11px/1.25 Inter,Segoe UI,sans-serif}*{box-sizing:border-box}.panel{display:grid;gap:8px}.group{display:grid;gap:5px;padding:8px;border:1px solid #29445c;border-radius:5px;background:#0b1824}.title{font-size:10px;font-weight:800;color:#9ab1c5;text-transform:uppercase;letter-spacing:.04em}.choices{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px}.choices.two{grid-template-columns:repeat(2,minmax(0,1fr))}.choice,select,input{min-height:30px;padding:4px 6px;border:1px solid #31506e;border-radius:3px;background:#102335;color:#eef6ff;font-weight:700;font-size:10px}.choice.active{border-color:#54d66c;background:#12391f}label{display:grid;gap:3px;color:#8da4b8}.row{display:grid;grid-template-columns:1fr auto;gap:5px;align-items:center}.row input{width:76px}.check{display:flex;align-items:center;gap:6px}.check input{width:auto;min-height:0}.summary{padding:7px;border:1px solid #29445c;border-radius:4px;background:#08131e;color:#7fd2f6;font-size:10px}
    </style><section class="panel">
      <div class="group"><span class="title">Slicer</span><div class="summary">Nativer Linux-Slicing-Server</div></div>
      <div class="group"><span class="title">Druckbetthaftung</span><div class="choices"><button class="choice ${value.adhesion_mode === "none" ? "active" : ""}" data-adhesion="none">Aus</button><button class="choice ${value.adhesion_mode === "brim" ? "active" : ""}" data-adhesion="brim">Brim</button><button class="choice ${value.adhesion_mode === "raft" ? "active" : ""}" data-adhesion="raft">Raft</button></div>${value.adhesion_mode === "brim" ? `<label class="row">Breite <input id="brim-width" type="number" min="1" max="30" step="0.5" value="${value.brim_width_mm}"></label>` : ""}${value.adhesion_mode === "raft" ? `<label class="row">Schichten <input id="raft-layers" type="number" min="1" max="10" step="1" value="${value.raft_layers}"></label>` : ""}</div>
      <div class="group"><span class="title">Stützstrukturen</span><label>Modus<select id="support-mode"><option value="off" ${value.support_mode === "off" ? "selected" : ""}>Aus</option><option value="normal" ${value.support_mode === "normal" ? "selected" : ""}>Normal</option><option value="tree" ${value.support_mode === "tree" ? "selected" : ""}>Baum-Support</option></select></label>${value.support_mode !== "off" ? `<label class="row">Grenzwinkel <input id="support-angle" type="number" min="0" max="89" step="1" value="${value.support_threshold_angle}"></label><label class="check"><input id="plate-only" type="checkbox" ${value.support_build_plate_only ? "checked" : ""}>Nur vom Druckbett</label>` : ""}</div>
      ${multicolor ? `<div class="group"><span class="title">Reinigungsturm</span><label class="check"><input id="purge-enabled" type="checkbox" ${this.#purge.enabled !== false ? "checked" : ""}>Aktiv</label></div>` : ""}
      <div class="summary">Slicing Server · ${value.adhesion_mode === "none" ? "Haftung aus" : value.adhesion_mode === "brim" ? `Brim ${value.brim_width_mm} mm` : `Raft ${value.raft_layers}`} · ${supportTargetLabel(value)}</div>
    </section>`;
    this.#bind(multicolor);
  }

  #bind(multicolor: boolean): void {
    this.#root.querySelectorAll<HTMLButtonElement>("[data-adhesion]").forEach((button) => button.addEventListener("click", () => this.#saveProcess({ ...this.#value, adhesion_mode: button.dataset.adhesion as AdhesionMode })));
    this.#root.querySelector<HTMLSelectElement>("#support-mode")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, support_mode: (event.currentTarget as HTMLSelectElement).value as SupportMode }));
    this.#root.querySelector<HTMLInputElement>("#brim-width")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, brim_width_mm: clamp((event.currentTarget as HTMLInputElement).value, 5, 1, 30) }));
    this.#root.querySelector<HTMLInputElement>("#raft-layers")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, raft_layers: Math.round(clamp((event.currentTarget as HTMLInputElement).value, 2, 1, 10)) }));
    this.#root.querySelector<HTMLInputElement>("#support-angle")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, support_threshold_angle: Math.round(clamp((event.currentTarget as HTMLInputElement).value, 30, 0, 89)) }));
    this.#root.querySelector<HTMLInputElement>("#plate-only")?.addEventListener("change", (event) => this.#saveProcess({ ...this.#value, support_build_plate_only: (event.currentTarget as HTMLInputElement).checked }));
    if (multicolor) this.#root.querySelector<HTMLInputElement>("#purge-enabled")?.addEventListener("change", (event) => this.#savePurge({ ...this.#purge, enabled: (event.currentTarget as HTMLInputElement).checked }));
  }
}

if (!customElements.get("studio-process-options-panel")) {
  customElements.define("studio-process-options-panel", StudioProcessOptionsPanel);
}