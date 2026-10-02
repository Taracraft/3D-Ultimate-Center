import { authenticatedFetch, errorMessage } from "./ha-api-transport.js";
import { createPlateSliceJob, type SliceMaterialPlan } from "./plate-slice-api.js";
import { createPrimitiveGeometry, type PrimitiveKind } from "./primitive-geometry.js";
import { ProfileApi, type V6ProfileCatalog } from "./profile-api.js";
import { bestFlatRotation, positionCenteredOnPlate, positionOnBed } from "./mesh-export.js";
import { buildPlateProfiles, studioBuildPlateVisual, type StudioBuildPlateVisual } from "./studio-build-plates.js";
import { shellHtml, type MegaUiPlate, type MegaUiState } from "./studio-mega-ui.js";
import { StudioMegaViewport, type MegaAxis, type MegaGizmoMode } from "./studio-mega-viewport.js";
import { export3mf } from "./three-mf-export.js";
import { fetchSliceJob, inspectSliceModel, type SliceJob, type SliceModelInspection, type SliceProjectFilament } from "./slicing-api.js";
import { fetchDetailedDirectPrintStatus, type DetailedAmsSlot } from "./direct-print-status-api.js";
import { parseStl, type MeshGeometry, type MeshInstance, type Vec3 } from "./webgl-studio-viewport.js";
import type { WorkspaceSourceRequest } from "./workspace-source-request.js";

const API_PREFIX = "/api/ultimate_3d_studio_v6/v1/slicer";
const ACTIVE = new Set(["queued", "running", "cancelling"]);
const COLORS = ["#ff4d4d", "#202020", "#36e51e", "#2e9bff", "#ffb62e", "#b96cff", "#25d5c5", "#f56ab3"];
const NEUTRAL_COLOR = "#6b7785";

type StudioMode = "prepare" | "colors" | "preview";
type PlateStage = "prepared" | "slicing" | "sliced" | "printed" | "error";
type ScenePart = Readonly<{ id: string; object_id: string; part_id: string; name: string; extruder: number; positions: number[]; triangle_count: number; visible: boolean }>;
type ScenePayload = Readonly<{ instances: ScenePart[]; plate_size: readonly [number, number] }>;
type ToolpathSegment = readonly [number, number, number, number, number, number, number];
type ToolpathLayer = Readonly<{ index: number; z: number; segments: ToolpathSegment[]; extrusion_mm: number }>;
type ToolpathPayload = Readonly<{ layer_count: number; chunk?: Readonly<{ layers: ToolpathLayer[] }> }>;
type Plate = {
  id: number;
  name: string;
  profileId: string;
  width: number;
  depth: number;
  instances: MeshInstance[];
  stage: PlateStage;
  jobId: string;
  lastError: string;
  layers: ToolpathLayer[];
  layerCount: number;
  visibleLayer: number;
};
type DragState = { pointerId: number; startX: number; startY: number; initial: Map<string, MeshInstance>; mode: MegaGizmoMode; axis: MegaAxis };

function newPlate(id: number, name: string, profileId = "build-plate-smooth-pei", width = 256, depth = 256): Plate {
  return { id, name, profileId, width, depth, instances: [], stage: "prepared", jobId: "", lastError: "", layers: [], layerCount: 0, visibleLayer: 0 };
}

function normalizeColor(value: string | null | undefined): string {
  const raw = String(value || "").trim().replace(/^#/, "");
  const rgb = raw.length >= 6 ? raw.slice(0, 6) : "6b7785";
  return /^[0-9a-f]{6}$/i.test(rgb) ? `#${rgb.toLowerCase()}` : NEUTRAL_COLOR;
}

function normals(positions: Float32Array): Float32Array {
  const result = new Float32Array(positions.length);
  for (let index = 0; index < positions.length; index += 9) {
    const ax = positions[index]!, ay = positions[index + 1]!, az = positions[index + 2]!;
    const bx = positions[index + 3]!, by = positions[index + 4]!, bz = positions[index + 5]!;
    const cx = positions[index + 6]!, cy = positions[index + 7]!, cz = positions[index + 8]!;
    const ux = bx - ax, uy = by - ay, uz = bz - az, vx = cx - ax, vy = cy - ay, vz = cz - az;
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

function geometry(source: number[] | Float32Array): MeshGeometry {
  const positions = source instanceof Float32Array ? source : new Float32Array(source);
  const min: Vec3 = [Infinity, Infinity, Infinity], max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let index = 0; index < positions.length; index += 3) {
    min[0] = Math.min(min[0], positions[index]!); min[1] = Math.min(min[1], positions[index + 1]!); min[2] = Math.min(min[2], positions[index + 2]!);
    max[0] = Math.max(max[0], positions[index]!); max[1] = Math.max(max[1], positions[index + 1]!); max[2] = Math.max(max[2], positions[index + 2]!);
  }
  return Object.freeze({ positions, normals: normals(positions), triangleCount: positions.length / 9, boundsMin: min, boundsMax: max });
}

function fitImportedGroup(instances: MeshInstance[], width: number, depth: number): MeshInstance[] {
  if (!instances.length) return instances;
  const min: Vec3 = [Infinity, Infinity, Infinity], max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (const item of instances) {
    for (let axis = 0; axis < 3; axis += 1) {
      min[axis] = Math.min(min[axis], item.geometry.boundsMin[axis]);
      max[axis] = Math.max(max[axis], item.geometry.boundsMax[axis]);
    }
  }
  const groupWidth = Math.max(.001, max[0] - min[0]);
  const groupDepth = Math.max(.001, max[1] - min[1]);
  const factor = Math.min(1, Math.max(.01, (width - 16) / groupWidth), Math.max(.01, (depth - 16) / groupDepth));
  const shiftX = width / 2 - (min[0] + max[0]) * factor / 2;
  const shiftY = depth / 2 - (min[1] + max[1]) * factor / 2;
  const shiftZ = -min[2] * factor;
  return instances.map((item) => ({ ...item, scale: [factor, factor, factor], position: [shiftX, shiftY, shiftZ] }));
}

async function scene(file: File, plateIndex: number): Promise<ScenePayload> {
  const response = await authenticatedFetch(`${API_PREFIX}/scene?filename=${encodeURIComponent(file.name)}&plate_index=${plateIndex}`, { method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file });
  if (!response.ok) {
    let message = `3MF-Szene HTTP ${response.status}`;
    try { message = errorMessage(await response.json(), message); } catch {}
    throw new Error(message);
  }
  return (await response.json() as { data: ScenePayload }).data;
}

async function toolpath(jobId: string, start?: number, end?: number): Promise<ToolpathPayload> {
  const query = new URLSearchParams();
  if (start !== undefined) query.set("start", String(start));
  if (end !== undefined) query.set("end", String(end));
  const response = await authenticatedFetch(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/toolpath${query.size ? `?${query}` : ""}`, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Toolpath HTTP ${response.status}`);
  return (await response.json() as { data: ToolpathPayload }).data;
}

function toolpathMeshes(layers: readonly ToolpathLayer[], maxLayer: number): MeshInstance[] {
  const byTool = new Map<number, number[]>();
  for (const layer of layers) {
    if (layer.index > maxLayer) continue;
    for (const segment of layer.segments) {
      const [x1, y1, x2, y2, z, tool, extrusion] = segment;
      const dx = x2 - x1, dy = y2 - y1, length = Math.hypot(dx, dy);
      if (length < .0001) continue;
      const width = Math.max(.12, Math.min(1.1, extrusion / length * .9));
      const nx = -dy / length * width / 2, ny = dx / length * width / 2, z0 = Math.max(0, z - .16);
      const a: Vec3 = [x1 + nx, y1 + ny, z0], b: Vec3 = [x1 - nx, y1 - ny, z0], c: Vec3 = [x2 - nx, y2 - ny, z0], d: Vec3 = [x2 + nx, y2 + ny, z0];
      const at: Vec3 = [a[0], a[1], z], bt: Vec3 = [b[0], b[1], z], ct: Vec3 = [c[0], c[1], z], dt: Vec3 = [d[0], d[1], z];
      const triangles = [a,b,c,a,c,d,at,ct,bt,at,dt,ct,a,at,bt,a,bt,b,d,c,ct,d,ct,dt,a,d,dt,a,dt,at,b,bt,ct,b,ct,c];
      const target = byTool.get(tool) ?? [];
      for (const point of triangles) target.push(...point);
      byTool.set(tool, target);
    }
  }
  return [...byTool.entries()].map(([tool, positions]) => ({ id: `tool-${tool}`, name: `Werkzeug ${tool + 1}`, geometry: geometry(positions), position: [0,0,0], rotation: [0,0,0], scale: [1,1,1], color: COLORS[tool % COLORS.length]!, visible: true }));
}

export class Ultimate3DMegaStudio extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #profileApi = new ProfileApi();
  #catalog: V6ProfileCatalog | null = null;
  #file: File | null = null;
  #inspection: SliceModelInspection | null = null;
  #plates: Plate[] = [newPlate(0, "Druckplatte 1")];
  #activePlate = 0;
  #mode: StudioMode = "prepare";
  #tool: MegaGizmoMode = "select";
  #axis: MegaAxis = "x";
  #selected = new Set<string>();
  #assignments = new Map<string, number>();
  #amsSlots: DetailedAmsSlot[] = [];
  #amsPrinter = "";
  #amsError = "";
  #amsLoading = false;
  #viewport: StudioMegaViewport | null = null;
  #drag: DragState | null = null;
  #status = "Bereit";
  #error = "";
  #loading = false;
  #generation = 0;
  #nextId = 1;
  #recentImportKey = "";
  #recentImportAt = 0;

  set files(value: readonly File[]) { const file = value[0]; if (file) this.file = file; }
  set file(value: File | null) {
    if (!value) return;
    const key = `${value.name}:${value.size}:${value.lastModified}`;
    const now = Date.now();
    if (key === this.#recentImportKey && now - this.#recentImportAt < 2500) return;
    this.#recentImportKey = key;
    this.#recentImportAt = now;
    this.#file = value;
    this.#mode = "prepare";
    void this.#load(value);
  }
  get file(): File | null { return this.#file; }

  connectedCallback(): void {
    this.tabIndex = 0;
    this.addEventListener("keydown", this.#keyDown);
    this.#root.addEventListener("pointerdown", this.#rootPointerDown);
    this.#render();
    void this.#loadProfiles();
  }

  disconnectedCallback(): void {
    this.removeEventListener("keydown", this.#keyDown);
    this.#root.removeEventListener("pointerdown", this.#rootPointerDown);
    this.#generation += 1;
    this.#viewport?.dispose();
  }

  readonly #rootPointerDown = (event: Event): void => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest(".menubar")) this.#closeMenus();
  };

  readonly #keyDown = (event: KeyboardEvent): void => {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || event.target instanceof HTMLTextAreaElement) return;
    const key = event.key.toLowerCase();
    if ((event.ctrlKey || event.metaKey) && key === "a") { event.preventDefault(); this.#selected = new Set(this.#plate().instances.map((item) => item.id)); this.#syncSelection(); return; }
    if ((event.ctrlKey || event.metaKey) && key === "d") { event.preventDefault(); this.#duplicate(); return; }
    if (event.key === "Delete") { event.preventDefault(); this.#remove(); return; }
    if (key === "g") this.#setTool("translate");
    if (key === "r") this.#setTool("rotate");
    if (key === "s") this.#setTool("scale");
    if (key === "q" || event.key === "Escape") this.#setTool("select");
    if (key === "x" || key === "y" || key === "z") this.#setAxis(key);
  };

  async #loadProfiles(): Promise<void> {
    try {
      this.#catalog = await this.#profileApi.getCatalog();
      const selected = this.#catalog.selection.build_plate_profile_id;
      if (selected && this.#plates.length === 1 && !this.#plates[0]!.instances.length) this.#setProfile(0, selected, false);
      this.#render();
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#render();
    }
  }

  #plate(): Plate { return this.#plates[this.#activePlate] ?? this.#plates[0]!; }
  #selectedItems(): MeshInstance[] { return this.#plate().instances.filter((item) => this.#selected.has(item.id)); }
  #center(): Vec3 | null {
    const items = this.#selectedItems();
    if (!items.length) return null;
    return [items.reduce((sum, item) => sum + item.position[0], 0) / items.length, items.reduce((sum, item) => sum + item.position[1], 0) / items.length, items.reduce((sum, item) => sum + item.position[2], 0) / items.length];
  }
  #profileVisual(plate = this.#plate()): StudioBuildPlateVisual {
    const profiles = buildPlateProfiles(this.#catalog?.profiles ?? []);
    return { ...studioBuildPlateVisual(profiles.find((item) => item.id === plate.profileId) ?? profiles[0]), widthMm: plate.width, depthMm: plate.depth };
  }
  #displayInstances(): MeshInstance[] {
    const plate = this.#plate();
    return this.#mode === "preview" && plate.layers.length ? toolpathMeshes(plate.layers, plate.visibleLayer) : plate.instances;
  }
  #filaments(): SliceProjectFilament[] {
    if (this.#amsSlots.length) {
      return this.#amsSlots.map((slot, index) => ({
        extruder: index + 1,
        name: `AMS ${slot.display_slot}: ${slot.sub_brand || slot.material || "Filament"}`,
        material: slot.material || "unknown",
        color: normalizeColor(slot.color),
      }));
    }
    return [...(this.#inspection?.filaments ?? [])];
  }
  #stageLabel(stage: PlateStage): string {
    return ({ prepared: "Vorbereitet", slicing: "Slicing läuft", sliced: "Geslicet", printed: "Gedruckt", error: "Fehler" } as const)[stage];
  }

  #ui(): MegaUiState {
    const active = this.#plate();
    const plates: MegaUiPlate[] = this.#plates.map((plate) => ({
      name: plate.name,
      width: plate.width,
      depth: plate.depth,
      profile: this.#profileVisual(plate),
      instances: plate.instances,
      status: this.#stageLabel(plate.stage),
    }));
    return {
      mode: this.#mode,
      tool: this.#tool,
      axis: this.#axis,
      activePlate: this.#activePlate,
      plates,
      selected: this.#selected,
      status: this.#error || active.lastError || this.#status,
      error: this.#error,
      loading: this.#loading,
      canSlice: active.instances.length > 0 && active.stage !== "slicing",
      layerCount: active.layerCount,
      visibleLayer: active.visibleLayer,
      center: this.#center(),
    };
  }

  async #load(file: File): Promise<void> {
    const generation = ++this.#generation;
    const importNumber = this.#nextId++;
    this.#loading = true;
    this.#error = "";
    this.#status = `${file.name} wird analysiert …`;
    this.#mode = "prepare";
    this.#render();
    try {
      const inspection = await inspectSliceModel(file);
      if (generation !== this.#generation) return;
      this.#inspection = inspection;
      for (const object of inspection.objects) this.#collectAssignments(object);
      const importedIds: string[] = [];

      if (inspection.format === "3mf") {
        const count = Math.max(1, inspection.plate_count || inspection.plates.length || 1);
        const importedPlates: Plate[] = [];
        for (let index = 0; index < count; index += 1) {
          const data = await scene(file, index);
          if (generation !== this.#generation) return;
          const profileId = this.#catalog?.selection.build_plate_profile_id || this.#plate().profileId || "build-plate-smooth-pei";
          const width = data.plate_size[0] || 256;
          const depth = data.plate_size[1] || 256;
          const rawInstances = data.instances.map((part) => {
            const id = `import-${importNumber}-${this.#nextId++}`;
            const extruder = this.#assignments.get(part.part_id) ?? this.#assignments.get(part.object_id) ?? part.extruder;
            this.#assignments.set(id, extruder);
            importedIds.push(id);
            return {
              id,
              name: part.name,
              geometry: geometry(part.positions),
              position: [0,0,0] as Vec3,
              rotation: [0,0,0] as Vec3,
              scale: [1,1,1] as Vec3,
              color: this.#filamentColor(extruder),
              visible: part.visible,
            };
          });
          const plate = newPlate(0, inspection.plates[index]?.name || `${file.name} · Platte ${index + 1}`, profileId, width, depth);
          plate.instances = fitImportedGroup(rawInstances, width, depth);
          importedPlates.push(plate);
        }
        const onlyEmptyStartPlate = this.#plates.length === 1 && this.#plates[0]!.instances.length === 0;
        const startIndex = onlyEmptyStartPlate ? 0 : this.#plates.length;
        if (onlyEmptyStartPlate) this.#plates = importedPlates;
        else this.#plates.push(...importedPlates);
        this.#plates.forEach((plate, index) => { plate.id = index; if (!plate.name.trim()) plate.name = `Druckplatte ${index + 1}`; });
        this.#activePlate = startIndex;
      } else {
        const mesh = parseStl(await file.arrayBuffer());
        const plate = this.#plate();
        const id = `import-${importNumber}-${this.#nextId++}`;
        const base: MeshInstance = { id, name: file.name.replace(/\.stl$/i, ""), geometry: mesh, position: [0,0,0], rotation: [0,0,0], scale: [1,1,1], color: NEUTRAL_COLOR, visible: true };
        const position = positionCenteredOnPlate(mesh, base, plate.width, plate.depth);
        plate.instances.push({ ...base, position: positionOnBed(mesh, { ...base, position }) });
        plate.stage = "prepared";
        importedIds.push(id);
      }

      this.#selected = new Set(this.#plate().instances.filter((item) => importedIds.includes(item.id)).map((item) => item.id));
      if (!this.#selected.size && this.#plate().instances[0]) this.#selected.add(this.#plate().instances[0]!.id);
      this.#status = `${file.name} hinzugefügt · ${this.#plates.length} Platte(n) · aktive Platte ${this.#activePlate + 1}`;
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    } finally {
      if (generation === this.#generation) { this.#loading = false; this.#render(); }
    }
  }

  #collectAssignments(item: { object_id: string; extruder: number | null; parts: readonly any[] }): void {
    if (item.object_id) this.#assignments.set(item.object_id, Number(item.extruder || 1));
    for (const part of item.parts) this.#collectAssignments(part);
  }
  #filamentColor(extruder: number): string {
    return normalizeColor(this.#filaments().find((item) => item.extruder === extruder)?.color ?? COLORS[(extruder - 1) % COLORS.length]);
  }
  #extruder(id: string): number { return this.#assignments.get(id) ?? 1; }

  async #syncAms(): Promise<void> {
    this.#amsLoading = true;
    this.#amsError = "";
    this.#renderSidebar();
    try {
      const status = await fetchDetailedDirectPrintStatus();
      const printer = status.items.find((item) => item.ams.available && item.ams.slots.some((slot) => slot.present))
        ?? status.items.find((item) => item.ams.available);
      this.#amsSlots = [...(printer?.ams.slots.filter((slot) => slot.present) ?? [])].sort((a, b) => a.display_slot - b.display_slot);
      this.#amsPrinter = printer?.name ?? "";
      if (!this.#amsSlots.length) throw new Error("Keine belegten AMS-Slots erkannt.");
      for (const plate of this.#plates) {
        plate.instances = plate.instances.map((item) => ({ ...item, color: this.#filamentColor(this.#extruder(item.id)) }));
      }
      this.#status = `${this.#amsSlots.length} AMS-Slot(s) von ${this.#amsPrinter || "Drucker"} synchronisiert.`;
    } catch (error) {
      this.#amsError = error instanceof Error ? error.message : String(error);
    } finally {
      this.#amsLoading = false;
      this.#render();
    }
  }

  #removeModelColors(): void {
    this.#assignments.clear();
    for (const plate of this.#plates) plate.instances = plate.instances.map((item) => ({ ...item, color: NEUTRAL_COLOR }));
    this.#status = "Projektfarben entfernt. Objekte können jetzt neu den AMS-Slots zugewiesen werden.";
    this.#render();
  }

  #setTool(tool: MegaGizmoMode): void { this.#tool = tool; this.#viewport?.setGizmo(this.#center(), tool, this.#axis); this.#render(); }
  #setAxis(axis: MegaAxis): void { this.#axis = axis; this.#viewport?.setGizmo(this.#center(), this.#tool, axis); this.#render(); }
  #select(id: string | null, additive: boolean): void {
    if (!id) { if (!additive) this.#selected.clear(); }
    else if (additive) { if (this.#selected.has(id)) this.#selected.delete(id); else this.#selected.add(id); }
    else { this.#selected.clear(); this.#selected.add(id); }
    this.#syncSelection();
  }
  #syncSelection(): void { this.#viewport?.setSelected([...this.#selected]); this.#viewport?.setGizmo(this.#center(), this.#tool, this.#axis); this.#render(); }
  #replace(changes: Map<string, MeshInstance>): void {
    const plate = this.#plate();
    plate.instances = plate.instances.map((item) => changes.get(item.id) ?? item);
    plate.stage = "prepared";
    plate.jobId = "";
    plate.layers = [];
    plate.layerCount = 0;
    plate.visibleLayer = 0;
    this.#viewport?.setInstances(this.#displayInstances());
    this.#syncSelection();
  }

  #duplicate(): void {
    const selected = this.#selectedItems();
    const copies = selected.map((item) => ({ ...item, id: `copy-${this.#nextId++}`, name: `${item.name} Kopie`, position: [item.position[0] + 10, item.position[1] + 10, item.position[2]] as Vec3 }));
    if (!copies.length) return;
    for (let index = 0; index < copies.length; index += 1) this.#assignments.set(copies[index]!.id, this.#extruder(selected[index]!.id));
    this.#plate().instances.push(...copies);
    this.#plate().stage = "prepared";
    this.#selected = new Set(copies.map((item) => item.id));
    this.#render();
  }
  #remove(): void {
    this.#plate().instances = this.#plate().instances.filter((item) => !this.#selected.has(item.id));
    for (const id of this.#selected) this.#assignments.delete(id);
    this.#plate().stage = "prepared";
    this.#selected.clear();
    this.#render();
  }
  #centerSelected(): void { const changes = new Map<string, MeshInstance>(); for (const item of this.#selectedItems()) changes.set(item.id, { ...item, position: positionCenteredOnPlate(item.geometry, item, this.#plate().width, this.#plate().depth) }); this.#replace(changes); }
  #bed(): void { const changes = new Map<string, MeshInstance>(); for (const item of this.#selectedItems()) changes.set(item.id, { ...item, position: positionOnBed(item.geometry, item) }); this.#replace(changes); }
  #flat(): void { const changes = new Map<string, MeshInstance>(); for (const item of this.#selectedItems()) { const rotation = bestFlatRotation(item.geometry, item.scale); changes.set(item.id, { ...item, rotation, position: positionOnBed(item.geometry, { ...item, rotation }) }); } this.#replace(changes); }
  #arrange(): void {
    const plate = this.#plate(), items = plate.instances;
    if (!items.length) return;
    const columns = Math.ceil(Math.sqrt(items.length)), rows = Math.ceil(items.length / columns), margin = 12, gap = 8;
    const cellWidth = (plate.width - margin * 2 - gap * (columns - 1)) / columns, cellDepth = (plate.depth - margin * 2 - gap * (rows - 1)) / rows;
    plate.instances = items.map((item, index) => {
      const width = Math.max(.001, item.geometry.boundsMax[0] - item.geometry.boundsMin[0]), depth = Math.max(.001, item.geometry.boundsMax[1] - item.geometry.boundsMin[1]);
      const factor = Math.min(1, (cellWidth - 4) / width, (cellDepth - 4) / depth), scale: Vec3 = [factor,factor,factor];
      const column = index % columns, row = Math.floor(index / columns), position: Vec3 = [margin + column * (cellWidth + gap) + cellWidth / 2, margin + row * (cellDepth + gap) + cellDepth / 2, 0];
      return { ...item, scale, position: positionOnBed(item.geometry, { ...item, scale, position }) };
    });
    plate.stage = "prepared";
    this.#render();
  }
  #primitive(kind: PrimitiveKind): void {
    const plate = this.#plate(), names: Record<PrimitiveKind, string> = { cube: "Würfel", cylinder: "Zylinder", sphere: "Kugel", cone: "Kegel", torus: "Ring", plate: "Platte", "first-layer": "First-Layer-Test" };
    const mesh = createPrimitiveGeometry(kind, plate.width, plate.depth);
    const id = `primitive-${this.#nextId++}`;
    const item: MeshInstance = { id, name: names[kind], geometry: mesh, position: positionCenteredOnPlate(mesh, { position: [0,0,0], rotation: [0,0,0], scale: [1,1,1] }, plate.width, plate.depth), rotation: [0,0,0], scale: [1,1,1], color: NEUTRAL_COLOR, visible: true };
    plate.instances.push(item);
    plate.stage = "prepared";
    this.#selected = new Set([item.id]);
    this.#render();
  }

  #addPlate(): void {
    const current = this.#plate(), id = this.#plates.length;
    this.#plates.push(newPlate(id, `Druckplatte ${id + 1}`, current.profileId, current.width, current.depth));
    this.#activePlate = id;
    this.#selected.clear();
    this.#status = `Druckplatte ${id + 1} wurde hinzugefügt.`;
    this.#closeMenus();
    this.#render();
  }
  #removePlate(): void {
    if (this.#plates.length <= 1) return;
    const removed = this.#plates.splice(this.#activePlate, 1)[0];
    for (const item of removed?.instances ?? []) this.#assignments.delete(item.id);
    this.#plates.forEach((plate, index) => { plate.id = index; if (/^Druckplatte \d+$/.test(plate.name)) plate.name = `Druckplatte ${index + 1}`; });
    this.#activePlate = Math.max(0, Math.min(this.#activePlate, this.#plates.length - 1));
    this.#selected.clear();
    this.#closeMenus();
    this.#render();
  }
  #setProfile(index: number, profileId: string, save = true): void {
    const plate = this.#plates[index], profiles = buildPlateProfiles(this.#catalog?.profiles ?? []), profile = profiles.find((item) => item.id === profileId);
    if (!plate || !profile) return;
    const visual = studioBuildPlateVisual(profile);
    plate.profileId = profile.id;
    plate.width = visual.widthMm;
    plate.depth = visual.depthMm;
    plate.stage = "prepared";
    if (save && this.#catalog?.profiles.some((item) => item.id === profile.id)) void this.#profileApi.saveSelection({ ...this.#catalog.selection, build_plate_profile_id: profile.id });
    this.#status = `${plate.name}: Profil ${profile.name} aktiviert. Modellpositionen bleiben unverändert.`;
    this.#render();
  }

  #materialPlan(): SliceMaterialPlan {
    return {
      assignments: Object.fromEntries(this.#assignments),
      filaments: this.#filaments(),
      purge_tower: { ...(this.#inspection?.purge_tower ?? {}), enabled: new Set(this.#assignments.values()).size > 1 },
    };
  }
  #plateFile(): File {
    const plate = this.#plate();
    const bytes = export3mf(plate.instances.filter((item) => item.visible).map((item) => ({ name: item.name, geometry: item.geometry, transform: { position: item.position, rotation: item.rotation, scale: item.scale }, color: item.color })), { title: plate.name, buildPlateName: plate.name, buildPlateProfileId: plate.profileId, plateWidthMm: plate.width, plateDepthMm: plate.depth });
    return new File([bytes], `plate-${plate.id + 1}-${plate.name.replace(/[^a-z0-9_-]+/gi, "-")}.3mf`, { type: "model/3mf" });
  }
  async #slice(): Promise<void> {
    const plate = this.#plate();
    if (!plate.instances.length || plate.stage === "slicing") return;
    const generation = ++this.#generation;
    plate.stage = "slicing";
    plate.lastError = "";
    this.#loading = true;
    this.#error = "";
    this.#status = `${plate.name} wird geslicet …`;
    this.#render();
    try {
      const job = await createPlateSliceJob(this.#plateFile(), 0, undefined, this.#materialPlan(), {
        studio_plate_id: plate.id,
        studio_plate_display_number: plate.id + 1,
        studio_plate_name: plate.name,
      });
      plate.jobId = job.id;
      let currentJob: SliceJob = job;
      while (generation === this.#generation && ACTIVE.has(currentJob.status)) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        currentJob = await fetchSliceJob(currentJob.id);
      }
      if (currentJob.status !== "succeeded") throw new Error(currentJob.error || "Slicing fehlgeschlagen");
      const summary = await toolpath(currentJob.id);
      plate.layerCount = summary.layer_count;
      plate.layers = [];
      for (let start = 0; start < summary.layer_count; start += 35) {
        plate.layers.push(...((await toolpath(currentJob.id, start, Math.min(summary.layer_count, start + 35))).chunk?.layers ?? []));
      }
      plate.visibleLayer = Math.max(0, plate.layerCount - 1);
      plate.stage = "sliced";
      this.#mode = "preview";
      this.#status = `${plate.name}: ${plate.layerCount} Layer erfolgreich erzeugt. Andere Platten bleiben unabhängig bearbeitbar.`;
    } catch (error) {
      plate.stage = "error";
      plate.lastError = error instanceof Error ? error.message : String(error);
      this.#error = plate.lastError;
    } finally {
      if (generation === this.#generation) { this.#loading = false; this.#render(); }
    }
  }

  #markPrinted(): void {
    const plate = this.#plate();
    if (plate.stage !== "sliced") return;
    plate.stage = "printed";
    this.#status = `${plate.name} als gedruckt markiert. Die übrigen Platten können weiter vorbereitet oder geslicet werden.`;
    this.#render();
  }

  #closeMenus(except?: HTMLDetailsElement): void {
    this.#root.querySelectorAll<HTMLDetailsElement>("details.menu[open]").forEach((menu) => { if (menu !== except) menu.open = false; });
  }

  #render(): void {
    this.#root.innerHTML = shellHtml(this.#ui());
    this.#bindUi();
    this.#renderSidebar();
    queueMicrotask(() => this.#mountViewport());
  }

  #bindUi(): void {
    const menus = [...this.#root.querySelectorAll<HTMLDetailsElement>("details.menu")];
    for (const menu of menus) menu.addEventListener("toggle", () => { if (menu.open) this.#closeMenus(menu); });
    this.#root.querySelectorAll<HTMLButtonElement>(".menu-pop button").forEach((button) => button.addEventListener("click", () => queueMicrotask(() => this.#closeMenus())));

    this.#root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((button) => { button.classList.toggle("active", button.dataset.mode === this.#mode); button.addEventListener("click", () => { this.#mode = button.dataset.mode as StudioMode; this.#render(); }); });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-tool]").forEach((button) => { button.classList.toggle("active", button.dataset.tool === this.#tool); button.addEventListener("click", () => this.#setTool(button.dataset.tool as MegaGizmoMode)); });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-axis]").forEach((button) => { button.classList.toggle("active", button.dataset.axis === this.#axis); button.addEventListener("click", () => this.#setAxis(button.dataset.axis as MegaAxis)); });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-object]").forEach((button) => button.addEventListener("click", (event) => this.#select(button.dataset.object || null, event.ctrlKey || event.metaKey)));
    this.#root.querySelectorAll<HTMLElement>("[data-plate]").forEach((card) => card.addEventListener("click", (event) => {
      if ((event.target as HTMLElement).closest("[data-remove-plate]")) return;
      this.#activePlate = Number(card.dataset.plate);
      this.#selected.clear();
      this.#error = "";
      this.#render();
    }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-remove-plate]").forEach((button) => button.addEventListener("click", (event) => { event.stopPropagation(); this.#activePlate = Number(button.dataset.removePlate); this.#removePlate(); }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='add-plate']").forEach((button) => button.addEventListener("click", () => this.#addPlate()));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='remove-active-plate']").forEach((button) => button.addEventListener("click", () => this.#removePlate()));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-source]").forEach((button) => button.addEventListener("click", () => this.dispatchEvent(new CustomEvent<WorkspaceSourceRequest>("workspace-source-request", { detail: { target: "slicer", source: button.dataset.source as WorkspaceSourceRequest["source"] }, bubbles: true, composed: true }))));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-primitive]").forEach((button) => button.addEventListener("click", () => this.#primitive(button.dataset.primitive as PrimitiveKind)));
    const on = (id: string, action: () => void): void => { this.#root.querySelector<HTMLButtonElement>(`#${id}`)?.addEventListener("click", action); };
    on("slice", () => void this.#slice());
    on("duplicate", () => this.#duplicate()); on("menu-duplicate", () => this.#duplicate());
    on("delete", () => this.#remove()); on("menu-delete", () => this.#remove());
    on("center", () => this.#centerSelected()); on("menu-center", () => this.#centerSelected());
    on("flat", () => this.#flat()); on("menu-flat", () => this.#flat());
    on("bed", () => this.#bed()); on("menu-bed", () => this.#bed());
    on("arrange", () => this.#arrange()); on("menu-arrange", () => this.#arrange());
    on("select-all", () => { this.#selected = new Set(this.#plate().instances.map((item) => item.id)); this.#syncSelection(); });
    on("clear-selection", () => { this.#selected.clear(); this.#syncSelection(); });
    on("frame-all", () => this.#viewport?.frameAll());
    on("view-prepare", () => { this.#mode = "prepare"; this.#render(); });
    on("view-colors", () => { this.#mode = "colors"; this.#render(); });
    on("view-preview", () => { this.#mode = "preview"; this.#render(); });
    const input = this.#root.querySelector<HTMLInputElement>("#local-file");
    on("local-open", () => input?.click());
    input?.addEventListener("change", () => { const file = input.files?.[0]; if (file) this.file = file; });
  }

  #mountViewport(): void {
    const canvas = this.#root.querySelector<HTMLCanvasElement>("canvas");
    if (!canvas) return;
    this.#viewport?.dispose();
    this.#viewport = new StudioMegaViewport(canvas, this.#profileVisual());
    this.#viewport.setInstances(this.#displayInstances());
    this.#viewport.setSelected([...this.#selected]);
    this.#viewport.setGizmo(this.#center(), this.#tool, this.#axis);
    this.#viewport.frameAll();
    let down: { x: number; y: number; id: number } | null = null;
    canvas.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      down = { x: event.clientX, y: event.clientY, id: event.pointerId };
      if (this.#tool !== "select" && this.#selected.size && this.#mode !== "preview") {
        event.preventDefault(); event.stopImmediatePropagation();
        this.#drag = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, initial: new Map(this.#selectedItems().map((item) => [item.id, item])), mode: this.#tool, axis: this.#axis };
      }
    }, { capture: true });
    canvas.addEventListener("pointermove", (event) => {
      const drag = this.#drag;
      if (!drag || drag.pointerId !== event.pointerId) return;
      event.preventDefault(); event.stopImmediatePropagation();
      const amount = drag.axis === "x" ? event.clientX - drag.startX : -(event.clientY - drag.startY);
      const axis = drag.axis === "x" ? 0 : drag.axis === "y" ? 1 : 2;
      const changes = new Map<string, MeshInstance>();
      for (const [id, item] of drag.initial) {
        if (drag.mode === "translate") { const position = [...item.position] as Vec3; position[axis] += amount * .25; changes.set(id, { ...item, position }); }
        if (drag.mode === "rotate") { const rotation = [...item.rotation] as Vec3; rotation[axis] += amount * .35; changes.set(id, { ...item, rotation }); }
        if (drag.mode === "scale") { const scale = [...item.scale] as Vec3, next = Math.max(.01, scale[axis] + amount * .005); if (event.shiftKey) scale[0] = scale[1] = scale[2] = next; else scale[axis] = next; changes.set(id, { ...item, scale }); }
      }
      this.#plate().instances = this.#plate().instances.map((item) => changes.get(item.id) ?? item);
      this.#plate().stage = "prepared";
      this.#viewport?.setInstances(this.#displayInstances());
      this.#viewport?.setGizmo(this.#center(), this.#tool, this.#axis);
    }, { capture: true });
    const finish = (event: PointerEvent): void => {
      if (this.#drag?.pointerId === event.pointerId) { event.preventDefault(); event.stopImmediatePropagation(); this.#drag = null; this.#render(); }
      else if (down && down.id === event.pointerId && Math.hypot(event.clientX - down.x, event.clientY - down.y) < 4) this.#select(this.#viewport?.pick(event.clientX, event.clientY) ?? null, event.ctrlKey || event.metaKey);
      down = null;
    };
    canvas.addEventListener("pointerup", finish, { capture: true });
    canvas.addEventListener("pointercancel", finish, { capture: true });
  }

  #renderSidebar(): void {
    const host = this.#root.querySelector<HTMLElement>("#sidebar");
    if (!host) return;
    const selected = this.#selectedItems(), primary = selected[0] ?? null, plate = this.#plate();
    if (this.#mode === "colors") {
      const current = primary ? this.#extruder(primary.id) : 1;
      const filaments = this.#filaments();
      host.innerHTML = `<h3>Mehrfarben & AMS</h3><div class="section"><button id="sync-ams" ${this.#amsLoading ? "disabled" : ""}>${this.#amsLoading ? "AMS wird synchronisiert …" : "AMS-Farben synchronisieren"}</button><button id="remove-model-colors">Projektfarben entfernen</button><small>${this.#amsPrinter ? `Quelle: ${this.#amsPrinter}` : "Noch keine AMS-Synchronisierung"}</small>${this.#amsError ? `<span class="error">${this.#amsError}</span>` : ""}</div><div class="section"><div class="assignment"><span class="swatch" style="background:${this.#filamentColor(current)}"></span><b>${primary?.name || "Objekt auswählen"}</b><select id="extruder" ${primary && filaments.length ? "" : "disabled"}>${filaments.map((item) => `<option value="${item.extruder}" ${item.extruder === current ? "selected" : ""}>${item.name} · ${item.material}</option>`).join("")}</select></div><small>Die Auswahl gilt für alle markierten Objekte/Teile.</small></div>`;
      host.querySelector<HTMLButtonElement>("#sync-ams")?.addEventListener("click", () => void this.#syncAms());
      host.querySelector<HTMLButtonElement>("#remove-model-colors")?.addEventListener("click", () => this.#removeModelColors());
      host.querySelector<HTMLSelectElement>("#extruder")?.addEventListener("change", (event) => {
        const value = Number((event.currentTarget as HTMLSelectElement).value);
        const changes = new Map<string, MeshInstance>();
        for (const item of selected) { this.#assignments.set(item.id, value); changes.set(item.id, { ...item, color: this.#filamentColor(value) }); }
        this.#replace(changes);
      });
      return;
    }
    if (this.#mode === "preview") {
      host.innerHTML = `<h3>G‑Code‑Vorschau</h3><div class="section"><b>${plate.name}</b><span>Status: ${this.#stageLabel(plate.stage)}</span><label>Layer ${plate.layerCount ? plate.visibleLayer + 1 : 0} / ${plate.layerCount}<input class="layer" id="layer" type="range" min="0" max="${Math.max(0, plate.layerCount - 1)}" value="${plate.visibleLayer}" ${plate.layerCount ? "" : "disabled"}></label>${plate.stage === "sliced" ? '<button id="mark-printed">Als gedruckt markieren</button>' : ""}</div>`;
      host.querySelector<HTMLInputElement>("#layer")?.addEventListener("input", (event) => { plate.visibleLayer = Number((event.currentTarget as HTMLInputElement).value); this.#viewport?.setInstances(this.#displayInstances()); });
      host.querySelector<HTMLButtonElement>("#mark-printed")?.addEventListener("click", () => this.#markPrinted());
      return;
    }
    const profiles = buildPlateProfiles(this.#catalog?.profiles ?? []), center = this.#center();
    host.innerHTML = `<h3>Transformieren</h3><div class="section"><b>${plate.name}</b><span>Status: ${this.#stageLabel(plate.stage)}</span><label>Druckplattenprofil<select id="plate-profile">${profiles.map((profile) => `<option value="${profile.id}" ${profile.id === plate.profileId ? "selected" : ""}>${profile.name}</option>`).join("")}</select></label><small>Profilwechsel verändert keine Modellposition.</small></div>${primary ? `<div class="section"><b>${selected.length > 1 ? `${selected.length} Objekte ausgewählt` : primary.name}</b><label>Position<div class="triple"><input data-kind="position" data-axis="0" type="number" step="0.1" value="${(center?.[0] ?? 0).toFixed(2)}"><input data-kind="position" data-axis="1" type="number" step="0.1" value="${(center?.[1] ?? 0).toFixed(2)}"><input data-kind="position" data-axis="2" type="number" step="0.1" value="${(center?.[2] ?? 0).toFixed(2)}"></div></label><label>Drehung<div class="triple"><input data-kind="rotation" data-axis="0" type="number" step="1" value="${primary.rotation[0].toFixed(1)}"><input data-kind="rotation" data-axis="1" type="number" step="1" value="${primary.rotation[1].toFixed(1)}"><input data-kind="rotation" data-axis="2" type="number" step="1" value="${primary.rotation[2].toFixed(1)}"></div></label><label>Skalierung<div class="triple"><input data-kind="scale" data-axis="0" type="number" step="0.01" value="${primary.scale[0].toFixed(3)}"><input data-kind="scale" data-axis="1" type="number" step="0.01" value="${primary.scale[1].toFixed(3)}"><input data-kind="scale" data-axis="2" type="number" step="0.01" value="${primary.scale[2].toFixed(3)}"></div></label></div>` : '<div class="section">Objekt im Canvas oder links auswählen.</div>'}`;
    host.querySelector<HTMLSelectElement>("#plate-profile")?.addEventListener("change", (event) => this.#setProfile(this.#activePlate, (event.currentTarget as HTMLSelectElement).value));
    host.querySelectorAll<HTMLInputElement>("[data-kind]").forEach((input) => input.addEventListener("change", () => {
      const kind = input.dataset.kind as "position" | "rotation" | "scale", axis = Number(input.dataset.axis) as 0 | 1 | 2, value = Number(input.value);
      if (!Number.isFinite(value)) return;
      const changes = new Map<string, MeshInstance>();
      if (kind === "position" && center) {
        const delta = value - center[axis];
        for (const item of selected) { const position = [...item.position] as Vec3; position[axis] += delta; changes.set(item.id, { ...item, position }); }
      } else {
        for (const item of selected) { const vector = [...item[kind]] as Vec3; vector[axis] = kind === "scale" ? Math.max(.001, value) : value; changes.set(item.id, { ...item, [kind]: vector }); }
      }
      this.#replace(changes);
    }));
  }
}

if (!customElements.get("ultimate-3d-unified-studio")) customElements.define("ultimate-3d-unified-studio", Ultimate3DMegaStudio);
