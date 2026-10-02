export type ToolpathSupportKind = "none" | "base" | "interface" | "transition";

export type ToolpathSupportStats = Readonly<{
  present: boolean;
  segmentCount: number;
  interfaceSegmentCount: number;
  firstLayer: number | null;
  lastLayer: number | null;
}>;

export type ToolpathPreviewIndex = Readonly<{
  support: ToolpathSupportStats;
  cumulativeTotalByLayer: ReadonlyMap<number, number>;
  cumulativeSupportByLayer: ReadonlyMap<number, number>;
  layerTotalByLayer: ReadonlyMap<number, number>;
  layerSupportByLayer: ReadonlyMap<number, number>;
  layerHeightByLayer: ReadonlyMap<number, number>;
}>;

export type ToolpathPreviewSampling = Readonly<{
  modelStride: number;
  supportStride: number;
  reduced: boolean;
  estimatedSegments: number;
}>;

type SupportLayerLike = Readonly<{
  index: number;
  z?: number;
  segments: readonly (readonly unknown[])[];
}>;

const kindCache = new Map<string, ToolpathSupportKind>();
const indexCache = new WeakMap<readonly SupportLayerLike[], ToolpathPreviewIndex>();

export function toolpathSupportKind(feature: unknown, category: unknown): ToolpathSupportKind {
  const featureText = String(feature ?? "").toLowerCase();
  const categoryText = String(category ?? "").toLowerCase();
  const cacheKey = categoryText + "\u0000" + featureText;
  const cached = kindCache.get(cacheKey);
  if (cached !== undefined) return cached;
  let kind: ToolpathSupportKind = "none";
  if (categoryText === "support" || featureText.includes("support")) {
    if (featureText.includes("interface") || featureText.includes("contact") || featureText.includes("roof")) kind = "interface";
    else if (featureText.includes("transition") || featureText.includes("bottom")) kind = "transition";
    else kind = "base";
  }
  if (kindCache.size >= 256) kindCache.clear();
  kindCache.set(cacheKey, kind);
  return kind;
}

export function toolpathSupportColor(kind: ToolpathSupportKind): string {
  if (kind === "interface") return "#32d6ff";
  if (kind === "transition") return "#ffd166";
  return "#45e087";
}

export function toolpathSupportLabel(kind: ToolpathSupportKind): string {
  if (kind === "interface") return "Support-Interface";
  if (kind === "transition") return "Support-Übergang";
  return "Supportstruktur";
}

export function toolpathPreviewIndex(layers: readonly SupportLayerLike[]): ToolpathPreviewIndex {
  const cached = indexCache.get(layers);
  if (cached) return cached;
  let total = 0;
  let supportTotal = 0;
  let interfaceSegmentCount = 0;
  let firstLayer: number | null = null;
  let lastLayer: number | null = null;
  let previousZ: number | null = null;
  const cumulativeTotalByLayer = new Map<number, number>();
  const cumulativeSupportByLayer = new Map<number, number>();
  const layerTotalByLayer = new Map<number, number>();
  const layerSupportByLayer = new Map<number, number>();
  const layerHeightByLayer = new Map<number, number>();
  for (const layer of layers) {
    let layerSupport = 0;
    for (const segment of layer.segments) {
      const kind = toolpathSupportKind(segment[7], segment[8]);
      if (kind === "none") continue;
      layerSupport += 1;
      if (kind === "interface") interfaceSegmentCount += 1;
    }
    const layerTotal = layer.segments.length;
    total += layerTotal;
    supportTotal += layerSupport;
    layerTotalByLayer.set(layer.index, layerTotal);
    layerSupportByLayer.set(layer.index, layerSupport);
    cumulativeTotalByLayer.set(layer.index, total);
    cumulativeSupportByLayer.set(layer.index, supportTotal);
    const z = Number(layer.z) || 0;
    const rawHeight = previousZ === null ? z || .2 : z - previousZ;
    layerHeightByLayer.set(layer.index, Math.max(.06, Math.min(.8, rawHeight || .2)));
    previousZ = z;
    if (layerSupport > 0) {
      firstLayer = firstLayer === null ? layer.index : Math.min(firstLayer, layer.index);
      lastLayer = lastLayer === null ? layer.index : Math.max(lastLayer, layer.index);
    }
  }
  const index: ToolpathPreviewIndex = Object.freeze({
    support: Object.freeze({
      present: supportTotal > 0,
      segmentCount: supportTotal,
      interfaceSegmentCount,
      firstLayer,
      lastLayer,
    }),
    cumulativeTotalByLayer,
    cumulativeSupportByLayer,
    layerTotalByLayer,
    layerSupportByLayer,
    layerHeightByLayer,
  });
  indexCache.set(layers, index);
  return index;
}

export function toolpathSupportStats(layers: readonly SupportLayerLike[]): ToolpathSupportStats {
  return toolpathPreviewIndex(layers).support;
}

export function toolpathPreviewCounts(index: ToolpathPreviewIndex, selectedLayer: number, cumulative: boolean): Readonly<{ total: number; support: number }> {
  return cumulative
    ? {
      total: index.cumulativeTotalByLayer.get(selectedLayer) ?? 0,
      support: index.cumulativeSupportByLayer.get(selectedLayer) ?? 0,
    }
    : {
      total: index.layerTotalByLayer.get(selectedLayer) ?? 0,
      support: index.layerSupportByLayer.get(selectedLayer) ?? 0,
    };
}

export function toolpathPreviewSampling(totalSegments: number, supportSegments: number, maximumSegments = 180_000): ToolpathPreviewSampling {
  const total = Math.max(0, Math.floor(Number(totalSegments) || 0));
  const support = Math.max(0, Math.min(total, Math.floor(Number(supportSegments) || 0)));
  const maximum = Math.max(1, Math.floor(Number(maximumSegments) || 1));
  if (total <= maximum) return { modelStride: 1, supportStride: 1, reduced: false, estimatedSegments: total };
  const model = total - support;
  const supportBudget = support > 0 ? Math.min(support, Math.max(24_000, Math.floor(maximum * .45))) : 0;
  const modelBudget = Math.max(1, maximum - supportBudget);
  const supportStride = support > 0 ? Math.max(1, Math.ceil(support / Math.max(1, supportBudget))) : 1;
  const modelStride = model > 0 ? Math.max(1, Math.ceil(model / modelBudget)) : 1;
  return {
    modelStride,
    supportStride,
    reduced: modelStride > 1 || supportStride > 1,
    estimatedSegments: Math.ceil(model / modelStride) + Math.ceil(support / supportStride),
  };
}

export function supportPreviewStride(segmentCount: number, maximumSegments = 160_000): number {
  if (!Number.isFinite(segmentCount) || segmentCount <= 0) return 1;
  if (!Number.isFinite(maximumSegments) || maximumSegments <= 0) return 1;
  return Math.max(1, Math.ceil(segmentCount / maximumSegments));
}