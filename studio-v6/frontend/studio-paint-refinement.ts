import type { MeshGeometry } from "./webgl-studio-viewport.js";
import type { PaintRegion } from "./studio-mesh-paint.js";

export type PaintRefinementOptions = Readonly<{
  targetEdgeMm?: number;
  maxSubdivisions?: number;
}>;

export type PaintRefinementResult = Readonly<{
  positions: Float32Array;
  changed: boolean;
  triangleIndexMap: ReadonlyMap<number, readonly number[]>;
  refinedTriangleCount: number;
}>;

function pointAt(
  a: readonly [number, number, number],
  b: readonly [number, number, number],
  c: readonly [number, number, number],
  i: number,
  j: number,
  subdivisions: number,
): readonly [number, number, number] {
  const inv = 1 / subdivisions;
  const wa = 1 - (i + j) * inv;
  return [
    a[0] * wa + b[0] * i * inv + c[0] * j * inv,
    a[1] * wa + b[1] * i * inv + c[1] * j * inv,
    a[2] * wa + b[2] * i * inv + c[2] * j * inv,
  ];
}

function longestEdge(
  a: readonly [number, number, number],
  b: readonly [number, number, number],
  c: readonly [number, number, number],
): number {
  const length = (left: readonly number[], right: readonly number[]): number =>
    Math.hypot(left[0]! - right[0]!, left[1]! - right[1]!, left[2]! - right[2]!);
  return Math.max(length(a, b), length(b, c), length(c, a));
}

function subdivisionsFor(
  a: readonly [number, number, number],
  b: readonly [number, number, number],
  c: readonly [number, number, number],
  options: PaintRefinementOptions,
): number {
  const target = Math.max(.25, Number(options.targetEdgeMm) || .7);
  const maximum = Math.max(2, Math.min(16, Math.floor(Number(options.maxSubdivisions) || 12)));
  return Math.max(1, Math.min(maximum, Math.ceil(longestEdge(a, b, c) / target)));
}

export function refinePaintGeometry(
  geometry: MeshGeometry,
  triangleIndices: readonly number[],
  options: PaintRefinementOptions = {},
): PaintRefinementResult {
  const requested = new Set(triangleIndices.filter((index) => Number.isInteger(index) && index >= 0 && index < geometry.triangleCount));
  const positions: number[] = [];
  const triangleIndexMap = new Map<number, readonly number[]>();
  let changed = false;
  let refinedTriangleCount = 0;

  for (let triangleIndex = 0; triangleIndex < geometry.triangleCount; triangleIndex += 1) {
    const base = triangleIndex * 9;
    const a: [number, number, number] = [geometry.positions[base]!, geometry.positions[base + 1]!, geometry.positions[base + 2]!];
    const b: [number, number, number] = [geometry.positions[base + 3]!, geometry.positions[base + 4]!, geometry.positions[base + 5]!];
    const c: [number, number, number] = [geometry.positions[base + 6]!, geometry.positions[base + 7]!, geometry.positions[base + 8]!];
    const subdivisions = requested.has(triangleIndex) ? subdivisionsFor(a, b, c, options) : 1;
    const children: number[] = [];
    const add = (first: readonly number[], second: readonly number[], third: readonly number[]): void => {
      children.push(positions.length / 9);
      positions.push(...first, ...second, ...third);
    };

    for (let i = 0; i < subdivisions; i += 1) {
      for (let j = 0; j < subdivisions - i; j += 1) {
        const first = pointAt(a, b, c, i, j, subdivisions);
        const second = pointAt(a, b, c, i + 1, j, subdivisions);
        const third = pointAt(a, b, c, i, j + 1, subdivisions);
        add(first, second, third);
        if (i + j < subdivisions - 1) {
          add(second, pointAt(a, b, c, i + 1, j + 1, subdivisions), third);
        }
      }
    }
    if (subdivisions > 1) {
      changed = true;
      refinedTriangleCount += children.length;
    }
    triangleIndexMap.set(triangleIndex, children);
  }

  return {
    positions: new Float32Array(positions),
    changed,
    triangleIndexMap,
    refinedTriangleCount,
  };
}

export function remapPaintRegions(
  regions: readonly PaintRegion[],
  objectId: string,
  triangleIndexMap: ReadonlyMap<number, readonly number[]>,
): PaintRegion[] {
  return regions.map((region) => {
    if (region.objectId !== objectId) return { ...region, triangleIndices: [...region.triangleIndices] };
    const triangleIndices = [...new Set(region.triangleIndices.flatMap((index) => triangleIndexMap.get(index) ?? [index]))].sort((left, right) => left - right);
    return { ...region, triangleIndices };
  });
}
