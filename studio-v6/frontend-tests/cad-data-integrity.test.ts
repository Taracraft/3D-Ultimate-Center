import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { createPaintSession } from "../frontend/studio-mesh-paint.js";
import { clonePaintLayer, restoreStudioPaintState, remapPaintLayerPlates, paintEditConflict, remapObjectPaintRegions, mirrorPaintLayer } from "../frontend/studio-paint-state.js";
import { readPlateLocalSettings, writePlateLocalSettings, reindexPlateLocalSettings } from "../frontend/studio-plate-storage.js";
import { ModelStateHistory } from "../frontend/model-state-history.js";
import { cloneWorkspaceSnapshot, workspaceHistorySignature } from "../frontend/studio-workspace-history.js";
import type { PersistedStudioWorkspace } from "../frontend/studio-persistence.js";
import { geometryFromPositions, mirrorMeshGeometry } from "../frontend/studio-mesh-tools.js";
import { transformPoint } from "../frontend/mesh-export.js";
import { generateCapFaces } from "../frontend/studio-mesh-cap.js";
import { nextStudioSelection, selectAllStudioObjects } from "../frontend/studio-selection.js";
import { preparePaintedExport, buildPaintedExportMeshes, localExportMaterialPlan } from "../frontend/studio-painted-export.js";
import { export3mfStreamed } from "../frontend/three-mf-export-stream.js";
import { inflateRawSync } from "node:zlib";

// Execute the selected production methods with explicit state/IO doubles.
// This is deliberately not a browser, layout, WebGL or touch acceptance test.
const sourceRoot = process.env.CAD_SOURCE_ROOT || process.cwd();
function method(name: string, dependencies: Record<string, unknown> = {}): (...args: any[]) => any {
  const filename = join(sourceRoot, "frontend/studio-mega-workspace-v2.ts");
  const source = ts.createSourceFile(filename, readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true);
  const declaration = source.statements.find((node) => ts.isClassDeclaration(node) && node.name?.text === "Ultimate3DMegaStudioV2") as ts.ClassDeclaration;
  const member = declaration.members.find((item) => item.name?.getText(source) === `#${name}`);
  assert.ok(member, `production method ${name} exists`);
  const compiled = ts.transpileModule(`exports.Subject = class Subject { ${member.getText(source)} };`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    transformers: { before: [(context) => {
      const visit: ts.Visitor = (node) => ts.isPrivateIdentifier(node)
        ? ts.factory.createIdentifier(node.text.slice(1)) : ts.visitEachChild(node, visit, context);
      return (file) => ts.visitNode(file, visit) as ts.SourceFile;
    }] },
  }).outputText;
  const exports: any = {};
  runInNewContext(compiled, { exports, Map, Set, Float32Array, Date, Math, Number, String, console,
    clonePaintLayer, restoreStudioPaintState, remapPaintLayerPlates, paintEditConflict, remapObjectPaintRegions, mirrorPaintLayer,
    readPlateLocalSettings, writePlateLocalSettings, reindexPlateLocalSettings, createPaintSession,
    preparePaintedExport, buildPaintedExportMeshes, localExportMaterialPlan,
    ...dependencies });
  if (typeof exports.Subject.prototype[name] === "function") return exports.Subject.prototype[name];
  return function(this: any, ...args: any[]) {
    const subject = Object.assign(new exports.Subject(), this);
    const result = subject[name](...args);
    for (const key of Object.keys(subject)) if (key !== name) this[key] = subject[key];
    return result;
  };
}

function productionModule(fileName: string, dependencies: Record<string, unknown>): any {
  const source = readFileSync(join(sourceRoot, "frontend", fileName), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  const exports: any = {};
  runInNewContext(compiled, { exports, Map, Set, Float32Array, Uint32Array, Date, Number, String, JSON, Headers, Response,
    require: (name: string) => { assert.ok(Object.hasOwn(dependencies, name), `declared IO dependency ${name}`); return dependencies[name]; } });
  return exports;
}

const triangle = new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]);
function item(id: string): any { return { id, name: id, geometry: { positions: new Float32Array(triangle), triangleCount: 1 }, position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], color: "#ff0000", visible: true }; }
function layer(objectId: string, plateId: number, id = `layer-${objectId}`): any { return { id, plateId, objectId, kind: "stroke", label: id, color: "#00ff00", materialKey: "ams:2", radiusMm: 1, points: [{ x: 0, y: 0, z: 0, screenX: .2, screenY: .3, normal: [0, 0, 1] }], mask: { kind: "rectangle", matrix: Array.from({ length: 16 }, (_, index) => index % 5 === 0 ? 1 : 0), left: 0, right: 1, top: 0, bottom: 1, runs: [0, 1] } }; }
function state(): any {
  const plates = [0, 1, 2].map((id) => ({ id, uid: `plate-uid-${id}`, name: `Druckplatte ${id + 1}`, width: 256, depth: 256, selection: { filament_profile_ids: [] }, instances: [item(`object-${id}`)], materialSource: "ams", externalFilamentProfileId: "", stage: "prepared", jobId: "", layers: [] }));
  const value: any = {
    plates, activePlate: 0, assignments: new Map(plates.map((plate) => [plate.instances[0].id, "ams:1"])),
    paintSession: createPaintSession(), paintLayers: new Map(plates.map((plate) => [plate.id, [layer(plate.instances[0].id, plate.id)]])), paintLegacyAmbiguousObjectIds: new Set(), nextPaintLayerId: 10,
    selected: new Set(), selectionAnchor: null, nextId: 10, modelMaterials: [], mode: "colors", status: "",
    plate() { return this.plates[this.activePlate]; },
    paintLayersForPlate(plate = this.plate()) { return this.paintLayers.get(plate.id) || []; },
    setPaintLayersForPlate(plate: any, entries: any[]) { if (entries.length) this.paintLayers.set(plate.id, entries); else this.paintLayers.delete(plate.id); },
    paintBaseRegionsForPlate(plate: any) { return plate.instances.flatMap((instance: any) => this.paintSession.getRegions(instance.id)); },
    paintRegionsForPlate(plate: any) { return this.paintBaseRegionsForPlate(plate); },
    paintRegions() { return this.paintRegionsForPlate(this.plate()); },
    paintRowsForSelection(plate: any) { return this.paintBaseRegionsForPlate(plate); },
    assertPaintEditable(objectId: string) { const conflict = paintEditConflict(objectId, this.paintLegacyAmbiguousObjectIds); if (conflict) throw new Error(conflict); },
    selectedItems() { return this.plate().instances.filter((entry: any) => this.selected.has(entry.id)); },
    audit() {}, closeMenus() {}, renderFull() {}, renderStatus() {}, invalidatePlate() {}, activatePlateJob() {}, schedulePersist() {},
    viewport: { setPaintRegions() {} },
  };
  for (const plate of plates) value.paintSession.paintTriangles(plate.instances[0].id, [0], { radiusMm: 1, color: "#ff0000", materialKey: "ams:1", mode: "add", label: `base-${plate.id}` });
  return value;
}

function plain<T>(value: T): T { return JSON.parse(JSON.stringify(value)); }
function snapshot(): PersistedStudioWorkspace {
  return method("workspaceSnapshot").call(state());
}

test("plate deletion retains paint on both surviving plates and remaps layer ownership", () => {
  const value = state(); value.activePlate = 1;
  method("removePlate").call(value);
  assert.deepEqual(value.plates.map((plate: any) => [plate.id, plate.instances[0].id]), [[0, "object-0"], [1, "object-2"]]);
  assert.equal(value.paintLayers.get(1)[0].objectId, "object-2");
  assert.equal(value.paintLayers.get(1)[0].plateId, 1);
  assert.equal(value.paintLayers.has(2), false);
  assert.equal(value.paintSession.getRegions("object-2")[0].label, "base-2");
  assert.equal(value.paintSession.getRegions("object-1").length, 0);
});

test("removing a layer cannot clear base paint or another plate", () => {
  const value = state(); value.selected.add("paint-layer:0");
  method("remove").call(value);
  assert.equal(value.paintLayersForPlate().length, 0);
  assert.equal(value.paintSession.getRegions("object-0")[0].label, "base-0");
  assert.equal(value.paintSession.getRegions("object-2")[0].label, "base-2");
});

test("removing a model cleans only its paint and leaves unrelated paint/layers intact", () => {
  const value = state(); value.selected.add("object-0");
  method("remove").call(value);
  assert.equal(value.paintSession.getRegions("object-0").length, 0);
  assert.equal(value.paintLayers.has(0), false);
  assert.equal(value.paintLayers.get(2)[0].objectId, "object-2");
  assert.equal(value.paintSession.getRegions("object-2").length, 1);
});

test("ambiguous legacy paint blocks only destructive individual edits without changing data", () => {
  const value = state(); value.selected.add("paint-layer:0"); value.paintLegacyAmbiguousObjectIds.add("object-0");
  const before = plain([...value.paintLayers]);
  method("remove").call(value);
  assert.deepEqual(plain([...value.paintLayers]), before);
  assert.equal(value.paintSession.getRegions("object-0").length, 1);
  assert.match(value.status, /Herkunftskennzeichnung/);
});

test("duplicating an object copies independent base paint, layers and legacy provenance", () => {
  const value = state(); value.selected.add("object-0"); value.paintLegacyAmbiguousObjectIds.add("object-0");
  method("duplicate").call(value);
  const copyId = [...value.selected][0];
  assert.equal(value.paintSession.getRegions(copyId)[0].label, "base-0");
  const copy = value.paintLayersForPlate().find((entry: any) => entry.objectId === copyId);
  assert.ok(copy); assert.notEqual(copy.id, "layer-object-0"); assert.ok(value.paintLegacyAmbiguousObjectIds.has(copyId));
  copy.points[0].x = 42; copy.mask.matrix[0] = 42;
  assert.equal(value.paintLayersForPlate()[0].points[0].x, 0); assert.equal(value.paintLayersForPlate()[0].mask.matrix[0], 1);
});

test("cut and paste between plates moves paint ownership and keeps clipboard paint independent", () => {
  const value = state(); value.selected.add("object-0");
  method("copySelection").call(value, "cut");
  value.paintLayersForPlate()[0].points[0].x = 99;
  value.activePlate = 2;
  method("pasteClipboard").call(value);
  const id = [...value.selected][0];
  assert.equal(value.paintSession.getRegions(id)[0].label, "base-0");
  assert.equal(value.paintSession.getRegions("object-0").length, 0);
  assert.equal(value.paintLayers.has(0), false);
  const moved = value.paintLayersForPlate().find((entry: any) => entry.objectId === id);
  assert.equal(moved.plateId, 2); assert.equal(moved.points[0].x, 0);
  assert.equal(value.paintSession.getRegions("object-1")[0].label, "base-1");
});

test("snapshot stores original base paint rather than a derived composed viewport", () => {
  const value = state();
  value.paintRegionsForPlate = () => [{ objectId: "derived", triangleIndices: [99], color: "#111111", materialKey: "ams:3" }];
  const saved = method("workspaceSnapshot").call(value);
  assert.equal(saved.paintCompositionVersion, 1);
  assert.deepEqual(saved.paintRegions.map((region: any) => region.objectId), ["object-0", "object-1", "object-2"]);
  saved.paintLayers[0][1][0].mask.matrix[0] = 99;
  assert.equal(value.paintLayersForPlate()[0].mask.matrix[0], 1);
});

test("legacy restore recovers stale plate indexes by unique object ownership without losing either source", () => {
  const saved = snapshot(); delete (saved as any).paintCompositionVersion;
  saved.plates.splice(0, 1); // historical removal left layer keys and saved plate IDs stale
  saved.paintRegions[1] = { ...saved.paintRegions[1], plateId: 90 };
  const restored = restoreStudioPaintState(saved);
  assert.equal(restored.layers.get(0)![0].objectId, "object-1");
  assert.equal(restored.layers.get(0)![0].plateId, 0);
  assert.equal(restored.regions.find((region) => region.objectId === "object-1")!.label, "base-1");
  assert.deepEqual([...restored.legacyAmbiguousObjectIds], ["object-1", "object-2"]);
});

test("versioned base plus layers remains editable across save/load; unknown/duplicate owners are rejected", () => {
  const saved = snapshot(); const restored = restoreStudioPaintState(saved);
  assert.equal(restored.legacyAmbiguousObjectIds.size, 0);
  assert.throws(() => restoreStudioPaintState({ ...saved, paintCompositionVersion: 2 } as any), /Version/);
  saved.plates[1].instances[0] = { ...saved.plates[0].instances[0] };
  assert.throws(() => restoreStudioPaintState(saved), /doppelte Kennungen/);
});

test("history owns geometry, mask, points and provenance and notices equal-length mesh changes", () => {
  const saved = snapshot();
  const production = productionModule("studio-workspace-history.ts", { "./studio-paint-state.js": { clonePaintLayer } });
  const history = new ModelStateHistory<PersistedStudioWorkspace>({ clone: production.cloneWorkspaceSnapshot, signature: production.workspaceHistorySignature });
  history.reset(saved);
  const changed = cloneWorkspaceSnapshot(saved);
  changed.plates[0].instances[0].positions[0] = 5;
  assert.equal(history.checkpoint(changed), true);
  changed.paintLayers[0][1][0].mask!.matrix[0] = 42;
  changed.plates[0].instances[0].positions[0] = 9;
  const undone = history.undo()!;
  assert.equal(undone.plates[0].instances[0].positions[0], 0);
  assert.equal(undone.paintLayers[0][1][0].mask!.matrix[0], 1);
  const redone = history.redo()!;
  assert.equal(redone.plates[0].instances[0].positions[0], 5);
  assert.equal(redone.paintLayers[0][1][0].mask!.matrix[0], 1);
});

test("history replay does not attach a shifted plate's job to a deleted plate", () => {
  const value = state();
  const saved = method("workspaceSnapshot").call(value);
  value.plates.splice(0, 1); value.plates.forEach((plate: any, index: number) => { plate.id = index; });
  value.plates[0].stage = "sliced"; value.plates[0].jobId = "job-survivor";
  const replayed = method("snapshotWithCurrentRuntime", { cloneWorkspaceSnapshot }).call(value, saved);
  assert.equal(replayed.plates[0].jobId, "");
  assert.equal(replayed.plates[1].jobId, "job-survivor");
});

test("blocked undo/redo never consumes history during a running slice", async () => {
  for (const name of ["undoWorkspace", "redoWorkspace"]) {
    const value = state(); value.plates[0].stage = "slicing";
    let consumed = 0;
    value.persistNow = async () => {};
    value.replayHistory = async () => {};
    value.history = { undo: () => { consumed++; return snapshot(); }, redo: () => { consumed++; return snapshot(); } };
    await method(name).call(value);
    assert.equal(consumed, 0);
    assert.match(value.status, /gesperrt/);
  }
});

test("production multi-selection treats model, paint layer and base region as separate ordered rows", () => {
  const value = state();
  value.paintSelectionId = (index: number) => `paint:${index}`;
  value.paintLayerSelectionId = (index: number) => `paint-layer:${index}`;
  value.orderedSelectionIds = method("orderedSelectionIds").bind(value);
  value.refreshSelectionUi = () => {};
  const select = method("select", { nextStudioSelection });
  select.call(value, "object-0", false);
  select.call(value, "paint:0", false, true);
  assert.deepEqual([...value.selected], ["object-0", "paint-layer:0", "paint:0"]);
  select.call(value, "paint-layer:0", true);
  assert.deepEqual([...value.selected], ["object-0", "paint:0"]);
});

test("mirrored geometry keeps object-local paint points, normals and captured masks aligned", () => {
  const original = layer("mesh", 0);
  original.points[0].x = 4; original.points[0].normal = [1, 0, 0];
  const mirrored = mirrorPaintLayer(original, "x");
  assert.equal(mirrored.points[0].x, -4);
  assert.deepEqual(mirrored.points[0].normal, [-1, 0, 0]);
  assert.equal(mirrored.mask.matrix[0], -1);
  assert.deepEqual(mirrorPaintLayer(mirrored, "x"), original);
  assert.equal(original.points[0].x, 4);
  const centered = mirrorPaintLayer(original, "x", 3);
  assert.equal(centered.points[0].x, 2);
  assert.equal(centered.mask.matrix[12], 6);
  assert.deepEqual(mirrorPaintLayer(centered, "x", 3), original);
});

test("production mirror follows the same non-zero geometry center for the paint and mesh", () => {
  const value = state(); value.selected.add("object-0");
  value.plate().instances[0] = { ...value.plate().instances[0], geometry: geometryFromPositions(new Float32Array([2, 0, 0, 4, 0, 0, 2, 1, 0])) };
  value.paintLayersForPlate()[0].points[0].x = 2;
  value.replace = (changes: Map<string, any>) => { value.plate().instances = value.plate().instances.map((entry: any) => changes.get(entry.id) || entry); };
  method("mirrorSelected", { mirrorMeshGeometry }).call(value, "x");
  assert.equal(value.plate().instances[0].geometry.positions[0], 4);
  assert.equal(value.paintLayersForPlate()[0].points[0].x, 4);
  assert.equal(value.paintLayersForPlate()[0].mask.matrix[12], 6);
});

test("keyboard select-all and delete respect editable focus and a pending native dialog", () => {
  class Input {} class Select {} class TextArea {} class Element { isContentEditable = false; }
  const value = state(); value.isConnected = true; value.getClientRects = () => [{}];
  value.orderedSelectionIds = () => ["object-0", "paint-layer:0", "paint:0"];
  value.refreshSelectionUi = () => {};
  let deletes = 0; value.remove = () => { deletes++; };
  const keyDown = method("keyDown", { nextStudioSelection, selectAllStudioObjects, HTMLInputElement: Input, HTMLSelectElement: Select, HTMLTextAreaElement: TextArea, HTMLElement: Element });
  const event = (key: string, path: unknown[] = [], ctrlKey = false) => ({ key, ctrlKey, metaKey: false, composedPath: () => path, preventDefault() {} });
  keyDown.call(value, event("a", [], true));
  assert.deepEqual([...value.selected], ["object-0", "paint-layer:0", "paint:0"]);
  keyDown.call(value, event("Delete", [new Input()]));
  keyDown.call(value, event("Delete", [new Select()]));
  keyDown.call(value, event("Delete", [new TextArea()]));
  const editable = new Element(); editable.isContentEditable = true;
  keyDown.call(value, event("Delete", [editable]));
  value.supportWarning = {};
  keyDown.call(value, event("Delete"));
  assert.equal(deletes, 0);
  value.supportWarning = null;
  keyDown.call(value, event("Delete"));
  assert.equal(deletes, 1);
});

test("production project API round-trip retains paint labels, masks and both legacy sources", async () => {
  const saved = snapshot();
  const production = productionModule("studio-project-api.ts", {
    "./studio-paint-state.js": { clonePaintLayer },
    "./ha-api-transport.js": { errorMessage: () => "failure", authenticatedFetch: async () => new Response(JSON.stringify({ data: { id: "project", name: "Saved", revision: 1, snapshot: saved } }), { status: 200 }) },
  });
  const restored = (await production.getStudioProject("project")).snapshot;
  assert.equal(restored.paintRegions[0].label, "base-0");
  assert.equal(restored.paintLayers[0][1][0].mask.matrix[0], 1);
  assert.ok(restored.plates[0].instances[0].positions instanceof Float32Array);
});

test("mesh repair preserves surviving face paint after removing an earlier invalid triangle", () => {
  const repair = productionModule("studio-mesh-repair.ts", { "./studio-mesh-tools.js": { geometryFromPositions } });
  const broken = geometryFromPositions(new Float32Array([0, 0, 0, 0, 0, 0, 0, 0, 0, ...triangle]));
  const value = state();
  value.plate().instances[0] = { ...value.plate().instances[0], geometry: broken };
  value.paintSession.clear("object-0");
  value.paintSession.paintTriangles("object-0", [1], { radiusMm: 1, color: "#00ff00", materialKey: "ams:2", label: "survivor", mode: "add" });
  value.replace = (changes: Map<string, any>) => { value.plate().instances = value.plate().instances.map((entry: any) => changes.get(entry.id) || entry); };
  const buttons = new Map<string, any>();
  const modal = { id: "", className: "", innerHTML: "", remove() {}, querySelector(selector: string) { if (!buttons.has(selector)) buttons.set(selector, { addEventListener(_event: string, handler: () => void) { this.click = handler; } }); return buttons.get(selector); } };
  value.root = { querySelector() { return null; }, append() {} };
  if (!process.env.CAD_SOURCE_ROOT) value.applyMeshRepairs = method("applyMeshRepairs", { repairMeshGeometry: repair.repairMeshGeometry }).bind(value);
  return method("confirmSafeMeshRepair", { document: { createElement: () => modal }, escapeHtml: (text: string) => text, repairMeshGeometry: repair.repairMeshGeometry }).call(value, [{ item: value.plate().instances[0], report: repair.analyzeMeshGeometry(broken) }]).then(() => {
    buttons.get("#mesh-repair-confirm").click();
    assert.deepEqual(plain(value.paintSession.getRegions("object-0")[0].triangleIndices), [0]);
    assert.equal(value.paintSession.getRegions("object-0")[0].label, "survivor");
    assert.equal(value.paintSession.getRegions("object-2")[0].label, "base-2");
  });
});

test("material conflicts on collapsed duplicate faces stop repair before any modification", () => {
  const repair = productionModule("studio-mesh-repair.ts", { "./studio-mesh-tools.js": { geometryFromPositions } });
  const mesh = geometryFromPositions(new Float32Array([...triangle, ...triangle]));
  const result = repair.repairMeshGeometry(mesh);
  assert.throws(() => remapObjectPaintRegions([
    { objectId: "mesh", triangleIndices: [0], color: "#ff0000", materialKey: "ams:1" },
    { objectId: "mesh", triangleIndices: [1], color: "#00ff00", materialKey: "ams:2" },
  ], "mesh", result.triangleIndexMap), /unterschiedliche Materialien/);
});

test("split maps every retained/clipped painted source face to its actual output indexes", () => {
  const split = productionModule("studio-mesh-split.ts", {
    "./studio-mesh-tools.js": { geometryFromPositions }, "./mesh-export.js": { transformPoint }, "./studio-mesh-cap.js": { generateCapFaces },
  });
  const negative = [-3, 0, 0, -2, 0, 0, -3, 1, 0], positive = [2, 0, 0, 3, 0, 0, 2, 1, 0];
  const source = { ...item("split-source"), geometry: geometryFromPositions(new Float32Array([...positive, ...negative])) };
  const preview = split.previewMeshPlaneSplit(source, "x", 0);
  assert.equal(preview.canApply, true);
  const original = [{ objectId: source.id, triangleIndices: [1], color: "#00ff00", materialKey: "ams:2", label: "negative" }];
  assert.deepEqual(plain(remapObjectPaintRegions(original, "negative", preview.negativeTriangleIndexMap)[0].triangleIndices), [0]);
  assert.deepEqual(remapObjectPaintRegions(original, "positive", preview.positiveTriangleIndexMap), []);
});

test("plate options and purge settings shift from staged originals, preserving unrelated keys", () => {
  const values = new Map<string, string>();
  const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value); }, removeItem: (key: string) => { values.delete(key); } };
  const old = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: storage });
  try {
    writePlateLocalSettings([0, 1, 2].map((id) => [id, { processOptions: `process-${id}`, purgeTower: `tower-${id}` }]));
    values.set("unrelated", "retain");
    reindexPlateLocalSettings([0, 1, 2], [0, 2]);
    assert.deepEqual(readPlateLocalSettings(1), { processOptions: "process-2", purgeTower: "tower-2" });
    assert.deepEqual(readPlateLocalSettings(2), { processOptions: null, purgeTower: null });
    assert.equal(values.get("unrelated"), "retain");
    let failed = false;
    storage.setItem = (key, value) => { if (!failed && value === "reject") { failed = true; throw new Error("quota"); } values.set(key, value); };
    assert.throws(() => writePlateLocalSettings([[0, { processOptions: "changed", purgeTower: "reject" }]]), /quota/);
    assert.deepEqual(readPlateLocalSettings(0), { processOptions: "process-0", purgeTower: "tower-0" });
  } finally { if (old) Object.defineProperty(globalThis, "localStorage", old); else delete (globalThis as any).localStorage; }
});

function archiveModel(bytes: ArrayBuffer): string {
  const view = new DataView(bytes);
  let offset = 0;
  while (view.getUint32(offset, true) === 0x04034b50) {
    const size = view.getUint32(offset + 18, true), nameLength = view.getUint16(offset + 26, true), extraLength = view.getUint16(offset + 28, true);
    const name = new TextDecoder().decode(new Uint8Array(bytes, offset + 30, nameLength));
    const dataOffset = offset + 30 + nameLength + extraLength;
    if (name === "3D/3dmodel.model") return inflateRawSync(new Uint8Array(bytes, dataOffset, size)).toString("utf8");
    offset = dataOffset + size;
  }
  throw new Error("3MF model entry missing");
}

test("selected-object production export preserves painted triangle materials in a real 3MF archive", async () => {
  const value = state(); value.selected.add("object-0");
  value.plate().instances[0].geometry = geometryFromPositions(triangle);
  value.paintLayers = new Map();
  value.paintSession.clear("object-0");
  value.paintSession.paintTriangles("object-0", [0], { radiusMm: 1, color: "#00ff00", materialKey: "ams:2", label: "painted face", mode: "add" });
  value.materialChoices = () => [{ key: "ams:1", name: "Red", color: "#ff0000" }, { key: "ams:2", name: "Green", color: "#00ff00" }];
  value.traceStudioOperation = () => {};
  value.root = { append() {} };
  let output: ArrayBuffer | undefined;
  const before = plain(method("workspaceSnapshot").call(value));
  class DownloadFile { size: number; name: string; constructor(parts: ArrayBuffer[], name: string) { this.size = parts[0].byteLength; this.name = name; } }
  await method("exportSelectedObjects", {
    export3mfStreamed: async (...args: Parameters<typeof export3mfStreamed>) => { output = await export3mfStreamed(...args); return output; },
    File: DownloadFile, URL: { createObjectURL: () => "blob:test", revokeObjectURL() {} }, setTimeout: () => 1,
    document: { createElement: () => ({ style: {}, click() {}, remove() {} }) },
  }).call(value);
  assert.ok(output, value.error || "export produced a ZIP");
  const xml = archiveModel(output);
  assert.match(xml, /displaycolor="#00FF00FF"/);
  assert.match(xml, /<triangle[^>]+p1="1"/);
  const after = plain(method("workspaceSnapshot").call(value)); before.savedAt = after.savedAt;
  assert.deepEqual(after, before, "download does not bake or mutate the editing session");
});

test("export refines a private geometry copy and validates original indices before refinement", () => {
  const source = { ...item("mesh"), geometry: geometryFromPositions(new Float32Array([0, 0, 0, 2, 0, 0, 0, 2, 0])) };
  const stroke = { ...layer("mesh", 0), mask: undefined, radiusMm: .8, points: [{ x: .5, y: .5, z: 0, screenX: .25, screenY: .25 }] };
  const base = [{ objectId: "mesh", triangleIndices: [0], color: "#ff0000", materialKey: "ams:1" }];
  const prepared = preparePaintedExport([source], base, [stroke], new Set());
  assert.ok(prepared.instances[0].geometry.triangleCount > 1);
  assert.equal(source.geometry.triangleCount, 1);
  assert.deepEqual(base[0].triangleIndices, [0]);
  assert.throws(() => preparePaintedExport([source], [{ ...base[0], triangleIndices: [2] }], [stroke], new Set()), /ursprüngliche/);
});

test("legacy selected export preserves the old raster without altering saved base or geometry", () => {
  const source = { ...item("mesh"), geometry: geometryFromPositions(triangle) };
  const stroke = { ...layer("mesh", 0), radiusMm: 2 };
  const base = [{ objectId: "mesh", triangleIndices: [0], color: "#ff0000", materialKey: "ams:1" }];
  const prepared = preparePaintedExport([source], base, [stroke], new Set(["mesh"]));
  assert.equal(prepared.instances[0].geometry, source.geometry);
  assert.equal(prepared.instances[0].geometry.triangleCount, 1);
  assert.equal(prepared.regions[0].materialKey, "ams:2");
  assert.equal(base[0].materialKey, "ams:1");
});

test("shared plate/file mesh contract rejects unknown faces and missing material channels", () => {
  const source = { ...item("mesh"), geometry: geometryFromPositions(triangle) };
  const region = { objectId: "mesh", triangleIndices: [0], color: "#00ff00", materialKey: "ams:2" };
  const objectMaterials = new Map([["mesh", 0]]), paintMaterials = new Map([["ams:2", 1]]);
  const meshes = buildPaintedExportMeshes([source], [region], objectMaterials, paintMaterials, 2);
  assert.deepEqual(meshes[0].triangleMaterialIndices, [1]);
  assert.throws(() => buildPaintedExportMeshes([source], [{ ...region, triangleIndices: [1] }], objectMaterials, paintMaterials, 2), /Dreiecksreferenz/);
  assert.throws(() => buildPaintedExportMeshes([source], [region], objectMaterials, new Map(), 2), /Exportmaterial/);
});

test("portable export preserves unassigned geometry while rejecting contradictory stored paint identities", () => {
  const source = { ...item("mesh"), geometry: geometryFromPositions(triangle) };
  const plan = localExportMaterialPlan([source], [], new Map(), []);
  assert.equal(plan.materials[0].color, "#ff0000");
  const region = { objectId: "mesh", triangleIndices: [0], color: "#00ff00", materialKey: "ams:2" };
  assert.throws(() => localExportMaterialPlan([source], [region, { ...region, color: "#0000ff" }], new Map(), []), /widersprüchliche Farben/);
  assert.throws(() => localExportMaterialPlan([source], [{ ...region, materialKey: "" }], new Map(), []), /Materialkennung/);
});
