import type { MeshGeometry } from "./webgl-studio-viewport.js";

export type StudioGeometryRecord = Readonly<{
  geometry: MeshGeometry;
  fileName: string;
}>;

const geometryRecords = new Map<string, StudioGeometryRecord>();

export function setStudioGeometry(objectId: string, record: StudioGeometryRecord): void {
  geometryRecords.set(objectId, record);
}

export function getStudioGeometry(objectId: string): StudioGeometryRecord | undefined {
  return geometryRecords.get(objectId);
}

export function removeStudioGeometry(objectId: string): void {
  geometryRecords.delete(objectId);
}

export function clearStudioGeometry(): void {
  geometryRecords.clear();
}
