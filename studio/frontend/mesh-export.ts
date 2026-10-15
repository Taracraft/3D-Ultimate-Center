import { STUDIO_BRANDING } from "./branding.js";
import type { MeshGeometry, Vec3 } from "./webgl-studio-viewport.js";

export type MeshTransform = Readonly<{
  position: readonly [number, number, number];
  rotation: readonly [number, number, number];
  scale: readonly [number, number, number];
}>;

export type ExportMesh = Readonly<{
  name: string;
  geometry: MeshGeometry;
  transform: MeshTransform;
}>;

export type MeshBounds = Readonly<{ min: Vec3; max: Vec3 }>;

const DEG = Math.PI / 180;

function rotateX(point: Vec3, degrees: number): Vec3 {
  const angle = degrees * DEG;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  return [
    point[0],
    point[1] * cosine - point[2] * sine,
    point[1] * sine + point[2] * cosine,
  ];
}

function rotateY(point: Vec3, degrees: number): Vec3 {
  const angle = degrees * DEG;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  return [
    point[0] * cosine + point[2] * sine,
    point[1],
    -point[0] * sine + point[2] * cosine,
  ];
}

function rotateZ(point: Vec3, degrees: number): Vec3 {
  const angle = degrees * DEG;
  const cosine = Math.cos(angle);
  const sine = Math.sin(angle);
  return [
    point[0] * cosine - point[1] * sine,
    point[0] * sine + point[1] * cosine,
    point[2],
  ];
}

export function transformPoint(point: Vec3, transform: MeshTransform): Vec3 {
  const scaled: Vec3 = [
    point[0] * transform.scale[0],
    point[1] * transform.scale[1],
    point[2] * transform.scale[2],
  ];
  const x = rotateX(scaled, transform.rotation[0]);
  const y = rotateY(x, transform.rotation[1]);
  const z = rotateZ(y, transform.rotation[2]);
  return [
    z[0] + transform.position[0],
    z[1] + transform.position[1],
    z[2] + transform.position[2],
  ];
}

function geometryCorners(geometry: MeshGeometry): Vec3[] {
  const [minX, minY, minZ] = geometry.boundsMin;
  const [maxX, maxY, maxZ] = geometry.boundsMax;
  return [
    [minX, minY, minZ], [maxX, minY, minZ],
    [minX, maxY, minZ], [maxX, maxY, minZ],
    [minX, minY, maxZ], [maxX, minY, maxZ],
    [minX, maxY, maxZ], [maxX, maxY, maxZ],
  ];
}

export function transformedBounds(
  geometry: MeshGeometry,
  transform: MeshTransform,
): MeshBounds {
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (const corner of geometryCorners(geometry)) {
    const point = transformPoint(corner, transform);
    for (const axis of [0, 1, 2] as const) {
      min[axis] = Math.min(min[axis], point[axis]);
      max[axis] = Math.max(max[axis], point[axis]);
    }
  }
  return { min, max };
}

export function positionOnBed(
  geometry: MeshGeometry,
  transform: MeshTransform,
): [number, number, number] {
  const bounds = transformedBounds(geometry, transform);
  return [
    transform.position[0],
    transform.position[1],
    transform.position[2] - bounds.min[2],
  ];
}

export function positionCenteredOnPlate(
  geometry: MeshGeometry,
  transform: MeshTransform,
  plateWidth = 256,
  plateDepth = 256,
): [number, number, number] {
  const bounds = transformedBounds(geometry, transform);
  return [
    transform.position[0] + plateWidth / 2 - (bounds.min[0] + bounds.max[0]) / 2,
    transform.position[1] + plateDepth / 2 - (bounds.min[1] + bounds.max[1]) / 2,
    transform.position[2] - bounds.min[2],
  ];
}

export function bestFlatRotation(
  geometry: MeshGeometry,
  scale: readonly [number, number, number],
): [number, number, number] {
  const candidates: Array<[number, number, number]> = [
    [0, 0, 0], [90, 0, 0], [-90, 0, 0],
    [0, 90, 0], [0, -90, 0], [180, 0, 0],
  ];
  let best = candidates[0]!;
  let bestHeight = Infinity;
  let bestFootprint = -Infinity;
  for (const rotation of candidates) {
    const bounds = transformedBounds(geometry, {
      position: [0, 0, 0],
      rotation,
      scale,
    });
    const height = bounds.max[2] - bounds.min[2];
    const footprint = (bounds.max[0] - bounds.min[0]) * (bounds.max[1] - bounds.min[1]);
    if (height < bestHeight - 1e-6 || (Math.abs(height - bestHeight) <= 1e-6 && footprint > bestFootprint)) {
      best = rotation;
      bestHeight = height;
      bestFootprint = footprint;
    }
  }
  return best;
}

function normal(a: Vec3, b: Vec3, c: Vec3): Vec3 {
  const ux = b[0] - a[0];
  const uy = b[1] - a[1];
  const uz = b[2] - a[2];
  const vx = c[0] - a[0];
  const vy = c[1] - a[1];
  const vz = c[2] - a[2];
  const nx = uy * vz - uz * vy;
  const ny = uz * vx - ux * vz;
  const nz = ux * vy - uy * vx;
  const length = Math.hypot(nx, ny, nz) || 1;
  return [nx / length, ny / length, nz / length];
}

export function exportBinaryStl(meshes: readonly ExportMesh[], label: string = STUDIO_BRANDING.exportApplication): ArrayBuffer {
  const triangleCount = meshes.reduce((total, mesh) => total + mesh.geometry.triangleCount, 0);
  if (!triangleCount) throw new Error("Die Szene enthält keine exportierbare Geometrie.");
  const buffer = new ArrayBuffer(84 + triangleCount * 50);
  const bytes = new Uint8Array(buffer);
  const encoded = new TextEncoder().encode(label.slice(0, 80));
  bytes.set(encoded.slice(0, 80), 0);
  const view = new DataView(buffer);
  view.setUint32(80, triangleCount, true);
  let offset = 84;
  for (const mesh of meshes) {
    const positions = mesh.geometry.positions;
    for (let index = 0; index < positions.length; index += 9) {
      const a = transformPoint([positions[index]!, positions[index + 1]!, positions[index + 2]!], mesh.transform);
      const b = transformPoint([positions[index + 3]!, positions[index + 4]!, positions[index + 5]!], mesh.transform);
      const c = transformPoint([positions[index + 6]!, positions[index + 7]!, positions[index + 8]!], mesh.transform);
      const n = normal(a, b, c);
      for (const value of n) {
        view.setFloat32(offset, value, true);
        offset += 4;
      }
      for (const point of [a, b, c]) {
        for (const value of point) {
          view.setFloat32(offset, value, true);
          offset += 4;
        }
      }
      view.setUint16(offset, 0, true);
      offset += 2;
    }
  }
  return buffer;
}
