import { authenticatedFetch, callHomeAssistantApi, errorMessage } from "./ha-api-transport.js";
import type { V6ProfileSelection } from "./profile-api.js";
import type { BatchQueueContext, SliceProcessOverrides } from "./plate-slice-api.js";

const API_PREFIX = "/api/ultimate_3d_studio_v6/v1/slicer";

export type SlicerBackend = "server";

export type SlicerProvider = Readonly<{
  id: string;
  name: string;
  mode: string;
  capabilities: Readonly<{
    geometry_preview: boolean;
    layer_preview: boolean;
    plan_persistence: boolean;
    gcode_generation: boolean;
    gcode_3mf_artifact?: boolean;
    job_cancellation?: boolean;
    direct_print: boolean;
    detailed_gcode_analysis?: boolean;
    prime_tower_safety_gate?: boolean;
  }>;
  server?: Readonly<Record<string, unknown>>;
  disclaimer: string;
}>;

export type StoredGeometry = Readonly<{
  geometry_id: string;
  filename: string;
  size_bytes: number;
  sha256: string;
}>;

export type SliceModelPlate = Readonly<{
  plate_index: number;
  display_number: number;
  name: string;
  object_count: number | null;
  source: string;
  thumbnail_available?: boolean;
  thumbnail_path?: string | null;
}>;

export type SliceModelPart = Readonly<{
  object_id: string;
  parent_id: string | null;
  name: string;
  plate_index: number | null;
  extruder: number | null;
  printable: boolean;
  type: string;
  parts: readonly SliceModelPart[];
}>;

export type SliceModelObject = SliceModelPart;

export type SliceProjectFilament = Readonly<{
  extruder: number;
  name: string;
  material: string;
  color: string | null;
  global_id?: string;
  unit_id?: string;
  slot_index?: number;
  display_slot?: number;
  tray_id?: string;
  filament_id?: string;
  source?: "ams" | "external_spool" | "profile" | "model";
}>;

export type SlicePurgeTower = Readonly<{
  enabled?: boolean;
  width_mm?: number | null;
  brim_width_mm?: number | null;
  position_x?: number | null;
  position_y?: number | null;
  positions_x?: readonly number[];
  positions_y?: readonly number[];
  flush_multiplier?: number | null;
  flush_volumes_matrix?: readonly unknown[];
  flush_volumes_vector?: readonly unknown[];
}>;

export type SliceModelInspection = Readonly<{
  filename: string;
  format: "stl" | "3mf";
  plate_count: number;
  plates: SliceModelPlate[];
  objects: SliceModelObject[];
  filaments: SliceProjectFilament[];
  purge_tower: SlicePurgeTower;
  multimaterial: boolean;
  used_extruders?: number[];
}>;

export type SlicePlan = Readonly<Record<string, unknown> & { id: string }>;
export type SliceJobStatus = "queued" | "running" | "cancelling" | "succeeded" | "failed" | "cancelled" | "interrupted";

export type SliceAnalysisMaterialShare = Readonly<{
  material_channel_number: number;
  length_mm: number;
  weight_g: number;
}>;

export type SliceAnalysisFeature = Readonly<{
  key: string;
  label: string;
  category: string;
  time_seconds: number;
  time_estimated: boolean;
  length_mm: number;
  volume_cm3: number;
  weight_g: number;
  extrusion_move_count?: number;
  motion_move_count?: number;
  materials?: readonly SliceAnalysisMaterialShare[];
}>;

export type SliceAnalysisMaterialFeature = Readonly<{
  key: string;
  label: string;
  category: string;
  length_mm: number;
  volume_cm3: number;
  weight_g: number;
  extrusion_move_count?: number;
}>;

export type SliceAnalysisMaterial = Readonly<{
  slicer_tool_index: number;
  material_channel_number: number;
  name: string;
  material: string;
  color: string;
  filament_id?: string;
  diameter_mm?: number | null;
  density_g_cm3?: number | null;
  density_source?: string;
  length_mm: number;
  volume_cm3: number;
  weight_g: number;
  weight_source?: string;
  features?: Readonly<Record<string, SliceAnalysisMaterialFeature>>;
}>;

export type SliceTowerSafety = Readonly<{
  present: boolean;
  extrusion_move_count: number;
  bounds: Readonly<{
    min_x: number;
    min_y: number;
    max_x: number;
    max_y: number;
  }> | null;
  inside_plate: boolean;
  source?: string;
}>;

export type SliceGcodeAnalysis = Readonly<{
  schema_version?: number;
  time?: Readonly<{
    total_seconds?: number | null;
    model_seconds?: number | null;
    preparation_seconds?: number | null;
    consistency?: {
      status?: "ok" | "mismatch" | "missing";
      source?: string;
      expected_total_seconds?: number | null;
      delta_seconds?: number | null;
      note?: string;
    } | null;
    feature_time_method?: string;
    feature_time_estimated?: boolean;
  }>;
  layer_count?: number | null;
  physical_extruder_count?: number;
  material_channel_count?: number;
  filament_change_count?: number;
  materials?: readonly SliceAnalysisMaterial[];
  features?: readonly SliceAnalysisFeature[];
  totals?: Readonly<{
    length_mm?: number | null;
    volume_cm3?: number | null;
    weight_g?: number | null;
  }>;
  tower_safety?: SliceTowerSafety;
  estimated_material_values?: boolean;
}>;

export type SliceResult = Readonly<{
  return_code?: number | null;
  error_string?: string | null;
  layer_height_mm?: number | null;
  plate_index?: number | null;
  triangle_count?: number | null;
  print_time_seconds?: number | null;
  model_time_seconds?: number | null;
  preparation_time_seconds?: number | null;
  slice_time_ms?: number | null;
  filament_used_g?: number | null;
  filament_length_mm?: number | null;
  filament_volume_cm3?: number | null;
  layer_count?: number | null;
  filament_change_count?: number | null;
  material_channel_count?: number | null;
  filament_profile?: string | null;
  printer_model?: string | null;
  nozzle_diameter?: number | null;
  warning?: string | null;
  analysis?: SliceGcodeAnalysis | null;
  consumption?: Readonly<Record<string, unknown>> | null;
}>;

export type SliceSlicerProgressEvent = Readonly<{
  at: string;
  epoch?: number;
  plate_index: number;
  plate_count: number;
  plate_percent: number;
  total_percent: number;
  message?: string | null;
  warning?: string | null;
}>;

export type SliceSlicerProgress = Readonly<{
  schema_version?: number;
  source?: string;
  job_id?: string;
  active?: boolean;
  started_at?: string | null;
  updated_at?: string | null;
  last_event_at?: string | null;
  elapsed_seconds?: number | null;
  plate_index?: number;
  plate_count?: number;
  plate_percent?: number;
  total_percent?: number;
  message?: string | null;
  warning?: string | null;
  event_count?: number;
  parse_error_count?: number;
  eta_seconds?: number | null;
  eta_confidence?: string | null;
  history?: readonly SliceSlicerProgressEvent[];
}>;

export type SliceRuntimeFilament = Readonly<Record<string, unknown> & {
  channel?: number;
  name?: string;
  material?: string;
  color?: string;
  ams_slot?: number;
}>;

export type SliceRuntimeSummary = Readonly<{
  schema_version?: number;
  model?: string;
  triangle_count?: number;
  physical_extruder_count?: number;
  material_channel_count?: number;
  requested_plate_index?: number;
  purge_tower?: Readonly<Record<string, unknown>>;
  filaments?: readonly SliceRuntimeFilament[];
  process?: Readonly<Record<string, unknown>>;
  machine?: Readonly<Record<string, unknown>>;
}>;

export type SliceEnginePlateResult = Readonly<Record<string, unknown> & {
  id?: number;
  sliced_time?: number;
  sliced_time_with_cache?: number;
  make_perimeters_time?: number;
  infill_time?: number;
  generate_support_material_time?: number;
  triangle_count?: number;
  warning_message?: string;
  total_predication?: number;
  main_predication?: number;
  filament_change_times?: number;
  feature_type_times?: Readonly<Record<string, number>>;
  objects?: readonly Readonly<Record<string, unknown>>[];
  filaments?: readonly Readonly<Record<string, unknown>>[];
}>;

export type SliceEngineResult = Readonly<Record<string, unknown> & {
  return_code?: number;
  error_string?: string;
  prepare_time?: number;
  export_time?: number;
  layer_height?: number;
  plate_index?: number;
  sparse_infill_density?: number;
  wall_loops?: number;
  sliced_plates?: readonly SliceEnginePlateResult[];
}>;

export type SliceAmsMaterialPlan = Readonly<{
  source?: string;
  target_printer_id?: string;
  assignments?: Readonly<Record<string, number>>;
  filaments?: readonly SliceProjectFilament[];
  purge_tower?: SlicePurgeTower;
}>;

export type SliceProfileApplication = Readonly<{
  selected: boolean;
  applied: boolean;
  gcode_confirmed: boolean;
  process?: Readonly<{
    profile_id?: string;
    name?: string;
    contract_sha256?: string;
    selected_setting_count?: number;
    effective_setting_count?: number;
    numeric_value_proof?: readonly Readonly<{
      key: string;
      label: string;
      unit: string;
      profile_value?: unknown;
      requested_value?: unknown;
      applied_value?: unknown;
      gcode_value?: unknown;
      overridden: boolean;
      status: "confirmed" | "mismatch" | "unverified";
    }>[];
    gcode_confirmed_setting_count?: number;
  }>;
  filament_profile_count?: number;
  material_channel_count?: number;
  confirmation_source?: string;
}>;

export type SliceJob = Readonly<{
  id: string;
  status: SliceJobStatus;
  backend?: SlicerBackend;
  backend_name?: string;
  model_file?: string;
  output_file?: string;
  output_filename?: string;
  output_size_bytes?: number;
  output_sha256?: string;
  return_code?: number;
  error?: string | null;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  updated_at?: string;
  cancel_requested?: boolean;
  cancellation_available?: boolean;
  command_summary?: readonly string[];
  profiles?: Readonly<{
    machine?: string | null;
    process?: string | null;
    filaments?: readonly string[];
    source?: string;
  }>;
  requested_profiles?: Readonly<Record<string, unknown>>;
  slice_result?: SliceResult | null;
  target_printer?: Readonly<{ printer_id?: string; name?: string }>;
  ams_material_plan?: SliceAmsMaterialPlan;
  material_source_plan?: SliceAmsMaterialPlan;
  requested_plate_index?: number;
  slicer_progress?: SliceSlicerProgress;
  runtime_summary?: SliceRuntimeSummary;
  engine_result?: SliceEngineResult;
  profile_application?: SliceProfileApplication;
}>;

export type DirectPrintSlot = Readonly<{
  global_id: string;
  slot_index: number;
  display_slot?: number;
  tray_id: string;
  unit_id?: string;
  material: string;
  sub_brand?: string;
  color: string | null;
  present: boolean;
  active?: boolean;
  remaining_percent?: number | null;
  nozzle_temp_min?: number | null;
  nozzle_temp_max?: number | null;
  bed_temp?: number | null;
}>;

export type DirectPrintPrinter = Readonly<{
  printer_id: string;
  name: string;
  provider: string;
  connection_state: string;
  printer_state: string;
  ready: boolean;
  reason: string | null;
  ams: Readonly<{
    available: boolean;
    slots: DirectPrintSlot[];
  }>;
}>;

export type DirectPrintStatus = Readonly<{
  items: DirectPrintPrinter[];
  two_step_confirmation: boolean;
}>;

export type PreparedDirectPrint = Readonly<{
  token: string;
  job_id: string;
  printer_id: string;
  printer_name: string;
  printer_state: string;
  remote_filename: string;
  size_bytes: number;
  sha256: string;
  gcode_path: string;
  created_at: string;
  expires_at: string;
  requires_final_confirmation: boolean;
  final_confirmation_text: "DRUCKEN";
  ams: Readonly<{
    available: boolean;
    slots: DirectPrintSlot[];
  }>;
}>;

export type DirectPrintTransferStatus = Readonly<{
  job_id: string;
  printer_id: string;
  printer_name: string;
  filename: string;
  loaded_bytes: number;
  total_bytes: number;
  progress: number;
  rate_bytes_per_second: number;
  eta_seconds?: number | null;
  elapsed_seconds?: number | null;
  stage: "preparing" | "connecting" | "uploading" | "verifying" | "completed" | "error";
  stage_label: string;
  active: boolean;
  status: "running" | "success" | "error";
  error?: string | null;
  started_at: string;
  updated_at: string;
}>;

export type DirectPrintStartOptions = Readonly<{
  use_ams: boolean;
  ams_mapping: number[];
  bed_leveling: boolean;
  flow_cali: boolean;
  vibration_cali: boolean;
  timelapse: boolean;
}>;

export type DirectPrintResult = Readonly<{
  printer_id: string;
  provider: string;
  command: "project_file";
  sequence_id: string;
  accepted: boolean;
  remote_filename: string;
}>;

async function responseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as unknown;
    return errorMessage(payload, `API-Anfrage fehlgeschlagen: HTTP ${response.status}`);
  } catch (_error) {
    return `API-Anfrage fehlgeschlagen: HTTP ${response.status}`;
  }
}

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const method = String(init?.method || "GET").toUpperCase() as "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  let parameters: unknown = undefined;
  if (typeof init?.body === "string" && init.body.trim()) {
    try {
      parameters = JSON.parse(init.body) as unknown;
    } catch {
      throw new Error("Die JSON-Anfrage konnte nicht vorbereitet werden.");
    }
  }
  const envelope = await callHomeAssistantApi<{ data?: T; error?: unknown }>(method, path, parameters);
  if (envelope.error) throw new Error(errorMessage(envelope.error));
  if (!("data" in envelope)) throw new Error("Die API hat keine verwertbaren Daten geliefert.");
  return envelope.data as T;
}

export async function fetchSlicerProvider(): Promise<SlicerProvider> {
  return jsonRequest<SlicerProvider>(`${API_PREFIX}/provider`);
}

export async function inspectSliceModel(file: File): Promise<SliceModelInspection> {
  const response = await authenticatedFetch(
    `${API_PREFIX}/inspect?filename=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    },
  );
  if (!response.ok) throw new Error(await responseError(response));
  const payload = await response.json() as { data: SliceModelInspection };
  return payload.data;
}

export async function inspectGallerySliceModel(assetId: string): Promise<SliceModelInspection> {
  const response = await authenticatedFetch(
    `${API_PREFIX}/inspect?gallery_asset_id=${encodeURIComponent(assetId)}`,
    { method: "POST", headers: { Accept: "application/json" } },
  );
  if (!response.ok) throw new Error(await responseError(response));
  const payload = await response.json() as { data: SliceModelInspection };
  return payload.data;
}

export async function uploadSliceGeometry(file: File): Promise<StoredGeometry> {
  const response = await authenticatedFetch(
    `${API_PREFIX}/geometry?filename=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    },
  );
  if (!response.ok) throw new Error(await responseError(response));
  const payload = await response.json() as { data: StoredGeometry };
  return payload.data;
}

export async function createSlicePlan(payload: Readonly<Record<string, unknown>>): Promise<SlicePlan> {
  return jsonRequest<SlicePlan>(`${API_PREFIX}/plans`, { method: "POST", body: JSON.stringify(payload) });
}

export async function listSlicePlans(): Promise<SlicePlan[]> {
  return jsonRequest<SlicePlan[]>(`${API_PREFIX}/plans`);
}

export async function createSliceJob(file: File, plateIndex = 0): Promise<SliceJob> {
  const response = await authenticatedFetch(
    `${API_PREFIX}/jobs?filename=${encodeURIComponent(file.name)}&plate_index=${encodeURIComponent(String(plateIndex))}`,
    { method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file },
  );
  if (!response.ok) throw new Error(await responseError(response));
  const payload = await response.json() as { data: SliceJob };
  return payload.data;
}

export async function fetchSliceJob(jobId: string): Promise<SliceJob> {
  return jsonRequest<SliceJob>(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}`);
}

export async function downloadSliceArtifact(jobId: string): Promise<{ blob: Blob; filename: string; sha256: string | null }> {
  const response = await authenticatedFetch(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/artifact`, { headers: { Accept: "model/3mf,application/octet-stream" } });
  if (!response.ok) throw new Error(await responseError(response));
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return { blob: await response.blob(), filename: match?.[1] ?? `${jobId}.gcode.3mf`, sha256: response.headers.get("X-Content-SHA256") };
}

export async function fetchDirectPrintStatus(): Promise<DirectPrintStatus> {
  return jsonRequest<DirectPrintStatus>(`${API_PREFIX}/direct-print/status`);
}

export async function prepareDirectPrint(jobId: string, printerId: string): Promise<PreparedDirectPrint> {
  return jsonRequest<PreparedDirectPrint>(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/print/prepare`, { method: "POST", body: JSON.stringify({ printer_id: printerId, confirmed: true }) });
}

export async function fetchDirectPrintTransferBaseline(jobId: string, printerId: string): Promise<string> {
  const query = new URLSearchParams({ printer_id: printerId });
  const response = await authenticatedFetch(
    `${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/print/transfer-status?${query}`,
    { method: "GET", cache: "no-store" },
  );
  if (response.status === 404) return "";
  if (!response.ok) throw new Error(await responseError(response));
  const payload = await response.json() as { data?: DirectPrintTransferStatus };
  if (!payload.data || payload.data.job_id !== jobId || payload.data.printer_id !== printerId || !payload.data.started_at) {
    throw new Error("Der vorherige Transferstand konnte nicht eindeutig zugeordnet werden.");
  }
  return payload.data.started_at;
}

export async function fetchDirectPrintTransferStatus(
  jobId: string,
  printerId: string,
): Promise<DirectPrintTransferStatus> {
  return jsonRequest<DirectPrintTransferStatus>(
    `${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/print/transfer-status?printer_id=${encodeURIComponent(printerId)}`,
  );
}

export async function startDirectPrint(prepared: PreparedDirectPrint, options: DirectPrintStartOptions, confirmationText: string): Promise<DirectPrintResult> {
  return jsonRequest<DirectPrintResult>(`${API_PREFIX}/jobs/${encodeURIComponent(prepared.job_id)}/print/start`, {
    method: "POST",
    body: JSON.stringify({ token: prepared.token, printer_id: prepared.printer_id, artifact_sha256: prepared.sha256, confirmation_text: confirmationText, confirmed: true, ...options }),
  });
}

export async function discardPreparedPrint(prepared: PreparedDirectPrint): Promise<Readonly<{ discarded: boolean; remote_deleted: boolean }>> {
  return jsonRequest<Readonly<{ discarded: boolean; remote_deleted: boolean }>>(`${API_PREFIX}/jobs/${encodeURIComponent(prepared.job_id)}/print/discard`, { method: "POST", body: JSON.stringify({ token: prepared.token, confirmed: true }) });
}

export type SlicerQueueStatus = Readonly<{
  total_jobs: number;
  queued_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
}>;

export type BatchCreateJobResult = Readonly<{
  created: number;
  failed: number;
  jobs: SliceJob[];
  errors: string[];
}>;

export async function getQueueStatus(): Promise<SlicerQueueStatus> {
  return jsonRequest<SlicerQueueStatus>(`${API_PREFIX}/queue/status`);
}

export async function batchCreateJobs(
  files: File[],
  plateIndex = 0,
  context?: BatchQueueContext,
  processOverrides?: SliceProcessOverrides,
): Promise<BatchCreateJobResult> {
  if (!context || !processOverrides) throw new Error("Für Batch-Aufträge fehlt die gültige Studio-Profil- und Prozesseinstellung.");
  const formData = new FormData();
  files.forEach((file, index) => {
    formData.append(`files_${index}`, file);
  });
  formData.append('plate_index', String(plateIndex));
  formData.append('auto_release', 'false');
  formData.append("studio_plate", JSON.stringify(context.studio_plate));
  formData.append("material_plan", JSON.stringify(context.material_plan));
  formData.append("process_overrides", JSON.stringify(processOverrides));

  const response = await authenticatedFetch(
    `${API_PREFIX}/jobs/batch`,
    { method: "POST", body: formData },
  );
  if (!response.ok) throw new Error(await responseError(response));
  const payload = await response.json() as { data: BatchCreateJobResult };
  return payload.data;
}

export async function releaseQueueJob(jobId: string): Promise<{ released: boolean }> {
  return jsonRequest<{ released: boolean }>(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/release`, { method: "POST" });
}

export async function releaseAllQueuedJobs(): Promise<{ released: number }> {
  return jsonRequest<{ released: number }>(`${API_PREFIX}/jobs/release-all`, { method: "POST" });
}


export async function cancelSliceJob(jobId: string): Promise<{ status: "cancelling" | "cancelled"; cancel_requested: boolean }> {
  return jsonRequest(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" });
}
