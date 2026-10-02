import type { StudioBuildPlateVisual } from "./studio-build-plates.js";
import type { MeshInstance, Vec3 } from "./webgl-studio-viewport.js";

type GpuMesh = { position: WebGLBuffer; normal: WebGLBuffer; count: number };
type FlatMesh = { buffer: WebGLBuffer; count: number; mode: number; color: string };
export type MegaGizmoMode = "select" | "translate" | "rotate" | "scale";
export type MegaAxis = "x" | "y" | "z";

const DEG = Math.PI / 180;

function add(a: Vec3, b: Vec3): Vec3 { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
function sub(a: Vec3, b: Vec3): Vec3 { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function mul(a: Vec3, value: number): Vec3 { return [a[0] * value, a[1] * value, a[2] * value]; }
function dot(a: Vec3, b: Vec3): number { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function cross(a: Vec3, b: Vec3): Vec3 { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function normalize(a: Vec3): Vec3 { const length = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / length, a[1] / length, a[2] / length]; }
function identity(): Float32Array { return new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]); }
function multiply(a: Float32Array, b: Float32Array): Float32Array {
  const result = new Float32Array(16);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      result[column * 4 + row] =
        a[row]! * b[column * 4]!
        + a[4 + row]! * b[column * 4 + 1]!
        + a[8 + row]! * b[column * 4 + 2]!
        + a[12 + row]! * b[column * 4 + 3]!;
    }
  }
  return result;
}
function invert(m: Float32Array): Float32Array | null {
  const out = new Float32Array(16);
  const b00 = m[0]! * m[5]! - m[1]! * m[4]!;
  const b01 = m[0]! * m[6]! - m[2]! * m[4]!;
  const b02 = m[0]! * m[7]! - m[3]! * m[4]!;
  const b03 = m[1]! * m[6]! - m[2]! * m[5]!;
  const b04 = m[1]! * m[7]! - m[3]! * m[5]!;
  const b05 = m[2]! * m[7]! - m[3]! * m[6]!;
  const b06 = m[8]! * m[13]! - m[9]! * m[12]!;
  const b07 = m[8]! * m[14]! - m[10]! * m[12]!;
  const b08 = m[8]! * m[15]! - m[11]! * m[12]!;
  const b09 = m[9]! * m[14]! - m[10]! * m[13]!;
  const b10 = m[9]! * m[15]! - m[11]! * m[13]!;
  const b11 = m[10]! * m[15]! - m[11]! * m[14]!;
  let det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
  if (!det) return null;
  det = 1 / det;
  out[0] = (m[5]! * b11 - m[6]! * b10 + m[7]! * b09) * det;
  out[1] = (m[2]! * b10 - m[1]! * b11 - m[3]! * b09) * det;
  out[2] = (m[13]! * b05 - m[14]! * b04 + m[15]! * b03) * det;
  out[3] = (m[10]! * b04 - m[9]! * b05 - m[11]! * b03) * det;
  out[4] = (m[6]! * b08 - m[4]! * b11 - m[7]! * b07) * det;
  out[5] = (m[0]! * b11 - m[2]! * b08 + m[3]! * b07) * det;
  out[6] = (m[14]! * b02 - m[12]! * b05 - m[15]! * b01) * det;
  out[7] = (m[8]! * b05 - m[10]! * b02 + m[11]! * b01) * det;
  out[8] = (m[4]! * b10 - m[5]! * b08 + m[7]! * b06) * det;
  out[9] = (m[1]! * b08 - m[0]! * b10 - m[3]! * b06) * det;
  out[10] = (m[12]! * b04 - m[13]! * b02 + m[15]! * b00) * det;
  out[11] = (m[9]! * b02 - m[8]! * b04 - m[11]! * b00) * det;
  out[12] = (m[5]! * b07 - m[4]! * b09 - m[6]! * b06) * det;
  out[13] = (m[8]! * b03 - m[0]! * b07 + m[2]! * b06) * det;
  out[14] = (m[13]! * b01 - m[12]! * b03 - m[14]! * b00) * det;
  out[15] = (m[4]! * b03 - m[8]! * b01 + m[10]! * b00) * det;
  return out;
}
function translation(value: Vec3): Float32Array { const matrix = identity(); matrix[12] = value[0]; matrix[13] = value[1]; matrix[14] = value[2]; return matrix; }
function scaling(value: Vec3): Float32Array { const matrix = identity(); matrix[0] = value[0]; matrix[5] = value[1]; matrix[10] = value[2]; return matrix; }
function rotationX(value: number): Float32Array { const c = Math.cos(value), s = Math.sin(value); return new Float32Array([1,0,0,0,0,c,s,0,0,-s,c,0,0,0,0,1]); }
function rotationY(value: number): Float32Array { const c = Math.cos(value), s = Math.sin(value); return new Float32Array([c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1]); }
function rotationZ(value: number): Float32Array { const c = Math.cos(value), s = Math.sin(value); return new Float32Array([c,s,0,0,-s,c,0,0,0,0,1,0,0,0,0,1]); }
function perspective(fovy: number, aspect: number, near: number, far: number): Float32Array {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
  return new Float32Array([f / aspect,0,0,0,0,f,0,0,0,0,(far + near) * nf,-1,0,0,2 * far * near * nf,0]);
}
function lookAt(eye: Vec3, target: Vec3, up: Vec3): Float32Array {
  const z = normalize(sub(eye, target));
  const x = normalize(cross(up, z));
  const y = cross(z, x);
  return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);
}
function modelMatrix(instance: MeshInstance): Float32Array {
  return multiply(
    translation(instance.position),
    multiply(
      rotationZ(instance.rotation[2] * DEG),
      multiply(rotationY(instance.rotation[1] * DEG), multiply(rotationX(instance.rotation[0] * DEG), scaling(instance.scale))),
    ),
  );
}
function rgb(value: string): Float32Array {
  const hex = value.replace("#", "").padEnd(6, "0").slice(0, 6);
  return new Float32Array([
    Number.parseInt(hex.slice(0, 2), 16) / 255,
    Number.parseInt(hex.slice(2, 4), 16) / 255,
    Number.parseInt(hex.slice(4, 6), 16) / 255,
  ]);
}
function transformPoint(matrix: Float32Array, point: Vec3): [number, number, number, number] {
  const [x, y, z] = point;
  return [
    matrix[0]! * x + matrix[4]! * y + matrix[8]! * z + matrix[12]!,
    matrix[1]! * x + matrix[5]! * y + matrix[9]! * z + matrix[13]!,
    matrix[2]! * x + matrix[6]! * y + matrix[10]! * z + matrix[14]!,
    matrix[3]! * x + matrix[7]! * y + matrix[11]! * z + matrix[15]!,
  ];
}
function corners(instance: MeshInstance): Vec3[] {
  const [x0, y0, z0] = instance.geometry.boundsMin;
  const [x1, y1, z1] = instance.geometry.boundsMax;
  return [[x0,y0,z0],[x1,y0,z0],[x0,y1,z0],[x1,y1,z0],[x0,y0,z1],[x1,y0,z1],[x0,y1,z1],[x1,y1,z1]];
}
function worldCorners(instance: MeshInstance): Vec3[] {
  const matrix = modelMatrix(instance);
  return corners(instance).map((point) => {
    const transformed = transformPoint(matrix, point);
    return [transformed[0], transformed[1], transformed[2]];
  });
}
function line(a: Vec3, b: Vec3, target: number[]): void { target.push(...a, ...b); }
function quad(x0: number, y0: number, x1: number, y1: number, z: number, target: number[]): void {
  target.push(x0,y0,z,x1,y0,z,x1,y1,z, x0,y0,z,x1,y1,z,x0,y1,z);
}
function shadeHex(value: string, factor: number): string {
  const source = value.replace("#", "").padEnd(6, "0").slice(0, 6);
  const channels = [0,2,4].map((offset) => Math.max(0, Math.min(255, Math.round(Number.parseInt(source.slice(offset, offset + 2), 16) * factor))));
  return `#${channels.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}
function diagonalTexture(width: number, depth: number, step: number, z: number, target: number[]): void {
  for (let offset = -depth; offset <= width; offset += step) {
    const x0 = Math.max(0, offset);
    const y0 = Math.max(0, -offset);
    const x1 = Math.min(width, depth + offset);
    const y1 = Math.min(depth, width - offset);
    if (x1 > x0 && y1 > y0) line([x0,y0,z],[x1,y1,z],target);
  }
}

export class StudioMegaViewport {
  readonly canvas: HTMLCanvasElement;
  readonly gl: WebGLRenderingContext;
  readonly #meshProgram: WebGLProgram;
  readonly #flatProgram: WebGLProgram;
  readonly #gpu = new Map<string, GpuMesh>();
  #instances: readonly MeshInstance[] = [];
  #selected = new Set<string>();
  #plate: StudioBuildPlateVisual;
  #plateMeshes: FlatMesh[] = [];
  #overlayMeshes: FlatMesh[] = [];
  #gizmoPosition: Vec3 | null = null;
  #gizmoMode: MegaGizmoMode = "select";
  #activeAxis: MegaAxis = "x";
  #azimuth = 45 * DEG;
  #elevation = 42 * DEG;
  #distance = 520;
  #target: Vec3 = [128, 128, 0];
  #previewMode = false;
  #pointer: { id: number; x: number; y: number; button: number } | null = null;
  #raf = 0;
  #resizeObserver: ResizeObserver;

  constructor(canvas: HTMLCanvasElement, plate: StudioBuildPlateVisual) {
    this.canvas = canvas;
    this.#plate = plate;
    const gl = canvas.getContext("webgl", { antialias: true, alpha: false, depth: true });
    if (!gl) throw new Error("WebGL ist nicht verfügbar");
    this.gl = gl;
    this.#meshProgram = this.#program(
      "attribute vec3 a_position;attribute vec3 a_normal;uniform mat4 u_mvp;uniform mat4 u_model;varying vec3 v_normal;void main(){v_normal=mat3(u_model)*a_normal;gl_Position=u_mvp*vec4(a_position,1.0);}",
      "precision mediump float;uniform vec3 u_color;varying vec3 v_normal;void main(){vec3 n=normalize(v_normal);vec3 light=normalize(vec3(.35,-.45,.82));float diffuse=max(dot(n,light),0.0);float back=max(dot(-n,light),0.0);float illumination=.22+.70*diffuse+.18*back;gl_FragColor=vec4(u_color*illumination,1.0);}",
    );
    this.#flatProgram = this.#program(
      "attribute vec3 a_position;uniform mat4 u_mvp;void main(){gl_Position=u_mvp*vec4(a_position,1.0);}",
      "precision mediump float;uniform vec3 u_color;void main(){gl_FragColor=vec4(u_color,1.0);}",
    );
    this.#rebuildPlate();
    this.#bind();
    this.#resizeObserver = new ResizeObserver(() => this.resize());
    this.#resizeObserver.observe(this.canvas);
    this.resize();
  }

  setPlate(plate: StudioBuildPlateVisual): void {
    this.#plate = plate;
    this.#target = [plate.widthMm / 2, plate.depthMm / 2, 0];
    this.#distance = Math.max(plate.widthMm, plate.depthMm) * 2;
    this.#rebuildPlate();
    this.requestRender();
  }
  setInstances(instances: readonly MeshInstance[]): void {
    const previousById = new Map(this.#instances.map((instance) => [instance.id, instance]));
    const nextById = new Map(instances.map((instance) => [instance.id, instance]));
    for (const [id, mesh] of this.#gpu) {
      const previous = previousById.get(id);
      const next = nextById.get(id);
      if (!next || previous?.geometry !== next.geometry) {
        this.gl.deleteBuffer(mesh.position);
        this.gl.deleteBuffer(mesh.normal);
        this.#gpu.delete(id);
      }
    }
    this.#instances = instances;
    for (const instance of instances) this.#ensureGpu(instance);
    this.#rebuildOverlays();
    this.resize();
    this.requestRender();
  }
  setSelected(ids: readonly string[]): void {
    this.#selected = new Set(ids);
    this.#rebuildOverlays();
    this.requestRender();
  }
  setGizmo(position: Vec3 | null, mode: MegaGizmoMode, axis: MegaAxis): void {
    this.#gizmoPosition = position;
    this.#gizmoMode = mode;
    this.#activeAxis = axis;
    this.#rebuildOverlays();
    this.requestRender();
  }
  setPreviewMode(value: boolean): void {
    this.#previewMode = value;
    this.requestRender();
  }
  frameAll(): void {
    this.resize();
    this.#target = [this.#plate.widthMm / 2, this.#plate.depthMm / 2, 0];
    this.#distance = Math.max(this.#plate.widthMm, this.#plate.depthMm) * (this.#previewMode ? 1.48 : 1.82);
    this.requestRender();
  }

  platePoint(clientX: number, clientY: number): Vec3 | null {
    const rect = this.canvas.getBoundingClientRect();
    const x = ((clientX - rect.left) / Math.max(1, rect.width)) * 2 - 1;
    const y = 1 - ((clientY - rect.top) / Math.max(1, rect.height)) * 2;
    const inverse = invert(this.#viewProjection());
    if (!inverse) return null;
    const unproject = (z: number): Vec3 | null => {
      const value = transformPoint(inverse, [x, y, z]);
      const w = value[3] || 1;
      return [value[0] / w, value[1] / w, value[2] / w];
    };
    const near = unproject(-1);
    const far = unproject(1);
    if (!near || !far) return null;
    const direction = sub(far, near);
    if (Math.abs(direction[2]) < 0.00001) return null;
    const amount = -near[2] / direction[2];
    if (!Number.isFinite(amount)) return null;
    const point = add(near, mul(direction, amount));
    return [
      Math.max(0, Math.min(this.#plate.widthMm, point[0])),
      Math.max(0, Math.min(this.#plate.depthMm, point[1])),
      0,
    ];
  }

  #projectedBounds(instance: MeshInstance): { minX: number; maxX: number; minY: number; maxY: number; depth: number } {
    const mvp = multiply(this.#viewProjection(), modelMatrix(instance));
    const projected = corners(instance).map((point) => {
      const value = transformPoint(mvp, point);
      const w = value[3] || 1;
      return {
        x: (value[0] / w * .5 + .5) * this.canvas.width,
        y: (1 - (value[1] / w * .5 + .5)) * this.canvas.height,
        z: value[2] / w,
      };
    });
    return {
      minX: Math.min(...projected.map((point) => point.x)),
      maxX: Math.max(...projected.map((point) => point.x)),
      minY: Math.min(...projected.map((point) => point.y)),
      maxY: Math.max(...projected.map((point) => point.y)),
      depth: projected.reduce((sum, point) => sum + point.z, 0) / projected.length,
    };
  }

  pick(clientX: number, clientY: number): string | null {
    const rect = this.canvas.getBoundingClientRect();
    const px = (clientX - rect.left) * (this.canvas.width / Math.max(1, rect.width));
    const py = (clientY - rect.top) * (this.canvas.height / Math.max(1, rect.height));
    let best: { id: string; area: number; depth: number } | null = null;
    for (const instance of this.#instances) {
      if (!instance.visible) continue;
      const bounds = this.#projectedBounds(instance);
      if (px < bounds.minX - 5 || px > bounds.maxX + 5 || py < bounds.minY - 5 || py > bounds.maxY + 5) continue;
      const area = Math.max(1, (bounds.maxX - bounds.minX) * (bounds.maxY - bounds.minY));
      if (!best || bounds.depth < best.depth || (Math.abs(bounds.depth - best.depth) < .02 && area < best.area)) {
        best = { id: instance.id, area, depth: bounds.depth };
      }
    }
    return best?.id ?? null;
  }

  pickRect(startClientX: number, startClientY: number, endClientX: number, endClientY: number): string[] {
    const rect = this.canvas.getBoundingClientRect();
    const toCanvasX = (value: number): number => (value - rect.left) * (this.canvas.width / Math.max(1, rect.width));
    const toCanvasY = (value: number): number => (value - rect.top) * (this.canvas.height / Math.max(1, rect.height));
    const left = Math.min(toCanvasX(startClientX), toCanvasX(endClientX));
    const right = Math.max(toCanvasX(startClientX), toCanvasX(endClientX));
    const top = Math.min(toCanvasY(startClientY), toCanvasY(endClientY));
    const bottom = Math.max(toCanvasY(startClientY), toCanvasY(endClientY));
    if (right - left < 4 || bottom - top < 4) return [];
    return this.#instances
      .filter((instance) => instance.visible)
      .filter((instance) => {
        const bounds = this.#projectedBounds(instance);
        return bounds.maxX >= left && bounds.minX <= right && bounds.maxY >= top && bounds.minY <= bottom;
      })
      .sort((a, b) => this.#projectedBounds(a).depth - this.#projectedBounds(b).depth)
      .map((instance) => instance.id);
  }

  resize(): void {
    if (this.#syncCanvasSize()) this.requestRender();
  }
  dispose(): void {
    cancelAnimationFrame(this.#raf);
    this.#resizeObserver.disconnect();
    for (const mesh of this.#gpu.values()) {
      this.gl.deleteBuffer(mesh.position);
      this.gl.deleteBuffer(mesh.normal);
    }
    this.#gpu.clear();
    this.#clearFlat(this.#plateMeshes);
    this.#clearFlat(this.#overlayMeshes);
  }
  requestRender(): void {
    if (this.#raf) return;
    this.#raf = requestAnimationFrame(() => {
      this.#raf = 0;
      this.#render();
    });
  }

  #syncCanvasSize(): boolean {
    const ratio = Math.min(devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.canvas.clientWidth * ratio));
    const height = Math.max(1, Math.floor(this.canvas.clientHeight * ratio));
    const changed = this.canvas.width !== width || this.canvas.height !== height;
    if (changed) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.gl.viewport(0, 0, width, height);
    return changed;
  }
  #shader(type: number, source: string): WebGLShader {
    const shader = this.gl.createShader(type);
    if (!shader) throw new Error("Shader konnte nicht erstellt werden");
    this.gl.shaderSource(shader, source);
    this.gl.compileShader(shader);
    if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
      throw new Error(this.gl.getShaderInfoLog(shader) || "Shaderfehler");
    }
    return shader;
  }
  #program(vertex: string, fragment: string): WebGLProgram {
    const program = this.gl.createProgram();
    if (!program) throw new Error("Programm konnte nicht erstellt werden");
    this.gl.attachShader(program, this.#shader(this.gl.VERTEX_SHADER, vertex));
    this.gl.attachShader(program, this.#shader(this.gl.FRAGMENT_SHADER, fragment));
    this.gl.linkProgram(program);
    if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) {
      throw new Error(this.gl.getProgramInfoLog(program) || "Linkfehler");
    }
    return program;
  }
  #flatMesh(values: readonly number[], mode: number, color: string): FlatMesh {
    const buffer = this.gl.createBuffer();
    if (!buffer) throw new Error("Puffer konnte nicht erstellt werden");
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, buffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array(values), this.gl.STATIC_DRAW);
    return { buffer, count: values.length / 3, mode, color };
  }
  #clearFlat(items: FlatMesh[]): void {
    for (const item of items) this.gl.deleteBuffer(item.buffer);
    items.length = 0;
  }
  #rebuildPlate(): void {
    this.#clearFlat(this.#plateMeshes);
    const width = this.#plate.widthMm;
    const depth = this.#plate.depthMm;
    const frame: number[] = [];
    const surface: number[] = [];
    const texture: number[] = [];
    const minor: number[] = [];
    const major: number[] = [];
    const border: number[] = [];
    const rim = 4;
    const tabWidth = Math.min(58, width * .28);
    const tabLeft = (width - tabWidth) / 2;
    const tabRight = tabLeft + tabWidth;

    quad(-rim,-rim,0,depth + rim,-.72,frame);
    quad(width,-rim,width + rim,depth + rim,-.72,frame);
    quad(0,-rim,width,0,-.72,frame);
    quad(0,depth,width,depth + rim,-.72,frame);
    quad(tabLeft,depth + rim,tabRight,depth + rim + 7,-.72,frame);
    quad(0,0,width,depth,-.56,surface);

    const textured = this.#plate.surface === "textured" || this.#plate.surface === "textured_cool";
    if (textured) {
      diagonalTexture(width, depth, 5, -.03, texture);
      diagonalTexture(width, depth, 5, -.025, texture);
    } else {
      for (let y = 16; y < depth; y += 32) line([0,y,-.02],[width,y,-.02],texture);
    }

    for (let x = 0; x <= width; x += 10) line([x,0,.02],[x,depth,.02],x % 50 === 0 ? major : minor);
    for (let y = 0; y <= depth; y += 10) line([0,y,.02],[width,y,.02],y % 50 === 0 ? major : minor);
    line([0,0,.05],[width,0,.05],border);
    line([width,0,.05],[width,depth,.05],border);
    line([width,depth,.05],[0,depth,.05],border);
    line([0,depth,.05],[0,0,.05],border);
    line([-rim,-rim,-.68],[width + rim,-rim,-.68],border);
    line([width + rim,-rim,-.68],[width + rim,depth + rim,-.68],border);
    line([width + rim,depth + rim,-.68],[tabRight,depth + rim,-.68],border);
    line([tabRight,depth + rim,-.68],[tabRight,depth + rim + 7,-.68],border);
    line([tabRight,depth + rim + 7,-.68],[tabLeft,depth + rim + 7,-.68],border);
    line([tabLeft,depth + rim + 7,-.68],[tabLeft,depth + rim,-.68],border);
    line([tabLeft,depth + rim,-.68],[-rim,depth + rim,-.68],border);
    line([-rim,depth + rim,-.68],[-rim,-rim,-.68],border);

    this.#plateMeshes.push(
      this.#flatMesh(frame, this.gl.TRIANGLES, shadeHex(this.#plate.baseColor, .68)),
      this.#flatMesh(surface, this.gl.TRIANGLES, this.#plate.baseColor),
      this.#flatMesh(texture, this.gl.LINES, shadeHex(this.#plate.minorGridColor, textured ? .74 : .58)),
      this.#flatMesh(minor, this.gl.LINES, this.#plate.minorGridColor),
      this.#flatMesh(major, this.gl.LINES, this.#plate.majorGridColor),
      this.#flatMesh(border, this.gl.LINES, this.#plate.accentColor),
    );
  }
  #rebuildOverlays(): void {
    this.#clearFlat(this.#overlayMeshes);
    for (const instance of this.#instances) {
      if (!this.#selected.has(instance.id)) continue;
      const points = worldCorners(instance);
      const edges = [[0,1],[0,2],[1,3],[2,3],[4,5],[4,6],[5,7],[6,7],[0,4],[1,5],[2,6],[3,7]] as const;
      const values: number[] = [];
      for (const [left, right] of edges) line(points[left]!, points[right]!, values);
      this.#overlayMeshes.push(this.#flatMesh(values, this.gl.LINES, "#ffb347"));
    }
    if (!this.#gizmoPosition) return;
    const [x, y, z] = this.#gizmoPosition;
    const size = 34;
    const axes: ReadonlyArray<readonly [MegaAxis, Vec3, string]> = [
      ["x", [x + size, y, z], "#ef5350"],
      ["y", [x, y + size, z], "#66bb6a"],
      ["z", [x, y, z + size], "#42a5f5"],
    ];
    for (const [axis, end, color] of axes) {
      const values: number[] = [];
      line([x, y, z], end, values);
      this.#overlayMeshes.push(this.#flatMesh(values, this.gl.LINES, axis === this.#activeAxis ? "#ffffff" : color));
    }
    if (this.#gizmoMode !== "rotate") return;
    for (const [axis, _end, color] of axes) {
      const values: number[] = [];
      for (let index = 0; index < 48; index += 1) {
        const a = index * Math.PI * 2 / 48;
        const b = (index + 1) * Math.PI * 2 / 48;
        const point = axis === "x"
          ? [x, y + Math.cos(a) * 20, z + Math.sin(a) * 20] as Vec3
          : axis === "y"
            ? [x + Math.cos(a) * 20, y, z + Math.sin(a) * 20] as Vec3
            : [x + Math.cos(a) * 20, y + Math.sin(a) * 20, z] as Vec3;
        const next = axis === "x"
          ? [x, y + Math.cos(b) * 20, z + Math.sin(b) * 20] as Vec3
          : axis === "y"
            ? [x + Math.cos(b) * 20, y, z + Math.sin(b) * 20] as Vec3
            : [x + Math.cos(b) * 20, y + Math.sin(b) * 20, z] as Vec3;
        line(point, next, values);
      }
      this.#overlayMeshes.push(this.#flatMesh(values, this.gl.LINES, axis === this.#activeAxis ? "#ffffff" : color));
    }
  }
  #ensureGpu(instance: MeshInstance): GpuMesh {
    const existing = this.#gpu.get(instance.id);
    if (existing) return existing;
    const position = this.gl.createBuffer();
    const normal = this.gl.createBuffer();
    if (!position || !normal) throw new Error("Modellpuffer konnte nicht erstellt werden");
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, position);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, instance.geometry.positions, this.gl.STATIC_DRAW);
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, normal);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, instance.geometry.normals, this.gl.STATIC_DRAW);
    const mesh = { position, normal, count: instance.geometry.positions.length / 3 };
    this.#gpu.set(instance.id, mesh);
    return mesh;
  }
  #cameraEye(): Vec3 {
    const cosine = Math.cos(this.#elevation);
    return add(this.#target, [
      this.#distance * cosine * Math.cos(this.#azimuth),
      this.#distance * cosine * Math.sin(this.#azimuth),
      this.#distance * Math.sin(this.#elevation),
    ]);
  }
  #viewProjection(): Float32Array {
    const eye = this.#cameraEye();
    const up: Vec3 = this.#elevation < -85 * DEG ? [0, 1, 0] : [0, 0, 1];
    return multiply(
      perspective(45 * DEG, this.canvas.width / this.canvas.height, 1, 5000),
      lookAt(eye, this.#target, up),
    );
  }
  #drawFlat(item: FlatMesh, vp: Float32Array): void {
    const gl = this.gl;
    gl.useProgram(this.#flatProgram);
    const location = gl.getAttribLocation(this.#flatProgram, "a_position");
    gl.bindBuffer(gl.ARRAY_BUFFER, item.buffer);
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, 3, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.#flatProgram, "u_mvp"), false, vp);
    gl.uniform3fv(gl.getUniformLocation(this.#flatProgram, "u_color"), rgb(item.color));
    gl.drawArrays(item.mode, 0, item.count);
  }
  #render(): void {
    const gl = this.gl;
    this.#syncCanvasSize();
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.depthMask(true);
    gl.disable(gl.CULL_FACE);
    if (this.#previewMode) gl.clearColor(.045, .065, .082, 1);
    else gl.clearColor(.025, .04, .065, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const vp = this.#viewProjection();

    gl.enable(gl.POLYGON_OFFSET_FILL);
    gl.polygonOffset(1, 1);
    for (const item of this.#plateMeshes) {
      if (item.mode === gl.TRIANGLES) this.#drawFlat(item, vp);
    }
    gl.disable(gl.POLYGON_OFFSET_FILL);

    gl.depthMask(false);
    for (const item of this.#plateMeshes) {
      if (item.mode !== gl.TRIANGLES) this.#drawFlat(item, vp);
    }
    gl.depthMask(true);

    gl.useProgram(this.#meshProgram);
    const positionLocation = gl.getAttribLocation(this.#meshProgram, "a_position");
    const normalLocation = gl.getAttribLocation(this.#meshProgram, "a_normal");
    for (const instance of this.#instances) {
      if (!instance.visible) continue;
      const mesh = this.#ensureGpu(instance);
      const model = modelMatrix(instance);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.position);
      gl.enableVertexAttribArray(positionLocation);
      gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.normal);
      gl.enableVertexAttribArray(normalLocation);
      gl.vertexAttribPointer(normalLocation, 3, gl.FLOAT, false, 0, 0);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.#meshProgram, "u_model"), false, model);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.#meshProgram, "u_mvp"), false, multiply(vp, model));
      gl.uniform3fv(gl.getUniformLocation(this.#meshProgram, "u_color"), rgb(instance.color));
      gl.drawArrays(gl.TRIANGLES, 0, mesh.count);
    }
    for (const item of this.#overlayMeshes) this.#drawFlat(item, vp);
  }
  #bind(): void {
    this.canvas.addEventListener("contextmenu", (event) => event.preventDefault());
    this.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      this.#distance = Math.max(40, Math.min(2500, this.#distance * Math.exp(event.deltaY * .0012)));
      this.requestRender();
    }, { passive: false });
    this.canvas.addEventListener("pointerdown", (event) => {
      this.canvas.setPointerCapture(event.pointerId);
      this.#pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, button: event.button };
    });
    this.canvas.addEventListener("pointermove", (event) => {
      if (!this.#pointer || this.#pointer.id !== event.pointerId) return;
      const dx = event.clientX - this.#pointer.x;
      const dy = event.clientY - this.#pointer.y;
      this.#pointer.x = event.clientX;
      this.#pointer.y = event.clientY;
      if (this.#pointer.button === 2 || event.shiftKey) {
        const eye = this.#cameraEye();
        const forward = normalize(sub(this.#target, eye));
        const right = normalize(cross(forward, [0, 0, 1]));
        const up = normalize(cross(right, forward));
        const scale = this.#distance * .0016;
        this.#target = add(this.#target, add(mul(right, -dx * scale), mul(up, dy * scale)));
      } else if (this.#gizmoMode === "select") {
        this.#azimuth -= dx * .006;
        this.#elevation = Math.max(-88 * DEG, Math.min(88 * DEG, this.#elevation + dy * .006));
      }
      this.requestRender();
    });
    const finish = (event: PointerEvent): void => {
      if (this.#pointer?.id === event.pointerId) this.#pointer = null;
    };
    this.canvas.addEventListener("pointerup", finish);
    this.canvas.addEventListener("pointercancel", finish);
  }
}