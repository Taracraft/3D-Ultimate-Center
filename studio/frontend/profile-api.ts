import { callEnvelopeApi } from "./ha-api-transport.js";

export type ProfileKind = "printer" | "nozzle" | "filament" | "process" | "build_plate";
export type ProfileSource = "builtin" | "local" | "bambu_cloud" | string;

export type StudioProfile = Readonly<{
  id: string;
  kind: ProfileKind;
  name: string;
  source: ProfileSource;
  payload: Readonly<Record<string, unknown>>;
  builtin: boolean;
  cloud_managed?: boolean;
  cloud_id?: string;
  cloud_type?: string;
  base_id?: string | null | undefined;
  version?: string | null | undefined;
  origin_profile_id?: string | null | undefined;
  created_at: string;
  updated_at: string;
}>;

export type StudioProfileSelection = Readonly<{
  printer_profile_id: string | null;
  nozzle_profile_id: string | null;
  process_profile_id: string | null;
  build_plate_profile_id: string | null;
  filament_profile_ids: string[];
}>;

export type StudioCloudSyncStatus = Readonly<{
  configured: boolean;
  syncing: boolean;
  available_offline: boolean;
  last_sync_at: string | null;
  last_attempt_at: string | null;
  last_error: string | null;
  profile_count: number;
  credential_source: string | null;
  remote_profile_count?: number;
  partial_failures?: number;
}>;

export type StudioProfileCatalog = Readonly<{
  profiles: StudioProfile[];
  groups: Readonly<Record<ProfileKind, StudioProfile[]>>;
  selection: StudioProfileSelection;
  persistent: boolean;
  custom_profiles_supported: boolean;
  all_profile_sources_removable?: boolean;
  cloud_sync: StudioCloudSyncStatus;
  source_counts: Readonly<{
    builtin: number;
    bambu_cloud: number;
    local: number;
  }>;
}>;

export type StudioCloudSyncResult = Readonly<{
  status: StudioCloudSyncStatus;
  profile_count: number;
  available_offline: boolean;
}>;

export type StudioProfileSaveRequest = Readonly<{
  id?: string | undefined;
  kind: ProfileKind;
  name: string;
  payload: Record<string, unknown>;
  base_id?: string | null | undefined;
  version?: string | null | undefined;
  origin_profile_id?: string | null | undefined;
}>;

export class ProfileApi {
  readonly #base = "ultimate_3d_studio/v1";

  async getCatalog(): Promise<StudioProfileCatalog> {
    const data = await callEnvelopeApi<StudioProfileCatalog>("GET", `${this.#base}/profiles`);
    if (!data) throw new Error("Leerer Profilkatalog.");
    return data;
  }

  async syncCloudProfiles(): Promise<StudioCloudSyncResult> {
    const data = await callEnvelopeApi<StudioCloudSyncResult>(
      "POST",
      `${this.#base}/profiles/cloud/sync`,
      { confirmed: true },
    );
    if (!data) throw new Error("Bambu-Cloud-Abgleich hat keine Daten geliefert.");
    return data;
  }

  async saveSelection(selection: Partial<StudioProfileSelection>): Promise<StudioProfileSelection> {
    const data = await callEnvelopeApi<StudioProfileSelection>(
      "POST",
      `${this.#base}/profiles/selection`,
      { ...selection, confirmed: true },
    );
    if (!data) throw new Error("Profilauswahl wurde nicht gespeichert.");
    return data;
  }

  async saveProfile(profile: StudioProfileSaveRequest): Promise<StudioProfile> {
    const data = await callEnvelopeApi<StudioProfile>(
      "POST",
      `${this.#base}/profiles`,
      { ...profile, confirmed: true },
    );
    if (!data) throw new Error("Profil wurde nicht gespeichert.");
    return data;
  }

  async removeProfile(profileId: string): Promise<StudioProfile> {
    const data = await callEnvelopeApi<StudioProfile>(
      "POST",
      `${this.#base}/profiles/${encodeURIComponent(profileId)}/remove`,
      { confirmed: true },
    );
    if (!data) throw new Error("Profil wurde nicht entfernt.");
    return data;
  }
}
