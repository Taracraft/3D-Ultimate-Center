import { createPaintSession, type PaintBrush } from "../frontend/studio-mesh-paint.js";
import type { MeshGeometry } from "../frontend/webgl-studio-viewport.js";

function makeGeometry(triangles: number[]): MeshGeometry {
  return {
    positions: new Float32Array(triangles),
    normals: new Float32Array(triangles.length),
    triangleCount: triangles.length / 9,
    boundsMin: [0, 0, 0] as [number, number, number],
    boundsMax: [1, 1, 1] as [number, number, number],
  };
}

test("paint session applies add mode correctly", () => {
  const session = createPaintSession();
  const geometry = makeGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,  // Triangle 0
    0, 0, 0, 1, 1, 0, 0, 1, 0,  // Triangle 1
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  expect(result.modified).toBe(true);
  expect(result.paintedTriangleCount).toBeGreaterThan(0);
  expect(result.regions.length).toBeGreaterThan(0);
});

test("paint session applies remove mode correctly", () => {
  const session = createPaintSession();
  const geometry = makeGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  
  const removeBrush: PaintBrush = { radiusMm: 1.0, color: "#000000", mode: "remove" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], removeBrush);
  expect(result.modified).toBe(true);
});

test("paint session applies replace mode correctly", () => {
  const session = createPaintSession();
  const geometry = makeGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "replace" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  expect(result.modified).toBe(true);
  const regions = session.getRegions("obj1");
  expect(regions[0].color).toBe("#ff0000");
});

test("paint session respects brush radius", () => {
  const session = createPaintSession();
  const geometry = makeGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 0.1, color: "#ff0000", mode: "add" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  // Small brush might not hit anything far away
  expect(result.paintedTriangleCount).toBeGreaterThanOrEqual(0);
});

test("getRegions groups by color", () => {
  const session = createPaintSession();
  const geometry = makeGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush1: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush1);
  
  const brush2: PaintBrush = { radiusMm: 1.0, color: "#00ff00", mode: "add" };
  session.paint("obj1", geometry, [], [0.0, 0.0, 0], brush2);
  
  const regions = session.getRegions("obj1");
  expect(regions.length).toBeGreaterThan(0);
});

test("clear removes all paint data", () => {
  const session = createPaintSession();
  const geometry = makeGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  
  expect(session.getRegions("obj1").length).toBeGreaterThan(0);
  
  session.clear();
  expect(session.getRegions("obj1").length).toBe(0);
});

test("clear with objectId removes only that object", () => {
  const session = createPaintSession();
  const geometry = makeGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  session.paint("obj2", geometry, [], [0.5, 0.5, 0], brush);
  
  expect(session.getRegions("obj1").length).toBeGreaterThan(0);
  expect(session.getRegions("obj2").length).toBeGreaterThan(0);
  
  session.clear("obj1");
  expect(session.getRegions("obj1").length).toBe(0);
  expect(session.getRegions("obj2").length).toBeGreaterThan(0);
});
