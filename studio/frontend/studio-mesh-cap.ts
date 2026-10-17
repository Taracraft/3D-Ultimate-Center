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

type Point2 = readonly [number, number];

function contourProjectionAxis(points: readonly Vec3[]): 0 | 1 | 2 | null {
  const normal = [0, 0, 0];
  for (let index = 0; index < points.length; index++) {
    const a = points[index]!, b = points[(index + 1) % points.length]!;
    normal[0]! += (a[1] - b[1]) * (a[2] + b[2]);
    normal[1]! += (a[2] - b[2]) * (a[0] + b[0]);
    normal[2]! += (a[0] - b[0]) * (a[1] + b[1]);
  }
  const axis = Math.abs(normal[0]!) > Math.abs(normal[1]!)
    ? (Math.abs(normal[0]!) > Math.abs(normal[2]!) ? 0 : 2)
    : (Math.abs(normal[1]!) > Math.abs(normal[2]!) ? 1 : 2);
  if (!Number.isFinite(normal[axis]) || normal[axis] === 0) return null;
  return axis;
}

function insideContour(point: Point2, polygon: readonly Point2[]): boolean {
  let inside = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const a = polygon[index]!, b = polygon[previous]!;
    if ((a[1] > point[1]) !== (b[1] > point[1])
      && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

// A triangle fan can fill only a convex contour without holes. Reject the
// unsupported case instead of producing overlapping disks over a cut-out.
function fanContoursSupported(contours: readonly Vec3[][]): boolean {
  for (let index = 0; index < contours.length; index++) {
    const points = contours[index]!, axis = contourProjectionAxis(points);
    if (axis === null) return false;
    const project = (point: Vec3): Point2 => axis === 0 ? [point[1], point[2]] : axis === 1 ? [point[0], point[2]] : [point[0], point[1]];
    const projected = points.map(project);
    let direction = 0;
    const span = Math.max(...projected.map((point) => point[0])) - Math.min(...projected.map((point) => point[0]));
    const height = Math.max(...projected.map((point) => point[1])) - Math.min(...projected.map((point) => point[1]));
    const tolerance = Math.max(span * span, height * height) * 1e-6;
    for (let vertex = 0; vertex < projected.length; vertex++) {
      const a = projected[vertex]!, b = projected[(vertex + 1) % projected.length]!, c = projected[(vertex + 2) % projected.length]!;
      const cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
      if (Math.abs(cross) <= tolerance) continue;
      if (direction && Math.sign(cross) !== direction) return false;
      direction = Math.sign(cross);
    }
    if (!direction) return false;
    for (let other = 0; other < contours.length; other++) {
      if (other === index) continue;
      // Use this contour's dominant projection for both loops, including
      // rotated models where the world split axis is not a local mesh axis.
      if (insideContour(project(contours[other]![0]!), projected)) return false;
    }
  }
  return true;
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

  if ([...boundary.values()].some((neighbors) => neighbors.size !== 2)) return { capPositions: new Float32Array(), capCount: 0 };

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

  const contours = loops.map((loop) => loop.map((key) => posMap.get(key)!).filter(Boolean));
  if (!fanContoursSupported(contours)) return { capPositions: new Float32Array(), capCount: 0 };

  const capPositions: number[] = [];
  for (const [contour, loop] of loops.entries()) {
    const points = contours[contour]!;
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
