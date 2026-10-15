import type { MeshGeometry, Vec3 } from "./webgl-studio-viewport.js";

export type PrimitiveKind = "cube" | "cylinder" | "sphere" | "cone" | "torus" | "plate" | "first-layer";

type Builder = { positions: number[]; normals: number[] };

function sub(a: Vec3, b: Vec3): Vec3 { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cross(a: Vec3, b: Vec3): Vec3 { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function normalize(a: Vec3): Vec3 { const length = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / length, a[1] / length, a[2] / length]; }

function triangle(builder: Builder, a: Vec3, b: Vec3, c: Vec3): void {
  const normal = normalize(cross(sub(b, a), sub(c, a)));
  builder.positions.push(...a, ...b, ...c);
  builder.normals.push(...normal, ...normal, ...normal);
}

function quad(builder: Builder, a: Vec3, b: Vec3, c: Vec3, d: Vec3): void {
  triangle(builder, a, b, c);
  triangle(builder, a, c, d);
}

function finish(builder: Builder): MeshGeometry {
  const positions = new Float32Array(builder.positions);
  const normals = new Float32Array(builder.normals);
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let index = 0; index < positions.length; index += 3) {
    min[0] = Math.min(min[0], positions[index]!);
    min[1] = Math.min(min[1], positions[index + 1]!);
    min[2] = Math.min(min[2], positions[index + 2]!);
    max[0] = Math.max(max[0], positions[index]!);
    max[1] = Math.max(max[1], positions[index + 1]!);
    max[2] = Math.max(max[2], positions[index + 2]!);
  }
  return Object.freeze({ positions, normals, triangleCount: positions.length / 9, boundsMin: min, boundsMax: max });
}

function box(width: number, depth: number, height: number): MeshGeometry {
  const b: Builder = { positions: [], normals: [] };
  const x = width / 2, y = depth / 2, z = height;
  const p: Vec3[] = [[-x,-y,0],[x,-y,0],[x,y,0],[-x,y,0],[-x,-y,z],[x,-y,z],[x,y,z],[-x,y,z]];
  quad(b,p[0]!,p[3]!,p[2]!,p[1]!); quad(b,p[4]!,p[5]!,p[6]!,p[7]!);
  quad(b,p[0]!,p[1]!,p[5]!,p[4]!); quad(b,p[1]!,p[2]!,p[6]!,p[5]!);
  quad(b,p[2]!,p[3]!,p[7]!,p[6]!); quad(b,p[3]!,p[0]!,p[4]!,p[7]!);
  return finish(b);
}

function cylinder(radius: number, height: number, segments = 64, topRadius = radius): MeshGeometry {
  const b: Builder = { positions: [], normals: [] };
  const bottom: Vec3 = [0, 0, 0], top: Vec3 = [0, 0, height];
  for (let index = 0; index < segments; index += 1) {
    const a0 = index * Math.PI * 2 / segments;
    const a1 = (index + 1) * Math.PI * 2 / segments;
    const b0: Vec3 = [Math.cos(a0) * radius, Math.sin(a0) * radius, 0];
    const b1: Vec3 = [Math.cos(a1) * radius, Math.sin(a1) * radius, 0];
    const t0: Vec3 = [Math.cos(a0) * topRadius, Math.sin(a0) * topRadius, height];
    const t1: Vec3 = [Math.cos(a1) * topRadius, Math.sin(a1) * topRadius, height];
    triangle(b, bottom, b1, b0);
    if (topRadius > 0) triangle(b, top, t0, t1);
    if (topRadius === 0) triangle(b, b0, b1, top);
    else quad(b, b0, b1, t1, t0);
  }
  return finish(b);
}

function sphere(radius: number, latitude = 32, longitude = 48): MeshGeometry {
  const b: Builder = { positions: [], normals: [] };
  const point = (lat: number, lon: number): Vec3 => {
    const phi = Math.PI * lat / latitude;
    const theta = Math.PI * 2 * lon / longitude;
    return [radius * Math.sin(phi) * Math.cos(theta), radius * Math.sin(phi) * Math.sin(theta), radius * (1 - Math.cos(phi))];
  };
  for (let lat = 0; lat < latitude; lat += 1) {
    for (let lon = 0; lon < longitude; lon += 1) {
      const a = point(lat, lon), b0 = point(lat, lon + 1), c = point(lat + 1, lon + 1), d = point(lat + 1, lon);
      if (lat > 0) triangle(b, a, b0, c);
      if (lat < latitude - 1) triangle(b, a, c, d);
    }
  }
  return finish(b);
}

function torus(majorRadius: number, tubeRadius: number, majorSegments = 64, tubeSegments = 24): MeshGeometry {
  const b: Builder = { positions: [], normals: [] };
  const point = (major: number, tube: number): Vec3 => {
    const a = Math.PI * 2 * major / majorSegments;
    const t = Math.PI * 2 * tube / tubeSegments;
    const ring = majorRadius + tubeRadius * Math.cos(t);
    return [ring * Math.cos(a), ring * Math.sin(a), tubeRadius + tubeRadius * Math.sin(t)];
  };
  for (let major = 0; major < majorSegments; major += 1) {
    for (let tube = 0; tube < tubeSegments; tube += 1) {
      quad(b, point(major,tube), point(major + 1,tube), point(major + 1,tube + 1), point(major,tube + 1));
    }
  }
  return finish(b);
}

export function firstLayerParameters(nozzleDiameter: number): { height: number; lineWidth: number } {
  if (![0.2, 0.4, 0.6, 0.8].some((diameter) => Math.abs(diameter - nozzleDiameter) < 1e-6)) {
    throw new Error("Für den First-Layer-Test zuerst eine unterstützte Düse auswählen.");
  }
  return { height: Math.round(nozzleDiameter * 70) / 100, lineWidth: Math.round(nozzleDiameter * 150) / 100 };
}

function firstLayer(width: number, depth: number, nozzleDiameter: number): MeshGeometry {
  const { height, lineWidth } = firstLayerParameters(nozzleDiameter);
  if (![width, depth].every((value) => Number.isFinite(value) && value >= 120 && value <= 1000)) {
    throw new Error("Ungültige Druckbettgröße für den First-Layer-Test.");
  }
  // Keep the physical edge and the native purge/wipe area clear. The selected
  // printer/plate contract remains authoritative during slicing.
  const margin = 5;
  const halfX = width / 2 - margin, halfY = depth / 2 - margin;
  const logoHalf = Math.min(width, depth) * 0.28;
  const stemHalf = logoHalf * 0.4;
  const shoulder = logoHalf * 0.48;
  const band = Math.max(0.8, lineWidth * 2);
  const offsets = Array.from({ length: 8 }, (_, index) => index * band);
  if (offsets[7]! >= stemHalf || shoulder + 2 * offsets[7]! >= logoHalf) throw new Error("Druckbett zu klein für drei druckbare T-Konturen mit dieser Düse.");
  const insideT = (x: number, y: number, inset: number): boolean =>
    y > -logoHalf + inset && y < logoHalf - inset
    && (Math.abs(x) < stemHalf - inset || (Math.abs(x) < logoHalf - inset && y > shoulder + inset));
  // Four empty T-shaped grooves isolate exactly three solid contour bands.
  // The central T and the surrounding sheet remain filled calibration areas.
  const filled = (x: number, y: number): boolean => {
    if (!insideT(x, y, 0) || insideT(x, y, offsets[7]!)) return true;
    return [1, 3, 5].some((index) => insideT(x, y, offsets[index]!) && !insideT(x, y, offsets[index + 1]!));
  };
  const sorted = (values: number[]): number[] => [...new Set(values.map((value) => Math.round(value * 1e6) / 1e6))].sort((a, b) => a - b);
  const xs = sorted([-halfX, halfX, ...offsets.flatMap((d) => [-logoHalf + d, logoHalf - d, -stemHalf + d, stemHalf - d])]);
  const ys = sorted([-halfY, halfY, ...offsets.flatMap((d) => [-logoHalf + d, logoHalf - d, shoulder + d])]);
  const cells = ys.slice(0, -1).map((y, j) => xs.slice(0, -1).map((x, i) => filled((x + xs[i + 1]!) / 2, (y + ys[j + 1]!) / 2)));
  const b: Builder = { positions: [], normals: [] };
  for (let j = 0; j < ys.length - 1; j += 1) {
    for (let i = 0; i < xs.length - 1; i += 1) {
      if (!cells[j]![i]) continue;
      const x0 = xs[i]!, x1 = xs[i + 1]!, y0 = ys[j]!, y1 = ys[j + 1]!;
      const p: Vec3[] = [[x0,y0,0],[x1,y0,0],[x1,y1,0],[x0,y1,0],[x0,y0,height],[x1,y0,height],[x1,y1,height],[x0,y1,height]];
      quad(b,p[0]!,p[3]!,p[2]!,p[1]!);
      quad(b,p[4]!,p[5]!,p[6]!,p[7]!);
      // Only exposed edges get side faces: no intersecting boxes or internal
      // walls, and shared grid edges have matching vertices on both sides.
      if (!cells[j - 1]?.[i]) quad(b,p[0]!,p[1]!,p[5]!,p[4]!);
      if (!cells[j]?.[i + 1]) quad(b,p[1]!,p[2]!,p[6]!,p[5]!);
      if (!cells[j + 1]?.[i]) quad(b,p[2]!,p[3]!,p[7]!,p[6]!);
      if (!cells[j]?.[i - 1]) quad(b,p[3]!,p[0]!,p[4]!,p[7]!);
    }
  }
  return finish(b);
}

export function createPrimitiveGeometry(kind: PrimitiveKind, plateWidth = 256, plateDepth = 256, nozzleDiameter = 0.4): MeshGeometry {
  if (kind === "cube") return box(20, 20, 20);
  if (kind === "cylinder") return cylinder(10, 20);
  if (kind === "sphere") return sphere(10);
  if (kind === "cone") return cylinder(12, 24, 64, 0);
  if (kind === "torus") return torus(12, 4);
  if (kind === "plate") return box(50, 50, 1);
  return firstLayer(plateWidth, plateDepth, nozzleDiameter);
}
