import { authenticatedFetch, callEnvelopeApi } from "./ha-api-transport.js";

export type MakerWorldStats = Readonly<{
  likes: number;
  downloads: number;
  comments: number;
  collects: number;
  prints: number;
}>;

export type MakerWorldPlate = Readonly<{
  id: string;
  index: number;
  name: string;
  thumbnail_url: string | null;
  print_time_seconds: number;
  weight_grams: number;
  filaments: readonly unknown[];
}>;

export type MakerWorldInstance = Readonly<{
  id: string;
  design_id: string;
  title: string;
  description: string;
  thumbnail_url: string | null;
  images: readonly string[];
  is_default: boolean;
  printer_model: string;
  nozzle_diameter: string;
  profile_name: string;
  plates: readonly MakerWorldPlate[];
  plate_count: number;
  download_available: boolean;
}>;

export type MakerWorldDesign = Readonly<{
  id: string;
  title: string;
  description: string;
  creator: string;
  thumbnail_url: string | null;
  images: readonly string[];
  tags: readonly string[];
  stats: MakerWorldStats;
  model_url: string;
  license: string;
  published_at: string;
}>;

export type MakerWorldDetail = MakerWorldDesign & Readonly<{
  instances: readonly MakerWorldInstance[];
  instance_count: number;
}>;

export type MakerWorldBrowseResult = Readonly<{
  items: MakerWorldDesign[];
  query: string;
  nav_key: string;
  offset: number;
  limit: number;
  source_endpoint: string;
  has_more: boolean;
  known_count?: number;
  total_count?: number | null;
}>;

export type MakerWorldSavedItem = Readonly<{
  asset_id: string;
  kind: "model";
  name: string;
  title: string;
  path: string;
  folder_id?: string | null;
}>;

function responseFilename(response: Response, fallback: string): string {
  const value = response.headers.get("Content-Disposition") || "";
  const match = value.match(/filename="?([^";]+)"?/i);
  return match?.[1] || fallback;
}

export class MakerWorldApi {
  readonly #instanceDesignIds = new Map<string, string>();

  constructor(private readonly baseUrl = "ultimate_3d_studio_v6/v1") {}

  async browse(
    query: string | readonly string[] = "",
    navKey = "Trending",
    offset = 0,
    limit = 24,
  ): Promise<MakerWorldBrowseResult> {
    const terms = Array.isArray(query)
      ? query.map((value) => String(value).trim()).filter(Boolean)
      : [];
    const params = new URLSearchParams({
      q: typeof query === "string" ? query : "",
      nav_key: navKey,
      offset: String(offset),
      limit: String(limit),
    });
    for (const term of terms) params.append("term", term);
    const data = await callEnvelopeApi<MakerWorldBrowseResult>(
      "GET",
      `${this.baseUrl}/makerworld/browse?${params.toString()}`,
    );
    if (!data) throw new Error("MakerWorld hat keine Modelle geliefert.");
    return {
      ...data,
      items: Array.isArray(data.items) ? data.items : [],
    };
  }

  async detail(designId: string): Promise<MakerWorldDetail> {
    const data = await callEnvelopeApi<MakerWorldDetail>(
      "GET",
      `${this.baseUrl}/makerworld/design/${encodeURIComponent(designId)}`,
    );
    if (!data) throw new Error("MakerWorld hat keine Modelldetails geliefert.");
    const instances = Array.isArray(data.instances) ? data.instances : [];
    for (const instance of instances) {
      this.#instanceDesignIds.set(instance.id, instance.design_id || data.id || designId);
    }
    return {
      ...data,
      images: Array.isArray(data.images) ? data.images : [],
      tags: Array.isArray(data.tags) ? data.tags : [],
      instances,
    };
  }

  async downloadInstance(
    instanceId: string,
    format: "3mf" | "stl",
    fallbackName: string,
  ): Promise<File> {
    const operation = format === "stl" ? "model-stl" : "download";
    const params = new URLSearchParams({
      design_id: this.#instanceDesignIds.get(instanceId) || "",
      profile_id: instanceId,
    });
    const response = await authenticatedFetch(
      `/api/${this.baseUrl}/makerworld/instance/${encodeURIComponent(instanceId)}/${operation}?${params.toString()}`,
      { method: "GET" },
    );
    if (!response.ok) {
      let message = `MakerWorld-Datei konnte nicht geladen werden: HTTP ${response.status}`;
      try {
        const payload = await response.json() as { error?: { message?: string } };
        if (payload.error?.message) message = payload.error.message;
      } catch (_error) {
        // Keep HTTP fallback.
      }
      throw new Error(message);
    }
    const blob = await response.blob();
    const suffix = format === "stl" ? ".stl" : ".3mf";
    const safeFallback = fallbackName.toLowerCase().endsWith(suffix)
      ? fallbackName
      : `${fallbackName}${suffix}`;
    return new File([blob], responseFilename(response, safeFallback), {
      type: blob.type || (format === "stl" ? "model/stl" : "application/octet-stream"),
    });
  }

  async saveInstance(
    instanceId: string,
    folder: string,
    filename: string,
    overwrite = false,
  ): Promise<MakerWorldSavedItem> {
    const data = await callEnvelopeApi<MakerWorldSavedItem>(
      "POST",
      `${this.baseUrl}/makerworld/instance/${encodeURIComponent(instanceId)}/save`,
      {
        design_id: this.#instanceDesignIds.get(instanceId) || "",
        profile_id: instanceId,
        folder,
        filename,
        overwrite,
        confirmed: true,
      },
    );
    if (!data) throw new Error("MakerWorld-Modell wurde nicht in der Galerie gespeichert.");
    return data;
  }
}