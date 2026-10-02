import type { MeshGeometry } from "./webgl-studio-viewport.js";

export type MeshCapResult = Readonly<{
  capPositions: Float32Array;
  capCount: number;
}>;

type VertexKey = string;
type Vec3 = [number, number, number];

function vertexKey(x: number, y: number, z: number): string {
  return `${Math.fround(x)},${Math.fround(y)},${Math.fround(z)}`;
}

function edgeKey(left: string, right: string): string {
  return left < right ? `${left}|${right}` : `${right}|${left}`;
}

function addBoundaryEdge(
  boundary: Map<VertexKey, Set<VertexKey>>,
  left: VertexKey,
  right: VertexKey,
): void {
  if (!boundary.has(left)) boundary.set(left, new Set());
  if (!boundary.has(right)) boundary.set(right, new Set());
  boundary.get(left)!.add(right);
  boundary.get(right)!.add(left);
}

function removeBoundaryEdge(
  boundary: Map<VertexKey, Set<VertexKey>>,
  left: VertexKey,
  right: VertexKey,
): void {
  boundary.get(left)?.delete(right);
  boundary.get(right)?.delete(left);
}

function edgeCount(edges: Map<string, { left: VertexKey; right: VertexKey; count: number }>, left: VertexKey, right: VertexKey): void {
  const key = edgeKey(left, right);
  const existing = edges.get(key);
  if (existing) {
    existing.count += 1;
    return;
  }
  edges.set(key, { left, right, count: 1 });
}

function signedAreaOnAxis(points: readonly Vec3[], axis: "x" | "y" | "z"): number {
  let area = 0;
  for (let index = 0; index < points.length; index++) {
    const current = points[index]!;
    const next = points[(index + 1) % points.length]!;
    const ax = axis === "x" ? current[1] : current[0];
    const ay = axis === "z" ? current[1] : current[2];
    const bx = axis === "x" ? next[1] : next[0];
    const by = axis === "z" ? next[1] : next[2];
    area += ax * by - bx * ay;
  }
  return area / 2;
}

export function generateCapFaces(
  geometry: MeshGeometry,
  axis: "x" | "y" | "z",
): MeshCapResult {
  const positions = geometry.positions;
  const posMap = new Map<VertexKey, Vec3>();
  const edges = new Map<string, { left: VertexKey; right: VertexKey; count: number }>();

  for (let index = 0; index < positions.length; index += 9) {
    const vertices: Vec3[] = [
      [positions[index]!, positions[index + 1]!, positions[index + 2]!],
      [positions[index + 3]!, positions[index + 4]!, positions[index + 5]!],
      [positions[index + 6]!, positions[index + 7]!, positions[index + 8]!],
    ];
    const keys = vertices.map((vertex) => {
      const key = vertexKey(vertex[0], vertex[1], vertex[2]);
      posMap.set(key, vertex);
      return key;
    });
    edgeCount(edges, keys[0]!, keys[1]!);
    edgeCount(edges, keys[1]!, keys[2]!);
    edgeCount(edges, keys[2]!, keys[0]!);
  }

  const boundary = new Map<VertexKey, Set<VertexKey>>();
  for (const edge of edges.values()) {
    if (edge.count === 1) addBoundaryEdge(boundary, edge.left, edge.right);
  }

  const loops: VertexKey[][] = [];
  for (const start of [...boundary.keys()]) {
    while ((boundary.get(start)?.size ?? 0) > 0) {
      const loop: VertexKey[] = [start];
      let current = start;
      let previous: VertexKey | null = null;

      for (let guard = 0; guard < 10000; guard++) {
        const neighbors = [...(boundary.get(current) ?? [])];
        const next = neighbors.find((candidate) => candidate !== previous) ?? neighbors[0];
        if (!next) break;
        removeBoundaryEdge(boundary, current, next);
        if (next === start) break;
        loop.push(next);
        previous = current;
        current = next;
      }

      if (loop.length >= 3) loops.push(loop);
    }
  }

  const capPositions: number[] = [];
  for (const loop of loops) {
    const points = loop.map((key) => posMap.get(key)).filter((point): point is Vec3 => Boolean(point));
    if (points.length < 3) continue;

    // Each cap must oppose the boundary winding of its own half, regardless of axis.
    const firstEdge = edges.get(edgeKey(loop[0]!, loop[1]!));
    const shouldReverse = firstEdge?.left === loop[0];
    const ordered = shouldReverse ? [...points].reverse() : points;
    const origin = ordered[0]!;
    for (let index = 1; index < ordered.length - 1; index++) {
      capPositions.push(
        origin[0], origin[1], origin[2],
        ordered[index]![0], ordered[index]![1], ordered[index]![2],
        ordered[index + 1]![0], ordered[index + 1]![1], ordered[index + 1]![2],
      );
    }
  }

  return {
    capPositions: new Float32Array(capPositions),
    capCount: capPositions.length / 9,
  };
}
