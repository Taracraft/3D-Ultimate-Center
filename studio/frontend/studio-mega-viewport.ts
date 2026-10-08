import type { StudioBuildPlateVisual } from "./studio-build-plates.js";
import type { MeshInstance, Vec3 } from "./webgl-studio-viewport.js";
import type { PaintRegion } from "./studio-mesh-paint.js";

type GpuMesh = { position: WebGLBuffer; normal: WebGLBuffer; count: number };
type FlatMesh = { buffer: WebGLBuffer; count: number; mode: number; color: string };
export type MegaGizmoMode = "select" | "translate" | "rotate" | "scale";
export type MegaAxis = "x" | "y" | "z";
export type PaintPickResult = Readonly<{
  objectId: string;
  triangleIndex: number;
  localPosition: Vec3;
  distancePx: number;
}>;

export type PaintShapeKind = "rectangle" | "circle";
export type PaintScreenPoint = Readonly<{ x: number; y: number }>;
export type PaintShapeBounds = Readonly<{ left: number; right: number; top: number; bottom: number }>;

export function projectedPaintHit(
  point: PaintScreenPoint,
  projected: readonly Readonly<{ x: number; y: number; w: number; depth: number }>[],
  positions: ArrayLike<number>,
  base = 0,
): Readonly<{ localPosition: Vec3; depth: number }> | null {
  const [a, b, c] = projected;
  if (!a || !b || !c || projected.some((vertex) => !Number.isFinite(vertex.w) || vertex.w <= 0)) return null;
  const denominator = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y);
  if (!Number.isFinite(denominator) || Math.abs(denominator) < 1e-10) return null;
  const first = ((b.y - c.y) * (point.x - c.x) + (c.x - b.x) * (point.y - c.y)) / denominator;
  const second = ((c.y - a.y) * (point.x - c.x) + (a.x - c.x) * (point.y - c.y)) / denominator;
  const weights = [first, second, 1 - first - second];
  if (weights.some((weight) => !Number.isFinite(weight) || weight < -1e-7)) return null;
  const depth = weights.reduce((sum, weight, index) => sum + weight * projected[index]!.depth, 0);
  if (!Number.isFinite(depth) || depth < -1 || depth > 1) return null;
  const corrected = weights.map((weight, index) => weight / projected[index]!.w);
  const total = corrected.reduce((sum, weight) => sum + weight, 0);
  const localPosition = [0, 1, 2].map((axis) => corrected.reduce((sum, weight, index) => sum + weight * positions[base + index * 3 + axis]!, 0) / total) as Vec3;
  return localPosition.every(Number.isFinite) ? { localPosition, depth } : null;
}

/** Clip before perspective division; behind-camera triangles must never enter selection. */
export function clipPaintPolygon(vertices: readonly (readonly number[])[]): number[][] {
  if (vertices.some((vertex) => vertex.length !== 4 || vertex.some((value) => !Number.isFinite(value)))) return [];
  let polygon = vertices.map((vertex) => [...vertex]);
  const planes = [(v: number[]) => v[3]! + v[0]!, (v: number[]) => v[3]! - v[0]!, (v: number[]) => v[3]! + v[1]!, (v: number[]) => v[3]! - v[1]!, (v: number[]) => v[3]! + v[2]!, (v: number[]) => v[3]! - v[2]!, (v: number[]) => v[3]! - 1e-8];
  for (const distance of planes) {
    const input = polygon; polygon = [];
    if (!input.length) break;
    let previous = input[input.length - 1]!, previousDistance = distance(previous);
    for (const current of input) {
      const currentDistance = distance(current);
      if ((currentDistance >= 0) !== (previousDistance >= 0)) {
        const ratio = previousDistance / (previousDistance - currentDistance);
        polygon.push(previous.map((value, axis) => value + (current[axis]! - value) * ratio));
      }
      if (currentDistance >= 0) polygon.push(current);
      previous = current; previousDistance = currentDistance;
    }
  }
  return polygon;
}

function pointInProjectedTriangle(point: PaintScreenPoint, a: PaintScreenPoint, b: PaintScreenPoint, c: PaintScreenPoint): boolean {
  const cross = (left: PaintScreenPoint, right: PaintScreenPoint, target: PaintScreenPoint): number =>
    (right.x - left.x) * (target.y - left.y) - (right.y - left.y) * (target.x - left.x);
  const first = cross(a, b, point);
  const second = cross(b, c, point);
  const third = cross(c, a, point);
  const epsilon = 0.0001;
  return (first >= -epsilon && second >= -epsilon && third >= -epsilon)
    || (first <= epsilon && second <= epsilon && third <= epsilon);
}

function projectedSegmentsIntersect(a: PaintScreenPoint, b: PaintScreenPoint, c: PaintScreenPoint, d: PaintScreenPoint): boolean {
  const cross = (left: PaintScreenPoint, right: PaintScreenPoint, target: PaintScreenPoint): number =>
    (right.x - left.x) * (target.y - left.y) - (right.y - left.y) * (target.x - left.x);
  const between = (left: number, value: number, right: number): boolean => value >= Math.min(left, right) - 0.0001 && value <= Math.max(left, right) + 0.0001;
  const first = cross(a, b, c), second = cross(a, b, d), third = cross(c, d, a), fourth = cross(c, d, b);
  if (((first > 0 && second < 0) || (first < 0 && second > 0)) && ((third > 0 && fourth < 0) || (third < 0 && fourth > 0))) return true;
  return Math.abs(first) <= 0.0001 && between(a.x, c.x, b.x) && between(a.y, c.y, b.y)
    || Math.abs(second) <= 0.0001 && between(a.x, d.x, b.x) && between(a.y, d.y, b.y)
    || Math.abs(third) <= 0.0001 && between(c.x, a.x, d.x) && between(c.y, a.y, d.y)
    || Math.abs(fourth) <= 0.0001 && between(c.x, b.x, d.x) && between(c.y, b.y, d.y);
}

function projectedSegmentIntersectsRectangle(a: PaintScreenPoint, b: PaintScreenPoint, bounds: PaintShapeBounds): boolean {
  const inside = (point: PaintScreenPoint): boolean => point.x >= bounds.left && point.x <= bounds.right && point.y >= bounds.top && point.y <= bounds.bottom;
  if (inside(a) || inside(b)) return true;
  const corners: readonly PaintScreenPoint[] = [
    { x: bounds.left, y: bounds.top }, { x: bounds.right, y: bounds.top },
    { x: bounds.right, y: bounds.bottom }, { x: bounds.left, y: bounds.bottom },
  ];
  return corners.some((corner, index) => projectedSegmentsIntersect(a, b, corner, corners[(index + 1) % corners.length]!));
}

function pointInProjectedEllipse(point: PaintScreenPoint, bounds: PaintShapeBounds): boolean {
  const radiusX = Math.max(1, (bounds.right - bounds.left) / 2);
  const radiusY = Math.max(1, (bounds.bottom - bounds.top) / 2);
  const centerX = (bounds.left + bounds.right) / 2;
  const centerY = (bounds.top + bounds.bottom) / 2;
  const dx = (point.x - centerX) / radiusX;
  const dy = (point.y - centerY) / radiusY;
  return dx * dx + dy * dy <= 1.0001;
}

function projectedSegmentIntersectsEllipse(a: PaintScreenPoint, b: PaintScreenPoint, bounds: PaintShapeBounds): boolean {
  if (pointInProjectedEllipse(a, bounds) || pointInProjectedEllipse(b, bounds)) return true;
  const radiusX = Math.max(1, (bounds.right - bounds.left) / 2);
  const radiusY = Math.max(1, (bounds.bottom - bounds.top) / 2);
  const centerX = (bounds.left + bounds.right) / 2;
  const centerY = (bounds.top + bounds.bottom) / 2;
  const ax = (a.x - centerX) / radiusX, ay = (a.y - centerY) / radiusY;
  const bx = (b.x - centerX) / radiusX, by = (b.y - centerY) / radiusY;
  const dx = bx - ax, dy = by - ay;
  const quadratic = dx * dx + dy * dy;
  if (quadratic <= 0.0000001) return false;
  const linear = 2 * (ax * dx + ay * dy);
  const constant = ax * ax + ay * ay - 1;
  const discriminant = linear * linear - 4 * quadratic * constant;
  if (discriminant < 0) return false;
  const root = Math.sqrt(discriminant);
  const first = (-linear - root) / (2 * quadratic);
  const second = (-linear + root) / (2 * quadratic);
  return (first >= 0 && first <= 1) || (second >= 0 && second <= 1);
}

export function projectedTriangleIntersectsPaintShape(
  triangle: readonly [PaintScreenPoint, PaintScreenPoint, PaintScreenPoint],
  shape: PaintShapeKind,
  bounds: PaintShapeBounds,
): boolean {
  const [a, b, c] = triangle;
  if (shape === "rectangle") {
    if ([a, b, c].some((point) => point.x >= bounds.left && point.x <= bounds.right && point.y >= bounds.top && point.y <= bounds.bottom)) return true;
    const corners: readonly PaintScreenPoint[] = [
      { x: bounds.left, y: bounds.top }, { x: bounds.right, y: bounds.top },
      { x: bounds.right, y: bounds.bottom }, { x: bounds.left, y: bounds.bottom },
    ];
    if (corners.some((corner) => pointInProjectedTriangle(corner, a, b, c))) return true;
    return projectedSegmentIntersectsRectangle(a, b, bounds)
      || projectedSegmentIntersectsRectangle(b, c, bounds)
      || projectedSegmentIntersectsRectangle(c, a, bounds);
  }
  const center = { x: (bounds.left + bounds.right) / 2, y: (bounds.top + bounds.bottom) / 2 };
  return pointInProjectedEllipse(a, bounds)
    || pointInProjectedEllipse(b, bounds)
    || pointInProjectedEllipse(c, bounds)
    || pointInProjectedTriangle(center, a, b, c)
    || projectedSegmentIntersectsEllipse(a, b, bounds)
    || projectedSegmentIntersectsEllipse(b, c, bounds)
    || projectedSegmentIntersectsEllipse(c, a, bounds);
}

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
  #paintRegions: readonly PaintRegion[] = [];
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
  setPaintRegions(regions: readonly PaintRegion[]): void {
    this.#paintRegions = regions;
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

  pick(clientX: number, clientY: number): string | null {
    const rect = this.canvas.getBoundingClientRect();
    const px = (clientX - rect.left) * (this.canvas.width / Math.max(1, rect.width));
    const py = (clientY - rect.top) * (this.canvas.height / Math.max(1, rect.height));
    const vp = this.#viewProjection();
    let best: { id: string; area: number; depth: number } | null = null;
    for (const instance of this.#instances) {
      if (!instance.visible) continue;
      const mvp = multiply(vp, modelMatrix(instance));
      const projected = corners(instance).map((point) => {
        const value = transformPoint(mvp, point);
        const w = value[3] || 1;
        return {
          x: (value[0] / w * .5 + .5) * this.canvas.width,
          y: (1 - (value[1] / w * .5 + .5)) * this.canvas.height,
          z: value[2] / w,
        };
      });
      const minX = Math.min(...projected.map((point) => point.x));
      const maxX = Math.max(...projected.map((point) => point.x));
      const minY = Math.min(...projected.map((point) => point.y));
      const maxY = Math.max(...projected.map((point) => point.y));
      if (px < minX - 5 || px > maxX + 5 || py < minY - 5 || py > maxY + 5) continue;
      const area = Math.max(1, (maxX - minX) * (maxY - minY));
      const depth = projected.reduce((sum, point) => sum + point.z, 0) / projected.length;
      if (!best || depth < best.depth || (Math.abs(depth - best.depth) < .02 && area < best.area)) {
        best = { id: instance.id, area, depth };
      }
    }
    return best?.id ?? null;
  }

  getPaintProjection(objectId: string): readonly number[] | null {
    const instance = this.#instances.find((item) => item.id === objectId && item.visible);
    return instance ? [...multiply(this.#viewProjection(), modelMatrix(instance))] : null;
  }

  pickSelectionRectangle(startX: number, startY: number, endX: number, endY: number): ReadonlyMap<string, readonly number[]> {
    const visible = this.#instances.filter((instance) => instance.visible && !instance.id.startsWith("purge-tower-"));
    if (visible.reduce((sum, instance) => sum + instance.geometry.triangleCount, 0) > 2_000_000) throw new Error("Die Rahmenauswahl überschreitet das interaktive Modellbudget. Bitte Modelle einzeln auswählen.");
    const result = new Map<string, readonly number[]>();
    for (const instance of visible) {
      const triangles = this.pickPaintShape(instance.id, startX, startY, endX, endY, "rectangle");
      if (triangles.length) result.set(instance.id, triangles);
    }
    return result;
  }

  pickPaintPoint(clientX: number, clientY: number): PaintPickResult | null {
    const rect = this.canvas.getBoundingClientRect();
    const px = (clientX - rect.left) * (this.canvas.width / Math.max(1, rect.width));
    const py = (clientY - rect.top) * (this.canvas.height / Math.max(1, rect.height));
    const vp = this.#viewProjection();
    let best: { objectId: string; triangleIndex: number; localPosition: Vec3; depth: number } | null = null;
    for (const instance of this.#instances) {
      if (!instance.visible) continue;
      const mvp = multiply(vp, modelMatrix(instance));
      const positions = instance.geometry.positions;
      for (let triangleIndex = 0; triangleIndex < instance.geometry.triangleCount; triangleIndex += 1) {
        const base = triangleIndex * 9;
        const projected = [0, 3, 6].map((offset) => {
          const value = transformPoint(mvp, [positions[base + offset]!, positions[base + offset + 1]!, positions[base + offset + 2]!]);
          const w = value[3] || 1;
          return { w, x: (value[0] / w * .5 + .5) * this.canvas.width, y: (1 - (value[1] / w * .5 + .5)) * this.canvas.height, depth: value[2] / w };
        });
        const hit = projectedPaintHit({ x: px, y: py }, projected, positions, base);
        if (hit && (!best || hit.depth < best.depth)) {
          best = { objectId: instance.id, triangleIndex, localPosition: hit.localPosition, depth: hit.depth };
        }
      }
    }
    return best ? { objectId: best.objectId, triangleIndex: best.triangleIndex, localPosition: best.localPosition, distancePx: 0 } : null;
  }

  pickPaintShape(objectId: string, startClientX: number, startClientY: number, endClientX: number, endClientY: number, shape: PaintShapeKind): readonly number[] {
    const instance = this.#instances.find((item) => item.id === objectId);
    if (!instance || !instance.visible) return [];
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / Math.max(1, rect.width);
    const scaleY = this.canvas.height / Math.max(1, rect.height);
    const startX = (startClientX - rect.left) * scaleX;
    const startY = (startClientY - rect.top) * scaleY;
    const endX = (endClientX - rect.left) * scaleX;
    const endY = (endClientY - rect.top) * scaleY;
    const bounds: PaintShapeBounds = {
      left: Math.min(startX, endX), right: Math.max(startX, endX),
      top: Math.min(startY, endY), bottom: Math.max(startY, endY),
    };
    const mvp = multiply(this.#viewProjection(), modelMatrix(instance));
    const matches: number[] = [];
    for (let triangleIndex = 0; triangleIndex < instance.geometry.triangleCount; triangleIndex += 1) {
      const base = triangleIndex * 9;
      const clipped = clipPaintPolygon([0, 3, 6].map((offset) => transformPoint(mvp, [instance.geometry.positions[base + offset]!, instance.geometry.positions[base + offset + 1]!, instance.geometry.positions[base + offset + 2]!])));
      const projected = clipped.map((value) => ({ x: (value[0]! / value[3]! * .5 + .5) * this.canvas.width, y: (1 - (value[1]! / value[3]! * .5 + .5)) * this.canvas.height }));
      for (let vertex = 1; vertex + 1 < projected.length; vertex += 1) {
        if (projectedTriangleIntersectsPaintShape([projected[0]!, projected[vertex]!, projected[vertex + 1]!], shape, bounds)) { matches.push(triangleIndex); break; }
      }
    }
    return matches;
  }

  pickPaintText(objectId: string, clientX: number, baselineClientY: number, text: string, fontSizeCssPx: number): readonly number[] {
    const instance = this.#instances.find((item) => item.id === objectId);
    const value = String(text || "").trim();
    if (!instance || !instance.visible || !value) return [];
    const rect = this.canvas.getBoundingClientRect();
    const scaleX = this.canvas.width / Math.max(1, rect.width);
    const scaleY = this.canvas.height / Math.max(1, rect.height);
    const scale = Math.min(scaleX, scaleY);
    const fontSize = Math.max(8, Math.min(192, Number(fontSizeCssPx) * scale || 28 * scale));
    const raster = this.canvas.ownerDocument.createElement("canvas");
    const context = raster.getContext("2d", { willReadFrequently: true });
    if (!context) return [];
    context.font = "700 " + fontSize + "px Inter,Segoe UI,sans-serif";
    const padding = Math.max(3, Math.ceil(fontSize * .18));
    const width = Math.max(1, Math.ceil(context.measureText(value).width + padding * 2));
    const height = Math.max(1, Math.ceil(fontSize * 1.4 + padding * 2));
    raster.width = width; raster.height = height;
    context.font = "700 " + fontSize + "px Inter,Segoe UI,sans-serif";
    context.fillStyle = "#ffffff"; context.textBaseline = "alphabetic";
    context.fillText(value, padding, padding + fontSize);
    const alpha = context.getImageData(0, 0, width, height).data;
    const startX = (clientX - rect.left) * scaleX;
    const baselineY = (baselineClientY - rect.top) * scaleY;
    const originX = startX - padding;
    const originY = baselineY - fontSize - padding;
    const mvp = multiply(this.#viewProjection(), modelMatrix(instance));
    const matches: number[] = [];
    for (let triangleIndex = 0; triangleIndex < instance.geometry.triangleCount; triangleIndex += 1) {
      const base = triangleIndex * 9;
      const projected = [0, 3, 6].map((offset) => {
        const point = transformPoint(mvp, [instance.geometry.positions[base + offset]!, instance.geometry.positions[base + offset + 1]!, instance.geometry.positions[base + offset + 2]!]);
        const w = point[3] || 1;
        return { w, x: (point[0] / w * .5 + .5) * this.canvas.width, y: (1 - (point[1] / w * .5 + .5)) * this.canvas.height };
      });
      if (projected.some((point) => point.w <= 0)) continue;
      const x = Math.floor((projected[0]!.x + projected[1]!.x + projected[2]!.x) / 3 - originX);
      const y = Math.floor((projected[0]!.y + projected[1]!.y + projected[2]!.y) / 3 - originY);
      if (x >= 0 && x < width && y >= 0 && y < height && alpha[(y * width + x) * 4 + 3]! > 80) matches.push(triangleIndex);
    }
    return matches;
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
    for (const region of this.#paintRegions) {
      const instance = this.#instances.find((item) => item.id === region.objectId);
      if (!instance) continue;
      const model = modelMatrix(instance);
      for (const triangleIndex of region.triangleIndices) {
        const base = triangleIndex * 9;
        if (base + 8 >= instance.geometry.positions.length) continue;
        const a = transformPoint(model, [instance.geometry.positions[base]!, instance.geometry.positions[base + 1]!, instance.geometry.positions[base + 2]!]);
        const b = transformPoint(model, [instance.geometry.positions[base + 3]!, instance.geometry.positions[base + 4]!, instance.geometry.positions[base + 5]!]);
        const c = transformPoint(model, [instance.geometry.positions[base + 6]!, instance.geometry.positions[base + 7]!, instance.geometry.positions[base + 8]!]);
        const values = [a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]];
        this.#overlayMeshes.push(this.#flatMesh(values, this.gl.TRIANGLES, region.color));
      }
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
    gl.enable(gl.POLYGON_OFFSET_FILL);
    gl.polygonOffset(-1, -1);
    for (const item of this.#overlayMeshes) this.#drawFlat(item, vp);
    gl.disable(gl.POLYGON_OFFSET_FILL);
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
