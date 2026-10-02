import type { StudioBuildPlateVisual } from "./studio-build-plates.js";
import type { MeshInstance, Vec3 } from "./webgl-studio-viewport.js";

type GpuMesh = {
  positionBuffer: WebGLBuffer;
  normalBuffer: WebGLBuffer;
  vertexCount: number;
};

type FlatGeometry = {
  buffer: WebGLBuffer;
  vertexCount: number;
  mode: number;
};

const DEG = Math.PI / 180;

function add(a: Vec3, b: Vec3): Vec3 { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
function sub(a: Vec3, b: Vec3): Vec3 { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function mul(a: Vec3, value: number): Vec3 { return [a[0] * value, a[1] * value, a[2] * value]; }
function dot(a: Vec3, b: Vec3): number { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function cross(a: Vec3, b: Vec3): Vec3 { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function normalize(a: Vec3): Vec3 {
  const length = Math.hypot(a[0], a[1], a[2]) || 1;
  return [a[0] / length, a[1] / length, a[2] / length];
}

function identity(): Float32Array {
  return new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
}

function multiply(a: Float32Array, b: Float32Array): Float32Array {
  const output = new Float32Array(16);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      output[column * 4 + row] =
        a[row]! * b[column * 4]!
        + a[4 + row]! * b[column * 4 + 1]!
        + a[8 + row]! * b[column * 4 + 2]!
        + a[12 + row]! * b[column * 4 + 3]!;
    }
  }
  return output;
}

function translation(value: Vec3): Float32Array {
  const matrix = identity();
  matrix[12] = value[0];
  matrix[13] = value[1];
  matrix[14] = value[2];
  return matrix;
}

function scaling(value: Vec3): Float32Array {
  const matrix = identity();
  matrix[0] = value[0];
  matrix[5] = value[1];
  matrix[10] = value[2];
  return matrix;
}

function rotationX(radians: number): Float32Array {
  const c = Math.cos(radians), s = Math.sin(radians);
  return new Float32Array([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1]);
}

function rotationY(radians: number): Float32Array {
  const c = Math.cos(radians), s = Math.sin(radians);
  return new Float32Array([c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1]);
}

function rotationZ(radians: number): Float32Array {
  const c = Math.cos(radians), s = Math.sin(radians);
  return new Float32Array([c, s, 0, 0, -s, c, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
}

function perspective(fovy: number, aspect: number, near: number, far: number): Float32Array {
  const f = 1 / Math.tan(fovy / 2);
  const nf = 1 / (near - far);
  return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0]);
}

function lookAt(eye: Vec3, target: Vec3, up: Vec3): Float32Array {
  const z = normalize(sub(eye, target));
  const x = normalize(cross(up, z));
  const y = cross(z, x);
  return new Float32Array([
    x[0], y[0], z[0], 0,
    x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0,
    -dot(x, eye), -dot(y, eye), -dot(z, eye), 1,
  ]);
}

function modelMatrix(instance: MeshInstance): Float32Array {
  return multiply(
    translation(instance.position),
    multiply(
      rotationZ(instance.rotation[2] * DEG),
      multiply(
        rotationY(instance.rotation[1] * DEG),
        multiply(rotationX(instance.rotation[0] * DEG), scaling(instance.scale)),
      ),
    ),
  );
}

function color(value: string): Float32Array {
  const hex = value.replace("#", "").padEnd(6, "0").slice(0, 6);
  return new Float32Array([
    Number.parseInt(hex.slice(0, 2), 16) / 255,
    Number.parseInt(hex.slice(2, 4), 16) / 255,
    Number.parseInt(hex.slice(4, 6), 16) / 255,
  ]);
}

function line(a: Vec3, b: Vec3, target: number[]): void {
  target.push(...a, ...b);
}

export class StudioPlateViewport {
  readonly canvas: HTMLCanvasElement;
  readonly gl: WebGLRenderingContext;
  readonly #meshProgram: WebGLProgram;
  readonly #flatProgram: WebGLProgram;
  readonly #gpu = new Map<string, GpuMesh>();
  #instances: readonly MeshInstance[] = [];
  #selected = new Set<string>();
  #plate: StudioBuildPlateVisual;
  #plateFill: FlatGeometry | null = null;
  #minorGrid: FlatGeometry | null = null;
  #majorGrid: FlatGeometry | null = null;
  #border: FlatGeometry | null = null;
  #axisX: FlatGeometry | null = null;
  #axisY: FlatGeometry | null = null;
  #axisZ: FlatGeometry | null = null;
  #raf = 0;
  #azimuth = 45 * DEG;
  #elevation = 42 * DEG;
  #distance = 520;
  #target: Vec3 = [128, 128, 0];
  #pointer: { id: number; x: number; y: number; button: number } | null = null;

  constructor(canvas: HTMLCanvasElement, plate: StudioBuildPlateVisual) {
    this.canvas = canvas;
    this.#plate = plate;
    const gl = canvas.getContext("webgl", { antialias: true, alpha: false, depth: true });
    if (!gl) throw new Error("WebGL ist nicht verfügbar");
    this.gl = gl;
    this.#meshProgram = this.#createMeshProgram();
    this.#flatProgram = this.#createFlatProgram();
    this.#rebuildPlate();
    this.#bindEvents();
    this.resize();
    this.requestRender();
  }

  setPlate(plate: StudioBuildPlateVisual): void {
    this.#plate = plate;
    this.#target = [plate.widthMm / 2, plate.depthMm / 2, 0];
    this.#distance = Math.max(plate.widthMm, plate.depthMm) * 2;
    this.#rebuildPlate();
    this.requestRender();
  }

  setInstances(instances: readonly MeshInstance[]): void {
    this.#instances = instances;
    for (const instance of instances) this.#ensureGpu(instance);
    this.requestRender();
  }

  setSelected(ids: readonly string[]): void {
    this.#selected = new Set(ids);
    this.requestRender();
  }

  frameAll(): void {
    this.#target = [this.#plate.widthMm / 2, this.#plate.depthMm / 2, 0];
    this.#distance = Math.max(this.#plate.widthMm, this.#plate.depthMm) * 2;
    this.requestRender();
  }

  resize(): void {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.canvas.clientWidth * ratio));
    const height = Math.max(1, Math.floor(this.canvas.clientHeight * ratio));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.gl.viewport(0, 0, width, height);
    this.requestRender();
  }

  dispose(): void {
    cancelAnimationFrame(this.#raf);
    for (const mesh of this.#gpu.values()) {
      this.gl.deleteBuffer(mesh.positionBuffer);
      this.gl.deleteBuffer(mesh.normalBuffer);
    }
    this.#gpu.clear();
    this.#deletePlateBuffers();
  }

  requestRender(): void {
    if (this.#raf) return;
    this.#raf = requestAnimationFrame(() => {
      this.#raf = 0;
      this.#render();
    });
  }

  #createShader(type: number, source: string): WebGLShader {
    const shader = this.gl.createShader(type);
    if (!shader) throw new Error("WebGL-Shader konnte nicht erstellt werden");
    this.gl.shaderSource(shader, source);
    this.gl.compileShader(shader);
    if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
      throw new Error(this.gl.getShaderInfoLog(shader) || "WebGL-Shaderfehler");
    }
    return shader;
  }

  #createProgram(vertexSource: string, fragmentSource: string): WebGLProgram {
    const program = this.gl.createProgram();
    if (!program) throw new Error("WebGL-Programm konnte nicht erstellt werden");
    this.gl.attachShader(program, this.#createShader(this.gl.VERTEX_SHADER, vertexSource));
    this.gl.attachShader(program, this.#createShader(this.gl.FRAGMENT_SHADER, fragmentSource));
    this.gl.linkProgram(program);
    if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) {
      throw new Error(this.gl.getProgramInfoLog(program) || "WebGL-Linkfehler");
    }
    return program;
  }

  #createMeshProgram(): WebGLProgram {
    return this.#createProgram(`
      attribute vec3 a_position;
      attribute vec3 a_normal;
      uniform mat4 u_mvp;
      uniform mat4 u_model;
      varying vec3 v_normal;
      void main(){
        v_normal=mat3(u_model)*a_normal;
        gl_Position=u_mvp*vec4(a_position,1.0);
      }
    `, `
      precision mediump float;
      uniform vec3 u_color;
      uniform float u_selected;
      varying vec3 v_normal;
      void main(){
        vec3 n=normalize(v_normal);
        vec3 light=normalize(vec3(0.35,-0.45,0.82));
        float diffuse=max(dot(n,light),0.0);
        float rim=pow(1.0-max(abs(n.z),0.0),2.0);
        vec3 base=mix(u_color,vec3(1.0,0.56,0.14),u_selected*0.42);
        gl_FragColor=vec4(base*(0.24+0.76*diffuse)+rim*0.12,1.0);
      }
    `);
  }

  #createFlatProgram(): WebGLProgram {
    return this.#createProgram(`
      attribute vec3 a_position;
      uniform mat4 u_mvp;
      void main(){gl_Position=u_mvp*vec4(a_position,1.0);}
    `, `
      precision mediump float;
      uniform vec3 u_color;
      void main(){gl_FragColor=vec4(u_color,1.0);}
    `);
  }

  #createFlatGeometry(values: readonly number[], mode: number): FlatGeometry {
    const buffer = this.gl.createBuffer();
    if (!buffer) throw new Error("WebGL-Plattenpuffer konnte nicht erstellt werden");
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, buffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array(values), this.gl.STATIC_DRAW);
    return { buffer, vertexCount: values.length / 3, mode };
  }

  #deletePlateBuffers(): void {
    for (const geometry of [this.#plateFill, this.#minorGrid, this.#majorGrid, this.#border, this.#axisX, this.#axisY, this.#axisZ]) {
      if (geometry) this.gl.deleteBuffer(geometry.buffer);
    }
    this.#plateFill = null;
    this.#minorGrid = null;
    this.#majorGrid = null;
    this.#border = null;
    this.#axisX = null;
    this.#axisY = null;
    this.#axisZ = null;
  }

  #rebuildPlate(): void {
    this.#deletePlateBuffers();
    const width = this.#plate.widthMm;
    const depth = this.#plate.depthMm;
    const fill = [
      0, 0, -0.18, width, 0, -0.18, width, depth, -0.18,
      0, 0, -0.18, width, depth, -0.18, 0, depth, -0.18,
    ];
    const minor: number[] = [];
    const major: number[] = [];
    for (let x = 0; x <= width; x += 10) {
      line([x, 0, -0.06], [x, depth, -0.06], x % 50 === 0 ? major : minor);
    }
    for (let y = 0; y <= depth; y += 10) {
      line([0, y, -0.06], [width, y, -0.06], y % 50 === 0 ? major : minor);
    }
    const border: number[] = [];
    line([0, 0, 0], [width, 0, 0], border);
    line([width, 0, 0], [width, depth, 0], border);
    line([width, depth, 0], [0, depth, 0], border);
    line([0, depth, 0], [0, 0, 0], border);
    const axisX: number[] = [];
    line([0, 0, 0.6], [38, 0, 0.6], axisX);
    line([38, 0, 0.6], [31, -4, 0.6], axisX);
    line([38, 0, 0.6], [31, 4, 0.6], axisX);
    const axisY: number[] = [];
    line([0, 0, 0.7], [0, 38, 0.7], axisY);
    line([0, 38, 0.7], [-4, 31, 0.7], axisY);
    line([0, 38, 0.7], [4, 31, 0.7], axisY);
    const axisZ: number[] = [];
    line([0, 0, 0.8], [0, 0, 38], axisZ);
    line([0, 0, 38], [-3, 0, 31], axisZ);
    line([0, 0, 38], [3, 0, 31], axisZ);
    this.#plateFill = this.#createFlatGeometry(fill, this.gl.TRIANGLES);
    this.#minorGrid = this.#createFlatGeometry(minor, this.gl.LINES);
    this.#majorGrid = this.#createFlatGeometry(major, this.gl.LINES);
    this.#border = this.#createFlatGeometry(border, this.gl.LINES);
    this.#axisX = this.#createFlatGeometry(axisX, this.gl.LINES);
    this.#axisY = this.#createFlatGeometry(axisY, this.gl.LINES);
    this.#axisZ = this.#createFlatGeometry(axisZ, this.gl.LINES);
  }

  #ensureGpu(instance: MeshInstance): GpuMesh {
    const existing = this.#gpu.get(instance.id);
    if (existing) return existing;
    const positionBuffer = this.gl.createBuffer();
    const normalBuffer = this.gl.createBuffer();
    if (!positionBuffer || !normalBuffer) throw new Error("WebGL-Modellpuffer konnte nicht erstellt werden");
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, positionBuffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, instance.geometry.positions, this.gl.STATIC_DRAW);
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, normalBuffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, instance.geometry.normals, this.gl.STATIC_DRAW);
    const mesh = { positionBuffer, normalBuffer, vertexCount: instance.geometry.positions.length / 3 };
    this.#gpu.set(instance.id, mesh);
    return mesh;
  }

  #cameraEye(): Vec3 {
    const cosElevation = Math.cos(this.#elevation);
    return add(this.#target, [
      this.#distance * cosElevation * Math.cos(this.#azimuth),
      this.#distance * cosElevation * Math.sin(this.#azimuth),
      this.#distance * Math.sin(this.#elevation),
    ]);
  }

  #viewProjection(): Float32Array {
    const view = lookAt(this.#cameraEye(), this.#target, [0, 0, 1]);
    const projection = perspective(45 * DEG, this.canvas.width / this.canvas.height, 0.1, 5000);
    return multiply(projection, view);
  }

  #drawFlat(geometry: FlatGeometry | null, rgb: string, viewProjection: Float32Array): void {
    if (!geometry) return;
    const gl = this.gl;
    gl.useProgram(this.#flatProgram);
    const positionLocation = gl.getAttribLocation(this.#flatProgram, "a_position");
    gl.bindBuffer(gl.ARRAY_BUFFER, geometry.buffer);
    gl.enableVertexAttribArray(positionLocation);
    gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.#flatProgram, "u_mvp"), false, viewProjection);
    gl.uniform3fv(gl.getUniformLocation(this.#flatProgram, "u_color"), color(rgb));
    gl.drawArrays(geometry.mode, 0, geometry.vertexCount);
  }

  #render(): void {
    const gl = this.gl;
    this.resize();
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
    gl.clearColor(0.025, 0.04, 0.065, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const viewProjection = this.#viewProjection();
    this.#drawFlat(this.#plateFill, this.#plate.baseColor, viewProjection);
    this.#drawFlat(this.#minorGrid, this.#plate.minorGridColor, viewProjection);
    this.#drawFlat(this.#majorGrid, this.#plate.majorGridColor, viewProjection);
    this.#drawFlat(this.#border, this.#plate.accentColor, viewProjection);
    this.#drawFlat(this.#axisX, "#ef5350", viewProjection);
    this.#drawFlat(this.#axisY, "#66bb6a", viewProjection);
    this.#drawFlat(this.#axisZ, "#42a5f5", viewProjection);

    gl.enable(gl.CULL_FACE);
    gl.cullFace(gl.BACK);
    gl.useProgram(this.#meshProgram);
    const positionLocation = gl.getAttribLocation(this.#meshProgram, "a_position");
    const normalLocation = gl.getAttribLocation(this.#meshProgram, "a_normal");
    const modelLocation = gl.getUniformLocation(this.#meshProgram, "u_model");
    const mvpLocation = gl.getUniformLocation(this.#meshProgram, "u_mvp");
    const colorLocation = gl.getUniformLocation(this.#meshProgram, "u_color");
    const selectedLocation = gl.getUniformLocation(this.#meshProgram, "u_selected");
    for (const instance of this.#instances) {
      if (!instance.visible) continue;
      const mesh = this.#ensureGpu(instance);
      const model = modelMatrix(instance);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.positionBuffer);
      gl.enableVertexAttribArray(positionLocation);
      gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.normalBuffer);
      gl.enableVertexAttribArray(normalLocation);
      gl.vertexAttribPointer(normalLocation, 3, gl.FLOAT, false, 0, 0);
      gl.uniformMatrix4fv(modelLocation, false, model);
      gl.uniformMatrix4fv(mvpLocation, false, multiply(viewProjection, model));
      gl.uniform3fv(colorLocation, color(instance.color));
      gl.uniform1f(selectedLocation, this.#selected.has(instance.id) ? 1 : 0);
      gl.drawArrays(gl.TRIANGLES, 0, mesh.vertexCount);
    }
  }

  #bindEvents(): void {
    const canvas = this.canvas;
    canvas.addEventListener("contextmenu", (event) => event.preventDefault());
    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      this.#distance = Math.max(40, Math.min(2500, this.#distance * Math.exp(event.deltaY * 0.0012)));
      this.requestRender();
    }, { passive: false });
    canvas.addEventListener("pointerdown", (event) => {
      canvas.setPointerCapture(event.pointerId);
      this.#pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, button: event.button };
    });
    canvas.addEventListener("pointermove", (event) => {
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
        const scale = this.#distance * 0.0016;
        this.#target = add(this.#target, add(mul(right, -dx * scale), mul(up, dy * scale)));
      } else {
        this.#azimuth -= dx * 0.006;
        this.#elevation = Math.max(5 * DEG, Math.min(88 * DEG, this.#elevation + dy * 0.006));
      }
      this.requestRender();
    });
    const finish = (event: PointerEvent): void => {
      if (this.#pointer?.id === event.pointerId) this.#pointer = null;
    };
    canvas.addEventListener("pointerup", finish);
    canvas.addEventListener("pointercancel", finish);
    new ResizeObserver(() => this.resize()).observe(canvas);
  }
}
