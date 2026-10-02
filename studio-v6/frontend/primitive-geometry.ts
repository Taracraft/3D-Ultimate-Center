import type { MeshGeometry, Vec3 } from "./webgl-studio-viewport.js";

export type PrimitiveKind = "cube" | "cylinder" | "sphere" | "cone" | "torus" | "plate" | "rectangle" | "circle" | "line" | "text" | "first-layer";

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


function flatRectangle(width: number, depth: number, height: number): MeshGeometry {
  return box(width, depth, height);
}

function flatCircle(radius: number, height: number, segments = 96): MeshGeometry {
  return cylinder(radius, height, segments);
}

function flatLine(length: number, thickness: number, height: number): MeshGeometry {
  return box(length, thickness, height);
}

export function createStrokeGeometry(length: number, thickness = 1.2, height = 0.4): MeshGeometry {
  return flatLine(Math.max(0.5, length), Math.max(0.1, thickness), Math.max(0.05, height));
}

const TEXT_GLYPHS: Readonly<Record<string, readonly string[]>> = Object.freeze({
  "0": ["11111", "10001", "10011", "10101", "11001", "10001", "11111"],
  "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
  "2": ["11110", "00001", "00001", "11110", "10000", "10000", "11111"],
  "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
  "4": ["10010", "10010", "10010", "11111", "00010", "00010", "00010"],
  "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
  "6": ["01111", "10000", "10000", "11110", "10001", "10001", "01110"],
  "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
  "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
  "9": ["01110", "10001", "10001", "01111", "00001", "00001", "11110"],
  A: ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
  B: ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
  C: ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
  D: ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
  E: ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
  F: ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
  G: ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
  H: ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
  I: ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
  J: ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
  K: ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
  L: ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
  M: ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
  N: ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
  O: ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
  P: ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
  Q: ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
  R: ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
  S: ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
  T: ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
  U: ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
  V: ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
  W: ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
  X: ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
  Y: ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
  Z: ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
  "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
  ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
});

function appendGeometry(target: Builder, geometry: MeshGeometry, offsetX: number, offsetY: number): void {
  for (let index = 0; index < geometry.positions.length; index += 3) {
    target.positions.push(geometry.positions[index]! + offsetX, geometry.positions[index + 1]! + offsetY, geometry.positions[index + 2]!);
    target.normals.push(geometry.normals[index]!, geometry.normals[index + 1]!, geometry.normals[index + 2]!);
  }
}

export function createTextGeometry(value = "TEXT", height = 0.6): MeshGeometry {
  const text = value.trim().toUpperCase().slice(0, 24) || "TEXT";
  const cell = 2.4;
  const gap = 0.35;
  const charGap = 1.4;
  const charWidth = 5 * cell + 4 * gap;
  const charHeight = 7 * cell + 6 * gap;
  const b: Builder = { positions: [], normals: [] };
  const totalWidth = text.length * charWidth + Math.max(0, text.length - 1) * charGap;
  let cursorX = -totalWidth / 2 + charWidth / 2;
  for (const character of text) {
    if (character === " ") {
      cursorX += charWidth * 0.65 + charGap;
      continue;
    }
    const rows = TEXT_GLYPHS[character] ?? ["11111", "10001", "10101", "10001", "10101", "10001", "11111"];
    for (let row = 0; row < rows.length; row += 1) {
      const line = rows[row]!;
      for (let column = 0; column < line.length; column += 1) {
        if (line[column] !== "1") continue;
        const x = cursorX - charWidth / 2 + column * (cell + gap) + cell / 2;
        const y = charHeight / 2 - row * (cell + gap) - cell / 2;
        appendGeometry(b, box(cell, cell, height), x, y);
      }
    }
    cursorX += charWidth + charGap;
  }
  return finish(b.positions.length ? b : { positions: [...box(charWidth, charHeight, height).positions], normals: [...box(charWidth, charHeight, height).normals] });
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
  if (kind === "rectangle") return flatRectangle(50, 30, 0.4);
  if (kind === "circle") return flatCircle(18, 0.4);
  if (kind === "line") return flatLine(Math.min(90, Math.max(30, plateWidth * 0.35)), 1.2, 0.4);
  if (kind === "text") return createTextGeometry();
  return firstLayer(plateWidth, plateDepth, 0.2);
}