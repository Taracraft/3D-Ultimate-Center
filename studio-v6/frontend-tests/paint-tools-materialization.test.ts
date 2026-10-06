import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import { createPaintSession, type PaintRegion } from "../frontend/studio-mesh-paint.js";
import { composePaintLayers, refinePaintLayers, type MaterialPaintLayer } from "../frontend/studio-paint-layers.js";
import { refinePaintGeometry, remapPaintRegions } from "../frontend/studio-paint-refinement.js";
import { paintMaskContains, paintMaskRuns, paintSamplingStep, validatePaintMask, type MaterialPaintMask } from "../frontend/studio-paint-mask.js";
import type { MeshGeometry } from "../frontend/webgl-studio-viewport.js";
import { clipPaintPolygon, projectedTriangleIntersectsPaintShape } from "../frontend/studio-mega-viewport.js";
import { clonePaintLayer, mirrorPaintLayer, restoreStudioPaintState } from "../frontend/studio-paint-state.js";
import { cloneWorkspaceSnapshot, workspaceHistorySignature } from "../frontend/studio-workspace-history.js";
import { ModelStateHistory } from "../frontend/model-state-history.js";
import { mirrorMeshGeometry } from "../frontend/studio-mesh-tools.js";
import type { PersistedStudioWorkspace } from "../frontend/studio-persistence.js";

function mesh(values: ArrayLike<number>): MeshGeometry {
  return { positions: new Float32Array(values), normals: new Float32Array(values.length), triangleCount: values.length / 9, boundsMin: [0, 0, 0], boundsMax: [20, 20, 0] };
}
const square = (): MeshGeometry => mesh([0, 0, 0, 20, 0, 0, 20, 20, 0, 0, 0, 0, 20, 20, 0, 0, 20, 0]);
const base: PaintRegion[] = [{ objectId: "part", triangleIndices: [0, 1], color: "#ff0000", materialKey: "ams:1", label: "Importfarbe" }];
const mask = (kind: MaterialPaintMask["kind"], extras: Partial<MaterialPaintMask> = {}): MaterialPaintMask => ({ kind, matrix: [.1,0,0,0, 0,.1,0,0, 0,0,1,0, -1,-1,0,1], left: .25, top: .25, right: .75, bottom: .75, ...extras });
const layer = (extras: Partial<MaterialPaintLayer> = {}): MaterialPaintLayer => ({ objectId: "part", kind: "stroke", label: "Pinselstrich", color: "#00ff00", materialKey: "ams:2", radiusMm: .8, points: [{ x: 8, y: 4, z: 0 }], ...extras });
const area = (geometry: MeshGeometry, indices: readonly number[]): number => indices.reduce((sum, triangle) => {
  const p = geometry.positions, b = triangle * 9;
  const ax = p[b + 3]! - p[b]!, ay = p[b + 4]! - p[b + 1]!, az = p[b + 5]! - p[b + 2]!;
  const bx = p[b + 6]! - p[b]!, by = p[b + 7]! - p[b + 1]!, bz = p[b + 8]! - p[b + 2]!;
  return sum + Math.hypot(ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx) / 2;
}, 0);

function subject(names: string[], context: Record<string, unknown>, dependencies: Record<string, unknown> = {}, file = "studio-mega-workspace-v2.ts"): any {
  const source = readFileSync(join(process.env.CAD_BASELINE_ROOT || process.cwd(), "frontend", file), "utf8");
  const tree = ts.createSourceFile("studio.ts", source, ts.ScriptTarget.Latest, true);
  const methods: string[] = [];
  tree.forEachChild((node) => {
    if (!ts.isClassDeclaration(node)) return;
    for (const member of node.members) if (ts.isMethodDeclaration(member) && names.includes(member.name.getText(tree))) methods.push(member.getText(tree).replace(/#/g, "_"));
  });
  assert.equal(methods.length, names.length);
  const code = ts.transpileModule(`class Harness { constructor(context: any) { Object.assign(this, context); } ${methods.join("\n")} }`, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
  return new Function("context", ...Object.keys(dependencies), `${code}; return new Harness(context);`)(context, ...Object.values(dependencies));
}
function workspace(layers: MaterialPaintLayer[], legacy = new Set<string>()) {
  const plate = { id: 0, instances: [{ id: "part", name: "Original.stl", scale: [1, 1, 1], geometry: square() }] };
  const other = { id: 1, instances: [{ id: "other", name: "Andere Platte.stl", scale: [1, 1, 1], geometry: square() }] };
  const session = createPaintSession();
  const getBase = (value: typeof plate): readonly PaintRegion[] => value.instances.flatMap((item) => session.getRegions(item.id));
  const host = subject(["#materializePaintLayersForSlicing", "#paintRegionsForPlate", "#createPaintLayer"], {
    _plates: [plate, other], _paintSession: session, _paintGeometryFailures: new Set(), _paintLegacyAmbiguousObjectIds: legacy,
    _paintBaseRegionsForPlate: getBase, _paintLayersForPlate: (value: typeof plate) => value.id === 0 ? layers : [], _nextPaintLayerId: 1,
    _setPaintLayersForPlate: (_plate: unknown, value: MaterialPaintLayer[]) => layers.splice(0, layers.length, ...value),
  }, { geometry: mesh, composePaintLayers, refinePaintLayers, normalizeColor: (value: string) => value });
  return { host, plate, other, session };
}

test("original unknown triangle cannot become valid after adaptive refinement", () => {
  const geometry = square(), before = [...geometry.positions];
  for (const invalid of [2, 7, -1, .5, Infinity]) {
    const regions = [{ ...base[0]!, triangleIndices: [invalid] }];
    assert.throws(() => refinePaintLayers("part", geometry, regions, [layer()]), /ursprüngliches Dreieck/);
    assert.deepEqual([...geometry.positions], before);
    assert.deepEqual(regions[0]!.triangleIndices, [invalid]);
  }
});

test("remapping rejects missing original indices instead of keeping accidentally valid numbers", () => {
  const refined = refinePaintGeometry(square(), [0], { targetEdgeMm: .35 });
  assert.throws(() => remapPaintRegions([{ ...base[0]!, triangleIndices: [4] }], "part", refined.triangleIndexMap), /ursprüngliches Dreieck/);
  assert.throws(() => refinePaintGeometry(square(), [4]), /ursprüngliches Dreieck/);
});

test("adaptive materialization activates real fine geometry and preserves every base material", () => {
  const { host, plate, session } = workspace([layer()]);
  session.replace([...base, { ...base[0]!, objectId: "other", triangleIndices: [0] }]);
  const otherBefore = session.getRegions("other");
  host._materializePaintLayersForSlicing(plate);
  const geometry = plate.instances[0]!.geometry;
  assert.ok(geometry.triangleCount > 2);
  assert.equal(plate.instances[0]!.name, "Original.stl");
  const regions: PaintRegion[] = host._paintRegionsForPlate(plate, true);
  const painted = regions.filter((region) => region.materialKey === "ams:2").flatMap((region) => region.triangleIndices);
  assert.ok(painted.length > 0);
  for (const triangle of painted) {
    const b = triangle * 9, p = geometry.positions;
    for (let edge = 0; edge < 3; edge += 1) {
      const a = b + edge * 3, c = b + (edge + 1) % 3 * 3;
      assert.ok(Math.hypot(p[a]! - p[c]!, p[a + 1]! - p[c + 1]!, p[a + 2]! - p[c + 2]!) <= .35001);
    }
  }
  assert.ok(Math.abs(area(geometry, regions.flatMap((region) => region.triangleIndices)) - 400) < 1e-4);
  assert.deepEqual(session.getRegions("other"), otherBefore);
});

test("circle mask creates the requested area on coarse geometry without sphere overspray", () => {
  const stroke = layer({ kind: "circle", radiusMm: 30, points: [{ x: 10, y: 10, z: 0 }], mask: mask("circle") });
  const refined = refinePaintLayers("part", square(), [], [stroke]);
  const geometry = mesh(refined.positions);
  const regions = composePaintLayers([{ id: "part", geometry }], [], [stroke]);
  const indices = regions.flatMap((region) => region.triangleIndices);
  assert.ok(Math.abs(area(geometry, indices) - Math.PI * 25) < 1.0);
  assert.ok(indices.length > 100);
  for (const triangle of indices) {
    const p = geometry.positions, b = triangle * 9;
    const x = (p[b]! + p[b + 3]! + p[b + 6]!) / 3, y = (p[b + 1]! + p[b + 4]! + p[b + 7]!) / 3;
    assert.ok((x - 10) ** 2 + (y - 10) ** 2 <= 25.0001);
  }
});

test("rectangle mask preserves sharp boundaries independently of brush radius", () => {
  const stroke = layer({ kind: "rectangle", radiusMm: 30, points: [{ x: 10, y: 10, z: 0 }], mask: mask("rectangle", { right: .5, bottom: .5 }) });
  const refined = refinePaintLayers("part", square(), [], [stroke]);
  const geometry = mesh(refined.positions), regions = composePaintLayers([{ id: "part", geometry }], [], [stroke]);
  assert.ok(Math.abs(area(geometry, regions.flatMap((region) => region.triangleIndices)) - 25) < .5);
});

test("eraser is a reversible material operation and leaves the saved base untouched", () => {
  const layers = [layer({ mode: "remove", label: "Radierer" })], { host, plate, session } = workspace(layers);
  session.replace(base);
  host._materializePaintLayersForSlicing(plate);
  const saved = session.getRegions("part"), savedJson = JSON.stringify(saved);
  const count = host._paintRegionsForPlate(plate).flatMap((region: PaintRegion) => region.triangleIndices).length;
  assert.ok(count < saved.flatMap((region) => region.triangleIndices).length);
  layers.splice(0);
  assert.equal(JSON.stringify(session.getRegions("part")), savedJson);
  assert.deepEqual(host._paintRegionsForPlate(plate), saved);
});

test("new remove gestures remain provisional and carry explicit eraser semantics", () => {
  const layers: MaterialPaintLayer[] = [], { host, plate } = workspace(layers);
  const created = host._createPaintLayer(plate, "part", "stroke", { radiusMm: 1, color: "#00ff00", mode: "remove", materialKey: "ams:2" }, "Radierer");
  assert.equal(created.mode, "remove");
  assert.equal(layers.length, 0, "unfinished gestures must not enter persistence");
});

test("ambiguous legacy projects retain their exact raster export and immutable saved base", () => {
  const layers = [layer({ label: "Radierer", mode: undefined, radiusMm: 30 })], { host, plate, session } = workspace(layers, new Set(["part"]));
  session.replace(base);
  const positions = plate.instances[0]!.geometry.positions, before = JSON.stringify(session.getRegions("part"));
  host._materializePaintLayersForSlicing(plate);
  assert.equal(plate.instances[0]!.geometry.positions, positions);
  assert.equal(JSON.stringify(host._paintRegionsForPlate(plate)), before);
  const exported = host._paintRegionsForPlate(plate, true);
  assert.equal(exported[0].materialKey, "ams:2");
  assert.deepEqual(exported[0].triangleIndices, [0, 1]);
  assert.equal(JSON.stringify(session.getRegions("part")), before);
});

test("text alpha has exact foreground and holes with no empty-text fallback dot", () => {
  const alpha = new Uint8ClampedArray(5 * 5 * 4);
  for (let y = 0; y < 5; y += 1) for (let x = 0; x < 5; x += 1) if (y === 0 || x === 2) alpha[(y * 5 + x) * 4 + 3] = 255;
  const textMask = mask("text", { left: 0, top: 0, right: 1, bottom: 1, width: 5, height: 5, runs: paintMaskRuns(alpha, 5, 5) });
  validatePaintMask(textMask);
  assert.equal(paintMaskContains(textMask, 10, 10, 0), true);
  assert.equal(paintMaskContains(textMask, 2, 10, 0), false);
  assert.equal(paintMaskContains(textMask, 2, 18, 0), true);
  const empty = { ...textMask, runs: paintMaskRuns(new Uint8ClampedArray(100), 5, 5) };
  assert.equal(paintMaskContains(empty, 10, 10, 0), false);
  assert.deepEqual(empty.runs, []);
});

test("invalid projection and text runs fail closed before model composition", () => {
  for (const invalid of [mask("circle", { matrix: [1] }), mask("circle", { right: .25 }), mask("text", { width: 5, height: 5, runs: [0, 30] }), mask("text", { width: 5, height: 5, runs: [0, 4, 3, 5] })]) {
    assert.throws(() => composePaintLayers([{ id: "part", geometry: square() }], base, [layer({ mask: invalid })]), /Maske|maske|Malform|Pixelbereiche/);
  }
  assert.deepEqual(base[0]!.triangleIndices, [0, 1]);
});

test("allocation and work limits leave geometry, base regions and other plates unchanged", () => {
  const original = square(), positions = [...original.positions], before = JSON.stringify(base);
  assert.throws(() => refinePaintGeometry(original, [0], { targetEdgeMm: .01, maxTriangles: 20 }), /Dreiecksbudget/);
  assert.throws(() => refinePaintLayers("part", original, base, [layer()], .35, { maxWork: 1 }), /aufwendig/);
  assert.throws(() => composePaintLayers([{ id: "part", geometry: original }], base, [layer()], { maxWork: 1 }), /Rechenbudget/);
  assert.deepEqual([...original.positions], positions);
  assert.equal(JSON.stringify(base), before);
});

test("scaled geometry reaches the requested sub-quarter-millimeter local edge", () => {
  const stroke = layer({ radiusMm: .2 });
  const refined = refinePaintLayers("part", square(), [], [stroke], .175);
  const geometry = mesh(refined.positions), regions = composePaintLayers([{ id: "part", geometry }], [], [stroke]);
  for (const triangle of regions.flatMap((region) => region.triangleIndices)) {
    const p = geometry.positions, b = triangle * 9;
    for (let edge = 0; edge < 3; edge += 1) {
      const a = b + edge * 3, c = b + (edge + 1) % 3 * 3;
      assert.ok(Math.hypot(p[a]! - p[c]!, p[a + 1]! - p[c + 1]!, p[a + 2]! - p[c + 2]!) <= .17501);
    }
  }
  assert.ok(regions.length);
});

// Boundary doubles supply canvas/viewport transport only. The registered production gesture
// handlers, transaction ordering, refinement and material composition execute unmodified.
function gestureWorkspace(tool: string, options: { guard?: () => void; contextAvailable?: boolean } = {}) {
  const handlers = new Map<string, (event: any) => void>();
  const toolHandlers = new Map<string, () => void>();
  const draw = new Proxy({}, { get: (_object, name) => name === "getImageData" ? () => ({ data: new Uint8ClampedArray(0) }) : () => {} });
  const canvas = { width: 100, height: 100, classList: { toggle() {} }, getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }), setPointerCapture() {}, addEventListener: (name: string, callback: (event: any) => void) => handlers.set(name, callback) };
  const overlay = { width: 100, height: 100, getContext: () => draw };
  const button = { getTool: () => tool, isActive: () => tool !== "select", getBrush: () => ({ radiusMm: .8, color: "#00ff00", materialKey: "ams:2", mode: tool === "eraser" ? "remove" : "add" }), getText: () => "T", getTextSizePx: () => 28, setMaterials() {}, addEventListener: (name: string, handler: () => void) => toolHandlers.set(name, handler) };
  class ViewportBoundary {
    setPreviewMode() {} setInstances() {} setSelected() {} setGizmo() {} frameAll() {} setPaintRegions() {} dispose() {}
    pick() { return "part"; }
    pickSelectionRectangle() { return new Map([["part", [0]]]); }
    getPaintProjection() { return [.1,0,0,0, 0,.1,0,0, 0,0,1,0, -1,-1,0,1]; }
    pickPaintPoint(x: number, y: number) { return x < 0 || x > 100 || y < 0 || y > 100 ? null : { objectId: "part", triangleIndex: 0, localPosition: [x / 5, (100 - y) / 5, 0], distancePx: 0 }; }
  }
  const plate = { id: 0, stage: "prepared", instances: [{ id: "part", name: "Plane", visible: true, scale: [1, 1, 1], geometry: square() }] };
  let layers: any[] = [];
  const observedLayers: any[] = [];
  const session = createPaintSession();
  let persisted = 0;
  const host = subject(["#mountViewport", "#materializePaintLayersForSlicing", "#paintRegionsForPlate", "#paintRegions", "#createPaintLayer", "#paintLayerSelectionId", "#setTool"], {
    _root: { querySelector: (name: string) => name === "canvas" ? canvas : name === "canvas.paint-shape-preview" ? overlay : null },
    _paintButton: () => button, _paintMaterials: () => [], _profileVisual: () => ({}), _displayInstances: () => plate.instances,
    _center: () => [0, 0, 0], _refreshToolUi() {}, _tool: "select", _gizmoAxis: () => "free", _mode: "prepare", _selected: new Set(),
    _plates: [plate], _plate: () => plate, _paintSession: session, _paintGeometryFailures: new Set(), _paintLegacyAmbiguousObjectIds: new Set(),
    _paintBaseRegionsForPlate: () => session.getRegions("part"), _paintLayersForPlate: () => layers, _nextPaintLayerId: 1,
    _setPaintLayersForPlate: (_plate: unknown, value: any[]) => { layers = value; observedLayers.splice(0, observedLayers.length, ...value); },
    _assertPaintEditable: options.guard || (() => {}), _historyReady: false, _invalidatePlate() {}, _renderObjectList() {}, _renderStatus() {},
    _schedulePersist: () => { persisted += 1; }, _refreshSelectionUi() {},
    _paintSelectionId: (index: number) => `paint:${index}`, _paintRowsForSelection: () => session.getRegions("part"),
    _select: (...args: unknown[]) => { host.lastSelection = args; },
  }, { StudioMegaViewport: ViewportBoundary, requestAnimationFrame: () => 0, geometry: mesh, composePaintLayers, refinePaintLayers, paintMaskContains, paintMaskRuns, paintSamplingStep, normalizeColor: (value: string) => value,
    PointerEvent: class { constructor(public type: string, attributes: object) { Object.assign(this, attributes); } },
    document: { createElement: () => ({ getContext: () => options.contextAvailable === false ? null : draw }) },
  });
  host._mountViewport();
  const dispatch = (type: string, x: number, y: number, modifiers: Record<string, unknown> = {}) => handlers.get(type)!({ type, clientX: x, clientY: y, pointerId: 1, button: 0, buttons: 1, preventDefault() {}, stopImmediatePropagation() {}, ...modifiers });
  return { host, plate, layers: observedLayers, session, dispatch, paintChange: () => toolHandlers.get("studio-paint-change")!(), persisted: () => persisted };
}

test("production circle gesture commits a projection mask and fine material geometry only at pointerup", () => {
  const { plate, layers, dispatch, persisted, host } = gestureWorkspace("circle");
  dispatch("pointerdown", 40, 40);
  dispatch("pointermove", 60, 60);
  assert.equal(layers.length, 0);
  assert.equal(persisted(), 0);
  dispatch("pointerup", 60, 60);
  assert.equal(layers.length, 1);
  assert.equal(layers[0].mask.kind, "circle");
  assert.ok(plate.instances[0]!.geometry.triangleCount > 2);
  assert.ok(host._paintRegionsForPlate(plate, true).length);
  assert.equal(persisted(), 1);
});

test("production pointercancel discards only the unfinished stroke and never persists it", () => {
  const { layers, session, dispatch, persisted } = gestureWorkspace("brush");
  session.replace(base);
  const before = JSON.stringify(session.getRegions("part"));
  dispatch("pointerdown", 40, 40);
  dispatch("pointermove", 50, 50);
  assert.equal(layers.length, 0);
  dispatch("pointercancel", 50, 50);
  assert.equal(layers.length, 0);
  assert.equal(persisted(), 0);
  assert.equal(JSON.stringify(session.getRegions("part")), before);
});

test("production straight-line gesture samples continuously and retains explicit material mode", () => {
  const { layers, plate, dispatch, host } = gestureWorkspace("line");
  dispatch("pointerdown", 25, 50);
  dispatch("pointerup", 75, 50);
  assert.equal(layers.length, 1);
  assert.equal(layers[0].kind, "stroke");
  assert.equal(layers[0].mode, "add");
  assert.ok(layers[0].points.length > 25);
  const regions: PaintRegion[] = host._paintRegionsForPlate(plate, true);
  assert.ok(regions.flatMap((region) => region.triangleIndices).length > 20);
});

test("production guarded legacy edits and unavailable text canvas leave saved data untouched", () => {
  const guarded = gestureWorkspace("eraser", { guard: () => { throw new Error("Historischer Malstand benötigt eine Entscheidung."); } });
  guarded.session.replace(base);
  guarded.dispatch("pointerdown", 50, 50);
  assert.equal(guarded.layers.length, 0);
  assert.match(guarded.host._status, /Historischer Malstand/);
  assert.deepEqual(guarded.session.getRegions("part")[0]!.triangleIndices, [0, 1]);
  const text = gestureWorkspace("text", { contextAvailable: false });
  text.dispatch("pointerdown", 50, 50);
  assert.equal(text.layers.length, 0);
  assert.match(text.host._status, /Textmaske/);
  assert.equal(text.persisted(), 0);
});

test("painting the front of a thin wall does not assign material to the opposite back face", () => {
  const geometry = mesh([0,0,0, 1,0,0, 0,1,0, 0,0,-.1, 0,1,-.1, 1,0,-.1]);
  const stroke = layer({ radiusMm: 2, points: [{ x: .3, y: .3, z: 0, normal: [0, 0, 1] }] });
  const refined = refinePaintLayers("part", geometry, [], [stroke]);
  const resultGeometry = mesh(refined.positions);
  const regions = composePaintLayers([{ id: "part", geometry: resultGeometry }], [], [stroke]);
  for (const triangle of regions.flatMap((region) => region.triangleIndices)) assert.equal(resultGeometry.positions[triangle * 9 + 2], 0);
  assert.ok(regions.length);
});

test("projected brush sampling adapts to zoom and rejects unresolvable subpixel work", () => {
  const camera = mask("circle").matrix;
  const near = paintSamplingStep(camera, [10, 10, 0], .8, 100, 100);
  const far = paintSamplingStep(camera, [10, 10, 0], .8, 20, 20);
  assert.ok(far < near);
  assert.throws(() => paintSamplingStep(camera, [10, 10, 0], .001, 100, 100), /heranzoomen/);
});

test("production stroke fills its final segment even when pointerup arrives without another move", () => {
  const { layers, dispatch } = gestureWorkspace("brush");
  dispatch("pointerdown", 25, 50);
  dispatch("pointerup", 75, 50);
  assert.equal(layers.length, 1);
  assert.ok(layers[0].points.length > 20);
  for (let index = 1; index < layers[0].points.length; index += 1) {
    const a = layers[0].points[index - 1], b = layers[0].points[index];
    assert.ok(Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) <= layers[0].radiusMm);
  }
});

function projectSerialization() {
  const source = readFileSync(join(process.cwd(), "frontend/studio-project-api.ts"), "utf8");
  const tree = ts.createSourceFile("project-api.ts", source, ts.ScriptTarget.Latest, true);
  const functions: string[] = [];
  tree.forEachChild((node) => { if (ts.isFunctionDeclaration(node) && ["plainSnapshot", "workspaceSnapshot"].includes(node.name?.getText(tree) || "")) functions.push(node.getText(tree)); });
  assert.equal(functions.length, 2);
  const code = ts.transpileModule(functions.join("\n"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
  return new Function("clonePaintLayer", `${code}; return {plainSnapshot, workspaceSnapshot};`)(clonePaintLayer);
}

function snapshotFixture(kind: "circle" | "text"): PersistedStudioWorkspace {
  const geometry = square(), stroke = layer({ kind, radiusMm: 30, points: [{ x: 10, y: 10, z: 0, normal: [0, 0, 1] }], mask: kind === "circle" ? mask("circle") : mask("text", { width: 3, height: 3, runs: [0, 3, 4, 5, 7, 8] }) });
  return { version: 1, savedAt: 1, activePlate: 0, mode: "colors", nextId: 2, selected: [], assignments: [], modelMaterials: [], paintCompositionVersion: 1, paintLegacyAmbiguousObjectIds: [], paintRegions: [], paintLayers: [[0, [{ ...stroke, id: "paint-layer-1", plateId: 0, points: stroke.points.map((point) => ({ ...point, screenX: .5, screenY: .5 })) }]]], nextPaintLayerId: 2,
    plates: [{ id: 0, name: "Platte 1", width: 256, depth: 256, selection: { filament_profile_ids: [] } as any, instances: [{ id: "part", name: "Original.stl", positions: geometry.positions, position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], color: "#ff0000", visible: true }] }] };
}

function materializedSnapshot(snapshot: PersistedStudioWorkspace): { regions: readonly PaintRegion[]; area: number } {
  const state = restoreStudioPaintState(snapshot), current = snapshot.plates[0]!, saved = current.instances[0]!;
  const plate = { ...current, instances: [{ ...saved, geometry: mesh(saved.positions) }] };
  const session = createPaintSession(); session.replace(state.regions);
  const host = subject(["#materializePaintLayersForSlicing", "#paintRegionsForPlate"], {
    _plates: [plate], _paintSession: session, _paintGeometryFailures: new Set(), _paintLegacyAmbiguousObjectIds: state.legacyAmbiguousObjectIds,
    _paintBaseRegionsForPlate: () => session.getRegions("part"), _paintLayersForPlate: () => state.layers.get(0) || [],
  }, { geometry: mesh, composePaintLayers, refinePaintLayers });
  host._materializePaintLayersForSlicing(plate);
  const regions = host._paintRegionsForPlate(plate, true) as readonly PaintRegion[];
  return { regions, area: area(plate.instances[0]!.geometry, regions.flatMap((region) => region.triangleIndices)) };
}

test("real project serialization, restore and Undo/Redo retain circle/text masks and the same material faces", () => {
  const api = projectSerialization();
  for (const kind of ["circle", "text"] as const) {
    const snapshot = snapshotFixture(kind), expected = materializedSnapshot(snapshot);
    const restored = api.workspaceSnapshot(JSON.parse(JSON.stringify(api.plainSnapshot(snapshot)))) as PersistedStudioWorkspace;
    assert.deepEqual(restored.paintLayers, snapshot.paintLayers);
    assert.deepEqual(materializedSnapshot(restored).regions, expected.regions);
    const history = new ModelStateHistory({ clone: cloneWorkspaceSnapshot, signature: workspaceHistorySignature });
    history.reset(restored);
    const moved = cloneWorkspaceSnapshot(restored);
    moved.plates[0]!.instances[0] = { ...moved.plates[0]!.instances[0]!, position: [20, 30, 40], rotation: [45, 90, 135] };
    history.checkpoint(moved);
    assert.deepEqual(materializedSnapshot(history.undo()!).regions, expected.regions);
    assert.deepEqual(materializedSnapshot(history.redo()!).regions, expected.regions);
    const copied = cloneWorkspaceSnapshot(restored);
    copied.paintLayers[0]![1][0]!.mask!.matrix[0] = 999;
    copied.paintLayers[0]![1][0]!.points[0]!.normal![2] = -1;
    if (copied.paintLayers[0]![1][0]!.mask!.runs) copied.paintLayers[0]![1][0]!.mask!.runs![0] = 1;
    assert.equal(restored.paintLayers[0]![1][0]!.mask!.matrix[0], .1);
    assert.equal(restored.paintLayers[0]![1][0]!.points[0]!.normal![2], 1);
    assert.deepEqual(materializedSnapshot(restored).regions, expected.regions);
  }
});

test("rescaling after restoration changes sampling resolution without moving the saved local shape", () => {
  const snapshot = snapshotFixture("circle"), original = materializedSnapshot(snapshot);
  const restored = cloneWorkspaceSnapshot(snapshot);
  restored.plates[0]!.instances[0] = { ...restored.plates[0]!.instances[0]!, scale: [2, 2, 2] };
  const scaled = materializedSnapshot(restored);
  assert.ok(Math.abs(scaled.area - original.area) < .5);
  assert.ok(scaled.regions.flatMap((region) => region.triangleIndices).length > original.regions.flatMap((region) => region.triangleIndices).length);
  assert.deepEqual(restored.paintLayers[0]![1][0]!.mask, snapshot.paintLayers[0]![1][0]!.mask);
});

test("rectangle selection clips crossing triangles and excludes geometry behind the far plane", () => {
  const front = mesh([-.5,-.5,0, .5,-.5,0, 0,.5,0]);
  const far = mesh([-.5,-.5,5, .5,-.5,5, 0,.5,5]);
  const crossing = clipPaintPolygon([[-.5,-.5,-2,1], [.5,-.5,0,1], [0,.5,0,1]]);
  assert.ok(crossing.length >= 3);
  assert.ok(crossing.every((vertex) => vertex[2]! >= -vertex[3]! && vertex[2]! <= vertex[3]!));
  assert.deepEqual(clipPaintPolygon([[-.5,-.5,0,-1], [.5,-.5,0,-1], [0,.5,0,-1]]), []);
  const host = subject(["pickSelectionRectangle", "pickPaintShape"], {
    canvas: { width: 100, height: 100, getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }) },
    _instances: [{ id: "front", visible: true, geometry: front }, { id: "far", visible: true, geometry: far }, { id: "hidden", visible: false, geometry: front }], _viewProjection: () => null,
  }, { multiply: () => null, modelMatrix: () => null, transformPoint: (_matrix: unknown, point: number[]) => [...point, 1], clipPaintPolygon, projectedTriangleIntersectsPaintShape }, "studio-mega-viewport.ts");
  assert.deepEqual([...host.pickSelectionRectangle(40, 40, 60, 60).keys()], ["front"]);
  assert.equal(host.pickSelectionRectangle(0, 0, 10, 10).size, 0);
});

test("production Ctrl-drag frame adds models and paint entries while preserving existing selection", () => {
  const { host, session, dispatch } = gestureWorkspace("select");
  session.replace(base);
  host._selected = new Set(["previous"]);
  host._paintLayersForPlate = () => [layer({ points: [{ x: 10, y: 10, z: 0 }] })];
  dispatch("pointerdown", 40, 40, { ctrlKey: true });
  dispatch("pointermove", 60, 60, { ctrlKey: true });
  assert.deepEqual([...host._selected], ["previous"]);
  dispatch("pointerup", 60, 60, { ctrlKey: true });
  assert.deepEqual([...host._selected], ["previous", "part", "paint-layer:0", "paint:0"]);
});

test("production Ctrl-click retains toggle behavior instead of becoming a tiny selection rectangle", () => {
  const { host, dispatch } = gestureWorkspace("select");
  dispatch("pointerdown", 50, 50, { ctrlKey: true });
  dispatch("pointerup", 50, 50, { ctrlKey: true, shiftKey: false });
  assert.deepEqual(host.lastSelection, ["part", true, false]);
});

test("production cancelled selection frame leaves selection and model data unchanged", () => {
  const { host, dispatch, plate, persisted } = gestureWorkspace("select");
  host._selected = new Set(["previous"]);
  const positions = plate.instances[0]!.geometry.positions;
  dispatch("pointerdown", 40, 40, { metaKey: true });
  dispatch("pointermove", 60, 60, { metaKey: true });
  dispatch("pointercancel", 60, 60, { metaKey: true });
  assert.deepEqual([...host._selected], ["previous"]);
  assert.equal(plate.instances[0]!.geometry.positions, positions);
  assert.equal(persisted(), 0);
});

test("100000 coarse triangles hit the allocation guard before replacing any model data", () => {
  const values = new Float32Array(100_000 * 9), triangle = [0,0,0, 20,0,0, 0,20,0];
  for (let index = 0; index < 100_000; index += 1) values.set(triangle, index * 9);
  const geometry = mesh(values), region = [{ ...base[0]!, triangleIndices: [0, 99_999] }];
  const before = geometry.positions, regionBefore = JSON.stringify(region);
  assert.throws(() => refinePaintLayers("part", geometry, region, [layer({ radiusMm: 30, points: [{ x: 10, y: 10, z: 0 }] })]), /250\.000 Dreiecke/);
  assert.equal(geometry.positions, before);
  assert.equal(geometry.positions.length, 900_000);
  assert.equal(JSON.stringify(region), regionBefore);
});

test("Escape tool transition discards pending paint before a late pointerup", () => {
  const { host, layers, dispatch, persisted } = gestureWorkspace("brush");
  dispatch("pointerdown", 30, 50);
  dispatch("pointermove", 50, 50);
  host._setTool("select"); // actual key handler routes Escape to this production method
  dispatch("pointerup", 70, 50);
  assert.equal(layers.length, 0);
  assert.equal(persisted(), 0);
});

test("lost capture and paint-panel changes discard unfinished stroke or shape", () => {
  for (const tool of ["brush", "circle"] as const) {
    for (const reason of ["capture", "panel"] as const) {
      const state = gestureWorkspace(tool);
      state.dispatch("pointerdown", 30, 40);
      state.dispatch("pointermove", 50, 60);
      if (reason === "capture") state.dispatch("lostpointercapture", 50, 60); else state.paintChange();
      state.dispatch("pointerup", 70, 70);
      assert.equal(state.layers.length, 0, `${tool}/${reason}`);
      assert.equal(state.persisted(), 0);
    }
  }
});

test("Escape and lost capture cancel additive selection frames without selecting on later pointerup", () => {
  for (const reason of ["escape", "capture"] as const) {
    const state = gestureWorkspace("select");
    state.host._selected = new Set(["previous"]);
    state.dispatch("pointerdown", 30, 30, { ctrlKey: true });
    state.dispatch("pointermove", 70, 70, { ctrlKey: true });
    if (reason === "escape") state.host._setTool("select"); else state.dispatch("lostpointercapture", 70, 70);
    state.dispatch("pointerup", 70, 70, { ctrlKey: true });
    assert.deepEqual([...state.host._selected], ["previous"]);
  }
});

test("a second touch cannot replace the active transient painting gesture", () => {
  const state = gestureWorkspace("brush");
  state.dispatch("pointerdown", 30, 50);
  state.dispatch("pointerdown", 80, 80, { pointerId: 2 });
  state.dispatch("pointerup", 90, 90, { pointerId: 2 });
  assert.equal(state.layers.length, 0);
  state.dispatch("pointerup", 50, 50);
  assert.equal(state.layers.length, 1);
  assert.ok(state.layers[0].points.every((point: { y: number }) => point.y === 10));
});

test("unsupported extreme scales fail closed instead of silently using a coarse world-space paint raster", () => {
  const geometry = square(), before = geometry.positions;
  assert.throws(() => refinePaintLayers("part", geometry, [], [layer()], .0035), /Skalierung/);
  assert.equal(geometry.positions, before);
});

test("mirror at fractional text-pixel boundaries preserves every material triangle", () => {
  const snapshot = snapshotFixture("text"), source = snapshot.paintLayers[0]![1][0]!;
  const textLayer = { ...source, mask: { ...source.mask!, runs: [0, 3, 4, 5, 6, 9] } };
  const refined = refinePaintLayers("part", square(), [], [textLayer]);
  const geometry = mesh(refined.positions), normal = composePaintLayers([{ id: "part", geometry }], [], [textLayer]);
  const mirroredGeometry = mirrorMeshGeometry(geometry, "x"), mirroredLayer = mirrorPaintLayer(textLayer, "x", 10);
  const mirrored = composePaintLayers([{ id: "part", geometry: mirroredGeometry }], [], [mirroredLayer]);
  assert.deepEqual(mirrored, normal);
  const twice = composePaintLayers([{ id: "part", geometry: mirrorMeshGeometry(mirroredGeometry, "x") }], [], [mirrorPaintLayer(mirroredLayer, "x", 10)]);
  assert.deepEqual(twice, normal);
});

test("optional masks on non-text layers cannot hide unbounded or malformed run buffers", () => {
  assert.doesNotThrow(() => validatePaintMask(mask("rectangle", { runs: [0, 4, 9, 12] })));
  assert.throws(() => validatePaintMask(mask("circle", { runs: [0, 1_000_001] })), /Maskenbereiche/);
  assert.throws(() => validatePaintMask(mask("rectangle", { runs: [0, 4, 2, 5] })), /Maskenbereiche/);
});
