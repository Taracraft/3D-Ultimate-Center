import { createPaintSession, type PaintRegion } from "./studio-mesh-paint.js";
import { refinePaintGeometry, remapPaintRegions } from "./studio-paint-refinement.js";
import type { MeshGeometry } from "./webgl-studio-viewport.js";
import { paintMaskContains, validatePaintMask, type MaterialPaintMask } from "./studio-paint-mask.js";

export type MaterialPaintLayer = Readonly<{
  objectId: string;
  kind: "stroke" | "rectangle" | "circle" | "text";
  label: string;
  color: string;
  materialKey: string;
  radiusMm: number;
  mode?: "add" | "remove";
  mask?: MaterialPaintMask;
  points: readonly Readonly<{ x: number; y: number; z: number; normal?: number[] }>[];
}>;

export function paintLayerMode(layer: MaterialPaintLayer): "add" | "remove" {
  // Old saved eraser strokes have a label but no explicit mode.
  return layer.mode ?? (layer.kind === "stroke" && layer.label === "Radierer" ? "remove" : "add");
}

export function validateOriginalPaintRegions(objectId: string, geometry: MeshGeometry, regions: readonly PaintRegion[]): void {
  if (!Number.isInteger(geometry.triangleCount) || geometry.triangleCount < 0 || geometry.positions.length !== geometry.triangleCount * 9) throw new Error("Das bemalte Modell enthält unvollständige Dreiecke.");
  for (const region of regions) {
    if (region.objectId !== objectId) continue;
    if (region.triangleIndices.some((index) => !Number.isInteger(index) || index < 0 || index >= geometry.triangleCount)) {
      throw new Error("Malbereich verweist auf ein unbekanntes ursprüngliches Dreieck. Das Projekt wurde nicht verändert.");
    }
  }
}

function validateLayer(layer: MaterialPaintLayer): void {
  if (!Number.isFinite(layer.radiusMm) || layer.radiusMm <= 0 || layer.points.length > 50_000 || layer.points.some((point) => ![point.x, point.y, point.z].every(Number.isFinite))) throw new Error("Der Malbereich enthält ungültige oder zu viele Malpunkte.");
  if (layer.points.some((point) => point.normal && (!Array.isArray(point.normal) || point.normal.length !== 3 || point.normal.some((value) => !Number.isFinite(value)) || Math.hypot(...point.normal) < 1e-8))) throw new Error("Der Malbereich enthält eine ungültige Oberflächenrichtung.");
  if (layer.mode !== undefined && layer.mode !== "add" && layer.mode !== "remove") throw new Error("Der gespeicherte Malmodus ist unbekannt.");
  if (layer.mask) validatePaintMask(layer.mask);
}

function layerRadius(layer: MaterialPaintLayer): number {
  return layer.kind === "stroke" ? Math.max(.05, layer.radiusMm) : Math.max(.08, layer.radiusMm * .55);
}

function faceNormal(p: Float32Array, base: number): number[] {
  const ax = p[base + 3]! - p[base]!, ay = p[base + 4]! - p[base + 1]!, az = p[base + 5]! - p[base + 2]!;
  const bx = p[base + 6]! - p[base]!, by = p[base + 7]! - p[base + 1]!, bz = p[base + 8]! - p[base + 2]!;
  return [ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx];
}

function sameSurfaceSide(point: Readonly<{ normal?: number[] }>, normal: readonly number[]): boolean {
  return !point.normal || point.normal[0]! * normal[0]! + point.normal[1]! * normal[1]! + point.normal[2]! * normal[2]! >= 0;
}

/** Derive one plate's visible/exportable paint without changing its saved base or another plate. */
export function composePaintLayers(
  instances: readonly Readonly<{ id: string; geometry: MeshGeometry }>[],
  baseRegions: readonly PaintRegion[],
  layers: readonly MaterialPaintLayer[],
  limits: Readonly<{ maxWork?: number; legacy?: boolean }> = {},
): readonly PaintRegion[] {
  const instancesById = new Map(instances.map((instance) => [instance.id, instance]));
  if (!limits.legacy && layers.length > 512) throw new Error("Die Bemalung überschreitet 512 Ebenen. Bitte das Projekt in kleinere Modelle aufteilen.");
  for (const instance of instances) validateOriginalPaintRegions(instance.id, instance.geometry, baseRegions);
  let remainingWork = limits.legacy ? Infinity : Math.max(1, Math.min(20_000_000, limits.maxWork ?? 20_000_000));
  const spend = (): void => {
    if (--remainingWork < 0) throw new Error("Die Materialflächen überschreiten das Rechenbudget. Malbereich verkleinern oder Modell vereinfachen.");
  };
  const session = createPaintSession();
  session.replace(baseRegions.filter((region) => instancesById.has(region.objectId)));
  for (const layer of layers) {
    const instance = instancesById.get(layer.objectId);
    if (!instance) continue;
    validateLayer(layer);
    const radius = layerRadius(layer);
    const cells = new Map<string, typeof layer.points[number][]>();
    const cell = (value: number): number => Math.floor(value / radius);
    for (const point of layer.points) {
      spend();
      const key = `${cell(point.x)}:${cell(point.y)}:${cell(point.z)}`;
      const bucket = cells.get(key) ?? [];
      bucket.push(point);
      cells.set(key, bucket);
    }
    const triangles: number[] = [];
    for (let triangle = 0; triangle < instance.geometry.triangleCount; triangle += 1) {
      spend();
      const base = triangle * 9, p = instance.geometry.positions;
      const x = (p[base]! + p[base + 3]! + p[base + 6]!) / 3;
      const y = (p[base + 1]! + p[base + 4]! + p[base + 7]!) / 3;
      const z = (p[base + 2]! + p[base + 5]! + p[base + 8]!) / 3;
      if (!limits.legacy && !paintMaskContains(layer.mask, x, y, z)) continue;
      const normal = faceNormal(p, base);
      let inside = false;
      for (let dx = -1; dx <= 1 && !inside; dx += 1) {
        for (let dy = -1; dy <= 1 && !inside; dy += 1) {
          for (let dz = -1; dz <= 1 && !inside; dz += 1) {
            spend();
            inside = (cells.get(`${cell(x) + dx}:${cell(y) + dy}:${cell(z) + dz}`) ?? [])
              .some((point) => { spend(); return (limits.legacy || sameSurfaceSide(point, normal)) && (x - point.x) ** 2 + (y - point.y) ** 2 + (z - point.z) ** 2 <= radius ** 2; });
          }
        }
      }
      if (inside) triangles.push(triangle);
    }
    session.paintTriangles(layer.objectId, triangles, {
      radiusMm: radius, color: layer.color, materialKey: layer.materialKey,
      label: layer.label, mode: limits.legacy ? "add" : paintLayerMode(layer),
    });
  }
  return instances.flatMap((instance) => session.getRegions(instance.id));
}

/** Refine only potentially touched surfaces, preserving all old triangle/material references. */
export function refinePaintLayers(
  objectId: string,
  geometry: MeshGeometry,
  baseRegions: readonly PaintRegion[],
  layers: readonly MaterialPaintLayer[],
  targetEdgeMm = .35,
  limits: Readonly<{ maxWork?: number }> = {},
): Readonly<{ positions: Float32Array; regions: readonly PaintRegion[]; changed: boolean }> {
  // Validate against the ORIGINAL mesh before an index can accidentally become valid after subdivision.
  validateOriginalPaintRegions(objectId, geometry, baseRegions);
  const objectLayers = layers.filter((layer) => layer.objectId === objectId);
  if (objectLayers.length > 512 || objectLayers.reduce((sum, layer) => sum + layer.points.length, 0) > 100_000) throw new Error("Die Bemalung überschreitet das Punktbudget. Bitte das Projekt in kleinere Modelle aufteilen.");
  objectLayers.forEach(validateLayer);
  const points = objectLayers.flatMap((layer) =>
    layer.points.map((point) => ({ ...point, radius: layerRadius(layer) })));
  if (!points.length) return { positions: geometry.positions, regions: baseRegions, changed: false };
  if (!Number.isFinite(targetEdgeMm) || targetEdgeMm < .01) throw new Error("Die Objektskalierung erfordert eine feinere Auflösung als das sichere Raster. Skalierung verringern oder Geometrie vorab passend skalieren.");
  type Point = typeof points[number];
  type Node = { low: number[]; high: number[]; points?: Point[]; children?: Node[] };
  let remainingWork = Math.max(1, Math.min(2_000_000, limits.maxWork ?? 2_000_000));
  const spend = (): void => {
    if (--remainingWork < 0) throw new Error("Feinbemalung ist für diesen Malbereich zu aufwendig. Malbereich verkleinern oder Modell vereinfachen.");
  };
  const build = (items: Point[]): Node => {
    spend();
    const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
    for (const point of items) {
      spend();
      [point.x, point.y, point.z].forEach((value, axis) => {
        low[axis] = Math.min(low[axis]!, value - point.radius);
        high[axis] = Math.max(high[axis]!, value + point.radius);
      });
    }
    if (items.length <= 16) return { low, high, points: items };
    const axis = high.map((value, index) => value - low[index]!).reduce((best, value, index, lengths) => value > lengths[best]! ? index : best, 0);
    const key = (["x", "y", "z"] as const)[axis]!;
    const sorted = [...items].sort((a, b) => a[key] - b[key]);
    const middle = Math.floor(sorted.length / 2);
    return { low, high, children: [build(sorted.slice(0, middle)), build(sorted.slice(middle))] };
  };
  const tree = build(points);
  const touches = (node: Node, low: number[], high: number[], normal: number[]): boolean => {
    spend();
    if (low.some((value, axis) => value > node.high[axis]! || high[axis]! < node.low[axis]!)) return false;
    if (node.children) return node.children.some((child) => touches(child, low, high, normal));
    return node.points!.some((point) => {
      spend();
      return sameSurfaceSide(point, normal) && [point.x, point.y, point.z].reduce((sum, value, axis) => sum + Math.max(low[axis]! - value, 0, value - high[axis]!) ** 2, 0) <= point.radius ** 2;
    });
  };
  let current = geometry;
  let regions = baseRegions;
  let changed = false;
  const target = targetEdgeMm;
  for (let pass = 0; pass < 16; pass += 1) {
    const touched: number[] = [];
    for (let triangle = 0; triangle < current.triangleCount; triangle += 1) {
      spend();
      const base = triangle * 9;
      const vertices = [0, 3, 6].map((offset) => [current.positions[base + offset]!, current.positions[base + offset + 1]!, current.positions[base + offset + 2]!]);
      const longest = Math.max(...vertices.map((a, index) => {
        const b = vertices[(index + 1) % 3]!;
        return Math.hypot(a[0]! - b[0]!, a[1]! - b[1]!, a[2]! - b[2]!);
      }));
      if (longest <= target * 1.00001) continue;
      const low = [0, 1, 2].map((axis) => Math.min(...vertices.map((v) => v[axis]!)));
      const high = [0, 1, 2].map((axis) => Math.max(...vertices.map((v) => v[axis]!)));
      if (touches(tree, low, high, faceNormal(current.positions, base))) touched.push(triangle);
    }
    if (!touched.length) return { positions: current.positions, regions, changed };
    // Do not partially replace the mesh when a paint operation exceeds the interactive budget.
    if (current.triangleCount + touched.length * 3 > 250_000) throw new Error("Feinbemalung überschreitet 250.000 Dreiecke. Malbereich verkleinern oder Modell vereinfachen.");
    const refined = refinePaintGeometry(current, touched, { targetEdgeMm: target, maxSubdivisions: 2, maxTriangles: 250_000 });
    regions = remapPaintRegions(regions, objectId, refined.triangleIndexMap);
    current = { ...current, positions: refined.positions, triangleCount: refined.positions.length / 9 };
    changed = true;
  }
  throw new Error("Feinbemalung konnte die benötigte Auflösung nicht erreichen.");
}
