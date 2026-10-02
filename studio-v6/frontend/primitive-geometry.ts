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

function firstLayer(width: number, depth: number, height: number): MeshGeometry {
  const margin = Math.max(5, Math.min(width, depth) * 0.025);
  const line = Math.max(0.42, Math.min(width, depth) / 500);
  const usableWidth = Math.max(10, width - margin * 2);
  const usableDepth = Math.max(10, depth - margin * 2);
  const b: Builder = { positions: [], normals: [] };
  const addBar = (centerX: number, centerY: number, barWidth: number, barDepth: number): void => {
    const geometry = box(barWidth, barDepth, height);
    for (let index = 0; index < geometry.positions.length; index += 3) {
      b.positions.push(geometry.positions[index]! + centerX, geometry.positions[index + 1]! + centerY, geometry.positions[index + 2]!);
      b.normals.push(geometry.normals[index]!, geometry.normals[index + 1]!, geometry.normals[index + 2]!);
    }
  };
  addBar(0, -usableDepth / 2, usableWidth, line);
  addBar(0, usableDepth / 2, usableWidth, line);
  addBar(-usableWidth / 2, 0, line, usableDepth);
  addBar(usableWidth / 2, 0, line, usableDepth);
  const spacing = Math.max(8, Math.min(width, depth) / 18);
  for (let y = -usableDepth / 2 + spacing; y < usableDepth / 2; y += spacing) addBar(0, y, usableWidth, line);
  addBar(0, 0, line * 2, usableDepth);
  return finish(b);
}

export function createPrimitiveGeometry(kind: PrimitiveKind, plateWidth = 256, plateDepth = 256): MeshGeometry {
  if (kind === "cube") return box(20, 20, 20);
  if (kind === "cylinder") return cylinder(10, 20);
  if (kind === "sphere") return sphere(10);
  if (kind === "cone") return cylinder(12, 24, 64, 0);
  if (kind === "torus") return torus(12, 4);
  if (kind === "plate") return box(50, 50, 1);
  return firstLayer(plateWidth, plateDepth, 0.2);
}
