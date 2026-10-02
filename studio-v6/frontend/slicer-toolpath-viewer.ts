import { authenticatedFetch, errorMessage } from "./ha-api-transport.js";

const API_PREFIX = "/api/ultimate_3d_studio_v6/v1/slicer";
const FALLBACK_COLORS = ["#50DB6C", "#F15B5B", "#58A6FF", "#FFB84D", "#B67CFF", "#28D7C0", "#F472B6", "#E6E65C", "#B0BEC5", "#FFFFFF", "#FF7A18", "#79FF7A"];
const FEATURE_COLORS: Readonly<Record<string, string>> = {
  support: "#45E087",
  brim: "#FFD24D",
  raft: "#D873FF",
  skirt: "#FF9B42",
  purge_tower: "#FF5F56",
  outer_wall: "#56E389",
  inner_wall: "#63B3FF",
  infill: "#4C7DFF",
  surface: "#F7D154",
  bridge: "#C792EA",
  model: "#C7D3DF",
};
const DEG = Math.PI / 180;

type Bounds = Readonly<{ min_x: number; min_y: number; min_z: number; max_x: number; max_y: number; max_z: number }>;
type LayerMeta = Readonly<{ index: number; z: number; segment_count: number; extrusion_mm: number; features?: string[] }>;
type ToolpathSegment = readonly [number, number, number, number, number, number, number, string?, string?];
type ToolpathLayer = Readonly<{ index: number; z: number; segments: ToolpathSegment[]; extrusion_mm: number; features?: string[] }>;
type ToolpathSummary = Readonly<{
  layer_count: number;
  layers: LayerMeta[];
  tools: number[];
  filament_colors?: string[];
  filament_names?: string[];
  feature_first_layers?: Readonly<Record<string, number>>;
  bounds?: Bounds;
  chunk?: Readonly<{ start_layer: number; end_layer: number; layers: ToolpathLayer[]; segment_count: number }>;
}>;
type Vec3 = [number, number, number];
type ColorMode = "material" | "feature";

async function fetchToolpath(jobId: string, start?: number, end?: number): Promise<ToolpathSummary> {
  const query = new URLSearchParams();
  if (start !== undefined) query.set("start", String(start));
  if (end !== undefined) query.set("end", String(end));
  const suffix = query.size ? `?${query}` : "";
  const response = await authenticatedFetch(`${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/toolpath${suffix}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let message = `Toolpath HTTP ${response.status}`;
    try { message = errorMessage(await response.json(), message); } catch {}
    throw new Error(message);
  }
  return (await response.json() as { data: ToolpathSummary }).data;
}

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function validColor(value: unknown, fallback: string): string {
  const raw = String(value || "").trim().toUpperCase();
  if (/^#[0-9A-F]{8}$/.test(raw)) return raw.slice(0, 7);
  return /^#[0-9A-F]{6}$/.test(raw) ? raw : fallback;
}

function hexColor(value: string, factor = 1): [number, number, number] {
  const hex = validColor(value, "#FFFFFF").slice(1);
  return [
    Math.min(1, Number.parseInt(hex.slice(0, 2), 16) / 255 * factor),
    Math.min(1, Number.parseInt(hex.slice(2, 4), 16) / 255 * factor),
    Math.min(1, Number.parseInt(hex.slice(4, 6), 16) / 255 * factor),
  ];
}

function featureCategory(segment: ToolpathSegment): string {
  if (segment[8]) return segment[8];
  const feature = String(segment[7] || "").toLowerCase();
  if (feature.includes("support")) return "support";
  if (feature.includes("brim")) return "brim";
  if (feature.includes("raft")) return "raft";
  if (feature.includes("skirt")) return "skirt";
  if (feature.includes("tower")) return "purge_tower";
  return "model";
}

function featureStyleKey(segment: ToolpathSegment): string {
  const category = featureCategory(segment);
  if (category !== "model") return category;
  const feature = String(segment[7] || "").toLowerCase();
  if (feature.includes("outer wall")) return "outer_wall";
  if (feature.includes("inner wall")) return "inner_wall";
  if (feature.includes("infill")) return "infill";
  if (feature.includes("surface") || feature.includes("bottom")) return "surface";
  if (feature.includes("bridge")) return "bridge";
  return "model";
}

function featureLabel(key: string): string {
  return ({
    support: "Supportstruktur",
    brim: "Brim",
    raft: "Raft",
    skirt: "Skirt",
    purge_tower: "Reinigungsturm",
    outer_wall: "Außenwand",
    inner_wall: "Innenwand",
    infill: "Füllung",
    surface: "Ober-/Unterfläche",
    bridge: "Brücke",
    model: "Modellpfad",
  } as Readonly<Record<string, string>>)[key] || key;
}

function materialColor(summary: ToolpathSummary | null, tool: number): string {
  return validColor(summary?.filament_colors?.[tool], FALLBACK_COLORS[tool % FALLBACK_COLORS.length] || "#50DB6C");
}

function identity(): Float32Array { return new Float32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]); }
function multiply(a: Float32Array, b: Float32Array): Float32Array {
  const out = new Float32Array(16);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      out[column * 4 + row] = a[row]! * b[column * 4]! + a[4 + row]! * b[column * 4 + 1]! + a[8 + row]! * b[column * 4 + 2]! + a[12 + row]! * b[column * 4 + 3]!;
    }
  }
  return out;
}
function perspective(fovy: number, aspect: number, near: number, far: number): Float32Array {
  const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
  return new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0]);
}
function normalize(vector: Vec3): Vec3 { const length = Math.hypot(...vector) || 1; return [vector[0] / length, vector[1] / length, vector[2] / length]; }
function sub(left: Vec3, right: Vec3): Vec3 { return [left[0] - right[0], left[1] - right[1], left[2] - right[2]]; }
function cross(left: Vec3, right: Vec3): Vec3 { return [left[1] * right[2] - left[2] * right[1], left[2] * right[0] - left[0] * right[2], left[0] * right[1] - left[1] * right[0]]; }
function dot(left: Vec3, right: Vec3): number { return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]; }
function lookAt(eye: Vec3, target: Vec3, up: Vec3): Float32Array {
  const z = normalize(sub(eye, target)), x = normalize(cross(up, z)), y = cross(z, x);
  return new Float32Array([x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -dot(x, eye), -dot(y, eye), -dot(z, eye), 1]);
}

class ToolpathWebGlRenderer {
  readonly canvas: HTMLCanvasElement;
  readonly gl: WebGLRenderingContext;
  readonly program: WebGLProgram;
  #pathPosition: WebGLBuffer;
  #pathColor: WebGLBuffer;
  #gridPosition: WebGLBuffer;
  #gridColor: WebGLBuffer;
  #pathVertexCount = 0;
  #gridVertexCount = 0;
  #azimuth = 42 * DEG;
  #elevation = 72 * DEG;
  #distance = 420;
  #target: Vec3 = [128, 128, 0];
  #pointer: { id: number; x: number; y: number } | null = null;
  #raf = 0;
  #observer: ResizeObserver;
  #frame: Bounds = { min_x: 0, min_y: 0, min_z: 0, max_x: 256, max_y: 256, max_z: 1 };

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl", { antialias: true, alpha: false });
    if (!gl) throw new Error("WebGL ist nicht verfügbar.");
    this.gl = gl;
    this.program = this.#createProgram();
    const pathPosition = gl.createBuffer(), pathColor = gl.createBuffer(), gridPosition = gl.createBuffer(), gridColor = gl.createBuffer();
    if (!pathPosition || !pathColor || !gridPosition || !gridColor) throw new Error("WebGL-Puffer konnten nicht erstellt werden.");
    this.#pathPosition = pathPosition;
    this.#pathColor = pathColor;
    this.#gridPosition = gridPosition;
    this.#gridColor = gridColor;
    this.#bind();
    this.#observer = new ResizeObserver(() => this.resize());
    this.#observer.observe(canvas);
    this.#setGrid();
    this.resize();
  }

  setFrame(bounds: Bounds): void {
    this.#frame = bounds;
    this.resetView();
  }

  resetView(): void {
    const minX = Math.min(0, this.#frame.min_x), minY = Math.min(0, this.#frame.min_y);
    const maxX = Math.max(256, this.#frame.max_x), maxY = Math.max(256, this.#frame.max_y);
    this.#target = [(minX + maxX) / 2, (minY + maxY) / 2, Math.max(0, this.#frame.max_z) / 2];
    const span = Math.max(maxX - minX, maxY - minY, 80);
    this.#distance = span * 1.55;
    this.#azimuth = 42 * DEG;
    this.#elevation = 72 * DEG;
    this.requestRender();
  }

  setPath(positions: Float32Array, colors: Float32Array): void {
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.#pathPosition);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.#pathColor);
    gl.bufferData(gl.ARRAY_BUFFER, colors, gl.STATIC_DRAW);
    this.#pathVertexCount = positions.length / 3;
    this.requestRender();
  }

  resize(): void {
    const ratio = Math.min(devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(this.canvas.clientWidth * ratio));
    const height = Math.max(1, Math.floor(this.canvas.clientHeight * ratio));
    const changed = this.canvas.width !== width || this.canvas.height !== height;
    if (changed) {
      this.canvas.width = width;
      this.canvas.height = height;
      this.gl.viewport(0, 0, width, height);
    }
    if (changed) this.requestRender();
  }

  requestRender(): void {
    if (this.#raf) return;
    this.#raf = requestAnimationFrame(() => { this.#raf = 0; this.#render(); });
  }

  dispose(): void {
    cancelAnimationFrame(this.#raf);
    this.#observer.disconnect();
    this.gl.deleteBuffer(this.#pathPosition);
    this.gl.deleteBuffer(this.#pathColor);
    this.gl.deleteBuffer(this.#gridPosition);
    this.gl.deleteBuffer(this.#gridColor);
    this.gl.deleteProgram(this.program);
  }

  #shader(type: number, source: string): WebGLShader {
    const shader = this.gl.createShader(type);
    if (!shader) throw new Error("Shader konnte nicht erstellt werden.");
    this.gl.shaderSource(shader, source);
    this.gl.compileShader(shader);
    if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) throw new Error(this.gl.getShaderInfoLog(shader) || "Shaderfehler");
    return shader;
  }

  #createProgram(): WebGLProgram {
    const program = this.gl.createProgram();
    if (!program) throw new Error("WebGL-Programm konnte nicht erstellt werden.");
    this.gl.attachShader(program, this.#shader(this.gl.VERTEX_SHADER, "attribute vec3 a_position;attribute vec3 a_color;uniform mat4 u_mvp;varying vec3 v_color;void main(){v_color=a_color;gl_Position=u_mvp*vec4(a_position,1.0);}"));
    this.gl.attachShader(program, this.#shader(this.gl.FRAGMENT_SHADER, "precision mediump float;varying vec3 v_color;void main(){gl_FragColor=vec4(v_color,1.0);}"));
    this.gl.linkProgram(program);
    if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) throw new Error(this.gl.getProgramInfoLog(program) || "Linkfehler");
    return program;
  }

  #setGrid(): void {
    const positions: number[] = [], colors: number[] = [];
    const add = (x1: number, y1: number, x2: number, y2: number, color: string): void => {
      positions.push(x1, y1, 0, x2, y2, 0);
      const rgb = hexColor(color);
      colors.push(...rgb, ...rgb);
    };
    for (let value = 0; value <= 256; value += 10) {
      const major = value % 50 === 0;
      add(value, 0, value, 256, major ? "#52677A" : "#283847");
      add(0, value, 256, value, major ? "#52677A" : "#283847");
    }
    add(0, 0, 256, 0, "#E5C84B");
    add(256, 0, 256, 256, "#E5C84B");
    add(256, 256, 0, 256, "#E5C84B");
    add(0, 256, 0, 0, "#E5C84B");
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.#gridPosition);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array(positions), this.gl.STATIC_DRAW);
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER, this.#gridColor);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array(colors), this.gl.STATIC_DRAW);
    this.#gridVertexCount = positions.length / 3;
  }

  #bind(): void {
    this.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      this.#distance = Math.max(20, Math.min(5000, this.#distance * Math.exp(event.deltaY * 0.0012)));
      this.requestRender();
    }, { passive: false });
    this.canvas.addEventListener("pointerdown", (event) => {
      this.canvas.setPointerCapture(event.pointerId);
      this.#pointer = { id: event.pointerId, x: event.clientX, y: event.clientY };
    });
    this.canvas.addEventListener("pointermove", (event) => {
      if (!this.#pointer || this.#pointer.id !== event.pointerId) return;
      const dx = event.clientX - this.#pointer.x, dy = event.clientY - this.#pointer.y;
      this.#pointer.x = event.clientX;
      this.#pointer.y = event.clientY;
      this.#azimuth -= dx * 0.006;
      this.#elevation = Math.max(8 * DEG, Math.min(89 * DEG, this.#elevation + dy * 0.006));
      this.requestRender();
    });
    const end = (event: PointerEvent): void => { if (this.#pointer?.id === event.pointerId) this.#pointer = null; };
    this.canvas.addEventListener("pointerup", end);
    this.canvas.addEventListener("pointercancel", end);
    this.canvas.addEventListener("contextmenu", (event) => event.preventDefault());
  }

  #bindAttributes(position: WebGLBuffer, color: WebGLBuffer): void {
    const gl = this.gl;
    const positionLocation = gl.getAttribLocation(this.program, "a_position");
    const colorLocation = gl.getAttribLocation(this.program, "a_color");
    gl.bindBuffer(gl.ARRAY_BUFFER, position);
    gl.enableVertexAttribArray(positionLocation);
    gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, color);
    gl.enableVertexAttribArray(colorLocation);
    gl.vertexAttribPointer(colorLocation, 3, gl.FLOAT, false, 0, 0);
  }

  #render(): void {
    const gl = this.gl;
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
    gl.clearColor(0.018, 0.03, 0.045, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    const cosine = Math.cos(this.#elevation);
    const eye: Vec3 = [
      this.#target[0] + this.#distance * cosine * Math.cos(this.#azimuth),
      this.#target[1] + this.#distance * cosine * Math.sin(this.#azimuth),
      this.#target[2] + this.#distance * Math.sin(this.#elevation),
    ];
    const mvp = multiply(perspective(42 * DEG, this.canvas.width / this.canvas.height, 0.1, 10000), lookAt(eye, this.#target, [0, 0, 1]));
    gl.useProgram(this.program);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.program, "u_mvp"), false, mvp);
    this.#bindAttributes(this.#gridPosition, this.#gridColor);
    gl.drawArrays(gl.LINES, 0, this.#gridVertexCount);
    if (this.#pathVertexCount) {
      this.#bindAttributes(this.#pathPosition, this.#pathColor);
      gl.drawArrays(gl.TRIANGLES, 0, this.#pathVertexCount);
    }
  }
}

function pathMesh(
  layers: readonly ToolpathLayer[],
  selectedLayer: number,
  cumulative: boolean,
  colorMode: ColorMode,
  summary: ToolpathSummary | null,
): { positions: Float32Array; colors: Float32Array } {
  const positions: number[] = [], colors: number[] = [];
  for (const layer of layers) {
    if (cumulative ? layer.index > selectedLayer : layer.index !== selectedLayer) continue;
    const olderFactor = cumulative && layer.index < selectedLayer ? 0.48 : 1;
    for (const segment of layer.segments) {
      const [x1, y1, x2, y2, z, tool, extrusion] = segment;
      const dx = x2 - x1, dy = y2 - y1, length = Math.hypot(dx, dy);
      if (length <= 0.0001) continue;
      const width = Math.max(0.22, Math.min(0.72, extrusion / length * 1.9));
      const nx = -dy / length * width / 2, ny = dx / length * width / 2;
      const height = z + (layer.index === selectedLayer ? 0.035 : 0.012);
      positions.push(
        x1 + nx, y1 + ny, height,
        x1 - nx, y1 - ny, height,
        x2 - nx, y2 - ny, height,
        x1 + nx, y1 + ny, height,
        x2 - nx, y2 - ny, height,
        x2 + nx, y2 + ny, height,
      );
      const color = colorMode === "material"
        ? materialColor(summary, tool)
        : FEATURE_COLORS[featureStyleKey(segment)] || FEATURE_COLORS.model!;
      const rgb = hexColor(color, olderFactor);
      for (let index = 0; index < 6; index += 1) colors.push(...rgb);
    }
  }
  return { positions: new Float32Array(positions), colors: new Float32Array(colors) };
}
function safeBounds(summary: ToolpathSummary | null): Bounds {
  const bounds = summary?.bounds;
  const values = bounds ? Object.values(bounds) : [];
  return bounds && values.every((value) => Number.isFinite(value))
    ? bounds
    : { min_x: 0, min_y: 0, min_z: 0, max_x: 256, max_y: 256, max_z: 1 };
}

export class Ultimate3DToolpathViewer extends HTMLElement {
  #jobId = "";
  #summary: ToolpathSummary | null = null;
  #layers: ToolpathLayer[] = [];
  #visibleLayer = 0;
  #cumulative = false;
  #colorMode: ColorMode = "material";
  #loading = false;
  #error = "";
  #renderer: ToolpathWebGlRenderer | null = null;
  #generation = 0;
  #mounted = false;

  set jobId(value: string) {
    if (value === this.#jobId) return;
    this.#jobId = value;
    this.#summary = null;
    this.#layers = [];
    this.#visibleLayer = 0;
    this.#error = "";
    if (this.isConnected && value) void this.#load();
  }
  get jobId(): string { return this.#jobId; }

  connectedCallback(): void {
    this.#mount();
    if (this.#jobId) void this.#load();
  }

  disconnectedCallback(): void {
    this.#generation += 1;
    this.#renderer?.dispose();
    this.#renderer = null;
    this.#mounted = false;
  }

  #mount(): void {
    if (this.#mounted) return;
    this.innerHTML = `<style>
      :host{display:block;width:100%;height:100%;min-height:650px;color:#edf5fc;font:12px/1.4 Inter,Segoe UI,sans-serif}*{box-sizing:border-box}.viewer{display:grid;grid-template-rows:auto auto minmax(0,1fr);height:100%;min-height:650px;background:#071018}.toolbar{display:grid;grid-template-columns:minmax(300px,1fr) repeat(3,auto);gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid #26394c;background:#0d1823}.slider{display:grid;gap:4px}.slider>div{display:flex;justify-content:space-between;gap:12px}.slider input{width:100%;accent-color:#59df76}.metric,.control{min-height:48px;padding:7px 10px;border:1px solid #2c455c;border-radius:8px;background:#11202d;color:#edf5fc}.metric b,.metric span{display:block}.metric span{font-size:10px;color:#8297ab}.control{display:grid;gap:3px}.control span{font-size:10px;color:#8297ab}.control select,.control button{border:0;background:transparent;color:#edf5fc;font:inherit;font-weight:700;outline:none}.control option{background:#11202d}.legend{display:flex;align-items:center;gap:8px;min-height:42px;padding:7px 12px;border-bottom:1px solid #26394c;background:#0a141e;overflow-x:auto}.legend .hint{color:#8297ab;white-space:nowrap}.chip{display:inline-flex;align-items:center;gap:6px;padding:5px 8px;border:1px solid #2c455c;border-radius:999px;background:#101d29;white-space:nowrap}.chip i{width:11px;height:11px;border-radius:3px;background:var(--chip)}.chip.start{border-color:#8c7730;color:#ffe98c}.stage{position:relative;min-height:560px;background:#071018}.stage canvas{display:block;width:100%;height:100%;min-height:560px}.overlay{position:absolute;left:12px;bottom:12px;max-width:calc(100% - 24px);padding:8px 10px;border:1px solid #31485d;border-radius:8px;background:#08131de8;color:#9db0c1}.error{position:absolute;inset:20px;display:grid;place-items:center;color:#ffc0c6;text-align:center}.loading{position:absolute;right:12px;bottom:12px;padding:7px 10px;border-radius:8px;background:#0b1824e8;color:#8fdca0}.first{color:#8ff0b5}.features{color:#b8cad9}@media(max-width:1000px){.toolbar{grid-template-columns:1fr 1fr}.slider{grid-column:1/-1}}@media(max-width:800px){.stage,.stage canvas{min-height:420px}}
    </style><div class="viewer"><div class="toolbar"><label class="slider"><div><b id="layer-label">Layer 0 / 0</b><span id="z-label">Z – mm</span></div><input id="layer-slider" type="range" min="0" max="0" value="0" disabled></label><div class="metric"><span>Layerpfade</span><b id="segment-count">0</b></div><label class="control"><span>Ansicht</span><select id="layer-mode"><option value="single">Nur aktueller Layer</option><option value="cumulative">Bis aktueller Layer</option></select></label><label class="control"><span>Färbung</span><select id="color-mode"><option value="material">Materialfarben</option><option value="feature">Pfadarten</option></select></label></div><div class="legend" id="legend"><span class="hint">Echte G-Code-Extrusionsbahnen werden geladen …</span></div><div class="stage"><canvas></canvas><div class="error" id="error" hidden></div><div class="overlay"><span id="layer-detail">Der erste echte Drucklayer wird nach dem Laden angezeigt.</span> · Linke Maustaste: drehen · Mausrad: zoomen · <button id="reset-view" type="button">Ansicht zentrieren</button></div><div class="loading" id="loading" hidden>Echte G-Code-Bahnen werden geladen …</div></div></div>`;
    const canvas = this.querySelector<HTMLCanvasElement>("canvas");
    if (!canvas) return;
    try {
      this.#renderer = new ToolpathWebGlRenderer(canvas);
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    }
    this.querySelector<HTMLInputElement>("#layer-slider")?.addEventListener("input", (event) => {
      this.#visibleLayer = Number((event.currentTarget as HTMLInputElement).value);
      this.#update();
    });
    this.querySelector<HTMLSelectElement>("#layer-mode")?.addEventListener("change", (event) => {
      this.#cumulative = (event.currentTarget as HTMLSelectElement).value === "cumulative";
      this.#update();
    });
    this.querySelector<HTMLSelectElement>("#color-mode")?.addEventListener("change", (event) => {
      this.#colorMode = (event.currentTarget as HTMLSelectElement).value === "feature" ? "feature" : "material";
      this.#update();
    });
    this.querySelector<HTMLButtonElement>("#reset-view")?.addEventListener("click", () => this.#renderer?.resetView());
    this.#mounted = true;
    this.#update();
  }

  async #load(): Promise<void> {
    const generation = ++this.#generation;
    this.#loading = true;
    this.#error = "";
    this.#visibleLayer = 0;
    this.#update();
    try {
      const summary = await fetchToolpath(this.#jobId);
      if (generation !== this.#generation) return;
      this.#summary = summary;
      this.#renderer?.setFrame(safeBounds(summary));
      const layers: ToolpathLayer[] = [];
      const chunkSize = 40;
      for (let start = 0; start < summary.layer_count; start += chunkSize) {
        const chunk = await fetchToolpath(this.#jobId, start, Math.min(summary.layer_count, start + chunkSize));
        if (generation !== this.#generation) return;
        layers.push(...(chunk.chunk?.layers ?? []));
        this.#layers = layers;
        this.#update();
      }
    } catch (error) {
      if (generation !== this.#generation) return;
      this.#error = error instanceof Error ? error.message : String(error);
    } finally {
      if (generation === this.#generation) {
        this.#loading = false;
        this.#update();
      }
    }
  }

  #legendHtml(): string {
    if (!this.#summary) return '<span class="hint">Echte G-Code-Extrusionsbahnen werden geladen …</span>';
    const chips: string[] = [];
    if (this.#colorMode === "material") {
      for (const tool of this.#summary.tools) {
        const color = materialColor(this.#summary, tool);
        const name = this.#summary.filament_names?.[tool] || `Filament ${tool + 1}`;
        chips.push(`<span class="chip"><i style="--chip:${esc(color)}"></i>${esc(name)} · T${tool}</span>`);
      }
    } else {
      const keys = new Set<string>();
      for (const layer of this.#layers) for (const segment of layer.segments) keys.add(featureStyleKey(segment));
      for (const key of keys) chips.push(`<span class="chip"><i style="--chip:${esc(FEATURE_COLORS[key] || FEATURE_COLORS.model)}"></i>${esc(featureLabel(key))}</span>`);
    }
    const labels: Readonly<Record<string, string>> = { brim: "Brim", raft: "Raft", support: "Support", skirt: "Skirt", purge_tower: "Reinigungsturm" };
    for (const [key, layer] of Object.entries(this.#summary.feature_first_layers || {})) {
      if (labels[key] !== undefined) chips.push(`<span class="chip start">${esc(labels[key])} ab Layer ${layer + 1}</span>`);
    }
    return chips.join("") || '<span class="hint">Keine Extrusionspfade vorhanden.</span>';
  }

  #update(): void {
    if (!this.#mounted) return;
    const count = this.#summary?.layer_count ?? this.#layers.length;
    this.#visibleLayer = Math.max(0, Math.min(this.#visibleLayer, Math.max(0, count - 1)));
    const currentMeta = this.#summary?.layers[this.#visibleLayer];
    const currentLayer = this.#layers.find((layer) => layer.index === this.#visibleLayer);
    const selectedLayers = this.#cumulative
      ? this.#layers.filter((layer) => layer.index <= this.#visibleLayer)
      : currentLayer ? [currentLayer] : [];
    const segments = selectedLayers.reduce((total, layer) => total + layer.segments.length, 0);
    const features = currentMeta?.features?.length ? currentMeta.features.join(" · ") : "Noch keine Pfade geladen";
    const layerLabel = this.querySelector<HTMLElement>("#layer-label");
    const zLabel = this.querySelector<HTMLElement>("#z-label");
    const segmentCount = this.querySelector<HTMLElement>("#segment-count");
    const detail = this.querySelector<HTMLElement>("#layer-detail");
    const slider = this.querySelector<HTMLInputElement>("#layer-slider");
    const legend = this.querySelector<HTMLElement>("#legend");
    const error = this.querySelector<HTMLElement>("#error");
    const loading = this.querySelector<HTMLElement>("#loading");
    const layerMode = this.querySelector<HTMLSelectElement>("#layer-mode");
    const colorMode = this.querySelector<HTMLSelectElement>("#color-mode");
    if (layerLabel) {
      layerLabel.textContent = `Layer ${count ? this.#visibleLayer + 1 : 0} / ${count}`;
      layerLabel.classList.toggle("first", count > 0 && this.#visibleLayer === 0);
    }
    if (zLabel) zLabel.textContent = `Z ${currentMeta?.z?.toFixed(3) ?? "–"} mm`;
    if (segmentCount) segmentCount.textContent = segments.toLocaleString("de-DE");
    if (detail) detail.innerHTML = `${this.#visibleLayer === 0 && count ? '<b class="first">Erster echter Drucklayer</b> · ' : ""}<span class="features">${esc(features)}</span>`;
    if (slider) {
      slider.max = String(Math.max(0, count - 1));
      slider.value = String(this.#visibleLayer);
      slider.disabled = count === 0;
    }
    if (legend) legend.innerHTML = this.#legendHtml();
    if (error) {
      error.textContent = this.#error;
      error.hidden = !this.#error;
    }
    if (loading) loading.hidden = !this.#loading;
    if (layerMode) layerMode.value = this.#cumulative ? "cumulative" : "single";
    if (colorMode) colorMode.value = this.#colorMode;
    const mesh = pathMesh(this.#layers, this.#visibleLayer, this.#cumulative, this.#colorMode, this.#summary);
    this.#renderer?.setPath(mesh.positions, mesh.colors);
  }
}

if (!customElements.get("ultimate-3d-toolpath-viewer")) customElements.define("ultimate-3d-toolpath-viewer", Ultimate3DToolpathViewer);
