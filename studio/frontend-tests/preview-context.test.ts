import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import * as ribbon from "../frontend/toolpath-ribbon-geometry.js";
import * as material from "../frontend/toolpath-material-colors.js";
import * as support from "../frontend/toolpath-support-filter.js";

// Actual production methods, geometry and cache; explicit DOM/network/GL doubles.
// These tests do not claim pixel, browser, device or live-deployment acceptance.
const root = process.env.PREVIEW_SOURCE_ROOT || process.cwd();
const file = join(root, "frontend/studio-mega-workspace-v2.ts");
const source = readFileSync(file, "utf8");
const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
const studio = ast.statements.find((node): node is ts.ClassDeclaration =>
  ts.isClassDeclaration(node) && node.name?.text === "Ultimate3DMegaStudioV2");
assert.ok(studio);
// Keep network loaders out of the lexical scope so injected fetch doubles bind.
const functions = ast.statements.filter((node): node is ts.FunctionDeclaration =>
  ts.isFunctionDeclaration(node) && !node.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.AsyncKeyword)
).map((node) => node.getText(ast)).join("\n");
const previewKeys = ["outer_wall", "inner_wall", "overhang_wall", "top_surface", "bottom_surface", "bridge", "ironing", "gap_infill", "solid_infill", "infill", "floating_shell", "support", "support_interface", "brim", "raft", "skirt", "purge_tower", "flush_waste", "custom", "other"];
const globals = {
  ...ribbon, ...material, ...support,
  NEUTRAL_COLOR: "#6b7785", COLORS: ["#ff4d4d", "#202020", "#36e51e", "#2e9bff"],
  PREVIEW_FEATURE_KEYS: previewKeys, Map, Set, WeakMap, Float32Array, Math, Number, String,
  Date, performance, console,
};

function evaluate(text: string, extra: Record<string, unknown> = {}) {
  const exports: any = {};
  const compiled = ts.transpileModule(text, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    transformers: { before: [(context) => {
      const visit: ts.Visitor = (node) => ts.isPrivateIdentifier(node)
        ? ts.factory.createIdentifier(node.text.slice(1)) : ts.visitEachChild(node, visit, context);
      return (node) => ts.visitNode(node, visit) as ts.SourceFile;
    }] },
  }).outputText;
  runInNewContext(compiled, { ...globals, exports, ...extra });
  return exports;
}

function method(name: string, extra: Record<string, unknown> = {}) {
  const member = studio!.members.find((node) => node.name?.getText(ast) === "#" + name);
  assert.ok(member, name);
  return evaluate(functions + `\nexports.Subject = class Subject { ${member.getText(ast)} };`, extra).Subject.prototype[name];
}

const display = method("displayInstances");
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));
const palette = ["#ff0000", "#0000ff"];
function layer(index: number): any {
  const z = (index + 1) * .25; // exact Float32 boundaries, no rounding-dependent assertions
  return { index, z, extrusion_mm: 2, features: ["Outer wall", "Sparse infill", "Support"], segments: [
    [0, 0, 10, 0, z, 0, .5, "Outer wall", "model"],
    [100, 0, 110, 0, z, 0, .5, "Sparse infill", "model"],
    [200, 0, 210, 0, z, 1, .5, "Support", "support"],
  ] };
}

function fixture() {
  const plate: any = { id: 0, uid: "plate-test", name: "test", jobId: "saved-job", layers: [0, 1, 2, 3].map(layer),
    layerCount: 4, visibleLayer: 0, toolColors: [...palette], instances: [] };
  const state: any = {
    plate: () => plate, mode: "preview", previewColorMode: "material", previewCumulative: true,
    previewSupportOnly: false, previewVisibleFeatures: new Set(previewKeys), purgeTowerData: () => ({ instances: [] }),
  };
  return { plate, state };
}

const ghosts = (instances: any[]) => instances.filter((instance) => instance.opacity !== undefined && instance.opacity < 1);
const opaque = (instances: any[]) => instances.filter((instance) => instance.opacity === undefined || instance.opacity === 1);
const geometries = (instances: any[]) => new Map(ghosts(instances).map((instance) => [instance.id, instance.geometry]));
function assertStable(before: Map<string, unknown>, after: any[]) {
  const actual = geometries(after);
  assert.deepEqual([...actual.keys()], [...before.keys()]);
  for (const [id, geometry] of before) assert.equal(actual.get(id), geometry, id);
}

for (const [label, selected] of [["first", 0], ["middle", 2], ["last", 3]] as const) {
  test(`${label} layer keeps the exact active cutoff and complete future context`, () => {
    const { plate, state } = fixture();
    plate.visibleLayer = selected;
    const instances = display.call(state);
    const context = ghosts(instances);
    assert.ok(context.length, "production preview must carry full-height context geometry");
    assert.ok(context.every((instance: any) => instance.opacity === .16 && instance.clipMinZ === plate.layers[selected].z));
    assert.equal(Math.max(...context.map((instance: any) => instance.geometry.boundsMax[2])), 1);
    assert.ok(opaque(instances).every((instance: any) => instance.geometry.boundsMax[2] <= plate.layers[selected].z + .002));
    const visible = context.filter((instance: any) => instance.visible);
    if (selected === 3) assert.equal(visible.length, 0, "last layer keeps only invisible context references");
    else assert.equal(Math.max(...visible.map((instance: any) => instance.geometry.boundsMax[2])), 1);
  });
}

test("single-layer mode keeps transparent future height without opaque history", () => {
  const { plate, state } = fixture();
  plate.visibleLayer = 2;
  state.previewCumulative = false;
  const instances = display.call(state);
  assert.ok(ghosts(instances).some((instance: any) => instance.visible && instance.geometry.boundsMax[2] === 1));
  assert.ok(opaque(instances).length);
  assert.ok(opaque(instances).every((instance: any) => instance.id.includes("-current-")));
});

test("moving first to middle to last reuses ghost geometry and typed arrays", () => {
  const { plate, state } = fixture();
  const first = display.call(state);
  const before = geometries(first);
  assert.ok(before.size);
  for (const selected of [2, 3, 0]) {
    plate.visibleLayer = selected;
    const next = display.call(state);
    assertStable(before, next);
    for (const instance of ghosts(next)) {
      const original: any = before.get(instance.id);
      assert.equal(instance.geometry.positions, original.positions);
      assert.equal(instance.geometry.normals, original.normals);
    }
  }
});

test("job-bound palette and source toolpaths stay unchanged and current AMS is never queried", () => {
  const { plate, state } = fixture();
  const before = plain(plate.layers);
  const paletteReference = plate.toolColors;
  let amsCalls = 0;
  state.materialChoices = () => { amsCalls++; return [{ color: "#00ff00" }]; };
  const instances = display.call(state);
  assert.equal(amsCalls, 0);
  assert.equal(plate.toolColors, paletteReference);
  assert.deepEqual(plate.toolColors, palette);
  assert.deepEqual(plain(plate.layers), before);
  assert.deepEqual([...new Set(ghosts(instances).map((instance: any) => instance.color))].sort(), [...palette].sort());
});

test("a different job invalidates cached ghost geometry even for the same layers reference", () => {
  const { plate, state } = fixture();
  const before = geometries(display.call(state));
  assert.ok(before.size);
  plate.jobId = "different-job";
  const after = geometries(display.call(state));
  assert.equal(after.size, before.size);
  for (const [id, geometry] of before) assert.notEqual(after.get(id), geometry);
});

test("palette changes invalidate ghost styles without mutating the old palette", () => {
  const { plate, state } = fixture();
  const oldPalette = plate.toolColors;
  const before = geometries(display.call(state));
  plate.toolColors = ["#00ff00", "#ff00ff"];
  const after = ghosts(display.call(state));
  assert.ok(after.length);
  assert.deepEqual([...new Set(after.map((instance: any) => instance.color))].sort(), [...plate.toolColors].sort());
  assert.deepEqual(oldPalette, palette);
  assert.ok(after.every((instance: any) => ![...before.values()].includes(instance.geometry)));
});

test("feature filters affect opaque paths and context and invalidate their cached geometry", () => {
  const { state } = fixture();
  const before = geometries(display.call(state));
  state.previewVisibleFeatures.clear();
  state.previewVisibleFeatures.add("outer_wall");
  const instances = display.call(state);
  assert.ok(ghosts(instances).length);
  assert.ok(instances.every((instance: any) => instance.geometry.boundsMax[0] < 20));
  assert.ok(ghosts(instances).every((instance: any) => ![...before.values()].includes(instance.geometry)));
});

test("a replaced layers array gets a new context cache even when its elements are unchanged", () => {
  const { plate, state } = fixture();
  const before = geometries(display.call(state));
  assert.ok(before.size);
  plate.layers = [...plate.layers];
  const after = geometries(display.call(state));
  assert.equal(after.size, before.size);
  for (const [id, geometry] of before) assert.notEqual(after.get(id), geometry);
});

test("an empty feature filter hides both active and future paths", () => {
  const { state } = fixture();
  state.previewVisibleFeatures.clear();
  assert.equal(display.call(state).length, 0);
});

test("support isolation removes model paths from future context too", () => {
  const { state } = fixture();
  state.previewSupportOnly = true;
  const instances = display.call(state);
  assert.ok(ghosts(instances).length);
  assert.ok(instances.every((instance: any) => instance.geometry.boundsMin[0] > 190));
});

test("prepare mode returns original model geometry without toolpath ghosts", () => {
  const { plate, state } = fixture();
  const item = { id: "model-test", geometry: { positions: new Float32Array(9) } };
  plate.instances = [item];
  state.mode = "prepare";
  const instances = display.call(state);
  assert.equal(instances.length, 1);
  assert.equal(instances[0], item);
  assert.equal(ghosts(instances).length, 0);
});

function contextBuilder(): (...args: any[]) => any[] {
  // Optional lookup keeps the old baseline loadable: absence produces a clear
  // assertion, while actual display-height regressions still execute separately.
  const result = (ribbon as unknown as Record<string, unknown>)["buildToolpathContextMeshes"];
  assert.equal(typeof result, "function", "production context builder is missing");
  return result as (...args: any[]) => any[];
}

test("context builder keeps all accepted extrusion layers at their full heights", () => {
  const layers = [0, 1, 2, 3].map(layer);
  const before = plain(layers);
  const heights = new Map(layers.map((value) => [value.index, .25]));
  const result = contextBuilder()(layers, heights, () => ({ key: "test", color: "#aabbcc", label: "test", flat: false }), "job-test");
  assert.ok(result.length);
  assert.equal(Math.max(...result.map((instance: any) => instance.geometry.boundsMax[2])), 1);
  assert.ok(result.every((instance: any) => instance.opacity === .16));
  assert.ok(result.every((instance: any) => !instance.id.includes(":highlight")));
  assert.deepEqual(plain(layers), before);
});

test("context builder cache uses layers identity and cache key", () => {
  const layers = [0, 1, 2, 3].map(layer);
  const heights = new Map(layers.map((value) => [value.index, .25]));
  const style = () => ({ key: "test", color: "#aabbcc", label: "test", flat: false });
  const builder = contextBuilder();
  const first = builder(layers, heights, style, "job-test");
  const same = builder(layers, heights, style, "job-test");
  assert.ok(first.length);
  assert.equal(same[0].geometry, first[0].geometry);
  const changed = builder(layers, heights, style, "other-job");
  assert.notEqual(changed[0].geometry, first[0].geometry);
});

function viewportMethods() {
  const path = join(root, "frontend/studio-mega-viewport.ts");
  const viewportSource = readFileSync(path, "utf8");
  const viewportAst = ts.createSourceFile(path, viewportSource, ts.ScriptTarget.Latest, true);
  const viewport = viewportAst.statements.find((node): node is ts.ClassDeclaration =>
    ts.isClassDeclaration(node) && node.name?.text === "StudioMegaViewport");
  assert.ok(viewport);
  const selected = new Set(["setInstances", "#ensureGpu", "dispose"]);
  const methods = viewport.members.filter((node) => selected.has(node.name?.getText(viewportAst) || ""));
  assert.equal(methods.length, selected.size);
  return evaluate(`exports.Subject = class Subject { ${methods.map((node) => node.getText(viewportAst)).join("\n")} };`, {
    cancelAnimationFrame() {},
  }).Subject.prototype;
}

test("viewport retains context GPU buffers for clip/visibility changes and releases them on removal", () => {
  const { plate, state } = fixture();
  const context = ghosts(display.call(state));
  assert.ok(context.length);
  let created = 0, uploads = 0, deleted = 0;
  const prototype = viewportMethods();
  const viewport: any = {
    gl: { ARRAY_BUFFER: 1, STATIC_DRAW: 2,
      createBuffer: () => ({ id: ++created }), bindBuffer() {}, bufferData: () => { uploads++; }, deleteBuffer: () => { deleted++; } },
    gpu: new Map(), instances: [], ensureGpu: prototype.ensureGpu,
    rebuildOverlays() {}, resize() {}, requestRender() {}, resizeObserver: { disconnect() {} },
    clearFlat() {}, plateMeshes: [], overlayMeshes: [], raf: 0,
  };
  prototype.setInstances.call(viewport, context);
  assert.equal(uploads, context.length * 2);
  plate.visibleLayer = 3;
  const last = ghosts(display.call(state));
  assert.ok(last.every((instance: any) => !instance.visible));
  prototype.setInstances.call(viewport, last);
  assert.equal(uploads, context.length * 2, "layer clipping must not upload unchanged geometry again");
  assert.equal(deleted, 0);
  prototype.setInstances.call(viewport, []);
  assert.equal(deleted, context.length * 2);
  assert.equal(viewport.gpu.size, 0);
  prototype.dispose.call(viewport);
  assert.equal(deleted, context.length * 2);
});

test("layer-only viewport refresh keeps the current camera frame", () => {
  const { state } = fixture();
  let frames = 0, updates = 0;
  state.displayInstances = () => display.call(state);
  state.viewport = { setInstances() { updates++; }, frameAll() { frames++; }, resize() {}, requestRender() {} };
  method("refreshPreviewViewport", { requestAnimationFrame: (callback: () => void) => { callback(); return 1; } }).call(state);
  assert.equal(updates, 1);
  assert.equal(frames, 0);
});

test("diagnostic color mode changes invalidate the cached context style", () => {
  const { state } = fixture();
  const before = geometries(display.call(state));
  state.previewColorMode = "feature";
  const after = ghosts(display.call(state));
  assert.ok(after.length);
  assert.ok(after.every((instance: any) => ![...before.values()].includes(instance.geometry)));
});

test("support-only changes invalidate context even with the same visible feature set", () => {
  const { state } = fixture();
  const before = geometries(display.call(state));
  state.previewSupportOnly = true;
  const after = ghosts(display.call(state));
  assert.ok(after.length);
  assert.ok(after.every((instance: any) => ![...before.values()].includes(instance.geometry)));
});

test("equivalent feature sets reuse context regardless of insertion order", () => {
  const { state } = fixture();
  const before = geometries(display.call(state));
  assert.ok(before.size);
  state.previewVisibleFeatures = new Set([...previewKeys].reverse());
  assertStable(before, display.call(state));
});

function reconcileState(plate: any) {
  return { plate: () => plate, reconcilingJobs: new Set<string>(), sliceTraceByJob: new Map<string, string>(),
    previewColorMode: "material", traceSliceActivity() {}, audit() {}, renderStatus() {}, renderAfterSliceReconcile() {},
    async persistNow() {} };
}

function replaceJob(plate: any) {
  const layers = [layer(0)], colors = ["#00aa00"];
  Object.assign(plate, { jobId: "new-job", stage: "prepared", lastError: "", layers, toolColors: colors,
    layerCount: 1, visibleLayer: 0 });
  return { layers, colors };
}

function reconciler(extra: Record<string, unknown>) {
  return method("activatePlateJob", {
    ACTIVE: new Set(["running", "queued"]), previewFeatureLabel: (value: string) => value,
    previewFeatureKey: () => "other", jobActivityStore: { registerSlicerJob() {} }, ...extra,
  });
}

test("replaced jobs cannot publish an old summary after awaiting toolpath metadata", async () => {
  const plate: any = { id: 0, name: "test", jobId: "old-job", layers: [], layerCount: 0, toolColors: [] };
  const state = reconcileState(plate);
  let replacement: ReturnType<typeof replaceJob> | undefined, chunkCalls = 0;
  await reconciler({
    fetchSliceJob: async () => ({ id: "old-job", status: "succeeded" }),
    fetchToolpath: async (_id: string, start?: number) => {
      if (start !== undefined) { chunkCalls++; return { chunk: { layers: [layer(0)], segment_count: 1 } }; }
      replacement = replaceJob(plate);
      return { layer_count: 3, filament_colors: ["#ff0000"], layers: [] };
    },
  }).call(state, plate);
  assert.ok(replacement);
  assert.equal(plate.jobId, "new-job");
  assert.equal(plate.toolColors, replacement.colors);
  assert.equal(plate.layers, replacement.layers);
  assert.equal(plate.layerCount, 1);
  assert.equal(plate.visibleLayer, 0);
  assert.equal(plate.stage, "prepared");
  assert.equal(chunkCalls, 0);
});

test("replaced jobs cannot publish the last awaited old toolpath chunk", async () => {
  const plate: any = { id: 0, name: "test", jobId: "old-job", layers: [], layerCount: 0, toolColors: [] };
  const state = reconcileState(plate);
  let replacement: ReturnType<typeof replaceJob> | undefined;
  const oldLayer = layer(0);
  await reconciler({
    fetchSliceJob: async () => ({ id: "old-job", status: "succeeded" }),
    fetchToolpath: async (_id: string, start?: number) => {
      if (start === undefined) return { layer_count: 1, filament_colors: ["#ff0000"], layers: [] };
      replacement = replaceJob(plate);
      return { chunk: { layers: [oldLayer], segment_count: 1 } };
    },
  }).call(state, plate);
  assert.ok(replacement);
  assert.equal(plate.jobId, "new-job");
  assert.equal(plate.toolColors, replacement.colors);
  assert.equal(plate.layers, replacement.layers);
  assert.notEqual(plate.layers[0], oldLayer);
  assert.equal(plate.layerCount, 1);
  assert.equal(plate.stage, "prepared");
});
