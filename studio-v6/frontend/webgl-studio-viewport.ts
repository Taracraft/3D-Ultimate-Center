export type Vec3 = [number, number, number];

export type MeshGeometry = Readonly<{
  positions: Float32Array;
  normals: Float32Array;
  triangleCount: number;
  boundsMin: Vec3;
  boundsMax: Vec3;
}>;

export type MeshInstance = Readonly<{
  id: string;
  name: string;
  geometry: MeshGeometry;
  position: Vec3;
  rotation: Vec3;
  scale: Vec3;
  color: string;
  visible: boolean;
}>;

type GpuMesh = {
  positionBuffer: WebGLBuffer;
  normalBuffer: WebGLBuffer;
  vertexCount: number;
};

const DEG = Math.PI / 180;

function vec3(x = 0, y = 0, z = 0): Vec3 { return [x, y, z]; }
function add(a: Vec3, b: Vec3): Vec3 { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
function sub(a: Vec3, b: Vec3): Vec3 { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function mul(a: Vec3, s: number): Vec3 { return [a[0] * s, a[1] * s, a[2] * s]; }
function dot(a: Vec3, b: Vec3): number { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function cross(a: Vec3, b: Vec3): Vec3 { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function length(a: Vec3): number { return Math.hypot(a[0], a[1], a[2]); }
function normalize(a: Vec3): Vec3 { const l = length(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }

function identity(): Float32Array {
  return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
}

function multiply(a: Float32Array, b: Float32Array): Float32Array {
  const out = new Float32Array(16);
  for (let c = 0; c < 4; c++) {
    for (let r = 0; r < 4; r++) {
      out[c * 4 + r] =
        a[0 * 4 + r]! * b[c * 4 + 0]! +
        a[1 * 4 + r]! * b[c * 4 + 1]! +
        a[2 * 4 + r]! * b[c * 4 + 2]! +
        a[3 * 4 + r]! * b[c * 4 + 3]!;
    }
  }
  return out;
}

function translation(v: Vec3): Float32Array {
  const m = identity(); m[12] = v[0]; m[13] = v[1]; m[14] = v[2]; return m;
}
function scaling(v: Vec3): Float32Array {
  const m = identity(); m[0] = v[0]; m[5] = v[1]; m[10] = v[2]; return m;
}
function rotationX(r: number): Float32Array {
  const c = Math.cos(r), s = Math.sin(r); return new Float32Array([1,0,0,0, 0,c,s,0, 0,-s,c,0, 0,0,0,1]);
}
function rotationY(r: number): Float32Array {
  const c = Math.cos(r), s = Math.sin(r); return new Float32Array([c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]);
}
function rotationZ(r: number): Float32Array {
  const c = Math.cos(r), s = Math.sin(r); return new Float32Array([c,s,0,0, -s,c,0,0, 0,0,1,0, 0,0,0,1]);
}
function perspective(fovy: number, aspect: number, near: number, far: number): Float32Array {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
  return new Float32Array([f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,2*far*near*nf,0]);
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
  const t = translation(instance.position);
  const rx = rotationX(instance.rotation[0] * DEG);
  const ry = rotationY(instance.rotation[1] * DEG);
  const rz = rotationZ(instance.rotation[2] * DEG);
  const s = scaling(instance.scale);
  return multiply(t, multiply(rz, multiply(ry, multiply(rx, s))));
}

function parseColor(value: string): Vec3 {
  const hex = value.replace("#", "").padEnd(6, "0").slice(0, 6);
  return [parseInt(hex.slice(0,2),16)/255, parseInt(hex.slice(2,4),16)/255, parseInt(hex.slice(4,6),16)/255];
}

function boundsFromPositions(positions: Float32Array): { min: Vec3; max: Vec3 } {
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < positions.length; i += 3) {
    min[0] = Math.min(min[0], positions[i]!); min[1] = Math.min(min[1], positions[i+1]!); min[2] = Math.min(min[2], positions[i+2]!);
    max[0] = Math.max(max[0], positions[i]!); max[1] = Math.max(max[1], positions[i+1]!); max[2] = Math.max(max[2], positions[i+2]!);
  }
  return { min, max };
}

function normalsForPositions(positions: Float32Array): Float32Array {
  const normals = new Float32Array(positions.length);
  for (let i = 0; i < positions.length; i += 9) {
    const a: Vec3 = [positions[i]!, positions[i+1]!, positions[i+2]!];
    const b: Vec3 = [positions[i+3]!, positions[i+4]!, positions[i+5]!];
    const c: Vec3 = [positions[i+6]!, positions[i+7]!, positions[i+8]!];
    const n = normalize(cross(sub(b, a), sub(c, a)));
    for (let v = 0; v < 3; v++) {
      normals[i + v*3] = n[0]; normals[i + v*3 + 1] = n[1]; normals[i + v*3 + 2] = n[2];
    }
  }
  return normals;
}

export function parseStl(buffer: ArrayBuffer): MeshGeometry {
  const bytes = new Uint8Array(buffer);
  const header = new TextDecoder("utf-8", { fatal: false }).decode(bytes.slice(0, Math.min(256, bytes.length))).trimStart();
  const view = new DataView(buffer);
  const binaryTriangleCount = buffer.byteLength >= 84 ? view.getUint32(80, true) : 0;
  const binarySize = 84 + binaryTriangleCount * 50;
  const likelyAscii = header.startsWith("solid") && binarySize !== buffer.byteLength;

  let positions: Float32Array;
  let normals: Float32Array;

  if (!likelyAscii && binaryTriangleCount > 0 && binarySize <= buffer.byteLength) {
    positions = new Float32Array(binaryTriangleCount * 9);
    normals = new Float32Array(binaryTriangleCount * 9);
    let offset = 84;
    for (let triangle = 0; triangle < binaryTriangleCount; triangle++) {
      const nx = view.getFloat32(offset, true), ny = view.getFloat32(offset + 4, true), nz = view.getFloat32(offset + 8, true);
      offset += 12;
      for (let vertex = 0; vertex < 3; vertex++) {
        const target = triangle * 9 + vertex * 3;
        positions[target] = view.getFloat32(offset, true);
        positions[target + 1] = view.getFloat32(offset + 4, true);
        positions[target + 2] = view.getFloat32(offset + 8, true);
        normals[target] = nx; normals[target + 1] = ny; normals[target + 2] = nz;
        offset += 12;
      }
      offset += 2;
    }
  } else {
    const text = new TextDecoder().decode(buffer);
    const vertexMatches = [...text.matchAll(/vertex\s+([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)/g)];
    if (vertexMatches.length < 3 || vertexMatches.length % 3 !== 0) throw new Error("Invalid ASCII STL: vertex count is not divisible by three");
    positions = new Float32Array(vertexMatches.length * 3);
    vertexMatches.forEach((match, index) => {
      positions[index*3] = Number(match[1]); positions[index*3+1] = Number(match[2]); positions[index*3+2] = Number(match[3]);
    });
    normals = normalsForPositions(positions);
  }

  const bounds = boundsFromPositions(positions);
  return Object.freeze({ positions, normals, triangleCount: positions.length / 9, boundsMin: bounds.min, boundsMax: bounds.max });
}

export class WebGlStudioViewport {
  readonly canvas: HTMLCanvasElement;
  readonly gl: WebGLRenderingContext;
  readonly #program: WebGLProgram;
  readonly #gpu = new Map<string, GpuMesh>();
  #instances: readonly MeshInstance[] = [];
  #selected = new Set<string>();
  #raf = 0;
  #azimuth = 45 * DEG;
  #elevation = 42 * DEG;
  #distance = 520;
  #target: Vec3 = [128, 128, 0];
  #pointer: { id: number; x: number; y: number; button: number } | null = null;
  #plateSize: Vec3 = [256, 256, 0.8];

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl", { antialias: true, alpha: false, depth: true });
    if (!gl) throw new Error("WebGL is not available");
    this.gl = gl;
    this.#program = this.#createProgram();
    this.#bindEvents();
    this.resize();
    this.requestRender();
  }

  setPlateSize(width: number, depth: number): void {
    this.#plateSize = [width, depth, 0.8];
    this.#target = [width / 2, depth / 2, 0];
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
    this.#target = [this.#plateSize[0] / 2, this.#plateSize[1] / 2, 0];
    this.#distance = Math.max(this.#plateSize[0], this.#plateSize[1]) * 2.0;
    this.requestRender();
  }

  resize(): void {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.canvas.clientWidth * dpr));
    const height = Math.max(1, Math.floor(this.canvas.clientHeight * dpr));
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width; this.canvas.height = height;
    }
    this.gl.viewport(0, 0, width, height);
    this.requestRender();
  }

  dispose(): void {
    cancelAnimationFrame(this.#raf);
    for (const mesh of this.#gpu.values()) {
      this.gl.deleteBuffer(mesh.positionBuffer); this.gl.deleteBuffer(mesh.normalBuffer);
    }
    this.#gpu.clear();
  }

  requestRender(): void {
    if (this.#raf) return;
    this.#raf = requestAnimationFrame(() => { this.#raf = 0; this.#render(); });
  }

  #createShader(type: number, source: string): WebGLShader {
    const shader = this.gl.createShader(type);
    if (!shader) throw new Error("Cannot create WebGL shader");
    this.gl.shaderSource(shader, source); this.gl.compileShader(shader);
    if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) throw new Error(this.gl.getShaderInfoLog(shader) || "Shader compile failed");
    return shader;
  }

  #createProgram(): WebGLProgram {
    const vertex = this.#createShader(this.gl.VERTEX_SHADER, `
      attribute vec3 a_position; attribute vec3 a_normal;
      uniform mat4 u_mvp; uniform mat4 u_model;
      varying vec3 v_normal; varying vec3 v_world;
      void main(){ vec4 world=u_model*vec4(a_position,1.0); v_world=world.xyz; v_normal=mat3(u_model)*a_normal; gl_Position=u_mvp*vec4(a_position,1.0); }
    `);
    const fragment = this.#createShader(this.gl.FRAGMENT_SHADER, `
      precision mediump float;
      uniform vec3 u_color; uniform float u_selected;
      varying vec3 v_normal; varying vec3 v_world;
      void main(){
        vec3 n=normalize(v_normal); vec3 light=normalize(vec3(0.35,-0.45,0.82));
        float diffuse=max(dot(n,light),0.0); float rim=pow(1.0-max(abs(n.z),0.0),2.0);
        vec3 base=mix(u_color,vec3(1.0,0.56,0.14),u_selected*0.42);
        vec3 color=base*(0.24+0.76*diffuse)+rim*0.12;
        gl_FragColor=vec4(color,1.0);
      }
    `);
    const program = this.gl.createProgram();
    if (!program) throw new Error("Cannot create WebGL program");
    this.gl.attachShader(program, vertex); this.gl.attachShader(program, fragment); this.gl.linkProgram(program);
    if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) throw new Error(this.gl.getProgramInfoLog(program) || "Program link failed");
    return program;
  }

  #ensureGpu(instance: MeshInstance): GpuMesh {
    const existing = this.#gpu.get(instance.id);
    if (existing) return existing;
    const positionBuffer = this.gl.createBuffer(), normalBuffer = this.gl.createBuffer();
    if (!positionBuffer || !normalBuffer) throw new Error("Cannot create WebGL buffers");
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, positionBuffer); this.gl.bufferData(this.gl.ARRAY_BUFFER, instance.geometry.positions, this.gl.STATIC_DRAW);
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, normalBuffer); this.gl.bufferData(this.gl.ARRAY_BUFFER, instance.geometry.normals, this.gl.STATIC_DRAW);
    const mesh = { positionBuffer, normalBuffer, vertexCount: instance.geometry.positions.length / 3 };
    this.#gpu.set(instance.id, mesh); return mesh;
  }

  #cameraEye(): Vec3 {
    const cosElevation = Math.cos(this.#elevation);
    return add(this.#target, [this.#distance * cosElevation * Math.cos(this.#azimuth), this.#distance * cosElevation * Math.sin(this.#azimuth), this.#distance * Math.sin(this.#elevation)]);
  }

  #render(): void {
    const gl = this.gl;
    this.resize();
    gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK);
    gl.clearColor(0.025, 0.04, 0.065, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.useProgram(this.#program);

    const eye = this.#cameraEye();
    const view = lookAt(eye, this.#target, [0,0,1]);
    const projection = perspective(45 * DEG, this.canvas.width / this.canvas.height, 0.1, 5000);
    const vp = multiply(projection, view);

    const positionLocation = gl.getAttribLocation(this.#program, "a_position");
    const normalLocation = gl.getAttribLocation(this.#program, "a_normal");
    const modelLocation = gl.getUniformLocation(this.#program, "u_model");
    const mvpLocation = gl.getUniformLocation(this.#program, "u_mvp");
    const colorLocation = gl.getUniformLocation(this.#program, "u_color");
    const selectedLocation = gl.getUniformLocation(this.#program, "u_selected");

    for (const instance of this.#instances) {
      if (!instance.visible) continue;
      const mesh = this.#ensureGpu(instance);
      const model = modelMatrix(instance), mvp = multiply(vp, model);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.positionBuffer); gl.enableVertexAttribArray(positionLocation); gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, mesh.normalBuffer); gl.enableVertexAttribArray(normalLocation); gl.vertexAttribPointer(normalLocation, 3, gl.FLOAT, false, 0, 0);
      gl.uniformMatrix4fv(modelLocation, false, model); gl.uniformMatrix4fv(mvpLocation, false, mvp);
      gl.uniform3fv(colorLocation, parseColor(instance.color)); gl.uniform1f(selectedLocation, this.#selected.has(instance.id) ? 1 : 0);
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
      const dx = event.clientX - this.#pointer.x, dy = event.clientY - this.#pointer.y;
      this.#pointer.x = event.clientX; this.#pointer.y = event.clientY;
      if (this.#pointer.button === 2 || event.shiftKey) {
        const eye = this.#cameraEye();
        const forward = normalize(sub(this.#target, eye));
        const right = normalize(cross(forward, [0,0,1]));
        const up = normalize(cross(right, forward));
        const scale = this.#distance * 0.0016;
        this.#target = add(this.#target, add(mul(right, -dx * scale), mul(up, dy * scale)));
      } else {
        this.#azimuth -= dx * 0.006;
        this.#elevation = Math.max(5 * DEG, Math.min(88 * DEG, this.#elevation + dy * 0.006));
      }
      this.requestRender();
    });
    const end = (event: PointerEvent) => { if (this.#pointer?.id === event.pointerId) this.#pointer = null; };
    canvas.addEventListener("pointerup", end); canvas.addEventListener("pointercancel", end);
    new ResizeObserver(() => this.resize()).observe(canvas);
  }
}
