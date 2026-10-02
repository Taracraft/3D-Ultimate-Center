import { authenticatedFetch, callEnvelopeApi } from "./ha-api-transport.js";

export type GalleryItemKind = "folder" | "model";
export type GalleryItem = Readonly<{
  asset_id: string;
  kind: GalleryItemKind;
  name: string;
  title: string;
  path: string;
  relative_path?: string;
  folder_id?: string | null;
  file_name?: string;
  format?: string;
  size_bytes?: number;
  modified?: number;
  updated_at?: number | string;
  preview_url?: string;
  download_url?: string;
  cad_url?: string;
  read_only?: boolean;
}>;
export type GalleryTreeItem = Readonly<{ name: string; path: string; depth: number }>;
export type GalleryStats = Readonly<{ files: number; folders: number; bytes: number }>;
export type GalleryLibrary = Readonly<{
  folder: string;
  parent: string;
  items: GalleryItem[];
  tree: GalleryTreeItem[];
  stats: GalleryStats;
  canonical_root: string;
}>;
export type GalleryImportSummary = Readonly<{
  files: number;
  folders: number;
  bytes: number;
  conflicts: string[];
  imported?: number;
  overwritten?: number;
  verification?: string;
}>;

function responseFilename(response: Response, fallback: string): string {
  const header = response.headers.get("Content-Disposition") || "";
  return header.match(/filename="?([^";]+)"?/i)?.[1] || fallback;
}

export class GalleryApi {
  constructor(private readonly baseUrl = "ultimate_3d_studio_v6/v1") {}

  async list(folder = "", query = "", recursive = false): Promise<GalleryLibrary> {
    const params = new URLSearchParams({ folder, q: query, recursive: recursive ? "1" : "0" });
    const data = await callEnvelopeApi<GalleryLibrary>("GET", `${this.baseUrl}/gallery/manage?${params}`);
    if (!data) throw new Error("Die Galerie hat keine Daten geliefert.");
    return { ...data, items: Array.isArray(data.items) ? data.items : [], tree: Array.isArray(data.tree) ? data.tree : [] };
  }

  async preview(item: GalleryItem): Promise<Blob | null> {
    if (item.kind !== "model") return null;
    const url = item.preview_url || `/api/${this.baseUrl}/gallery/manage/${encodeURIComponent(item.asset_id)}/preview`;
    const response = await authenticatedFetch(url);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Vorschau konnte nicht geladen werden: HTTP ${response.status}`);
    return response.blob();
  }

  async download(item: GalleryItem): Promise<File> {
    if (item.kind !== "model") throw new Error("Ordner können nicht als Modell geladen werden.");
    const url = item.download_url || `/api/${this.baseUrl}/gallery/manage/${encodeURIComponent(item.asset_id)}/download`;
    const response = await authenticatedFetch(url);
    if (!response.ok) throw new Error(`Galeriedatei konnte nicht geladen werden: HTTP ${response.status}`);
    const blob = await response.blob();
    return new File([blob], responseFilename(response, item.file_name || item.name), { type: blob.type || "application/octet-stream" });
  }

  async downloadForCad(item: GalleryItem): Promise<File> {
    if (item.kind !== "model") throw new Error("Ordner können nicht in das CAD-Studio geladen werden.");
    const url = item.cad_url || `/api/${this.baseUrl}/gallery/manage/${encodeURIComponent(item.asset_id)}/model-stl`;
    const response = await authenticatedFetch(url);
    if (!response.ok) {
      let message = `CAD-Geometrie konnte nicht geladen werden: HTTP ${response.status}`;
      try {
        const payload = await response.json() as Readonly<{ error?: Readonly<{ message?: string }> }>;
        if (payload.error?.message) message = payload.error.message;
      } catch {}
      throw new Error(message);
    }
    const blob = await response.blob();
    return new File([blob], responseFilename(response, `${item.title}.stl`), { type: "model/stl" });
  }

  async upload(file: File, folder = "", overwrite = false): Promise<GalleryItem> {
    const params = new URLSearchParams({ filename: file.name, folder, overwrite: overwrite ? "1" : "0", confirmed: "true" });
    const response = await authenticatedFetch(`/api/${this.baseUrl}/gallery/manage/upload?${params}`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    const payload = await response.json() as Readonly<{ data?: GalleryItem; error?: Readonly<{ message?: string }> }>;
    if (!response.ok || !payload.data) throw new Error(payload.error?.message || `Upload fehlgeschlagen: HTTP ${response.status}`);
    return payload.data;
  }

  async createFolder(folder: string, name: string): Promise<GalleryItem> {
    return this.#action("create_folder", { folder, name });
  }

  async rename(path: string, newName: string): Promise<GalleryItem> {
    return this.#action("rename", { path, new_name: newName });
  }

  async move(path: string, targetFolder: string, overwrite = false): Promise<GalleryItem> {
    return this.#action("move", { path, target_folder: targetFolder, overwrite });
  }

  async copy(path: string, targetFolder: string, overwrite = false): Promise<GalleryItem> {
    return this.#action("copy", { path, target_folder: targetFolder, overwrite });
  }

  async remove(path: string): Promise<Readonly<Record<string, unknown>>> {
    return this.#action<Readonly<Record<string, unknown>>>("delete", { path });
  }

  async exportZip(): Promise<File> {
    const response = await authenticatedFetch(`/api/${this.baseUrl}/gallery/manage/transfer/export`);
    if (!response.ok) throw new Error(`Galerieexport fehlgeschlagen: HTTP ${response.status}`);
    const blob = await response.blob();
    return new File([blob], responseFilename(response, "ultimate-3d-studio-v6-gallery.zip"), { type: "application/zip" });
  }

  async inspectImport(file: File): Promise<GalleryImportSummary> {
    return this.#transfer("inspect", file, false, false);
  }

  async importZip(file: File, overwrite = false): Promise<GalleryImportSummary> {
    return this.#transfer("import", file, true, overwrite);
  }

  async #action<T = GalleryItem>(action: string, values: Readonly<Record<string, unknown>>): Promise<T> {
    const data = await callEnvelopeApi<T>("POST", `${this.baseUrl}/gallery/manage/action`, { action, ...values, confirmed: true });
    if (!data) throw new Error("Galerieaktion hat keine Daten geliefert.");
    return data;
  }

  async #transfer(operation: "inspect" | "import", file: File, confirmed: boolean, overwrite: boolean): Promise<GalleryImportSummary> {
    const params = new URLSearchParams({ confirmed: confirmed ? "true" : "false", overwrite: overwrite ? "1" : "0" });
    const response = await authenticatedFetch(`/api/${this.baseUrl}/gallery/manage/transfer/${operation}?${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/zip" },
      body: file,
    });
    const payload = await response.json() as Readonly<{ data?: GalleryImportSummary; error?: Readonly<{ message?: string }> }>;
    if (!response.ok || !payload.data) throw new Error(payload.error?.message || `Galerieimport fehlgeschlagen: HTTP ${response.status}`);
    return payload.data;
  }
}