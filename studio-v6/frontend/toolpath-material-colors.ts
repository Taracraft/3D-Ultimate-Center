/** Colors belong to the sliced job, never to the current AMS population. */
export const UNKNOWN_TOOLPATH_COLOR = "#6b7785";
type Layer = Readonly<{ segments: readonly (readonly unknown[])[] }>;
const toolsCache = new WeakMap<readonly Layer[], readonly unknown[]>();

export function normalizeToolpathColor(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const raw = value.trim();
  return /^#?[0-9a-f]{6}(?:[0-9a-f]{2})?$/i.test(raw)
    ? "#" + raw.replace(/^#/, "").slice(0, 6).toLowerCase() : null;
}

export function normalizeToolpathPalette(value: unknown): string[] {
  // Keep empty/invalid positions so later channels never shift to another color.
  return Array.isArray(value) ? Array.from(value, (item) => normalizeToolpathColor(item) ?? "") : [];
}

export function toolpathMaterialColor(palette: readonly unknown[], tool: unknown): string | null {
  if (typeof tool !== "number" || !Number.isSafeInteger(tool) || tool < 0 || tool >= palette.length) return null;
  return normalizeToolpathColor(palette[tool]);
}

export function toolpathPaletteWarning(layers: readonly Layer[], palette: readonly unknown[]): string {
  let tools = toolsCache.get(layers);
  if (!tools) {
    const found = new Set<unknown>();
    for (const layer of layers) for (const segment of layer.segments) found.add(segment[5]);
    tools = [...found]; toolsCache.set(layers, tools);
  }
  const unknown = tools.filter((tool) => toolpathMaterialColor(palette, tool) === null);
  if (!unknown.length) return "";
  const labels = unknown.slice(0, 12).map((tool) => typeof tool === "number" && Number.isSafeInteger(tool) && tool >= 0 && tool < 10000 ? `Kanal ${tool + 1}` : "ungültiger Kanal");
  return `Materialfarbe im Auftrag nicht nachgewiesen: ${labels.join(", ")}${unknown.length > 12 ? " …" : ""}. Grau ist nur eine Kennzeichnung unbekannter Farben, keine Filamentzuordnung.`;
}
