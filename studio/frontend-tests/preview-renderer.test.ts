import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Actual constructor, GPU lifecycle, camera and render methods execute below.
// Canvas/GL/RAF are the explicit boundaries. MockGL does not produce pixels or
// compile GLSL, so these cases are not a visual black-material acceptance.
const sourceRoot = process.env.PREVIEW_SOURCE_ROOT || process.cwd();
const file = join(sourceRoot, "frontend/studio-mega-viewport.ts");
const text = readFileSync(file, "utf8");
const ast = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
const source = ast.statements.filter((node) => !ts.isImportDeclaration(node))
  .map((node) => node.getText(ast)).join("\n")
  + "\nexports.Subject = StudioMegaViewport; exports.worldCorners = worldCorners; exports.transformPoint = transformPoint;";
const compiled = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  transformers: { before: [(context) => {
    const visit: ts.Visitor = (node) => ts.isPrivateIdentifier(node)
      ? ts.factory.createIdentifier(node.text.slice(1))
      : ts.visitEachChild(node, visit, context);
    return (node) => ts.visitNode(node, visit) as ts.SourceFile;
  }] },
}).outputText;
const exported: any = {};
runInNewContext(compiled, {
  exports: exported,
  Float32Array, Math, Number, String, Map, Set,
  devicePixelRatio: 1,
  ResizeObserver: class { observe() {} disconnect() {} },
  requestAnimationFrame: () => 1,
  cancelAnimationFrame() {},
});

type Buffer = { id: number; data?: unknown };
type Program = { id: number; shaders: any[]; uniforms: Map<string, any> };
type Draw = {
  id: string | null;
  program: Program;
  uniforms: Record<string, any>;
  blend: boolean;
  depthTest: boolean;
  depthWrite: boolean;
  blendFactors: readonly [number, number] | null;
};

class MockGL {
  ARRAY_BUFFER = 34962;
  STATIC_DRAW = 35044;
  FLOAT = 5126;
  TRIANGLES = 4;
  LINES = 1;
  VERTEX_SHADER = 35633;
  FRAGMENT_SHADER = 35632;
  COMPILE_STATUS = 35713;
  LINK_STATUS = 35714;
  DEPTH_TEST = 2929;
  CULL_FACE = 2884;
  BLEND = 3042;
  LEQUAL = 515;
  POLYGON_OFFSET_FILL = 32823;
  COLOR_BUFFER_BIT = 16384;
  DEPTH_BUFFER_BIT = 256;
  SRC_ALPHA = 770;
  ONE_MINUS_SRC_ALPHA = 771;
  FRONT = 1028;
  BACK = 1029;
  enabled = new Set<number>();
  depthWrite = true;
  blendFactors: readonly [number, number] | null = null;
  currentProgram: Program | null = null;
  currentBuffer: Buffer | null = null;
  buffers: Buffer[] = [];
  programs: Program[] = [];
  shaders: any[] = [];
  draws: Draw[] = [];
  uploads = 0;
  deletes = 0;
  resolveId: (buffer: Buffer | null) => string | null = () => null;
  failDrawId: string | null = null;

  createBuffer() { const buffer = { id: this.buffers.length }; this.buffers.push(buffer); return buffer; }
  bindBuffer(_target: number, buffer: Buffer) { this.currentBuffer = buffer; }
  bufferData(_target: number, data: unknown) { this.currentBuffer!.data = data; this.uploads++; }
  deleteBuffer() { this.deletes++; }
  createShader(type: number) { const shader = { type, source: "" }; this.shaders.push(shader); return shader; }
  shaderSource(shader: any, shaderText: string) { shader.source = shaderText; }
  compileShader() {}
  getShaderParameter() { return true; }
  getShaderInfoLog() { return ""; }
  createProgram() { const program = { id: this.programs.length, shaders: [], uniforms: new Map() }; this.programs.push(program); return program; }
  attachShader(program: Program, shader: any) { program.shaders.push(shader); }
  linkProgram() {}
  getProgramParameter() { return true; }
  getProgramInfoLog() { return ""; }
  useProgram(program: Program) { this.currentProgram = program; }
  getAttribLocation(_program: Program, name: string) { return name === "a_normal" ? 1 : 0; }
  enableVertexAttribArray() {}
  vertexAttribPointer() {}
  getUniformLocation(program: Program, name: string) { return { program, name }; }
  uniformMatrix4fv(location: any, _transpose: boolean, value: ArrayLike<number>) { location.program.uniforms.set(location.name, Array.from(value)); }
  uniform3fv(location: any, value: ArrayLike<number>) { location.program.uniforms.set(location.name, Array.from(value)); }
  uniform1f(location: any, value: number) { location.program.uniforms.set(location.name, value); }
  uniform1i(location: any, value: number) { location.program.uniforms.set(location.name, value); }
  enable(cap: number) { this.enabled.add(cap); }
  disable(cap: number) { this.enabled.delete(cap); }
  depthMask(value: boolean) { this.depthWrite = value; }
  depthFunc() {}
  blendFunc(sourceFactor: number, destinationFactor: number) { this.blendFactors = [sourceFactor, destinationFactor]; }
  cullFace() {}
  clearColor() {}
  clear() {}
  polygonOffset() {}
  viewport() {}
  drawArrays() {
    const id = this.currentProgram === this.programs[0] ? this.resolveId(this.currentBuffer) : null;
    if (id && id === this.failDrawId) throw new Error("synthetic draw failure");
    this.draws.push({
      id, program: this.currentProgram!,
      uniforms: Object.fromEntries(this.currentProgram!.uniforms),
      blend: this.enabled.has(this.BLEND), depthTest: this.enabled.has(this.DEPTH_TEST),
      depthWrite: this.depthWrite, blendFactors: this.blendFactors,
    });
  }
}

const plate = {
  widthMm: 256, depthMm: 256, surface: "textured",
  baseColor: "#555555", minorGridColor: "#777777",
  majorGridColor: "#888888", accentColor: "#999999",
};

function subject() {
  const gl = new MockGL();
  const canvas = {
    width: 640, height: 480, clientWidth: 640, clientHeight: 480,
    getContext: () => gl,
    addEventListener() {},
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 640, height: 480 }),
    setPointerCapture() {},
  };
  const viewport = new exported.Subject(canvas, plate);
  gl.resolveId = (buffer) => {
    for (const [id, mesh] of viewport.gpu) {
      if (mesh.position === buffer || mesh.normal === buffer) return id;
    }
    return null;
  };
  return { viewport, gl };
}

function instance(id: string, extra: Record<string, unknown> = {}): any {
  return {
    id, name: id,
    geometry: {
      positions: new Float32Array([0, 0, 0, 10, 0, 0, 0, 10, 0]),
      normals: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
      triangleCount: 1, boundsMin: [0, 0, 0], boundsMax: [10, 10, .2],
    },
    position: [20, 20, 0], rotation: [0, 0, 0], scale: [1, 1, 1],
    color: "#000000", visible: true, ...extra,
  };
}

function meshDraws(gl: MockGL) { return gl.draws.filter((draw) => draw.id !== null); }

test("actual renderer draws opaque preview before transparent remainder and restores GL state", () => {
  const { viewport, gl } = subject();
  viewport.setPreviewMode(true);
  viewport.setInstances([
    instance("remainder", { opacity: .16, clipMinZ: .2 }),
    instance("printed"),
  ]);
  // An overlay runs after both mesh passes; it must not inherit ghost blending.
  viewport.overlayMeshes = [{ buffer: gl.createBuffer(), count: 2, mode: gl.LINES, color: "#ffffff" }];
  viewport.render();
  const draws = meshDraws(gl);
  assert.deepEqual(draws.map((draw) => draw.id), ["printed", "remainder"]);
  assert.equal(draws[0]!.uniforms.u_opacity, 1);
  assert.equal(draws[0]!.blend, false);
  assert.equal(draws[0]!.depthWrite, true);
  assert.equal(draws[1]!.uniforms.u_opacity, .16);
  assert.equal(draws[1]!.blend, true);
  assert.equal(draws[1]!.depthTest, true);
  assert.equal(draws[1]!.depthWrite, false);
  assert.deepEqual(draws[1]!.blendFactors, [gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA]);
  const overlay = gl.draws.at(-1)!;
  assert.equal(overlay.program, gl.programs[1]);
  assert.equal(overlay.blend, false);
  assert.equal(overlay.depthWrite, true);
  assert.equal(gl.enabled.has(gl.BLEND), false);
  assert.equal(gl.depthWrite, true);
});

test("actual preview render preserves black job RGB and supplies preview-lighting control", () => {
  const { viewport, gl } = subject();
  viewport.setPreviewMode(true);
  const black = instance("black-filament");
  viewport.setInstances([black]);
  viewport.render();
  const draw = meshDraws(gl)[0]!;
  assert.deepEqual(draw.uniforms.u_color, [0, 0, 0]);
  assert.equal(draw.uniforms.u_preview, 1);
  assert.equal(black.color, "#000000");
  const shaderSources = gl.programs[0]!.shaders.map((shader) => shader.source);
  assert.ok(shaderSources.some((shaderText) => shaderText.includes("uniform vec3 u_color")));
  // The captured actual GLSL is available for a later real-WebGL pixel pass.
  // No claim about visible shaded RGB can follow from this MockGL case alone.
});

test("transparent remainder pages draw far to near and follow an actual camera orbit", () => {
  const { viewport, gl } = subject();
  const near = instance("near-blue", { opacity: .16, position: [224, 128, 0], color: "#0000ff" });
  const far = instance("far-red", { opacity: .16, position: [32, 128, 0], color: "#ff0000" });
  viewport.setPreviewMode(true);
  // Default camera is at positive X/Y. Intentionally supply near before far.
  viewport.setInstances([near, far]);
  viewport.render();
  assert.deepEqual(meshDraws(gl).map((draw) => draw.id), ["far-red", "near-blue"]);
  assert.deepEqual(meshDraws(gl)[0]!.uniforms.u_color, [1, 0, 0]);
  assert.deepEqual(meshDraws(gl)[1]!.uniforms.u_color, [0, 0, 1]);
  gl.draws.length = 0;
  viewport.azimuth += Math.PI;
  viewport.render();
  assert.deepEqual(meshDraws(gl).map((draw) => draw.id), ["near-blue", "far-red"]);
  for (const draw of meshDraws(gl)) {
    assert.equal(draw.blend, true);
    assert.equal(draw.depthTest, true);
    assert.equal(draw.depthWrite, false);
  }
});

test("opaque meshes reset ghost clipping and opacity uniforms in the next frame", () => {
  const { viewport, gl } = subject();
  viewport.setPreviewMode(true);
  viewport.setInstances([instance("remainder", { opacity: .16, clipMinZ: 12.4 })]);
  viewport.render();
  const first = meshDraws(gl)[0]!;
  assert.equal(first.uniforms.u_clip_enabled, 1);
  assert.equal(first.uniforms.u_clip_min_z, 12.4);
  gl.draws.length = 0;
  viewport.setPreviewMode(false);
  viewport.setInstances([instance("cad-model")]);
  viewport.render();
  const second = meshDraws(gl)[0]!;
  assert.equal(second.uniforms.u_opacity, 1);
  assert.equal(second.uniforms.u_clip_enabled, 0);
  assert.equal(second.uniforms.u_preview, 0);
  assert.equal(second.blend, false);
  assert.equal(second.depthWrite, true);
});

test("layer clipping updates retain the actual GPU buffers for unchanged remainder geometry", () => {
  const { viewport, gl } = subject();
  const remainder = instance("job-remainder", { opacity: .16, clipMinZ: .2 });
  viewport.setInstances([remainder]);
  const cached = viewport.gpu.get(remainder.id);
  const uploads = gl.uploads;
  const deletes = gl.deletes;
  for (const z of [.4, .6, .8]) {
    viewport.setInstances([{ ...remainder, clipMinZ: z }]);
    assert.equal(viewport.gpu.get(remainder.id), cached);
    assert.equal(gl.uploads, uploads);
    assert.equal(gl.deletes, deletes);
  }
});

test("transparent draw failure restores GL state before it propagates", () => {
  const { viewport, gl } = subject();
  viewport.setInstances([instance("failed-remainder", { opacity: .16, clipMinZ: .2 })]);
  gl.failDrawId = "failed-remainder";
  assert.throws(() => viewport.render(), /synthetic draw failure/);
  assert.equal(gl.enabled.has(gl.BLEND), false);
  assert.equal(gl.depthWrite, true);
});

test("preview framing contains the full tall job including an invisible remainder", () => {
  const { viewport } = subject();
  const remainder = instance("tall-job-remainder", { opacity: .16, visible: false });
  remainder.geometry = { ...remainder.geometry, boundsMax: [10, 10, 600] };
  viewport.setPreviewMode(true);
  viewport.setInstances([instance("printed-layer"), remainder]);
  viewport.frameAll();
  assert.ok(viewport.target[2] > 200 && viewport.target[2] < 400);
  const vp = viewport.viewProjection();
  const points = [...exported.worldCorners(remainder), [0, 0, 0], [256, 256, 0]];
  for (const point of points) {
    const [x, y, z, w] = exported.transformPoint(vp, point);
    assert.ok(w > 0, "job point must lie in front of camera");
    assert.ok(Math.abs(x / w) <= 1.001, "full job width must fit camera");
    assert.ok(Math.abs(y / w) <= 1.001, "full job height must fit camera");
    assert.ok(Math.abs(z / w) <= 1.001, "full job must fit near/far clip planes");
  }
});

test("layer changes preserve the actual camera after full-job framing", () => {
  const { viewport } = subject();
  const remainder = instance("stable-job-remainder", { opacity: .16, clipMinZ: .2 });
  remainder.geometry = { ...remainder.geometry, boundsMax: [10, 10, 600] };
  viewport.setPreviewMode(true);
  viewport.setInstances([remainder]);
  viewport.frameAll();
  const camera = {
    target: [...viewport.target], distance: viewport.distance,
    azimuth: viewport.azimuth, elevation: viewport.elevation,
  };
  viewport.setInstances([{ ...remainder, clipMinZ: 480 }]);
  viewport.render();
  assert.deepEqual({
    target: [...viewport.target], distance: viewport.distance,
    azimuth: viewport.azimuth, elevation: viewport.elevation,
  }, camera);
});

test("prepare framing keeps the plate-centered camera behavior", () => {
  const { viewport } = subject();
  const tall = instance("tall-cad-model");
  tall.geometry = { ...tall.geometry, boundsMax: [10, 10, 600] };
  viewport.setPreviewMode(false);
  viewport.setInstances([tall]);
  viewport.frameAll();
  assert.deepEqual([...viewport.target], [128, 128, 0]);
});
