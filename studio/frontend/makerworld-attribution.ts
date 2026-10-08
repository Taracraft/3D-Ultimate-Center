/** Render only attribution supplied by the model source, without inventing rights. */
export function makerWorldLicenseHtml(license: unknown): string {
  const value = typeof license === "string" ? license.trim() : "";
  const text = value || "Keine Lizenzangabe von MakerWorld. Vor Verwendung auf der Modellseite prüfen.";
  const escaped = text.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
  return `<div class="mw-license"><strong>Lizenz</strong><span>${escaped}</span></div>`;
}
