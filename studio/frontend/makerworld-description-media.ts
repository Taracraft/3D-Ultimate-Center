export function safeMediaUrl(value: string): string {
  if (!value.trim()) return "";
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : "";
  } catch (_error) {
    return "";
  }
}

export function descriptionImageUrls(value: string): string[] {
  const urls = new Set<string>();
  const patterns = [
    /<img\b[^>]*\bsrc=["']([^"']+)["']/gi,
    /!\[[^\]]*\]\((https?:\/\/[^)\s]+)\)/gi,
    /(?:(?:https:)?\/\/[^\s"'<>)]*\.(?:png|jpe?g|webp|gif)(?:\?[^\s"'<>)]*)?)/gi,
  ];
  for (const pattern of patterns) {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(value)) !== null) {
      const raw = (match[1] || match[0] || "").trim();
      const normalized = raw.startsWith("//") ? `https:${raw}` : raw;
      const safe = safeMediaUrl(normalized);
      if (safe) urls.add(safe);
    }
  }
  return [...urls];
}

export function missingDescriptionImages(candidates: readonly string[], rendered: Iterable<string | null>): string[] {
  const present = new Set([...rendered].map((value) => safeMediaUrl(value || "")));
  return [...new Set(candidates.map(safeMediaUrl))].filter((value) => value && !present.has(value));
}
