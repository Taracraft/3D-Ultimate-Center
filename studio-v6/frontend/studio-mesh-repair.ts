import { geometryFromPositions } from "./studio-mesh-tools.js";
import type { MeshGeometry } from "./webgl-studio-viewport.js";

export type MeshRepairReport = Readonly<{
  triangleCount: number;
  validTriangleCount: number;
  nonFiniteTriangleCount: number;
  zeroAreaTriangleCount: number;
  duplicateTriangleCount: number;
  boundaryEdgeCount: number;
  nonManifoldEdgeCount: number;
  repairableTriangleCount: number;
}>;

export type MeshRepairResult = Readonly<{
  geometry: MeshGeometry;
  report: MeshRepairReport;
  changed: boolean;
}>;

function vertexKey(x: number, y: number, z: number): string {
  return `${Math.fround(x)},${Math.fround(y)},${Math.fround(z)}`;
}

function triangleKey(vertices: readonly string[]): string {
  return [...vertices].sort().join("|");
}

function edgeKey(left: string, right: string): string {
  return left < right ? `${left}|${right}` : `${right}|${left}`;
}

function triangleIsZeroArea(values: readonly number[]): boolean {
  const ux = values[3]! - values[0]!;
  const uy = values[4]! - values[1]!;
  const uz = values[5]! - values[2]!;
  const vx = values[6]! - values[0]!;
  const vy = values[7]! - values[1]!;
  const vz = values[8]! - values[2]!;
  const nx = uy * vz - uz * vy;
  const ny = uz * vx - ux * vz;
  const nz = ux * vy - uy * vx;
  return nx === 0 && ny === 0 && nz === 0;
}

function inspectAndCollect(geometry: MeshGeometry): {
  report: MeshRepairReport;
  kept: number[];
} {
  const kept: number[] = [];
  const triangles = new Set<string>();
  const edges = new Map<string, number>();
  let nonFiniteTriangleCount = 0;
  let zeroAreaTriangleCount = 0;
  let duplicateTriangleCount = 0;
  for (let index = 0; index < geometry.positions.length; index += 9) {
    const values = Array.from(geometry.positions.slice(index, index + 9));
    if (values.length !== 9 || values.some((value) => !Number.isFinite(value))) {
      nonFiniteTriangleCount += 1;
      continue;
    }
    if (triangleIsZeroArea(values)) {
      zeroAreaTriangleCount += 1;
      continue;
    }
    const vertices = [
      vertexKey(values[0]!, values[1]!, values[2]!),
      vertexKey(values[3]!, values[4]!, values[5]!),
      vertexKey(values[6]!, values[7]!, values[8]!),
    ];
    const key = triangleKey(vertices);
    if (triangles.has(key)) {
      duplicateTriangleCount += 1;
      continue;
    }
    triangles.add(key);
    kept.push(...values);
    for (const [left, right] of [[0, 1], [1, 2], [2, 0]] as const) {
      const edge = edgeKey(vertices[left]!, vertices[right]!);
      edges.set(edge, (edges.get(edge) ?? 0) + 1);
    }
  }
  let boundaryEdgeCount = 0;
  let nonManifoldEdgeCount = 0;
  for (const count of edges.values()) {
    if (count === 1) boundaryEdgeCount += 1;
    else if (count > 2) nonManifoldEdgeCount += 1;
  }
  const repairableTriangleCount = nonFiniteTriangleCount + zeroAreaTriangleCount + duplicateTriangleCount;
  return {
    kept,
    report: {
      triangleCount: geometry.triangleCount,
      validTriangleCount: kept.length / 9,
      nonFiniteTriangleCount,
      zeroAreaTriangleCount,
      duplicateTriangleCount,
      boundaryEdgeCount,
      nonManifoldEdgeCount,
      repairableTriangleCount,
    },
  };
}

export function analyzeMeshGeometry(geometry: MeshGeometry): MeshRepairReport {
  return inspectAndCollect(geometry).report;
}

export function repairMeshGeometry(geometry: MeshGeometry): MeshRepairResult {
  const { kept, report } = inspectAndCollect(geometry);
  if (!report.repairableTriangleCount) return { geometry, report, changed: false };
  if (!kept.length) return { geometry, report, changed: false };
  return {
    geometry: geometryFromPositions(new Float32Array(kept)),
    report,
    changed: true,
  };
}
