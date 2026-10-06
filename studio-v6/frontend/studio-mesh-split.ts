import { transformPoint } from "./mesh-export.js";
import { generateCapFaces } from "./studio-mesh-cap.js";
import { geometryFromPositions } from "./studio-mesh-tools.js";
import type { MeshGeometry, MeshInstance, Vec3 } from "./webgl-studio-viewport.js";

export type MeshSplitAxis = "x" | "y" | "z";

export type MeshPlaneSplitPreview = Readonly<{
  axis: MeshSplitAxis;
  planeMm: number;
  sourceTriangleCount: number;
  negativeTriangleCount: number;
  positiveTriangleCount: number;
  crossingTriangleCount: number;
  touchingTriangleCount: number;
  canApply: boolean;
  negativeGeometry: MeshGeometry | null;
  positiveGeometry: MeshGeometry | null;
  negativeTriangleIndexMap: ReadonlyMap<number, readonly number[]>;
  positiveTriangleIndexMap: ReadonlyMap<number, readonly number[]>;
}>;

type ClipVertex = Readonly<{
  local: Vec3;
  distance: number;
}>;

function axisIndex(axis: MeshSplitAxis): 0 | 1 | 2 {
  return axis === "x" ? 0 : axis === "y" ? 1 : 2;
}

function vertexKey(point: Vec3): string {
  return `${Math.fround(point[0])},${Math.fround(point[1])},${Math.fround(point[2])}`;
}

function edgeKey(left: string, right: string): string {
  return left < right ? `${left}|${right}` : `${right}|${left}`;
}

function boundaryEdgeCount(positions: Float32Array): number {
  const edges = new Map<string, number>();
  for (let index = 0; index < positions.length; index += 9) {
    const keys = [
      vertexKey([positions[index]!, positions[index + 1]!, positions[index + 2]!]),
      vertexKey([positions[index + 3]!, positions[index + 4]!, positions[index + 5]!]),
      vertexKey([positions[index + 6]!, positions[index + 7]!, positions[index + 8]!]),
    ];
    for (const [left, right] of [[keys[0]!, keys[1]!], [keys[1]!, keys[2]!], [keys[2]!, keys[0]!]] as const) {
      const key = edgeKey(left, right);
      edges.set(key, (edges.get(key) ?? 0) + 1);
    }
  }
  let count = 0;
  for (const value of edges.values()) {
    if (value !== 2) count += 1;
  }
  return count;
}

function interpolate(left: ClipVertex, right: ClipVertex): ClipVertex {
  const denominator = left.distance - right.distance;
  const t = Math.abs(denominator) <= Number.EPSILON ? 0 : left.distance / denominator;
  return {
    distance: 0,
    local: [
      left.local[0] + (right.local[0] - left.local[0]) * t,
      left.local[1] + (right.local[1] - left.local[1]) * t,
      left.local[2] + (right.local[2] - left.local[2]) * t,
    ],
  };
}

function clipPolygon(
  vertices: readonly ClipVertex[],
  keepNegative: boolean,
  epsilonMm: number,
): ClipVertex[] {
  const output: ClipVertex[] = [];
  const inside = (vertex: ClipVertex): boolean => keepNegative
    ? vertex.distance <= epsilonMm
    : vertex.distance >= -epsilonMm;

  for (let index = 0; index < vertices.length; index++) {
    const current = vertices[index]!;
    const next = vertices[(index + 1) % vertices.length]!;
    const currentInside = inside(current);
    const nextInside = inside(next);
    if (currentInside && nextInside) {
      output.push(next);
    } else if (currentInside && !nextInside) {
      output.push(interpolate(current, next));
    } else if (!currentInside && nextInside) {
      output.push(interpolate(current, next), next);
    }
  }
  return output;
}

function triangleAreaSquared(a: Vec3, b: Vec3, c: Vec3): number {
  const ux = b[0] - a[0];
  const uy = b[1] - a[1];
  const uz = b[2] - a[2];
  const vx = c[0] - a[0];
  const vy = c[1] - a[1];
  const vz = c[2] - a[2];
  const nx = uy * vz - uz * vy;
  const ny = uz * vx - ux * vz;
  const nz = ux * vy - uy * vx;
  return nx * nx + ny * ny + nz * nz;
}

function triangulateFan(points: readonly ClipVertex[], target: number[]): void {
  if (points.length < 3) return;
  const origin = points[0]!.local;
  for (let index = 1; index < points.length - 1; index++) {
    const b = points[index]!.local;
    const c = points[index + 1]!.local;
    if (triangleAreaSquared(origin, b, c) <= 1e-12) continue;
    target.push(origin[0], origin[1], origin[2], b[0], b[1], b[2], c[0], c[1], c[2]);
  }
}

function appendCapFaces(target: number[], axis: MeshSplitAxis): void {
  if (target.length < 9) return;
  const geometry = geometryFromPositions(new Float32Array(target));
  const cap = generateCapFaces(geometry, axis);
  target.push(...Array.from(cap.capPositions));
}

export function previewMeshPlaneSplit(
  instance: MeshInstance,
  axis: MeshSplitAxis,
  planeMm: number,
  epsilonMm = 0.000001,
): MeshPlaneSplitPreview {
  const selectedAxis = axisIndex(axis);
  const negative: number[] = [];
  const positive: number[] = [];
  const negativeTriangleIndexMap = new Map<number, readonly number[]>();
  const positiveTriangleIndexMap = new Map<number, readonly number[]>();
  let crossingTriangleCount = 0;
  let touchingTriangleCount = 0;
  let invalidGeometry = !Number.isFinite(planeMm) || !Number.isFinite(epsilonMm) || epsilonMm < 0;
  const positions = instance.geometry.positions;
  invalidGeometry ||= positions.length % 9 !== 0;
  const sourceIsClosed = boundaryEdgeCount(positions) === 0;

  for (let index = 0; index < positions.length; index += 9) {
    const sourceIndex = index / 9;
    negativeTriangleIndexMap.set(sourceIndex, []);
    positiveTriangleIndexMap.set(sourceIndex, []);
    const vertices: ClipVertex[] = [
      [positions[index]!, positions[index + 1]!, positions[index + 2]!] as Vec3,
      [positions[index + 3]!, positions[index + 4]!, positions[index + 5]!] as Vec3,
      [positions[index + 6]!, positions[index + 7]!, positions[index + 8]!] as Vec3,
    ].map((local) => ({
      local,
      distance: transformPoint(local, instance)[selectedAxis] - planeMm,
    }));

    if (vertices.some((vertex) => !Number.isFinite(vertex.distance))) {
      invalidGeometry = true;
      crossingTriangleCount += 1;
      continue;
    }
    if (vertices.some((vertex) => Math.abs(vertex.distance) <= epsilonMm)) {
      touchingTriangleCount += 1;
    }
    if (vertices.every((vertex) => vertex.distance < -epsilonMm)) {
      negativeTriangleIndexMap.set(sourceIndex, [negative.length / 9]);
      negative.push(...positions.slice(index, index + 9));
      continue;
    }
    if (vertices.every((vertex) => vertex.distance > epsilonMm)) {
      positiveTriangleIndexMap.set(sourceIndex, [positive.length / 9]);
      positive.push(...positions.slice(index, index + 9));
      continue;
    }

    crossingTriangleCount += 1;
    const negativeStart = negative.length / 9, positiveStart = positive.length / 9;
    triangulateFan(clipPolygon(vertices, true, epsilonMm), negative);
    triangulateFan(clipPolygon(vertices, false, epsilonMm), positive);
    negativeTriangleIndexMap.set(sourceIndex, Array.from({ length: negative.length / 9 - negativeStart }, (_, offset) => negativeStart + offset));
    positiveTriangleIndexMap.set(sourceIndex, Array.from({ length: positive.length / 9 - positiveStart }, (_, offset) => positiveStart + offset));
  }

  if (sourceIsClosed && crossingTriangleCount > 0) {
    appendCapFaces(negative, axis);
    appendCapFaces(positive, axis);
  }

  // Separating existing groups is safe; newly cut surfaces must be closed on both sides.
  const canApply = !invalidGeometry && negative.length > 0 && positive.length > 0
    && (crossingTriangleCount === 0 || (sourceIsClosed
      && boundaryEdgeCount(new Float32Array(negative)) === 0
      && boundaryEdgeCount(new Float32Array(positive)) === 0));
  return {
    axis,
    planeMm,
    negativeTriangleIndexMap,
    positiveTriangleIndexMap,
    sourceTriangleCount: positions.length / 9,
    negativeTriangleCount: negative.length / 9,
    positiveTriangleCount: positive.length / 9,
    crossingTriangleCount,
    touchingTriangleCount,
    canApply,
    negativeGeometry: canApply ? geometryFromPositions(new Float32Array(negative)) : null,
    positiveGeometry: canApply ? geometryFromPositions(new Float32Array(positive)) : null,
  };
}
