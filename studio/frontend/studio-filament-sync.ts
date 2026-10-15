import type { DetailedExternalSpool } from "./direct-print-status-api.js";

export function filamentSyncError(
  source: "ams" | "external_spool",
  external: Pick<DetailedExternalSpool, "available" | "loaded"> | null | undefined,
  occupiedAmsSlots: number,
): string | null {
  if (source === "external_spool") {
    return external?.available || external?.loaded ? null : "Keine Telemetrie der externen Spule verfügbar.";
  }
  return occupiedAmsSlots > 0 ? null : "Keine belegten AMS-Slots erkannt.";
}

export function filamentSyncActionsHtml(loading: boolean, error: string): string {
  const safeError = error.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
  return `<button id="sync-filaments" ${loading ? "disabled" : ""}>${loading ? "Filamente werden synchronisiert …" : "Filamente synchronisieren"}</button><button id="remove-model-colors" ${loading ? "disabled" : ""}>Projektfarben zurücksetzen</button>${safeError ? `<span class="error-box">${safeError}</span>` : ""}`;
}
