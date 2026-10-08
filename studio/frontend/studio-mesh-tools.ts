import { transformPoint } from "./mesh-export.js";
import type { MeshGeometry, MeshInstance, Vec3 } from "./webgl-studio-viewport.js";

export type StudioMirrorAxis = "x" | "y" | "z";

export type MeshSelectionMeasurement = Readonly<{
  minimum: Vec3;
  maximum: Vec3;
  size: Vec3;
  objectCount: number;
  triangleCount: number;
}>;

function axisIndex(axis: StudioMirrorAxis): 0 | 1 | 2 {
  return axis === "x" ? 0 : axis === "y" ? 1 : 2;
}

export function geometryFromPositions(positions: Float32Array): MeshGeometry {
  const normals = new Float32Array(positions.length);
  const minimum: Vec3 = [Infinity, Infinity, Infinity];
  const maximum: Vec3 = [-Infinity, -Infinity, -Infinity];
  for (let index = 0; index < positions.length; index += 9) {
    const a: Vec3 = [positions[index]!, positions[index + 1]!, positions[index + 2]!];
    const b: Vec3 = [positions[index + 3]!, positions[index + 4]!, positions[index + 5]!];
    const c: Vec3 = [positions[index + 6]!, positions[index + 7]!, positions[index + 8]!];
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
    const vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
    let nx = uy * vz - uz * vy;
    let ny = uz * vx - ux * vz;
    let nz = ux * vy - uy * vx;
    const length = Math.hypot(nx, ny, nz) || 1;
    nx /= length;
    ny /= length;
    nz /= length;
    for (let vertex = 0; vertex < 3; vertex += 1) {
      const offset = index + vertex * 3;
      normals[offset] = nx;
      normals[offset + 1] = ny;
      normals[offset + 2] = nz;
      minimum[0] = Math.min(minimum[0], positions[offset]!);
      minimum[1] = Math.min(minimum[1], positions[offset + 1]!);
      minimum[2] = Math.min(minimum[2], positions[offset + 2]!);
      maximum[0] = Math.max(maximum[0], positions[offset]!);
      maximum[1] = Math.max(maximum[1], positions[offset + 1]!);
      maximum[2] = Math.max(maximum[2], positions[offset + 2]!);
    }
  }
  return Object.freeze({
    positions,
    normals,
    triangleCount: positions.length / 9,
    boundsMin: minimum,
    boundsMax: maximum,
  });
}

export function mirrorMeshGeometry(geometry: MeshGeometry, axis: StudioMirrorAxis): MeshGeometry {
  const selectedAxis = axisIndex(axis);
  const center = (geometry.boundsMin[selectedAxis] + geometry.boundsMax[selectedAxis]) / 2;
  const output = new Float32Array(geometry.positions.length);
  const reflected = (sourceOffset: number, targetOffset: number): void => {
    for (let coordinate = 0; coordinate < 3; coordinate += 1) {
      const value = geometry.positions[sourceOffset + coordinate]!;
      output[targetOffset + coordinate] = coordinate === selectedAxis ? center * 2 - value : value;
    }
  };
  for (let index = 0; index < geometry.positions.length; index += 9) {
    reflected(index, index);
    reflected(index + 6, index + 3);
    reflected(index + 3, index + 6);
  }
  return geometryFromPositions(output);
}

export function measureMeshInstances(instances: readonly MeshInstance[]): MeshSelectionMeasurement | null {
  if (!instances.length) return null;
  const minimum: Vec3 = [Infinity, Infinity, Infinity];
  const maximum: Vec3 = [-Infinity, -Infinity, -Infinity];
  let triangleCount = 0;
  for (const instance of instances) {
    triangleCount += instance.geometry.triangleCount;
    const positions = instance.geometry.positions;
    for (let index = 0; index < positions.length; index += 3) {
      const point = transformPoint(
        [positions[index]!, positions[index + 1]!, positions[index + 2]!],
        instance,
      );
      for (const coordinate of [0, 1, 2] as const) {
        minimum[coordinate] = Math.min(minimum[coordinate], point[coordinate]);
        maximum[coordinate] = Math.max(maximum[coordinate], point[coordinate]);
      }
    }
  }
  return {
    minimum,
    maximum,
    size: [maximum[0] - minimum[0], maximum[1] - minimum[1], maximum[2] - minimum[2]],
    objectCount: instances.length,
    triangleCount,
  };
}
