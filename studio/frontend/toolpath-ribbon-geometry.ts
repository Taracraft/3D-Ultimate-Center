import type { MeshGeometry, MeshInstance, Vec3 } from "./webgl-studio-viewport.js";

export type RibbonSegment = readonly [number, number, number, number, number, number, number, string, string];
export type RibbonLayer = Readonly<{ index: number; z: number; segments: readonly RibbonSegment[] }>;
export type RibbonStyle = Readonly<{ key: string; color: string; label: string; flat: boolean; highlight?: string }>;
type Group = { style: RibbonStyle; current: boolean; page: Float32Array; used: number; serial: number };
type CornerFrame = { segment: RibbonSegment; style: RibbonStyle; nx: number; ny: number; dx: number; dy: number; length: number };
const PAGE_FLOATS = 54 * 4096;

/** Extrusion volume divided by travelled distance and layer height (1.75 mm filament).
 * This is a width estimate from the available toolpath contract, not a nozzle setting.
 */
export function extrusionRibbonWidth(extrusion: number, length: number, height: number): number {
  const estimate = extrusion * Math.PI * .875 * .875 / (length * height);
  return Number.isFinite(estimate) && estimate > 0 ? Math.max(.07, Math.min(1.25, estimate)) : .38;
}

function visualRibbonHeight(style: RibbonStyle, current: boolean, height: number): number {
  void current;
  return style.flat ? 0 : height;
}

function meshGeometry(positions: Float32Array): MeshGeometry {
  const normals = new Float32Array(positions.length);
  const minimum: Vec3 = [Infinity, Infinity, Infinity];
  const maximum: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i += 9) {
    const ux = positions[i + 3]! - positions[i]!;
    const uy = positions[i + 4]! - positions[i + 1]!;
    const uz = positions[i + 5]! - positions[i + 2]!;
    const vx = positions[i + 6]! - positions[i]!;
    const vy = positions[i + 7]! - positions[i + 1]!;
    const vz = positions[i + 8]! - positions[i + 2]!;
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz) || 1;
    const lowZ = Math.min(positions[i + 2]!, positions[i + 5]!, positions[i + 8]!);
    const highZ = Math.max(positions[i + 2]!, positions[i + 5]!, positions[i + 8]!);
    for (let vertex = 0; vertex < 3; vertex += 1) {
      const offset = i + vertex * 3;
      normals[offset] = nx / length; normals[offset + 1] = ny / length; normals[offset + 2] = nz / length;
      // Per-bead lighting keeps layer boundaries legible without shrinking geometry.
      if (highZ > lowZ && Math.abs(nz / length) < .001) {
        const tilt = ((positions[offset + 2]! - lowZ) / (highZ - lowZ) - .5) * .8;
        const scale = Math.hypot(1, tilt);
        normals[offset] = nx / length / scale;
        normals[offset + 1] = ny / length / scale;
        normals[offset + 2] = tilt / scale;
      }
      for (let axis = 0; axis < 3; axis += 1) {
        minimum[axis] = Math.min(minimum[axis]!, positions[offset + axis]!);
        maximum[axis] = Math.max(maximum[axis]!, positions[offset + axis]!);
      }
    }
  }
  return { positions, normals, triangleCount: positions.length / 9, boundsMin: minimum, boundsMax: maximum };
}

/** All accepted segments survive. Pages bound temporary allocations, never sample paths. */
export function buildContinuousToolpathMeshes(
  layers: readonly RibbonLayer[], selectedLayer: number, cumulative: boolean,
  heights: ReadonlyMap<number, number>,
  styleFor: (segment: RibbonSegment, current: boolean) => RibbonStyle | null,
): MeshInstance[] {
  if (!layers.some((layer) => layer.index === selectedLayer)) return [];
  const groups = new Map<string, Group>();
  const meshes: MeshInstance[] = [];
  const flush = (group: Group): void => {
    if (!group.used) return;
    const positions = group.used === group.page.length ? group.page : group.page.slice(0, group.used);
    meshes.push({
      id: `toolpath-${selectedLayer}-${group.current ? "current" : "history"}-${group.style.key}-${group.serial++}`,
      name: `${group.current ? "Aktueller Layer" : "Vorherige Layer"} · ${group.style.label}`,
      geometry: meshGeometry(positions), position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1],
      color: group.style.color, visible: true,
    });
    group.page = new Float32Array(PAGE_FLOATS);
    group.used = 0;
  };
  const append = (style: RibbonStyle, current: boolean, values: readonly number[]): void => {
    const key = `${current}:${style.key}`;
    let group = groups.get(key);
    if (!group) {
      group = { style, current, page: new Float32Array(PAGE_FLOATS), used: 0, serial: 0 };
      groups.set(key, group);
    }
    if (group.used + values.length > group.page.length) flush(group);
    group.page.set(values, group.used);
    group.used += values.length;
  };
  const connected = (before: CornerFrame, after: CornerFrame): boolean => {
    const a = before.segment, b = after.segment;
    return Math.hypot(a[2] - b[0], a[3] - b[1]) <= .00001
      && Math.abs(a[4] - b[4]) <= .000001 && a[5] === b[5]
      && (before.dx * after.dx + before.dy * after.dy) / (before.length * after.length) > -.999999
      && a[7] === b[7] && a[8] === b[8]
      && before.style.key === after.style.key && before.style.color === after.style.color
      && before.style.flat === after.style.flat && before.style.highlight === after.style.highlight;
  };
  const corner = (before: CornerFrame, after: CornerFrame, current: boolean, height: number): void => {
    const turn = (before.dx * after.dy - before.dy * after.dx) / (before.length * after.length);
    // Bevel joins fill the outer corner without the spikes of unbounded miters.
    if (Math.abs(turn) < .000001) return;
    const [x, y, , , z] = after.segment;
    const side = turn > 0 ? -1 : 1;
    let ax = before.nx * side, ay = before.ny * side;
    let bx = after.nx * side, by = after.ny * side;
    if (turn < 0) { [ax, bx] = [bx, ax]; [ay, by] = [by, ay]; }
    append(after.style, current, [x, y, z, x + ax, y + ay, z, x + bx, y + by, z]);
    if (!after.style.flat) {
      const bottom = Math.max(0, z - visualRibbonHeight(after.style, current, height));
      append(after.style, current, [
        x + ax, y + ay, bottom, x + bx, y + by, bottom, x + bx, y + by, z,
        x + ax, y + ay, bottom, x + bx, y + by, z, x + ax, y + ay, z,
      ]);
    }
    if (after.style.highlight) {
      append({ key: `${after.style.key}:highlight`, color: after.style.highlight, label: after.style.label, flat: true }, current, [
        x, y, z + .001, x + ax * .12, y + ay * .12, z + .001, x + bx * .12, y + by * .12, z + .001,
      ]);
    }
  };
  const cap = (frame: CornerFrame, start: boolean, current: boolean, height: number): void => {
    if (frame.style.flat) return;
    const segment = frame.segment;
    const x = segment[start ? 0 : 2], y = segment[start ? 1 : 3], z = segment[4];
    const side = start ? 1 : -1;
    const nx = frame.nx * side, ny = frame.ny * side;
    const bottom = Math.max(0, z - visualRibbonHeight(frame.style, current, height));
    // Only open chain endpoints get a face; the contour interior stays unsplit.
    append(frame.style, current, [
      x + nx, y + ny, bottom, x - nx, y - ny, bottom, x - nx, y - ny, z,
      x + nx, y + ny, bottom, x - nx, y - ny, z, x + nx, y + ny, z,
    ]);
  };
  for (const layer of layers) {
    if (layer.index > selectedLayer || (!cumulative && layer.index !== selectedLayer)) continue;
    const current = layer.index === selectedLayer;
    const height = heights.get(layer.index) ?? .2;
    let previous: CornerFrame | null = null;
    let first: CornerFrame | null = null;
    const finishChain = (): void => {
      if (first && previous) {
        cap(first, true, current, height);
        cap(previous, false, current, height);
      }
      first = null;
      previous = null;
    };
    for (const segment of layer.segments) {
      const [x1, y1, x2, y2, z, , extrusion] = segment;
      if (![x1, y1, x2, y2, z, extrusion, height].every(Number.isFinite) || height <= 0 || extrusion <= 0) { finishChain(); continue; }
      const dx = x2 - x1, dy = y2 - y1, length = Math.hypot(dx, dy);
      if (length < .0001) { finishChain(); continue; }
      const style = styleFor(segment, current);
      if (!style) { finishChain(); continue; }
      const width = extrusionRibbonWidth(extrusion, length, height);
      const nx = -dy / length * width / 2, ny = dx / length * width / 2;
      const frame: CornerFrame = { segment, style, nx, ny, dx, dy, length };
      if (previous && connected(previous, frame)) corner(previous, frame, current, height);
      else { finishChain(); first = frame; }
      previous = frame;
      if (first !== frame && first && connected(frame, first)) {
        corner(frame, first, current, height);
        previous = null;
        first = null;
      }
      const bottom = Math.max(0, z - visualRibbonHeight(style, current, height));
      // Keep exact layer heights for non-flat paths; Bambu-like flattening comes from bead width and lighting without opening Z gaps.
      const top = z;
      append(style, current, [
        x1 + nx, y1 + ny, top, x1 - nx, y1 - ny, top, x2 - nx, y2 - ny, top,
        x1 + nx, y1 + ny, top, x2 - nx, y2 - ny, top, x2 + nx, y2 + ny, top,
      ]);
      if (!style.flat) append(style, current, [
        x1 + nx, y1 + ny, bottom, x2 + nx, y2 + ny, top, x2 + nx, y2 + ny, bottom,
        x1 + nx, y1 + ny, bottom, x1 + nx, y1 + ny, top, x2 + nx, y2 + ny, top,
        x1 - nx, y1 - ny, bottom, x2 - nx, y2 - ny, bottom, x2 - nx, y2 - ny, top,
        x1 - nx, y1 - ny, bottom, x2 - nx, y2 - ny, top, x1 - nx, y1 - ny, top,
      ]);
      if (style.highlight) {
        const hx = nx * .12, hy = ny * .12, hz = z + .001;
        append({ key: `${style.key}:highlight`, color: style.highlight, label: style.label, flat: true }, current, [
          x1 + hx, y1 + hy, hz, x1 - hx, y1 - hy, hz, x2 - hx, y2 - hy, hz,
          x1 + hx, y1 + hy, hz, x2 - hx, y2 - hy, hz, x2 + hx, y2 + hy, hz,
        ]);
      }
    }
    finishChain();
  }
  for (const group of groups.values()) flush(group);
  return meshes;
}


