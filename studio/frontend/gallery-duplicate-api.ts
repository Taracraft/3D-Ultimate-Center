import { authenticatedFetch } from "./ha-api-transport.js";
import { galleryRelativePath, parseGalleryDuplicateReport, type GalleryDuplicateReport } from "./gallery-duplicate-contract.js";

export async function fetchGalleryDuplicates(
  baseUrl: string, folder: string, signal?: AbortSignal,
): Promise<GalleryDuplicateReport> {
  if (!galleryRelativePath(folder, true) || folder.length > 2048) throw new Error("Ungültiger Galerieordner.");
  if (signal?.aborted) throw new DOMException("Duplikatprüfung abgebrochen.", "AbortError");
  const parameters = new URLSearchParams({ folder });
  const options: RequestInit = { method: "GET", cache: "no-store" };
  if (signal) options.signal = signal;
  const response = await authenticatedFetch(`/api/${baseUrl}/gallery/duplicates?${parameters}`, options);
  let body: unknown;
  try { body = await response.json(); }
  catch (error) {
    if (signal?.aborted) throw error;
    throw new Error(response.status === 404
      ? "Die Duplikatprüfung ist auf diesem Server noch nicht verfügbar."
      : `Duplikatprüfung: keine gültige Serverantwort (HTTP ${response.status}).`);
  }
  if (signal?.aborted) throw new DOMException("Duplikatprüfung abgebrochen.", "AbortError");
  const envelope = body !== null && typeof body === "object" && !Array.isArray(body)
    ? body as { data?: unknown; error?: { message?: unknown } | null } : null;
  if (!response.ok || envelope?.error) {
    const message = envelope?.error?.message;
    throw new Error(typeof message === "string" && message.trim()
      ? message.slice(0, 1500) : `Duplikatprüfung fehlgeschlagen (HTTP ${response.status}).`);
  }
  return parseGalleryDuplicateReport(envelope?.data, folder);
}
