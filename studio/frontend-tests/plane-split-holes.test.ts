import assert from "node:assert/strict";
import test from "node:test";
import { createPrimitiveGeometry } from "../frontend/primitive-geometry.js";
import { geometryFromPositions } from "../frontend/studio-mesh-tools.js";
import { generateCapFaces } from "../frontend/studio-mesh-cap.js";
import { previewMeshPlaneSplit } from "../frontend/studio-mesh-split.js";
import { remapObjectPaintRegions } from "../frontend/studio-paint-state.js";
import type { MeshGeometry, MeshInstance } from "../frontend/webgl-studio-viewport.js";

function closed(geometry: MeshGeometry): void {
  const edges = new Map<string, { count: number; direction: number }>(), p = geometry.positions;
  for (let index = 0; index < p.length; index += 9) {
    const vertices = [0, 3, 6].map((offset) => Array.from(p.slice(index + offset, index + offset + 3)).join(","));
    for (let edge = 0; edge < 3; edge++) {
      const a = vertices[edge]!, b = vertices[(edge + 1) % 3]!;
      assert.notEqual(a, b);
      const name = a < b ? `${a}|${b}` : `${b}|${a}`, value = edges.get(name) ?? { count: 0, direction: 0 };
      value.count++; value.direction += a < b ? 1 : -1; edges.set(name, value);
    }
  }
  for (const edge of edges.values()) { assert.equal(edge.count, 2); assert.equal(edge.direction, 0); }
}

function volume(geometry: MeshGeometry): number {
  let total = 0; const p = geometry.positions;
  for (let i = 0; i < p.length; i += 9) total += (p[i]! * (p[i + 4]! * p[i + 8]! - p[i + 5]! * p[i + 7]!) + p[i + 1]! * (p[i + 5]! * p[i + 6]! - p[i + 3]! * p[i + 8]!) + p[i + 2]! * (p[i + 3]! * p[i + 7]! - p[i + 4]! * p[i + 6]!)) / 6;
  return total;
}

function instance(geometry: MeshGeometry, rotated = false): MeshInstance {
  return { id: "painted-source", name: "Fixture", geometry, position: [0, 0, 0], rotation: rotated ? [0.4, -0.7, 0.2] : [0, 0, 0], scale: [1, 1, 1], visible: true, color: "#aabbcc" };
}

function splitAndCheck(source: MeshInstance, axis: "x" | "y" | "z", plane: number): void {
  const original = new Float32Array(source.geometry.positions), originalNormals = new Float32Array(source.geometry.normals), transform = JSON.stringify([source.position, source.rotation, source.scale, source.color]);
  const originalVolume = volume(source.geometry);
  closed(source.geometry);
  const regions = [0, 1, 2].map((channel) => ({ objectId: source.id, color: ["#000000", "#ffffff", "#ff0000"][channel]!, materialKey: `ams:${channel}`,
    triangleIndices: Array.from({ length: source.geometry.triangleCount }, (_, index) => index).filter((index) => index % 3 === channel) }));
  const paintBefore = JSON.stringify(regions);
  const result = previewMeshPlaneSplit(source, axis, plane);
  assert.ok(result.crossingTriangleCount > 0); assert.equal(result.canApply, true);
  assert.ok(result.negativeGeometry && result.positiveGeometry);
  closed(result.negativeGeometry); closed(result.positiveGeometry);
  const negativeVolume = volume(result.negativeGeometry), positiveVolume = volume(result.positiveGeometry);
  assert.ok(negativeVolume > 0 && positiveVolume > 0);
  assert.ok(Math.abs(negativeVolume + positiveVolume - originalVolume) <= Math.abs(originalVolume) * 1e-6);
  for (const [side, map, objectId] of [[result.negativeGeometry, result.negativeTriangleIndexMap, "negative-half"], [result.positiveGeometry, result.positiveTriangleIndexMap, "positive-half"]] as const) {
    const painted = remapObjectPaintRegions(regions, objectId, map);
    for (const region of painted) for (const index of region.triangleIndices) {
      assert.equal(region.objectId, objectId);
      assert.ok(index >= 0 && index < side.triangleCount);
      const originalFaces = [...map].filter(([, values]) => values.includes(index)).map(([face]) => face);
      assert.equal(originalFaces.length, 1);
      const sourceRegion = regions[originalFaces[0]! % 3]!;
      assert.equal(region.materialKey, sourceRegion.materialKey); assert.equal(region.color, sourceRegion.color);
    }
    const knownFaces = new Set([...map.values()].flat());
    assert.ok(knownFaces.size > 0 && knownFaces.size < side.triangleCount, "new interior caps have no false source-face material owner");
    assert.equal(new Set(painted.flatMap((region) => region.triangleIndices)).size, knownFaces.size);
  }
  assert.deepEqual(source.geometry.positions, original); assert.deepEqual(source.geometry.normals, originalNormals); assert.equal(JSON.stringify(regions), paintBefore);
  assert.equal(JSON.stringify([source.position, source.rotation, source.scale, source.color]), transform);
}

for (const [axis, plane] of [["z", 4], ["x", 2]] as const) test(`torus real ${axis}=${plane} split closes holes/concavity and retains material channels`, () => {
  splitAndCheck(instance(createPrimitiveGeometry("torus")), axis, plane);
});

function gridPrism(open = false): MeshGeometry {
  const material = (x: number, y: number): boolean => x >= 0 && x < 10 && y >= 0 && y < 10
    && (!(x >= 2 && x < 6 && y >= 2 && y < 6) || x >= 3 && x < 5 && y >= 3 && y < 5)
    && !(x >= 7 && x < 9 && y >= 2 && y < 5);
  const positions: number[] = [];
  const quad = (a: number[], b: number[], c: number[], d: number[]): void => { positions.push(...a, ...b, ...c, ...a, ...c, ...d); };
  for (let x = 0; x < 10; x++) for (let y = 0; y < 10; y++) if (material(x, y)) {
    quad([x, y, 0], [x, y + 1, 0], [x + 1, y + 1, 0], [x + 1, y, 0]);
    if (!open) quad([x, y, 1], [x + 1, y, 1], [x + 1, y + 1, 1], [x, y + 1, 1]);
    if (!material(x - 1, y)) quad([x, y + 1, 0], [x, y, 0], [x, y, 1], [x, y + 1, 1]);
    if (!material(x + 1, y)) quad([x + 1, y, 0], [x + 1, y + 1, 0], [x + 1, y + 1, 1], [x + 1, y, 1]);
    if (!material(x, y - 1)) quad([x, y, 0], [x + 1, y, 0], [x + 1, y, 1], [x, y, 1]);
    if (!material(x, y + 1)) quad([x + 1, y + 1, 0], [x, y + 1, 0], [x, y + 1, 1], [x + 1, y + 1, 1]);
  }
  return geometryFromPositions(new Float32Array(positions));
}

test("closed prism with two holes, nested island and collinear edge subdivisions preserves known volume 82", () => {
  const source = gridPrism(); closed(source); assert.ok(Math.abs(volume(source) - 82) < 1e-10);
  splitAndCheck(instance(source), "z", .5);
});

test("rotated closed hole/island prism uses its local cap plane rather than the world split axis", () => {
  splitAndCheck(instance(gridPrism(), true), "z", .4);
});

test("open hole/island prism receives precisely the missing area and exact original boundary subdivisions", () => {
  const source = gridPrism(true), original = new Float32Array(source.positions), cap = generateCapFaces(source, "z");
  assert.ok(cap.capCount > 0);
  const full = geometryFromPositions(new Float32Array([...source.positions, ...cap.capPositions]));
  closed(full); assert.ok(Math.abs(volume(full) - 82) < 1e-10);
  let area = 0;
  for (let i = 0; i < cap.capPositions.length; i += 9) { const p = cap.capPositions; area += ((p[i + 3]! - p[i]!) * (p[i + 7]! - p[i + 1]!) - (p[i + 4]! - p[i + 1]!) * (p[i + 6]! - p[i]!)) / 2; }
  assert.ok(Math.abs(area - 82) < 1e-10); assert.deepEqual(source.positions, original);
});

function openRings(rings: readonly (readonly (readonly [number, number])[])[], heights: readonly number[] = []): MeshGeometry {
  const positions: number[] = [];
  for (const [ringIndex, ring] of rings.entries()) {
    const height = heights[ringIndex] || 0;
    for (let index = 0; index < ring.length; index++) {
      const a = ring[index]!, b = ring[(index + 1) % ring.length]!;
      // Each independent cone carries only this one planar contour as boundary.
      positions.push(a[0], a[1], height, b[0], b[1], height, 0, 0, -5);
    }
  }
  return geometryFromPositions(new Float32Array(positions));
}
const square = [[-3, -3], [3, -3], [3, 3], [-3, 3]] as const;
for (const [name, geometry] of [
  ["self-crossing contour with nonzero signed area", openRings([[[0, 0], [4, 4], [0, 4], [3, 0]]])],
  ["touching contours", openRings([square, [[3, -1], [4, -1], [4, 1], [3, 1]]])],
  ["intersecting contours", openRings([square, [[2, -1], [4, -1], [4, 1], [2, 1]]])],
  ["nested overlapping outward shells", openRings([square, [[-1, -1], [1, -1], [1, 1], [-1, 1]]])],
  ["noncoplanar contours", openRings([square, [[7, -1], [9, -1], [9, 1], [7, 1]]], [0, 1])],
] as const) test(`${name} remains fail closed`, () => {
  const result = generateCapFaces(geometry, "z"); assert.equal(result.capCount, 0); assert.equal(result.capPositions.length, 0);
});
