import assert from "node:assert/strict";
import test from "node:test";
import { generateCapFaces } from "../frontend/studio-mesh-cap.js";
import { geometryFromPositions } from "../frontend/studio-mesh-tools.js";
import { createPrimitiveGeometry, type PrimitiveKind } from "../frontend/primitive-geometry.js";
import { previewMeshPlaneSplit, type MeshSplitAxis } from "../frontend/studio-mesh-split.js";
import type { MeshGeometry, MeshInstance } from "../frontend/webgl-studio-viewport.js";

// Exercise the same exact Float32 vertex identity that the production safe
// plane-split validator uses; no engine, job or printer operation is involved.
function assertClosed(geometry: MeshGeometry): void {
  const edges = new Map<string, { count: number; direction: number }>();
  for (let offset = 0; offset < geometry.positions.length; offset += 9) {
    const vertices = [0, 3, 6].map((vertex) => Array.from(geometry.positions.slice(offset + vertex, offset + vertex + 3)).join(","));
    for (const [left, right] of [[0, 1], [1, 2], [2, 0]] as const) {
      const a = vertices[left]!, b = vertices[right]!;
      assert.notEqual(a, b, "a primitive must not contain a collapsed triangle edge");
      const key = a < b ? `${a}|${b}` : `${b}|${a}`;
      const edge = edges.get(key) ?? { count: 0, direction: 0 };
      edge.count += 1;
      edge.direction += a < b ? 1 : -1;
      edges.set(key, edge);
    }
  }
  for (const edge of edges.values()) {
    assert.equal(edge.count, 2, "every exact Float32 edge must have two incident faces");
    assert.equal(edge.direction, 0, "incident faces must traverse a shared edge in opposite directions");
  }
}

function signedVolume(geometry: MeshGeometry): number {
  const p = geometry.positions;
  let volume = 0;
  for (let i = 0; i < p.length; i += 9) {
    volume += (p[i]! * (p[i + 4]! * p[i + 8]! - p[i + 5]! * p[i + 7]!)
      + p[i + 1]! * (p[i + 5]! * p[i + 6]! - p[i + 3]! * p[i + 8]!)
      + p[i + 2]! * (p[i + 3]! * p[i + 7]! - p[i + 4]! * p[i + 6]!)) / 6;
  }
  return volume;
}

function instance(kind: PrimitiveKind): MeshInstance {
  return { id: "primitive", name: kind, geometry: createPrimitiveGeometry(kind),
    position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], color: "#ffffff", visible: true };
}

for (const [kind, triangleCount] of [["cylinder", 256], ["cone", 128], ["sphere", 2976]] as const) {
  test(`${kind} has an exact closed seam and poles without changing tessellation`, () => {
    const geometry = createPrimitiveGeometry(kind);
    assert.equal(geometry.triangleCount, triangleCount);
    assert.ok(geometry.positions.every(Number.isFinite));
    assert.ok(geometry.normals.every(Number.isFinite));
    assert.ok(signedVolume(geometry) > 0, "surface orientation must point outwards");
    assertClosed(geometry);
  });

  test(`${kind} passes the actual safe plane-split path and preserves total volume`, () => {
    const source = instance(kind), originalPositions = new Float32Array(source.geometry.positions);
    const sourceVolume = signedVolume(source.geometry);
    for (const axis of ["x", "y", "z"] as const satisfies readonly MeshSplitAxis[]) {
      const result = previewMeshPlaneSplit(source, axis, axis === "z" ? 10 : 1);
      assert.ok(result.crossingTriangleCount > 0, "the test must actually cut through the solid");
      assert.equal(result.canApply, true, `safe ${axis} split must accept its own generated primitive`);
      assert.ok(result.negativeGeometry && result.positiveGeometry);
      assertClosed(result.negativeGeometry);
      assertClosed(result.positiveGeometry);
      const negativeVolume = signedVolume(result.negativeGeometry), positiveVolume = signedVolume(result.positiveGeometry);
      assert.ok(negativeVolume > 0 && positiveVolume > 0, "both result halves must keep their outward orientation");
      assert.ok(Math.abs(negativeVolume + positiveVolume - sourceVolume) < sourceVolume * 1e-6,
        "the two closed halves must preserve the original solid volume");
    }
    assert.deepEqual(source.geometry.positions, originalPositions, "preview must preserve the original model");
  });
}

for (const kind of ["cube", "plate"] as const) {
  test(`${kind} remains closed and accepted by the safe plane-split path`, () => {
    const source = instance(kind);
    assertClosed(source.geometry);
    const result = previewMeshPlaneSplit(source, "x", 1);
    assert.equal(result.canApply, true);
    assert.ok(result.negativeGeometry && result.positiveGeometry);
    assertClosed(result.negativeGeometry);
    assertClosed(result.positiveGeometry);
  });
}

// Closed periodic geometry and genuine hole-aware caps share the same split path.
test("torus has exact closed periodic seams without changing tessellation", () => {
  const geometry = createPrimitiveGeometry("torus");
  assert.equal(geometry.triangleCount, 3072);
  assertClosed(geometry);
  assert.ok(signedVolume(geometry) > 0);
});

test("torus central vertical cuts preserve two disjoint convex sections", () => {
  const source = instance("torus"), volume = signedVolume(source.geometry);
  for (const axis of ["x", "y"] as const) {
    const result = previewMeshPlaneSplit(source, axis, 0);
    assert.equal(result.canApply, true);
    assert.ok(result.negativeGeometry && result.positiveGeometry);
    assertClosed(result.negativeGeometry);
    assertClosed(result.positiveGeometry);
    assert.ok(Math.abs(signedVolume(result.negativeGeometry) + signedVolume(result.positiveGeometry) - volume) < volume * 1e-6);
  }
});

for (const [axis, plane] of [["z", 4], ["x", 2]] as const) {
  test(`torus ${axis}=${plane} hole-bearing/concave cut preserves its closed volume`, () => {
    const source = instance("torus"), original = new Float32Array(source.geometry.positions);
    const result = previewMeshPlaneSplit(source, axis, plane);
    assert.ok(result.crossingTriangleCount > 0);
    assert.equal(result.canApply, true);
    assert.ok(result.negativeGeometry && result.positiveGeometry);
    assertClosed(result.negativeGeometry); assertClosed(result.positiveGeometry);
    const sourceVolume = signedVolume(source.geometry);
    assert.ok(Math.abs(signedVolume(result.negativeGeometry) + signedVolume(result.positiveGeometry) - sourceVolume) < sourceVolume * 1e-6);
    assert.deepEqual(source.geometry.positions, original);
  });
}

function openHollowPrism(rotated = false): MeshGeometry {
  const outer = [[-2, -2], [2, -2], [2, 2], [-2, 2]], inner = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
  const positions: number[] = [];
  const vertex = (ring: number[][], index: number, height: number): number[] => {
    const [x, y] = ring[index]!;
    // A cyclic coordinate rotation changes the local cap axis without rounding.
    return rotated ? [height, x!, y!] : [x!, y!, height];
  };
  const quad = (a: number[], b: number[], c: number[], d: number[]): void => { positions.push(...a, ...b, ...c, ...a, ...c, ...d); };
  for (let i = 0; i < 4; i++) {
    const next = (i + 1) % 4;
    quad(vertex(outer, i, 0), vertex(inner, i, 0), vertex(inner, next, 0), vertex(outer, next, 0));
    quad(vertex(outer, i, 0), vertex(outer, next, 0), vertex(outer, next, 1), vertex(outer, i, 1));
    quad(vertex(inner, next, 0), vertex(inner, i, 0), vertex(inner, i, 1), vertex(inner, next, 1));
  }
  return geometryFromPositions(new Float32Array(positions));
}

for (const rotated of [false, true]) {
  test(`hollow prism cap closes the real annulus${rotated ? " after local-axis rotation" : ""}`, () => {
    const source = openHollowPrism(rotated), original = new Float32Array(source.positions);
    // The supplied world axis is deliberately unchanged for the rotated model.
    const result = generateCapFaces(source, "z");
    assert.ok(result.capCount > 0, "the missing annulus must receive a hole-aware cap");
    const full = geometryFromPositions(new Float32Array([...source.positions, ...result.capPositions]));
    assertClosed(full);
    assert.ok(Math.abs(signedVolume(full) - 12) < 1e-10, "the inner hole must retain its real volume");
    assert.deepEqual(source.positions, original);
  });
}
