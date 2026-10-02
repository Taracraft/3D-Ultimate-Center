import { authenticatedFetch, errorMessage } from "./ha-api-transport.js";
import { WebGlStudioViewport, type MeshGeometry, type MeshInstance, type Vec3 } from "./webgl-studio-viewport.js";
import type { SliceModelInspection } from "./slicing-api.js";

const API_PREFIX = "/api/ultimate_3d_studio_v6/v1/slicer";

export type ProjectSceneInstance = Readonly<{
  id: string;
  object_id: string;
  part_id: string;
  name: string;
  extruder: number;
  positions: number[];
  triangle_count: number;
  visible: boolean;
}>;

export type ProjectScene = Readonly<{
  filename: string;
  plate_index: number;
  plate_display_number: number;
  instances: ProjectSceneInstance[];
  triangle_count: number;
  bounds: Readonly<{ min: Vec3; max: Vec3 }>;
  plate_size: readonly [number, number];
}>;

export type ProjectTransform = Readonly<{
  id: string;
  object_id: string;
  part_id: string;
  position: Vec3;
  rotation: Vec3;
  scale: Vec3;
}>;

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function normals(positions: Float32Array): Float32Array {
  const result = new Float32Array(positions.length);
  for (let index = 0; index < positions.length; index += 9) {
    const ax = positions[index]!, ay = positions[index + 1]!, az = positions[index + 2]!;
    const bx = positions[index + 3]!, by = positions[index + 4]!, bz = positions[index + 5]!;
    const cx = positions[index + 6]!, cy = positions[index + 7]!, cz = positions[index + 8]!;
    const ux = bx - ax, uy = by - ay, uz = bz - az;
    const vx = cx - ax, vy = cy - ay, vz = cz - az;
    let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz) || 1;
    nx /= length; ny /= length; nz /= length;
    for (let vertex = 0; vertex < 3; vertex += 1) {
      result[index + vertex * 3] = nx;
      result[index + vertex * 3 + 1] = ny;
      result[index + vertex * 3 + 2] = nz;
    }
  }
  return result;
}

function bounds(positions: Float32Array): { min: Vec3; max: Vec3 } {
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let index = 0; index < positions.length; index += 3) {
    min[0] = Math.min(min[0], positions[index]!);
    min[1] = Math.min(min[1], positions[index + 1]!);
    min[2] = Math.min(min[2], positions[index + 2]!);
    max[0] = Math.max(max[0], positions[index]!);
    max[1] = Math.max(max[1], positions[index + 1]!);
    max[2] = Math.max(max[2], positions[index + 2]!);
  }
  return { min, max };
}

function geometry(source: ProjectSceneInstance): MeshGeometry {
  const positions = new Float32Array(source.positions);
  const calculated = bounds(positions);
  return Object.freeze({
    positions,
    normals: normals(positions),
    triangleCount: source.triangle_count,
    boundsMin: calculated.min,
    boundsMax: calculated.max,
  });
}

async function fetchScene(file: File, plateIndex: number): Promise<ProjectScene> {
  const response = await authenticatedFetch(
    `${API_PREFIX}/scene?filename=${encodeURIComponent(file.name)}&plate_index=${plateIndex}`,
    {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    },
  );
  if (!response.ok) {
    let message = `3MF-Projektszene: HTTP ${response.status}`;
    try { message = errorMessage(await response.json(), message); } catch (_error) { /* no JSON */ }
    throw new Error(message);
  }
  return (await response.json() as { data: ProjectScene }).data;
}

export class Ultimate3DProjectEditor extends HTMLElement {
  #file: File | null = null;
  #inspection: SliceModelInspection | null = null;
  #plateIndex = 0;
  #scene: ProjectScene | null = null;
  #instances: MeshInstance[] = [];
  #transforms = new Map<string, ProjectTransform>();
  #selected = "";
  #viewport: WebGlStudioViewport | null = null;
  #generation = 0;
  #status = "Projekt wird geladen …";
  #error = "";

  set project(value: Readonly<{ file: File; inspection: SliceModelInspection; plateIndex: number }> | null) {
    if (!value) return;
    const changed = this.#file !== value.file || this.#plateIndex !== value.plateIndex;
    this.#file = value.file;
    this.#inspection = value.inspection;
    this.#plateIndex = value.plateIndex;
    if (changed && this.isConnected) void this.#load();
  }

  get transforms(): ProjectTransform[] { return [...this.#transforms.values()]; }

  connectedCallback(): void {
    this.#render();
    if (this.#file) void this.#load();
  }

  disconnectedCallback(): void {
    this.#generation += 1;
    this.#viewport?.dispose();
    this.#viewport = null;
  }

  async #load(): Promise<void> {
    const file = this.#file;
    if (!file) return;
    const generation = ++this.#generation;
    this.#status = `Druckplatte ${this.#plateIndex + 1} wird als 3D-Szene geladen …`;
    this.#error = "";
    this.#render();
    try {
      const scene = await fetchScene(file, this.#plateIndex);
      if (generation !== this.#generation) return;
      this.#scene = scene;
      this.#instances = scene.instances.map((source) => {
        const filament = this.#inspection?.filaments.find((item) => item.extruder === source.extruder);
        const transform: ProjectTransform = {
          id: source.id,
          object_id: source.object_id,
          part_id: source.part_id,
          position: [0, 0, 0],
          rotation: [0, 0, 0],
          scale: [1, 1, 1],
        };
        this.#transforms.set(source.id, transform);
        return {
          id: source.id,
          name: source.name,
          geometry: geometry(source),
          position: transform.position,
          rotation: transform.rotation,
          scale: transform.scale,
          color: filament?.color || "#68D879",
          visible: source.visible,
        };
      });
      this.#selected = this.#instances[0]?.id || "";
      this.#status = `${scene.instances.length} Teile · ${scene.triangle_count.toLocaleString("de-DE")} Dreiecke`;
    } catch (error) {
      if (generation !== this.#generation) return;
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = "3D-Projektszene konnte nicht geladen werden";
    }
    this.#render();
  }

  #selectedTransform(): ProjectTransform | null {
    return this.#transforms.get(this.#selected) ?? null;
  }

  #updateTransform(field: "position" | "rotation" | "scale", axis: number, value: number): void {
    const current = this.#selectedTransform();
    if (!current) return;
    const vector = [...current[field]] as Vec3;
    vector[axis] = value;
    const next: ProjectTransform = { ...current, [field]: vector };
    this.#transforms.set(current.id, next);
    this.#instances = this.#instances.map((instance) => instance.id === current.id ? { ...instance, [field]: vector } : instance);
    this.#viewport?.setInstances(this.#instances);
    this.dispatchEvent(new CustomEvent<ProjectTransform>("project-transform-change", { detail: next, bubbles: true, composed: true }));
    this.#renderControls();
  }

  #renderControls(): void {
    const host = this.querySelector<HTMLElement>(".transform-controls");
    const selected = this.#selectedTransform();
    if (!host || !selected) return;
    host.innerHTML = ([
      ["Position", "position", selected.position, "mm", "0.1"],
      ["Drehung", "rotation", selected.rotation, "°", "1"],
      ["Skalierung", "scale", selected.scale, "×", "0.01"],
    ] as const).map(([label, field, values, unit, step]) => `
      <div class="transform-group"><b>${label}</b>${["X", "Y", "Z"].map((axis, index) => `
        <label><span>${axis}</span><input type="number" data-transform="${field}" data-axis="${index}" step="${step}" value="${Number(values[index]).toFixed(field === "rotation" ? 1 : 3)}"><i>${unit}</i></label>`).join("")}</div>`).join("");
    host.querySelectorAll<HTMLInputElement>("[data-transform]").forEach((input) => input.addEventListener("change", () => {
      this.#updateTransform(input.dataset.transform as "position" | "rotation" | "scale", Number(input.dataset.axis), Number(input.value));
    }));
  }

  #mountViewport(): void {
    const canvas = this.querySelector<HTMLCanvasElement>("canvas");
    if (!canvas || !this.#scene) return;
    this.#viewport?.dispose();
    this.#viewport = new WebGlStudioViewport(canvas);
    this.#viewport.setPlateSize(this.#scene.plate_size[0], this.#scene.plate_size[1]);
    this.#viewport.setInstances(this.#instances);
    this.#viewport.setSelected(this.#selected ? [this.#selected] : []);
    this.#viewport.frameAll();
    this.#renderControls();
  }

  #render(): void {
    const selected = this.#instances.find((item) => item.id === this.#selected);
    this.innerHTML = `<style>
      :host{display:block;width:100%;height:100%;min-height:560px;color:#edf5fc;font:12px/1.4 Inter,Segoe UI,sans-serif}.editor{display:grid;grid-template-columns:210px minmax(0,1fr) 230px;height:100%;min-height:560px;background:#0a131c}.objects,.properties{padding:10px;overflow:auto;background:#0b1621}.objects{border-right:1px solid #26394c}.properties{border-left:1px solid #26394c}.objects h3,.properties h3{margin:0 0 9px;font-size:12px;color:#9eb2c4}.object-list{display:grid;gap:5px}.object-button{display:grid;grid-template-columns:12px minmax(0,1fr);gap:7px;align-items:center;width:100%;min-height:38px;padding:7px;border:1px solid #263d52;border-radius:7px;background:#101e2b;color:#edf5fc;text-align:left;cursor:pointer}.object-button.selected{border-color:#58d878;background:#11291b}.object-button i{width:10px;height:10px;border-radius:3px;background:#68d879}.object-button b,.object-button small{display:block;overflow:hidden;text-overflow:ellipsis}.object-button small{font-size:9px;color:#7f94a8}.stage{position:relative;min-width:0;min-height:560px;background:#071018}.stage canvas{display:block;width:100%;height:100%;min-height:560px}.stage-status{position:absolute;left:10px;bottom:10px;padding:7px 10px;border:1px solid #ffffff1f;border-radius:8px;background:#07111bd9;color:#9fb3c4}.error{padding:9px;border:1px solid #753d47;border-radius:8px;background:#351d23;color:#ffbdc4}.transform-controls{display:grid;gap:11px}.transform-group{display:grid;gap:5px;padding:8px;border:1px solid #263d52;border-radius:8px;background:#101d29}.transform-group>b{color:#9eb4c7}.transform-group label{display:grid;grid-template-columns:18px minmax(0,1fr) 22px;gap:5px;align-items:center}.transform-group input{min-width:0;width:100%;padding:5px;border:1px solid #31506e;border-radius:6px;background:#091520;color:#eef5ff}.transform-group i{font-style:normal;color:#7f94a8}.selected-name{padding:8px;margin-bottom:9px;border:1px solid #36526a;border-radius:8px;background:#102231}.selected-name b,.selected-name small{display:block}.selected-name small{color:#8197aa}@media(max-width:900px){.editor{grid-template-columns:1fr}.objects,.properties{border:0;border-top:1px solid #26394c}.stage{order:-1;min-height:400px}.stage canvas{min-height:400px}}
    </style><div class="editor">
      <aside class="objects"><h3>Objekte und Teile</h3><div class="object-list">${this.#instances.map((item) => `
        <button class="object-button ${item.id === this.#selected ? "selected" : ""}" data-object="${esc(item.id)}"><i style="background:${esc(item.color)}"></i><span><b>${esc(item.name)}</b><small>${esc(item.id)} · ${item.geometry.triangleCount} Dreiecke</small></span></button>`).join("") || '<div class="error">Noch keine Projektszene geladen.</div>'}</div></aside>
      <main class="stage">${this.#scene ? '<canvas></canvas>' : ""}<div class="stage-status">${esc(this.#status)}</div></main>
      <aside class="properties"><h3>Transformieren</h3>${this.#error ? `<div class="error">${esc(this.#error)}</div>` : `<div class="selected-name"><b>${esc(selected?.name || "Kein Teil ausgewählt")}</b><small>${esc(selected?.id || "")}</small></div><div class="transform-controls"></div>`}</aside>
    </div>`;
    this.querySelectorAll<HTMLButtonElement>("[data-object]").forEach((button) => button.addEventListener("click", () => {
      this.#selected = button.dataset.object || "";
      this.#viewport?.setSelected(this.#selected ? [this.#selected] : []);
      this.dispatchEvent(new CustomEvent("project-object-select", { detail: { id: this.#selected }, bubbles: true, composed: true }));
      this.#render();
    }));
    queueMicrotask(() => this.#mountViewport());
  }
}

if (!customElements.get("ultimate-3d-project-editor")) {
  customElements.define("ultimate-3d-project-editor", Ultimate3DProjectEditor);
}
