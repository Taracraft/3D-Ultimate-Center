import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { arrangePlateInstances } from "../frontend/studio-arrangement.js";
import { transformedBounds } from "../frontend/mesh-export.js";
import { studioBuildPlateVisual, buildPlateProfiles } from "../frontend/studio-build-plates.js";
import { buildPlateProfileFromCatalog, profileById } from "../frontend/studio-profile-catalog.js";
import type { MeshInstance, Vec3 } from "../frontend/webgl-studio-viewport.js";

// Isolated source-flow tests. UI/WebGL, provider, HTTP and hardware boundaries
// are explicit doubles; no browser, printer, engine or actual slice is started.
const root = process.env.CAD_SOURCE_ROOT || process.cwd();
const workspace = "frontend/studio-mega-workspace-v2.ts";
const common = { Map, Set, Float32Array, Date, Math, Number, String, Error, JSON,
  URLSearchParams, Response, File, Headers, CustomEvent, console };
const plain = <T>(value: T): T => JSON.parse(JSON.stringify(value));
function source(file: string): ts.SourceFile {
  return ts.createSourceFile(file, readFileSync(join(root, file), "utf8"), ts.ScriptTarget.Latest, true);
}
function productionMethod(file: string, name: string, dependencies: Record<string, unknown> = {}): (...args: any[]) => any {
  const ast = source(file);
  const classes = ast.statements.filter(ts.isClassDeclaration);
  const owners = classes.filter(cls => cls.members.some(member => member.name?.getText(ast) === `#${name}`));
  assert.equal(owners.length, 1, `unique source method ${name}`);
  const member = owners[0]!.members.find(node => node.name?.getText(ast) === `#${name}`)!;
  const code = ts.transpileModule(`exports.Subject = class { ${member.getText(ast)} };`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    transformers: { before: [context => {
      const visit: ts.Visitor = node => ts.isPrivateIdentifier(node)
        ? ts.factory.createIdentifier(node.text.slice(1)) : ts.visitEachChild(node, visit, context);
      return file => ts.visitNode(file, visit) as ts.SourceFile;
    }] },
  }).outputText;
  const exports: any = {};
  runInNewContext(code, { exports, ...common, ...dependencies });
  if (typeof exports.Subject.prototype[name] === "function") return exports.Subject.prototype[name];
  return function (this: any, ...args: any[]) {
    const subject = Object.assign(new exports.Subject(), this);
    const result = subject[name](...args);
    for (const key of Object.keys(subject)) if (key !== name) this[key] = subject[key];
    return result;
  };
}
function productionFunctions(file: string, names: string[], dependencies: Record<string, unknown> = {}): any {
  const ast = source(file);
  const declarations = names.map(name => {
    const node = ast.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === name);
    assert.ok(node, `source function ${name}`);
    return node.getText(ast).replace(/^export\s+/, "");
  });
  const code = ts.transpileModule(declarations.join("\n") + names.map(name => `\nexports.${name}=${name};`).join(""), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const exports: any = {};
  runInNewContext(code, { exports, ...common, ...dependencies });
  return exports;
}
function productionModule(file: string, dependencies: Record<string, unknown>, globals: Record<string, unknown> = {}): any {
  const code = ts.transpileModule(readFileSync(join(root, file), "utf8"), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const exports: any = {};
  runInNewContext(code, { exports, ...common, ...globals, require: (name: string) => {
    assert.ok(Object.hasOwn(dependencies, name), `explicit dependency ${name}`); return dependencies[name];
  } });
  return exports;
}
function item(id: string, size: Vec3 = [20, 20, 20]): MeshInstance {
  return { id, name: id, geometry: { boundsMin: [0, 0, 0], boundsMax: size,
    positions: new Float32Array([0, 0, 0, ...size, 0, size[1], size[2]]), normals: new Float32Array(9), triangleCount: 1 },
    position: [70, 80, 10], rotation: [0, 0, 0], scale: [1, 1, 1], color: "#112233", visible: true };
}
function verifyLayout(items: readonly MeshInstance[], width: number, depth: number, margin = 12, gap = 8): void {
  const boxes = items.map(entry => transformedBounds(entry.geometry, entry));
  for (let i = 0; i < boxes.length; i++) {
    const a = boxes[i]!;
    assert.ok(a.min[0] >= margin - 1e-6 && a.min[1] >= margin - 1e-6);
    assert.ok(a.max[0] <= width - margin + 1e-6 && a.max[1] <= depth - margin + 1e-6);
    assert.ok(Math.abs(a.min[2]) < 1e-6);
    for (let j = 0; j < i; j++) {
      const b = boxes[j]!;
      assert.ok(a.max[0] + gap <= b.min[0] + 1e-6 || b.max[0] + gap <= a.min[0] + 1e-6
        || a.max[1] + gap <= b.min[1] + 1e-6 || b.max[1] + gap <= a.min[1] + 1e-6);
    }
  }
}
const arrange = productionMethod(workspace, "arrange", { arrangePlateInstances });
function arrangementState(items: MeshInstance[]): any {
  const plate = { id: 0, width: 256, depth: 256, instances: items, jobId: "retained", stage: "sliced" };
  return { plate: () => plate, status: "", invalidated: 0, renderCount: 0, audit() {},
    renderStatus() {}, renderFull() { this.renderCount++; }, invalidatePlate() { this.invalidated++; } };
}

test("arrangement preserves scale rotation reflection geometry and material identity", () => {
  const a = { ...item("a"), scale: [-2, .5, 1.25] as Vec3, rotation: [10, 20, 30] as Vec3 };
  const b = { ...item("b"), visible: false };
  const inputs = [a, b], before = plain(inputs);
  const result = arrangePlateInstances(inputs, 256, 256);
  assert.ok(result.ok); verifyLayout(result.instances, 256, 256);
  assert.deepEqual(plain(inputs), before);
  result.instances.forEach((entry, i) => {
    assert.equal(entry.id, inputs[i]!.id); assert.equal(entry.name, inputs[i]!.name);
    assert.equal(entry.geometry, inputs[i]!.geometry); assert.equal(entry.rotation, inputs[i]!.rotation);
    assert.equal(entry.scale, inputs[i]!.scale); assert.equal(entry.color, inputs[i]!.color);
    assert.equal(entry.visible, inputs[i]!.visible); assert.notEqual(entry.position, inputs[i]!.position);
  });
});
test("arrangement places rotated non-centred geometry inside the physical plate", () => {
  const a = { ...item("a", [200, 20, 10]), rotation: [0, 0, 90] as Vec3 };
  const value = arrangementState([a]); arrange.call(value);
  verifyLayout(value.plate().instances, 256, 256);
  assert.equal(value.invalidated, 1); assert.equal(value.plate().instances[0].scale, a.scale);
});
test("arrangement rejects oversized or unplaceable groups atomically without shrinking", () => {
  for (const entries of [[item("a", [300, 20, 10])], [item("a", [230, 230, 10]), item("b", [230, 230, 10])]]) {
    const value = arrangementState(entries), before = plain(entries);
    arrange.call(value);
    assert.equal(value.plate().instances, entries); assert.equal(value.invalidated, 0);
    assert.equal(value.plate().jobId, "retained"); assert.deepEqual(plain(entries), before);
    assert.match(value.status, /Platz/);
  }
});
test("arrangement handles mixed rectangle sizes that do not fit equal grid cells", () => {
  const inputs = [item("large", [150, 150, 30]), ...Array.from({ length: 6 }, (_, i) => item(`small-${i}`, [25, 25, 8]))];
  const result = arrangePlateInstances(inputs, 256, 256);
  assert.ok(result.ok); verifyLayout(result.instances, 256, 256);
});
test("arrangement supports exact margins and explicit zero gap", () => {
  const inputs = [item("left", [116, 232, 1]), item("right", [116, 232, 1])];
  const result = arrangePlateInstances(inputs, 256, 256, { gapMm: 0 });
  assert.ok(result.ok); verifyLayout(result.instances, 256, 256, 12, 0);
});
test("arrangement is deterministic preserves input order and is idempotent", () => {
  const input = [item("z", [40, 15, 4]), item("b", [65, 30, 5]), item("a", [10, 10, 8])];
  const first = arrangePlateInstances(input, 256, 256), second = arrangePlateInstances(input, 256, 256);
  assert.ok(first.ok && second.ok); assert.deepEqual(first, second);
  assert.deepEqual(first.instances.map(entry => entry.id), ["z", "b", "a"]);
  const repeated = arrangePlateInstances(first.instances, 256, 256);
  assert.ok(repeated.ok); assert.equal(repeated.movedCount, 0);
});
test("arrangement leaves empty scenes and already arranged jobs unchanged", () => {
  assert.deepEqual(arrangePlateInstances([], 256, 256), { ok: true, instances: [], movedCount: 0 });
  const first = arrangePlateInstances([item("a")], 256, 256); assert.ok(first.ok);
  const value = arrangementState(first.instances); arrange.call(value);
  assert.equal(value.invalidated, 0); assert.equal(value.plate().instances, first.instances);
});
test("arrangement rejects invalid plate geometry and invalid object transforms", () => {
  for (const width of [NaN, Infinity, 0, -1, 24]) assert.deepEqual(arrangePlateInstances([item("a")], width, 256), { ok: false, reason: "invalid_plate" });
  for (const options of [{ marginMm: -1 }, { gapMm: -1 }, { gapMm: Infinity }]) assert.equal(arrangePlateInstances([item("a")], 256, 256, options).ok, false);
  for (const bad of [{ ...item("a"), scale: [0, 1, 1] as Vec3 }, { ...item("a"), rotation: [NaN, 0, 0] as Vec3 },
    { ...item("a"), position: [0, Infinity, 0] as Vec3 }, { ...item("a"), geometry: { ...item("a").geometry, triangleCount: 0 } }]) {
    assert.deepEqual(arrangePlateInstances([bad], 256, 256), { ok: false, reason: "invalid_object" });
  }
  assert.deepEqual(arrangePlateInstances([item("same"), item("same")], 256, 256), { ok: false, reason: "invalid_object" });
});
test("arrangement complexity limit rejects before modifying large scenes", () => {
  const input = Array.from({ length: 2049 }, (_, i) => item(`id-${i}`));
  assert.deepEqual(arrangePlateInstances(input, 256, 256), { ok: false, reason: "complexity_limit" });
  assert.deepEqual(input[0]!.position, [70, 80, 10]);
});
test("arrangement seeded varied footprints remain separated within both rectangular axes", () => {
  let state = 8123;
  const random = () => { state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 2 ** 32; };
  for (let batch = 0; batch < 30; batch++) {
    const input = Array.from({ length: 16 }, (_, i) => ({ ...item(`${batch}-${i}`, [5 + random() * 15, 5 + random() * 15, 1 + random() * 5]),
      rotation: [0, 0, random() * 180] as Vec3, scale: [random() > .5 ? -1 : 1, .5 + random(), 1] as Vec3 }));
    const result = arrangePlateInstances(input, 320, 200); assert.ok(result.ok); verifyLayout(result.instances, 320, 200);
  }
});

const { newPlate } = productionFunctions(workspace, ["newPlateUid", "newPlate"]);
function selection(): any { return { target_printer_id: "printer", printer_profile_id: "a1", nozzle_profile_id: "04", process_profile_id: "020", build_plate_profile_id: "textured", filament_profile_ids: ["pla"], gcode_preset_ids: { start_sound: "original", gcode_1: "machine" } }; }
test("new plates own independent nested preset selections material lists and runtime arrays", () => {
  const original = selection(), a = newPlate(0, "one", original), b = newPlate(1, "two", a.selection);
  b.selection.filament_profile_ids.push("other"); b.selection.gcode_preset_ids.start_sound = "changed";
  b.instances.push(item("new")); b.layers.push({ z: .2 }); b.toolColors.push("#ff0000");
  assert.deepEqual(plain(a.selection), original); assert.equal(original.gcode_preset_ids.start_sound, "original");
  assert.equal(a.instances.length, 0); assert.equal(a.layers.length, 0); assert.equal(a.toolColors.length, 0);
  assert.notEqual(a.uid, b.uid); assert.equal(b.stage, "prepared"); assert.equal(b.jobId, "");
});
test("new plate inherits dimensions and material source without mutating the old plate", () => {
  const original = newPlate(0, "one", selection(), 235, 240, "external_spool", "external-pla");
  original.instances.push(item("old")); original.stage = "sliced"; original.jobId = "old-job";
  const previous = plain(original);
  const value: any = { plates: [original], activePlate: 0, selected: new Set(["old"]), status: "", audit() {}, closeMenus() {}, renderFull() {},
    activated: [], plate() { return this.plates[this.activePlate]; }, activatePlateJob(plate: any) { this.activated.push(plate.uid); } };
  productionMethod(workspace, "addPlate", { newPlate }).call(value);
  assert.equal(value.plates.length, 2); assert.equal(value.activePlate, 1); assert.equal(value.selected.size, 0);
  assert.deepEqual(plain(original), previous); assert.equal(value.plate().width, 235); assert.equal(value.plate().depth, 240);
  assert.equal(value.plate().materialSource, "external_spool"); assert.equal(value.plate().externalFilamentProfileId, "external-pla");
  assert.deepEqual(value.activated, [value.plate().uid]); assert.equal(value.plate().jobId, "");
});

for (const surface of ["cool", "engineering", "high_temp", "smooth", "textured", "smooth_cool", "textured_cool", "supertack", "custom"]) {
  test(`plate visual prioritizes explicit ${surface} over a conflicting display name`, () => {
    const profile: any = { id: "my-plate", kind: "build_plate", name: "Bambu Textured Cool Plate", payload: { surface, width_mm: 235, depth_mm: 240 } };
    const before = plain(profile), result = studioBuildPlateVisual(profile);
    assert.equal(result.surface, surface); assert.equal(result.widthMm, 235); assert.equal(result.depthMm, 240);
    assert.deepEqual(profile, before);
  });
}
test("plate visuals retain legacy name inference dimension aliases and local profile precedence", () => {
  const p: any = { id: "build-plate-textured-pei", kind: "build_plate", name: "Bambu Textured PEI Plate", payload: { bed_width: [220], y_size: "230" } };
  assert.equal(studioBuildPlateVisual(p).surface, "textured");
  assert.equal(studioBuildPlateVisual(p).widthMm, 220); assert.equal(studioBuildPlateVisual(p).depthMm, 230);
  assert.equal(buildPlateProfiles([p]).filter(entry => entry.id === p.id).length, 1);
  assert.equal(buildPlateProfiles([p]).find(entry => entry.id === p.id), p);
});
test("selected plate profile changes physical bounds without moving model transforms", () => {
  const profile: any = { id: "plate", kind: "build_plate", name: "Local", payload: { surface: "high_temp", width_mm: 230, depth_mm: 240 } };
  const plate: any = { width: 256, depth: 256, selection: { build_plate_profile_id: "plate" }, instances: [item("existing")] };
  const before = plain(plate.instances);
  const value: any = { catalog: { profiles: [profile] }, invalidated: 0, invalidatePlate() { this.invalidated++; } };
  const apply = productionMethod(workspace, "applyBuildPlateProfile", { profileById, buildPlateProfileFromCatalog });
  apply.call(value, plate); assert.equal(plate.width, 230); assert.equal(plate.depth, 240);
  assert.deepEqual(plain(plate.instances), before); assert.equal(value.invalidated, 1);
  apply.call(value, plate, false); assert.equal(value.invalidated, 1);
  plate.selection.build_plate_profile_id = "missing"; apply.call(value, plate); assert.equal(value.invalidated, 1);
});

function localStorageDouble(): any {
  const data = new Map<string, string>();
  return { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => { data.set(key, value); }, removeItem: (key: string) => data.delete(key) };
}
function plateApi(storage: any, requests: any[], events: any[]): any {
  return productionModule("frontend/plate-slice-api.ts", {
    "./direct-print-panel.js": {},
    "./process-profile-editor-model.js": { PROCESS_EDITOR_FIELDS: [], processFieldBounds: () => ({ min: 0 }) },
    "./ha-api-transport.js": { authenticatedFetch: () => { throw Error("not part of this case"); }, errorMessage: (_: unknown, fallback: string) => fallback,
      authenticatedUpload: async (url: string, options: any) => { requests.push({ url, options }); return new Response(JSON.stringify({ data: { id: "synthetic-held", status: "queued" } }), { status: 200 }); } },
    "./profile-api.js": { ProfileApi: class { async saveSelection(value: unknown) { requests.push({ profiles: plain(value) }); } } },
    "./purge-tower-state.js": { mergePlatePurgeTower: (value: unknown) => value },
    "./nozzle-process-contract.js": {},
  }, { localStorage: storage, window: { dispatchEvent: (event: CustomEvent) => { events.push(event); } } });
}
for (const mode of ["none", "brim", "raft"]) {
  test(`adhesion ${mode} retains explicit settings in a mock-only job request`, async () => {
    const requests: any[] = [], events: any[] = [], storage = localStorageDouble(), api = plateApi(storage, requests, events);
    const overrides = { ...api.DEFAULT_SLICE_PROCESS_OVERRIDES, adhesion_mode: mode, brim_width_mm: 9, raft_layers: 4 };
    const file = new File(["synthetic-not-a-real-model"], "fixture.3mf");
    const context = { studio_plate_id: 2, studio_plate_display_number: 3, studio_plate_name: "Third", build_plate_profile_id: "explicit-plate" };
    const result = await api.createPlateSliceJob(file, 0, overrides, undefined, context);
    assert.equal(result.id, "synthetic-held"); assert.equal(requests.length, 2);
    assert.equal(requests[0].profiles.build_plate_profile_id, "explicit-plate");
    const request = requests[1], query = new URL(request.url, "https://example.invalid").searchParams;
    assert.equal(query.get("adhesion_mode"), mode); assert.equal(query.get("brim_width_mm"), mode === "brim" ? "9" : null);
    assert.equal(query.get("raft_layers"), mode === "raft" ? "4" : null); assert.equal(request.options.body, file);
    assert.equal(JSON.parse(decodeURIComponent(request.options.headers["X-U3D-Studio-Plate"])).studio_plate_id, 2);
    assert.equal(events.length, 1); assert.equal(events[0].detail.jobId, "synthetic-held");
  });
}
test("per-plate adhesion storage remains independent and constrains malformed fields", () => {
  const storage = localStorageDouble(), api = plateApi(storage, [], []);
  const state = productionModule("frontend/studio-process-options-state.ts", {
    "./studio-plate-storage-keys.js": { PROCESS_OPTIONS_PLATE_PREFIX: "test:plate:" }, "./plate-slice-api.js": api,
  }, { localStorage: storage });
  state.saveProcess("a", { ...api.DEFAULT_SLICE_PROCESS_OVERRIDES, adhesion_mode: "brim", brim_width_mm: 9 });
  state.saveProcess("b", { ...api.DEFAULT_SLICE_PROCESS_OVERRIDES, adhesion_mode: "raft", raft_layers: 4 });
  assert.equal(state.loadProcess("a").adhesion_mode, "brim"); assert.equal(state.loadProcess("a").brim_width_mm, 9);
  assert.equal(state.loadProcess("b").adhesion_mode, "raft"); assert.equal(state.loadProcess("b").raft_layers, 4);
  storage.setItem("test:plate:bad", JSON.stringify({ adhesion_mode: "unknown", brim_width_mm: 200, raft_layers: -5 }));
  assert.equal(state.loadProcess("bad").adhesion_mode, "none"); assert.equal(state.loadProcess("bad").brim_width_mm, 30);
  assert.equal(state.loadProcess("bad").raft_layers, 1);
});

test("SD file download uses the selected printer path and preserves returned file bytes", async () => {
  const calls: string[] = [], bytes = new Uint8Array([80, 75, 3, 4, 0, 9]);
  const api = productionModule("frontend/printer-storage-api.ts", { "./ha-api-transport.js": {
    authenticatedFetch: async (url: string) => { calls.push(url); return new Response(bytes, { headers: { "Content-Type": "application/octet-stream", "Content-Disposition": "attachment; filename*=UTF-8''example%203.3mf" } }); },
    callEnvelopeApi: () => { throw Error("No inventory calls in this case"); }, errorMessage: (_: unknown, fallback: string) => fallback,
  } });
  const file: File = await new api.PrinterStorageApi().download("test printer", { path: "/models/a & b.3mf", name: "fallback.3mf", kind: "project" });
  const url = new URL(calls[0]!, "https://example.invalid");
  assert.equal(url.pathname, "/api/ultimate_3d_studio/v1/storage/test%20printer/download");
  assert.equal(url.searchParams.get("path"), "/models/a & b.3mf"); assert.equal(file.name, "example 3.3mf");
  assert.deepEqual(new Uint8Array(await file.arrayBuffer()), bytes);
});
test("SD permission failure does not create a file handoff", async () => {
  const api = productionModule("frontend/printer-storage-api.ts", { "./ha-api-transport.js": {
    authenticatedFetch: async () => new Response(JSON.stringify({ error: "forbidden" }), { status: 403 }),
    callEnvelopeApi() {}, errorMessage: (_: unknown, fallback: string) => fallback,
  } });
  await assert.rejects(new api.PrinterStorageApi().download("test", { path: "/denied.3mf", name: "denied.3mf" }), /403/);
});
test("SD workspace handoff queues the exact file and emits no direct print command", async () => {
  const queued: any[] = [], events: any[] = [], errors: unknown[] = [], file = new File(["fixture"], "sd.3mf");
  const open = productionMethod("frontend/printer-storage-workspace-v2.ts", "openWorkspace", {
    queueWorkspaceFile: (target: string, value: File) => queued.push({ target, value }), errorMessage: (e: Error) => e.message,
  });
  const selected = { path: "/sd.3mf", name: "sd.3mf" };
  const value: any = { printerId: "test", api: { async download(printer: string, selectedItem: unknown) { assert.equal(printer, "test"); assert.equal(selectedItem, selected); return file; } },
    dispatchEvent: (event: CustomEvent) => events.push(event), showError: (error: unknown) => errors.push(error) };
  await open.call(value, selected, "studio");
  assert.equal(queued.length, 1); assert.equal(queued[0].value, file); assert.equal(queued[0].target, "studio");
  assert.deepEqual(events.map(e => e.type), ["gallery-open-studio"]); assert.equal(errors.length, 0);
  value.api.download = async () => { throw Error("read blocked"); };
  await open.call(value, selected, "studio"); assert.equal(queued.length, 1); assert.equal(events.length, 1); assert.deepEqual(errors, ["read blocked"]);
});
test("source navigation selects the SD storage view without triggering a device operation", () => {
  const view: any = { selectedTab: "" }, routes: any[] = [];
  const value: any = { source: null, transient: view, navigate: (route: unknown) => routes.push(route) };
  productionMethod("frontend/app-shell-v4.ts", "sourceRequest").call(value, { detail: { source: "storage", target: "studio" } });
  assert.equal(view.selectedTab, "storage"); assert.deepEqual(plain(routes), [{ name: "galerie" }]);
});
test("local 3MF inspection posts the original file with its encoded name and propagates failure", async () => {
  const calls: any[] = [], file = new File(["fixture bytes"], "test & model.3mf", { type: "application/3mf" });
  const inspection = { format: "3mf", plate_count: 2, filaments: [] };
  let failure = false;
  const api = productionFunctions("frontend/slicing-api.ts", ["inspectSliceModel"], {
    API_PREFIX: "/api/ultimate_3d_studio/v1/slicer",
    authenticatedFetch: async (url: string, options: unknown) => { calls.push({ url, options }); return new Response(JSON.stringify({ data: inspection }), { status: failure ? 403 : 200 }); },
    responseError: async () => "inspection denied",
  });
  assert.deepEqual(plain(await api.inspectSliceModel(file)), inspection);
  assert.equal(new URL(calls[0].url, "https://example.invalid").searchParams.get("filename"), file.name);
  assert.equal(calls[0].options.body, file); assert.equal(calls[0].options.method, "POST");
  failure = true; await assert.rejects(api.inspectSliceModel(file), /inspection denied/);
});
test("local 3MF loader requests every plate and preserves instance material identity across mocked scene IO", async () => {
  const requested: number[] = [], file = new File(["synthetic 3mf"], "multi.3mf"), initial = newPlate(0, "old", selection());
  const data = { format: "3mf", plate_count: 2, plates: [{ name: "First" }, { name: "Second" }],
    filaments: [{ extruder: 2, name: "White", material: "PLA", color: "#ffffff" }], objects: [] };
  const load = productionMethod(workspace, "load", {
    newPlate, normalizeColor: (value: string) => value,
    inspectSliceModel: async (input: File) => { assert.equal(input, file); return data; },
    fetchScene: async (input: File, index: number, assetId: string) => { assert.equal(input, file); assert.equal(assetId, ""); requested.push(index);
      return { plate_size: [230 + index, 240], instances: [{ part_id: `part-${index}`, object_id: `object-${index}`, name: `Model ${index}`, positions: [0, 0, 0, 1, 0, 0, 0, 1, 0], extruder: 2, visible: true }] }; },
    buildMeshGeometryAsync: async () => item("geometry").geometry,
    fitImportedGroup: (entries: MeshInstance[]) => entries,
  });
  const value: any = { generation: 0, nextId: 1, operationTraceId: "", plates: [initial], activePlate: 0, assignments: new Map(), selected: new Set(),
    plate() { return this.plates[this.activePlate]; }, materialColor: () => "#ffffff", collectExtruders() {},
    traceStudioOperation() {}, audit() {}, renderFull() {}, renderStatus() {}, schedulePersist() {} };
  await load.call(value, file);
  assert.equal(value.error, ""); assert.equal(value.loading, false); assert.deepEqual(requested, [0, 1]);
  assert.equal(value.plates.length, 2); assert.deepEqual(plain(value.plates.map((p: any) => p.width)), [230, 231]);
  assert.equal(new Set(value.plates.map((p: any) => p.uid)).size, 2);
  for (const p of value.plates) { assert.equal(p.instances.length, 1); assert.equal(value.assignments.get(p.instances[0].id), "model:2"); assert.equal(p.instances[0].color, "#ffffff"); }
  assert.match(value.status, /hinzugefügt/);
});
