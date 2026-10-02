import { authenticatedFetch, errorMessage } from "./ha-api-transport.js";

const API_PREFIX = "/api/ultimate_3d_studio_v6/v1/slicer";

export async function fetch3mfPlatePreview(file: File, plateIndex: number): Promise<Blob | null> {
  const response = await authenticatedFetch(
    `${API_PREFIX}/preview?filename=${encodeURIComponent(file.name)}&plate_index=${encodeURIComponent(String(plateIndex))}`,
    {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    },
  );
  if (response.status === 404) return null;
  if (!response.ok) {
    let message = `3MF-Vorschau fehlgeschlagen: HTTP ${response.status}`;
    try { message = errorMessage(await response.json(), message); } catch (_error) { /* response has no JSON body */ }
    throw new Error(message);
  }
  return response.blob();
}
