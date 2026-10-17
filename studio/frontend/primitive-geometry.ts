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
    // Reuse the first ring vertex at the seam; sin(2*PI) is not exactly zero.
    const a1 = ((index + 1) % segments) * Math.PI * 2 / segments;
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
    // All longitude samples share the exact same pole and seam positions.
    if (lat === 0) return [0, 0, 0];
    if (lat === latitude) return [0, 0, radius * 2];
    const phi = Math.PI * lat / latitude;
    const theta = Math.PI * 2 * (lon % longitude) / longitude;
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
    const a = Math.PI * 2 * (major % majorSegments) / majorSegments;
    const t = Math.PI * 2 * (tube % tubeSegments) / tubeSegments;
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
  return { height: Math.round(nozzleDiameter * 50) / 100, lineWidth: Math.round(nozzleDiameter * 150) / 100 };
}

/**
 * One thin closed solid, not a stack of sheets. A sparse diagnostic network
 * samples the whole bed; nine small pads show adjacent-line bonding. Three
 * isolated T contours are branding and corner tests, not embossed extra layers.
 * Model caps and side faces close the mesh; they do not represent print layers.
 */
function firstLayer(width: number, depth: number, nozzleDiameter: number): MeshGeometry {
  const { height, lineWidth } = firstLayerParameters(nozzleDiameter);
  if (![width, depth].every((value) => Number.isFinite(value) && value >= 120 && value <= 1000)) {
    throw new Error("Ungültige Druckbettgröße für den First-Layer-Test.");
  }
  const halfX = width / 2 - 5, halfY = depth / 2 - 5;
  const logoHalf = Math.min(width, depth) * 0.25;
  const stemHalf = logoHalf * 0.4, shoulder = logoHalf * 0.48;
  const band = Math.max(0.55, lineWidth * 1.25);
  const offsets = [-band, 0, band, 2 * band, 3 * band, 4 * band, 5 * band];
  const padHalf = Math.min(15, Math.max(7.5, Math.min(width, depth) * 0.038));
  const centreHalf = Math.min(padHalf, stemHalf - 5 * band - 2 * lineWidth);
  if (centreHalf <= lineWidth) throw new Error("Druckbett zu klein für die gewählte First-Layer-Düse.");
  type Point = readonly [number, number];
  const pads: { x: number; y: number; half: number }[] = [];
  for (const x of [-halfX + padHalf + 3 * lineWidth, 0, halfX - padHalf - 3 * lineWidth]) {
    for (const y of [-halfY + padHalf + 3 * lineWidth, 0, halfY - padHalf - 3 * lineWidth]) {
      pads.push({ x, y, half: x === 0 && y === 0 ? centreHalf : padHalf });
    }
  }
  const insideT = (x: number, y: number, inset: number): boolean =>
    y > -logoHalf + inset && y < logoHalf - inset
    && (Math.abs(x) < stemHalf - inset || (Math.abs(x) < logoHalf - inset && y > shoulder + inset));
  const sorted = (values: number[]): number[] => [...new Set(values.map((v) => Math.round(v * 1e6) / 1e6))].sort((a, b) => a - b);
  const xs = sorted([-halfX, halfX, -halfX + lineWidth, halfX - lineWidth,
    ...offsets.flatMap((d) => [-logoHalf + d, logoHalf - d, -stemHalf + d, stemHalf - d]),
    ...pads.flatMap((p) => [p.x - p.half, p.x + p.half])]);
  const ys = sorted([-halfY, halfY, -halfY + lineWidth, halfY - lineWidth,
    ...offsets.flatMap((d) => [-logoHalf + d, logoHalf - d, shoulder + d]),
    ...pads.flatMap((p) => [p.y - p.half, p.y + p.half])]);
  // x+y=constant runs from upper-left to lower-right in the bed plane.
  const pitch = 14 * Math.SQRT2, diagonalHalf = lineWidth * Math.SQRT2;
  const extent = halfX + halfY;
  const cuts = sorted([-extent, extent, ...Array.from(
    { length: 2 * Math.ceil(extent / pitch) + 3 },
    (_, index) => (index - Math.ceil(extent / pitch) - 1) * pitch,
  ).flatMap((u) => [u - diagonalHalf, u + diagonalHalf]).filter((u) => u > -extent && u < extent)]);
  const solidCell = (x: number, y: number): boolean =>
    Math.abs(x) > halfX - lineWidth || Math.abs(y) > halfY - lineWidth
    || pads.some((p) => Math.abs(x - p.x) < p.half && Math.abs(y - p.y) < p.half)
    || [0, 2 * band, 4 * band].some((d) => insideT(x, y, d) && !insideT(x, y, d + band));
  const clip = (poly: readonly Point[], limit: number, keepGreater: boolean): Point[] => {
    const output: Point[] = [];
    for (let index = 0; index < poly.length; index += 1) {
      const a = poly[index]!, z = poly[(index + 1) % poly.length]!;
      const da = a[0] + a[1] - limit, dz = z[0] + z[1] - limit;
      const aIn = keepGreater ? da >= 0 : da <= 0;
      const zIn = keepGreater ? dz >= 0 : dz <= 0;
      if (aIn) output.push(a);
      if (aIn !== zIn) {
        const t = da / (da - dz);
        output.push([a[0] + t * (z[0] - a[0]), a[1] + t * (z[1] - a[1])]);
      }
    }
    return output;
  };
  const vertices = new Map<string, Point>();
  const point = (p: Point): Point => {
    const rounded: Point = [Math.round(p[0] * 1e6) / 1e6, Math.round(p[1] * 1e6) / 1e6];
    const key = `${rounded[0]},${rounded[1]}`;
    if (!vertices.has(key)) vertices.set(key, rounded);
    return vertices.get(key)!;
  };
  const edgeKey = (a: Point, z: Point): string => [`${a[0]},${a[1]}`, `${z[0]},${z[1]}`].sort().join("|");
  const boundary = new Map<string, { a: Point; z: Point; count: number }>();
  const b: Builder = { positions: [], normals: [] };
  const addCell = (input: readonly Point[]): void => {
    const poly: Point[] = [];
    for (const p of input.map(point)) if (poly.at(-1) !== p) poly.push(p);
    if (poly[0] === poly.at(-1)) poly.pop();
    if (poly.length < 3) return;
    let twiceArea = 0;
    for (let k = 0; k < poly.length; k += 1) {
      const a = poly[k]!, z = poly[(k + 1) % poly.length]!;
      twiceArea += a[0] * z[1] - a[1] * z[0];
    }
    if (twiceArea <= 1e-8) return;
    // Centre fans retain every shared edge, including collinear subdivisions.
    // Removing those vertices would introduce T-junctions in adjacent cells.
    const centre: Point = [poly.reduce((s, p) => s + p[0], 0) / poly.length,
      poly.reduce((s, p) => s + p[1], 0) / poly.length];
    for (let k = 0; k < poly.length; k += 1) {
      const a = poly[k]!, z = poly[(k + 1) % poly.length]!;
      triangle(b, [centre[0], centre[1], 0], [z[0], z[1], 0], [a[0], a[1], 0]);
      triangle(b, [centre[0], centre[1], height], [a[0], a[1], height], [z[0], z[1], height]);
      const key = edgeKey(a, z), entry = boundary.get(key);
      if (entry) entry.count += 1;
      else boundary.set(key, { a, z, count: 1 });
    }
  };
  for (let j = 0; j < ys.length - 1; j += 1) {
    for (let i = 0; i < xs.length - 1; i += 1) {
      const x0 = xs[i]!, x1 = xs[i + 1]!, y0 = ys[j]!, y1 = ys[j + 1]!;
      if (x1 - x0 < 1e-5 || y1 - y0 < 1e-5) continue;
      const x = (x0 + x1) / 2, y = (y0 + y1) / 2;
      const full = solidCell(x, y), clearLogo = insideT(x, y, -band);
      if (!full && clearLogo) continue;
      const rectangle: Point[] = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
      for (let k = 0; k < cuts.length - 1; k += 1) {
        const low = cuts[k]!, high = cuts[k + 1]!;
        if (high <= x0 + y0 || low >= x1 + y1) continue;
        const u = (low + high) / 2;
        if (!full && Math.abs(u - Math.round(u / pitch) * pitch) >= diagonalHalf) continue;
        addCell(clip(clip(rectangle, low, true), high, false));
      }
    }
  }
  for (const { a, z, count } of boundary.values()) {
    if (count > 2) throw new Error("Ungültige First-Layer-Topologie.");
    if (count === 1) quad(b, [a[0], a[1], 0], [z[0], z[1], 0], [z[0], z[1], height], [a[0], a[1], height]);
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
