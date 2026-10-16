import { transformedBounds } from "./mesh-export.js";
import type { MeshInstance, Vec3 } from "./webgl-studio-viewport.js";

export type PlateArrangement =
  | Readonly<{ ok: true; instances: MeshInstance[]; movedCount: number }>
  | Readonly<{ ok: false; reason: "invalid_plate" | "invalid_object" | "no_space" | "complexity_limit" }>;

type Rect = Readonly<{ x: number; y: number; width: number; depth: number }>;
type Footprint = Readonly<{ index: number; min: Vec3; width: number; depth: number }>;
const EPSILON = 1e-7;
const MAX_OBJECTS = 2048;
const MAX_FREE_RECTS = 4096;

function finiteVector(value: readonly number[]): boolean {
  return value.length === 3 && value.every(Number.isFinite);
}

function contains(outer: Rect, inner: Rect): boolean {
  return inner.x >= outer.x - EPSILON && inner.y >= outer.y - EPSILON
    && inner.x + inner.width <= outer.x + outer.width + EPSILON
    && inner.y + inner.depth <= outer.y + outer.depth + EPSILON;
}

function overlaps(left: Rect, right: Rect): boolean {
  return left.x < right.x + right.width - EPSILON && left.x + left.width > right.x + EPSILON
    && left.y < right.y + right.depth - EPSILON && left.y + left.depth > right.y + EPSILON;
}

function splitFreeRectangles(free: readonly Rect[], used: Rect): Rect[] | null {
  const split: Rect[] = [];
  for (const area of free) {
    if (!overlaps(area, used)) { split.push(area); continue; }
    const right = area.x + area.width;
    const back = area.y + area.depth;
    if (used.x > area.x + EPSILON) split.push({ ...area, width: used.x - area.x });
    if (used.x + used.width < right - EPSILON) split.push({ ...area, x: used.x + used.width, width: right - used.x - used.width });
    if (used.y > area.y + EPSILON) split.push({ ...area, depth: used.y - area.y });
    if (used.y + used.depth < back - EPSILON) split.push({ ...area, y: used.y + used.depth, depth: back - used.y - used.depth });
  }
  if (split.length > MAX_FREE_RECTS) return null;
  // Free rectangles may overlap each other, but never an allocated footprint.
  return split.filter((area, index) => !split.some((other, otherIndex) =>
    otherIndex !== index && contains(other, area)
      && (!contains(area, other) || otherIndex < index)));
}

function pack(
  footprints: readonly Footprint[], order: readonly number[], width: number,
  depth: number, margin: number, gap: number,
): { positions: Map<number, Rect> } | { failure: "no_space" | "complexity_limit" } {
  // The virtual right/back gap lets actual objects end at the physical margin.
  let free: Rect[] = [{ x: margin, y: margin, width: width - margin * 2 + gap, depth: depth - margin * 2 + gap }];
  const positions = new Map<number, Rect>();
  for (const index of order) {
    const footprint = footprints[index]!;
    const w = footprint.width + gap;
    const d = footprint.depth + gap;
    let best: Rect | undefined;
    let bestShort = Infinity;
    let bestLong = Infinity;
    for (const area of free) {
      if (w > area.width + EPSILON || d > area.depth + EPSILON) continue;
      const shorter = Math.min(area.width - w, area.depth - d);
      const longer = Math.max(area.width - w, area.depth - d);
      if (!best || shorter < bestShort - EPSILON
          || (Math.abs(shorter - bestShort) <= EPSILON && longer < bestLong - EPSILON)
          || (Math.abs(shorter - bestShort) <= EPSILON && Math.abs(longer - bestLong) <= EPSILON
              && (area.y < best.y - EPSILON || (Math.abs(area.y - best.y) <= EPSILON && area.x < best.x)))) {
        best = { x: area.x, y: area.y, width: w, depth: d };
        bestShort = shorter;
        bestLong = longer;
      }
    }
    if (!best) return { failure: "no_space" };
    positions.set(index, best);
    const next = splitFreeRectangles(free, best);
    if (!next) return { failure: "complexity_limit" };
    free = next;
  }
  return { positions };
}

/** Translate only: preserve dimensions, rotations, reflection, mesh/material
 * identity and input order. Conservative transformed bounding boxes are used;
 * this deterministic heuristic does not promise an optimal polygon packing.
 * Invalid/no-space input is not mutated. This is not a sequential-print,
 * support, brim or purge-tower clearance acceptance. */
export function arrangePlateInstances(
  instances: readonly MeshInstance[], width: number, depth: number,
  options: Readonly<{ marginMm?: number; gapMm?: number }> = {},
): PlateArrangement {
  const margin = options.marginMm ?? 12;
  const gap = options.gapMm ?? 8;
  if (![width, depth, margin, gap].every(Number.isFinite) || width <= 0 || depth <= 0
      || margin < 0 || gap < 0 || width <= margin * 2 || depth <= margin * 2
      || !Number.isFinite(width + gap) || !Number.isFinite(depth + gap)) {
    return { ok: false, reason: "invalid_plate" };
  }
  if (instances.length > MAX_OBJECTS) return { ok: false, reason: "complexity_limit" };
  if (!instances.length) return { ok: true, instances: [], movedCount: 0 };
  const ids = new Set<string>();
  const footprints: Footprint[] = [];
  for (const [index, item] of instances.entries()) {
    const mesh = item.geometry;
    if (!item.id || ids.has(item.id) || !finiteVector(item.position) || !finiteVector(item.rotation)
        || !finiteVector(item.scale) || item.scale.some(value => value === 0)
        || !finiteVector(mesh.boundsMin) || !finiteVector(mesh.boundsMax)
        || mesh.boundsMin.some((value, axis) => value > mesh.boundsMax[axis]!)
        || !Number.isInteger(mesh.triangleCount) || mesh.triangleCount <= 0) {
      return { ok: false, reason: "invalid_object" };
    }
    ids.add(item.id);
    const bounds = transformedBounds(mesh, { ...item, position: [0, 0, 0] });
    const w = bounds.max[0] - bounds.min[0];
    const d = bounds.max[1] - bounds.min[1];
    if (!finiteVector(bounds.min) || !finiteVector(bounds.max) || w <= EPSILON || d <= EPSILON) {
      return { ok: false, reason: "invalid_object" };
    }
    if (w > width - margin * 2 + EPSILON || d > depth - margin * 2 + EPSILON) {
      return { ok: false, reason: "no_space" };
    }
    footprints.push({ index, min: bounds.min, width: w, depth: d });
  }
  const sorters = [
    (a: Footprint, b: Footprint) => b.width * b.depth - a.width * a.depth,
    (a: Footprint, b: Footprint) => b.depth - a.depth || b.width - a.width,
    (a: Footprint, b: Footprint) => b.width - a.width || b.depth - a.depth,
  ];
  const attempted = new Set<string>();
  let complexityExceeded = false;
  for (const sorter of sorters) {
    const order = [...footprints].sort((a, b) => sorter(a, b) || a.index - b.index).map(item => item.index);
    const key = order.join(",");
    if (attempted.has(key)) continue;
    attempted.add(key);
    const result = pack(footprints, order, width, depth, margin, gap);
    if ("failure" in result) { complexityExceeded ||= result.failure === "complexity_limit"; continue; }
    const placed = instances.map((item, index): MeshInstance => {
      const area = result.positions.get(index)!;
      const origin = footprints[index]!.min;
      return { ...item, position: [area.x - origin[0], area.y - origin[1], -origin[2]] };
    });
    // Validate the entire proposal before returning any new position.
    const bounds = placed.map(item => transformedBounds(item.geometry, item));
    for (let i = 0; i < bounds.length; i++) {
      const a = bounds[i]!;
      if (a.min[0] < margin - EPSILON || a.min[1] < margin - EPSILON
          || a.max[0] > width - margin + EPSILON || a.max[1] > depth - margin + EPSILON
          || Math.abs(a.min[2]) > EPSILON) return { ok: false, reason: "no_space" };
      for (let j = 0; j < i; j++) {
        const b = bounds[j]!;
        if (!(a.max[0] + gap <= b.min[0] + EPSILON || b.max[0] + gap <= a.min[0] + EPSILON
              || a.max[1] + gap <= b.min[1] + EPSILON || b.max[1] + gap <= a.min[1] + EPSILON)) {
          return { ok: false, reason: "no_space" };
        }
      }
    }
    return { ok: true, instances: placed, movedCount: placed.filter((item, index) =>
      item.position.some((value, axis) => Math.abs(value - instances[index]!.position[axis]!) > EPSILON)).length };
  }
  return { ok: false, reason: complexityExceeded ? "complexity_limit" : "no_space" };
}
