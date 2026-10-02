import { yieldToBrowser } from "./browser-yield.js";
import type { MeshGeometry, Vec3 } from "./webgl-studio-viewport.js";

const DEFAULT_TRIANGLE_BATCH = 8_192;

export async function buildMeshGeometryAsync(
  source: readonly number[] | Float32Array,
  triangleBatch = DEFAULT_TRIANGLE_BATCH,
): Promise<MeshGeometry> {
  const positions = new Float32Array(source.length);
  const generatedNormals = new Float32Array(source.length);
  const min: Vec3 = [Infinity, Infinity, Infinity];
  const max: Vec3 = [-Infinity, -Infinity, -Infinity];
  const triangleCount = Math.floor(source.length / 9);
  const batch = Math.max(256, Math.floor(triangleBatch));

  for (let triangle = 0; triangle < triangleCount; triangle += 1) {
    const index = triangle * 9;
    for (let offset = 0; offset < 9; offset += 1) positions[index + offset] = Number(source[index + offset] ?? 0);

    const ax = positions[index]!;
    const ay = positions[index + 1]!;
    const az = positions[index + 2]!;
    const bx = positions[index + 3]!;
    const by = positions[index + 4]!;
    const bz = positions[index + 5]!;
    const cx = positions[index + 6]!;
    const cy = positions[index + 7]!;
    const cz = positions[index + 8]!;

    const ux = bx - ax;
    const uy = by - ay;
    const uz = bz - az;
    const vx = cx - ax;
    const vy = cy - ay;
    const vz = cz - az;
    let nx = uy * vz - uz * vy;
    let ny = uz * vx - ux * vz;
    let nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz) || 1;
    nx /= length;
    ny /= length;
    nz /= length;

    for (let vertex = 0; vertex < 3; vertex += 1) {
      const vertexIndex = index + vertex * 3;
      const x = positions[vertexIndex]!;
      const y = positions[vertexIndex + 1]!;
      const z = positions[vertexIndex + 2]!;
      min[0] = Math.min(min[0], x);
      min[1] = Math.min(min[1], y);
      min[2] = Math.min(min[2], z);
      max[0] = Math.max(max[0], x);
      max[1] = Math.max(max[1], y);
      max[2] = Math.max(max[2], z);
      generatedNormals[vertexIndex] = nx;
      generatedNormals[vertexIndex + 1] = ny;
      generatedNormals[vertexIndex + 2] = nz;
    }

    if ((triangle + 1) % batch === 0) await yieldToBrowser();
  }

  if (!triangleCount) {
    min[0] = min[1] = min[2] = 0;
    max[0] = max[1] = max[2] = 0;
  }

  return Object.freeze({
    positions,
    normals: generatedNormals,
    triangleCount,
    boundsMin: min,
    boundsMax: max,
  });
}