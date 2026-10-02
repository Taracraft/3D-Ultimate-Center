import { callEnvelopeApi } from "./ha-api-transport.js";

const STATUS_PATH = "ultimate_3d_studio_v6/v1/slicer/direct-print/status-detailed";

export type DetailedAmsSlot = Readonly<{
  global_id: string;
  slot_index: number;
  display_slot: number;
  tray_id: string;
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

export type DetailedDirectPrintPrinter = Readonly<{
  printer_id: string;
  name: string;
  provider: string;
  connection_state: string;
  printer_state: string;
  ready: boolean;
  reason: string | null;
  ams: Readonly<{
    available: boolean;
    kind: string | null;
    unit_count: number;
    slot_count: number;
    occupied_slot_count: number;
    slots: DetailedAmsSlot[];
  }>;
}>;

export type DetailedDirectPrintStatus = Readonly<{
  items: DetailedDirectPrintPrinter[];
  two_step_confirmation: boolean;
  slot_numbering: string;
  rfid_refresh_mode?: "telemetry_sync";
}>;

export async function fetchDetailedDirectPrintStatus(): Promise<DetailedDirectPrintStatus> {
  const payload = await callEnvelopeApi<DetailedDirectPrintStatus>("GET", STATUS_PATH);
  if (!payload) throw new Error("Direktdruckstatus: Die API hat keine Daten geliefert.");
  return payload;
}
