import type { MeshGeometry, Vec3 } from "./webgl-studio-viewport.js";

export type LayerSegment = Readonly<{ a: readonly [number, number]; b: readonly [number, number] }>;
export type Segment2 = LayerSegment;

export type GeometryAnalysis = Readonly<{
  triangleCount: number;
  dimensions: readonly [number, number, number];
  boundsMin: Vec3;
  boundsMax: Vec3;
  surfaceAreaMm2: number;
  volumeMm3: number;
  minZ: number;
  maxZ: number;
}>;

function point(positions: Float32Array, offset: number): Vec3 {
  return [positions[offset]!, positions[offset + 1]!, positions[offset + 2]!];
}

function crossLength(a: Vec3, b: Vec3, c: Vec3): number {
  const ux = b[0] - a[0];
  const uy = b[1] - a[1];
  const uz = b[2] - a[2];
  const vx = c[0] - a[0];
  const vy = c[1] - a[1];
  const vz = c[2] - a[2];
  return Math.hypot(
    uy * vz - uz * vy,
    uz * vx - ux * vz,
    ux * vy - uy * vx,
  );
}

export function analyzeGeometry(geometry: MeshGeometry): GeometryAnalysis {
  let area = 0;
  let signedVolume = 0;
  const positions = geometry.positions;
  for (let index = 0; index < positions.length; index += 9) {
    const a = point(positions, index);
    const b = point(positions, index + 3);
    const c = point(positions, index + 6);
    area += crossLength(a, b, c) / 2;
    signedVolume += (
      a[0] * (b[1] * c[2] - b[2] * c[1])
      - a[1] * (b[0] * c[2] - b[2] * c[0])
      + a[2] * (b[0] * c[1] - b[1] * c[0])
    ) / 6;
  }
  return {
    triangleCount: geometry.triangleCount,
    dimensions: [
      geometry.boundsMax[0] - geometry.boundsMin[0],
      geometry.boundsMax[1] - geometry.boundsMin[1],
      geometry.boundsMax[2] - geometry.boundsMin[2],
    ],
    boundsMin: [...geometry.boundsMin] as Vec3,
    boundsMax: [...geometry.boundsMax] as Vec3,
    surfaceAreaMm2: area,
    volumeMm3: Math.abs(signedVolume),
    minZ: geometry.boundsMin[2],
    maxZ: geometry.boundsMax[2],
  };
}

function edgeIntersection(a: Vec3, b: Vec3, z: number, epsilon: number): readonly [number, number] | null {
  const da = a[2] - z;
  const db = b[2] - z;
  if (Math.abs(da) <= epsilon && Math.abs(db) <= epsilon) return null;
  if ((da > epsilon && db > epsilon) || (da < -epsilon && db < -epsilon)) return null;
  if (Math.abs(a[2] - b[2]) <= epsilon) return null;
  const t = (z - a[2]) / (b[2] - a[2]);
  if (t < -epsilon || t > 1 + epsilon) return null;
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}

function samePoint(a: readonly [number, number], b: readonly [number, number], epsilon: number): boolean {
  return Math.abs(a[0] - b[0]) <= epsilon && Math.abs(a[1] - b[1]) <= epsilon;
}

export function sliceSegmentsAtZ(
  geometry: MeshGeometry,
  z: number,
  epsilon = 1e-5,
): LayerSegment[] {
  const result: LayerSegment[] = [];
  const positions = geometry.positions;
  for (let index = 0; index < positions.length; index += 9) {
    const vertices = [point(positions, index), point(positions, index + 3), point(positions, index + 6)] as const;
    const intersections: Array<readonly [number, number]> = [];
    for (const [a, b] of [[vertices[0], vertices[1]], [vertices[1], vertices[2]], [vertices[2], vertices[0]]] as const) {
      const intersection = edgeIntersection(a, b, z, epsilon);
      if (intersection && !intersections.some((item) => samePoint(item, intersection, epsilon))) {
        intersections.push(intersection);
      }
    }
    if (intersections.length === 2 && Math.hypot(
      intersections[1]![0] - intersections[0]![0],
      intersections[1]![1] - intersections[0]![1],
    ) > epsilon) {
      result.push({ a: intersections[0]!, b: intersections[1]! });
    }
  }
  return result;
}

export function layerCount(analysis: GeometryAnalysis, layerHeight: number): number {
  if (!Number.isFinite(layerHeight) || layerHeight <= 0) return 0;
  return Math.max(1, Math.ceil((analysis.maxZ - analysis.minZ) / layerHeight));
}

export function layerZ(analysis: GeometryAnalysis, layerHeight: number, layerIndex: number): number {
  const count = layerCount(analysis, layerHeight);
  const safeIndex = Math.max(0, Math.min(Math.floor(layerIndex), Math.max(0, count - 1)));
  return Math.min(analysis.maxZ, analysis.minZ + layerHeight * (safeIndex + 0.5));
}

export function segmentLength(segments: readonly LayerSegment[]): number {
  return segments.reduce((total, segment) => total + Math.hypot(
    segment.b[0] - segment.a[0],
    segment.b[1] - segment.a[1],
  ), 0);
}

export function drawLayerPreview(
  canvas: HTMLCanvasElement,
  segments: readonly LayerSegment[],
  geometry: MeshGeometry,
): void {
  const width = Math.max(1, Math.floor(canvas.clientWidth * (globalThis.devicePixelRatio || 1)));
  const height = Math.max(1, Math.floor(canvas.clientHeight * (globalThis.devicePixelRatio || 1)));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#050a10";
  context.fillRect(0, 0, width, height);
  const minX = geometry.boundsMin[0];
  const minY = geometry.boundsMin[1];
  const sizeX = Math.max(1e-6, geometry.boundsMax[0] - minX);
  const sizeY = Math.max(1e-6, geometry.boundsMax[1] - minY);
  const padding = 24 * (globalThis.devicePixelRatio || 1);
  const scale = Math.min((width - padding * 2) / sizeX, (height - padding * 2) / sizeY);
  const offsetX = (width - sizeX * scale) / 2;
  const offsetY = (height - sizeY * scale) / 2;
  context.strokeStyle = "#42c8ff";
  context.lineWidth = Math.max(1, 1.25 * (globalThis.devicePixelRatio || 1));
  context.beginPath();
  for (const segment of segments) {
    const ax = offsetX + (segment.a[0] - minX) * scale;
    const ay = height - offsetY - (segment.a[1] - minY) * scale;
    const bx = offsetX + (segment.b[0] - minX) * scale;
    const by = height - offsetY - (segment.b[1] - minY) * scale;
    context.moveTo(ax, ay);
    context.lineTo(bx, by);
  }
  context.stroke();
  context.strokeStyle = "#25425b";
  context.lineWidth = 1;
  context.strokeRect(offsetX, offsetY, sizeX * scale, sizeY * scale);
}