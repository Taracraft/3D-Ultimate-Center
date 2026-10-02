import { callEnvelopeApi } from "./ha-api-transport.js";

export type ProfileKind = "printer" | "nozzle" | "filament" | "process" | "build_plate";
export type ProfileSource = "builtin" | "local" | "bambu_cloud" | string;

export type V6Profile = Readonly<{
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

export type V6ProfileSelection = Readonly<{
  printer_profile_id: string | null;
  nozzle_profile_id: string | null;
  process_profile_id: string | null;
  build_plate_profile_id: string | null;
  filament_profile_ids: string[];
}>;

export type V6CloudSyncStatus = Readonly<{
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

export type V6ProfileCatalog = Readonly<{
  profiles: V6Profile[];
  groups: Readonly<Record<ProfileKind, V6Profile[]>>;
  selection: V6ProfileSelection;
  persistent: boolean;
  custom_profiles_supported: boolean;
  all_profile_sources_removable?: boolean;
  cloud_sync: V6CloudSyncStatus;
  source_counts: Readonly<{
    builtin: number;
    bambu_cloud: number;
    local: number;
  }>;
}>;

export type V6CloudSyncResult = Readonly<{
  status: V6CloudSyncStatus;
  profile_count: number;
  available_offline: boolean;
}>;

export type V6ProfileSaveRequest = Readonly<{
  id?: string | undefined;
  kind: ProfileKind;
  name: string;
  payload: Record<string, unknown>;
  base_id?: string | null | undefined;
  version?: string | null | undefined;
  origin_profile_id?: string | null | undefined;
}>;

export class ProfileApi {
  readonly #base = "ultimate_3d_studio_v6/v1";

  async getCatalog(): Promise<V6ProfileCatalog> {
    const data = await callEnvelopeApi<V6ProfileCatalog>("GET", `${this.#base}/profiles`);
    if (!data) throw new Error("Leerer Profilkatalog.");
    return data;
  }

  async syncCloudProfiles(): Promise<V6CloudSyncResult> {
    const data = await callEnvelopeApi<V6CloudSyncResult>(
      "POST",
      `${this.#base}/profiles/cloud/sync`,
      { confirmed: true },
    );
    if (!data) throw new Error("Bambu-Cloud-Abgleich hat keine Daten geliefert.");
    return data;
  }

  async saveSelection(selection: Partial<V6ProfileSelection>): Promise<V6ProfileSelection> {
    const data = await callEnvelopeApi<V6ProfileSelection>(
      "POST",
      `${this.#base}/profiles/selection`,
      { ...selection, confirmed: true },
    );
    if (!data) throw new Error("Profilauswahl wurde nicht gespeichert.");
    return data;
  }

  async saveProfile(profile: V6ProfileSaveRequest): Promise<V6Profile> {
    const data = await callEnvelopeApi<V6Profile>(
      "POST",
      `${this.#base}/profiles`,
      { ...profile, confirmed: true },
    );
    if (!data) throw new Error("Profil wurde nicht gespeichert.");
    return data;
  }

  async removeProfile(profileId: string): Promise<V6Profile> {
    const data = await callEnvelopeApi<V6Profile>(
      "POST",
      `${this.#base}/profiles/${encodeURIComponent(profileId)}/remove`,
      { confirmed: true },
    );
    if (!data) throw new Error("Profil wurde nicht entfernt.");
    return data;
  }
}
