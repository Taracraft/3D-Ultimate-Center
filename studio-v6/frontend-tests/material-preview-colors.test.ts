import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { normalizeToolpathColor, normalizeToolpathPalette, toolpathMaterialColor, toolpathPaletteWarning, UNKNOWN_TOOLPATH_COLOR } from "../frontend/toolpath-material-colors.js";
import { buildContinuousToolpathMeshes } from "../frontend/toolpath-ribbon-geometry.js";
import { toolpathPreviewIndex, toolpathSupportKind, toolpathSupportColor, toolpathSupportLabel } from "../frontend/toolpath-support-filter.js";

// Executes actual production color/geometry and lifecycle methods, with explicit
// network and DOM boundaries. No browser, pixel or hardware acceptance is implied.
const root = process.env.PREVIEW_SOURCE_ROOT || process.cwd();
const file = join(root, "frontend/studio-mega-workspace-v2.ts");
const text = readFileSync(file, "utf8");
const ast = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
const studio = ast.statements.find((n): n is ts.ClassDeclaration => ts.isClassDeclaration(n) && n.name?.text === "Ultimate3DMegaStudioV2")!;
const pureNames = new Set(["normalizeColor", "mixColor", "materialPreviewColor", "materialHighlightColor", "previewFeatureKey", "featurePreviewColor", "historyShellFeature", "toolpathMeshes"]);
const functionSource = ast.statements.filter((n) => ts.isFunctionDeclaration(n) && pureNames.has(n.name?.text || "")).map((n) => n.getText(ast)).join("\n");
const globals = { normalizeToolpathPalette, toolpathMaterialColor, toolpathPaletteWarning, UNKNOWN_TOOLPATH_COLOR,
  buildContinuousToolpathMeshes, toolpathPreviewIndex, toolpathSupportKind, toolpathSupportColor, toolpathSupportLabel,
  NEUTRAL_COLOR: "#6b7785", COLORS: ["#ff4d4d", "#202020", "#36e51e", "#2e9bff"], Map, Set, Float32Array, Math, Number, String, Date, performance, console };
function evaluate(source: string, extra: Record<string, unknown> = {}) {
  const exports: any = {};
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    transformers: { before: [(context) => { const visit: ts.Visitor = (node) => ts.isPrivateIdentifier(node)
      ? ts.factory.createIdentifier(node.text.slice(1)) : ts.visitEachChild(node, visit, context);
      return (node) => ts.visitNode(node, visit) as ts.SourceFile; }] } }).outputText;
  runInNewContext(compiled, { ...globals, exports, ...extra });
  return exports;
}
function method(name: string, extra: Record<string, unknown> = {}) {
  const member = studio.members.find((m) => m.name?.getText(ast) === "#" + name)!;
  assert.ok(member, name);
  return evaluate(`exports.Subject = class Subject { ${member.getText(ast)} };`, extra).Subject.prototype[name];
}
const meshes = evaluate(functionSource + "\nexports.meshes = toolpathMeshes;").meshes;
const colors = ["#f72323", "#ffffff", "#fbff00", "#000000"];
const all = new Set(["outer_wall", "inner_wall", "top_surface", "bottom_surface", "infill", "solid_infill", "support", "support_interface", "purge_tower", "other"]);
function layer(index = 0, tools: number[] = [0, 1, 2, 3], feature = "Outer wall", category = "model"): any {
  return { index, z: (index + 1) * .2, extrusion_mm: tools.length, features: [feature],
    segments: tools.map((tool, n) => [n * 20, 10, n * 20 + 10, 10, (index + 1) * .2, tool, .5, feature, category]) };
}
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));

for (const [input, expected] of [["#000000", "#000000"], [" FFFFFF ", "#ffffff"], ["#AbCdEfFF", "#abcdef"], ["FBFF00", "#fbff00"]]) {
  test(`palette retains exact RGB for ${input}`, () => assert.equal(normalizeToolpathColor(input), expected));
}
for (const input of ["#123", "#123456junk", "rgb(1,2,3)", "", null, undefined, 123456, "#gg0000"]) {
  test(`palette never invents a filament color for ${JSON.stringify(input)}`, () => assert.equal(normalizeToolpathColor(input), null));
}
test("invalid palette entries retain channel positions rather than compacting", () => {
  assert.deepEqual(normalizeToolpathPalette(["#F72323", null, "invalid", "#000000"]), ["#f72323", "", "", "#000000"]);
  assert.deepEqual(normalizeToolpathPalette({}), []);
});
for (const tool of [-1, 4, 255, 1000, 1.5, NaN, Infinity, "1", null]) {
  test(`unknown tool ${String(tool)} is not wrapped to an existing color`, () => assert.equal(toolpathMaterialColor(colors, tool), null));
}
test("production meshes preserve all four real material colors", () => {
  const input = [layer()]; const before = plain(input);
  const result = meshes(input, 0, colors, false, "material", false, all);
  assert.deepEqual([...new Set(result.filter((m: any) => !m.id.includes(":highlight")).map((m: any) => m.color))].sort(), [...colors].sort());
  assert.deepEqual(plain(input), before);
});
test("history keeps material RGB while active-layer highlights remain available", () => {
  const result = meshes([layer(0), layer(1)], 1, colors, true, "material", false, all);
  assert.deepEqual([...new Set(result.filter((m: any) => !m.id.includes(":highlight")).map((m: any) => m.color))].sort(), [...colors].sort());
  assert.ok(result.some((m: any) => m.id.includes(":highlight")));
});
test("diagnostic Drucktyp remains explicit and does not rewrite source paths", () => {
  const input = [layer()]; const before = plain(input);
  const result = meshes(input, 0, colors, false, "feature", false, all);
  assert.deepEqual([...new Set(result.filter((m: any) => !m.id.includes(":highlight")).map((m: any) => m.color))], ["#ff4b4b"]);
  assert.deepEqual(plain(input), before);
});
test("unknown material in actual meshes is neutrally labelled, never another channel", () => {
  const result = meshes([layer(0, [4])], 0, colors, false, "material", false, all);
  assert.ok(result.length); assert.ok(result.filter((m: any) => !m.id.includes(":highlight")).every((m: any) => m.color === UNKNOWN_TOOLPATH_COLOR));
  assert.ok(result.every((m: any) => m.name.endsWith(" · Unbekannte Materialfarbe")));
});
test("feature hiding and safe support isolation survive material default", () => {
  assert.equal(meshes([layer()], 0, colors, false, "material", false, new Set()).length, 0);
  const input = [layer(0, [1], "Support interface", "support")];
  const result = meshes(input, 0, colors, false, "material", true, all);
  assert.ok(result.every((m: any) => m.color === toolpathSupportColor("interface")));
  assert.equal(meshes([layer()], 0, colors, false, "material", true, all).length, 0);
});
test("missing palette is visible and input text cannot enter a warning", () => {
  const input = [layer(0, [0, 3])];
  assert.match(toolpathPaletteWarning(input, []), /Kanal 1, Kanal 4/);
  assert.match(toolpathPaletteWarning(input, []), /Grau.*keine Filamentzuordnung/);
  assert.equal(toolpathPaletteWarning(input, colors), "");
  input[0].segments = [[0, 0, 1, 1, .2, "<script>bad</script>", 1]];
  assert.doesNotMatch(toolpathPaletteWarning([...input], []), /script/);
});
test("new sessions initialize material mode in the real class field", () => {
  const field = studio.members.find((m) => m.name?.getText(ast) === "#previewColorMode") as ts.PropertyDeclaration;
  assert.ok(field.initializer && ts.isStringLiteral(field.initializer));
  assert.equal(field.initializer.text, "material");
});
test("only the explicit diagnostic click handler can assign feature mode", () => {
  const owners: string[] = [];
  for (const member of studio.members) {
    const visit = (node: ts.Node): void => {
      if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken
        && node.left.getText(ast) === "this.#previewColorMode" && ts.isStringLiteral(node.right) && node.right.text === "feature") owners.push(member.name?.getText(ast) || "");
      ts.forEachChild(node, visit);
    }; visit(member);
  }
  assert.deepEqual(owners, ["#renderSidebarContent"]);
});
test("production viewport never queries current AMS to color a saved job", () => {
  for (const palette of [colors, []]) {
    const plate = { layers: [layer()], visibleLayer: 0, toolColors: palette };
    let actual: unknown; let amsCalls = 0;
    method("displayInstances", { toolpathMeshes: (...args: any[]) => { actual = args[2]; return []; } }).call({
      plate: () => plate, mode: "preview", previewColorMode: "material", previewCumulative: true,
      previewSupportOnly: false, previewVisibleFeatures: all,
      materialChoices: () => { amsCalls++; return [{ color: "#00ff00" }]; },
    });
    assert.equal(amsCalls, 0); assert.equal(actual, palette);
  }
});
for (const selectedMode of ["material", "feature"]) {
  test(`production job reconciliation retains explicitly selected ${selectedMode}`, async () => {
    const plate: any = { id: 0, name: "test", jobId: "saved-job", layers: [], layerCount: 0, toolColors: [] };
    const job = { id: plate.jobId, status: "succeeded" };
    const state: any = { plate: () => plate, reconcilingJobs: new Set(), sliceTraceByJob: new Map(), previewColorMode: selectedMode,
      traceSliceActivity() {}, audit() {}, renderStatus() {}, renderAfterSliceReconcile() {}, async persistNow() {} };
    const loaded = layer();
    await method("activatePlateJob", {
      ACTIVE: new Set(["running", "queued"]), fetchSliceJob: async () => job,
      fetchToolpath: async (_id: string, start?: number) => start === undefined
        ? { layer_count: 1, filament_colors: ["#F72323", "#FFFFFF", "#FBFF00", "#000000"], layers: [{ segment_count: 4, features: [] }] }
        : { chunk: { layers: [loaded], segment_count: 4 } },
      previewFeatureLabel: (x: string) => x, previewFeatureKey: () => "other",
      jobActivityStore: { registerSlicerJob() {} },
    }).call(state, plate);
    assert.equal(plate.stage, "sliced"); assert.equal(plate.lastError, "");
    assert.equal(state.mode, "preview"); assert.equal(state.previewColorMode, selectedMode);
    assert.deepEqual(plain(plate.toolColors), colors); assert.equal(plate.layers[0], loaded);
  });
}
