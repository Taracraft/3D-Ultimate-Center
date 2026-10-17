import type { MeshGeometry } from "./webgl-studio-viewport.js";
import earcut from "./vendor/earcut/earcut.js";

export type MeshCapResult = Readonly<{ capPositions: Float32Array; capCount: number }>;
type Vec3 = readonly [number, number, number];
type Point2 = readonly [number, number];
type Edge = { left: string; right: string; count: number; direction: number };
const empty = (): MeshCapResult => ({ capPositions: new Float32Array(), capCount: 0 });
const key = (point: Vec3): string => `${Math.fround(point[0])},${Math.fround(point[1])},${Math.fround(point[2])}`;
const edgeKey = (left: string, right: string): string => left < right ? `${left}|${right}` : `${right}|${left}`;
const cross = (a: Point2, b: Point2, c: Point2): number => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
const lengthEpsilon = 1e-10;
const areaEpsilon = 1e-12;

function onSegment(point: Point2, a: Point2, b: Point2): boolean {
  return Math.abs(cross(a, b, point)) <= areaEpsilon
    && point[0] >= Math.min(a[0], b[0]) - lengthEpsilon && point[0] <= Math.max(a[0], b[0]) + lengthEpsilon
    && point[1] >= Math.min(a[1], b[1]) - lengthEpsilon && point[1] <= Math.max(a[1], b[1]) + lengthEpsilon;
}

function segmentsMeet(a: Point2, b: Point2, c: Point2, d: Point2): boolean {
  const abC = cross(a, b, c), abD = cross(a, b, d), cdA = cross(c, d, a), cdB = cross(c, d, b);
  return ((abC > areaEpsilon && abD < -areaEpsilon || abC < -areaEpsilon && abD > areaEpsilon)
    && (cdA > areaEpsilon && cdB < -areaEpsilon || cdA < -areaEpsilon && cdB > areaEpsilon))
    || onSegment(c, a, b) || onSegment(d, a, b) || onSegment(a, c, d) || onSegment(b, c, d);
}

function area(polygon: readonly Point2[]): number {
  const anchor = polygon[0]!;
  let result = 0;
  for (let index = 1; index + 1 < polygon.length; index++) result += cross(anchor, polygon[index]!, polygon[index + 1]!);
  return result / 2;
}

function inside(point: Point2, polygon: readonly Point2[]): boolean {
  let result = false;
  for (let index = 0, previous = polygon.length - 1; index < polygon.length; previous = index++) {
    const a = polygon[index]!, b = polygon[previous]!;
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) result = !result;
  }
  return result;
}

function normal(points: readonly Vec3[]): Vec3 {
  const origin = points[0]!;
  const result: [number, number, number] = [0, 0, 0];
  for (let index = 1; index + 1 < points.length; index++) {
    const a = points[index]!, b = points[index + 1]!;
    const ax = a[0] - origin[0], ay = a[1] - origin[1], az = a[2] - origin[2];
    const bx = b[0] - origin[0], by = b[1] - origin[1], bz = b[2] - origin[2];
    result[0] += ay * bz - az * by; result[1] += az * bx - ax * bz; result[2] += ax * by - ay * bx;
  }
  return result;
}

function triangulate(rings: readonly number[][], points: readonly Point2[]): number[] | null {
  const vertices = rings.flat(), coordinates = vertices.flatMap((index) => [points[index]![0], points[index]![1]]);
  const holeIndices: number[] = [];
  let offset = rings[0]!.length;
  for (let index = 1; index < rings.length; index++) { holeIndices.push(offset); offset += rings[index]!.length; }
  const triangles = earcut(coordinates, holeIndices, 2).map((index) => vertices[index]!);
  if (!triangles.length || triangles.some((index) => !Number.isInteger(index))) return null;
  const orientation = Math.sign(area(rings[0]!.map((index) => points[index]!)));
  for (let index = 0; index < triangles.length; index += 3) {
    const signed = cross(points[triangles[index]!]!, points[triangles[index + 1]!]!, points[triangles[index + 2]!]!);
    if (!Number.isFinite(signed) || signed === 0) return null;
    if (Math.sign(signed) !== orientation) [triangles[index + 1], triangles[index + 2]] = [triangles[index + 2]!, triangles[index + 1]!];
  }
  // Earcut may remove collinear boundary vertices or leave a bridge with a
  // shorter edge on only one side. Make the triangle chain conforming at every
  // original boundary vertex, including vertices already used by another face.
  // Coordinates are reused verbatim; this never invents or snaps a vertex.
  for (const vertex of vertices) {
    const p = points[vertex]!;
    for (let index = 0; index < triangles.length; index += 3) {
      if (triangles.slice(index, index + 3).includes(vertex)) continue;
      for (let edge = 0; edge < 3; edge++) {
        const left = triangles[index + edge]!, right = triangles[index + (edge + 1) % 3]!, third = triangles[index + (edge + 2) % 3]!;
        const a = points[left]!, b = points[right]!;
        if (Math.abs(cross(a, b, p)) > Number.EPSILON * 32 || !onSegment(p, a, b)) continue;
        if (Math.hypot(p[0] - a[0], p[1] - a[1]) <= lengthEpsilon || Math.hypot(p[0] - b[0], p[1] - b[1]) <= lengthEpsilon) return null;
        triangles.splice(index, 3, left, vertex, third, vertex, right, third);
        index += 3;
        break;
      }
    }
  }
  // The oriented triangle chain must have precisely the input boundary, with
  // no missing collinear edges, holes filled, overlapping disks or loose faces.
  const expected = new Map<string, number>(), actual = new Map<string, { count: number; direction: number }>();
  for (const ring of rings) for (let index = 0; index < ring.length; index++) {
    const left = String(ring[index]!), right = String(ring[(index + 1) % ring.length]!);
    expected.set(edgeKey(left, right), left < right ? 1 : -1);
  }
  let triangleArea = 0;
  for (let index = 0; index < triangles.length; index += 3) {
    const signed = cross(points[triangles[index]!]!, points[triangles[index + 1]!]!, points[triangles[index + 2]!]!);
    if (!Number.isFinite(signed) || signed * orientation <= 0) return null;
    triangleArea += Math.abs(signed) / 2;
    for (let edge = 0; edge < 3; edge++) {
      const left = String(triangles[index + edge]!), right = String(triangles[index + (edge + 1) % 3]!);
      const name = edgeKey(left, right), current = actual.get(name) ?? { count: 0, direction: 0 };
      current.count++; current.direction += left < right ? 1 : -1; actual.set(name, current);
    }
  }
  for (const [name, edge] of actual) {
    const boundary = expected.get(name);
    if (boundary === undefined ? edge.count !== 2 || edge.direction !== 0 : edge.count !== 1 || edge.direction !== boundary) return null;
  }
  for (const name of expected.keys()) if (!actual.has(name)) return null;
  const expectedArea = Math.abs(area(rings[0]!.map((index) => points[index]!)))
    - rings.slice(1).reduce((total, ring) => total + Math.abs(area(ring.map((index) => points[index]!))), 0);
  if (expectedArea <= areaEpsilon || Math.abs(triangleArea - expectedArea) > Math.max(expectedArea * 1e-9, Number.EPSILON * triangles.length)) return null;
  return triangles;
}

export function generateCapFaces(geometry: MeshGeometry, _axis: "x" | "y" | "z"): MeshCapResult {
  const positions = geometry.positions;
  if (!positions.length || positions.length % 9 !== 0 || !positions.every(Number.isFinite)) return empty();
  const vertices = new Map<string, Vec3>(), edges = new Map<string, Edge>();
  for (let offset = 0; offset < positions.length; offset += 9) {
    const keys: string[] = [];
    for (let index = 0; index < 9; index += 3) {
      const point: Vec3 = [positions[offset + index]!, positions[offset + index + 1]!, positions[offset + index + 2]!];
      const name = key(point); vertices.set(name, point); keys.push(name);
    }
    if (new Set(keys).size !== 3) return empty();
    for (let edge = 0; edge < 3; edge++) {
      const left = keys[edge]!, right = keys[(edge + 1) % 3]!, name = edgeKey(left, right);
      const current = edges.get(name) ?? { left, right, count: 0, direction: 0 };
      current.count++; current.direction += left < right ? 1 : -1; edges.set(name, current);
    }
  }
  const next = new Map<string, string>(), incoming = new Set<string>();
  for (const edge of edges.values()) {
    if (edge.count !== 1) { if (edge.count !== 2 || edge.direction !== 0) return empty(); continue; }
    // The cap must traverse each source boundary edge in the opposite direction.
    if (next.has(edge.right) || incoming.has(edge.left)) return empty();
    next.set(edge.right, edge.left); incoming.add(edge.left);
  }
  if (!next.size || next.size > 10000 || [...next.keys()].some((name) => !incoming.has(name))) return empty();
  const visited = new Set<string>(), contours: Vec3[][] = [];
  for (const start of next.keys()) {
    if (visited.has(start)) continue;
    const contour: Vec3[] = [];
    let current = start;
    do {
      if (visited.has(current) || contour.length >= 10000) return empty();
      visited.add(current); contour.push(vertices.get(current)!); current = next.get(current)!;
    } while (current !== start);
    if (contour.length < 3) return empty();
    contours.push(contour);
  }
  let plane: Vec3 = [0, 0, 0];
  for (const contour of contours) { const value = normal(contour); if (Math.hypot(...value) > Math.hypot(...plane)) plane = value; }
  const magnitude = Math.hypot(...plane);
  if (!Number.isFinite(magnitude) || magnitude === 0) return empty();
  const axis = Math.abs(plane[0]) > Math.abs(plane[1]) ? (Math.abs(plane[0]) > Math.abs(plane[2]) ? 0 : 2) : (Math.abs(plane[1]) > Math.abs(plane[2]) ? 1 : 2);
  const origin = contours[0]![0]!, flattened = contours.flat();
  let span = 0;
  for (const point of flattened) span = Math.max(span, Math.abs(point[0] - origin[0]), Math.abs(point[1] - origin[1]), Math.abs(point[2] - origin[2]));
  if (!Number.isFinite(span) || span === 0) return empty();
  for (const point of flattened) {
    const distance = ((point[0] - origin[0]) * plane[0] + (point[1] - origin[1]) * plane[1] + (point[2] - origin[2]) * plane[2]) / magnitude;
    if (!Number.isFinite(distance) || Math.abs(distance) > span * 1e-6) return empty();
  }
  const projected = contours.map((contour) => contour.map((point): Point2 => [(point[(axis + 1) % 3]! - origin[(axis + 1) % 3]!) / span, (point[(axis + 2) % 3]! - origin[(axis + 2) % 3]!) / span]));
  const areas = projected.map(area);
  for (let ring = 0; ring < projected.length; ring++) {
    const points = projected[ring]!;
    if (Math.abs(areas[ring]!) <= areaEpsilon) return empty();
    for (let index = 0; index < points.length; index++) {
      const a = points[index]!, b = points[(index + 1) % points.length]!, c = points[(index + 2) % points.length]!;
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) <= lengthEpsilon) return empty();
      if (Math.abs(cross(a, b, c)) <= areaEpsilon && (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0) return empty();
      for (let other = index + 2; other < points.length; other++) {
        if ((other + 1) % points.length === index) continue;
        if (segmentsMeet(a, b, points[other]!, points[(other + 1) % points.length]!)) return empty();
      }
      for (let other = ring + 1; other < projected.length; other++) {
        const candidate = projected[other]!;
        for (let edge = 0; edge < candidate.length; edge++) if (segmentsMeet(a, b, candidate[edge]!, candidate[(edge + 1) % candidate.length]!)) return empty();
      }
    }
  }
  const parents = projected.map((polygon, index) => {
    let parent = -1;
    for (let candidate = 0; candidate < projected.length; candidate++) if (candidate !== index && inside(polygon[0]!, projected[candidate]!)) {
      if (parent < 0 || Math.abs(areas[candidate]!) < Math.abs(areas[parent]!)) parent = candidate;
    }
    return parent;
  });
  const depths = parents.map((_, index) => { let depth = 0, parent = parents[index]!; while (parent >= 0 && depth <= contours.length) { depth++; parent = parents[parent]!; } return depth; });
  if (depths.some((depth) => depth > contours.length)) return empty();
  const outer = depths.findIndex((depth) => depth === 0), orientation = Math.sign(areas[outer]!);
  if (areas.some((value, index) => Math.sign(value) !== (depths[index]! % 2 ? -orientation : orientation))) return empty();
  const points = projected.flat(), rings: number[][] = [];
  let offset = 0;
  for (const contour of contours) { rings.push(Array.from({ length: contour.length }, (_, index) => offset + index)); offset += contour.length; }
  const cap: number[] = [];
  for (let index = 0; index < contours.length; index++) {
    if (depths[index]! % 2) continue;
    const group = [rings[index]!, ...rings.filter((_, child) => parents[child] === index)];
    const triangles = triangulate(group, points);
    if (!triangles) return empty();
    for (const vertex of triangles) cap.push(...flattened[vertex]!);
  }
  return { capPositions: new Float32Array(cap), capCount: cap.length / 9 };
}
