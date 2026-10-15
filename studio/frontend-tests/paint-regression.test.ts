import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import { createPaintSession } from "../frontend/studio-mesh-paint.js";
import { projectedPaintHit } from "../frontend/studio-mega-viewport.js";
import type { MeshGeometry } from "../frontend/webgl-studio-viewport.js";

// These execute the actual production method bodies with explicit data dependencies.
// They do not claim DOM, WebGL or pointer-device acceptance.
function subject(file: string, names: string[], context: Record<string, unknown>, dependencies: Record<string, unknown> = {}): any {
  const source = readFileSync(join(process.env.CAD_BASELINE_ROOT || process.cwd(), "frontend", file), "utf8");
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  const methods: string[] = [];
  tree.forEachChild((node) => {
    if (!ts.isClassDeclaration(node)) return;
    for (const member of node.members) {
      if (ts.isMethodDeclaration(member) && names.includes(member.name.getText(tree))) methods.push(member.getText(tree).replace(/#/g, "_"));
    }
  });
  assert.equal(methods.length, names.length, "all requested production methods were found");
  const code = ts.transpileModule(`class Harness { constructor(context: any) { Object.assign(this, context); } ${methods.join("\n")} }`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
  return new Function("context", ...Object.keys(dependencies), `${code}; return new Harness(context);`)(context, ...Object.values(dependencies));
}

function geometry(positions: ArrayLike<number>): MeshGeometry {
  return { positions: new Float32Array(positions), normals: new Float32Array(positions.length), triangleCount: positions.length / 9, boundsMin: [0, 0, 0], boundsMax: [20, 20, 0] };
}

test("paint pick follows distinct pointer locations inside the same coarse triangle", () => {
  const mesh = geometry([-1, -1, 0, 1, -1, 0, -1, 1, 0]);
  const host = subject("studio-mega-viewport.ts", ["pickPaintPoint"], {
    canvas: { width: 100, height: 100, getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }) },
    _instances: [{ id: "model", visible: true, geometry: mesh }], _viewProjection: () => null,
  }, { multiply: () => null, modelMatrix: () => null, transformPoint: (_matrix: any, point: number[]) => [...point, 1], projectedPaintHit,
    pointInProjectedTriangle: () => true });
  assert.deepEqual(host.pickPaintPoint(10, 90).localPosition.map((x: number) => Math.round(x * 1000) / 1000), [-.8, -.8, 0]);
  assert.deepEqual(host.pickPaintPoint(30, 90).localPosition.map((x: number) => Math.round(x * 1000) / 1000), [-.4, -.8, 0]);
});

test("paint hit uses perspective-correct coordinates and interpolated depth", () => {
  const hit = projectedPaintHit({ x: 1, y: 1 }, [{ x: 0, y: 0, w: 1, depth: 0 }, { x: 4, y: 0, w: 2, depth: .4 }, { x: 0, y: 4, w: 4, depth: .8 }], [0, 0, 0, 8, 0, 0, 0, 16, 0]);
  assert.ok(hit);
  assert.ok(Math.abs(hit.localPosition[0] - 16 / 11) < 1e-10);
  assert.ok(Math.abs(hit.localPosition[1] - 16 / 11) < 1e-10);
  assert.ok(Math.abs(hit.depth - .3) < 1e-10);
  assert.equal(projectedPaintHit({ x: 1, y: 1 }, [{ x: 0, y: 0, w: 1, depth: 0 }, { x: 1, y: 1, w: 1, depth: 0 }, { x: 2, y: 2, w: 1, depth: 0 }], new Float32Array(9)), null);
});

test("paint pick selects the visible surface at the pointer instead of average triangle depth", () => {
  const mesh = geometry([-1, -1, -.9, 1, -1, .9, -1, 1, .9, -1, -1, 0, 1, -1, 0, -1, 1, 0]);
  const host = subject("studio-mega-viewport.ts", ["pickPaintPoint"], {
    canvas: { width: 100, height: 100, getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }) },
    _instances: [{ id: "model", visible: true, geometry: mesh }], _viewProjection: () => null,
  }, { multiply: () => null, modelMatrix: () => null, transformPoint: (_matrix: any, point: number[]) => [...point, 1], projectedPaintHit,
    pointInProjectedTriangle: () => true });
  assert.equal(host.pickPaintPoint(5, 95).triangleIndex, 0);
  assert.ok(Math.abs(host.pickPaintPoint(5, 95).localPosition[2] + .72) < 1e-6);
});

test("refreshing the selected loaded material also refreshes the brush color", () => {
  const host = subject("studio-paint-ui.ts", ["setMaterials"], { _materialKey: "ams:1", _color: "#ff0000", _render: () => {}, _emit: () => {} }, { normalColor: (value: string) => value });
  host.setMaterials([{ key: "ams:1", name: "PLA Blau", color: "#0000ff" }]);
  assert.equal(host._materialKey, "ams:1");
  assert.equal(host._color, "#0000ff");
});

test("object list renders imported object and material names as text", () => {
  const hostElement = { innerHTML: "", querySelectorAll: () => [] };
  const name = '<img src=x onerror="alert(1)">';
  const plate = { instances: [{ id: 'id" onclick="alert(1)', name, color: "#ff0000", geometry: { triangleCount: 2 } }] };
  const host = subject("studio-mega-workspace-v2.ts", ["#renderObjectList"], {
    _root: { querySelector: () => hostElement }, _plate: () => plate, _selected: new Set(),
    _paintMaterials: () => [{ key: "ams:1", name }], _paintLayersForPlate: () => [{ objectId: plate.instances[0]!.id, kind: "stroke", materialKey: "ams:1", color: "#ff0000", label: "Pinselstrich", points: [] }],
    _paintLayerSelectionId: () => "paint-layer:0", _paintRowsForSelection: () => [],
  }, { escapeHtml: (value: unknown) => String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]!)), normalizeColor: () => "#ff0000" });
  host._renderObjectList();
  assert.doesNotMatch(hostElement.innerHTML, /<img|data-object="id" onclick=/);
  assert.match(hostElement.innerHTML, /&lt;img/);
});
