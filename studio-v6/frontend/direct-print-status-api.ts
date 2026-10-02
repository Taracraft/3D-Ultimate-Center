import { callEnvelopeApi } from "./ha-api-transport.js";

const STATUS_PATH = "ultimate_3d_studio_v6/v1/slicer/direct-print/status-detailed";
export const FILAMENT_COLOR_PATH = "ultimate_3d_studio_v6/v1/slicer/filament-color";

export type DetailedAmsSlot = Readonly<{
  global_id: string;
  slot_index: number;
  display_slot: number;
  tray_id: string;
  filament_id: string;
  unit_id: string;
  material: string;
  sub_brand: string;
  color: string | null;
  present: boolean;
  active: boolean;
  remaining_percent: number | null;
  remaining_reliable: boolean;
  weight: number | null;
  diameter: number | null;
  nozzle_temp_min: number | null;
  nozzle_temp_max: number | null;
  bed_temp: number | null;
  tag_uid: string;
  rfid_detected: boolean;
  rfid_status: "detected" | "not_detected";
}>;

export type DetailedExternalSpool = Readonly<{
  available: boolean;
  loaded: boolean;
  entity_id: string | null;
  tray_id: string;
  filament_id: string;
  material: string;
  sub_brand: string;
  color: string | null;
  remaining_percent: number | null;
  remaining_reliable: boolean;
  weight: number | null;
  diameter: number | null;
  nozzle_temp_min: number | null;
  nozzle_temp_max: number | null;
  bed_temp: number | null;
  tag_uid: string;
  rfid_detected: boolean;
  rfid_status: "detected" | "not_detected";
}>;

export type DetailedDirectPrintPrinter = Readonly<{
  printer_id: string;
  name: string;
  provider: string;
  connection_state: string;
  printer_state: string;
  ready: boolean;
  reason: string | null;
  external_spool: DetailedExternalSpool;
  ams: Readonly<{
    available: boolean;
    kind: string | null;
    unit_count: number;
    slot_count: number;
    occupied_slot_count: number;
    slots: DetailedAmsSlot[];
  }>;
}>;

export type ManualA1FilamentProfile = Readonly<{
  id: string;
  name: string;
  vendor: string;
  material_type: string;
  nozzle_temp_min: number;
  nozzle_temp_max: number;
  setting_id: string;
  targets: FilamentSettingTargetKind[];
}>;

export type DetailedDirectPrintStatus = Readonly<{
  items: DetailedDirectPrintPrinter[];
  filament_catalog?: Readonly<{
    source: string;
    version: string;
    items: ManualA1FilamentProfile[];
  }>;
  two_step_confirmation: boolean;
  slot_numbering: string;
  rfid_refresh_mode?: "telemetry_sync";
}>;

export async function fetchDetailedDirectPrintStatus(): Promise<DetailedDirectPrintStatus> {
  const payload = await callEnvelopeApi<DetailedDirectPrintStatus>("GET", STATUS_PATH);
  if (!payload) throw new Error("Direktdruckstatus: Die API hat keine Daten geliefert.");
  return payload;
}


export type ManualA1FilamentType = string;
export type FilamentSettingTargetKind = "external_spool" | "ams_slot";

export type FilamentSettingPreview = Readonly<{
  token: string;
  expires_in_seconds: number;
  printer_id: string;
  target_kind: FilamentSettingTargetKind;
  target_id: string;
  target_label: string;
  current_color: string | null;
  new_color: string;
  current_material: string;
  new_material: ManualA1FilamentType;
  new_filament_id: string;
  new_filament_name: string;
  new_filament_vendor: string;
  confirmation_text: "FARBE SETZEN";
  confirmation_message: string;
}>;

export type FilamentSettingResult = Readonly<{
  printer_id: string;
  provider: string;
  command: "ams_filament_setting";
  sequence_id: string;
  accepted: boolean;
  response_received: boolean;
  target_label: string;
  old_color: string | null;
  new_color: string;
  old_material: string;
  new_material: ManualA1FilamentType;
  new_filament_id: string;
  new_filament_name: string;
  new_filament_vendor: string;
  telemetry_confirmed: boolean;
}>;

export async function previewFilamentSetting(request: Readonly<{
  printer_id: string;
  target_kind: FilamentSettingTargetKind;
  target_id: string;
  color: string;
  filament_id?: string;
  material_type?: ManualA1FilamentType;
}>): Promise<FilamentSettingPreview> {
  const data = await callEnvelopeApi<FilamentSettingPreview>("POST", FILAMENT_COLOR_PATH, {
    ...request,
    confirmed: false,
  });
  if (!data) throw new Error("Die Filamenteinstellung konnte nicht geprüft werden.");
  return data;
}

export async function applyFilamentSetting(token: string): Promise<FilamentSettingResult> {
  const data = await callEnvelopeApi<FilamentSettingResult>("POST", FILAMENT_COLOR_PATH, {
    token,
    confirmed: true,
    confirmation_text: "FARBE SETZEN",
  });
  if (!data) throw new Error("Die Filamenteinstellung wurde vom Drucker nicht bestätigt.");
  return data;
}
