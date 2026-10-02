import type { MeshGeometry } from "./webgl-studio-viewport.js";

export type PaintRegion = Readonly<{
  objectId: string;
  triangleIndices: readonly number[];
  color: string;
  materialKey: string;
  label?: string;
}>;

export type PaintBrush = Readonly<{
  radiusMm: number;
  color: string;
  materialKey?: string;
  label?: string;
  mode: "add" | "remove" | "replace";
}>;

export type PaintResult = Readonly<{
  regions: readonly PaintRegion[];
  paintedTriangleCount: number;
  modified: boolean;
}>;

type PaintMark = Readonly<{ color: string; materialKey: string; label: string }>;
type PaintState = Map<string, Map<number, PaintMark>>;

function paintMark(brush: PaintBrush): PaintMark {
  return {
    color: String(brush.color || "#6b7785").trim() || "#6b7785",
    materialKey: String(brush.materialKey || "").trim(),
    label: String(brush.label || "").trim().slice(0, 64),
  };
}

function regionsFor(objectId: string, objectMap: Map<number, PaintMark>): PaintRegion[] {
  const groups = new Map<string, { color: string; materialKey: string; label: string; triangleIndices: number[] }>();
  for (const [triangleIndex, mark] of objectMap) {
    const key = mark.materialKey + "\u0000" + mark.color + "\u0000" + mark.label;
    const group = groups.get(key) ?? { color: mark.color, materialKey: mark.materialKey, label: mark.label, triangleIndices: [] };
    group.triangleIndices.push(triangleIndex);
    groups.set(key, group);
  }
  return [...groups.values()].map((group) => ({
    objectId,
    color: group.color,
    materialKey: group.materialKey,
    ...(group.label ? { label: group.label } : {}),
    triangleIndices: group.triangleIndices.sort((left, right) => left - right),
  }));
}

export function createPaintSession(): {
  state: PaintState;
  paint: (
    objectId: string,
    geometry: MeshGeometry,
    transformMatrix: readonly number[],
    mouseWorldPos: readonly [number, number, number],
    brush: PaintBrush,
  ) => PaintResult;
  paintTriangles: (objectId: string, triangleIndices: readonly number[], brush: PaintBrush) => PaintResult;
  getRegions: (objectId: string) => readonly PaintRegion[];
  replace: (regions: readonly PaintRegion[]) => void;
  clear: (objectId?: string) => void;
} {
  const state: PaintState = new Map();

  function mapFor(objectId: string): Map<number, PaintMark> {
    const existing = state.get(objectId);
    if (existing) return existing;
    const created = new Map<number, PaintMark>();
    state.set(objectId, created);
    return created;
  }

  function apply(objectId: string, triangleIndices: Iterable<number>, brush: PaintBrush): PaintResult {
    const objectMap = mapFor(objectId);
    const applied: number[] = [];
    const mark = paintMark(brush);
    for (const triangleIndex of new Set(triangleIndices)) {
      if (!Number.isInteger(triangleIndex) || triangleIndex < 0) continue;
      if (brush.mode === "remove") objectMap.delete(triangleIndex);
      else objectMap.set(triangleIndex, mark);
      applied.push(triangleIndex);
    }
    if (objectMap.size === 0) state.delete(objectId);
    const regions = applied.length ? [{
      objectId,
      triangleIndices: applied,
      color: mark.color,
      materialKey: mark.materialKey,
      ...(mark.label ? { label: mark.label } : {}),
    }] : [];
    return { regions, paintedTriangleCount: applied.length, modified: applied.length > 0 };
  }

  function paint(
    objectId: string,
    geometry: MeshGeometry,
    _transformMatrix: readonly number[],
    mouseWorldPos: readonly [number, number, number],
    brush: PaintBrush,
  ): PaintResult {
    const indices: number[] = [];
    const radius2 = Math.max(.01, Number(brush.radiusMm) || 1) ** 2;
    for (let triangle = 0; triangle < geometry.triangleCount; triangle += 1) {
      const base = triangle * 9;
      const cx = (geometry.positions[base]! + geometry.positions[base + 3]! + geometry.positions[base + 6]!) / 3;
      const cy = (geometry.positions[base + 1]! + geometry.positions[base + 4]! + geometry.positions[base + 7]!) / 3;
      const cz = (geometry.positions[base + 2]! + geometry.positions[base + 5]! + geometry.positions[base + 8]!) / 3;
      const dx = cx - mouseWorldPos[0], dy = cy - mouseWorldPos[1], dz = cz - mouseWorldPos[2];
      if (dx * dx + dy * dy + dz * dz <= radius2) indices.push(triangle);
    }
    return apply(objectId, indices, brush);
  }

  function paintTriangles(objectId: string, triangleIndices: readonly number[], brush: PaintBrush): PaintResult {
    return apply(objectId, triangleIndices, brush);
  }

  function getRegions(objectId: string): readonly PaintRegion[] {
    const objectMap = state.get(objectId);
    return objectMap ? regionsFor(objectId, objectMap) : [];
  }

  function replace(regions: readonly PaintRegion[]): void {
    state.clear();
    for (const region of regions) {
      const objectId = String(region.objectId || "").trim();
      if (!objectId) continue;
      const map = mapFor(objectId);
      const color = String(region.color || "#6b7785").trim() || "#6b7785";
      const materialKey = String(region.materialKey || "").trim();
      const label = String(region.label || "").trim().slice(0, 64);
      for (const triangleIndex of new Set(region.triangleIndices || [])) {
        if (Number.isInteger(triangleIndex) && triangleIndex >= 0) map.set(triangleIndex, { color, materialKey, label });
      }
      if (map.size === 0) state.delete(objectId);
    }
  }

  function clear(objectId?: string): void {
    if (objectId) state.delete(objectId); else state.clear();
  }

  return { state, paint, paintTriangles, getRegions, replace, clear };
}
