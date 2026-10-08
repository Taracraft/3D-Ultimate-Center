import { normalizeToolpathPalette, toolpathMaterialColor, toolpathPaletteWarning, UNKNOWN_TOOLPATH_COLOR } from "./toolpath-material-colors.js";
import { preparePaintedExport, buildPaintedExportMeshes, localExportMaterialPlan } from "./studio-painted-export.js";
import { readPlateLocalSettings, writePlateLocalSettings, reindexPlateLocalSettings } from "./studio-plate-storage.js";
import { clonePaintLayer, restoreStudioPaintState, remapPaintLayerPlates, paintEditConflict, remapObjectPaintRegions, mirrorPaintLayer } from "./studio-paint-state.js";
import { buildContinuousToolpathMeshes } from "./toolpath-ribbon-geometry.js";
import { authenticatedFetch, errorMessage, writeFrontendAudit } from "./ha-api-transport.js";
import { jobActivityStore } from "./job-activity-store.js";
import { emitSliceActivity, type SliceActivityMetrics, type SliceActivityStatus } from "./slice-activity-events.js";
import { emitStudioOperation, type StudioOperationMetrics, type StudioOperationStatus } from "./studio-operation-events.js";
import { nextStudioSelection, selectAllStudioObjects } from "./studio-selection.js";
import { createPlateSliceJob, loadSliceProcessOverrides, setBatchQueueContext, type LayerHeightRange, type SliceMaterialPlan, type SliceProcessOverrides } from "./plate-slice-api.js";
import { processOverrideValidationError } from "./nozzle-process-contract.js";
import { saveProcess } from "./studio-process-options-state.js";
import { analyzeFloatingSupportNeeds, type FloatingSupportIssue } from "./floating-support-analysis.js";
import { openSupportWarning, type SupportWarning } from "./support-warning-dialog.js";
import {
  toolpathPreviewIndex,
  toolpathSupportColor,
  toolpathSupportKind,
  toolpathSupportLabel,
  toolpathSupportStats,
} from "./toolpath-support-filter.js";
import { loadPlatePurgeTower, savePlatePurgeTower } from "./purge-tower-state.js";
import { createPrimitiveGeometry, firstLayerParameters, type PrimitiveKind } from "./primitive-geometry.js";
import { firstLayerProcessOptions } from "./first-layer-process.js";
import { ProfileApi, type StudioProfile, type StudioProfileCatalog } from "./profile-api.js";
import { bestFlatRotation, positionCenteredOnPlate, positionOnBed } from "./mesh-export.js";
import { measureMeshInstances, mirrorMeshGeometry, type StudioMirrorAxis } from "./studio-mesh-tools.js";
import { analyzeMeshGeometry, repairMeshGeometry, type MeshRepairReport } from "./studio-mesh-repair.js";
import { previewMeshPlaneSplit, type MeshPlaneSplitPreview, type MeshSplitAxis } from "./studio-mesh-split.js";
import { shellHtmlV2, type MegaUiPlateV2, type MegaUiStateV2 } from "./studio-mega-ui-v2.js";
import { StudioMegaViewport, type MegaAxis, type MegaGizmoMode } from "./studio-mega-viewport.js";
import { createPaintSession, type PaintRegion } from "./studio-mesh-paint.js";
import { composePaintLayers, refinePaintLayers } from "./studio-paint-layers.js";
import { paintMaskContains, paintMaskRuns, paintSamplingStep, type MaterialPaintMask } from "./studio-paint-mask.js";
import { refinePaintGeometry, remapPaintRegions } from "./studio-paint-refinement.js";
import type { StudioPaintMaterial, StudioPaintTool } from "./studio-paint-ui.js";
import "./studio-paint-ui.js";
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
import { filamentMaterial, filamentProfilesHtml, studioProfileBarHtml } from "./studio-profile-ui.js";
import { updateDetailsOpenState } from "./details-open-state.js";
import { preserveFilamentView } from "./filament-view-state.js";
import { filamentSyncError, filamentSyncActionsHtml } from "./studio-filament-sync.js";
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
import { ModelStateHistory } from "./model-state-history.js";
import { cloneWorkspaceSnapshot, workspaceHistorySignature } from "./studio-workspace-history.js";
import {
  createStudioProject,
  getStudioProject,
  listStudioProjects,
  saveStudioProject,
} from "./studio-project-api.js";
import {
  loadStudioWorkspace,
  saveStudioWorkspace,
  type PersistedStudioWorkspace,
} from "./studio-persistence.js";

const API_PREFIX = "/api/ultimate_3d_studio/v1/slicer";
const ACTIVE = new Set(["queued", "running", "cancelling"]);
const COLORS = ["#ff4d4d", "#202020", "#36e51e", "#2e9bff", "#ffb62e", "#b96cff", "#25d5c5", "#f56ab3"];
const NEUTRAL_COLOR = "#6b7785";

type StudioMode = "prepare" | "colors" | "preview";
type PreviewColorMode = "material" | "feature";
type PreviewFeatureKey = "outer_wall" | "inner_wall" | "overhang_wall" | "top_surface" | "bottom_surface" | "bridge" | "ironing" | "gap_infill" | "solid_infill" | "infill" | "floating_shell" | "support" | "support_interface" | "brim" | "raft" | "skirt" | "purge_tower" | "flush_waste" | "custom" | "other";
const PREVIEW_FEATURE_KEYS: readonly PreviewFeatureKey[] = ["outer_wall", "inner_wall", "overhang_wall", "top_surface", "bottom_surface", "bridge", "ironing", "gap_infill", "solid_infill", "infill", "floating_shell", "support", "support_interface", "brim", "raft", "skirt", "purge_tower", "flush_waste", "custom", "other"];
type AxisMode = "free" | "x" | "y" | "z";
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
  uid: string;
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

type StudioPaintButtonElement = HTMLElement & {
  isActive?: () => boolean;
  toggle?: () => void;
  getTool?: () => StudioPaintTool;
  getBrush?: () => { radiusMm: number; color: string; materialKey?: string; label?: string; mode: "add" | "remove" | "replace" };
  getText?: () => string;
  getTextSizePx?: () => number;
  setMaterials?: (materials: readonly StudioPaintMaterial[]) => void;
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
  paintRegions: PaintRegion[];
  paintLayers: StudioPaintLayer[];
  legacyPaintAmbiguous: boolean;
}>;
type StudioClipboard = Readonly<{
  mode: "copy" | "cut";
  sourcePlate: Plate;
  sourcePlateId: number;
  sourceIds: readonly string[];
  objects: readonly StudioClipboardEntry[];
}>;

type PaintLayerKind = "stroke" | "rectangle" | "circle" | "text";
type PaintLayerPoint = { x: number; y: number; z: number; screenX: number; screenY: number; normal?: number[] };
type StudioPaintLayer = {
  id: string;
  plateId: number;
  objectId: string;
  kind: PaintLayerKind;
  label: string;
  color: string;
  materialKey: string;
  radiusMm: number;
  mode?: "add" | "remove";
  mask?: MaterialPaintMask;
  points: PaintLayerPoint[];
  text?: string;
  textSizePx?: number;
};

type PaintHit = Readonly<{ objectId: string; triangleIndex: number; localPosition: readonly [number, number, number]; distancePx: number }>;


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

function newPlateUid(): string {
  return globalThis.crypto?.randomUUID?.() || `plate-${Date.now()}-${Math.random().toString(16).slice(2)}`;
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
    uid: newPlateUid(),
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

function variableLayerRangeAt(
  ranges: readonly LayerHeightRange[],
  z: number,
): LayerHeightRange | null {
  return ranges.find((range) => z >= range.min_z_mm && z <= range.max_z_mm) ?? null;
}

function variableLayerRangeText(range: LayerHeightRange | null): string {
  return range
    ? `Aktuell: ${range.layer_height_mm.toFixed(2)} mm · Z ${range.min_z_mm.toFixed(1)}–${range.max_z_mm.toFixed(1)} mm`
    : "Aktuell: Standardprofil";
}

function variableLayerRangesHtml(
  ranges: readonly LayerHeightRange[],
  currentZ: number,
): string {
  if (!ranges.length) return "";
  const active = variableLayerRangeAt(ranges, currentZ);
  const rows = ranges.map((range, index) => {
    const isActive = active === range;
    return `<span class="feature-chip ${isActive ? "active" : ""}" data-layer-height-range="${index}"><i style="background:${isActive ? "#54d66c" : "#7fd2f6"}"></i>Z ${range.min_z_mm.toFixed(1)}–${range.max_z_mm.toFixed(1)} · ${range.layer_height_mm.toFixed(2)} mm</span>`;
  }).join("");
  return `<div class="section"><b>Variable Schichthöhen</b><span id="preview-layer-height-range-current">${escapeHtml(variableLayerRangeText(active))}</span><div class="feature-legend" id="preview-layer-height-ranges">${rows}</div></div>`;
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

function toolpathMeshes(layers: readonly ToolpathLayer[], selectedLayer: number, toolColors: readonly string[], cumulative: boolean, colorMode: PreviewColorMode, supportOnly: boolean, visibleFeatures: ReadonlySet<PreviewFeatureKey>): MeshInstance[] {
  const previewIndex = toolpathPreviewIndex(layers);
  return buildContinuousToolpathMeshes(layers, selectedLayer, cumulative, previewIndex.layerHeightByLayer, (segment, current) => {
    const [, , , , , tool, , feature = "Modell", category = "model"] = segment;
    const supportKind = toolpathSupportKind(feature, category);
    const isSupport = supportKind !== "none";
    if (!visibleFeatures.has(previewFeatureKey(feature, category))) return null;
    if (supportOnly && !isSupport) return null;
    if (!current && !supportOnly && !historyShellFeature(feature, category)) return null;
    const verifiedMaterialColor = toolpathMaterialColor(toolColors, tool);
    const materialColor = verifiedMaterialColor ?? UNKNOWN_TOOLPATH_COLOR;
    const base = supportOnly ? toolpathSupportColor(supportKind) : colorMode === "feature" ? featurePreviewColor(feature, category) : materialColor;
    const color = current || (!supportOnly && colorMode === "material") ? base : mixColor(base, supportOnly ? "#102b27" : "#17212a", .18);
    const label = supportOnly ? toolpathSupportLabel(supportKind) : colorMode === "feature" ? feature : verifiedMaterialColor ? "Filament " + (tool + 1) : "Unbekannte Materialfarbe";
    const family = supportOnly ? supportKind : colorMode === "feature" ? category : "tool-" + tool;
    const highlight = !supportOnly && current
      ? colorMode === "material" ? materialHighlightColor(materialColor) : mixColor(base, "#ffffff", .28)
      : undefined;
    return {
      key: color + ":" + family,
      color, label, flat: supportOnly,
      ...(highlight ? { highlight } : {}),
    };
  });
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
  #catalog: StudioProfileCatalog | null = null;
  #printers: DetailedDirectPrintPrinter[] = [];
  #file: File | null = null;
  #inspection: SliceModelInspection | null = null;
  #plates: Plate[] = [newPlate(0, "Druckplatte 1", initialStudioSelection(null))];
  #activePlate = 0;
  #mode: StudioMode = "prepare";
  #previewColorMode: PreviewColorMode = "material";
  #previewCumulative = true;
  #previewSupportOnly = false;
  #previewVisibleFeatures = new Set<PreviewFeatureKey>(PREVIEW_FEATURE_KEYS);
  #previewMaterialOpen = true;
  #topCollapsed = false;
  #leftCollapsed = false;
  #rightCollapsed = false;
  #tool: MegaGizmoMode = "select";
  #axis: AxisMode = "free";
  #selected = new Set<string>();
  #profileBarOpen = true;
  #openFilamentDetailKeys = new Set<string>();
  #selectionAnchor: string | null = null;
  #assignments = new Map<string, string>();
  #clipboard: StudioClipboard | null = null;
  #modelMaterials: MaterialChoice[] = [];
  #amsSlots = new Map<string, DetailedAmsSlot[]>();
  #amsError = "";
  #amsLoading = false;
  #filamentSelectionSaving = false;
  #filamentPickerOpen = false;
  #supportWarning: SupportWarning | null = null;
  #modalError = "";
  #viewport: StudioMegaViewport | null = null;
  #paintSession = createPaintSession();
  #paintGeometryFailures = new Set<number>();
  #cancelViewportGesture: (() => void) | null = null;
  #paintLayers = new Map<number, StudioPaintLayer[]>();
  #nextPaintLayerId = 1;
  #paintLegacyAmbiguousObjectIds = new Set<string>();
  #drag: DragState | null = null;
  #purgeDrag: PurgeDragState | null = null;
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
  #historyReady = false;
  #historyReplay = false;
  readonly #history = new ModelStateHistory<PersistedStudioWorkspace>({
    clone: cloneWorkspaceSnapshot,
    signature: workspaceHistorySignature,
    maximum: 20,
  });
  #projectId = "";
  #projectName = "";
  #projectRevision = 0;
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
    emitSliceActivity({
      active: options.active !== false,
      traceId,
      jobId: jobId || undefined,
      fileName: this.#file?.name || plate.name,
      plateName: plate.name,
      plateId: plate.id,
      code,
      label,
      detail: options.detail || "",
      progress: options.progress ?? null,
      status: options.status || "info",
      metrics: options.metrics,
    });
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
    emitStudioOperation({
      active: options.active !== false,
      traceId,
      kind,
      fileName: options.fileName || this.#file?.name || this.#plate().name,
      source: options.source,
      code,
      label,
      detail: options.detail || "",
      progress: options.progress ?? null,
      status: options.status || "running",
      metrics: options.metrics,
    });
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
    this.#paintSession = createPaintSession();
    this.#paintLayers.clear();
    this.#paintLegacyAmbiguousObjectIds.clear();
    this.#clipboard = null;
    this.#projectId = "";
    this.#projectName = "";
    this.#projectRevision = 0;
    this.#modelMaterials = [];
    this.#inspection = null;
    this.#file = null;
    this.#mode = "prepare";
    this.#previewColorMode = "material";
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
    this.#cancelViewportGesture?.();
    this.#supportWarning?.cancel();
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
    if (this.#supportWarning) return;
    const target = event.target instanceof Element ? event.target : null;
    if (!target?.closest(".menubar")) this.#closeMenus();
    if (!target?.closest("input,select,textarea,[contenteditable='true']")) this.focus({ preventScroll: true });
  };

  readonly #pageHide = (): void => { this.#cancelViewportGesture?.(); void this.#persistNow(); };
  readonly #visibilityChanged = (): void => {
    if (document.visibilityState === "hidden") { this.#cancelViewportGesture?.(); void this.#persistNow(); }
  };

  readonly #keyDown = (event: KeyboardEvent): void => {
    if (this.#supportWarning || !this.isConnected || this.getClientRects().length === 0) return;
    if (event.composedPath().some((node) => node instanceof HTMLInputElement || node instanceof HTMLSelectElement || node instanceof HTMLTextAreaElement || (node instanceof HTMLElement && node.isContentEditable))) return;
    const key = event.key.toLowerCase();
    if ((event.ctrlKey || event.metaKey) && key === "z") {
      event.preventDefault();
      if (event.shiftKey) void this.#redoWorkspace(); else void this.#undoWorkspace();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && key === "y") { event.preventDefault(); void this.#redoWorkspace(); return; }
    if ((event.ctrlKey || event.metaKey) && key === "a") {
      event.preventDefault();
      const selection = selectAllStudioObjects(this.#orderedSelectionIds());
      this.#selected = selection.selected;
      this.#selectionAnchor = selection.anchor;
      this.#refreshSelectionUi();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && key === "c") { event.preventDefault(); this.#copySelection("copy"); return; }
    if ((event.ctrlKey || event.metaKey) && key === "x") { event.preventDefault(); this.#copySelection("cut"); return; }
    if ((event.ctrlKey || event.metaKey) && key === "v") { event.preventDefault(); this.#pasteClipboard(); return; }
    if ((event.ctrlKey || event.metaKey) && key === "d") { event.preventDefault(); this.#duplicate(); return; }
    if (event.key === "Delete") { event.preventDefault(); this.#remove(); return; }
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
    this.#history.reset(this.#workspaceSnapshot());
    this.#historyReady = true;
    this.#workspaceReady = true;
    this.#loading = false;
    this.#renderFull();
    void this.#activatePlateJob(this.#plate());
    void this.#loadEnvironment();
  }

  #workspaceSnapshot(): PersistedStudioWorkspace {
    const snapshot: PersistedStudioWorkspace = {
      version: 1,
      savedAt: Date.now(),
      activePlate: this.#activePlate,
      mode: this.#mode === "colors" ? "colors" : "prepare",
      nextId: this.#nextId,
      selected: [...this.#selected],
      assignments: [...this.#assignments.entries()],
      modelMaterials: this.#modelMaterials.map((item) => ({ ...item })),
      paintCompositionVersion: 1,
      paintLegacyAmbiguousObjectIds: [...this.#paintLegacyAmbiguousObjectIds],
      paintRegions: this.#plates.flatMap((plate) => this.#paintBaseRegionsForPlate(plate).map((region) => ({ ...region, plateId: plate.id, triangleIndices: [...region.triangleIndices] }))),
      plates: this.#plates.map((plate) => ({
        id: plate.id,
        uid: plate.uid,
        name: plate.name,
        width: plate.width,
        depth: plate.depth,
        localSettings: readPlateLocalSettings(plate.id),
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
      paintLayers: [...this.#paintLayers.entries()].map(([plateId, layers]) => [plateId, layers.map(clonePaintLayer)] as const),
      nextPaintLayerId: this.#nextPaintLayerId,
    };
    return snapshot;
  }

  async #restoreWorkspace(): Promise<void> {
    try {
      const snapshot = await loadStudioWorkspace();
      if (!snapshot?.plates.length) return;
      const plates: Plate[] = snapshot.plates.map((plate, index) => ({
        id: index,
        uid: plate.uid || newPlateUid(),
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
      const paintState = restoreStudioPaintState(snapshot);
      const instanceIds = new Set(plates.flatMap((plate) => plate.instances.map((item) => item.id)));
      writePlateLocalSettings(snapshot.plates.flatMap((plate, index) => plate.localSettings ? [[index, plate.localSettings] as const] : []));
      this.#plates = plates;
      this.#activePlate = Math.max(0, Math.min(snapshot.activePlate, plates.length - 1));
      this.#mode = snapshot.mode;
      this.#nextId = Math.max(1, snapshot.nextId);
      this.#assignments = new Map(snapshot.assignments.filter(([id]) => instanceIds.has(id)));
      this.#modelMaterials = snapshot.modelMaterials.map((item) => ({ ...item }));
      this.#paintSession.replace(paintState.regions);
      this.#paintLayers = paintState.layers as Map<number, StudioPaintLayer[]>;
      this.#paintLegacyAmbiguousObjectIds = paintState.legacyAmbiguousObjectIds;
      const extendedSnapshot = snapshot;
      this.#nextPaintLayerId = Math.max(1, Number(extendedSnapshot.nextPaintLayerId) || 1, ...[...this.#paintLayers.values()].flat().map((layer) => Number(String(layer.id).replace(/^paint-layer-/, "")) + 1 || 1));
      this.#selected = new Set(snapshot.selected.filter((id) => instanceIds.has(id) || id.startsWith("paint:") || id.startsWith("paint-layer:")));
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
    if (this.#historyReady && !this.#historyReplay) this.#history.checkpoint(snapshot);
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

  #snapshotWithCurrentRuntime(snapshot: PersistedStudioWorkspace): PersistedStudioWorkspace {
    const runtime = new Map(this.#plates.map((plate) => [plate.uid, plate]));
    return {
      ...cloneWorkspaceSnapshot(snapshot),
      savedAt: Date.now(),
      plates: snapshot.plates.map((plate) => {
        const current = plate.uid ? runtime.get(plate.uid) : undefined;
        const stage = current?.stage ?? "prepared";
        const jobId = current?.jobId ?? "";
        return {
          ...plate,
          stage,
          jobId,
        };
      }),
    };
  }

  async #replayHistory(snapshot: PersistedStudioWorkspace, label: string): Promise<void> {
    if (this.#plates.some((plate) => plate.stage === "slicing")) {
      this.#status = "Rückgängig/Wiederholen ist während eines laufenden Slicing-Auftrags gesperrt.";
      this.#renderStatus();
      return;
    }
    const safe = this.#snapshotWithCurrentRuntime(snapshot);
    this.#historyReplay = true;
    try {
      await saveStudioWorkspace(safe);
      await this.#restoreWorkspace();
      this.#status = label;
      this.#renderFull();
    } finally {
      this.#historyReplay = false;
    }
  }

  async #undoWorkspace(): Promise<void> {
    if (this.#plates.some((plate) => plate.stage === "slicing")) {
      this.#status = "Rückgängig/Wiederholen ist während eines laufenden Slicing-Auftrags gesperrt.";
      this.#renderStatus();
      return;
    }
    await this.#persistNow();
    const snapshot = this.#history.undo();
    if (!snapshot) {
      this.#status = "Keine frühere Modelländerung vorhanden.";
      this.#renderStatus();
      return;
    }
    await this.#replayHistory(snapshot, "Letzte Modelländerung rückgängig gemacht.");
  }

  async #redoWorkspace(): Promise<void> {
    if (this.#plates.some((plate) => plate.stage === "slicing")) {
      this.#status = "Rückgängig/Wiederholen ist während eines laufenden Slicing-Auftrags gesperrt.";
      this.#renderStatus();
      return;
    }
    await this.#persistNow();
    const snapshot = this.#history.redo();
    if (!snapshot) {
      this.#status = "Keine wiederholbare Modelländerung vorhanden.";
      this.#renderStatus();
      return;
    }
    await this.#replayHistory(snapshot, "Modelländerung wiederholt.");
  }

  async #saveHaProject(): Promise<void> {
    await this.#persistNow();
    this.#loading = true;
    this.#status = "Projekt wird revisionssicher auf Home Assistant gespeichert …";
    this.#renderStatus();
    try {
      const snapshot = this.#workspaceSnapshot();
      const fallback = this.#inspection?.filename || this.#file?.name || `Studio-Projekt ${new Date().toLocaleString("de-DE")}`;
      const saved = this.#projectId
        ? await saveStudioProject(this.#projectId, this.#projectName || fallback, this.#projectRevision, snapshot)
        : await createStudioProject(fallback, snapshot);
      this.#projectId = saved.id;
      this.#projectName = saved.name;
      this.#projectRevision = saved.revision;
      this.#status = `${saved.name} · Revision ${saved.revision} auf Home Assistant gespeichert.`;
      this.#audit("ha_project_saved", "success", { project_id: saved.id, revision: saved.revision });
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = "Projekt konnte nicht auf Home Assistant gespeichert werden.";
      this.#audit("ha_project_save_failed", "error", { error: this.#error });
    } finally {
      this.#loading = false;
      this.#renderStatus();
    }
  }

  async #openHaProject(): Promise<void> {
    this.#loading = true;
    this.#status = "HA-Projektliste wird geladen …";
    this.#renderStatus();
    try {
      const projects = await listStudioProjects();
      if (!projects.length) {
        this.#status = "Auf Home Assistant ist noch kein Studio-Projekt gespeichert.";
        return;
      }
      const modal = document.createElement("div");
      modal.className = "error-modal support-warning-modal";
      modal.innerHTML = `<section class="error-modal-panel" role="dialog" aria-modal="true" aria-labelledby="project-open-title"><header class="error-modal-head"><strong id="project-open-title">HA-Projekt öffnen</strong></header><div class="error-modal-body"><label>Projekt<select id="ha-project-choice">${projects.map((project) => `<option value="${escapeHtml(project.id)}">${escapeHtml(project.name)} · Revision ${project.revision}</option>`).join("")}</select></label><small>Das gewählte Projekt ersetzt den aktuellen lokalen Modellzustand erst nach erfolgreichem Laden.</small></div><footer class="support-warning-actions"><button id="ha-project-cancel" type="button">Abbrechen</button><button class="primary" id="ha-project-confirm" type="button">Projekt öffnen</button></footer></section>`;
      const close = (): void => modal.remove();
      modal.querySelector<HTMLButtonElement>("#ha-project-cancel")?.addEventListener("click", close);
      modal.querySelector<HTMLButtonElement>("#ha-project-confirm")?.addEventListener("click", () => {
        const projectId = modal.querySelector<HTMLSelectElement>("#ha-project-choice")?.value || "";
        close();
        void this.#loadHaProject(projectId);
      });
      this.#root.append(modal);
      this.#status = `${projects.length} HA-Projekt(e) verfügbar.`;
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = "HA-Projektliste konnte nicht geladen werden.";
    } finally {
      this.#loading = false;
      this.#renderStatus();
    }
  }

  async #loadHaProject(projectId: string): Promise<void> {
    if (!projectId) return;
    this.#loading = true;
    this.#status = "HA-Projekt wird geladen …";
    this.#renderStatus();
    try {
      const project = await getStudioProject(projectId);
      restoreStudioPaintState(project.snapshot);
      this.#historyReplay = true;
      await saveStudioWorkspace(project.snapshot);
      await this.#restoreWorkspace();
      this.#history.reset(project.snapshot);
      this.#projectId = project.id;
      this.#projectName = project.name;
      this.#projectRevision = project.revision;
      this.#status = `${project.name} · Revision ${project.revision} geladen.`;
      this.#audit("ha_project_loaded", "success", { project_id: project.id, revision: project.revision });
      this.#renderFull();
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = "HA-Projekt konnte nicht geladen werden; der lokale Zustand blieb erhalten.";
      this.#renderStatus();
    } finally {
      this.#historyReplay = false;
      this.#loading = false;
    }
  }

  #bindGcodePresets(): void {
    this.#root.querySelectorAll<HTMLSelectElement>("[data-gcode-preset]").forEach((select) => {
      select.addEventListener("change", () => {
        const slot = select.dataset.gcodePreset as "start_sound" | "end_sound" | "gcode_1" | "gcode_2";
        const plate = this.#plate();
        plate.selection = { ...plate.selection, gcode_preset_ids: { ...plate.selection.gcode_preset_ids, [slot]: select.value } };
        this.#invalidatePlate(plate);
        this.#schedulePersist();
        this.#refreshEnvironmentUi();
      });
    });
  }

  #bindProfileSelectors(): void {
    const profileBar = this.#root.querySelector<HTMLDetailsElement>(".profilebar-shell");
    profileBar?.addEventListener("toggle", () => { this.#profileBarOpen = profileBar.open; });
    this.#root.querySelectorAll<HTMLSelectElement>("[data-profile-field]").forEach((select) => {
      select.addEventListener("change", () => void this.#profileChanged(
        select.dataset.profileField as keyof StudioPlateProfileSelection,
        select.value,
      ));
    });
    this.#root.querySelector<HTMLSelectElement>("[data-material-source]")?.addEventListener("change", (event) => {
      this.#materialSourceChanged((event.currentTarget as HTMLSelectElement).value);
    });
    this.#bindGcodePresets();
    this.#bindFilamentProfilePicker();
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
    preserveFilamentView(this.#root, () => {
      const current = this.#root.querySelector<HTMLElement>(".profilebar-shell");
      if (current) {
        const template = document.createElement("template");
        template.innerHTML = studioProfileBarHtml(this.#catalog, this.#printers, this.#plate().selection, this.#plate().materialSource, this.#plate().externalFilamentProfileId, this.#profileBarOpen).trim();
        const replacement = template.content.firstElementChild;
        if (replacement) current.replaceWith(replacement);
      }
      this.#bindProfileSelectors();
      this.#viewport?.setPlate(this.#profileVisual());
      this.#viewport?.setInstances(this.#displayInstances());
      this.#renderSidebar();
      this.#renderStatus();
      this.#schedulePersist();
    });
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
      this.#recolorAll();
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
    let profilesSelectedReported = false;
    let profilesAppliedReported = false;
    let profilesGcodeReported = false;
    let summaryFeatureLabels: string[] = [];
    let totalSegments = 0;
    const reportJobState = (job: SliceJob): void => {
      const application = job.profile_application;
      if (application?.selected && !profilesSelectedReported) {
        profilesSelectedReported = true;
        this.#traceSliceActivity("profiles_selected", "Profile vollständig ausgewählt", {
          traceId,
          jobId,
          detail: `${application.process?.name || application.process?.profile_id || "Prozessprofil"} · ${application.filament_profile_count || 0} Filamentprofil(e)`,
          progress: 57,
          status: "success",
          active: true,
          metrics: { materialCount: application.filament_profile_count },
        });
      }
      if (application?.applied && !profilesAppliedReported) {
        profilesAppliedReported = true;
        this.#traceSliceActivity("profiles_applied", "Profile im nativen Slicer angewendet", {
          traceId,
          jobId,
          detail: `Prozessvertrag und ${application.material_channel_count || 0} Materialkanal/-kanäle wurden beim Materialisieren bestätigt.`,
          progress: 72,
          status: "success",
          active: true,
          metrics: { materialCount: application.material_channel_count },
        });
      }
      if (application?.gcode_confirmed && !profilesGcodeReported) {
        profilesGcodeReported = true;
        this.#traceSliceActivity("profiles_gcode_confirmed", "Profile im G-Code bestätigt", {
          traceId,
          jobId,
          detail: `${application.process?.gcode_confirmed_setting_count || 0} Prozesseinstellung(en) sowie alle Materialkanäle stimmen mit dem analysierten G-Code überein.`,
          progress: 89,
          status: "success",
          active: true,
          metrics: { materialCount: application.material_channel_count },
        });
      }
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
        plate.toolColors = normalizeToolpathPalette(summary.filament_colors);
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
      reportJobState(job);
      if (this.#plate() === plate) {
        this.#mode = "preview";
        // Preserve the user-selected view; new sessions and projects start in material mode.
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
        plate.toolColors,
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

  #externalSpool(plate = this.#plate()) {
    return this.#printers.find((printer) => printer.printer_id === plate.selection.target_printer_id)?.external_spool ?? null;
  }

  #externalFilamentChoice(plate = this.#plate()): MaterialChoice | null {
    if (!plate.externalFilamentProfileId) return null;
    const profile = profileById(this.#catalog, plate.externalFilamentProfileId);
    if (!profile || profile.kind !== "filament") return null;
    const material = filamentMaterial(profile);
    const filamentId = String(profile.payload.filament_id || profile.id).trim();
    if (!material || !filamentId) return null;
    const live = this.#externalSpool(plate);
    return {
      key: `external:${profile.id}`,
      name: live?.loaded && live.material ? `${live.material} · externe Spule` : profile.name,
      material,
      color: normalizeColor(live?.loaded && live.color ? live.color : filamentColor(profile, COLORS[0]!)),
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
    const visible = plate.instances.filter((instance) => instance.visible);
    if (!visible.length) throw new Error("Die aktive Druckplatte enthält kein sichtbares Objekt.");
    this.#materializePaintLayersForSlicing(plate);
    const visibleIds = new Set(visible.map((instance) => instance.id));
    const painted = this.#paintRegionsForPlate(plate, true).filter((region) => visibleIds.has(region.objectId) && region.triangleIndices.length > 0);

    if (plate.materialSource === "external_spool") {
      if (painted.length) throw new Error("Bemalte Flächen benötigen mehrere Materialkanäle. Eine externe Einzelspule kann keine Farbfläche drucken; bitte AMS Lite mit den gewünschten Filamenten wählen.");
      const choice = this.#externalFilamentChoice(plate);
      if (!choice) throw new Error("Für die externe Spule muss genau ein vollständiges Filamentprofil gewählt werden.");
      return {
        source: "external_spool",
        target_printer_id: targetPrinterId,
        assignments: Object.fromEntries(visible.map((item) => [item.id, 1])),
        filaments: [{ extruder: 1, name: choice.name, material: choice.material, color: choice.color, filament_id: choice.filament_id!, source: "external_spool" }],
        paintMaterialKeys: [],
        purge_tower: { enabled: false },
      };
    }

    const choices = this.#amsMaterialChoices(plate);
    if (!choices.length) throw new Error("Am Ziel-Drucker ist kein belegter AMS-Slot verfügbar. Bitte Filamente synchronisieren.");
    const originalIndexByKey = new Map(choices.map((choice, index) => [choice.key, index + 1]));
    const pending: Array<readonly [MeshInstance, number]> = [];
    const missing: string[] = [];
    for (const item of visible) {
      const key = this.#assignments.get(item.id) || "";
      const originalIndex = originalIndexByKey.get(key);
      if (!originalIndex) missing.push(item.name);
      else pending.push([item, originalIndex]);
    }
    const missingPaint = painted.filter((region) => !region.materialKey || !originalIndexByKey.has(region.materialKey));
    if (missingPaint.length) throw new Error("Mindestens ein Malbereich ist keinem aktuell belegten AMS-Filament zugeordnet. Wähle im Malwerkzeug einen geladenen AMS-Slot und male den Bereich erneut.");
    if (missing.length) {
      const names = [...new Set(missing)].slice(0, 4).join(", ");
      const suffix = missing.length > 4 ? ` und ${missing.length - 4} weitere` : "";
      throw new Error(`Nicht alle sichtbaren Objekte sind einem belegten AMS-Slot zugeordnet: ${names}${suffix}.`);
    }
    const usedOriginal = [...new Set([
      ...pending.map((entry) => entry[1]),
      ...painted.map((region) => originalIndexByKey.get(region.materialKey)!),
    ])].sort((left, right) => left - right);
    const usedChoices = usedOriginal.map((index) => choices[index - 1]!);
    const colorOwners = new Map<string, string>();
    for (const choice of usedChoices) {
      const color = normalizeColor(choice.color);
      const previous = colorOwners.get(color);
      if (previous && previous !== choice.key) throw new Error("Die verwendeten AMS-Filamente haben dieselbe gemeldete Farbe. Für bemalte Flächen muss jeder verwendete Slot eine eindeutige Farbe melden, damit die Materialzuordnung sicher bleibt.");
      colorOwners.set(color, choice.key);
    }
    const compactByOriginal = new Map(usedOriginal.map((value, index) => [value, index + 1]));
    const assignments: Record<string, number> = {};
    for (const [item, originalIndex] of pending) assignments[item.id] = compactByOriginal.get(originalIndex)!;
    const filaments: Array<SliceProjectFilament & { global_id: string; unit_id: string; slot_index: number; display_slot: number; tray_id: string; filament_id: string; source: "ams"; }> = usedChoices.map((choice, index) => ({
      extruder: index + 1, name: choice.name, material: choice.material, color: choice.color,
      global_id: choice.global_id || "", unit_id: choice.unit_id || "", slot_index: choice.slot_index ?? 0,
      display_slot: choice.display_slot ?? (choice.slot_index ?? 0) + 1, tray_id: choice.tray_id || "",
      filament_id: choice.filament_id || choice.tray_id || "", source: "ams",
    }));
    const tower = loadPlatePurgeTower(plate.id);
    const towerData = this.#purgeTowerData(plate);
    savePlatePurgeTower(plate.id, { ...tower, width_mm: towerData.width || Number(tower.width_mm ?? 35), brim_width_mm: towerData.brim || Number(tower.brim_width_mm ?? 3), position_x: towerData.x || Number(tower.position_x ?? plate.width - 40), position_y: towerData.y || Number(tower.position_y ?? plate.depth - 40) });
    return {
      source: "ams", target_printer_id: targetPrinterId, assignments, filaments,
      paintMaterialKeys: usedChoices.map((choice) => choice.key),
      purge_tower: { ...(this.#inspection?.purge_tower ?? {}), ...tower, enabled: usedChoices.length > 1 && tower.enabled !== false, width_mm: towerData.width, brim_width_mm: towerData.brim, position_x: towerData.x, position_y: towerData.y, flush_multiplier: Math.max(.1, Number(tower.flush_multiplier ?? 1)) },
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
      visibleLayerZ: plate.layers[plate.visibleLayer]?.z ?? null,
      center: this.#center(),
      profileBar: studioProfileBarHtml(this.#catalog, this.#printers, plate.selection, plate.materialSource, plate.externalFilamentProfileId, this.#profileBarOpen),
      activeNozzleDiameter: this.#selectedNozzleDiameter(),
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
        this.#paintSession = createPaintSession();
        this.#paintLayers.clear();
        this.#paintLegacyAmbiguousObjectIds.clear();
        this.#clipboard = null;
        this.#projectId = "";
        this.#projectName = "";
        this.#projectRevision = 0;
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
      const live = this.#externalSpool(plate);
      if (live?.loaded && live.color) return normalizeColor(live.color);
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

  async #syncFilaments(): Promise<void> {
    if (this.#amsLoading) return;
    const plate = this.#plate();
    const source = plate.materialSource;
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
      this.#amsSlots.set(printerId, slots);
      const syncError = filamentSyncError(source, printer.external_spool, slots.length);
      if (syncError) throw new Error(syncError);
      this.#clearErrors();
      this.#recolorAll();
      this.#status = source === "external_spool"
        ? `Externes Filament von ${printer.name} synchronisiert.`
        : `${slots.length} AMS-Slot(s) von ${printer.name} synchronisiert.`;
      this.#schedulePersist();
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
    this.#status = this.#plate().materialSource === "external_spool"
      ? "Projektfarben zurückgesetzt. Filamente synchronisieren übernimmt wieder die Farbe der externen Spule."
      : "Projektfarben zurückgesetzt. Objekte können jetzt den belegten AMS-Slots zugewiesen werden.";
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
    this.#cancelViewportGesture?.();
    this.#tool = tool;
    this.#viewport?.setGizmo(this.#center(), tool, this.#gizmoAxis());
    this.#refreshToolUi();
  }

  #setAxis(axis: AxisMode): void {
    this.#axis = axis;
    this.#viewport?.setGizmo(this.#center(), this.#tool, this.#gizmoAxis());
    this.#refreshToolUi();
  }

  #select(id: string | null, toggle: boolean, range = false): void {
    const orderedIds = this.#orderedSelectionIds();
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
  }

  #refreshSelectionUi(): void {
    this.#viewport?.setSelected(this.#plate().instances.filter((item) => this.#selected.has(item.id)).map((item) => item.id));
    this.#viewport?.setGizmo(this.#center(), this.#tool, this.#gizmoAxis());
    this.#renderObjectList();
    this.#renderSidebar();
    this.#renderCoordinates();
    this.#refreshActionButtons();
  }

  #refreshActionButtons(): void {
    const selectedModels = this.#selectedItems().length;
    const hasSelection = this.#selected.size > 0;
    const modelActions = new Set(["duplicate", "center", "flat", "bed", "mirror-x", "mirror-y", "mirror-z", "measure", "repair"]);
    for (const id of ["duplicate", "center", "flat", "bed", "mirror-x", "mirror-y", "mirror-z", "measure", "repair", "split", "delete"]) {
      const button = this.#root.querySelector<HTMLButtonElement>(`#${id}`);
      if (!button) continue;
      if (id === "delete") button.disabled = !hasSelection;
      else if (id === "split") button.disabled = selectedModels !== 1;
      else button.disabled = modelActions.has(id) ? selectedModels === 0 : !hasSelection;
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
      const sourceId = selected[index]!.id;
      const copyId = copies[index]!.id;
      if (key) this.#assignments.set(copyId, key);
      for (const region of this.#paintSession.getRegions(sourceId)) this.#paintSession.paintTriangles(copyId, region.triangleIndices, { ...region, radiusMm: 1, mode: "add" });
      const layers = this.#paintLayersForPlate().filter((layer) => layer.objectId === sourceId).map((layer) => clonePaintLayer({ ...layer, id: `paint-layer-${this.#nextPaintLayerId++}`, objectId: copyId }));
      this.#setPaintLayersForPlate(this.#plate(), [...this.#paintLayersForPlate(), ...layers]);
      if (this.#paintLegacyAmbiguousObjectIds.has(sourceId)) this.#paintLegacyAmbiguousObjectIds.add(copyId);
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
        paintRegions: this.#paintSession.getRegions(item.id).map((region) => ({ ...region, triangleIndices: [...region.triangleIndices] })),
        paintLayers: this.#paintLayersForPlate(sourcePlate).filter((layer) => layer.objectId === item.id).map(clonePaintLayer),
        legacyPaintAmbiguous: this.#paintLegacyAmbiguousObjectIds.has(item.id),
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
    const pasted = clipboard.objects.map(({ instance, assignment, paintRegions, paintLayers, legacyPaintAmbiguous }) => {
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
      for (const region of paintRegions) this.#paintSession.paintTriangles(item.id, region.triangleIndices, { ...region, radiusMm: 1, mode: "add" });
      this.#setPaintLayersForPlate(targetPlate, [...this.#paintLayersForPlate(targetPlate), ...paintLayers.map((layer) => clonePaintLayer({ ...layer, id: `paint-layer-${this.#nextPaintLayerId++}`, plateId: targetPlate.id, objectId: item.id }))]);
      if (legacyPaintAmbiguous) this.#paintLegacyAmbiguousObjectIds.add(item.id);
      return item;
    });
    if (clipboard.mode === "cut" && this.#plates.includes(clipboard.sourcePlate)) {
      const sourceIds = new Set(clipboard.sourceIds);
      clipboard.sourcePlate.instances = clipboard.sourcePlate.instances.filter((item) => !sourceIds.has(item.id));
      for (const id of sourceIds) {
        this.#assignments.delete(id);
        this.#paintSession.clear(id);
        this.#paintLegacyAmbiguousObjectIds.delete(id);
      }
      this.#setPaintLayersForPlate(clipboard.sourcePlate, this.#paintLayersForPlate(clipboard.sourcePlate).filter((layer) => !sourceIds.has(layer.objectId)));
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
    const traceId = `studio-export-${Date.now()}-${this.#nextId}`;
    const exportName = `objects-${plate.id + 1}-${plate.name.replace(/[^a-z0-9_-]+/gi, "-")}.3mf`;
    this.#operationTraceId = traceId;
    this.#error = "";
    this.#status = "Ausgewählte Objekte werden als 3MF exportiert …";
    this.#traceStudioOperation("export", "export_started", "3MF-Export gestartet", {
      traceId,
      fileName: exportName,
      source: plate.name,
      detail: `${selected.length.toLocaleString("de-DE")} sichtbare Objekt(e) werden exportiert.`,
      progress: 2,
      status: "running",
      metrics: { objectCount: selected.length },
    });
    this.#renderStatus();
    try {
      let lastTraceProgress = -10;
      const prepared = preparePaintedExport(selected, this.#paintBaseRegionsForPlate(plate), this.#paintLayersForPlate(plate), this.#paintLegacyAmbiguousObjectIds);
      const palette = localExportMaterialPlan(prepared.instances, prepared.regions, this.#assignments, this.#materialChoices(plate));
      const meshes = buildPaintedExportMeshes(prepared.instances, prepared.regions, palette.objectMaterials, palette.paintMaterials, palette.materials.length);
      const bytes = await export3mfStreamed(
        meshes,
        {
          title: `${plate.name} – Auswahl`,
          materials: palette.materials,
          buildPlateName: plate.name,
          buildPlateProfileId: plate.selection.build_plate_profile_id,
          plateWidthMm: plate.width,
          plateDepthMm: plate.depth,
        },
        (progress) => {
          const value = Math.round(progress * 100);
          this.#status = `Ausgewählte Objekte werden exportiert · ${value} %`;
          if (value >= 100 || value >= lastTraceProgress + 10) {
            lastTraceProgress = Math.min(100, Math.floor(value / 10) * 10);
            this.#traceStudioOperation("export", "export_progress", `3MF wird geschrieben · ${value} %`, {
              traceId,
              fileName: exportName,
              source: plate.name,
              detail: "Geometrie, Transformationen, Druckplatte und Farbinformationen werden in das 3MF geschrieben.",
              progress: Math.max(5, Math.min(92, value * .92)),
              status: "running",
              metrics: { objectCount: selected.length },
            });
          }
          this.#renderStatus();
        },
      );
      const file = new File([bytes], exportName, { type: "model/3mf" });
      this.#traceStudioOperation("export", "export_archive_ready", "3MF-Archiv vollständig erzeugt", {
        traceId,
        fileName: exportName,
        source: plate.name,
        detail: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
        progress: 96,
        status: "success",
        metrics: { objectCount: selected.length, outputSizeBytes: file.size },
      });
      const url = URL.createObjectURL(file);
      const link = document.createElement("a");
      link.href = url;
      link.download = file.name;
      link.style.display = "none";
      this.#root.append(link);
      link.click();
      link.remove();
      globalThis.setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.#status = `${selected.length} Objekt(e) wurden exportiert.`;
      this.#audit("objects_exported", "success", { count: selected.length, plate_id: plate.id, filename: file.name });
      this.#traceStudioOperation("export", "export_complete", "Export abgeschlossen", {
        traceId,
        fileName: file.name,
        source: plate.name,
        detail: `${selected.length.toLocaleString("de-DE")} Objekt(e) · ${(file.size / 1024 / 1024).toFixed(2)} MB`,
        progress: 100,
        status: "success",
        active: false,
        metrics: { objectCount: selected.length, outputSizeBytes: file.size },
      });
      this.#renderStatus();
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = `Objektexport fehlgeschlagen: ${this.#error}`;
      this.#audit("objects_export_failed", "error", { error: this.#error });
      this.#traceStudioOperation("export", "export_failed", "Export fehlgeschlagen", {
        traceId,
        fileName: exportName,
        source: plate.name,
        detail: this.#error,
        progress: 100,
        status: "error",
        active: false,
      });
      this.#renderFull();
    } finally {
      if (this.#operationTraceId === traceId) this.#operationTraceId = "";
    }
  }

  #remove(): void {
    const plate = this.#plate();
    const paintRows = this.#paintRowsForSelection(plate);
    const paintLayers = this.#paintLayersForPlate(plate);
    const selectedPaintLayers = [...this.#selected]
      .map((id) => id.startsWith("paint-layer:") ? Number(id.slice(12)) : Number.NaN)
      .filter((index) => Number.isInteger(index) && index >= 0 && index < paintLayers.length)
      .sort((left, right) => right - left);
    const selectedPaintRows = [...this.#selected]
      .map((id) => id.startsWith("paint:") ? Number(id.slice(6)) : Number.NaN)
      .filter((index) => Number.isInteger(index) && index >= 0 && index < paintRows.length)
      .sort((left, right) => right - left);
    const removedIds = [...this.#selected].filter((id) => plate.instances.some((item) => item.id === id));
    try {
      for (const objectId of [...selectedPaintLayers.map((index) => paintLayers[index]!.objectId), ...selectedPaintRows.map((index) => paintRows[index]!.objectId)]) {
        if (!removedIds.includes(objectId)) this.#assertPaintEditable(objectId);
      }
    } catch (error) {
      this.#status = error instanceof Error ? error.message : String(error);
      this.#renderStatus();
      return;
    }
    let removedPaintTriangles = 0;
    for (const index of selectedPaintRows) {
      const region = paintRows[index];
      if (!region) continue;
      const result = this.#paintSession.paintTriangles(region.objectId, region.triangleIndices, {
        radiusMm: 1,
        color: region.color,
        materialKey: region.materialKey,
        mode: "remove",
      });
      removedPaintTriangles += result.paintedTriangleCount;
    }
    if (selectedPaintLayers.length) {
      const nextLayers = paintLayers.filter((_, index) => !selectedPaintLayers.includes(index));
      this.#setPaintLayersForPlate(plate, nextLayers);
      this.#viewport?.setPaintRegions(this.#paintRegions());
    }
    plate.instances = plate.instances.filter((item) => !this.#selected.has(item.id));
    for (const id of removedIds) {
      this.#assignments.delete(id);
      this.#paintSession.clear(id);
      this.#paintLegacyAmbiguousObjectIds.delete(id);
    }
    this.#setPaintLayersForPlate(plate, this.#paintLayersForPlate(plate).filter((layer) => !removedIds.includes(layer.objectId)));
    this.#selected.clear();
    this.#selectionAnchor = null;
    this.#audit("objects_deleted", "success", { count: removedIds.length, object_ids: removedIds, paint_area_count: selectedPaintRows.length + selectedPaintLayers.length });
    this.#invalidatePlate(plate);
    this.#status = (selectedPaintRows.length || selectedPaintLayers.length) && !removedIds.length
      ? `Malbereich entfernt: ${(selectedPaintLayers.length + removedPaintTriangles).toLocaleString("de-DE")} Element(e).`
      : `${removedIds.length} Objekt(e) und ${selectedPaintRows.length + selectedPaintLayers.length} Malbereich(e) entfernt.`;
    this.#renderFull();
  }

  #centerSelected(): void {
    const changes = new Map<string, MeshInstance>();
    for (const item of this.#selectedItems()) {
      changes.set(item.id, {
        ...item,
        position: positionCenteredOnPlate(item.geometry, item, this.#plate().width, this.#plate().depth),
      });
    }
    this.#replace(changes);
  }

  #bed(): void {
    const changes = new Map<string, MeshInstance>();
    for (const item of this.#selectedItems()) changes.set(item.id, { ...item, position: positionOnBed(item.geometry, item) });
    this.#replace(changes);
  }

  #flat(): void {
    const changes = new Map<string, MeshInstance>();
    for (const item of this.#selectedItems()) {
      const rotation = bestFlatRotation(item.geometry, item.scale);
      changes.set(item.id, {
        ...item,
        rotation,
        position: positionOnBed(item.geometry, { ...item, rotation }),
      });
    }
    this.#replace(changes);
  }

  #mirrorSelected(axis: StudioMirrorAxis): void {
    const selected = this.#selectedItems();
    if (!selected.length) {
      this.#status = "Zum Spiegeln mindestens ein Objekt auswählen.";
      this.#renderStatus();
      return;
    }
    const changes = new Map<string, MeshInstance>();
    for (const item of selected) {
      changes.set(item.id, { ...item, geometry: mirrorMeshGeometry(item.geometry, axis) });
    }
    const coordinate = axis === "x" ? 0 : axis === "y" ? 1 : 2;
    const centers = new Map(selected.map((item) => [item.id, (item.geometry.boundsMin[coordinate] + item.geometry.boundsMax[coordinate]) / 2]));
    this.#setPaintLayersForPlate(this.#plate(), this.#paintLayersForPlate().map((layer) => centers.has(layer.objectId) ? mirrorPaintLayer(layer, axis, centers.get(layer.objectId)!) : layer));
    this.#status = `${selected.length} Objekt(e) an der ${axis.toUpperCase()}-Achse gespiegelt.`;
    this.#audit("objects_mirrored", "success", {
      axis,
      count: selected.length,
      object_ids: selected.map((item) => item.id),
    });
    this.#replace(changes);
  }

  #measureSelected(): void {
    const measurement = measureMeshInstances(this.#selectedItems().filter((item) => item.visible));
    if (!measurement) {
      this.#status = "Zum Messen mindestens ein sichtbares Objekt auswählen.";
      this.#renderStatus();
      return;
    }
    const [width, depth, height] = measurement.size;
    this.#status = `Auswahlmaß: ${width.toFixed(2)} × ${depth.toFixed(2)} × ${height.toFixed(2)} mm · ${measurement.objectCount} Objekt(e) · ${measurement.triangleCount.toLocaleString("de-DE")} Dreiecke.`;
    this.#audit("objects_measured", "success", {
      object_count: measurement.objectCount,
      triangle_count: measurement.triangleCount,
      size_mm: measurement.size,
      minimum_mm: measurement.minimum,
      maximum_mm: measurement.maximum,
    });
    this.#renderStatus();
  }

  async #inspectAndRepairSelected(): Promise<void> {
    const selected = this.#selectedItems().filter((item) => item.visible);
    if (!selected.length) {
      this.#status = "Zur Mesh-Prüfung mindestens ein sichtbares Objekt auswählen.";
      this.#renderStatus();
      return;
    }
    this.#status = `${selected.length} Mesh(es) werden ausschließlich lesend geprüft …`;
    this.#renderStatus();
    await waitForBrowserPaint();
    const reports = selected.map((item) => ({ item, report: analyzeMeshGeometry(item.geometry) }));
    const repairable = reports.reduce((sum, entry) => sum + entry.report.repairableTriangleCount, 0);
    const boundaryEdges = reports.reduce((sum, entry) => sum + entry.report.boundaryEdgeCount, 0);
    const nonManifoldEdges = reports.reduce((sum, entry) => sum + entry.report.nonManifoldEdgeCount, 0);
    if (!repairable) {
      this.#status = `Mesh-Prüfung: keine sicher entfernbaren Dreiecke · ${boundaryEdges} offene Kanten · ${nonManifoldEdges} nicht-manifold Kanten. Kantenbefunde wurden nicht verändert.`;
      this.#audit("mesh_inspection_complete", "success", {
        object_count: reports.length,
        repairable_triangles: 0,
        boundary_edges: boundaryEdges,
        non_manifold_edges: nonManifoldEdges,
      });
      this.#renderStatus();
      return;
    }
    await this.#confirmSafeMeshRepair(reports);
  }

  async #confirmSafeMeshRepair(
    reports: readonly { item: MeshInstance; report: MeshRepairReport }[],
  ): Promise<void> {
    this.#root.querySelector("#mesh-repair-modal")?.remove();
    const modal = document.createElement("div");
    modal.id = "mesh-repair-modal";
    modal.className = "error-modal support-warning-modal";
    const rows = reports.map(({ item, report }) => `<li><b>${escapeHtml(item.name)}</b> · ${report.nonFiniteTriangleCount} ungültig · ${report.zeroAreaTriangleCount} flächenlos · ${report.duplicateTriangleCount} Duplikate · ${report.boundaryEdgeCount} offene / ${report.nonManifoldEdgeCount} nicht-manifold Kanten</li>`).join("");
    modal.innerHTML = `<section class="error-modal-panel" role="dialog" aria-modal="true" aria-labelledby="mesh-repair-title"><header class="error-modal-head"><strong id="mesh-repair-title">Sichere Mesh-Reparatur prüfen</strong></header><div class="error-modal-body"><p>Entfernt werden ausschließlich Dreiecke mit nicht-endlichen Koordinaten, exakt null Fläche oder exakte Duplikate.</p><ul class="support-warning-list">${rows}</ul><p>Offene und nicht-manifold Kanten werden nur gemeldet. Löcher werden nicht automatisch geschlossen.</p></div><footer class="support-warning-actions"><button id="mesh-repair-cancel" type="button">Abbrechen</button><button class="primary" id="mesh-repair-confirm" type="button">Sichere Reparatur anwenden</button></footer></section>`;
    const close = (): void => modal.remove();
    modal.querySelector<HTMLButtonElement>("#mesh-repair-cancel")?.addEventListener("click", () => {
      close();
      this.#status = "Mesh-Reparatur abgebrochen; Geometrie blieb unverändert.";
      this.#renderStatus();
    });
    modal.querySelector<HTMLButtonElement>("#mesh-repair-confirm")?.addEventListener("click", () => {
      close();
      this.#applyMeshRepairs(reports);
    });
    this.#root.append(modal);
  }

  #applyMeshRepairs(reports: readonly { item: MeshInstance; report: MeshRepairReport }[]): void {
    const changes = new Map<string, MeshInstance>();
    const paint = new Map<string, PaintRegion[]>();
    let removed = 0;
    try {
      for (const { item } of reports) {
        if (!this.#plate().instances.includes(item)) throw new Error("Das Modell wurde seit der Prüfung verändert. Bitte erneut prüfen.");
        const result = repairMeshGeometry(item.geometry);
        if (!result.changed) continue;
        this.#assertPaintEditable(item.id);
        paint.set(item.id, remapObjectPaintRegions(this.#paintSession.getRegions(item.id), item.id, result.triangleIndexMap));
        removed += result.report.repairableTriangleCount;
        changes.set(item.id, { ...item, geometry: result.geometry });
      }
    } catch (error) {
      this.#status = error instanceof Error ? error.message : String(error);
      this.#renderStatus();
      return;
    }
    if (!changes.size) {
      this.#status = "Mesh-Reparatur nicht erforderlich; Geometrie blieb unverändert.";
      this.#renderStatus();
      return;
    }
    for (const [objectId, regions] of paint) {
      this.#paintSession.clear(objectId);
      for (const region of regions) this.#paintSession.paintTriangles(objectId, region.triangleIndices, { ...region, radiusMm: 1, mode: "add" });
    }
    this.#status = `${removed} eindeutig ungültige oder doppelte Dreiecke sicher entfernt; Bemalungen wurden mitgeführt.`;
    this.#audit("mesh_safe_repair_applied", "success", { object_count: changes.size, removed_triangles: removed, object_ids: [...changes.keys()] });
    this.#replace(changes);
  }

  #openSafeSplitDialog(): void {
    const selected = this.#selectedItems().filter((item) => item.visible);
    if (selected.length !== 1) {
      this.#status = "Zum geometrischen Teilen genau ein sichtbares Objekt auswählen.";
      this.#renderStatus();
      return;
    }
    const source = selected[0]!;
    const bounds = measureMeshInstances([source]);
    if (!bounds) return;
    this.#root.querySelector("#mesh-split-modal")?.remove();
    const modal = document.createElement("div");
    modal.id = "mesh-split-modal";
    modal.className = "error-modal support-warning-modal";
    modal.innerHTML = `<section class="error-modal-panel" role="dialog" aria-modal="true" aria-labelledby="mesh-split-title"><header class="error-modal-head"><strong id="mesh-split-title">Geometrisch sicher teilen</strong></header><div class="error-modal-body"><p>Achse und Weltposition der Trennebene festlegen. Das Quellobjekt bleibt bis zur ausdrücklichen Übernahme unverändert.</p><div class="triple"><label>Achse<select id="mesh-split-axis"><option value="x">X</option><option value="y">Y</option><option value="z">Z</option></select></label><label>Position (mm)<input id="mesh-split-plane" type="number" step="0.01" value="${((bounds.minimum[0] + bounds.maximum[0]) / 2).toFixed(2)}"></label><button id="mesh-split-preview" type="button">Teilung prüfen</button></div><div id="mesh-split-result"><small>Die Vorschau verändert das Modell nicht.</small></div></div><footer class="support-warning-actions"><button id="mesh-split-cancel" type="button">Abbrechen</button><button class="primary" id="mesh-split-confirm" type="button" disabled>Als zwei Objekte übernehmen</button></footer></section>`;
    let preview: MeshPlaneSplitPreview | null = null;
    const axisSelect = modal.querySelector<HTMLSelectElement>("#mesh-split-axis")!;
    const planeInput = modal.querySelector<HTMLInputElement>("#mesh-split-plane")!;
    const resultHost = modal.querySelector<HTMLElement>("#mesh-split-result")!;
    const confirm = modal.querySelector<HTMLButtonElement>("#mesh-split-confirm")!;
    const resetPreview = (): void => {
      preview = null;
      confirm.disabled = true;
      const axis = axisSelect.value as MeshSplitAxis;
      const index = axis === "x" ? 0 : axis === "y" ? 1 : 2;
      planeInput.value = ((bounds.minimum[index] + bounds.maximum[index]) / 2).toFixed(2);
      resultHost.innerHTML = "<small>Teilung erneut prüfen, bevor sie übernommen werden kann.</small>";
    };
    axisSelect.addEventListener("change", resetPreview);
    planeInput.addEventListener("input", () => {
      preview = null;
      confirm.disabled = true;
      resultHost.innerHTML = "<small>Position geändert · Teilung erneut prüfen.</small>";
    });
    modal.querySelector<HTMLButtonElement>("#mesh-split-preview")?.addEventListener("click", () => {
      const planeMm = Number(planeInput.value);
      if (!Number.isFinite(planeMm)) {
        resultHost.innerHTML = '<span class="error-box">Eine gültige Ebenenposition in Millimetern eingeben.</span>';
        return;
      }
      preview = previewMeshPlaneSplit(source, axisSelect.value as MeshSplitAxis, planeMm);
      confirm.disabled = !preview.canApply;
      if (!preview.canApply) {
        const reason = preview.crossingTriangleCount || preview.touchingTriangleCount
          ? `Die Ebene schneidet ${preview.crossingTriangleCount} und berührt ${preview.touchingTriangleCount} Dreieck(e). Dafür wäre eine noch nicht freigegebene Kappenbildung nötig.`
          : "Die Ebene erzeugt nicht zwei jeweils belegte Seiten.";
        resultHost.innerHTML = `<div class="error-box">${escapeHtml(reason)} Die Geometrie bleibt unverändert.</div>`;
        return;
      }
      const axis = preview.axis.toUpperCase();
      resultHost.innerHTML = `<div class="section"><b>Vorschau · zwei getrennte Ergebnisobjekte</b><div class="assignment"><span>${escapeHtml(source.name)} – ${axis}−</span><b>${preview.negativeTriangleCount.toLocaleString("de-DE")} Dreiecke</b></div><div class="assignment"><span>${escapeHtml(source.name)} – ${axis}+</span><b>${preview.positiveTriangleCount.toLocaleString("de-DE")} Dreiecke</b></div><small>Quellobjekt: ${preview.sourceTriangleCount.toLocaleString("de-DE")} Dreiecke · Ebene ${axis} ${preview.planeMm.toFixed(2)} mm.</small></div>`;
    });
    const close = (): void => modal.remove();
    modal.querySelector<HTMLButtonElement>("#mesh-split-cancel")?.addEventListener("click", () => {
      close();
      this.#status = "Geometrisches Teilen abgebrochen; Quellobjekt blieb unverändert.";
      this.#renderStatus();
    });
    confirm.addEventListener("click", () => {
      if (!preview?.canApply || !preview.negativeGeometry || !preview.positiveGeometry) return;
      close();
      this.#applyMeshSplit(source, preview);
    });
    this.#root.append(modal);
  }

  #applyMeshSplit(source: MeshInstance, preview: MeshPlaneSplitPreview): void {
    const plate = this.#plate();
    const index = plate.instances.indexOf(source);
    if (index < 0 || !preview.canApply || !preview.negativeGeometry || !preview.positiveGeometry) {
      this.#status = "Das Modell oder die Teilung hat sich geändert. Bitte erneut prüfen.";
      this.#renderStatus();
      return;
    }
    const axis = preview.axis.toUpperCase();
    const negative: MeshInstance = { ...source, id: `split-${this.#nextId}`, name: `${source.name} – ${axis}−`, geometry: preview.negativeGeometry };
    const positive: MeshInstance = { ...source, id: `split-${this.#nextId + 1}`, name: `${source.name} – ${axis}+`, geometry: preview.positiveGeometry };
    let negativePaint: PaintRegion[], positivePaint: PaintRegion[];
    try {
      this.#assertPaintEditable(source.id);
      const original = this.#paintSession.getRegions(source.id);
      negativePaint = remapObjectPaintRegions(original, negative.id, preview.negativeTriangleIndexMap);
      positivePaint = remapObjectPaintRegions(original, positive.id, preview.positiveTriangleIndexMap);
    } catch (error) {
      this.#status = error instanceof Error ? error.message : String(error);
      this.#renderStatus();
      return;
    }
    const layers = this.#paintLayersForPlate(plate);
    const originalLayers = layers.filter((layer) => layer.objectId === source.id);
    this.#setPaintLayersForPlate(plate, [
      ...layers.filter((layer) => layer.objectId !== source.id),
      ...[negative, positive].flatMap((item) => originalLayers.map((layer) => clonePaintLayer({ ...layer, id: `paint-layer-${this.#nextPaintLayerId++}`, objectId: item.id }))),
    ]);
    this.#paintSession.clear(source.id);
    for (const region of [...negativePaint, ...positivePaint]) this.#paintSession.paintTriangles(region.objectId, region.triangleIndices, { ...region, radiusMm: 1, mode: "add" });
    this.#nextId += 2;
    plate.instances.splice(index, 1, negative, positive);
    const assignment = this.#assignments.get(source.id);
    this.#assignments.delete(source.id);
    if (assignment) { this.#assignments.set(negative.id, assignment); this.#assignments.set(positive.id, assignment); }
    this.#invalidatePlate(plate);
    this.#selected = new Set([negative.id, positive.id]);
    this.#selectionAnchor = negative.id;
    this.#status = `${source.name} wurde an ${axis} ${preview.planeMm.toFixed(2)} mm geteilt. Bestehende Materialflächen und Malebenen wurden mitgeführt. Neue Schnittflächen bitte in der Materialvorschau prüfen.`;
    this.#audit("mesh_safe_plane_split_applied", "success", { source_object_id: source.id, result_object_ids: [negative.id, positive.id], axis: preview.axis, plane_mm: preview.planeMm, triangle_counts: [preview.negativeTriangleCount, preview.positiveTriangleCount] });
    this.#renderFull();
  }

  #arrange(): void {
    const plate = this.#plate();
    const items = plate.instances;
    if (!items.length) return;
    const columns = Math.ceil(Math.sqrt(items.length));
    const rows = Math.ceil(items.length / columns);
    const margin = 12;
    const gap = 8;
    const cellWidth = (plate.width - margin * 2 - gap * (columns - 1)) / columns;
    const cellDepth = (plate.depth - margin * 2 - gap * (rows - 1)) / rows;
    plate.instances = items.map((item, index) => {
      const width = Math.max(.001, item.geometry.boundsMax[0] - item.geometry.boundsMin[0]);
      const depth = Math.max(.001, item.geometry.boundsMax[1] - item.geometry.boundsMin[1]);
      const factor = Math.min(1, (cellWidth - 4) / width, (cellDepth - 4) / depth);
      const scale: Vec3 = [factor, factor, factor];
      const column = index % columns;
      const row = Math.floor(index / columns);
      const position: Vec3 = [
        margin + column * (cellWidth + gap) + cellWidth / 2,
        margin + row * (cellDepth + gap) + cellDepth / 2,
        0,
      ];
      return { ...item, scale, position: positionOnBed(item.geometry, { ...item, scale, position }) };
    });
    this.#invalidatePlate(plate);
    this.#renderFull();
  }

  #primitive(kind: PrimitiveKind): void {
    const nozzle = this.#selectedNozzleDiameter();
    if (kind === "first-layer" && nozzle === null) {
      this.#status = "Für den First-Layer-Test zuerst eine unterstützte Düse auswählen.";
      this.#renderFull();
      return;
    }
    // A full-bed calibration must not overlap existing user models.
    if (kind === "first-layer" && this.#plate().instances.length) this.#addPlate();
    const plate = this.#plate();
    const names: Record<PrimitiveKind, string> = {
      cube: "Würfel",
      cylinder: "Zylinder",
      sphere: "Kugel",
      cone: "Kegel",
      torus: "Ring",
      plate: "Platte",
      "first-layer": "First-Layer-Test",
    };
    let mesh: MeshGeometry;
    try {
      mesh = createPrimitiveGeometry(kind, plate.width, plate.depth, nozzle ?? 0.4);
    } catch (error) {
      this.#status = error instanceof Error ? error.message : String(error);
      this.#renderFull();
      return;
    }
    if (kind === "first-layer") {
      const { height, lineWidth } = firstLayerParameters(nozzle!);
      saveProcess(String(plate.id), firstLayerProcessOptions(nozzle!, loadSliceProcessOverrides()));
      this.#status = `TaraCraft First-Layer: ${height.toLocaleString("de-DE")} mm Höhe · ${lineWidth.toLocaleString("de-DE")} mm Linienbreite · diagonale Füllung · drei T-Konturen.`;
    }
    const id = `primitive-${this.#nextId++}`;
    const item: MeshInstance = {
      id,
      name: kind === "first-layer" ? "TaraCraft · First-Layer · dreifache T-Kontur" : names[kind],
      geometry: mesh,
      position: positionCenteredOnPlate(mesh, { position: [0,0,0], rotation: [0,0,0], scale: [1,1,1] }, plate.width, plate.depth),
      rotation: [0,0,0],
      scale: [1,1,1],
      color: NEUTRAL_COLOR,
      visible: true,
    };
    plate.instances.push(item);
    this.#invalidatePlate(plate);
    this.#selected = new Set([item.id]);
    this.#renderFull();
  }

  #addPlate(): void {
    const current = this.#plate();
    const id = this.#plates.length;
    this.#plates.push(newPlate(id, `Druckplatte ${id + 1}`, current.selection, current.width, current.depth, current.materialSource, current.externalFilamentProfileId));
    this.#activePlate = id;
    this.#selected.clear();
    this.#status = `Druckplatte ${id + 1} wurde hinzugefügt.`;
    this.#audit("plate_added", "success", { new_plate_index: id, plate_count: this.#plates.length });
    this.#closeMenus();
    this.#renderFull();
    void this.#activatePlateJob(this.#plate());
  }

  #removePlate(): void {
    if (this.#plates.length <= 1) return;
    try {
      reindexPlateLocalSettings(this.#plates.map((plate) => plate.id), this.#plates.filter((_, index) => index !== this.#activePlate).map((plate) => plate.id));
    } catch (error) {
      this.#status = `Druckplatte blieb erhalten: Einstellungen konnten nicht sicher umgeordnet werden. ${error instanceof Error ? error.message : String(error)}`;
      this.#renderStatus();
      return;
    }
    const removed = this.#plates.splice(this.#activePlate, 1)[0];
    for (const item of removed?.instances ?? []) {
      this.#assignments.delete(item.id);
      this.#paintSession.clear(item.id);
      this.#paintLegacyAmbiguousObjectIds.delete(item.id);
    }
    this.#plates.forEach((plate, index) => {
      plate.id = index;
      if (/^Druckplatte \d+$/.test(plate.name)) plate.name = `Druckplatte ${index + 1}`;
    });
    this.#paintLayers = remapPaintLayerPlates(this.#paintLayers, this.#plates);
    this.#activePlate = Math.max(0, Math.min(this.#activePlate, this.#plates.length - 1));
    this.#audit("plate_removed", "success", { removed_plate: removed?.name || null, plate_count: this.#plates.length });
    this.#selected.clear();
    this.#selectionAnchor = null;
    this.#closeMenus();
    this.#renderFull();
    void this.#activatePlateJob(this.#plate());
  }

  #applyBuildPlateProfile(plate: Plate, invalidate = true): void {
    const profile = profileById(this.#catalog, plate.selection.build_plate_profile_id);
    if (!profile) return;
    const converted = buildPlateProfileFromCatalog(profile);
    plate.width = converted.widthMm;
    plate.depth = converted.depthMm;
    if (invalidate) this.#invalidatePlate(plate);
  }

  #bindFilamentProfilePicker(): void {
    const picker = this.#root.querySelector<HTMLDetailsElement>("[data-filament-profile-picker]");
    if (!picker) return;
    picker.open = this.#filamentPickerOpen;
    picker.addEventListener("toggle", () => { this.#filamentPickerOpen = picker.open; });
    picker.querySelectorAll<HTMLButtonElement>("[data-filament-profile]").forEach((button) => {
      button.disabled = this.#filamentSelectionSaving;
      button.addEventListener("click", () => {
        const id = button.dataset.filamentProfile || "";
        const plate = this.#plate();
        if (plate.materialSource === "external_spool") {
          this.#externalFilamentProfileChanged(id === plate.externalFilamentProfileId ? "" : id);
        } else {
          void this.#toggleFilamentProfile(id);
        }
      });
    });
  }

  #materialSourceChanged(value: string): void {
    const plate = this.#plate();
    const source = value === "external_spool" ? "external_spool" : "ams";
    if (plate.materialSource === source) return;
    plate.materialSource = source;
    this.#invalidatePlate(plate);
    this.#recolorAll();
    this.#status = source === "ams"
      ? `${plate.name}: AMS Lite als Materialquelle gewählt.`
      : `${plate.name}: Externe Spule gewählt · ein Filamentprofil für alle Objekte erforderlich.`;
    this.#audit("material_source_changed", "info", { material_source: source });
    this.#renderFull();
    this.#schedulePersist();
  }

  #externalFilamentProfileChanged(value: string): void {
    const plate = this.#plate();
    const profile = value ? profileById(this.#catalog, value) : null;
    if (value && (!profile || profile.kind !== "filament")) {
      this.#showError(new Error("Das gewählte Profil ist kein gültiges Filamentprofil."));
      this.#renderFull();
      return;
    }
    plate.externalFilamentProfileId = value;
    this.#invalidatePlate(plate);
    this.#recolorAll();
    this.#status = value
      ? `${plate.name}: ${profile?.name || "Filament"} für die externe Spule gewählt.`
      : `${plate.name}: Filamentprofil der externen Spule entfernt.`;
    this.#audit("external_spool_filament_changed", "info", { profile_id: value || null });
    this.#renderFull();
    this.#schedulePersist();
  }

  async #profileChanged(field: keyof StudioPlateProfileSelection, value: string): Promise<void> {
    const plate = this.#plate();
    if (field === "filament_profile_ids") return;
    plate.selection = { ...plate.selection, [field]: value };
    this.#audit("profile_selection_changed", "info", { field, value });
    if (field === "build_plate_profile_id") {
      this.#applyBuildPlateProfile(plate);
      this.#status = `${plate.name}: Druckplattenprofil geändert. Modellpositionen bleiben unverändert.`;
    } else if (field === "printer_profile_id") {
      const model = String(profileById(this.#catalog, value)?.payload.model || "").toLowerCase();
      if (["a1", "h2s"].includes(model)) {
        const presets = { ...plate.selection.gcode_preset_ids };
        for (const slot of ["start_sound", "end_sound", "gcode_1", "gcode_2"] as const) {
          if (presets[slot] === undefined || /^builtin\.(a1|h2s)\./.test(presets[slot] || "")) {
            presets[slot] = `builtin.${model}.${slot}`;
          }
        }
        plate.selection = { ...plate.selection, gcode_preset_ids: presets };
      }
      const volume = printerBuildVolume(profileById(this.#catalog, value));
      this.#status = `${plate.name}: Druckerprofil aktiv · Bauraum ${volume[0]}×${volume[1]}×${volume[2]} mm.`;
      this.#invalidatePlate(plate);
    } else if (field === "nozzle_profile_id") {
      const nozzle = profileById(this.#catalog, value);
      const diameter = Number(nozzle?.payload.diameter_mm);
      const currentPrinter = profileById(this.#catalog, plate.selection.printer_profile_id);
      const configuredDiameter = Number(currentPrinter?.payload.nozzle_diameter_mm);
      if (Number.isFinite(diameter) && Number.isFinite(configuredDiameter) && Math.abs(diameter - configuredDiameter) > .000001) {
        const compatiblePrinter = uniqueStudioProfiles(this.#catalog, "printer").find((profile) => (
          String(profile.payload.model || "").trim().toLocaleLowerCase("de-DE") === "a1"
          && Math.abs(Number(profile.payload.nozzle_diameter_mm) - diameter) < .000001
        ));
        if (compatiblePrinter) plate.selection = { ...plate.selection, printer_profile_id: compatiblePrinter.id };
      }
      const validationError = processOverrideValidationError(loadSliceProcessOverrides(), diameter);
      this.#error = validationError || "";
      this.#status = validationError
        ? `${plate.name}: Düse geändert; benutzerdefinierte Prozesswerte müssen geprüft werden.`
        : `${plate.name}: Düse ${Number.isFinite(diameter) ? `${diameter.toLocaleString("de-DE")} mm` : ""} und passendes natives Maschinenprofil gewählt.`;
      this.#invalidatePlate(plate);
    } else if (field === "target_printer_id") {
      const printer = this.#printers.find((item) => item.printer_id === value);
      this.#status = printer ? `${plate.name} ist an ${printer.name} gebunden.` : `${plate.name}: Druckerbindung aufgehoben.`;
    } else {
      this.#invalidatePlate(plate);
    }
    try {
      await this.#profileApi.saveSelection(selectionPatch(plate.selection));
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    }
    this.#renderFull();
  }

  async #toggleFilamentProfile(profileId: string): Promise<void> {
    if (!profileId || this.#filamentSelectionSaving) return;
    const plate = this.#plate();
    const previous = [...plate.selection.filament_profile_ids];
    const selected = new Set(previous);
    if (selected.has(profileId)) selected.delete(profileId);
    else selected.add(profileId);
    plate.selection = { ...plate.selection, filament_profile_ids: [...selected] };
    this.#invalidatePlate(plate);
    this.#filamentSelectionSaving = true;
    this.#error = "";
    this.#status = `${plate.name}: Filamentauswahl wird gespeichert …`;
    this.#renderFull();
    try {
      const saved = await this.#profileApi.saveSelection(selectionPatch(plate.selection));
      plate.selection = {
        ...plate.selection,
        filament_profile_ids: [...saved.filament_profile_ids],
      };
      this.#status = `${plate.name}: Filamentauswahl wurde gespeichert.`;
      this.#audit("filament_profile_selection_changed", "success", {
        profile_id: profileId,
        selected: plate.selection.filament_profile_ids.includes(profileId),
      });
    } catch (error) {
      plate.selection = { ...plate.selection, filament_profile_ids: previous };
      this.#error = `Filamentauswahl konnte nicht gespeichert werden: ${error instanceof Error ? error.message : String(error)}`;
      this.#audit("filament_profile_selection_failed", "error", {
        profile_id: profileId,
        error: this.#error,
      });
    } finally {
      this.#filamentSelectionSaving = false;
      this.#renderFull();
    }
  }

  async #plateFile(materialPlan: SliceMaterialPlan, onProgress?: (progress: number) => void): Promise<File> {
    const plate = this.#plate();
    const materialIndexByKey = new Map((materialPlan.paintMaterialKeys || []).map((key, index) => [key, index]));
    const meshes = buildPaintedExportMeshes(
      plate.instances.filter((item) => item.visible),
      this.#paintRegionsForPlate(plate, true),
      new Map(Object.entries(materialPlan.assignments).map(([id, index]) => [id, Number(index) - 1])),
      materialIndexByKey,
      materialPlan.filaments.length,
    );
    const bytes = await export3mfStreamed(meshes, {
      title: plate.name, buildPlateName: plate.name, buildPlateProfileId: plate.selection.build_plate_profile_id,
      plateWidthMm: plate.width, plateDepthMm: plate.depth,
      materials: materialPlan.filaments.map((filament) => ({ name: filament.name, color: normalizeColor(filament.color) })),
    }, onProgress);
    return new File([bytes], `plate-${plate.id + 1}-${plate.name.replace(/[^a-z0-9_-]+/gi, "-")}.3mf`, { type: "model/3mf" });
  }

  async #supportDecision(issues: readonly FloatingSupportIssue[]): Promise<"cancel" | "enable" | "continue"> {
    this.#supportWarning?.cancel();
    const warning = openSupportWarning(this.#root, issues);
    this.#supportWarning = warning;
    try {
      const decision = await warning.result;
      return this.isConnected ? decision : "cancel";
    } finally {
      if (this.#supportWarning === warning) this.#supportWarning = null;
    }
  }
  async #slice(): Promise<void> {
    const plate = this.#plate();
    if (this.#loading || !plate.instances.length || plate.stage === "slicing") return;

    let handedToReconcile = false;
    let preparationActive = true;
    plate.lastError = "";
    this.#loading = true;
    this.#clearErrors();
    this.#status = `${plate.name}: Modell wird für das Slicing geprüft …`;
    this.#setSlicePreparation(true, "Modell und Druckplatte werden geprüft", 5);
    this.#traceSliceActivity("slice_started", "Slicing gestartet", {
      detail: `${plate.name} · ${plate.instances.filter((item) => item.visible).length.toLocaleString("de-DE")} sichtbare Objekt(e)`,
      progress: 3,
      status: "running",
    });
    this.#renderFull();
    await waitForBrowserPaint();

    try {
      const processPanel = this.#root.querySelector("studio-process-options-panel") as (HTMLElement & { getProcessOverrides?: () => SliceProcessOverrides }) | null;
      const processOptions = processPanel?.getProcessOverrides?.() ?? loadSliceProcessOverrides();
      const processValidationError = processOverrideValidationError(processOptions, this.#selectedNozzleDiameter());
      if (processValidationError) throw new Error(processValidationError);
      if (processOptions.support_mode === "off") {
        this.#setSlicePreparation(true, "Freischwebende Modellbereiche werden geprüft", 12);
        this.#traceSliceActivity("support_check_started", "Freischwebende Modellbereiche werden geprüft", {
          detail: "Support ist deaktiviert; das Modell wird auf Bereiche ohne tragende Geometrie geprüft.",
          progress: 8,
          status: "running",
        });
        const supportIssues = analyzeFloatingSupportNeeds(plate.instances, processOptions.support_threshold_angle ?? 30);
        if (supportIssues.length) {
          this.#traceSliceActivity("support_check_warning", "Supportbedarf erkannt", {
            detail: `${supportIssues.length.toLocaleString("de-DE")} Objekt(e) enthalten freischwebende Bereiche. Benutzerentscheidung erforderlich.`,
            progress: 10,
            status: "warning",
          });
          const decision = await this.#supportDecision(supportIssues);
          if (decision === "cancel") {
            this.#status = "Slicing wurde abgebrochen.";
            this.#traceSliceActivity("slice_cancelled_before_job", "Slicing vor Auftragserstellung abgebrochen", {
              detail: "Die Supportwarnung wurde mit Abbrechen beendet. Es wurde kein Slicerauftrag erzeugt.",
              progress: 100,
              status: "warning",
              active: false,
            });
            return;
          }
          if (decision === "enable") {
            saveProcess(String(plate.id), { ...processOptions, support_mode: "normal" });
            this.#invalidatePlate(plate);
            const panel = this.#root.querySelector("studio-process-options-panel") as (HTMLElement & { setSupportMode?: (mode: "normal" | "tree" | "off") => void }) | null;
            panel?.setSupportMode?.("normal");
            this.#status = "Normal-Support wurde aktiviert. Supporttyp und Grenzwinkel können rechts angepasst werden.";
            this.#traceSliceActivity("support_enabled", "Normal-Support wurde aktiviert", {
              detail: "Der aktuelle Slicing-Versuch endet hier, damit die Supporteinstellungen vor dem nächsten Slicing geprüft werden können.",
              progress: 100,
              status: "info",
              active: false,
            });
            return;
          }
          this.#traceSliceActivity("support_override_confirmed", "Slicing ohne Support bestätigt", {
            detail: "Die Supportwarnung wurde bewusst übergangen.",
            progress: 11,
            status: "warning",
          });
        } else {
          this.#traceSliceActivity("support_check_ok", "Supportprüfung abgeschlossen", {
            detail: "Keine freischwebenden Bereiche erkannt, die eine Benutzerentscheidung erfordern.",
            progress: 11,
            status: "success",
          });
        }
      } else {
        this.#traceSliceActivity("support_configuration_ready", "Support-Konfiguration übernommen", {
          detail: `Supportmodus: ${String(processOptions.support_mode || "aktiv")}`,
          progress: 11,
          status: "info",
        });
      }

      const materialSourceLabel = plate.materialSource === "ams" ? "AMS Lite" : "externe Spule";
      this.#setSlicePreparation(true, `${materialSourceLabel} und Materialzuordnung werden geprüft`, 18);
      this.#traceSliceActivity("material_check_started", `${materialSourceLabel} und Materialzuordnung werden geprüft`, {
        progress: 13,
        status: "running",
      });
      const materialPlan = this.#materialPlan();
      this.#traceSliceActivity("material_check_ok", `${materialSourceLabel} und Materialzuordnung gültig`, {
        detail: `${materialPlan.filaments.length.toLocaleString("de-DE")} Materialkanal/-kanäle werden an den Slicer übergeben.`,
        progress: 15,
        status: "success",
        metrics: { materialCount: materialPlan.filaments.length },
      });

      this.#setSlicePreparation(true, "Bauraum und Objektpositionen werden geprüft", 24);
      this.#traceSliceActivity("bounds_check_started", "Bauraum und Objektpositionen werden geprüft", {
        progress: 16,
        status: "running",
      });
      const buildVolume = printerBuildVolume(profileById(this.#catalog, plate.selection.printer_profile_id));
      const boundsIssues = await analyzePlateBounds(plate.instances, plate.width, plate.depth, buildVolume[2]);
      if (boundsIssues.length) {
        this.#selected = new Set(boundsIssues.map((issue) => issue.instanceId));
        this.#selectionAnchor = boundsIssues[0]?.instanceId ?? null;
        this.#mode = "prepare";
        throw new Error(plateBoundsErrorMessage(boundsIssues));
      }
      this.#traceSliceActivity("bounds_check_ok", "Bauraumprüfung erfolgreich", {
        detail: `Druckplatte ${plate.width} × ${plate.depth} mm · Bauraumhöhe ${buildVolume[2]} mm`,
        progress: 18,
        status: "success",
      });

      this.#audit("slice_started", "info", {
        gcode_preset_ids: { ...plate.selection.gcode_preset_ids },
        build_plate_profile_id: plate.selection.build_plate_profile_id,
        process_profile_id: plate.selection.process_profile_id,
        filament_profile_ids: plate.materialSource === "external_spool"
          ? [plate.externalFilamentProfileId]
          : [...plate.selection.filament_profile_ids],
        material_source: plate.materialSource,
      });
      this.#setSlicePreparation(true, "3MF wird gestreamt und komprimiert", 30);
      const compressionTotalBytes = plate.instances
        .filter((item) => item.visible)
        .reduce((sum, item) => sum + item.geometry.positions.byteLength, 0);
      const compressionStartedAt = performance.now();
      let lastCompressionTraceAt = 0;
      this.#traceSliceActivity("plate_export", "3MF wird gestreamt und komprimiert", {
        detail: "Rohgeometrie, Transformationen, Druckplatte und Materialinformationen werden verarbeitet.",
        progress: 20,
        status: "running",
        metrics: { totalBytes: compressionTotalBytes },
      });
      let lastReportedProgress = -1;
      const plateFile = await this.#plateFile(materialPlan, (progress) => {
        const percent = Math.round(progress * 100);
        const now = performance.now();
        const shouldTrace = progress >= 1 || now - lastCompressionTraceAt >= 250;
        if (shouldTrace) {
          lastCompressionTraceAt = now;
          const elapsedSeconds = Math.max(.001, (now - compressionStartedAt) / 1000);
          const processedBytes = Math.round(compressionTotalBytes * Math.max(0, Math.min(1, progress)));
          const rateBytesPerSecond = processedBytes > 0 ? processedBytes / elapsedSeconds : undefined;
          const etaSeconds = rateBytesPerSecond && rateBytesPerSecond > 0
            ? Math.max(0, (compressionTotalBytes - processedBytes) / rateBytesPerSecond)
            : undefined;
          this.#traceSliceActivity("plate_export", "3MF wird gestreamt und komprimiert", {
            detail: "Fortschritt bezieht sich auf die verarbeitete Rohgeometrie; die endgültige ZIP-Größe steht nach Abschluss fest.",
            progress: 20 + progress * 28,
            status: "running",
            metrics: { processedBytes, totalBytes: compressionTotalBytes, rateBytesPerSecond, elapsedSeconds, etaSeconds },
          });
        }
        if (percent < 100 && percent < lastReportedProgress + 2) return;
        lastReportedProgress = percent;
        this.#setSlicePreparation(true, `3MF wird komprimiert · ${percent} %`, 30 + progress * 48);
      });
      const compressionElapsedSeconds = Math.max(.001, (performance.now() - compressionStartedAt) / 1000);
      this.#traceSliceActivity("plate_export", "3MF-Erstellung und Komprimierung abgeschlossen", {
        detail: `${plateFile.name} wurde vollständig erzeugt.`,
        progress: 49,
        status: "success",
        metrics: {
          processedBytes: compressionTotalBytes,
          totalBytes: compressionTotalBytes,
          outputSizeBytes: plateFile.size,
          rateBytesPerSecond: compressionTotalBytes > 0 ? compressionTotalBytes / compressionElapsedSeconds : undefined,
          elapsedSeconds: compressionElapsedSeconds,
        },
      });

      plate.stage = "slicing";
      this.#status = `${plate.name}: Slicerauftrag wird übertragen …`;
      this.#setSlicePreparation(true, "Slicerauftrag wird übertragen", 82);
      const uploadStartedAt = performance.now();
      let lastUploadRateBytesPerSecond = 0;
      let lastUploadElapsedSeconds = 0;
      let lastUploadTraceAt = 0;
      this.#traceSliceActivity("slice_upload", "Slicerauftrag wird übertragen", {
        detail: "Die vollständige 3MF-Datei wird über den bestehenden authentifizierten Home-Assistant-Transport an den nativen Slicing Server übergeben.",
        progress: 52,
        status: "running",
        metrics: { totalBytes: plateFile.size },
      });
      this.#renderStatus();
      const job = await createPlateSliceJob(
        plateFile,
        0,
        undefined,
        materialPlan,
        {
          studio_plate_id: plate.id,
          studio_plate_display_number: plate.id + 1,
          studio_plate_name: plate.name,
          project_name: this.#inspection?.filename || this.#file?.name || "",
          target_printer_id: plate.selection.target_printer_id,
          printer_profile_id: plate.selection.printer_profile_id,
          nozzle_profile_id: plate.selection.nozzle_profile_id,
          process_profile_id: plate.selection.process_profile_id,
          gcode_preset_ids: { ...plate.selection.gcode_preset_ids },
          build_plate_profile_id: plate.selection.build_plate_profile_id,
          filament_profile_ids: plate.materialSource === "external_spool"
            ? [plate.externalFilamentProfileId]
            : [...plate.selection.filament_profile_ids],
        },
        (upload) => {
          const now = performance.now();
          lastUploadRateBytesPerSecond = upload.rateBytesPerSecond || lastUploadRateBytesPerSecond;
          lastUploadElapsedSeconds = upload.elapsedSeconds;
          if (upload.loadedBytes < upload.totalBytes && now - lastUploadTraceAt < 120) return;
          lastUploadTraceAt = now;
          const percent = Math.round(upload.ratio * 100);
          this.#setSlicePreparation(true, `Slicerauftrag wird übertragen · ${percent} %`, 82 + upload.ratio * 8);
          this.#traceSliceActivity("slice_upload", "Slicerauftrag wird übertragen", {
            detail: "Browserseitig gemessener Übertragungsfortschritt zum Home-Assistant-Endpunkt.",
            progress: 52 + upload.ratio * 3,
            status: "running",
            metrics: {
              processedBytes: upload.loadedBytes,
              totalBytes: upload.totalBytes,
              rateBytesPerSecond: upload.rateBytesPerSecond || undefined,
              elapsedSeconds: upload.elapsedSeconds,
              etaSeconds: upload.etaSeconds ?? undefined,
            },
          });
        },
      );
      const uploadElapsedSeconds = Math.max(.001, (performance.now() - uploadStartedAt) / 1000);
      this.#traceSliceActivity("slice_upload", "Slicerauftrag vollständig übertragen", {
        jobId: job.id,
        detail: "Die Ende-zu-Ende-Übertragung über Home Assistant und die Annahme durch den Slicing Server sind abgeschlossen.",
        progress: 55,
        status: "success",
        metrics: {
          processedBytes: plateFile.size,
          totalBytes: plateFile.size,
          rateBytesPerSecond: lastUploadRateBytesPerSecond || plateFile.size / uploadElapsedSeconds,
          elapsedSeconds: lastUploadElapsedSeconds || uploadElapsedSeconds,
        },
      });
      plate.jobId = job.id;
      const traceId = this.#slicePreparationId || `slice-job-${job.id}`;
      this.#sliceTraceByJob.set(job.id, traceId);
      this.#audit("slice_job_created", "success", { job_id: job.id, backend: job.backend, status: job.status, upload_size_bytes: plateFile.size });
      this.#traceSliceActivity("slice_job_created", "Slicerauftrag wurde angelegt", {
        traceId,
        jobId: job.id,
        detail: `Job ${job.id} · ${job.backend_name || "Slicing Server"} · Status ${job.status}`,
        progress: 56,
        status: "success",
        metrics: { outputSizeBytes: plateFile.size, materialCount: materialPlan.filaments.length },
      });
      this.#setSlicePreparation(false);
      preparationActive = false;
      jobActivityStore.registerSlicerJob(job);
      await this.#persistNow();
      handedToReconcile = true;
      await this.#activatePlateJob(plate);
    } catch (error) {
      plate.stage = "error";
      plate.lastError = error instanceof Error ? error.message : String(error);
      this.#audit("slice_failed", "error", { error: plate.lastError });
      this.#traceSliceActivity("slice_failed", "Slicing konnte nicht abgeschlossen werden", {
        jobId: plate.jobId || undefined,
        detail: plate.lastError,
        progress: 100,
        status: "error",
        active: false,
      });
      this.#showError(error);
    } finally {
      if (preparationActive) this.#setSlicePreparation(false);
      if (!handedToReconcile) {
        this.#loading = false;
        this.#renderAfterSliceReconcile();
      }
    }
  }

  #markPrinted(): void {
    const plate = this.#plate();
    if (plate.stage !== "sliced") return;
    plate.stage = "printed";
    this.#status = `${plate.name} als gedruckt markiert. Andere Platten bleiben unabhängig bearbeitbar.`;
    this.#audit("plate_marked_printed", "success", { job_id: plate.jobId });
    this.#renderFull();
  }

  #closeMenus(except?: HTMLDetailsElement): void {
    this.#root.querySelectorAll<HTMLDetailsElement>("details.menu[open]").forEach((menu) => {
      if (menu !== except) menu.open = false;
    });
  }

  #renderFull(): void {
    if (this.#supportWarning) { this.#deferredFullRender = true; return; }
    this.#deferredFullRender = false;
    preserveFilamentView(this.#root, () => {
      this.#root.innerHTML = shellHtmlV2(this.#ui());
      this.#bindUi();
      this.#renderSidebar();
    });
    queueMicrotask(() => this.#mountViewport());
    this.#schedulePersist();
  }

  #renderStatus(): void {
    const status = this.#root.querySelector<HTMLElement>("#status");
    if (status) status.textContent = this.#plate().lastError || this.#status;
  }

  #renderObjectList(): void {
    const host = this.#root.querySelector<HTMLElement>("#object-list");
    if (!host) return;
    const plate = this.#plate();
    const objects = plate.instances.map((instance) => (
      `<button class="object ${this.#selected.has(instance.id) ? "active" : ""}" data-object="${escapeHtml(instance.id)}"><span class="swatch" style="background:${escapeHtml(normalizeColor(instance.color))}"></span><span><b>${escapeHtml(instance.name)}</b><small>${instance.geometry.triangleCount.toLocaleString("de-DE")} Dreiecke</small></span></button>`
    )).join("");
    const materialNames = new Map(this.#paintMaterials(plate).map((material) => [material.key, material.name]));
    const paintLayers = this.#paintLayersForPlate(plate);
    const layerRows = paintLayers.map((layer, index) => {
      const object = plate.instances.find((item) => item.id === layer.objectId);
      const material = materialNames.get(layer.materialKey) || "Filament nicht zugeordnet";
      const paintId = this.#paintLayerSelectionId(index);
      const kind = layer.kind === "stroke" ? "Freihand" : layer.kind === "rectangle" ? "Rechteck" : layer.kind === "circle" ? "Kreis" : "Text";
      return `<div class="paint-area-row"><button class="object paint-area ${this.#selected.has(paintId) ? "active" : ""}" data-paint-layer-select="${paintId}" data-paint-layer="${index}"><span class="swatch" style="background:${escapeHtml(normalizeColor(layer.color))}"></span><span><b>${escapeHtml(object?.name || "Malbereich")} · ${escapeHtml(layer.label || kind)}</b><small>${kind} · ${layer.points.length.toLocaleString("de-DE")} Punkt(e) · ${escapeHtml(material)}</small></span></button><button class="paint-area-remove" data-paint-layer-remove="${index}" title="Dieses Malobjekt entfernen" aria-label="Dieses Malobjekt entfernen">×</button></div>`;
    }).join("");
    const paintRows = this.#paintRowsForSelection(plate);
    const regionRows = paintRows.map((region, index) => {
      const object = plate.instances.find((item) => item.id === region.objectId);
      const material = materialNames.get(region.materialKey) || "Filament nicht zugeordnet";
      const label = region.label || `Fläche ${index + 1}`;
      const paintId = this.#paintSelectionId(index);
      return `<div class="paint-area-row"><button class="object paint-area ${this.#selected.has(paintId) ? "active" : ""}" data-paint-select="${paintId}" data-paint-area="${index}"><span class="swatch" style="background:${escapeHtml(normalizeColor(region.color))}"></span><span><b>${escapeHtml(object?.name || "Malbereich")} · ${escapeHtml(label)}</b><small>Slicer-Fläche · ${region.triangleIndices.length.toLocaleString("de-DE")} Rasterflächen · ${escapeHtml(material)}</small></span></button><button class="paint-area-remove" data-paint-remove="${index}" title="Diese Malfläche entfernen" aria-label="Diese Malfläche entfernen">×</button></div>`;
    }).join("");
    const painted = layerRows || regionRows ? `<div class="object-section-title">Malbereich · ${paintLayers.length + paintRows.length}</div>${layerRows}${regionRows}` : "";
    host.innerHTML = objects + painted || '<div class="message"><div><b>Keine Objekte</b></div></div>';
    host.querySelectorAll<HTMLButtonElement>("[data-object]").forEach((button) => {
      button.addEventListener("click", (event) => this.#select(button.dataset.object || null, event.ctrlKey || event.metaKey, event.shiftKey));
    });
    host.querySelectorAll<HTMLButtonElement>("[data-paint-layer-select]").forEach((button) => {
      button.addEventListener("click", (event) => this.#select(button.dataset.paintLayerSelect || null, event.ctrlKey || event.metaKey, event.shiftKey));
    });
    host.querySelectorAll<HTMLButtonElement>("[data-paint-select]").forEach((button) => {
      button.addEventListener("click", (event) => this.#select(button.dataset.paintSelect || null, event.ctrlKey || event.metaKey, event.shiftKey));
    });
    host.querySelectorAll<HTMLButtonElement>("[data-paint-layer-remove]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const index = Number(button.dataset.paintLayerRemove);
        this.#selected = new Set([this.#paintLayerSelectionId(index)]);
        this.#remove();
      });
    });
    host.querySelectorAll<HTMLButtonElement>("[data-paint-remove]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const index = Number(button.dataset.paintRemove);
        const region = paintRows[index];
        if (region) this.#removePaintRegion(region);
      });
    });
  }

  #removePaintRegion(region: PaintRegion): void {
    try { this.#assertPaintEditable(region.objectId); }
    catch (error) { this.#status = error instanceof Error ? error.message : String(error); this.#renderStatus(); return; }
    const result = this.#paintSession.paintTriangles(region.objectId, region.triangleIndices, {
      radiusMm: 1,
      color: region.color,
      materialKey: region.materialKey,
      mode: "remove",
    });
    if (!result.modified) return;
    this.#invalidatePlate();
    this.#viewport?.setPaintRegions(this.#paintRegions());
    this.#status = `Malbereich entfernt: ${result.paintedTriangleCount.toLocaleString("de-DE")} Dreieck(e).`;
    this.#renderObjectList();
    this.#renderStatus();
    this.#schedulePersist(180);
  }

  #toggleChrome(target: "top" | "left" | "right"): void {
    if (target === "top") this.#topCollapsed = !this.#topCollapsed;
    if (target === "left") this.#leftCollapsed = !this.#leftCollapsed;
    if (target === "right") this.#rightCollapsed = !this.#rightCollapsed;
    const app = this.#root.querySelector<HTMLElement>(".app");
    const body = this.#root.querySelector<HTMLElement>(".body");
    app?.classList.toggle("top-collapsed", this.#topCollapsed);
    body?.classList.toggle("left-collapsed", this.#leftCollapsed);
    body?.classList.toggle("right-collapsed", this.#rightCollapsed);
    requestAnimationFrame(() => { this.#viewport?.resize(); this.#viewport?.requestRender(); });
  }

  #bindUi(): void {
    this.#root.querySelectorAll<HTMLButtonElement>("[data-chrome-toggle]").forEach((button) => button.addEventListener("click", () => this.#toggleChrome(button.dataset.chromeToggle as "top" | "left" | "right")));
    this.#root.querySelector<HTMLButtonElement>("#error-modal-close")?.addEventListener("click", () => {
      this.#modalError = "";
      this.#root.querySelector("#error-modal")?.remove();
    });
    const menus = [...this.#root.querySelectorAll<HTMLDetailsElement>("details.menu")];
    for (const menu of menus) menu.addEventListener("toggle", () => { if (menu.open) this.#closeMenus(menu); });
    this.#root.querySelectorAll<HTMLButtonElement>(".menu-pop button").forEach((button) => {
      button.addEventListener("click", () => queueMicrotask(() => this.#closeMenus()));
    });
    this.#root.querySelectorAll<HTMLSelectElement>("[data-profile-field]").forEach((select) => {
      select.addEventListener("change", () => void this.#profileChanged(
        select.dataset.profileField as keyof StudioPlateProfileSelection,
        select.value,
      ));
    });
    this.#root.querySelector<HTMLSelectElement>("[data-material-source]")?.addEventListener("change", (event) => {
      this.#materialSourceChanged((event.currentTarget as HTMLSelectElement).value);
    });
    this.#bindGcodePresets();
    this.#bindFilamentProfilePicker();
    this.#bindProcessOverrideInputs();
    this.#root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((button) => {
      button.classList.toggle("active", button.dataset.mode === this.#mode);
      button.addEventListener("click", () => {
        this.#mode = button.dataset.mode as StudioMode;
        this.#root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((item) => item.classList.toggle("active", item.dataset.mode === this.#mode));
        this.#viewport?.setPreviewMode(this.#mode === "preview");
        this.#viewport?.setInstances(this.#displayInstances());
        this.#viewport?.resize();
        this.#renderSidebar();
      });
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-tool]").forEach((button) => {
      button.classList.toggle("active", button.dataset.tool === this.#tool);
      button.addEventListener("click", () => this.#setTool(button.dataset.tool as MegaGizmoMode));
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-axis]").forEach((button) => {
      button.classList.toggle("active", button.dataset.axis === this.#axis);
      button.addEventListener("click", () => this.#setAxis(button.dataset.axis as AxisMode));
    });
    this.#root.querySelectorAll<HTMLElement>("[data-plate]").forEach((card) => {
      card.addEventListener("click", (event) => {
        if ((event.target as HTMLElement).closest("[data-remove-plate]")) return;
        this.#activePlate = Number(card.dataset.plate);
        this.#selected.clear();
        this.#selectionAnchor = null;
        this.#error = "";
        this.#renderFull();
        void this.#activatePlateJob(this.#plate());
      });
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-remove-plate]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        this.#activePlate = Number(button.dataset.removePlate);
        this.#removePlate();
      });
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='add-plate']").forEach((button) => button.addEventListener("click", () => this.#addPlate()));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='remove-active-plate']").forEach((button) => button.addEventListener("click", () => this.#removePlate()));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-source]").forEach((button) => {
      button.addEventListener("click", () => this.dispatchEvent(new CustomEvent<WorkspaceSourceRequest>(
        "workspace-source-request",
        {
          detail: { target: "slicer", source: button.dataset.source as WorkspaceSourceRequest["source"] },
          bubbles: true,
          composed: true,
        },
      )));
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-primitive]").forEach((button) => {
      button.addEventListener("click", () => this.#primitive(button.dataset.primitive as PrimitiveKind));
    });
    const on = (id: string, action: () => void): void => {
      this.#root.querySelector<HTMLButtonElement>(`#${id}`)?.addEventListener("click", action);
    };
    on("slice", () => void this.#slice());
    on("project-save", () => void this.#saveHaProject());
    on("project-open", () => void this.#openHaProject());
    on("undo", () => void this.#undoWorkspace());
    on("redo", () => void this.#redoWorkspace());
    on("duplicate", () => this.#duplicate());
    on("menu-duplicate", () => this.#duplicate());
    on("menu-copy", () => this.#copySelection("copy"));
    on("menu-cut", () => this.#copySelection("cut"));
    on("menu-paste", () => this.#pasteClipboard());
    on("delete", () => this.#remove());
    on("menu-delete", () => this.#remove());
    on("center", () => this.#centerSelected());
    on("menu-center", () => this.#centerSelected());
    on("flat", () => this.#flat());
    on("menu-flat", () => this.#flat());
    on("bed", () => this.#bed());
    on("menu-bed", () => this.#bed());
    on("mirror-x", () => this.#mirrorSelected("x"));
    on("mirror-y", () => this.#mirrorSelected("y"));
    on("mirror-z", () => this.#mirrorSelected("z"));
    on("measure", () => this.#measureSelected());
    on("repair", () => void this.#inspectAndRepairSelected());
    on("split", () => this.#openSafeSplitDialog());
    on("menu-mirror-x", () => this.#mirrorSelected("x"));
    on("menu-mirror-y", () => this.#mirrorSelected("y"));
    on("menu-mirror-z", () => this.#mirrorSelected("z"));
    on("menu-measure", () => this.#measureSelected());
    on("menu-repair", () => void this.#inspectAndRepairSelected());
    on("menu-split", () => this.#openSafeSplitDialog());
    on("arrange", () => this.#arrange());
    on("menu-arrange", () => this.#arrange());
    on("select-all", () => {
      const selection = selectAllStudioObjects(this.#orderedSelectionIds());
      this.#selected = selection.selected;
      this.#selectionAnchor = selection.anchor;
      this.#refreshSelectionUi();
    });
    on("clear-selection", () => {
      this.#selected.clear();
      this.#selectionAnchor = null;
      this.#refreshSelectionUi();
    });
    on("frame-all", () => this.#viewport?.frameAll());
    on("view-prepare", () => { this.#mode = "prepare"; this.#viewport?.setPreviewMode(false); this.#viewport?.setInstances(this.#displayInstances()); this.#renderSidebar(); });
    on("view-colors", () => { this.#mode = "colors"; this.#viewport?.setPreviewMode(false); this.#viewport?.setInstances(this.#displayInstances()); this.#renderSidebar(); });
    on("view-preview", () => { this.#mode = "preview"; this.#viewport?.setPreviewMode(true); this.#viewport?.setInstances(this.#displayInstances()); this.#viewport?.frameAll(); this.#renderSidebar(); });
    const input = this.#root.querySelector<HTMLInputElement>("#local-file");
    on("local-open", () => input?.click());
    on("object-import", () => input?.click());
    on("object-export", () => void this.#exportSelectedObjects());
    input?.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) this.file = file;
    });
  }

  #paintButton(): StudioPaintButtonElement | null {
    return this.#root.querySelector<StudioPaintButtonElement>("studio-paint-tools");
  }

  #paintBaseRegionsForPlate(plate: Plate): readonly PaintRegion[] {
    return plate.instances.flatMap((instance) => this.#paintSession.getRegions(instance.id));
  }

  #assertPaintEditable(objectId: string): void {
    const conflict = paintEditConflict(objectId, this.#paintLegacyAmbiguousObjectIds);
    if (conflict) throw new Error(conflict);
  }

  #paintRegions(): readonly PaintRegion[] {
    return this.#paintRegionsForPlate(this.#plate());
  }

  #paintRegionsForPlate(plate: Plate, forExport = false): readonly PaintRegion[] {
    const base = this.#paintBaseRegionsForPlate(plate);
    const legacyIds = this.#paintLegacyAmbiguousObjectIds;
    const normal = plate.instances.filter((instance) => !legacyIds.has(instance.id));
    const legacy = plate.instances.filter((instance) => legacyIds.has(instance.id));
    const layers = this.#paintLayersForPlate(plate);
    const modernRegions = this.#paintGeometryFailures.has(plate.id) && !forExport
      ? base.filter((region) => !legacyIds.has(region.objectId))
      : composePaintLayers(normal, base, layers);
    // Old ambiguous exports used only rasterized layers, always in add mode. Preserve that
    // contract without overwriting the saved base or another plate's paint.
    const legacyRegions = forExport
      ? composePaintLayers(legacy, [], layers, { legacy: true })
      : base.filter((region) => legacyIds.has(region.objectId));
    return [...modernRegions, ...legacyRegions];
  }

  #paintLayersForPlate(plate = this.#plate()): StudioPaintLayer[] {
    return this.#paintLayers.get(plate.id) || [];
  }

  #setPaintLayersForPlate(plate: Plate, layers: StudioPaintLayer[]): void {
    if (layers.length) this.#paintLayers.set(plate.id, layers);
    else this.#paintLayers.delete(plate.id);
  }

  #paintSelectionId(index: number): string {
    return `paint:${index}`;
  }

  #paintLayerSelectionId(index: number): string {
    return `paint-layer:${index}`;
  }

  #paintRowsForSelection(plate = this.#plate()): readonly PaintRegion[] {
    return this.#paintBaseRegionsForPlate(plate).filter((region) => region.triangleIndices.length > 0);
  }

  #orderedSelectionIds(plate = this.#plate()): string[] {
    return [
      ...plate.instances.map((item) => item.id),
      ...this.#paintLayersForPlate(plate).map((_, index) => this.#paintLayerSelectionId(index)),
      ...this.#paintRowsForSelection(plate).map((_, index) => this.#paintSelectionId(index)),
    ];
  }

  #createPaintLayer(plate: Plate, objectId: string, kind: PaintLayerKind, brush: ReturnType<NonNullable<StudioPaintButtonElement["getBrush"]>>, label: string, options: { text?: string; textSizePx?: number } = {}): StudioPaintLayer {
    const layer: StudioPaintLayer = {
      id: `paint-layer-${this.#nextPaintLayerId++}`,
      plateId: plate.id,
      objectId,
      kind,
      label,
      color: normalizeColor(brush.color),
      materialKey: String(brush.materialKey || ""),
      radiusMm: Math.max(.05, Number(brush.radiusMm) || 1),
      mode: brush.mode === "remove" ? "remove" : "add",
      points: [],
      ...(options.text ? { text: options.text } : {}),
      ...(options.textSizePx ? { textSizePx: options.textSizePx } : {}),
    };
    // Provisional gestures are not persisted until geometry and material composition succeed.
    return layer;
  }

  #materializePaintLayersForSlicing(plate: Plate): void {
    const layers = this.#paintLayersForPlate(plate).filter((layer) => layer.points.length > 0 && !this.#paintLegacyAmbiguousObjectIds.has(layer.objectId));
    this.#paintGeometryFailures.add(plate.id);
    let base = this.#plates.flatMap((item) => this.#paintBaseRegionsForPlate(item));
    let changed = false;
    const instances = plate.instances.map((instance) => {
      if (this.#paintLegacyAmbiguousObjectIds.has(instance.id)) return instance;
      const scale = Math.max(...instance.scale.map((value) => Math.abs(value)), .01);
      const refined = refinePaintLayers(instance.id, instance.geometry, base, layers, .35 / scale);
      if (!refined.changed) return instance;
      base = [...refined.regions];
      changed = true;
      return { ...instance, geometry: geometry(refined.positions) };
    });
    // Complete composition before committing either half of the geometry/reference pair.
    // Invalid material references and budget failures therefore leave the model untouched.
    composePaintLayers(instances.filter((instance) => !this.#paintLegacyAmbiguousObjectIds.has(instance.id)), base, layers);
    if (changed) {
      plate.instances = instances;
      this.#paintSession.replace(base);
    }
    this.#paintGeometryFailures.delete(plate.id);
  }

  #paintMaterials(plate = this.#plate()): readonly StudioPaintMaterial[] {
    return this.#materialChoices(plate)
      .filter((choice) => choice.source === "ams" || choice.source === "external_spool")
      .map((choice) => ({ key: choice.key, name: `${choice.name} · ${choice.material}`, color: choice.color }));
  }

  #mountViewport(): void {
    this.#cancelViewportGesture?.();
    const canvas = this.#root.querySelector<HTMLCanvasElement>("canvas");
    const shapePreviewCanvas = this.#root.querySelector<HTMLCanvasElement>("canvas.paint-shape-preview");
    if (!canvas) return;
    let paintStroke: { pointerId: number; lastX: number; lastY: number; layer: StudioPaintLayer } | null = null;
    let remainingPickWork = 20_000_000;
    const pickPaint = (clientX: number, clientY: number): PaintHit | null => {
      remainingPickWork -= this.#plate().instances.filter((item) => item.visible).reduce((sum, item) => sum + item.geometry.triangleCount, 0);
      if (remainingPickWork < 0) throw new Error("Der Malvorgang überschreitet das interaktive Rechenbudget. Bitte einen kleineren Bereich oder ein einfacheres Modell verwenden.");
      return this.#viewport?.pickPaintPoint(clientX, clientY) ?? null;
    };
    const captureMask = (objectId: string, kind: MaterialPaintMask["kind"], left: number, top: number, right: number, bottom: number): MaterialPaintMask => {
      const rect = canvas.getBoundingClientRect();
      const matrix = this.#viewport?.getPaintProjection(objectId);
      if (!matrix || rect.width <= 0 || rect.height <= 0 || right <= left || bottom <= top) throw new Error("Die Malform benötigt eine sichtbare Fläche mit Breite und Höhe.");
      return { kind, matrix: [...matrix], left: (left - rect.left) / rect.width, top: (top - rect.top) / rect.height, right: (right - rect.left) / rect.width, bottom: (bottom - rect.top) / rect.height };
    };
    const sampleStepFor = (objectId: string, radiusMm: number, point: readonly number[]): number => {
      const matrix = this.#viewport?.getPaintProjection(objectId);
      const rect = canvas.getBoundingClientRect();
      if (!matrix) throw new Error("Die Malfläche ist nicht mehr verfügbar.");
      return paintSamplingStep(matrix, point, radiusMm, rect.width, rect.height);
    };
    const clientPointForLayer = (point: PaintLayerPoint): readonly [number, number] => {
      const rect = canvas.getBoundingClientRect();
      return [rect.left + point.screenX * rect.width, rect.top + point.screenY * rect.height];
    };
    const drawPaintLayers = (): void => {
      const context = shapePreviewCanvas?.getContext("2d") ?? null;
      if (!context || !shapePreviewCanvas) return;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / Math.max(1, rect.width);
      const scaleY = canvas.height / Math.max(1, rect.height);
      for (const layer of paintStroke ? [paintStroke.layer] : []) {
        if (!layer.points.length) continue;
        context.save();
        context.strokeStyle = layer.color;
        context.fillStyle = layer.color;
        context.globalAlpha = layer.kind === "text" ? .9 : .78;
        context.lineWidth = Math.max(1.5, (layer.kind === "stroke" ? layer.radiusMm : Math.max(1, layer.radiusMm * .55)) * Math.min(scaleX, scaleY));
        context.lineCap = "round";
        context.lineJoin = "round";
        context.shadowColor = "#000000";
        context.shadowBlur = Math.max(1, Math.min(scaleX, scaleY) * 1.5);
        if (layer.kind === "stroke") {
          context.beginPath();
          layer.points.forEach((point, index) => {
            const [clientX, clientY] = clientPointForLayer(point);
            const x = (clientX - rect.left) * scaleX;
            const y = (clientY - rect.top) * scaleY;
            if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
          });
          context.stroke();
        } else {
          const dot = Math.max(1.3, context.lineWidth * .45);
          for (const point of layer.points) {
            const [clientX, clientY] = clientPointForLayer(point);
            context.beginPath();
            context.arc((clientX - rect.left) * scaleX, (clientY - rect.top) * scaleY, dot, 0, Math.PI * 2);
            context.fill();
          }
        }
        context.restore();
      }
    };
    const clearShapePreview = (): void => {
      const context = shapePreviewCanvas?.getContext("2d") ?? null;
      if (!context || !shapePreviewCanvas) return;
      shapePreviewCanvas.width = canvas.width;
      shapePreviewCanvas.height = canvas.height;
      context.clearRect(0, 0, shapePreviewCanvas.width, shapePreviewCanvas.height);
      drawPaintLayers();
    };
    const pointFromHit = (hit: PaintHit | null, clientX: number, clientY: number): PaintLayerPoint | null => {
      if (!hit) return null;
      const rect = canvas.getBoundingClientRect();
      const mesh = this.#plate().instances.find((instance) => instance.id === hit.objectId)?.geometry;
      if (!mesh || !Number.isInteger(hit.triangleIndex) || hit.triangleIndex < 0 || hit.triangleIndex >= mesh.triangleCount) return null;
      const p = mesh.positions, base = hit.triangleIndex * 9;
      const ax = p[base + 3]! - p[base]!, ay = p[base + 4]! - p[base + 1]!, az = p[base + 5]! - p[base + 2]!;
      const bx = p[base + 6]! - p[base]!, by = p[base + 7]! - p[base + 1]!, bz = p[base + 8]! - p[base + 2]!;
      const normal = [ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx], length = Math.hypot(...normal);
      if (!Number.isFinite(length) || length < 1e-8) return null;
      return {
        x: hit.localPosition[0],
        y: hit.localPosition[1],
        z: hit.localPosition[2],
        screenX: Math.max(0, Math.min(1, (clientX - rect.left) / Math.max(1, rect.width))),
        screenY: Math.max(0, Math.min(1, (clientY - rect.top) / Math.max(1, rect.height))),
        normal: normal.map((value) => value / length),
      };
    };
    const addPointToLayer = (layer: StudioPaintLayer, hit: PaintHit | null, clientX: number, clientY: number): boolean => {
      if (!hit || hit.objectId !== layer.objectId) return false;
      const point = pointFromHit(hit, clientX, clientY);
      if (!point) return false;
      const previous = layer.points[layer.points.length - 1];
      if (layer.points.length >= 50_000) throw new Error("Der Malbereich überschreitet 50.000 Punkte. Die laufende Geste wurde verworfen.");
      if (previous && Math.hypot(previous.x - point.x, previous.y - point.y, previous.z - point.z) < Math.max(.001, layer.radiusMm * .08)) return false;
      layer.points.push(point);
      return true;
    };
    const sampleLayerPoints = (layer: StudioPaintLayer, points: readonly (readonly [number, number])[]): number => {
      let added = 0;
      const seen = new Set<string>();
      for (const [clientX, clientY] of points) {
        const hit = pickPaint(clientX, clientY);
        if (!hit || hit.objectId !== layer.objectId) continue;
        const key = Math.round(clientX * 2) + ":" + Math.round(clientY * 2);
        if (seen.has(key)) continue;
        seen.add(key);
        if (addPointToLayer(layer, hit, clientX, clientY)) added += 1;
      }
      return added;
    };
    const drawTextPreview = (text: string, fontSizeCssPx: number, clientX: number, baselineClientY: number): void => {
      const context = shapePreviewCanvas?.getContext("2d") ?? null;
      if (!context || !shapePreviewCanvas || !text.trim()) return;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / Math.max(1, rect.width);
      const scaleY = canvas.height / Math.max(1, rect.height);
      clearShapePreview();
      context.save();
      context.font = "700 " + Math.max(8, fontSizeCssPx * Math.min(scaleX, scaleY)) + "px Inter,Segoe UI,sans-serif";
      context.fillStyle = this.#paintButton()?.getBrush?.().color || "#ffd36a";
      context.globalAlpha = .82;
      context.shadowColor = "#000000"; context.shadowBlur = Math.max(2, scaleX * 2);
      context.fillText(text, (clientX - rect.left) * scaleX, (baselineClientY - rect.top) * scaleY);
      context.restore();
    };
    const drawShapePreview = (shape: "rectangle" | "circle" | "line", startX: number, startY: number, endX: number, endY: number): void => {
      const context = shapePreviewCanvas?.getContext("2d") ?? null;
      if (!context || !shapePreviewCanvas) return;
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / Math.max(1, rect.width);
      const scaleY = canvas.height / Math.max(1, rect.height);
      clearShapePreview();
      const x = (startX - rect.left) * scaleX;
      const y = (startY - rect.top) * scaleY;
      const width = (endX - startX) * scaleX;
      const height = (endY - startY) * scaleY;
      const brush = this.#paintButton()?.getBrush?.();
      context.save();
      context.strokeStyle = brush?.color || "#ffd36a";
      context.lineWidth = Math.max(2, Math.min(scaleX, scaleY) * 2);
      context.setLineDash([Math.max(5, scaleX * 5), Math.max(4, scaleX * 3)]);
      context.lineDashOffset = 0;
      context.shadowColor = "#000000";
      context.shadowBlur = Math.max(2, scaleX * 2);
      context.beginPath();
      if (shape === "line") { context.moveTo(x, y); context.lineTo(x + width, y + height); }
      else if (shape === "rectangle") context.rect(x, y, width, height);
      else context.ellipse(x + width / 2, y + height / 2, Math.max(1, Math.abs(width) / 2), Math.max(1, Math.abs(height) / 2), 0, 0, Math.PI * 2);
      context.stroke();
      context.restore();
    };
    this.#viewport?.dispose();
    try { this.#materializePaintLayersForSlicing(this.#plate()); }
    catch (error) { this.#status = error instanceof Error ? error.message : String(error); this.#renderStatus(); }
    this.#viewport = new StudioMegaViewport(canvas, this.#profileVisual());
    this.#viewport.setPreviewMode(this.#mode === "preview");
    this.#viewport.setInstances(this.#displayInstances());
    this.#viewport.setSelected(this.#plate().instances.filter((item) => this.#selected.has(item.id)).map((item) => item.id));
    this.#viewport.setGizmo(this.#center(), this.#tool, this.#gizmoAxis());
    this.#viewport.frameAll();
    const paintBtn = this.#paintButton();
    paintBtn?.setMaterials?.(this.#paintMaterials());
    const syncPaintMode = (): void => {
      this.#cancelViewportGesture?.();
      const active = Boolean(paintBtn?.isActive?.()); canvas.classList.toggle("paint-mode", active);
      const toggle = this.#root.querySelector<HTMLButtonElement>("#paint-toggle");
      if (toggle) { toggle.classList.toggle("active", active); toggle.textContent = active ? "✋ Malen AUS" : "🎨 Malen AN"; }
      this.#viewport?.setPaintRegions(this.#paintRegions());
    };
    paintBtn?.addEventListener("studio-paint-change", syncPaintMode);
    this.#root.querySelector<HTMLButtonElement>("#paint-toggle")?.addEventListener("click", () => paintBtn?.toggle?.());
    syncPaintMode();
    clearShapePreview();
    const mountedViewport = this.#viewport;
    requestAnimationFrame(() => {
      if (this.#viewport !== mountedViewport) return;
      mountedViewport.resize();
      mountedViewport.frameAll();
      requestAnimationFrame(() => {
        if (this.#viewport !== mountedViewport) return;
        mountedViewport.resize();
        mountedViewport.requestRender();
      });
    });
    let down: { x: number; y: number; id: number } | null = null;
    let selectionFrame: { pointerId: number; startX: number; startY: number; initial: Set<string> } | null = null;
    let paintShape: { pointerId: number; objectId: string; startX: number; startY: number; localPoint: readonly number[]; tool: "rectangle" | "circle" | "line" } | null = null;
    const failPaint = (error: unknown): void => {
      paintStroke = null;
      paintShape = null;
      clearShapePreview();
      this.#viewport?.setSelected(this.#plate().instances.filter((item) => this.#selected.has(item.id)).map((item) => item.id));
      this.#status = error instanceof Error ? error.message : String(error);
      this.#renderStatus();
    };
    const refinePaintResolution = (layer: StudioPaintLayer): boolean => {
      if (!layer.points.length) return false;
      const plate = this.#plate(), previousLayers = this.#paintLayersForPlate(plate);
      let committed = false;
      try {
        this.#assertPaintEditable(layer.objectId);
        if (this.#historyReady && !this.#historyReplay) this.#history.checkpoint(this.#workspaceSnapshot());
        this.#setPaintLayersForPlate(plate, [...previousLayers, layer]);
        this.#materializePaintLayersForSlicing(plate);
        committed = true;
        this.#invalidatePlate(plate);
        this.#selected = new Set([this.#paintLayerSelectionId(previousLayers.length)]);
        this.#selectionAnchor = [...this.#selected][0] ?? null;
        this.#viewport?.setInstances(this.#displayInstances());
        this.#viewport?.setPaintRegions(this.#paintRegions());
        this.#renderObjectList();
        this.#schedulePersist(350);
        return true;
      } catch (error) {
        if (!committed) this.#setPaintLayersForPlate(plate, previousLayers);
        this.#paintGeometryFailures.delete(plate.id);
        failPaint(error);
        if (committed) this.#schedulePersist(350);
        return false;
      }
    };
    const applyPaint = (event: Pick<PointerEvent, "clientX" | "clientY">): boolean => {
      const hit = pickPaint(event.clientX, event.clientY);
      const instance = hit ? this.#plate().instances.find((item) => item.id === hit.objectId) ?? null : null;
      if (!hit || !instance) { this.#status = "Malen: Kein Objekt unter dem Zeiger."; this.#renderStatus(); return false; }
      const stroke = paintStroke;
      if (!stroke || stroke.layer.objectId !== hit.objectId) return false;
      const added = addPointToLayer(stroke.layer, hit, event.clientX, event.clientY);
      if (!added) return false;
      return true;
    };
    const showStrokeProgress = (): void => {
      if (!paintStroke) return;
      this.#viewport?.setSelected([paintStroke.layer.objectId]);
      clearShapePreview();
      this.#status = paintStroke.layer.label + " · " + paintStroke.layer.points.length.toLocaleString("de-DE") + " Oberflächenpunkte (noch nicht gespeichert).";
      this.#renderStatus();
    };
    const appendStrokeTo = (clientX: number, clientY: number): void => {
      const stroke = paintStroke;
      if (!stroke) return;
      const last = stroke.layer.points[stroke.layer.points.length - 1];
      if (!last) throw new Error("Unter dem Zeiger wurde keine gültige Modellfläche gefunden.");
      const stepPx = sampleStepFor(stroke.layer.objectId, stroke.layer.radiusMm, [last.x, last.y, last.z]);
      const steps = Math.max(1, Math.ceil(Math.hypot(clientX - stroke.lastX, clientY - stroke.lastY) / stepPx));
      if (steps > 20_000) throw new Error("Die Zeigerstrecke überschreitet das interaktive Malbudget.");
      for (let step = 1; step <= steps; step += 1) {
        const ratio = step / steps;
        applyPaint({ clientX: stroke.lastX + (clientX - stroke.lastX) * ratio, clientY: stroke.lastY + (clientY - stroke.lastY) * ratio });
      }
      stroke.lastX = clientX;
      stroke.lastY = clientY;
      showStrokeProgress();
    };
    const applyTextPaint = (event: PointerEvent): boolean => {
      const button = this.#paintButton(), hit = pickPaint(event.clientX, event.clientY);
      const instance = hit ? this.#plate().instances.find((item) => item.id === hit.objectId) ?? null : null;
      const text = button?.getText?.() ?? "";
      const fontSize = button?.getTextSizePx?.() ?? 28;
      if (!hit || !instance) { this.#status = "Text: Kein Objekt unter dem Zeiger."; this.#renderStatus(); return false; }
      if (!text) { this.#status = "Text: Bitte zuerst einen Schriftzug eingeben."; this.#renderStatus(); return false; }
      const brush = button?.getBrush?.() ?? { radiusMm: 1, color: "#ff4444", mode: "add" as const };
      const layer = this.#createPaintLayer(this.#plate(), hit.objectId, "text", { ...brush, radiusMm: Math.max(.12, brush.radiusMm * .45) }, "Text: " + text, { text, textSizePx: fontSize });
      const sampleCanvas = document.createElement("canvas");
      const ctx = sampleCanvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) throw new Error("Die Textmaske konnte nicht erstellt werden. Es wurde kein Malbereich angelegt.");
      const padding = Math.max(4, Math.ceil(fontSize * .18));
      ctx.font = "700 " + fontSize + "px Inter,Segoe UI,sans-serif";
      const measured = ctx.measureText(text);
      const glyphWidth = Number.isFinite(measured.actualBoundingBoxRight) && Number.isFinite(measured.actualBoundingBoxLeft) ? measured.actualBoundingBoxRight + Math.abs(measured.actualBoundingBoxLeft) : measured.width;
      const maskWidth = Math.ceil(Math.max(measured.width, glyphWidth, fontSize) + padding * 2);
      const maskHeight = Math.ceil(fontSize * 1.45 + padding * 2);
      if (![maskWidth, maskHeight].every(Number.isFinite) || maskWidth < 1 || maskHeight < 1 || maskWidth * maskHeight > 1_000_000) throw new Error("Der Schriftzug überschreitet das Textbudget. Text verkürzen oder Schriftgröße verringern.");
      sampleCanvas.width = maskWidth;
      sampleCanvas.height = maskHeight;
      ctx.font = "700 " + fontSize + "px Inter,Segoe UI,sans-serif";
      ctx.fillStyle = "#fff";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(text, padding, padding + fontSize);
      const data = ctx.getImageData(0, 0, sampleCanvas.width, sampleCanvas.height).data;
      const maskLeft = event.clientX - padding, maskTop = event.clientY - padding - fontSize;
      layer.mask = { ...captureMask(hit.objectId, "text", maskLeft, maskTop, maskLeft + sampleCanvas.width, maskTop + sampleCanvas.height), width: sampleCanvas.width, height: sampleCanvas.height, runs: paintMaskRuns(data, sampleCanvas.width, sampleCanvas.height) };
      const samples: Array<readonly [number, number]> = [];
      const naturalStep = sampleStepFor(hit.objectId, Math.max(.08, layer.radiusMm * .55), hit.localPosition);
      // The exact alpha mask clips the footprint; every opaque pixel still needs geometric coverage.
      if (naturalStep < 1) layer.radiusMm /= naturalStep;
      const step = Math.max(1, Math.min(Math.floor(fontSize / 24) || 1, Math.floor(naturalStep) || 1));
      for (let y = 0; y < sampleCanvas.height; y += step) {
        for (let x = 0; x < sampleCanvas.width; x += step) {
          if (data[(y * sampleCanvas.width + x) * 4 + 3]! >= 128) samples.push([maskLeft + x + .5, maskTop + y + .5]);
        }
      }
      const count = sampleLayerPoints(layer, samples);
      if (!count) {
        this.#setPaintLayersForPlate(this.#plate(), this.#paintLayersForPlate().filter((item) => item !== layer));
        this.#status = "Text: Keine beschreibbare Oberfläche unter dem Schriftzug gefunden.";
        this.#renderStatus();
        return false;
      }
      clearShapePreview();
      if (!refinePaintResolution(layer)) return false;
      this.#status = instance.name + ": Text \"" + text + "\" als Materialfläche angelegt.";
      this.#renderStatus(); return true;
    };
    canvas.addEventListener("pointerdown", (event) => {
      const paintButton = this.#paintButton();
      if (paintStroke || paintShape || selectionFrame) {
        event.preventDefault(); event.stopImmediatePropagation();
        return;
      }
      if (event.button !== 0) {
        if (paintButton?.isActive?.()) { event.preventDefault(); event.stopImmediatePropagation(); }
        return;
      }
      if (paintButton?.isActive?.() && this.#mode !== "preview") {
        event.preventDefault(); event.stopImmediatePropagation();
        remainingPickWork = 20_000_000;
        try {
        const hit = pickPaint(event.clientX, event.clientY);
        const tool = paintButton.getTool?.() ?? "brush";
        if (!hit) { this.#status = "Malen: Kein Objekt unter dem Zeiger."; this.#renderStatus(); down = null; return; }
        this.#assertPaintEditable(hit.objectId);
        if (this.#plate().stage === "slicing") throw new Error("Während des Slicings kann die Modellbemalung nicht geändert werden.");
        const activeBrush = paintButton.getBrush?.();
        if (!activeBrush) throw new Error("Die Malwerkzeuge sind noch nicht bereit.");
        if (activeBrush.mode !== "remove" && !activeBrush.materialKey) throw new Error("Bitte vor dem Malen ein geladenes Druckfilament wählen.");
        canvas.setPointerCapture(event.pointerId);
        if (tool === "text") {
          clearShapePreview(); applyTextPaint(event); down = null; return;
        }
        if (tool === "rectangle" || tool === "circle" || tool === "line") {
          paintShape = { pointerId: event.pointerId, objectId: hit.objectId, startX: event.clientX, startY: event.clientY, localPoint: hit.localPosition, tool };
          clearShapePreview();
          this.#status = (tool === "line" ? "Linie" : tool === "rectangle" ? "Rechteck" : "Kreis") + ": Bereich mit gedrückter Maustaste aufziehen."; this.#renderStatus();
        } else {
          const brush = paintButton.getBrush?.() ?? { radiusMm: 10, color: "#ff4444", mode: "add" as const };
          const label = tool === "pen" ? "Stiftstrich" : tool === "eraser" ? "Radierer" : "Pinselstrich";
          const layer = this.#createPaintLayer(this.#plate(), hit.objectId, "stroke", brush, label);
          paintStroke = { pointerId: event.pointerId, lastX: event.clientX, lastY: event.clientY, layer };
          if (!applyPaint(event)) throw new Error("Unter dem Zeiger wurde keine gültige Modellfläche gefunden.");
          showStrokeProgress();
        }
        } catch (error) { failPaint(error); }
        down = null; return;
      }
      if (this.#tool === "select" && this.#mode !== "preview" && (event.ctrlKey || event.metaKey)) {
        selectionFrame = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, initial: new Set(this.#selected) };
        canvas.setPointerCapture(event.pointerId);
        event.preventDefault(); event.stopImmediatePropagation();
        this.#status = "Rahmenauswahl: Strg/Cmd gedrückt halten und den Bereich aufziehen. Bestehende Auswahl bleibt erhalten.";
        this.#renderStatus();
        down = null;
        return;
      }
      const picked = this.#viewport?.pick(event.clientX, event.clientY) ?? null;
      if (picked?.startsWith("purge-tower-") && this.#mode !== "preview") {
        const purge = loadPlatePurgeTower(this.#plate().id);
        this.#purgeDrag = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          initialX: this.#purgeTowerData().x || Number(purge.position_x ?? this.#plate().width - 30),
          initialY: this.#purgeTowerData().y || Number(purge.position_y ?? this.#plate().depth - 30),
        };
        canvas.setPointerCapture(event.pointerId);
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      down = { x: event.clientX, y: event.clientY, id: event.pointerId };
      if (this.#tool !== "select" && this.#selected.size && this.#mode !== "preview") {
        event.preventDefault();
        event.stopImmediatePropagation();
        this.#drag = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          initial: new Map(this.#selectedItems().map((item) => [item.id, item])),
          mode: this.#tool,
          axis: this.#axis,
        };
      }
    }, { capture: true });
    canvas.addEventListener("pointermove", (event) => {
      if (selectionFrame?.pointerId === event.pointerId) {
        event.preventDefault(); event.stopImmediatePropagation();
        drawShapePreview("rectangle", selectionFrame.startX, selectionFrame.startY, event.clientX, event.clientY);
        return;
      }
      if (this.#paintButton()?.isActive?.() && this.#paintButton()?.getTool?.() === "text") {
        event.preventDefault(); event.stopImmediatePropagation();
        drawTextPreview(this.#paintButton()?.getText?.() ?? "", this.#paintButton()?.getTextSizePx?.() ?? 28, event.clientX, event.clientY); return;
      }
      if (paintStroke?.pointerId === event.pointerId && this.#paintButton()?.isActive?.()) {
        event.preventDefault();
        event.stopImmediatePropagation();
        try { appendStrokeTo(event.clientX, event.clientY); }
        catch (error) { failPaint(error); }
        return;
      }
      if (paintShape?.pointerId === event.pointerId) {
        event.preventDefault();
        event.stopImmediatePropagation();
        drawShapePreview(paintShape.tool, paintShape.startX, paintShape.startY, event.clientX, event.clientY);
        return;
      }
      const purgeDrag = this.#purgeDrag;
      if (purgeDrag && purgeDrag.pointerId === event.pointerId) {
        event.preventDefault();
        event.stopImmediatePropagation();
        const state = loadPlatePurgeTower(this.#plate().id);
        const data = this.#purgeTowerData();
        const visibleInset = 18;
        const minimumCenter = data.width / 2 + data.brim + visibleInset;
        const maximumX = Math.max(minimumCenter, this.#plate().width - data.width / 2 - data.brim - visibleInset);
        const maximumY = Math.max(minimumCenter, this.#plate().depth - data.width / 2 - data.brim - visibleInset);
        const x = Math.max(minimumCenter, Math.min(maximumX, purgeDrag.initialX + (event.clientX - purgeDrag.startX) * .28));
        const y = Math.max(minimumCenter, Math.min(maximumY, purgeDrag.initialY - (event.clientY - purgeDrag.startY) * .28));
        savePlatePurgeTower(this.#plate().id, { ...state, width_mm: data.width, brim_width_mm: data.brim, position_x: Math.round(x), position_y: Math.round(y) });
        this.#viewport?.setInstances(this.#displayInstances());
        return;
      }
      const drag = this.#drag;
      if (!drag || drag.pointerId !== event.pointerId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const dx = event.clientX - drag.startX;
      const dy = event.clientY - drag.startY;
      const changes = new Map<string, MeshInstance>();
      for (const [id, item] of drag.initial) {
        if (drag.mode === "translate") {
          const position = [...item.position] as Vec3;
          if (drag.axis === "free") {
            position[0] += dx * .28;
            position[1] -= dy * .28;
          } else {
            const axis = drag.axis === "x" ? 0 : drag.axis === "y" ? 1 : 2;
            position[axis] += (drag.axis === "x" ? dx : -dy) * .25;
          }
          changes.set(id, { ...item, position });
        }
        if (drag.mode === "rotate") {
          const rotation = [...item.rotation] as Vec3;
          if (drag.axis === "free") {
            rotation[2] += dx * .35;
            rotation[0] -= dy * .35;
          } else {
            const axis = drag.axis === "x" ? 0 : drag.axis === "y" ? 1 : 2;
            rotation[axis] += (drag.axis === "x" ? dx : -dy) * .35;
          }
          changes.set(id, { ...item, rotation });
        }
        if (drag.mode === "scale") {
          const scale = [...item.scale] as Vec3;
          const delta = (dx - dy) * .005;
          if (drag.axis === "free" || event.shiftKey) {
            const next = Math.max(.01, scale[0] + delta);
            scale[0] = scale[1] = scale[2] = next;
          } else {
            const axis = drag.axis === "x" ? 0 : drag.axis === "y" ? 1 : 2;
            scale[axis] = Math.max(.01, scale[axis] + delta);
          }
          changes.set(id, { ...item, scale });
        }
      }
      this.#plate().instances = this.#plate().instances.map((item) => changes.get(item.id) ?? item);
      this.#invalidatePlate();
      this.#viewport?.setInstances(this.#displayInstances());
      this.#viewport?.setGizmo(this.#center(), this.#tool, this.#gizmoAxis());
      this.#renderCoordinates();
    }, { capture: true });
    const finish = (event: PointerEvent): void => {
      if (selectionFrame?.pointerId === event.pointerId) {
        event.preventDefault(); event.stopImmediatePropagation();
        const frame = selectionFrame; selectionFrame = null;
        clearShapePreview();
        if (event.type === "pointercancel") return;
        if (Math.hypot(event.clientX - frame.startX, event.clientY - frame.startY) < 4) {
          this.#select(this.#viewport?.pick(event.clientX, event.clientY) ?? null, true, event.shiftKey);
          return;
        }
        try {
          const triangles = this.#viewport?.pickSelectionRectangle(frame.startX, frame.startY, event.clientX, event.clientY) ?? new Map<string, readonly number[]>();
          const plate = this.#plate(), selected = new Set(frame.initial);
          for (const instance of plate.instances) if (triangles.has(instance.id)) selected.add(instance.id);
          const left = Math.min(frame.startX, event.clientX), top = Math.min(frame.startY, event.clientY);
          const right = Math.max(frame.startX, event.clientX), bottom = Math.max(frame.startY, event.clientY);
          this.#paintLayersForPlate(plate).forEach((layer, index) => {
            if (!triangles.has(layer.objectId)) return;
            const rectangle = captureMask(layer.objectId, "rectangle", left, top, right, bottom);
            if (layer.points.some((point) => paintMaskContains(rectangle, point.x, point.y, point.z))) selected.add(this.#paintLayerSelectionId(index));
          });
          const selectedFaces = new Map([...triangles].map(([id, values]) => [id, new Set(values)]));
          this.#paintRowsForSelection(plate).forEach((region, index) => {
            if (region.triangleIndices.some((triangle) => selectedFaces.get(region.objectId)?.has(triangle))) selected.add(this.#paintSelectionId(index));
          });
          this.#selected = selected;
          this.#selectionAnchor = [...selected].at(-1) ?? null;
          this.#refreshSelectionUi();
          this.#status = `${selected.size} Einträge ausgewählt.`;
          this.#renderStatus();
        } catch (error) { failPaint(error); }
        return;
      }
      if (paintShape?.pointerId === event.pointerId) {
        const shape = paintShape; paintShape = null;
        clearShapePreview();
        if (event.type === "pointercancel") return;
        try {
          const baseBrush = this.#paintButton()?.getBrush?.() ?? { radiusMm: 10, color: "#ff4444", mode: "add" as const };
          const label = shape.tool === "line" ? "Linie" : shape.tool === "rectangle" ? "Rechteck" : "Kreis";
          const layer = this.#createPaintLayer(this.#plate(), shape.objectId, shape.tool === "line" ? "stroke" : shape.tool, baseBrush, label);
          const left = Math.min(shape.startX, event.clientX), right = Math.max(shape.startX, event.clientX);
          const top = Math.min(shape.startY, event.clientY), bottom = Math.max(shape.startY, event.clientY);
          const samples: Array<readonly [number, number]> = [];
          if (shape.tool === "line") {
            const steps = Math.max(1, Math.ceil(Math.hypot(right - left, bottom - top) / sampleStepFor(shape.objectId, layer.radiusMm, shape.localPoint)));
            if (steps > 20_000) throw new Error("Die Linie überschreitet das interaktive Malbudget.");
            for (let step = 0; step <= steps; step += 1) samples.push([shape.startX + (event.clientX - shape.startX) * step / steps, shape.startY + (event.clientY - shape.startY) * step / steps]);
          } else {
            layer.mask = captureMask(shape.objectId, shape.tool, left, top, right, bottom);
            const cx = (left + right) / 2, cy = (top + bottom) / 2;
            const rx = (right - left) / 2, ry = (bottom - top) / 2;
            const step = sampleStepFor(shape.objectId, Math.max(.08, layer.radiusMm * .55), shape.localPoint);
            if (Math.ceil((right - left) / step) * Math.ceil((bottom - top) / step) > 50_000) throw new Error("Die Form überschreitet das interaktive Malbudget. Bitte einen kleineren Bereich zeichnen.");
            for (let y = top + Math.min(step / 2, ry); y < bottom; y += step) {
              for (let x = left + Math.min(step / 2, rx); x < right; x += step) {
                if (shape.tool === "rectangle" || ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1) samples.push([x, y]);
              }
            }
          }
          const count = sampleLayerPoints(layer, samples);
          if (!count) { this.#status = label + ": Keine beschreibbare Oberfläche im gezogenen Bereich."; this.#renderStatus(); return; }
          if (refinePaintResolution(layer)) { this.#status = label + ": Materialfläche mit " + count.toLocaleString("de-DE") + " Oberflächenpunkten angelegt."; this.#renderStatus(); }
        } catch (error) { failPaint(error); }
        return;
      }
      if (paintStroke?.pointerId === event.pointerId) {
        const stroke = paintStroke;
        if (event.type !== "pointercancel") {
          try { appendStrokeTo(event.clientX, event.clientY); } catch (error) { failPaint(error); return; }
        }
        paintStroke = null;
        clearShapePreview();
        if (event.type !== "pointercancel" && refinePaintResolution(stroke.layer)) {
          this.#status = stroke.layer.label + ": Materialfläche gespeichert.";
          this.#renderStatus();
        }
        return;
      }
      if (this.#purgeDrag?.pointerId === event.pointerId) {
        event.preventDefault();
        event.stopImmediatePropagation();
        this.#purgeDrag = null;
        this.#renderSidebar();
        this.#renderStatus();
        this.#schedulePersist();
        down = null;
        return;
      }
      if (this.#drag?.pointerId === event.pointerId) {
        event.preventDefault();
        event.stopImmediatePropagation();
        this.#drag = null;
        this.#renderSidebar();
        this.#renderStatus();
        this.#schedulePersist();
      } else if (down && down.id === event.pointerId && Math.hypot(event.clientX - down.x, event.clientY - down.y) < 4) {
        this.#select(this.#viewport?.pick(event.clientX, event.clientY) ?? null, event.ctrlKey || event.metaKey, event.shiftKey);
      }
      down = null;
    };
    canvas.addEventListener("pointerup", finish, { capture: true });
    canvas.addEventListener("pointercancel", finish, { capture: true });
    const cancelGesture = (): void => {
      if (this.#cancelViewportGesture !== cancelGesture || (!paintStroke && !paintShape && !selectionFrame)) return;
      paintStroke = null;
      paintShape = null;
      selectionFrame = null;
      down = null;
      clearShapePreview();
      this.#viewport?.setSelected(this.#plate().instances.filter((item) => this.#selected.has(item.id)).map((item) => item.id));
      this.#status = "Laufende Geste verworfen; gespeicherte Modell- und Materialdaten bleiben erhalten.";
      this.#renderStatus();
    };
    this.#cancelViewportGesture = cancelGesture;
    canvas.addEventListener("lostpointercapture", (event) => {
      if (paintStroke?.pointerId === event.pointerId || paintShape?.pointerId === event.pointerId || selectionFrame?.pointerId === event.pointerId) cancelGesture();
    });
  }

  #bindFilamentSyncActions(host: HTMLElement): void {
    host.querySelector<HTMLButtonElement>("#sync-filaments")?.addEventListener("click", () => void this.#syncFilaments());
    host.querySelector<HTMLButtonElement>("#remove-model-colors")?.addEventListener("click", () => this.#removeModelColors());
  }

  #bindFilamentDetails(host: HTMLElement): void {
    host.querySelectorAll<HTMLDetailsElement>("details[data-filament-detail-key]").forEach((details) => {
      details.addEventListener("toggle", () => updateDetailsOpenState(
        this.#openFilamentDetailKeys,
        details.dataset.filamentDetailKey || "",
        details.open,
      ));
    });
  }

  #renderSidebar(): void {
    const host = this.#root.querySelector<HTMLElement>("#sidebar");
    if (!host) return;
    preserveFilamentView(host, () => this.#renderSidebarContent());
  }

  #renderSidebarContent(): void {
    const host = this.#root.querySelector<HTMLElement>("#sidebar");
    if (!host) return;
    const selected = this.#selectedItems();
    const primary = selected[0] ?? null;
    const plate = this.#plate();
    try {
      setBatchQueueContext({
        studio_plate_id: plate.id,
        studio_plate_display_number: plate.id + 1,
        studio_plate_name: plate.name,
        project_name: this.#inspection?.filename || this.#file?.name || "",
        target_printer_id: plate.selection.target_printer_id,
        printer_profile_id: plate.selection.printer_profile_id,
        nozzle_profile_id: plate.selection.nozzle_profile_id,
        process_profile_id: plate.selection.process_profile_id,
        gcode_preset_ids: { ...plate.selection.gcode_preset_ids },
        build_plate_profile_id: plate.selection.build_plate_profile_id,
        filament_profile_ids: plate.materialSource === "external_spool"
          ? [plate.externalFilamentProfileId]
          : [...plate.selection.filament_profile_ids],
      }, this.#materialPlan());
    } catch {
      // Incomplete selections must never replace the last valid batch context.
    }
    if (this.#mode === "colors") {
      const syncActions = filamentSyncActionsHtml(this.#amsLoading, this.#amsError);
      const sourceOptions = `<label><span>Materialquelle</span><select id="material-source-sidebar"><option value="ams" ${plate.materialSource === "ams" ? "selected" : ""}>AMS Lite</option><option value="external_spool" ${plate.materialSource === "external_spool" ? "selected" : ""}>Externe Spule</option></select></label>`;
      if (plate.materialSource === "external_spool") {
        const external = this.#externalFilamentChoice(plate);
        host.innerHTML = `<h3>Materialquelle</h3><div class="section">${sourceOptions}${syncActions}<small>Die externe Spule ist ein eigener Einzelmaterialkanal. Das gewählte Filament muss vor dem Druck manuell am Drucker geladen sein; AMS-Fallback und Materialwechsel sind deaktiviert.</small></div><div class="section"><b>Filamentprofile</b>${filamentProfilesHtml(this.#catalog, plate.externalFilamentProfileId ? [plate.externalFilamentProfileId] : [], this.#openFilamentDetailKeys)}${external ? `<div class="assignment"><span class="swatch" style="background:${external.color}"></span><b>${escapeHtml(external.name)}</b><span>${escapeHtml(external.material)}</span></div>` : '<span class="error-box">Ein Filamentprofil muss ausdrücklich gewählt werden.</span>'}</div>`;
        this.#bindFilamentSyncActions(host);
        this.#bindFilamentDetails(host);
        host.querySelector<HTMLSelectElement>("#material-source-sidebar")?.addEventListener("change", (event) => this.#materialSourceChanged((event.currentTarget as HTMLSelectElement).value));
        host.querySelectorAll<HTMLButtonElement>("[data-filament-profile]").forEach((button) => {
          button.addEventListener("click", () => this.#externalFilamentProfileChanged(button.dataset.filamentProfile === plate.externalFilamentProfileId ? "" : button.dataset.filamentProfile || ""));
        });
        return;
      }
      const choices = this.#amsMaterialChoices();
      const currentKey = primary ? this.#assignments.get(primary.id) || "" : "";
      host.innerHTML = `<h3>Mehrfarben & AMS</h3><div class="section">${sourceOptions}${syncActions}</div><div class="section"><b>Filamentprofile</b><small>Lokale, Standard- und bereits synchronisierte Cloud-Profile. Die Materialquelle bestimmt automatisch die Verwendung: belegte AMS-Kanäle oder externe Einzelspule. Cloud-Synchronisation erfolgt ausschließlich manuell unter Profile.</small>${filamentProfilesHtml(this.#catalog, plate.selection.filament_profile_ids, this.#openFilamentDetailKeys)}</div><div class="section"><div class="assignment"><span class="swatch" style="background:${this.#materialColor(currentKey)}"></span><b>${primary?.name || "Objekt auswählen"}</b><select id="material-choice" ${primary && choices.length ? "" : "disabled"}><option value="">Nicht zugewiesen</option>${choices.map((choice) => `<option value="${choice.key}" ${choice.key === currentKey ? "selected" : ""}>${choice.name} · ${choice.material}</option>`).join("")}</select></div><small>Zuweisung gilt für alle markierten Objekte/Teile.</small></div>`;
      this.#bindFilamentDetails(host);
      host.querySelector<HTMLSelectElement>("#material-source-sidebar")?.addEventListener("change", (event) => this.#materialSourceChanged((event.currentTarget as HTMLSelectElement).value));
      this.#bindFilamentSyncActions(host);
      host.querySelectorAll<HTMLButtonElement>("[data-filament-profile]").forEach((button) => {
        button.addEventListener("click", () => void this.#toggleFilamentProfile(button.dataset.filamentProfile || ""));
      });
      host.querySelector<HTMLSelectElement>("#material-choice")?.addEventListener("change", (event) => {
        const key = (event.currentTarget as HTMLSelectElement).value;
        const changes = new Map<string, MeshInstance>();
        this.#clearErrors();
        for (const item of selected) {
          if (key) this.#assignments.set(item.id, key);
          else this.#assignments.delete(item.id);
          changes.set(item.id, { ...item, color: key ? this.#materialColor(key) : NEUTRAL_COLOR });
        }
        this.#replace(changes);
      });
      return;
    }
    if (this.#mode === "preview") {
      const currentLayer = plate.layers.find((layer) => layer.index === plate.visibleLayer);
      const features = [...new Set((currentLayer?.segments ?? []).map((segment) => String(segment[7] || "Modell")))];
      const categories = new Map<string, string>();
      for (const segment of currentLayer?.segments ?? []) categories.set(String(segment[7] || "Modell"), String(segment[8] || "model"));
      const featureFilter = PREVIEW_FEATURE_KEYS.map((key) => `<label class="preview-filter-item"><input type="checkbox" data-preview-feature="${key}" ${this.#previewVisibleFeatures.has(key) ? "checked" : ""}><i style="--feature-color:${previewFeatureColor(key)}"></i><span>${escapeHtml(previewFeatureLabel(key))}</span></label>`).join("");
      const materials = normalizeToolpathPalette(plate.toolColors);
      const paletteWarning = toolpathPaletteWarning(plate.layers, materials);
      const materialRows = materials.map((color, index) => `<div class="preview-material-row"><i style="--material-color:${color || UNKNOWN_TOOLPATH_COLOR}"></i><span>Filament ${index + 1}</span><small>${color ? color.toUpperCase() : "Farbe unbekannt"}</small></div>`).join("");
      const support = toolpathSupportStats(plate.layers);
      if (!support.present) this.#previewSupportOnly = false;
      const supportPanel = support.present ? `<div class="section"><b>Support-Vorschau</b><span>${support.segmentCount.toLocaleString("de-DE")} Supportbahnen · ${support.interfaceSegmentCount.toLocaleString("de-DE")} Interface-Bahnen</span><small>Layer ${(support.firstLayer ?? 0) + 1} bis ${(support.lastLayer ?? 0) + 1}. Der sichere Modus blendet Modell, Brim, Raft und Reinigungsturm aus und erzeugt keine zusätzlichen 3D-Seitenflächen. Alle geladenen Supportbahnen bleiben zusammenhängend erhalten.</small><button id="preview-support-only" class="${this.#previewSupportOnly ? "active" : ""}" type="button">${this.#previewSupportOnly ? "Gesamte Vorschau anzeigen" : "Nur Supportstruktur anzeigen"}</button></div>` : "";
      const legend = features.slice(0, 12).map((feature) => {
        const color = featurePreviewColor(feature, categories.get(feature) || "model");
        return `<span class="feature-chip"><i style="background:${color}"></i>${escapeHtml(feature)}</span>`;
      }).join("");
      const filterSection = `<div class="section preview-filter"><div class="preview-filter-head"><b>Sichtbare Druckbahnen</b><span class="preview-filter-actions"><button id="preview-feature-all" type="button">Alle</button><button id="preview-feature-none" type="button">Keine</button></span></div><small>Druckbahntypen können wie in Bambu Studio vollständig aus der 3D-Vorschau ausgeblendet werden.</small><div class="preview-filter-grid">${featureFilter}</div></div>`;
      const materialSection = materialRows ? `<details class="preview-material-details" id="preview-material-summary" ${this.#previewMaterialOpen ? "open" : ""}><summary>Filamentfarben · ${materials.length} Filament(e)</summary><div class="preview-material-body">${materialRows}</div></details>` : "";
      const variableLayerRanges = loadSliceProcessOverrides().layer_height_ranges;
      const variableLayerSection = variableLayerRangesHtml(variableLayerRanges, currentLayer?.z ?? 0);
      const layerControlsDisabled = plate.layerCount ? "" : "disabled";
      host.innerHTML = `<h3>G‑Code‑Vorschau</h3>${paletteWarning ? `<div class="error-box" role="status">${escapeHtml(paletteWarning)}</div>` : ""}${supportPanel}${variableLayerSection}<div class="section"><b>${escapeHtml(plate.name)}</b><span>Status: ${this.#stageLabel(plate.stage)}</span><div class="preview-summary"><span id="preview-track-count">${(currentLayer?.segments.length ?? 0).toLocaleString("de-DE")} Bahnen</span><span id="preview-extrusion">${(currentLayer?.extrusion_mm ?? 0).toFixed(2)} mm Extrusion</span></div><label><span id="layer-label">Layer ${plate.layerCount ? plate.visibleLayer + 1 : 0} / ${plate.layerCount} · Z ${(currentLayer?.z ?? 0).toFixed(2)} mm</span><input class="layer" id="layer" type="range" min="0" max="${Math.max(0, plate.layerCount - 1)}" value="${plate.visibleLayer}" ${layerControlsDisabled}></label><div class="layer-stepper" aria-label="Layer schrittweise wechseln"><button id="layer-first" type="button" ${layerControlsDisabled}>Erster</button><button id="layer-jump-back" type="button" ${layerControlsDisabled}>-10</button><button id="layer-prev" type="button" ${layerControlsDisabled}>Zurück</button><label class="layer-jump">Layer <input id="layer-index" type="number" min="1" max="${Math.max(1, plate.layerCount)}" step="1" value="${plate.layerCount ? plate.visibleLayer + 1 : 0}" ${layerControlsDisabled}></label><button id="layer-next" type="button" ${layerControlsDisabled}>Weiter</button><button id="layer-jump-forward" type="button" ${layerControlsDisabled}>+10</button><button id="layer-last" type="button" ${layerControlsDisabled}>Letzter</button></div><div class="preview-toggle"><button id="preview-material" class="${this.#previewColorMode === "material" ? "active" : ""}">Filamentfarben</button><button id="preview-feature" class="${this.#previewColorMode === "feature" ? "active" : ""}">Drucktyp</button></div><label class="preview-check"><input id="preview-cumulative" type="checkbox" ${this.#previewCumulative ? "checked" : ""}>Vorherige Layer räumlich anzeigen</label>${this.#previewColorMode === "feature" && legend ? `<div class="feature-legend">${legend}</div>` : ""}${filterSection}${materialSection}${plate.stage === "sliced" ? '<button id="mark-printed">Als gedruckt markieren</button>' : ""}</div>`;
      host.querySelector<HTMLButtonElement>("#preview-support-only")?.addEventListener("click", () => {
        this.#previewSupportOnly = !this.#previewSupportOnly;
        if (this.#previewSupportOnly) this.#previewCumulative = true;
        this.#refreshPreviewViewport();
        this.#renderSidebar();
      });
      const layerSlider = host.querySelector<HTMLInputElement>("#layer");
      const updateVisibleLayerSidebar = (value: number): void => {
        const layer = plate.layers.find((item) => item.index === value);
        if (layerSlider) layerSlider.value = String(value);
        const layerIndexInput = this.#root.querySelector<HTMLInputElement>("#layer-index");
        if (layerIndexInput) layerIndexInput.value = String(value + 1);
        const label = this.#root.querySelector<HTMLElement>("#layer-label");
        if (label) label.textContent = "Layer " + (value + 1) + " / " + plate.layerCount + " · Z " + (layer?.z ?? 0).toFixed(2) + " mm";
        const tracks = this.#root.querySelector<HTMLElement>("#preview-track-count");
        if (tracks) tracks.textContent = (layer?.segments.length ?? 0).toLocaleString("de-DE") + " Bahnen";
        const extrusion = this.#root.querySelector<HTMLElement>("#preview-extrusion");
        if (extrusion) extrusion.textContent = (layer?.extrusion_mm ?? 0).toFixed(2) + " mm Extrusion";
        const rangeCurrent = this.#root.querySelector<HTMLElement>("#preview-layer-height-range-current");
        const activeRange = variableLayerRangeAt(variableLayerRanges, layer?.z ?? 0);
        if (rangeCurrent) rangeCurrent.textContent = variableLayerRangeText(activeRange);
        this.#root.querySelectorAll<HTMLElement>("[data-layer-height-range]").forEach((chip) => {
          const range = variableLayerRanges[Number(chip.dataset.layerHeightRange)];
          const isActive = Boolean(range && activeRange === range);
          chip.classList.toggle("active", isActive);
          const marker = chip.querySelector<HTMLElement>("i");
          if (marker) marker.style.background = isActive ? "#54d66c" : "#7fd2f6";
        });
      };
      const selectVisibleLayer = (rawValue: number, rerender = false): void => {
        const value = Math.max(0, Math.min(Math.max(0, plate.layerCount - 1), Math.round(rawValue)));
        plate.visibleLayer = value;
        updateVisibleLayerSidebar(value);
        this.#refreshPreviewViewport();
        if (rerender) this.#renderSidebar();
      };
      layerSlider?.addEventListener("input", (event) => {
        const value = Number((event.currentTarget as HTMLInputElement).value);
        plate.visibleLayer = value;
        updateVisibleLayerSidebar(value);
        this.#refreshPreviewViewport();
      });
      layerSlider?.addEventListener("change", () => this.#renderSidebar());
      host.querySelector<HTMLButtonElement>("#layer-first")?.addEventListener("click", () => selectVisibleLayer(0, true));
      host.querySelector<HTMLButtonElement>("#layer-jump-back")?.addEventListener("click", () => selectVisibleLayer(plate.visibleLayer - 10, true));
      host.querySelector<HTMLButtonElement>("#layer-prev")?.addEventListener("click", () => selectVisibleLayer(plate.visibleLayer - 1, true));
      host.querySelector<HTMLInputElement>("#layer-index")?.addEventListener("change", (event) => {
        selectVisibleLayer(Number((event.currentTarget as HTMLInputElement).value) - 1, true);
      });
      host.querySelector<HTMLButtonElement>("#layer-next")?.addEventListener("click", () => selectVisibleLayer(plate.visibleLayer + 1, true));
      host.querySelector<HTMLButtonElement>("#layer-jump-forward")?.addEventListener("click", () => selectVisibleLayer(plate.visibleLayer + 10, true));
      host.querySelector<HTMLButtonElement>("#layer-last")?.addEventListener("click", () => selectVisibleLayer(plate.layerCount - 1, true));
      host.querySelector<HTMLButtonElement>("#preview-material")?.addEventListener("click", () => {
        this.#previewColorMode = "material";
        this.#refreshPreviewViewport();
        this.#renderSidebar();
      });
      host.querySelector<HTMLButtonElement>("#preview-feature")?.addEventListener("click", () => {
        this.#previewColorMode = "feature";
        this.#refreshPreviewViewport();
        this.#renderSidebar();
      });
      host.querySelectorAll<HTMLInputElement>("[data-preview-feature]").forEach((input) => input.addEventListener("change", () => {
        const key = input.dataset.previewFeature as PreviewFeatureKey;
        if (input.checked) this.#previewVisibleFeatures.add(key); else this.#previewVisibleFeatures.delete(key);
        this.#refreshPreviewViewport();
      }));
      host.querySelector<HTMLButtonElement>("#preview-feature-all")?.addEventListener("click", () => {
        this.#previewVisibleFeatures = new Set(PREVIEW_FEATURE_KEYS);
        this.#refreshPreviewViewport();
        this.#renderSidebar();
      });
      host.querySelector<HTMLButtonElement>("#preview-feature-none")?.addEventListener("click", () => {
        this.#previewVisibleFeatures.clear();
        this.#refreshPreviewViewport();
        this.#renderSidebar();
      });
      host.querySelector<HTMLDetailsElement>("#preview-material-summary")?.addEventListener("toggle", (event) => {
        this.#previewMaterialOpen = (event.currentTarget as HTMLDetailsElement).open;
      });
      host.querySelector<HTMLInputElement>("#preview-cumulative")?.addEventListener("change", (event) => {
        this.#previewCumulative = (event.currentTarget as HTMLInputElement).checked;
        this.#refreshPreviewViewport();
      });
      host.querySelector<HTMLButtonElement>("#mark-printed")?.addEventListener("click", () => this.#markPrinted());
      return;
    }
    const center = this.#center();
    host.innerHTML = `<h3>Transformieren</h3><div class="section"><b>${plate.name}</b><span>Status: ${this.#stageLabel(plate.stage)}</span><small>Profile werden oben pro Platte ausgewählt. Ein Profilwechsel verschiebt kein Modell.</small></div>${primary ? `<div class="section"><b>${selected.length > 1 ? `${selected.length} Objekte ausgewählt` : primary.name}</b><label>Position<div class="triple"><input data-kind="position" data-axis="0" type="number" step="0.1" value="${(center?.[0] ?? 0).toFixed(2)}"><input data-kind="position" data-axis="1" type="number" step="0.1" value="${(center?.[1] ?? 0).toFixed(2)}"><input data-kind="position" data-axis="2" type="number" step="0.1" value="${(center?.[2] ?? 0).toFixed(2)}"></div></label><label>Drehung<div class="triple"><input data-kind="rotation" data-axis="0" type="number" step="1" value="${primary.rotation[0].toFixed(1)}"><input data-kind="rotation" data-axis="1" type="number" step="1" value="${primary.rotation[1].toFixed(1)}"><input data-kind="rotation" data-axis="2" type="number" step="1" value="${primary.rotation[2].toFixed(1)}"></div></label><label>Skalierung<div class="triple"><input data-kind="scale" data-axis="0" type="number" step="0.01" value="${primary.scale[0].toFixed(3)}"><input data-kind="scale" data-axis="1" type="number" step="0.01" value="${primary.scale[1].toFixed(3)}"><input data-kind="scale" data-axis="2" type="number" step="0.01" value="${primary.scale[2].toFixed(3)}"></div></label></div>` : '<div class="section">Objekt im Canvas oder links auswählen.</div>'}`;
    host.querySelectorAll<HTMLInputElement>("[data-kind]").forEach((input) => {
      input.addEventListener("change", () => {
        const kind = input.dataset.kind as "position" | "rotation" | "scale";
        const axis = Number(input.dataset.axis) as 0 | 1 | 2;
        const value = Number(input.value);
        if (!Number.isFinite(value)) return;
        const changes = new Map<string, MeshInstance>();
        if (kind === "position" && center) {
          const delta = value - center[axis];
          for (const item of selected) {
            const position = [...item.position] as Vec3;
            position[axis] += delta;
            changes.set(item.id, { ...item, position });
          }
        } else {
          for (const item of selected) {
            const vector = [...item[kind]] as Vec3;
            vector[axis] = kind === "scale" ? Math.max(.001, value) : value;
            changes.set(item.id, { ...item, [kind]: vector });
          }
        }
        this.#replace(changes);
      });
    });
  }
}

if (!customElements.get("ultimate-3d-unified-studio")) {
  customElements.define("ultimate-3d-unified-studio", Ultimate3DMegaStudioV2);
}
