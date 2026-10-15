import assert from "node:assert/strict";
import test from "node:test";
import { createPrimitiveGeometry, firstLayerParameters } from "../frontend/primitive-geometry.js";
import { firstLayerProcessOptions } from "../frontend/first-layer-process.js";
import type { SliceProcessOverrides } from "../frontend/plate-slice-api.js";

function inspect(nozzle: number, width: number, depth: number): void {
  const mesh = createPrimitiveGeometry("first-layer", width, depth, nozzle);
  const { height } = firstLayerParameters(nozzle);
  assert.deepEqual(mesh.boundsMin, [-width / 2 + 5, -depth / 2 + 5, 0]);
  assert.ok(Math.abs(mesh.boundsMax[2] - height) < 1e-6);
  const edges = new Map<string, { count: number; balance: number }>();
  const graph = new Map<string, Set<string>>();
  let signedVolume = 0;
  for (let i = 0; i < mesh.positions.length; i += 9) {
    const points = [0, 3, 6].map((offset) => Array.from(mesh.positions.slice(i + offset, i + offset + 3)));
    const keys = points.map((point) => point.map((v) => v.toFixed(5)).join(","));
    assert.equal(new Set(keys).size, 3, "no degenerate triangle");
    const [a, b, c] = points as [number[], number[], number[]];
    signedVolume += (a[0]! * (b[1]! * c[2]! - b[2]! * c[1]!) - a[1]! * (b[0]! * c[2]! - b[2]! * c[0]!) + a[2]! * (b[0]! * c[1]! - b[1]! * c[0]!)) / 6;
    for (let k = 0; k < 3; k += 1) {
      const u = keys[k]!, v = keys[(k + 1) % 3]!;
      const key = [u, v].sort().join("|");
      const edge = edges.get(key) ?? { count: 0, balance: 0 };
      edge.count += 1; edge.balance += u < v ? 1 : -1; edges.set(key, edge);
      if (!graph.has(u)) graph.set(u, new Set());
      if (!graph.has(v)) graph.set(v, new Set());
      graph.get(u)!.add(v); graph.get(v)!.add(u);
    }
  }
  for (const edge of edges.values()) assert.deepEqual(edge, { count: 2, balance: 0 }, "closed consistently wound mesh");
  let components = 0;
  const visited = new Set<string>();
  for (const key of graph.keys()) {
    if (visited.has(key)) continue;
    components += 1;
    const queue = [key];
    while (queue.length) {
      const vertex = queue.pop()!;
      if (visited.has(vertex)) continue;
      visited.add(vertex);
      queue.push(...graph.get(vertex)!);
    }
  }
  assert.equal(components, 5, "outer sheet, three separate T contours, filled T centre");
  assert.ok(signedVolume > (width - 10) * (depth - 10) * height * 0.85, "calibration covers the bed, not sparse lines");
  assert.ok(signedVolume < (width - 10) * (depth - 10) * height, "visible contour gaps remain open");
}

for (const nozzle of [0.2, 0.4, 0.6, 0.8]) {
  test(`TaraCraft full-bed first layer ${nozzle} mm nozzle`, () => {
    inspect(nozzle, 256, 256);
    inspect(nozzle, 340, 320);
  });
}

test("first layer rejects invalid dimensions and unsupported nozzles", () => {
  for (const nozzle of [0, 0.3, NaN, Infinity]) assert.throws(() => createPrimitiveGeometry("first-layer", 256, 256, nozzle));
  for (const width of [0, -1, NaN, Infinity]) assert.throws(() => createPrimitiveGeometry("first-layer", width, 256));
});

test("first-layer process matches mesh and preserves unrelated process settings", () => {
  const before = { layer_height_ranges: [{ min_z_mm: 0, max_z_mm: 10, layer_height_mm: 0.1 }], travel_speed_mm_s: 200 } as unknown as SliceProcessOverrides;
  const after = firstLayerProcessOptions(0.4, before);
  assert.equal(after.first_layer_height_mm, 0.28);
  assert.equal(after.layer_height_mm, 0.28);
  assert.equal(after.initial_layer_line_width_mm, 0.6);
  assert.equal(after.infill_direction_deg, 135);
  assert.equal(after.initial_layer_infill_speed_mm_s, 30);
  assert.equal(after.infill_percent, 0);
  assert.equal(after.bottom_shell_layers, 1);
  assert.equal(after.travel_speed_mm_s, 200);
  assert.deepEqual(after.layer_height_ranges, []);
  assert.equal(before.layer_height_ranges.length, 1);
});
