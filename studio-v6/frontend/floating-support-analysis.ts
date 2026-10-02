import { transformPoint } from "./mesh-export.js";
import type { MeshInstance } from "./webgl-studio-viewport.js";

export type FloatingSupportIssue = Readonly<{
  instanceId: string;
  name: string;
  floatingShellCount: number;
  minimumGapMm: number;
}>;

const BED_TOLERANCE_MM = 0.35;
const CONTACT_TOLERANCE_MM = 0.4;
const MINIMUM_XY_OVERLAP_MM = 0.05;
const MAX_COMPONENT_TRIANGLES = 200_000;
const VERTEX_QUANTIZATION = 10_000;

type ComponentBounds = {
  minX: number;
  minY: number;
  minZ: number;
  maxX: number;
  maxY: number;
  maxZ: number;
};

type SupportComponent = Readonly<{
  instanceId: string;
  name: string;
  bounds: ComponentBounds;
}>;

function vertexKey(x: number, y: number, z: number): string {
  return `${Math.round(x * VERTEX_QUANTIZATION)},${Math.round(y * VERTEX_QUANTIZATION)},${Math.round(z * VERTEX_QUANTIZATION)}`;
}

function transformedVertex(instance: MeshInstance, x: number, y: number, z: number): readonly [number, number, number] {
  return transformPoint([x, y, z], {
    position: instance.position,
    rotation: instance.rotation,
    scale: instance.scale,
  });
}

function emptyBounds(): ComponentBounds {
  return {
    minX: Infinity,
    minY: Infinity,
    minZ: Infinity,
    maxX: -Infinity,
    maxY: -Infinity,
    maxZ: -Infinity,
  };
}

function includePoint(bounds: ComponentBounds, point: readonly [number, number, number]): void {
  bounds.minX = Math.min(bounds.minX, point[0]);
  bounds.minY = Math.min(bounds.minY, point[1]);
  bounds.minZ = Math.min(bounds.minZ, point[2]);
  bounds.maxX = Math.max(bounds.maxX, point[0]);
  bounds.maxY = Math.max(bounds.maxY, point[1]);
  bounds.maxZ = Math.max(bounds.maxZ, point[2]);
}

function includeBounds(target: ComponentBounds, source: ComponentBounds): void {
  target.minX = Math.min(target.minX, source.minX);
  target.minY = Math.min(target.minY, source.minY);
  target.minZ = Math.min(target.minZ, source.minZ);
  target.maxX = Math.max(target.maxX, source.maxX);
  target.maxY = Math.max(target.maxY, source.maxY);
  target.maxZ = Math.max(target.maxZ, source.maxZ);
}

function axisGap(leftMin: number, leftMax: number, rightMin: number, rightMax: number): number {
  if (leftMax < rightMin) return rightMin - leftMax;
  if (rightMax < leftMin) return leftMin - rightMax;
  return 0;
}

function xyOverlaps(upper: ComponentBounds, lower: ComponentBounds): boolean {
  const overlapX = Math.min(upper.maxX, lower.maxX) - Math.max(upper.minX, lower.minX);
  const overlapY = Math.min(upper.maxY, lower.maxY) - Math.max(upper.minY, lower.minY);
  return overlapX >= MINIMUM_XY_OVERLAP_MM && overlapY >= MINIMUM_XY_OVERLAP_MM;
}

function restsOn(upper: ComponentBounds, lower: ComponentBounds): boolean {
  if (lower.minZ > upper.minZ + CONTACT_TOLERANCE_MM) return false;
  const verticalGap = upper.minZ - lower.maxZ;
  return verticalGap >= -CONTACT_TOLERANCE_MM
    && verticalGap <= CONTACT_TOLERANCE_MM
    && xyOverlaps(upper, lower);
}

function touchesOrIntersects(left: ComponentBounds, right: ComponentBounds): boolean {
  return axisGap(left.minX, left.maxX, right.minX, right.maxX) <= CONTACT_TOLERANCE_MM
    && axisGap(left.minY, left.maxY, right.minY, right.maxY) <= CONTACT_TOLERANCE_MM
    && axisGap(left.minZ, left.maxZ, right.minZ, right.maxZ) <= CONTACT_TOLERANCE_MM;
}

function wholeInstanceBounds(instance: MeshInstance): ComponentBounds {
  const bounds = emptyBounds();
  const positions = instance.geometry.positions;
  for (let index = 0; index < positions.length; index += 3) {
    includePoint(
      bounds,
      transformedVertex(instance, positions[index]!, positions[index + 1]!, positions[index + 2]!),
    );
  }
  return bounds;
}

function componentBounds(instance: MeshInstance): ComponentBounds[] {
  const positions = instance.geometry.positions;
  const triangleCount = Math.floor(positions.length / 9);
  if (!triangleCount) return [];
  if (triangleCount > MAX_COMPONENT_TRIANGLES) return [wholeInstanceBounds(instance)];

  const parent = new Int32Array(triangleCount);
  const rank = new Uint8Array(triangleCount);
  const triangleBounds: ComponentBounds[] = [];
  const vertexOwner = new Map<string, number>();

  const find = (value: number): number => {
    let root = value;
    while (parent[root] !== root) root = parent[root]!;
    while (parent[value] !== value) {
      const next = parent[value]!;
      parent[value] = root;
      value = next;
    }
    return root;
  };

  const union = (left: number, right: number): void => {
    let leftRoot = find(left);
    let rightRoot = find(right);
    if (leftRoot === rightRoot) return;
    if ((rank[leftRoot] ?? 0) < (rank[rightRoot] ?? 0)) [leftRoot, rightRoot] = [rightRoot, leftRoot];
    parent[rightRoot] = leftRoot;
    if ((rank[leftRoot] ?? 0) === (rank[rightRoot] ?? 0)) rank[leftRoot] = (rank[leftRoot] ?? 0) + 1;
  };

  for (let triangle = 0; triangle < triangleCount; triangle += 1) {
    parent[triangle] = triangle;
    const bounds = emptyBounds();
    triangleBounds.push(bounds);
    const offset = triangle * 9;
    for (let vertex = 0; vertex < 3; vertex += 1) {
      const index = offset + vertex * 3;
      const x = positions[index]!;
      const y = positions[index + 1]!;
      const z = positions[index + 2]!;
      includePoint(bounds, transformedVertex(instance, x, y, z));
      const key = vertexKey(x, y, z);
      const owner = vertexOwner.get(key);
      if (owner === undefined) vertexOwner.set(key, triangle);
      else union(triangle, owner);
    }
  }

  const byRoot = new Map<number, ComponentBounds>();
  for (let triangle = 0; triangle < triangleCount; triangle += 1) {
    const root = find(triangle);
    const bounds = byRoot.get(root) ?? emptyBounds();
    includeBounds(bounds, triangleBounds[triangle]!);
    byRoot.set(root, bounds);
  }
  return [...byRoot.values()];
}

export function analyzeFloatingSupportNeeds(instances: readonly MeshInstance[]): FloatingSupportIssue[] {
  const components: SupportComponent[] = [];
  for (const instance of instances) {
    if (!instance.visible || !instance.geometry.positions.length) continue;
    for (const bounds of componentBounds(instance)) {
      components.push({ instanceId: instance.id, name: instance.name, bounds });
    }
  }

  const supported = new Set<number>();
  components.forEach((component, index) => {
    if (component.bounds.minZ <= BED_TOLERANCE_MM) supported.add(index);
  });

  let changed = true;
  while (changed) {
    changed = false;
    components.forEach((component, index) => {
      if (supported.has(index)) return;
      for (const supportedIndex of supported) {
        const lower = components[supportedIndex]!;
        if (restsOn(component.bounds, lower.bounds) || touchesOrIntersects(component.bounds, lower.bounds)) {
          supported.add(index);
          changed = true;
          break;
        }
      }
    });
  }

  const byInstance = new Map<string, { name: string; count: number; minimumGapMm: number }>();
  components.forEach((component, index) => {
    if (supported.has(index)) return;
    const current = byInstance.get(component.instanceId) ?? {
      name: component.name,
      count: 0,
      minimumGapMm: Infinity,
    };
    current.count += 1;
    current.minimumGapMm = Math.min(current.minimumGapMm, component.bounds.minZ);
    byInstance.set(component.instanceId, current);
  });

  return [...byInstance.entries()].map(([instanceId, issue]) => ({
    instanceId,
    name: issue.name,
    floatingShellCount: issue.count,
    minimumGapMm: Number.isFinite(issue.minimumGapMm) ? issue.minimumGapMm : 0,
  }));
}