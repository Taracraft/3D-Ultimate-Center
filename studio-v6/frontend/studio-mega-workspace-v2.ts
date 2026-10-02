import { authenticatedFetch, errorMessage, writeFrontendAudit } from "./ha-api-transport.js";
import { jobActivityStore } from "./job-activity-store.js";
import { emitSliceActivity, type SliceActivityMetrics, type SliceActivityStatus } from "./slice-activity-events.js";
import { emitStudioOperation, type StudioOperationMetrics, type StudioOperationStatus } from "./studio-operation-events.js";
import { nextStudioSelection, selectAllStudioObjects } from "./studio-selection.js";
import { createPlateSliceJob, loadSliceProcessOverrides, type SliceMaterialPlan, type SliceProcessOverrides } from "./plate-slice-api.js";
import { processOverrideValidationError } from "./nozzle-process-contract.js";
import { saveProcess } from "./studio-process-options-state.js";
import { analyzeFloatingSupportNeeds, type FloatingSupportIssue } from "./floating-support-analysis.js";
import {
  supportPreviewStride,
  toolpathPreviewCounts,
  toolpathPreviewIndex,
  toolpathPreviewSampling,
  toolpathSupportColor,
  toolpathSupportKind,
  toolpathSupportLabel,
  toolpathSupportStats,
} from "./toolpath-support-filter.js";
import { loadPlatePurgeTower, savePlatePurgeTower } from "./purge-tower-state.js";
import { createPrimitiveGeometry, createStrokeGeometry, createTextGeometry, type PrimitiveKind } from "./primitive-geometry.js";
import "./v6-action-dialog.js";
import type { V6ActionDialog } from "./v6-action-dialog.js";
import { ProfileApi, type V6Profile, type V6ProfileCatalog } from "./profile-api.js";
import { bestFlatRotation, positionCenteredOnPlate, positionOnBed } from "./mesh-export.js";
import { shellHtmlV2, type MegaUiPlateV2, type MegaUiStateV2 } from "./studio-mega-ui-v2.js";
import { StudioMegaViewport, type MegaAxis, type MegaGizmoMode } from "./studio-mega-viewport.js";
import {
  buildPlateProfileFromCatalog,
  filamentColor,
  initialStudioSelection,
  plateVisualFromCatalog,
  printerBuildVolume,
  profileById,
  selectionPatch,
  uniqueStudioProfiles,
  type StudioPlateProfileSelection,
} from "./studio-profile-catalog.js";
import { externalFilamentProfileSelectHtml, filamentMaterial, filamentProfilesHtml, studioProfileBarHtml } from "./studio-profile-ui.js";
import { waitForBrowserPaint } from "./browser-yield.js";
import { buildMeshGeometryAsync } from "./mesh-geometry-async.js";
import { analyzePlateBounds, plateBoundsErrorMessage } from "./studio-plate-preflight.js";
import { export3mfStreamed } from "./three-mf-export-stream.js";
import {
  fetchSliceJob,
  inspectGallerySliceModel,
  inspectSliceModel,
  type SliceJob,
  type SliceModelInspection,
  type SliceProjectFilament,
} from "./slicing-api.js";
import {
  fetchDetailedDirectPrintStatus,
  type DetailedAmsSlot,
  type DetailedDirectPrintPrinter,
} from "./direct-print-status-api.js";
import { parseStl, type MeshGeometry, type MeshInstance, type Vec3 } from "./webgl-studio-viewport.js";
import type { WorkspaceSourceRequest } from "./workspace-source-request.js";
import {
  loadStudioWorkspace,
  saveStudioWorkspace,
  type PersistedStudioWorkspace,
} from "./studio-persistence.js";

const API_PREFIX = "/api/ultimate_3d_studio_v6/v1/slicer";
const ACTIVE = new Set(["queued", "running", "cancelling"]);
const COLORS = ["#ff4d4d", "#202020", "#36e51e", "#2e9bff", "#ffb62e", "#b96cff", "#25d5c5", "#f56ab3"];
const NEUTRAL_COLOR = "#6b7785";

type StudioMode = "prepare" | "colors" | "preview";
type PreviewColorMode = "material" | "feature";
type PreviewFeatureKey = "outer_wall" | "inner_wall" | "overhang_wall" | "top_surface" | "bottom_surface" | "bridge" | "ironing" | "gap_infill" | "solid_infill" | "infill" | "floating_shell" | "support" | "support_interface" | "brim" | "raft" | "skirt" | "purge_tower" | "flush_waste" | "custom" | "other";
const PREVIEW_FEATURE_KEYS: readonly PreviewFeatureKey[] = ["outer_wall", "inner_wall", "overhang_wall", "top_surface", "bottom_surface", "bridge", "ironing", "gap_infill", "solid_infill", "infill", "floating_shell", "support", "support_interface", "brim", "raft", "skirt", "purge_tower", "flush_waste", "custom", "other"];
type AxisMode = "free" | "x" | "y" | "z";
type DrawTool = "none" | "brush" | "eraser";
type PlateStage = "prepared" | "slicing" | "sliced" | "printed" | "error";
type ScenePart = Readonly<{
  id: string;
  object_id: string;
  part_id: string;
  name: string;
  extruder: number;
  positions: number[];
  triangle_count: number;
  visible: boolean;
}>;
type ScenePayload = Readonly<{ instances: ScenePart[]; plate_size: readonly [number, number] }>;
type ToolpathSegment = readonly [number, number, number, number, number, number, number, string, string];
type ToolpathLayer = Readonly<{ index: number; z: number; segments: ToolpathSegment[]; extrusion_mm: number; features?: string[] }>;
type ToolpathSummaryLayer = Readonly<{ index: number; z: number; segment_count: number; extrusion_mm: number; features?: string[] }>;
type ToolpathPayload = Readonly<{
  layer_count: number;
  filament_colors?: string[];
  layers?: ToolpathSummaryLayer[];
  chunk?: Readonly<{
    start_layer?: number;
    end_layer?: number;
    segment_count?: number;
    layers: ToolpathLayer[];
  }>;
}>;
type MaterialChoice = Readonly<{
  key: string;
  name: string;
  material: string;
  color: string;
  source: "ams" | "external_spool" | "model";
  global_id?: string;
  unit_id?: string;
  slot_index?: number;
  display_slot?: number;
  tray_id?: string;
  filament_id?: string;
}>;
type Plate = {
  id: number;
  name: string;
  width: number;
  depth: number;
  instances: MeshInstance[];
  selection: StudioPlateProfileSelection;
  materialSource: "ams" | "external_spool";
  externalFilamentProfileId: string;
  stage: PlateStage;
  jobId: string;
  lastError: string;
  layers: ToolpathLayer[];
  layerCount: number;
  visibleLayer: number;
  toolColors: string[];
};
type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  initial: Map<string, MeshInstance>;
  mode: MegaGizmoMode;
  axis: AxisMode;
};
type PurgeDragState = {
  pointerId: number;
  startX: number;
  startY: number;
  initialX: number;
  initialY: number;
};

type SelectionFrameDrag = {
  pointerId: number;
  startX: number;
  startY: number;
};

type BrushDrag = {
  pointerId: number;
  startX: number;
  startY: number;
  startPoint: Vec3;
};

type InspectNode = Readonly<{
  object_id: string;
  extruder: number | null;
  parts: readonly InspectNode[];
}>;
type ProjectOpenOptions = Readonly<{ replaceWorkspace?: boolean }>;
type StudioClipboardEntry = Readonly<{
  instance: MeshInstance;
  assignment: string;
}>;
type StudioClipboard = Readonly<{
  mode: "copy" | "cut";
  sourcePlate: Plate;
  sourcePlateId: number;
  sourceIds: readonly string[];
  objects: readonly StudioClipboardEntry[];
}>;

function normalizeColor(value: string | null | undefined): string {
  const raw = String(value || "").trim().replace(/^#/, "");
  const rgb = raw.length >= 6 ? raw.slice(0, 6) : "6b7785";
  return /^[0-9a-f]{6}$/i.test(rgb) ? `#${rgb.toLowerCase()}` : NEUTRAL_COLOR;
}

function amsSlotOccupied(slot: DetailedAmsSlot): boolean {
  return Boolean(
    slot.present
    || String(slot.material || "").trim()
    || String(slot.sub_brand || "").trim()
    || String(slot.color || "").trim(),
  );
}

function colorLabel(value: string | null | undefined): string {
  const raw = String(value || "").trim().replace(/^#/, "").slice(0, 6);
  if (!/^[0-9a-f]{6}$/i.test(raw)) return "";
  const red = Number.parseInt(raw.slice(0, 2), 16);
  const green = Number.parseInt(raw.slice(2, 4), 16);
  const blue = Number.parseInt(raw.slice(4, 6), 16);
  const maximum = Math.max(red, green, blue);
  const minimum = Math.min(red, green, blue);
  if (maximum < 45) return "Schwarz";
  if (minimum > 215) return "Weiß";
  if (maximum - minimum < 28) return "Grau";
  if (red > green * 1.35 && red > blue * 1.35) return "Rot";
  if (green > red * 1.25 && green > blue * 1.2) return "Grün";
  if (blue > red * 1.25 && blue > green * 1.15) return "Blau";
  if (red > 180 && green > 105 && blue < 90) return "Orange";
  if (red > 160 && green > 150 && blue < 100) return "Gelb";
  return "";
}

function newPlate(
  id: number,
  name: string,
  selection: StudioPlateProfileSelection,
  width = 256,
  depth = 256,
  materialSource: "ams" | "external_spool" = "ams",
  externalFilamentProfileId = "",
): Plate {
  return {
    id,
    name,
    width,
    depth,
    instances: [],
    selection: { ...selection, filament_profile_ids: [...selection.filament_profile_ids] },
    materialSource,
    externalFilamentProfileId,
    stage: "prepared",
    jobId: "",
    lastError: "",
    layers: [],
    layerCount: 0,
    visibleLayer: 0,
    toolColors: [],
  };
}

function normals(positions: Float32Array): Float32Array {
  const result = new Float32Array(positions.length);
  for (let index = 0; index < positions.length; index += 9) {
    const ax = positions[index]!, ay = positions[index + 1]!, az = positions[index + 2]!;
    const bx = positions[index + 3]!, by = positions[index + 4]!, bz = positions[index + 5]!;
    const cx = positions[index + 6]!, cy = positions[index + 7]!, cz = positions[index + 8]!;
    const ux = bx - ax, uy = by - ay, uz = bz - az;
    const vx = cx - ax, vy = cy - ay, vz = cz - az;
    let nx = uy * vz - uz * vy;
    let ny = uz * vx - ux * vz;
    let nz = ux * vy - uy * vx;
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
  return Object.freeze({
    positions,
    normals: normals(positions),
    triangleCount: positions.length / 9,
    boundsMin: min,
    boundsMax: max,
  });
}

function fitImportedGroup(instances: MeshInstance[], width: number, depth: number): MeshInstance[] {
  if (!instances.length) return instances;
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (const item of instances) {
    min[0] = Math.min(min[0], item.geometry.boundsMin[0]);
    min[1] = Math.min(min[1], item.geometry.boundsMin[1]);
    min[2] = Math.min(min[2], item.geometry.boundsMin[2]);
    max[0] = Math.max(max[0], item.geometry.boundsMax[0]);
    max[1] = Math.max(max[1], item.geometry.boundsMax[1]);
    max[2] = Math.max(max[2], item.geometry.boundsMax[2]);
  }
  const groupWidth = Math.max(.001, max[0] - min[0]);
  const groupDepth = Math.max(.001, max[1] - min[1]);
  const factor = Math.min(1, Math.max(.01, (width - 16) / groupWidth), Math.max(.01, (depth - 16) / groupDepth));
  const shiftX = width / 2 - (min[0] + max[0]) * factor / 2;
  const shiftY = depth / 2 - (min[1] + max[1]) * factor / 2;
  const shiftZ = -min[2] * factor;
  return instances.map((item) => ({
    ...item,
    scale: [factor, factor, factor],
    position: [shiftX, shiftY, shiftZ],
  }));
}

async function fetchScene(file: File, plateIndex: number, galleryAssetId = ""): Promise<ScenePayload> {
  const query = new URLSearchParams({
    filename: file.name,
    plate_index: String(plateIndex),
  });
  const init: RequestInit = galleryAssetId
    ? { method: "POST", headers: { Accept: "application/json" } }
    : {
        method: "POST",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      };
  if (galleryAssetId) query.set("gallery_asset_id", galleryAssetId);
  const response = await authenticatedFetch(
    `${API_PREFIX}/scene?${query}`,
    init,
  );
  if (!response.ok) {
    let message = `3MF-Szene HTTP ${response.status}`;
    try { message = errorMessage(await response.json(), message); } catch {}
    throw new Error(message);
  }
  return (await response.json() as { data: ScenePayload }).data;
}

async function fetchToolpath(jobId: string, start?: number, end?: number): Promise<ToolpathPayload> {
  const query = new URLSearchParams();
  if (start !== undefined) query.set("start", String(start));
  if (end !== undefined) query.set("end", String(end));
  const response = await authenticatedFetch(
    `${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/toolpath${query.size ? `?${query}` : ""}`,
    { headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new Error(`Toolpath HTTP ${response.status}`);
  return (await response.json() as { data: ToolpathPayload }).data;
}

/* U3D_DIRECT_PURGE_TOWER_V1 */
function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function mixColor(left: string, right: string, amount: number): string {
  const parse = (value: string): number[] => {
    const raw = value.replace("#", "").padEnd(6, "0").slice(0, 6);
    return [0,2,4].map((offset) => Number.parseInt(raw.slice(offset, offset + 2), 16));
  };
  const a = parse(left);
  const b = parse(right);
  const t = Math.max(0, Math.min(1, amount));
  return `#${a.map((value, index) => Math.round(value * (1 - t) + b[index]! * t).toString(16).padStart(2, "0")).join("")}`;
}

function materialPreviewColor(value: string): string {
  return normalizeColor(value);
}

function materialHighlightColor(value: string): string {
  const base = normalizeColor(value);
  const raw = base.replace("#", "");
  const red = Number.parseInt(raw.slice(0, 2), 16);
  const green = Number.parseInt(raw.slice(2, 4), 16);
  const blue = Number.parseInt(raw.slice(4, 6), 16);
  const luminance = (red * .2126 + green * .7152 + blue * .0722) / 255;
  return mixColor(base, "#ffffff", luminance < .12 ? .38 : luminance < .3 ? .25 : .14);
}

function previewFeatureKey(feature: string, category: string): PreviewFeatureKey {
  const supportKind = toolpathSupportKind(feature, category);
  if (supportKind === "interface") return "support_interface";
  if (supportKind !== "none") return "support";
  const value = feature.toLocaleLowerCase("de-DE").replaceAll("_", " ");
  if (category === "brim" || value.includes("brim")) return "brim";
  if (category === "raft" || value.includes("raft")) return "raft";
  if (category === "skirt" || value.includes("skirt")) return "skirt";
  if (category === "purge_tower" || value.includes("tower")) return "purge_tower";
  if (value.includes("flush") || value.includes("wipe")) return "flush_waste";
  if (value.includes("floating vertical shell") || value.includes("floating shell")) return "floating_shell";
  if (value.includes("overhang wall") || value.includes("overhang perimeter")) return "overhang_wall";
  if (value.includes("outer wall") || value.includes("external perimeter")) return "outer_wall";
  if (value.includes("inner wall") || value.includes("perimeter")) return "inner_wall";
  if (value.includes("top surface") || value.includes("top solid")) return "top_surface";
  if (value.includes("bottom surface") || value.includes("bottom solid")) return "bottom_surface";
  if (value.includes("bridge")) return "bridge";
  if (value.includes("ironing")) return "ironing";
  if (value.includes("gap infill") || value.includes("gap fill") || value.includes("gap")) return "gap_infill";
  if (value.includes("solid infill")) return "solid_infill";
  if (value.includes("infill")) return "infill";
  if (value.includes("custom")) return "custom";
  return "other";
}

function previewFeatureLabel(key: PreviewFeatureKey): string {
  return ({
    outer_wall: "Außenwand", inner_wall: "Innenwand", overhang_wall: "Überhangwand", top_surface: "Obere Oberfläche", bottom_surface: "Untere Oberfläche",
    bridge: "Brücken", ironing: "Bügeln / Ironing", gap_infill: "Lückenfüllung", solid_infill: "Massives Infill", infill: "Infill", floating_shell: "Freistehende Hülle", support: "Support",
    support_interface: "Support-Interface", brim: "Brim", raft: "Raft", skirt: "Skirt", purge_tower: "Reinigungsturm", flush_waste: "Spülpfade", custom: "Benutzerdefiniert", other: "Sonstige Bahnen",
  } as const)[key];
}

function previewFeatureColor(key: PreviewFeatureKey): string {
  return ({
    outer_wall: "#ff4b4b", inner_wall: "#ff8a3d", overhang_wall: "#ff5fa2", top_surface: "#42d4e8", bottom_surface: "#4c9dff",
    bridge: "#5ea7ff", ironing: "#7de2d1", gap_infill: "#f077bd", solid_infill: "#a579e8", infill: "#f2dc55", floating_shell: "#7de1ff", support: toolpathSupportColor("base"),
    support_interface: toolpathSupportColor("interface"), brim: "#f3c34d", raft: "#b889e8", skirt: "#9ca9b5", purge_tower: "#48d2d8", flush_waste: "#6ed6a7", custom: "#d3d7dc", other: "#f0f3f5",
  } as const)[key];
}

function featurePreviewColor(feature: string, category: string): string {
  const supportKind = toolpathSupportKind(feature, category);
  if (supportKind !== "none") return toolpathSupportColor(supportKind);
  const value = feature.toLocaleLowerCase("de-DE").replaceAll("_", " ");
  if (category === "brim" || value.includes("brim")) return "#f3c34d";
  if (category === "raft" || value.includes("raft")) return "#b889e8";
  if (category === "skirt" || value.includes("skirt")) return "#9ca9b5";
  if (category === "purge_tower" || value.includes("tower")) return "#48d2d8";
  if (value.includes("flush") || value.includes("wipe")) return "#6ed6a7";
  if (value.includes("floating vertical shell") || value.includes("floating shell")) return "#7de1ff";
  if (value.includes("overhang wall") || value.includes("overhang perimeter")) return "#ff5fa2";
  if (value.includes("outer wall") || value.includes("external perimeter")) return "#ff4b4b";
  if (value.includes("inner wall") || value.includes("perimeter")) return "#ff8a3d";
  if (value.includes("top surface") || value.includes("top solid")) return "#42d4e8";
  if (value.includes("bottom surface") || value.includes("bottom solid")) return "#4c9dff";
  if (value.includes("bridge")) return "#5ea7ff";
  if (value.includes("ironing")) return "#7de2d1";
  if (value.includes("gap infill") || value.includes("gap fill") || value.includes("gap")) return "#f077bd";
  if (value.includes("solid infill")) return "#a579e8";
  if (value.includes("infill")) return "#f2dc55";
  if (value.includes("custom")) return "#d3d7dc";
  return "#f0f3f5";
}

function layerHeight(layers: readonly ToolpathLayer[], layerIndex: number): number {
  const current = layers.find((layer) => layer.index === layerIndex);
  if (!current) return .2;
  const previous = [...layers].reverse().find((layer) => layer.index < layerIndex);
  return Math.max(.06, Math.min(.8, previous ? current.z - previous.z : current.z || .2));
}

function ribbonWidth(extrusion: number, length: number, height: number, feature: string): number {
  const filamentArea = Math.PI * .875 * .875;
  const estimated = extrusion > 0 ? extrusion * filamentArea / Math.max(.001, length * height) : .42;
  const value = feature.toLocaleLowerCase("de-DE");
  const limit = value.includes("support") ? .72 : value.includes("bridge") ? .9 : 1.15;
  return Math.max(.22, Math.min(limit, estimated));
}

function historyShellFeature(feature: string, category: string): boolean {
  const supportKind = toolpathSupportKind(feature, category);
  if (supportKind !== "none") return true;
  if (["brim", "raft", "skirt", "purge_tower"].includes(category)) return true;
  const value = feature.toLocaleLowerCase("de-DE").replaceAll("_", " ");
  return value.includes("outer wall")
    || value.includes("external perimeter")
    || value.includes("top surface")
    || value.includes("top solid")
    || value.includes("bottom surface")
    || value.includes("bottom solid")
    || value.includes("overhang wall")
    || value.includes("floating vertical shell")
    || value.includes("bridge");
}

function appendFlatRibbon(target: number[], x1: number, y1: number, x2: number, y2: number, nx: number, ny: number, z: number): void {
  target.push(
    x1 + nx, y1 + ny, z,
    x1 - nx, y1 - ny, z,
    x2 - nx, y2 - ny, z,
    x1 + nx, y1 + ny, z,
    x2 - nx, y2 - ny, z,
    x2 + nx, y2 + ny, z,
  );
}

function appendShellRibbon(target: number[], x1: number, y1: number, x2: number, y2: number, nx: number, ny: number, z: number, height: number): void {
  const top = z + .012;
  const bottom = Math.max(0, z - Math.max(.045, Math.min(.8, height) * .72));
  appendFlatRibbon(target, x1, y1, x2, y2, nx, ny, top);
  target.push(
    x1 + nx, y1 + ny, bottom,
    x2 + nx, y2 + ny, bottom,
    x2 + nx, y2 + ny, top,
    x1 + nx, y1 + ny, bottom,
    x2 + nx, y2 + ny, top,
    x1 + nx, y1 + ny, top,
    x1 - nx, y1 - ny, bottom,
    x2 - nx, y2 - ny, top,
    x2 - nx, y2 - ny, bottom,
    x1 - nx, y1 - ny, bottom,
    x1 - nx, y1 - ny, top,
    x2 - nx, y2 - ny, top,
  );
}

function toolpathMeshes(layers: readonly ToolpathLayer[], selectedLayer: number, toolColors: readonly string[], cumulative: boolean, colorMode: PreviewColorMode, supportOnly: boolean, visibleFeatures: ReadonlySet<PreviewFeatureKey>): MeshInstance[] {
  if (!layers.find((layer) => layer.index === selectedLayer)) return [];
  const startLayer = cumulative ? 0 : selectedLayer;
  const previewIndex = toolpathPreviewIndex(layers);
  const counts = toolpathPreviewCounts(previewIndex, selectedLayer, cumulative);
  const segmentBudget = supportOnly ? 160_000 : cumulative ? 145_000 : 180_000;
  const sampling = toolpathPreviewSampling(supportOnly ? counts.support : counts.total, counts.support, segmentBudget);
  const supportStride = sampling.supportStride;
  let supportSegmentIndex = 0;
  let modelSegmentIndex = 0;
  const groups = new Map<string, { color: string; positions: number[]; current: boolean; label: string }>();
  const groupFor = (key: string, color: string, current: boolean, label: string) => {
    const existing = groups.get(key);
    if (existing) return existing;
    const created = { color, positions: [], current, label };
    groups.set(key, created);
    return created;
  };

  for (const layer of layers) {
    if (layer.index < startLayer || layer.index > selectedLayer) continue;
    const current = layer.index === selectedLayer;
    const height = previewIndex.layerHeightByLayer.get(layer.index) ?? .2;
    for (const segment of layer.segments) {
      const [x1, y1, x2, y2, z, tool, extrusion, feature = "Modell", category = "model"] = segment;
      const dx = x2 - x1;
      const dy = y2 - y1;
      const length = Math.hypot(dx, dy);
      if (length < .0001) continue;
      const supportKind = toolpathSupportKind(feature, category);
      const isSupport = supportKind !== "none";
      const featureKey = previewFeatureKey(feature, category);
      if (!visibleFeatures.has(featureKey)) continue;
      if (supportOnly && !isSupport) continue;
      if (!current && !supportOnly && !historyShellFeature(feature, category)) continue;
      const preserveHistoryDetail = ["brim", "raft", "skirt", "purge_tower"].includes(category) || featureKey === "flush_waste";
      if (!current && !preserveHistoryDetail) {
        if (isSupport) {
          const include = supportSegmentIndex % supportStride === 0;
          supportSegmentIndex += 1;
          if (!include) continue;
        } else {
          const include = modelSegmentIndex % sampling.modelStride === 0;
          modelSegmentIndex += 1;
          if (!include) continue;
        }
      }

      const physicalWidth = ribbonWidth(extrusion, length, height, feature);
      const visibleWidth = Math.max(.18, physicalWidth * (current ? .80 : .76));
      const supportWidth = Math.min(.92, visibleWidth * (supportOnly ? 1.24 : 1.08));
      const width = isSupport ? supportWidth : visibleWidth;
      const nx = -dy / length * width / 2;
      const ny = dx / length * width / 2;
      const materialColor = materialPreviewColor(toolColors[tool % Math.max(1, toolColors.length)] ?? COLORS[tool % COLORS.length]!);
      const base = supportOnly ? toolpathSupportColor(supportKind) : colorMode === "feature" ? featurePreviewColor(feature, category) : materialColor;
      const color = current ? base : mixColor(base, supportOnly ? "#102b27" : "#17212a", colorMode === "feature" ? .18 : .12);
      const label = supportOnly ? toolpathSupportLabel(supportKind) : colorMode === "feature" ? feature : "Werkzeug " + (tool + 1);
      const family = supportOnly ? supportKind : colorMode === "feature" ? category : "tool-" + tool;
      const key = (current ? "current" : "history") + ":base:" + color + ":" + family;
      const group = groupFor(key, color, current, label);
      if (current || supportOnly) appendFlatRibbon(group.positions, x1, y1, x2, y2, nx, ny, z + (current ? .035 : .012));
      else appendShellRibbon(group.positions, x1, y1, x2, y2, nx, ny, z, height);

      if (!supportOnly && colorMode === "material") {
        const highlightColor = materialHighlightColor(materialColor);
        const highlightWidth = Math.max(.045, width * (current ? .18 : .12));
        const hnx = -dy / length * highlightWidth / 2;
        const hny = dx / length * highlightWidth / 2;
        const highlightKey = (current ? "current" : "history") + ":highlight:" + highlightColor + ":tool-" + tool;
        const highlight = groupFor(highlightKey, highlightColor, current, "Lichtkante · Werkzeug " + (tool + 1));
        appendFlatRibbon(highlight.positions, x1, y1, x2, y2, hnx, hny, z + (current ? .052 : .026));
      }
    }
  }

  return [...groups.entries()].filter(([, group]) => group.positions.length >= 9).map(([key, group], index) => ({
    id: "toolpath-" + selectedLayer + "-" + index + "-" + key,
    name: group.current ? "Aktueller Layer · " + group.label : "Vorherige Layer · " + group.label,
    geometry: geometry(group.positions),
    position: [0,0,0], rotation: [0,0,0], scale: [1,1,1], color: group.color, visible: true,
  }));
}
function boxGeometry(width: number, depth: number, z0: number, z1: number): MeshGeometry {
  const positions = [
    0,0,z0,width,0,z0,width,depth,z0, 0,0,z0,width,depth,z0,0,depth,z0,
    0,0,z1,width,depth,z1,width,0,z1, 0,0,z1,0,depth,z1,width,depth,z1,
    0,0,z0,0,0,z1,width,0,z1, 0,0,z0,width,0,z1,width,0,z0,
    width,0,z0,width,0,z1,width,depth,z1, width,0,z0,width,depth,z1,width,depth,z0,
    width,depth,z0,width,depth,z1,0,depth,z1, width,depth,z0,0,depth,z1,0,depth,z0,
    0,depth,z0,0,depth,z1,0,0,z1, 0,depth,z0,0,0,z1,0,0,z0,
  ];
  return geometry(positions);
}

export class Ultimate3DMegaStudioV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #profileApi = new ProfileApi();
  #catalog: V6ProfileCatalog | null = null;
  #printers: DetailedDirectPrintPrinter[] = [];
  #file: File | null = null;
  #inspection: SliceModelInspection | null = null;
  #plates: Plate[] = [newPlate(0, "Druckplatte 1", initialStudioSelection(null))];
  #activePlate = 0;
  #mode: StudioMode = "prepare";
  #previewColorMode: PreviewColorMode = "feature";
  #previewCumulative = true;
  #previewSupportOnly = false;
  #previewVisibleFeatures = new Set<PreviewFeatureKey>(PREVIEW_FEATURE_KEYS);
  #previewMaterialOpen = true;
  #topCollapsed = false;
  #leftCollapsed = false;
  #rightCollapsed = false;
  #tool: MegaGizmoMode = "select";
  #drawTool: DrawTool = "none";
  #axis: AxisMode = "free";
  #selected = new Set<string>();
  #selectionAnchor: string | null = null;
  #assignments = new Map<string, string>();
  #clipboard: StudioClipboard | null = null;
  #modelMaterials: MaterialChoice[] = [];
  #amsSlots = new Map<string, DetailedAmsSlot[]>();
  #amsError = "";
  #amsLoading = false;
  #modalError = "";
  #viewport: StudioMegaViewport | null = null;
  #drag: DragState | null = null;
  #purgeDrag: PurgeDragState | null = null;
  #selectionFrameDrag: SelectionFrameDrag | null = null;
  #brushDrag: BrushDrag | null = null;
  #status = "Bereit";
  #error = "";
  #loading = false;
  #generation = 0;
  #nextId = 1;
  #recentImportKey = "";
  #recentImportAt = 0;
  #initialized = false;
  #cleanupTimer: number | null = null;
  #persistTimer: number | null = null;
  #persistQueue: Promise<void> = Promise.resolve();
  #workspaceReady = false;
  #deferredFullRender = false;
  #reconcilingJobs = new Set<string>();
  #slicePreparationId = "";
  #sliceTraceByJob = new Map<string, string>();
  #operationTraceId = "";

  #audit(event: string, status: "info" | "success" | "warning" | "error" = "info", details: Readonly<Record<string, unknown>> = {}): void {
    const plate = this.#plates[this.#activePlate];
    writeFrontendAudit({
      category: "Studio",
      component: "studio-workspace",
      event,
      status,
      job_id: plate?.jobId || undefined,
      details: { plate_index: this.#activePlate, plate_name: plate?.name || null, object_count: plate?.instances.length ?? 0, ...details },
    });
  }

  #setSlicePreparation(active: boolean, phase = "", progress = 0): void {
    const plate = this.#plate();
    if (active && !this.#slicePreparationId) this.#slicePreparationId = `studio-plate-${plate.id}-${Date.now()}`;
    const id = this.#slicePreparationId;
    globalThis.dispatchEvent(new CustomEvent("ultimate-3d-slice-preparation", {
      detail: {
        active,
        id,
        fileName: this.#file?.name || plate.name,
        plateName: plate.name,
        phase,
        progress: Math.max(0, Math.min(100, progress)),
      },
    }));
    if (!active) this.#slicePreparationId = "";
  }

  #traceSliceActivity(
    code: string,
    label: string,
    options: Readonly<{
      traceId?: string | undefined;
      jobId?: string | undefined;
      detail?: string | undefined;
      progress?: number | null | undefined;
      status?: SliceActivityStatus | undefined;
      active?: boolean | undefined;
      metrics?: SliceActivityMetrics | undefined;
    }> = {},
  ): void {
    const plate = this.#plate();
    const jobId = String(options.jobId || "").trim();
    const mappedTrace = jobId ? this.#sliceTraceByJob.get(jobId) || "" : "";
    const traceId = String(options.traceId || mappedTrace || this.#slicePreparationId || (jobId ? `slice-job-${jobId}` : "")).trim();
    if (!traceId) return;
    if (jobId) this.#sliceTraceByJob.set(jobId, traceId);
    const detail = {
      active: options.active !== false,
      traceId,
      fileName: this.#file?.name || plate.name,
      plateName: plate.name,
      plateId: plate.id,
      code,
      label,
      detail: options.detail || "",
      progress: options.progress ?? null,
      status: options.status || "info",
    } as {
      active: boolean;
      traceId: string;
      jobId?: string;
      fileName: string;
      plateName: string;
      plateId: number;
      code: string;
      label: string;
      detail: string;
      progress: number | null;
      status: SliceActivityStatus;
      metrics?: SliceActivityMetrics;
    };
    if (jobId) detail.jobId = jobId;
    if (options.metrics !== undefined) detail.metrics = options.metrics;
    emitSliceActivity(detail);
  }

  #traceStudioOperation(
    kind: "import" | "export",
    code: string,
    label: string,
    options: Readonly<{
      traceId?: string | undefined;
      fileName?: string | undefined;
      source?: string | undefined;
      detail?: string | undefined;
      progress?: number | null | undefined;
      status?: StudioOperationStatus | undefined;
      active?: boolean | undefined;
      metrics?: StudioOperationMetrics | undefined;
    }> = {},
  ): void {
    const traceId = String(options.traceId || this.#operationTraceId || "").trim();
    if (!traceId) return;
    const detail = {
      active: options.active !== false,
      traceId,
      kind,
      fileName: options.fileName || this.#file?.name || this.#plate().name,
      code,
      label,
      detail: options.detail || "",
      progress: options.progress ?? null,
      status: options.status || "running",
    } as {
      active: boolean;
      traceId: string;
      kind: "import" | "export";
      fileName: string;
      source?: string;
      code: string;
      label: string;
      detail: string;
      progress: number | null;
      status: StudioOperationStatus;
      metrics?: StudioOperationMetrics;
    };
    if (options.source !== undefined) detail.source = options.source;
    if (options.metrics !== undefined) detail.metrics = options.metrics;
    emitStudioOperation(detail);
  }

  set files(value: readonly File[]) { const file = value[0]; if (file) this.file = file; }
  set file(value: File | null) {
    if (value) this.#requestImport(value, false, "");
  }
  get file(): File | null { return this.#file; }

  openProject(value: File, options: ProjectOpenOptions = {}): void {
    this.#requestImport(value, options.replaceWorkspace !== false, "");
  }

  openGalleryProject(assetId: string, fileName: string, options: ProjectOpenOptions = {}): void {
    const normalizedAssetId = String(assetId || "").trim();
    const normalizedFileName = String(fileName || "gallery-project.3mf").trim() || "gallery-project.3mf";
    if (!normalizedAssetId) return;
    const placeholder = new File([], normalizedFileName, { type: "model/3mf" });
    this.#requestImport(placeholder, options.replaceWorkspace !== false, normalizedAssetId);
  }

  #resetWorkspaceForProjectOpen(fileName: string, galleryAssetId: string): void {
    const previous = this.#plate();
    const selection = {
      ...previous.selection,
      filament_profile_ids: [...previous.selection.filament_profile_ids],
    };
    for (const plate of this.#plates) {
      plate.jobId = "";
      plate.stage = "prepared";
      plate.lastError = "";
      plate.layers = [];
      plate.layerCount = 0;
      plate.visibleLayer = 0;
      plate.toolColors = [];
    }
    jobActivityStore.dismissSlicerJob();
    this.#reconcilingJobs.clear();
    this.#sliceTraceByJob.clear();
    if (this.#slicePreparationId) this.#setSlicePreparation(false);
    this.#plates = [newPlate(0, "Druckplatte 1", selection, previous.width, previous.depth, previous.materialSource, previous.externalFilamentProfileId)];
    this.#activePlate = 0;
    this.#selected.clear();
    this.#selectionAnchor = null;
    this.#assignments.clear();
    this.#modelMaterials = [];
    this.#inspection = null;
    this.#file = null;
    this.#mode = "prepare";
    this.#previewColorMode = "feature";
    this.#previewCumulative = true;
    this.#previewSupportOnly = false;
    this.#previewVisibleFeatures = new Set(PREVIEW_FEATURE_KEYS);
    this.#previewMaterialOpen = true;
    this.#error = "";
    this.#modalError = "";
    this.#amsError = "";
    this.#loading = true;
    this.#status = `${fileName} wird als neues Projekt geöffnet …`;
    this.#viewport?.setPreviewMode(false);
    this.#viewport?.setInstances([]);
    this.#audit("project_workspace_reset", "success", {
      filename: fileName,
      source: galleryAssetId ? "gallery_server_asset" : "browser_file",
    });
    this.#renderFull();
    this.#schedulePersist(700);
  }

  #requestImport(value: File, replaceWorkspace: boolean, galleryAssetId: string): void {
    const key = galleryAssetId || `${value.name}:${value.size}:${value.lastModified}`;
    const now = Date.now();
    if (key === this.#recentImportKey && now - this.#recentImportAt < 2500) return;
    this.#recentImportKey = key;
    this.#recentImportAt = now;
    if (replaceWorkspace) this.#resetWorkspaceForProjectOpen(value.name, galleryAssetId);
    this.#file = value;
    this.#mode = "prepare";
    this.#operationTraceId = `studio-import-${Date.now()}-${this.#nextId}`;
    this.#traceStudioOperation("import", "import_requested", "Import gestartet", {
      traceId: this.#operationTraceId,
      fileName: value.name,
      source: galleryAssetId ? "Galerie / Server-Asset" : "Lokale Datei",
      detail: `${replaceWorkspace ? "Projekt öffnen" : "Objekt hinzufügen"}${value.size > 0 ? ` · ${(value.size / 1024 / 1024).toFixed(2)} MB` : ""}`,
      progress: 1,
      status: "running",
      metrics: { inputSizeBytes: value.size || undefined },
    });
    this.#audit("model_import_requested", "info", {
      filename: value.name,
      size_bytes: value.size,
      type: value.type,
      source: galleryAssetId ? "gallery_server_asset" : "browser_file",
      replace_workspace: replaceWorkspace,
    });
    void this.#load(value, replaceWorkspace, galleryAssetId);
  }

  connectedCallback(): void {
    if (this.#cleanupTimer !== null) {
      globalThis.clearTimeout(this.#cleanupTimer);
      this.#cleanupTimer = null;
    }
    this.tabIndex = 0;
    document.removeEventListener("keydown", this.#keyDown, true);
    this.#root.removeEventListener("pointerdown", this.#rootPointerDown);
    this.removeEventListener("studio-process-options-changed", this.#processOptionsChanged as EventListener);
    globalThis.removeEventListener("pagehide", this.#pageHide);
    document.removeEventListener("visibilitychange", this.#visibilityChanged);
    document.addEventListener("keydown", this.#keyDown, true);
    this.#root.addEventListener("pointerdown", this.#rootPointerDown);
    this.addEventListener("studio-process-options-changed", this.#processOptionsChanged as EventListener);
    globalThis.addEventListener("pagehide", this.#pageHide);
    document.addEventListener("visibilitychange", this.#visibilityChanged);
    if (!this.#initialized) {
      this.#initialized = true;
      void this.#bootstrap();
      return;
    }
    queueMicrotask(() => {
      if (!this.isConnected) return;
      if (this.#deferredFullRender) {
        this.#deferredFullRender = false;
        this.#renderFull();
      } else if (!this.#viewport) this.#mountViewport();
      else {
        this.#viewport.resize();
        this.#viewport.requestRender();
      }
      if (!this.#loading && this.#plate().stage === "slicing") void this.#activatePlateJob(this.#plate());
    });
  }

  disconnectedCallback(): void {
    document.removeEventListener("keydown", this.#keyDown, true);
    this.#root.removeEventListener("pointerdown", this.#rootPointerDown);
    this.removeEventListener("studio-process-options-changed", this.#processOptionsChanged as EventListener);
    globalThis.removeEventListener("pagehide", this.#pageHide);
    document.removeEventListener("visibilitychange", this.#visibilityChanged);
    void this.#persistNow();
    if (this.#cleanupTimer !== null) globalThis.clearTimeout(this.#cleanupTimer);
    this.#cleanupTimer = globalThis.setTimeout(() => {
      this.#cleanupTimer = null;
      if (this.isConnected) return;
      this.#viewport?.dispose();
      this.#viewport = null;
    }, 5000);
  }

  readonly #processOptionsChanged = (): void => {
    this.#viewport?.setInstances(this.#displayInstances());
    this.#renderStatus();
  };

  readonly #rootPointerDown = (event: Event): void => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest(".menubar")) this.#closeMenus();
    if (!target?.closest("input,select,textarea,[contenteditable='true']")) this.focus({ preventScroll: true });
  };

  readonly #pageHide = (): void => { void this.#persistNow(); };
  readonly #visibilityChanged = (): void => {
    if (document.visibilityState === "hidden") void this.#persistNow();
  };

  readonly #keyDown = (event: KeyboardEvent): void => {
    if (!this.isConnected || this.getClientRects().length === 0) return;
    if (event.composedPath().some((node) => node instanceof HTMLInputElement || node instanceof HTMLSelectElement || node instanceof HTMLTextAreaElement || (node instanceof HTMLElement && node.isContentEditable))) return;
    const key = event.key.toLowerCase();
    if ((event.ctrlKey || event.metaKey) && key === "a") {
      event.preventDefault();
      const selection = selectAllStudioObjects(this.#plate().instances.map((item) => item.id));
      this.#selected = selection.selected;
      this.#selectionAnchor = selection.anchor;
      this.#refreshSelectionUi();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && key === "c") { event.preventDefault(); this.#copySelection("copy"); return; }
    if ((event.ctrlKey || event.metaKey) && key === "x") { event.preventDefault(); this.#copySelection("cut"); return; }
    if ((event.ctrlKey || event.metaKey) && key === "v") { event.preventDefault(); this.#pasteClipboard(); return; }
    if ((event.ctrlKey || event.metaKey) && key === "d") { event.preventDefault(); this.#duplicate(); return; }
    if (event.key === "Delete" || event.key === "Backspace") { event.preventDefault(); this.#remove(); return; }
    if (key === "g") this.#setTool("translate");
    if (key === "r") this.#setTool("rotate");
    if (key === "s") this.#setTool("scale");
    if (key === "q" || event.key === "Escape") this.#setTool("select");
    if (key === "x" || key === "y" || key === "z") this.#setAxis(key);
    if (key === "f") this.#setAxis("free");
  };

  async #bootstrap(): Promise<void> {
    this.#loading = true;
    this.#status = "Gespeicherte Studio-Sitzung wird geladen …";
    this.#renderFull();
    await this.#restoreWorkspace();
    if (!this.isConnected) return;
    this.#workspaceReady = true;
    this.#loading = false;
    this.#renderFull();
    void this.#activatePlateJob(this.#plate());
    void this.#loadEnvironment();
  }

  #workspaceSnapshot(): PersistedStudioWorkspace {
    return {
      version: 1,
      savedAt: Date.now(),
      activePlate: this.#activePlate,
      mode: this.#mode === "colors" ? "colors" : "prepare",
      nextId: this.#nextId,
      selected: [...this.#selected],
      assignments: [...this.#assignments.entries()],
      modelMaterials: this.#modelMaterials.map((item) => ({ ...item })),
      plates: this.#plates.map((plate) => ({
        id: plate.id,
        name: plate.name,
        width: plate.width,
        depth: plate.depth,
        stage: plate.stage,
        jobId: plate.jobId,
        materialSource: plate.materialSource,
        externalFilamentProfileId: plate.externalFilamentProfileId,
        selection: {
          ...plate.selection,
          filament_profile_ids: [...plate.selection.filament_profile_ids],
        },
        instances: plate.instances.map((item) => ({
          id: item.id,
          name: item.name,
          positions: new Float32Array(item.geometry.positions),
          position: [...item.position] as Vec3,
          rotation: [...item.rotation] as Vec3,
          scale: [...item.scale] as Vec3,
          color: item.color,
          visible: item.visible,
        })),
      })),
    };
  }

  async #restoreWorkspace(): Promise<void> {
    try {
      const snapshot = await loadStudioWorkspace();
      if (!snapshot?.plates.length) return;
      const plates: Plate[] = snapshot.plates.map((plate, index) => ({
        id: index,
        name: plate.name || `Druckplatte ${index + 1}`,
        width: Math.max(1, Number(plate.width) || 256),
        depth: Math.max(1, Number(plate.depth) || 256),
        selection: {
          ...plate.selection,
          filament_profile_ids: [...plate.selection.filament_profile_ids],
        },
        materialSource: plate.materialSource === "external_spool" ? "external_spool" : "ams",
        externalFilamentProfileId: String(plate.externalFilamentProfileId || ""),
        instances: plate.instances.map((item) => ({
          id: item.id,
          name: item.name,
          geometry: geometry(item.positions),
          position: [...item.position] as Vec3,
          rotation: [...item.rotation] as Vec3,
          scale: [...item.scale] as Vec3,
          color: item.color,
          visible: item.visible,
        })),
        stage: plate.stage ?? "prepared",
        jobId: String(plate.jobId || ""),
        lastError: "",
        layers: [],
        layerCount: 0,
        visibleLayer: 0,
        toolColors: [],
      }));
      const instanceIds = new Set(plates.flatMap((plate) => plate.instances.map((item) => item.id)));
      this.#plates = plates;
      this.#activePlate = Math.max(0, Math.min(snapshot.activePlate, plates.length - 1));
      this.#mode = snapshot.mode;
      this.#nextId = Math.max(1, snapshot.nextId);
      this.#assignments = new Map(snapshot.assignments.filter(([id]) => instanceIds.has(id)));
      this.#modelMaterials = snapshot.modelMaterials.map((item) => ({ ...item }));
      this.#selected = new Set(snapshot.selected.filter((id) => instanceIds.has(id)));
      this.#selectionAnchor = [...this.#selected][0] ?? null;
      this.#status = `Studio-Sitzung wiederhergestellt · ${instanceIds.size} Objekt(e)`;
      this.#audit("workspace_restored", "success", { restored_objects: instanceIds.size, plate_count: plates.length });
    } catch (error) {
      console.warn("Studio-Sitzung konnte nicht wiederhergestellt werden", error);
      this.#audit("workspace_restore_failed", "error", { error: error instanceof Error ? error.message : String(error) });
    }
  }

  async #persistNow(): Promise<void> {
    if (!this.#workspaceReady) return;
    if (this.#persistTimer !== null) {
      globalThis.clearTimeout(this.#persistTimer);
      this.#persistTimer = null;
    }
    const snapshot = this.#workspaceSnapshot();
    this.#persistQueue = this.#persistQueue
      .then(() => saveStudioWorkspace(snapshot))
      .catch((error) => {
        console.warn("Studio-Sitzung konnte nicht gespeichert werden", error);
      });
    await this.#persistQueue;
  }

  #schedulePersist(delay = 180): void {
    if (!this.#workspaceReady) return;
    if (this.#persistTimer !== null) globalThis.clearTimeout(this.#persistTimer);
    this.#persistTimer = globalThis.setTimeout(() => {
      this.#persistTimer = null;
      void this.#persistNow();
    }, Math.max(0, delay));
  }

  #bindProfileSelectors(): void {
    this.#root.querySelectorAll<HTMLSelectElement>("[data-profile-field]").forEach((select) => {
      select.addEventListener("change", () => void this.#profileChanged(
        select.dataset.profileField as keyof StudioPlateProfileSelection,
        select.value,
      ));
    });
    this.#root.querySelector<HTMLSelectElement>("[data-material-source]")?.addEventListener("change", (event) => {
      this.#materialSourceChanged((event.currentTarget as HTMLSelectElement).value);
    });
    this.#root.querySelector<HTMLSelectElement>("[data-external-filament-profile]")?.addEventListener("change", (event) => {
      this.#externalFilamentProfileChanged((event.currentTarget as HTMLSelectElement).value);
    });
    this.#bindProcessOverrideInputs();
  }

  #selectedNozzleDiameter(): number | null {
    const payload = profileById(this.#catalog, this.#plate().selection.nozzle_profile_id)?.payload;
    const diameter = Number(payload?.diameter_mm);
    return Number.isFinite(diameter) ? diameter : null;
  }

  #bindProcessOverrideInputs(): void {
    this.#root.querySelectorAll<HTMLInputElement>("[data-process-override]").forEach((input) => {
      input.addEventListener("change", () => {
        const field = input.dataset.processOverride as "layer_height_mm" | "outer_wall_speed_mm_s" | "inner_wall_speed_mm_s";
        const raw = input.value.trim();
        const parsed = raw === "" ? null : Number(raw);
        const current = loadSliceProcessOverrides();
        const next = { ...current, [field]: parsed } as SliceProcessOverrides;
        const error = processOverrideValidationError(next, this.#selectedNozzleDiameter());
        input.setCustomValidity(error || "");
        if (error) {
          input.reportValidity();
          this.#error = error;
          this.#renderStatus();
          return;
        }
        this.#error = "";
        saveProcess(String(this.#plate().id), next);
        this.#invalidatePlate(this.#plate());
        this.#status = raw === ""
          ? `${this.#plate().name}: ${field === "layer_height_mm" ? "Schichthöhe" : field === "outer_wall_speed_mm_s" ? "Außenwandgeschwindigkeit" : "Innenwandgeschwindigkeit"} verwendet wieder das Standardprofil.`
          : `${this.#plate().name}: Benutzerdefinierte Slicereinstellung gespeichert.`;
        this.#renderFull();
      });
    });
  }

  #refreshEnvironmentUi(): void {
    const current = this.#root.querySelector<HTMLElement>(".profilebar");
    if (current) {
      const template = document.createElement("template");
      template.innerHTML = studioProfileBarHtml(this.#catalog, this.#printers, this.#plate().selection, this.#plate().materialSource, this.#plate().externalFilamentProfileId).trim();
      const replacement = template.content.firstElementChild;
      if (replacement) current.replaceWith(replacement);
    }
    this.#bindProfileSelectors();
    this.#viewport?.setPlate(this.#profileVisual());
    this.#viewport?.setInstances(this.#displayInstances());
    this.#renderSidebar();
    this.#renderStatus();
    this.#schedulePersist();
  }

  async #loadEnvironment(): Promise<void> {
    try {
      const [catalog, status] = await Promise.all([
        this.#profileApi.getCatalog(),
        fetchDetailedDirectPrintStatus().catch(() => ({ items: [], two_step_confirmation: true, slot_numbering: "global" })),
      ]);
      this.#catalog = catalog;
      this.#printers = [...status.items];
      for (const printer of this.#printers) {
        this.#amsSlots.set(printer.printer_id, this.#occupiedAmsSlots(printer));
      }
      const initial = initialStudioSelection(catalog);
      const firstPrinter = this.#printers.find((printer) => printer.ready) ?? this.#printers[0];
      if (firstPrinter) initial.target_printer_id = firstPrinter.printer_id;
      for (const plate of this.#plates) {
        plate.selection = {
          ...initial,
          ...plate.selection,
          target_printer_id: plate.selection.target_printer_id || initial.target_printer_id,
          printer_profile_id: plate.selection.printer_profile_id || initial.printer_profile_id,
          nozzle_profile_id: plate.selection.nozzle_profile_id || initial.nozzle_profile_id,
          process_profile_id: plate.selection.process_profile_id || initial.process_profile_id,
          build_plate_profile_id: plate.selection.build_plate_profile_id || initial.build_plate_profile_id,
          filament_profile_ids: plate.selection.filament_profile_ids.length
            ? [...plate.selection.filament_profile_ids]
            : [...initial.filament_profile_ids],
        };
        this.#applyBuildPlateProfile(plate, false);
      }
      this.#refreshEnvironmentUi();
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#refreshEnvironmentUi();
    }
  }

  async #activatePlateJob(plate: Plate): Promise<void> {
    const jobId = String(plate.jobId || "").trim();
    if (!jobId) {
      const current = jobActivityStore.snapshot.slicer;
      if (current && !ACTIVE.has(current.status)) jobActivityStore.dismissSlicerJob(current.id);
      return;
    }
    if (this.#reconcilingJobs.has(jobId)) return;
    this.#reconcilingJobs.add(jobId);
    const traceId = this.#sliceTraceByJob.get(jobId) || `slice-job-${jobId}`;
    this.#sliceTraceByJob.set(jobId, traceId);
    const ownedLoadingState = this.#plate() === plate;
    let lastJobStatus = "";
    let summaryFeatureLabels: string[] = [];
    let totalSegments = 0;
    const reportJobState = (job: SliceJob): void => {
      if (job.status === "running") {
        const createdAt = new Date(String(job.started_at || job.created_at || "")).getTime();
        const elapsedSeconds = Number.isFinite(createdAt) ? Math.max(0, (Date.now() - createdAt) / 1000) : undefined;
        lastJobStatus = job.status;
        this.#traceSliceActivity("slicer_running", "Bambu Studio verarbeitet das Modell", {
          traceId,
          jobId,
          detail: "Der native Slicer arbeitet. Die aktuelle Server-API veröffentlicht noch keine belastbare interne Unterphase oder Prozentzahl.",
          progress: 66,
          status: "running",
          active: true,
          metrics: { elapsedSeconds },
        });
        return;
      }
      if (job.status === lastJobStatus) return;
      lastJobStatus = job.status;
      const state = ({
        queued: ["Slicerauftrag wartet auf den Slicing-Server", "Der Auftrag wurde angenommen und wartet auf Verarbeitung.", 58, "running", true],
        running: ["Slicing Server verarbeitet das Modell", "Das native Slicing läuft. Der Server liefert für diese Phase keinen belastbaren Prozentwert.", 66, "running", true],
        cancelling: ["Abbruch wird angefordert", "Der Slicerauftrag befindet sich im Abbruchzustand.", 70, "warning", true],
        succeeded: ["Slicing Server meldet Abschluss", "Das G-Code-Artefakt ist erzeugt. Analyse und Vorschaudaten folgen.", 78, "success", true],
        failed: ["Slicing fehlgeschlagen", job.error || "Der Slicing Server hat den Auftrag als fehlgeschlagen gemeldet.", 100, "error", false],
        cancelled: ["Slicing wurde abgebrochen", "Der Slicerauftrag wurde abgebrochen.", 100, "warning", false],
        interrupted: ["Slicing wurde unterbrochen", job.error || "Der Slicerauftrag wurde unterbrochen.", 100, "warning", false],
      } as const)[job.status];
      if (!state) return;
      this.#traceSliceActivity(`slicer_${job.status}`, state[0], {
        traceId,
        jobId,
        detail: state[1],
        progress: state[2],
        status: state[3],
        active: state[4],
      });
    };
    try {
      let job = await fetchSliceJob(jobId);
      reportJobState(job);
      if (ACTIVE.has(job.status)) {
        plate.stage = "slicing";
        jobActivityStore.registerSlicerJob(job);
        if (this.#plate() === plate) {
          this.#loading = true;
          this.#status = plate.name + " wird weiter verarbeitet …";
          this.#renderStatus();
        }
        while (plate.jobId === jobId && ACTIVE.has(job.status)) {
          await new Promise((resolve) => globalThis.setTimeout(resolve, 700));
          job = await fetchSliceJob(jobId);
          jobActivityStore.registerSlicerJob(job);
          reportJobState(job);
        }
      }
      if (plate.jobId !== jobId) return;
      reportJobState(job);
      if (job.status !== "succeeded") throw new Error(job.error || "Slicing fehlgeschlagen");

      const sliceResult = job.slice_result;
      const resultFacts: string[] = [];
      if (Number(sliceResult?.layer_count) > 0) resultFacts.push(`${Number(sliceResult?.layer_count).toLocaleString("de-DE")} Layer`);
      if (Number(sliceResult?.material_channel_count) > 0) resultFacts.push(`${Number(sliceResult?.material_channel_count).toLocaleString("de-DE")} Materialkanal/-kanäle`);
      if (Number(job.output_size_bytes) > 0) resultFacts.push(`${(Number(job.output_size_bytes) / 1024 / 1024).toFixed(1)} MB G-Code-3MF`);
      this.#traceSliceActivity("gcode_artifact_ready", "G-Code erfolgreich erzeugt", {
        traceId,
        jobId,
        detail: resultFacts.length ? resultFacts.join(" · ") : "Das G-Code-Artefakt wurde erfolgreich erzeugt.",
        progress: 80,
        status: "success",
        metrics: {
          layerCount: Number(sliceResult?.layer_count) || undefined,
          materialCount: Number(sliceResult?.material_channel_count) || undefined,
          outputSizeBytes: Number(job.output_size_bytes) || undefined,
        },
      });

      plate.stage = "sliced";
      plate.lastError = "";
      if (this.#plate() === plate) {
        this.#loading = false;
        this.#status = plate.name + ": Slicing abgeschlossen · Vorschau wird geladen …";
        this.#renderAfterSliceReconcile();
      }
      if (!plate.layers.length || plate.layerCount <= 0) {
        this.#traceSliceActivity("toolpath_parse_started", "G-Code wird für die 3D-Vorschau analysiert", {
          traceId,
          jobId,
          detail: "Layer, Extrusionsbahnen und Druckbahntypen werden aus dem G-Code ermittelt.",
          progress: 82,
          status: "running",
        });
        const summary = await fetchToolpath(jobId);
        plate.toolColors = (summary.filament_colors ?? []).map((color) => normalizeColor(color));
        plate.layerCount = summary.layer_count;
        plate.visibleLayer = Math.max(0, plate.layerCount - 1);
        const summaryLayers = summary.layers ?? [];
        totalSegments = summaryLayers.reduce((sum, layer) => sum + Math.max(0, Number(layer.segment_count) || 0), 0);
        summaryFeatureLabels = [...new Set(summaryLayers.flatMap((layer) => layer.features ?? []).map((feature) => previewFeatureLabel(previewFeatureKey(String(feature), "model"))))];
        this.#traceSliceActivity("toolpath_summary_ready", "Toolpath-Analyse abgeschlossen", {
          traceId,
          jobId,
          detail: `${summary.layer_count.toLocaleString("de-DE")} Layer · ${totalSegments.toLocaleString("de-DE")} Extrusionsbahnen · ${summaryFeatureLabels.length.toLocaleString("de-DE")} Druckbahntyp(en)${summaryFeatureLabels.length ? ` · ${summaryFeatureLabels.join(", ")}` : ""}`,
          progress: 88,
          status: "success",
          metrics: {
            layerCount: summary.layer_count,
            segmentCount: totalSegments,
            materialCount: plate.toolColors.length,
            features: summaryFeatureLabels,
          },
        });
        const ranges: Array<readonly [number, number]> = [];
        for (let start = 0; start < summary.layer_count; start += 35) {
          ranges.push([start, Math.min(summary.layer_count, start + 35)]);
        }
        const layers: ToolpathLayer[] = [];
        const parallelRequests = 4;
        const renderStartedAt = performance.now();
        let loadedSegments = 0;
        const seenFeatureLabels = new Set<string>();
        for (let offset = 0; offset < ranges.length; offset += parallelRequests) {
          if (plate.jobId !== jobId) return;
          const batch = ranges.slice(offset, offset + parallelRequests);
          const chunks = await Promise.all(batch.map(([start, end]) => fetchToolpath(jobId, start, end)));
          let batchSegments = 0;
          for (const chunk of chunks) {
            const chunkLayers = chunk.chunk?.layers ?? [];
            layers.push(...chunkLayers);
            batchSegments += Math.max(0, Number(chunk.chunk?.segment_count) || chunkLayers.reduce((sum, layer) => sum + layer.segments.length, 0));
            for (const feature of chunkLayers.flatMap((layer) => layer.features ?? [])) {
              seenFeatureLabels.add(previewFeatureLabel(previewFeatureKey(String(feature), "model")));
            }
          }
          loadedSegments += batchSegments;
          const loaded = Math.min(summary.layer_count, (offset + batch.length) * 35);
          if (this.#plate() === plate) {
            this.#status = plate.name + ": Slicing abgeschlossen · Vorschau " + loaded + " / " + summary.layer_count + " Layer";
            this.#renderStatus();
          }
          const featureText = seenFeatureLabels.size ? ` · Bahntypen bisher: ${[...seenFeatureLabels].join(", ")}` : "";
          const renderElapsedSeconds = Math.max(.001, (performance.now() - renderStartedAt) / 1000);
          const layerRatePerSecond = loaded > 0 ? loaded / renderElapsedSeconds : undefined;
          const segmentRatePerSecond = loadedSegments > 0 ? loadedSegments / renderElapsedSeconds : undefined;
          const etaSeconds = layerRatePerSecond && layerRatePerSecond > 0
            ? Math.max(0, (summary.layer_count - loaded) / layerRatePerSecond)
            : undefined;
          this.#traceSliceActivity("preview_chunk_loaded", `Renderdaten ${loaded.toLocaleString("de-DE")} / ${summary.layer_count.toLocaleString("de-DE")} Layer geladen`, {
            traceId,
            jobId,
            detail: `${batchSegments.toLocaleString("de-DE")} Bahnen in diesem Block · ${loadedSegments.toLocaleString("de-DE")}${totalSegments ? ` / ${totalSegments.toLocaleString("de-DE")}` : ""} Bahnen im Browser${featureText}`,
            progress: 90 + (summary.layer_count ? loaded / summary.layer_count * 9 : 0),
            status: "running",
            metrics: {
              loadedLayers: loaded,
              layerCount: summary.layer_count,
              loadedSegmentCount: loadedSegments,
              segmentCount: totalSegments || undefined,
              elapsedSeconds: renderElapsedSeconds,
              etaSeconds,
              layerRatePerSecond,
              segmentRatePerSecond,
              features: [...seenFeatureLabels],
            },
          });
        }
        layers.sort((left, right) => left.index - right.index);
        plate.layers = layers;
        this.#traceSliceActivity("render_data_ready", "Renderdaten vollständig in den Browser übertragen", {
          traceId,
          jobId,
          detail: `${plate.layerCount.toLocaleString("de-DE")} Layer · ${loadedSegments.toLocaleString("de-DE")} Bahnen${summaryFeatureLabels.length ? ` · ${summaryFeatureLabels.join(", ")}` : ""}`,
          progress: 99,
          status: "success",
          metrics: {
            loadedLayers: plate.layerCount,
            layerCount: plate.layerCount,
            loadedSegmentCount: loadedSegments,
            segmentCount: totalSegments || loadedSegments,
            features: summaryFeatureLabels,
          },
        });
      } else {
        totalSegments = plate.layers.reduce((sum, layer) => sum + layer.segments.length, 0);
        summaryFeatureLabels = [...new Set(plate.layers.flatMap((layer) => layer.features ?? []).map((feature) => previewFeatureLabel(previewFeatureKey(String(feature), "model"))))];
        this.#traceSliceActivity("render_data_reused", "Bereits geladene Renderdaten werden verwendet", {
          traceId,
          jobId,
          detail: `${plate.layerCount.toLocaleString("de-DE")} Layer · ${totalSegments.toLocaleString("de-DE")} Bahnen`,
          progress: 99,
          status: "info",
        });
      }
      job = await fetchSliceJob(jobId);
      if (plate.jobId !== jobId) return;
      if (this.#plate() === plate) {
        this.#mode = "preview";
        this.#previewColorMode = "feature";
        this.#status = plate.name + ": " + plate.layerCount + " Layer erfolgreich geladen.";
      }
      jobActivityStore.registerSlicerJob(job);
      this.#audit("slice_completed", "success", { job_id: job.id, layer_count: plate.layerCount });
      await this.#persistNow();
      this.#traceSliceActivity("preview_ready", "Vorschaudaten vollständig bereit", {
        traceId,
        jobId,
        detail: `${plate.layerCount.toLocaleString("de-DE")} Layer stehen für die 3D-Vorschau bereit${summaryFeatureLabels.length ? ` · Druckbahntypen: ${summaryFeatureLabels.join(", ")}` : ""}`,
        progress: 100,
        status: "success",
        active: false,
        metrics: {
          layerCount: plate.layerCount,
          segmentCount: totalSegments || undefined,
          features: summaryFeatureLabels,
        },
      });
    } catch (error) {
      if (plate.jobId === jobId) {
        plate.stage = "error";
        plate.lastError = error instanceof Error ? error.message : String(error);
        this.#audit("slice_reconcile_failed", "error", { job_id: jobId, plate_id: plate.id, error: plate.lastError });
        this.#traceSliceActivity("slice_pipeline_failed", "Slicer-/Vorschauverarbeitung fehlgeschlagen", {
          traceId,
          jobId,
          detail: plate.lastError,
          progress: 100,
          status: "error",
          active: false,
        });
      }
      console.warn("Plattengebundener Slicerauftrag konnte nicht aktiviert werden", error);
    } finally {
      this.#reconcilingJobs.delete(jobId);
      if (ownedLoadingState) this.#loading = false;
      this.#renderAfterSliceReconcile();
    }
  }

  #plate(): Plate { return this.#plates[this.#activePlate] ?? this.#plates[0]!; }
  #renderAfterSliceReconcile(): void {
    if (this.isConnected) this.#renderFull();
    else this.#deferredFullRender = true;
  }
  #selectedItems(): MeshInstance[] { return this.#plate().instances.filter((item) => this.#selected.has(item.id)); }
  #center(): Vec3 | null {
    const items = this.#selectedItems();
    if (!items.length) return null;
    return [
      items.reduce((sum, item) => sum + item.position[0], 0) / items.length,
      items.reduce((sum, item) => sum + item.position[1], 0) / items.length,
      items.reduce((sum, item) => sum + item.position[2], 0) / items.length,
    ];
  }
  #gizmoAxis(): MegaAxis { return this.#axis === "free" ? "x" : this.#axis; }
  #purgeTowerData(plate = this.#plate()): { instances: MeshInstance[]; width: number; height: number; flushVolume: number; colorCount: number; x: number; y: number; brim: number } {
    if (plate.materialSource === "external_spool") return { instances: [], width: 0, height: 0, flushVolume: 0, colorCount: 1, x: 0, y: 0, brim: 0 };
    const keys = [...new Set(
      plate.instances
        .map((item) => this.#assignments.get(item.id))
        .filter((key): key is string => Boolean(key)),
    )];
    const stored = loadPlatePurgeTower(plate.id);
    if (keys.length <= 1 || stored.enabled === false) return { instances: [], width: 0, height: 0, flushVolume: 0, colorCount: keys.length, x: 0, y: 0, brim: 0 };
    const matrix = this.#inspection?.purge_tower?.flush_volumes_matrix;
    const matrixVolume = Array.isArray(matrix)
      ? matrix.reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0)
      : 0;
    const pairCount = keys.length * Math.max(1, keys.length - 1);
    const flushMultiplier = Math.max(.1, Math.min(3, Number(stored.flush_multiplier ?? 1)));
    const flushVolume = Math.max(pairCount * 110, matrixVolume) * flushMultiplier;
    const modelHeight = Math.max(8, ...plate.instances.map((item) => (
      item.position[2] + (item.geometry.boundsMax[2] - item.geometry.boundsMin[2]) * Math.abs(item.scale[2])
    )));
    const height = Math.max(8, modelHeight);
    const requiredArea = Math.max(625, flushVolume / Math.max(1, height * .34));
    const width = Math.max(25, Math.min(60, Math.ceil(Math.sqrt(requiredArea) / 2) * 2));
    const brim = Math.max(0, Math.min(20, Number(stored.brim_width_mm ?? 3)));
    const visibleInset = 18;
    const minimumCenter = width / 2 + brim + visibleInset;
    const maximumX = Math.max(minimumCenter, plate.width - width / 2 - brim - visibleInset);
    const maximumY = Math.max(minimumCenter, plate.depth - width / 2 - brim - visibleInset);
    const x = Math.max(minimumCenter, Math.min(maximumX, Number(stored.position_x ?? maximumX)));
    const y = Math.max(minimumCenter, Math.min(maximumY, Number(stored.position_y ?? maximumY)));
    const segmentHeight = height / keys.length;
    const instances = keys.map((key, index) => ({
      id: `purge-tower-${plate.id}-${index}`,
      name: "Reinigungsturm",
      geometry: boxGeometry(width, width, index * segmentHeight, (index + 1) * segmentHeight),
      position: [x - width / 2, y - width / 2, 0] as Vec3,
      rotation: [0,0,0] as Vec3,
      scale: [1,1,1] as Vec3,
      color: this.#materialColor(key),
      visible: true,
    }));
    return { instances, width, height, flushVolume, colorCount: keys.length, x, y, brim };
  }

  #refreshPreviewViewport(): void {
    const viewport = this.#viewport;
    if (!viewport) return;
    viewport.setInstances(this.#displayInstances());
    requestAnimationFrame(() => {
      if (this.#viewport !== viewport) return;
      viewport.resize();
      viewport.requestRender();
      requestAnimationFrame(() => {
        if (this.#viewport !== viewport) return;
        viewport.requestRender();
      });
    });
  }

  #displayInstances(): MeshInstance[] {
    const plate = this.#plate();
    if (this.#mode === "preview" && plate.layers.length) {
      return toolpathMeshes(
        plate.layers,
        plate.visibleLayer,
        plate.toolColors.length ? plate.toolColors : this.#materialChoices(plate).map((choice) => choice.color),
        this.#previewCumulative,
        this.#previewColorMode,
        this.#previewSupportOnly,
        this.#previewVisibleFeatures,
      );
    }
    return [...plate.instances, ...this.#purgeTowerData(plate).instances];
  }
  #stageLabel(stage: PlateStage): string {
    return ({ prepared: "Vorbereitet", slicing: "Slicing läuft", sliced: "Geslicet", printed: "Gedruckt", error: "Fehler" } as const)[stage];
  }
  #profileVisual(plate = this.#plate()) {
    const visual = plateVisualFromCatalog(this.#catalog, plate.selection.build_plate_profile_id);
    return { ...visual, widthMm: plate.width, depthMm: plate.depth };
  }

  #amsMaterialChoices(plate = this.#plate()): MaterialChoice[] {
    const slots = this.#amsSlots.get(plate.selection.target_printer_id) ?? [];
    const seen = new Set<string>();
    const choices: MaterialChoice[] = [];
    for (const slot of slots) {
      if (!amsSlotOccupied(slot) || !slot.global_id || seen.has(slot.global_id)) continue;
      seen.add(slot.global_id);
      const materialName = String(slot.sub_brand || slot.material || "Filament").trim();
      const shade = colorLabel(slot.color);
      choices.push({
        key: `ams:${slot.global_id}`,
        name: `AMS ${slot.display_slot}: ${materialName}${shade && !materialName.toLocaleLowerCase("de-DE").includes(shade.toLocaleLowerCase("de-DE")) ? ` ${shade}` : ""}`,
        material: slot.material || "unknown",
        color: normalizeColor(slot.color),
        source: "ams",
        global_id: slot.global_id,
        unit_id: slot.unit_id,
        slot_index: slot.slot_index,
        display_slot: slot.display_slot,
        tray_id: slot.tray_id,
        filament_id: slot.tray_id,
      });
    }
    return choices.sort((left, right) => (left.display_slot ?? 0) - (right.display_slot ?? 0));
  }

  #externalFilamentChoice(plate = this.#plate()): MaterialChoice | null {
    if (!plate.externalFilamentProfileId) return null;
    const profile = profileById(this.#catalog, plate.externalFilamentProfileId);
    if (!profile || profile.kind !== "filament") return null;
    const material = filamentMaterial(profile);
    const filamentId = String(profile.payload.filament_id || profile.id).trim();
    if (!material || !filamentId) return null;
    return {
      key: `external:${profile.id}`,
      name: profile.name,
      material,
      color: normalizeColor(filamentColor(profile, COLORS[0]!)),
      source: "external_spool",
      filament_id: filamentId,
    };
  }

  #materialChoices(plate = this.#plate()): MaterialChoice[] {
    const choices = [...this.#amsMaterialChoices(plate)];
    const external = this.#externalFilamentChoice(plate);
    if (external) choices.push(external);
    for (const model of this.#modelMaterials) {
      if (!choices.some((choice) => choice.key === model.key)) choices.push(model);
    }
    return choices;
  }

  #materialPlan(): SliceMaterialPlan {
    const plate = this.#plate();
    const targetPrinterId = String(plate.selection.target_printer_id || "").trim();
    if (!targetPrinterId) throw new Error("Vor dem Slicing muss ein Ziel-Drucker gewählt werden.");
    if (plate.materialSource === "external_spool") {
      const choice = this.#externalFilamentChoice(plate);
      if (!choice) throw new Error("Für die externe Spule muss genau ein vollständiges Filamentprofil gewählt werden.");
      const visible = plate.instances.filter((instance) => instance.visible);
      if (!visible.length) throw new Error("Die aktive Druckplatte enthält kein sichtbares Objekt.");
      return {
        source: "external_spool",
        target_printer_id: targetPrinterId,
        assignments: Object.fromEntries(visible.map((item) => [item.id, 1])),
        filaments: [{
          extruder: 1,
          name: choice.name,
          material: choice.material,
          color: choice.color,
          filament_id: choice.filament_id!,
          source: "external_spool",
        }],
        purge_tower: { enabled: false },
      };
    }
    const choices = this.#amsMaterialChoices(plate);
    if (!choices.length) {
      throw new Error("Am Ziel-Drucker ist kein belegter AMS-Slot verfügbar. Bitte AMS synchronisieren.");
    }
    const originalIndexByKey = new Map(choices.map((choice, index) => [choice.key, index + 1]));
    const pending: Array<readonly [MeshInstance, number]> = [];
    const missing: string[] = [];
    for (const item of plate.instances.filter((instance) => instance.visible)) {
      const key = this.#assignments.get(item.id) || "";
      const originalIndex = originalIndexByKey.get(key);
      if (!originalIndex) missing.push(item.name);
      else pending.push([item, originalIndex]);
    }
    if (missing.length) {
      const names = [...new Set(missing)].slice(0, 4).join(", ");
      const suffix = missing.length > 4 ? ` und ${missing.length - 4} weitere` : "";
      throw new Error(`Nicht alle sichtbaren Objekte sind einem belegten AMS-Slot zugeordnet: ${names}${suffix}.`);
    }
    const usedOriginal = [...new Set(pending.map((entry) => entry[1]))].sort((left, right) => left - right);
    const compactByOriginal = new Map(usedOriginal.map((value, index) => [value, index + 1]));
    const assignments: Record<string, number> = {};
    for (const [item, originalIndex] of pending) assignments[item.id] = compactByOriginal.get(originalIndex)!;
    const usedChoices = usedOriginal.map((index) => choices[index - 1]!);
    const filaments: Array<SliceProjectFilament & {
      global_id: string;
      unit_id: string;
      slot_index: number;
      display_slot: number;
      tray_id: string;
      filament_id: string;
      source: "ams";
    }> = usedChoices.map((choice, index) => ({
      extruder: index + 1,
      name: choice.name,
      material: choice.material,
      color: choice.color,
      global_id: choice.global_id || "",
      unit_id: choice.unit_id || "",
      slot_index: choice.slot_index ?? 0,
      display_slot: choice.display_slot ?? (choice.slot_index ?? 0) + 1,
      tray_id: choice.tray_id || "",
      filament_id: choice.filament_id || choice.tray_id || "",
      source: "ams",
    }));
    const tower = loadPlatePurgeTower(plate.id);
    const towerData = this.#purgeTowerData(plate);
    savePlatePurgeTower(plate.id, {
      ...tower,
      width_mm: towerData.width || Number(tower.width_mm ?? 35),
      brim_width_mm: towerData.brim || Number(tower.brim_width_mm ?? 3),
      position_x: towerData.x || Number(tower.position_x ?? plate.width - 40),
      position_y: towerData.y || Number(tower.position_y ?? plate.depth - 40),
    });
    return {
      source: "ams",
      target_printer_id: targetPrinterId,
      assignments,
      filaments,
      purge_tower: {
        ...(this.#inspection?.purge_tower ?? {}),
        ...tower,
        enabled: usedChoices.length > 1 && tower.enabled !== false,
        width_mm: towerData.width,
        brim_width_mm: towerData.brim,
        position_x: towerData.x,
        position_y: towerData.y,
        flush_multiplier: Math.max(.1, Number(tower.flush_multiplier ?? 1)),
      },
    };
  }

  #ui(): MegaUiStateV2 {
    const plate = this.#plate();
    const plates: MegaUiPlateV2[] = this.#plates.map((item) => ({
      name: item.name,
      width: item.width,
      depth: item.depth,
      profile: this.#profileVisual(item),
      instances: item.instances,
      status: this.#stageLabel(item.stage),
      jobId: item.jobId,
    }));
    return {
      mode: this.#mode,
      tool: this.#tool,
      axis: this.#axis,
      activePlate: this.#activePlate,
      plates,
      selected: this.#selected,
      status: plate.lastError || this.#status,
      error: this.#error || plate.lastError,
      modalError: this.#modalError,
      loading: this.#loading,
      canSlice: plate.instances.length > 0 && plate.stage !== "slicing",
      layerCount: plate.layerCount,
      visibleLayer: plate.visibleLayer,
      center: this.#center(),
      profileBar: studioProfileBarHtml(this.#catalog, this.#printers, plate.selection, plate.materialSource, plate.externalFilamentProfileId),
      topCollapsed: this.#topCollapsed,
      leftCollapsed: this.#leftCollapsed,
      rightCollapsed: this.#rightCollapsed,
    };
  }

  async #load(file: File, replaceWorkspace = false, galleryAssetId = ""): Promise<void> {
    const generation = ++this.#generation;
    const importNumber = this.#nextId++;
    const traceId = this.#operationTraceId || `studio-import-${Date.now()}-${importNumber}`;
    const source = galleryAssetId ? "Galerie / Server-Asset" : "Lokale Datei";
    this.#operationTraceId = traceId;
    this.#loading = true;
    this.#error = "";
    this.#status = `${file.name} wird analysiert …`;
    this.#mode = "prepare";
    this.#traceStudioOperation("import", "inspection_started", "Datei und Projektstruktur werden analysiert", {
      traceId,
      fileName: file.name,
      source,
      detail: `${source}${file.size > 0 ? ` · ${(file.size / 1024 / 1024).toFixed(2)} MB` : ""}`,
      progress: 4,
      status: "running",
      metrics: { inputSizeBytes: file.size || undefined },
    });
    this.#renderFull();
    try {
      const inspection = galleryAssetId
        ? await inspectGallerySliceModel(galleryAssetId)
        : await inspectSliceModel(file);
      if (generation !== this.#generation) return;
      const inspectedPlateCount = inspection.format === "3mf" ? Math.max(1, inspection.plate_count || inspection.plates.length || 1) : 1;
      this.#traceStudioOperation("import", "inspection_ready", "Projektanalyse abgeschlossen", {
        traceId,
        fileName: file.name,
        source,
        detail: `${inspection.format.toUpperCase()} · ${inspectedPlateCount.toLocaleString("de-DE")} Druckplatte(n) · ${inspection.filaments.length.toLocaleString("de-DE")} Materialdefinition(en)`,
        progress: 12,
        status: "success",
        metrics: {
          plateCount: inspectedPlateCount,
          objectCount: inspection.objects.length,
          materialCount: inspection.filaments.length,
          inputSizeBytes: file.size || undefined,
        },
      });
      if (replaceWorkspace) {
        const previous = this.#plate();
        const selection = {
          ...previous.selection,
          filament_profile_ids: [...previous.selection.filament_profile_ids],
        };
        for (const plate of this.#plates) plate.jobId = "";
        const activeJob = jobActivityStore.snapshot.slicer;
        if (activeJob && !ACTIVE.has(activeJob.status)) jobActivityStore.dismissSlicerJob(activeJob.id);
        this.#plates = [newPlate(0, "Druckplatte 1", selection, previous.width, previous.depth, previous.materialSource, previous.externalFilamentProfileId)];
        this.#activePlate = 0;
        this.#selected.clear();
        this.#selectionAnchor = null;
        this.#assignments.clear();
        this.#modelMaterials = [];
        this.#inspection = null;
        this.#previewSupportOnly = false;
        this.#audit("project_workspace_replaced", "success", {
          filename: file.name,
          source: galleryAssetId ? "gallery_server_asset" : "browser_file",
        });
        this.#traceStudioOperation("import", "workspace_ready", "Studio-Arbeitsbereich für das Projekt vorbereitet", {
          traceId,
          fileName: file.name,
          source,
          detail: "Vorherige Projektinhalte wurden kontrolliert aus dem Arbeitsbereich entfernt.",
          progress: 16,
          status: "success",
        });
      }
      this.#inspection = inspection;
      this.#modelMaterials = inspection.filaments.map((filament) => ({
        key: `model:${filament.extruder}`,
        name: filament.name || `Modellfarbe ${filament.extruder}`,
        material: filament.material || "unknown",
        color: normalizeColor(filament.color),
        source: "model",
      }));
      const originalExtruders = new Map<string, number>();
      for (const object of inspection.objects as readonly InspectNode[]) this.#collectExtruders(object, originalExtruders);
      const importedIds: string[] = [];
      let processedObjects = 0;
      let importedTriangles = 0;

      if (inspection.format === "3mf") {
        const count = Math.max(1, inspection.plate_count || inspection.plates.length || 1);
        const importedPlates: Plate[] = [];
        for (let index = 0; index < count; index += 1) {
          this.#traceStudioOperation("import", `plate_${index + 1}_load`, `Druckplatte ${index + 1} / ${count} wird geladen`, {
            traceId,
            fileName: file.name,
            source,
            detail: inspection.plates[index]?.name || `Druckplatte ${index + 1}`,
            progress: 18 + index / Math.max(1, count) * 62,
            status: "running",
            metrics: { plateCount: count, loadedPlates: index, loadedObjects: processedObjects },
          });
          const data = await fetchScene(file, index, galleryAssetId);
          if (generation !== this.#generation) return;
          this.#traceStudioOperation("import", `plate_${index + 1}_scene`, `Druckplatte ${index + 1} analysiert`, {
            traceId,
            fileName: file.name,
            source,
            detail: `${data.instances.length.toLocaleString("de-DE")} Objekt/Teil(e) · ${data.plate_size[0] || 256} × ${data.plate_size[1] || 256} mm`,
            progress: 20 + index / Math.max(1, count) * 62,
            status: "success",
            metrics: { plateCount: count, loadedPlates: index, objectCount: data.instances.length, loadedObjects: processedObjects },
          });
          const selection = { ...this.#plate().selection, filament_profile_ids: [...this.#plate().selection.filament_profile_ids] };
          const width = data.plate_size[0] || 256;
          const depth = data.plate_size[1] || 256;
          const rawInstances: MeshInstance[] = [];
          for (let partIndex = 0; partIndex < data.instances.length; partIndex += 1) {
            const part = data.instances[partIndex]!;
            const geometryProgress = 22 + ((index + (partIndex / Math.max(1, data.instances.length))) / Math.max(1, count)) * 60;
            const geometryCode = `plate_${index + 1}_geometry_${partIndex + 1}`;
            this.#traceStudioOperation("import", geometryCode, `Geometrie ${partIndex + 1} / ${data.instances.length} wird berechnet`, {
              traceId,
              fileName: file.name,
              source,
              detail: `${inspection.plates[index]?.name || `Druckplatte ${index + 1}`} · ${part.name}`,
              progress: geometryProgress,
              status: "running",
              metrics: { plateCount: count, loadedPlates: index, objectCount: data.instances.length, loadedObjects: processedObjects, triangleCount: importedTriangles },
            });
            this.#status = `${file.name}: Geometrie ${partIndex + 1} / ${data.instances.length} wird vorbereitet …`;
            this.#renderStatus();
            const partGeometry = await buildMeshGeometryAsync(part.positions);
            if (generation !== this.#generation) return;
            processedObjects += 1;
            importedTriangles += partGeometry.triangleCount;
            this.#traceStudioOperation("import", geometryCode, `Geometrie ${partIndex + 1} / ${data.instances.length} berechnet`, {
              traceId,
              fileName: file.name,
              source,
              detail: `${part.name} · ${partGeometry.triangleCount.toLocaleString("de-DE")} Dreiecke`,
              progress: geometryProgress,
              status: "success",
              metrics: { plateCount: count, loadedPlates: index, objectCount: data.instances.length, loadedObjects: processedObjects, triangleCount: importedTriangles },
            });
            const id = `import-${importNumber}-${this.#nextId++}`;
            const extruder = originalExtruders.get(part.part_id)
              ?? originalExtruders.get(part.object_id)
              ?? part.extruder
              ?? 1;
            const key = `model:${extruder}`;
            this.#assignments.set(id, key);
            importedIds.push(id);
            rawInstances.push({
              id,
              name: part.name,
              geometry: partGeometry,
              position: [0,0,0] as Vec3,
              rotation: [0,0,0] as Vec3,
              scale: [1,1,1] as Vec3,
              color: this.#materialColor(key),
              visible: part.visible,
            });
          }
          const plate = newPlate(
            0,
            inspection.plates[index]?.name || `${file.name} · Platte ${index + 1}`,
            selection,
            width,
            depth,
            this.#plate().materialSource,
            this.#plate().externalFilamentProfileId,
          );
          plate.instances = fitImportedGroup(rawInstances, width, depth);
          importedPlates.push(plate);
          this.#traceStudioOperation("import", `plate_${index + 1}_ready`, `Druckplatte ${index + 1} / ${count} vorbereitet`, {
            traceId,
            fileName: file.name,
            source,
            detail: `${plate.name} · ${plate.instances.length.toLocaleString("de-DE")} Objekt/Teil(e) positioniert`,
            progress: 22 + (index + 1) / Math.max(1, count) * 64,
            status: "success",
            metrics: { plateCount: count, loadedPlates: index + 1, loadedObjects: processedObjects, triangleCount: importedTriangles },
          });
        }
        const onlyEmptyStartPlate = this.#plates.length === 1 && this.#plates[0]!.instances.length === 0;
        const startIndex = onlyEmptyStartPlate ? 0 : this.#plates.length;
        if (onlyEmptyStartPlate) this.#plates = importedPlates;
        else this.#plates.push(...importedPlates);
        this.#plates.forEach((plate, index) => {
          plate.id = index;
          if (!plate.name.trim()) plate.name = `Druckplatte ${index + 1}`;
        });
        this.#activePlate = startIndex;
      } else {
        this.#traceStudioOperation("import", "stl_read", "STL-Geometrie wird gelesen", {
          traceId,
          fileName: file.name,
          source,
          progress: 28,
          status: "running",
          metrics: { inputSizeBytes: file.size || undefined },
        });
        const mesh = parseStl(await file.arrayBuffer());
        if (generation !== this.#generation) return;
        processedObjects = 1;
        importedTriangles = mesh.triangleCount;
        this.#traceStudioOperation("import", "stl_read", "STL-Geometrie gelesen", {
          traceId,
          fileName: file.name,
          source,
          detail: `${mesh.triangleCount.toLocaleString("de-DE")} Dreiecke`,
          progress: 64,
          status: "success",
          metrics: { objectCount: 1, loadedObjects: 1, triangleCount: mesh.triangleCount, inputSizeBytes: file.size || undefined },
        });
        const plate = this.#plate();
        const id = `import-${importNumber}-${this.#nextId++}`;
        const base: MeshInstance = {
          id,
          name: file.name.replace(/\.stl$/i, ""),
          geometry: mesh,
          position: [0,0,0],
          rotation: [0,0,0],
          scale: [1,1,1],
          color: NEUTRAL_COLOR,
          visible: true,
        };
        const position = positionCenteredOnPlate(mesh, base, plate.width, plate.depth);
        plate.instances.push({ ...base, position: positionOnBed(mesh, { ...base, position }) });
        plate.stage = "prepared";
        importedIds.push(id);
        this.#traceStudioOperation("import", "stl_placed", "STL auf der aktiven Druckplatte positioniert", {
          traceId,
          fileName: file.name,
          source,
          detail: `${plate.name} · zentriert und auf das Druckbett gesetzt`,
          progress: 88,
          status: "success",
          metrics: { plateCount: 1, loadedPlates: 1, objectCount: 1, loadedObjects: 1, triangleCount: mesh.triangleCount },
        });
      }
      this.#selected = new Set(this.#plate().instances.filter((item) => importedIds.includes(item.id)).map((item) => item.id));
      if (!this.#selected.size && this.#plate().instances[0]) this.#selected.add(this.#plate().instances[0]!.id);
      const importAction = replaceWorkspace ? "geöffnet" : "hinzugefügt";
      this.#status = `${file.name} ${importAction} · ${this.#plates.length} Platte(n) · aktive Platte ${this.#activePlate + 1}`;
      this.#audit(replaceWorkspace ? "project_open_completed" : "model_import_completed", "success", {
        filename: file.name,
        plate_count: this.#plates.length,
        imported_objects: importedIds.length,
        format: inspection.format,
        source: galleryAssetId ? "gallery_server_asset" : "browser_file",
      });
      this.#traceStudioOperation("import", "import_complete", replaceWorkspace ? "Projekt vollständig geöffnet" : "Import vollständig abgeschlossen", {
        traceId,
        fileName: file.name,
        source,
        detail: `${importedIds.length.toLocaleString("de-DE")} Objekt/Teil(e) · ${this.#plates.length.toLocaleString("de-DE")} Druckplatte(n) · ${importedTriangles.toLocaleString("de-DE")} Dreiecke`,
        progress: 100,
        status: "success",
        active: false,
        metrics: { plateCount: this.#plates.length, loadedPlates: this.#plates.length, objectCount: importedIds.length, loadedObjects: importedIds.length, triangleCount: importedTriangles, materialCount: inspection.filaments.length },
      });
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#audit("model_import_failed", "error", { filename: file.name, error: this.#error });
      this.#traceStudioOperation("import", "import_failed", "Import fehlgeschlagen", {
        traceId,
        fileName: file.name,
        source,
        detail: this.#error,
        progress: 100,
        status: "error",
        active: false,
      });
    } finally {
      if (generation === this.#generation) {
        if (this.#operationTraceId === traceId) this.#operationTraceId = "";
        this.#loading = false;
        this.#renderFull();
        this.#schedulePersist(700);
      }
    }
  }

  #collectExtruders(item: InspectNode, target: Map<string, number>): void {
    if (item.object_id) target.set(item.object_id, Number(item.extruder || 1));
    for (const part of item.parts) this.#collectExtruders(part, target);
  }

  #materialColor(key: string, plate = this.#plate()): string {
    if (plate.materialSource === "external_spool") {
      return this.#externalFilamentChoice(plate)?.color ?? NEUTRAL_COLOR;
    }
    return this.#materialChoices(plate).find((choice) => choice.key === key)?.color ?? NEUTRAL_COLOR;
  }

  #occupiedAmsSlots(printer: DetailedDirectPrintPrinter): DetailedAmsSlot[] {
    return printer.ams.slots
      .filter((slot) => amsSlotOccupied(slot))
      .sort((left, right) => left.display_slot - right.display_slot);
  }

  #clearErrors(): void {
    this.#error = "";
    this.#modalError = "";
    this.#amsError = "";
    this.#plate().lastError = "";
    this.#root.querySelector("#error-modal")?.remove();
    this.#root.querySelector("#global-error-box")?.remove();
    this.#renderStatus();
  }

  #showError(error: unknown): void {
    const message = error instanceof Error ? error.message : String(error);
    this.#error = message;
    this.#modalError = message;
  }

  async #syncAms(): Promise<void> {
    const plate = this.#plate();
    const printerId = plate.selection.target_printer_id;
    if (!printerId) {
      this.#amsError = "Zuerst oben einen Drucker auswählen.";
      this.#renderSidebar();
      return;
    }
    this.#amsLoading = true;
    this.#amsError = "";
    this.#renderSidebar();
    try {
      const status = await fetchDetailedDirectPrintStatus();
      this.#printers = [...status.items];
      const printer = status.items.find((item) => item.printer_id === printerId);
      if (!printer) throw new Error("Der ausgewählte Drucker ist nicht mehr verfügbar.");
      const slots = this.#occupiedAmsSlots(printer);
      if (!slots.length) throw new Error("Keine belegten AMS-Slots erkannt.");
      this.#amsSlots.set(printerId, slots);
      this.#recolorAll();
      this.#status = `${slots.length} AMS-Slot(s) von ${printer.name} synchronisiert.`;
    } catch (error) {
      this.#amsError = error instanceof Error ? error.message : String(error);
      this.#showError(error);
    } finally {
      this.#amsLoading = false;
      this.#renderFull();
    }
  }

  #recolorAll(): void {
    for (const plate of this.#plates) {
      plate.instances = plate.instances.map((item) => ({
        ...item,
        color: this.#materialColor(this.#assignments.get(item.id) || "", plate),
      }));
    }
  }

  #removeModelColors(): void {
    this.#assignments.clear();
    for (const plate of this.#plates) {
      plate.instances = plate.instances.map((item) => ({ ...item, color: NEUTRAL_COLOR }));
      this.#invalidatePlate(plate);
    }
    this.#status = "Projektfarben entfernt. Objekte können jetzt den belegten AMS-Slots zugewiesen werden.";
    this.#renderFull();
  }

  #invalidatePlate(plate = this.#plate()): void {
    plate.stage = "prepared";
    plate.jobId = "";
    plate.lastError = "";
    plate.layers = [];
    plate.layerCount = 0;
    plate.visibleLayer = 0;
    plate.toolColors = [];
    this.#previewSupportOnly = false;
  }

  #setTool(tool: MegaGizmoMode): void {
    this.#tool = tool;
    this.#drawTool = "none";
    this.#viewport?.setGizmo(this.#center(), tool, this.#gizmoAxis());
    this.#refreshToolUi();
  }

  #setDrawTool(tool: DrawTool): void {
    this.#drawTool = this.#drawTool === tool ? "none" : tool;
    if (this.#drawTool !== "none") this.#tool = "select";
    this.#viewport?.setGizmo(this.#center(), this.#tool, this.#gizmoAxis());
    this.#status = this.#drawTool === "eraser"
      ? "Radierer aktiv: Objekt anklicken, um es zu entfernen."
      : this.#drawTool === "brush"
        ? "Pinsel aktiv: auf dem Druckbett ziehen, um einen Strich zu erzeugen."
        : "Bereit";
    this.#refreshToolUi();
    this.#renderStatus();
  }

  #setAxis(axis: AxisMode): void {
    this.#axis = axis;
    this.#viewport?.setGizmo(this.#center(), this.#tool, this.#gizmoAxis());
    this.#refreshToolUi();
  }

  #select(id: string | null, toggle: boolean, range = false): void {
    const orderedIds = this.#plate().instances.map((item) => item.id);
    const selection = nextStudioSelection(
      orderedIds,
      this.#selected,
      id,
      toggle,
      range,
      this.#selectionAnchor,
    );
    this.#selected = selection.selected;
    this.#selectionAnchor = selection.anchor;
    this.#refreshSelectionUi();
  }

  #refreshToolUi(): void {
    this.#root.querySelectorAll<HTMLButtonElement>("[data-tool]").forEach((button) => {
      button.classList.toggle("active", button.dataset.tool === this.#tool);
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-axis]").forEach((button) => {
      button.classList.toggle("active", button.dataset.axis === this.#axis);
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-draw-tool]").forEach((button) => {
      button.classList.toggle("active", button.dataset.drawTool === this.#drawTool);
    });
  }

  #refreshSelectionUi(): void {
    this.#viewport?.setSelected([...this.#selected]);
    this.#viewport?.setGizmo(this.#center(), this.#tool, this.#gizmoAxis());
    this.#renderObjectList();
    this.#renderSidebar();
    this.#renderCoordinates();
    this.#refreshActionButtons();
  }

  #refreshActionButtons(): void {
    const enabled = this.#selected.size > 0;
    for (const id of ["duplicate", "center", "flat", "bed", "delete"]) {
      const button = this.#root.querySelector<HTMLButtonElement>(`#${id}`);
      if (button) button.disabled = !enabled;
    }
  }

  #renderCoordinates(): void {
    const stage = this.#root.querySelector<HTMLElement>(".stage");
    if (!stage) return;
    stage.querySelector(".coordinate")?.remove();
    const center = this.#center();
    if (!center) return;
    const node = document.createElement("div");
    node.className = "coordinate";
    node.innerHTML = `<div class="x">X ${center[0].toFixed(2)} mm</div><div class="y">Y ${center[1].toFixed(2)} mm</div><div class="z">Z ${center[2].toFixed(2)} mm</div>`;
    stage.append(node);
  }

  #replace(changes: Map<string, MeshInstance>): void {
    const plate = this.#plate();
    plate.instances = plate.instances.map((item) => changes.get(item.id) ?? item);
    this.#invalidatePlate(plate);
    this.#viewport?.setInstances(this.#displayInstances());
    this.#viewport?.resize();
    this.#audit("objects_transformed", "info", { selected_count: this.#selected.size, object_ids: [...this.#selected] });
    this.#refreshSelectionUi();
    this.#renderStatus();
    this.#schedulePersist();
  }

  #duplicate(): void {
    const selected = this.#selectedItems();
    const copies = selected.map((item) => ({
      ...item,
      id: `copy-${this.#nextId++}`,
      name: `${item.name} Kopie`,
      position: [item.position[0] + 10, item.position[1] + 10, item.position[2]] as Vec3,
    }));
    if (!copies.length) return;
    for (let index = 0; index < copies.length; index += 1) {
      const key = this.#assignments.get(selected[index]!.id);
      if (key) this.#assignments.set(copies[index]!.id, key);
    }
    this.#plate().instances.push(...copies);
    this.#audit("objects_duplicated", "success", { count: copies.length, source_ids: selected.map((item) => item.id) });
    this.#invalidatePlate();
    this.#selected = new Set(copies.map((item) => item.id));
    this.#renderFull();
  }

  #copySelection(mode: "copy" | "cut"): void {
    const selected = this.#selectedItems();
    if (!selected.length) {
      this.#status = "Zum Kopieren oder Ausschneiden mindestens ein Objekt auswählen.";
      this.#renderStatus();
      return;
    }
    const sourcePlate = this.#plate();
    this.#clipboard = {
      mode,
      sourcePlate,
      sourcePlateId: sourcePlate.id,
      sourceIds: selected.map((item) => item.id),
      objects: selected.map((item) => ({
        instance: {
          ...item,
          position: [...item.position] as Vec3,
          rotation: [...item.rotation] as Vec3,
          scale: [...item.scale] as Vec3,
        },
        assignment: this.#assignments.get(item.id) || "",
      })),
    };
    this.#status = mode === "cut"
      ? `${selected.length} Objekt(e) zum Ausschneiden vorgemerkt. Zielplatte wählen und einfügen.`
      : `${selected.length} Objekt(e) kopiert. Zielplatte wählen und einfügen.`;
    this.#audit(mode === "cut" ? "objects_cut" : "objects_copied", "success", {
      count: selected.length,
      source_plate_id: sourcePlate.id,
      source_ids: selected.map((item) => item.id),
    });
    this.#renderStatus();
  }

  #pasteClipboard(): void {
    const clipboard = this.#clipboard;
    if (!clipboard?.objects.length) {
      this.#status = "Die Objekt-Zwischenablage ist leer.";
      this.#renderStatus();
      return;
    }
    const targetPlate = this.#plate();
    const samePlate = targetPlate === clipboard.sourcePlate;
    const pasted = clipboard.objects.map(({ instance, assignment }) => {
      const item: MeshInstance = {
        ...instance,
        id: `paste-${this.#nextId++}`,
        name: clipboard.mode === "copy" ? `${instance.name} Kopie` : instance.name,
        position: clipboard.mode === "copy" && samePlate
          ? [instance.position[0] + 10, instance.position[1] + 10, instance.position[2]] as Vec3
          : [...instance.position] as Vec3,
        rotation: [...instance.rotation] as Vec3,
        scale: [...instance.scale] as Vec3,
      };
      if (assignment) this.#assignments.set(item.id, assignment);
      return item;
    });
    if (clipboard.mode === "cut" && this.#plates.includes(clipboard.sourcePlate)) {
      const sourceIds = new Set(clipboard.sourceIds);
      clipboard.sourcePlate.instances = clipboard.sourcePlate.instances.filter((item) => !sourceIds.has(item.id));
      for (const id of sourceIds) this.#assignments.delete(id);
      this.#invalidatePlate(clipboard.sourcePlate);
    }
    targetPlate.instances.push(...pasted);
    this.#invalidatePlate(targetPlate);
    this.#selected = new Set(pasted.map((item) => item.id));
    this.#selectionAnchor = pasted[0]?.id ?? null;
    if (clipboard.mode === "cut") this.#clipboard = null;
    this.#status = `${pasted.length} Objekt(e) auf ${targetPlate.name} eingefügt.`;
    this.#audit("objects_pasted", "success", {
      count: pasted.length,
      target_plate_id: targetPlate.id,
      source_plate_id: clipboard.sourcePlateId,
      cut: clipboard.mode === "cut",
    });
    this.#renderFull();
  }

  async #exportSelectedObjects(): Promise<void> {
    const selected = this.#selectedItems().filter((item) => item.visible);
    if (!selected.length) {
      this.#status = "Zum Exportieren mindestens ein sichtbares Objekt auswählen.";
      this.#renderStatus();
      return;
    }
    const plate = this.#plate();
    const traceId = `s

[OUTPUT TRUNCATED — exceeded 100KB limit]