import "./direct-print-panel.js";
import { authenticatedFetch, authenticatedUpload, errorMessage, type AuthenticatedUploadProgress } from "./ha-api-transport.js";
import { ProfileApi } from "./profile-api.js";
import { mergePlatePurgeTower } from "./purge-tower-state.js";
import type { SliceJob, SliceProjectFilament, SlicePurgeTower } from "./slicing-api.js";
export { nozzleProcessContract, processOverrideValidationError, type NozzleProcessContract } from "./nozzle-process-contract.js";

export type AdhesionMode = "none" | "brim" | "raft";
export type SupportMode = "off" | "normal" | "tree";
export type SliceProcessOverrides = Readonly<{
  adhesion_mode: AdhesionMode;
  brim_width_mm: number;
  raft_layers: number;
  support_mode: SupportMode;
  support_build_plate_only: boolean;
  support_threshold_angle: number;
  layer_height_mm: number | null;
  outer_wall_speed_mm_s: number | null;
  inner_wall_speed_mm_s: number | null;
}>;
export type SliceMaterialPlan = Readonly<{
  source?: "ams" | "external_spool";
  target_printer_id?: string;
  assignments: Readonly<Record<string, number>>;
  filaments: readonly SliceProjectFilament[];
  purge_tower: SlicePurgeTower;
}>;
export type PlateSliceContext = Readonly<{
  studio_plate_id: number;
  studio_plate_display_number: number;
  studio_plate_name: string;
  project_name?: string;
  target_printer_id?: string;
  printer_profile_id?: string;
  nozzle_profile_id?: string;
  process_profile_id?: string;
  build_plate_profile_id?: string;
  filament_profile_ids?: readonly string[];
}>;
export type PlateSliceJob = SliceJob & Readonly<{
  requested_plate_index?: number;
  requested_plate_display_number?: number;
  requested_profiles?: Readonly<Record<string, unknown>>;
  process_overrides?: SliceProcessOverrides;
  material_plan?: Readonly<Record<string, unknown>>;
}>;

export const SLICER_PROCESS_OPTIONS_KEY = "ultimate-3d-studio-v6:slicer-process-options";
export const DEFAULT_SLICE_PROCESS_OVERRIDES: SliceProcessOverrides = {
  adhesion_mode: "none",
  brim_width_mm: 5,
  raft_layers: 2,
  support_mode: "off",
  support_build_plate_only: true,
  support_threshold_angle: 30,
  layer_height_mm: null,
  outer_wall_speed_mm_s: null,
  inner_wall_speed_mm_s: null,
};
let activeMaterialPlan: SliceMaterialPlan | undefined;

export function setActiveSliceMaterialPlan(plan: SliceMaterialPlan | undefined): void { activeMaterialPlan = plan; }
export function getActiveSliceMaterialPlan(): SliceMaterialPlan | undefined { return activeMaterialPlan; }

function numberInRange(value: unknown, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(minimum, Math.min(maximum, parsed)) : fallback;
}

function optionalNumberInRange(value: unknown, minimum: number, maximum: number): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : null;
}

export function loadSliceProcessOverrides(): SliceProcessOverrides {
  try {
    const raw = localStorage.getItem(SLICER_PROCESS_OPTIONS_KEY);
    const value = raw ? JSON.parse(raw) as Record<string, unknown> : {};
    const adhesion = ["none", "brim", "raft"].includes(String(value.adhesion_mode))
      ? String(value.adhesion_mode) as AdhesionMode
      : "none";
    const support = ["off", "normal", "tree"].includes(String(value.support_mode))
      ? String(value.support_mode) as SupportMode
      : "off";
    return {
      adhesion_mode: adhesion,
      brim_width_mm: numberInRange(value.brim_width_mm, 5, 1, 30),
      raft_layers: Math.round(numberInRange(value.raft_layers, 2, 1, 10)),
      support_mode: support,
      support_build_plate_only: value.support_build_plate_only !== false,
      support_threshold_angle: Math.round(numberInRange(value.support_threshold_angle, 30, 0, 89)),
      layer_height_mm: optionalNumberInRange(value.layer_height_mm, .04, .56),
      outer_wall_speed_mm_s: optionalNumberInRange(value.outer_wall_speed_mm_s, 1, 500),
      inner_wall_speed_mm_s: optionalNumberInRange(value.inner_wall_speed_mm_s, 1, 500),
    };
  } catch {
    return DEFAULT_SLICE_PROCESS_OVERRIDES;
  }
}

export function saveSliceProcessOverrides(value: SliceProcessOverrides): void {
  localStorage.setItem(SLICER_PROCESS_OPTIONS_KEY, JSON.stringify({
    adhesion_mode: value.adhesion_mode,
    brim_width_mm: numberInRange(value.brim_width_mm, 5, 1, 30),
    raft_layers: Math.round(numberInRange(value.raft_layers, 2, 1, 10)),
    support_mode: value.support_mode,
    support_build_plate_only: value.support_build_plate_only !== false,
    support_threshold_angle: Math.round(numberInRange(value.support_threshold_angle, 30, 0, 89)),
    layer_height_mm: optionalNumberInRange(value.layer_height_mm, .04, .56),
    outer_wall_speed_mm_s: optionalNumberInRange(value.outer_wall_speed_mm_s, 1, 500),
    inner_wall_speed_mm_s: optionalNumberInRange(value.inner_wall_speed_mm_s, 1, 500),
  }));
}

async function activatePlateProfiles(context: PlateSliceContext | undefined): Promise<void> {
  if (!context) return;
  const hasProfiles = Boolean(
    context.printer_profile_id
    || context.nozzle_profile_id
    || context.process_profile_id
    || context.build_plate_profile_id
    || context.filament_profile_ids?.length,
  );
  if (!hasProfiles) return;
  await new ProfileApi().saveSelection({
    printer_profile_id: context.printer_profile_id || null,
    nozzle_profile_id: context.nozzle_profile_id || null,
    process_profile_id: context.process_profile_id || null,
    build_plate_profile_id: context.build_plate_profile_id || null,
    filament_profile_ids: [...(context.filament_profile_ids ?? [])],
  });
}

export async function createPlateSliceJob(
  file: File,
  plateIndex: number,
  overrides: SliceProcessOverrides = loadSliceProcessOverrides(),
  materialPlan?: SliceMaterialPlan,
  context?: PlateSliceContext,
  onUploadProgress?: (progress: AuthenticatedUploadProgress) => void,
): Promise<PlateSliceJob> {
  await activatePlateProfiles(context);

  const query = new URLSearchParams({
    filename: file.name,
    plate_index: String(plateIndex),
    adhesion_mode: overrides.adhesion_mode,
    support_mode: overrides.support_mode,
  });

  if (overrides.adhesion_mode === "brim") {
    query.set("brim_width_mm", String(numberInRange(overrides.brim_width_mm, 5, 1, 30)));
  } else if (overrides.adhesion_mode === "raft") {
    query.set("raft_layers", String(Math.round(numberInRange(overrides.raft_layers, 2, 1, 10))));
  }
  if (overrides.support_mode !== "off") {
    query.set("support_build_plate_only", String(overrides.support_build_plate_only));
    query.set("support_threshold_angle", String(Math.round(numberInRange(overrides.support_threshold_angle, 30, 0, 89))));
  }
  if (overrides.layer_height_mm !== null) query.set("layer_height_mm", String(overrides.layer_height_mm));
  if (overrides.outer_wall_speed_mm_s !== null) query.set("outer_wall_speed_mm_s", String(overrides.outer_wall_speed_mm_s));
  if (overrides.inner_wall_speed_mm_s !== null) query.set("inner_wall_speed_mm_s", String(overrides.inner_wall_speed_mm_s));

  const headers: Record<string, string> = { "Content-Type": "application/octet-stream" };
  const effectivePlan = mergePlatePurgeTower(
    materialPlan ?? activeMaterialPlan,
    context?.studio_plate_id,
  );
  if (effectivePlan) headers["X-U3D-Material-Plan"] = encodeURIComponent(JSON.stringify(effectivePlan));
  if (context) headers["X-U3D-Studio-Plate"] = encodeURIComponent(JSON.stringify(context));

  const response = await authenticatedUpload(`/api/ultimate_3d_studio_v6/v1/slicer/jobs-plate?${query}`, {
    method: "POST",
    headers,
    body: file,
  }, onUploadProgress);
  let payload: unknown;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) throw new Error(errorMessage(payload, `Slicer HTTP ${response.status}`));
  const envelope = payload as Readonly<{ data?: PlateSliceJob; error?: unknown }>;
  if (envelope.error || !envelope.data?.id) {
    throw new Error(errorMessage(envelope.error, "Kein Slicerauftrag angelegt."));
  }
  window.dispatchEvent(new CustomEvent("ultimate-3d-slice-job-created", {
    detail: {
      job: envelope.data,
      jobId: envelope.data.id,
        fileName: file.name,
      plateIndex,
      studioPlate: context ?? null,
      materialPlan: effectivePlan ?? null,
    },
  }));
  return envelope.data;
}