import {
  authenticatedFetch,
  errorMessage,
} from "./ha-api-transport.js";
import type { PrinterStorageItem } from "./printer-storage-api.js";

const BASE = "ultimate_3d_studio/v1";

export async function lookupHistoryStorageFile(
  printerId: string,
  filename: string,
): Promise<PrinterStorageItem | null> {
  const requestedPrinter = String(printerId || "").trim();
  const requestedFile = String(filename || "").trim();
  if (!requestedPrinter || !requestedFile) return null;

  const query = new URLSearchParams({ filename: requestedFile });
  const response = await authenticatedFetch(
    `/api/${BASE}/storage/${encodeURIComponent(requestedPrinter)}/lookup?${query}`,
  );
  if (response.status === 404) return null;

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    throw new Error(errorMessage(payload, `HTTP ${response.status}`));
  }

  const envelope = payload as Readonly<{
    data?: PrinterStorageItem;
    error?: unknown;
  }>;
  if (envelope.error || !envelope.data) {
    throw new Error(errorMessage(envelope.error, "Druckerdatei wurde nicht gefunden."));
  }
  return envelope.data;
}
