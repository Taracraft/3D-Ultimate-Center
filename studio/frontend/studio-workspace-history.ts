import { clonePaintLayer } from "./studio-paint-state.js";
import type { PersistedStudioWorkspace } from "./studio-persistence.js";

export function cloneWorkspaceSnapshot(snapshot: PersistedStudioWorkspace): PersistedStudioWorkspace {
  return {
    ...snapshot,
    selected: [...snapshot.selected],
    paintLegacyAmbiguousObjectIds: [...(snapshot.paintLegacyAmbiguousObjectIds || [])],
    assignments: snapshot.assignments.map(([id, material]) => [id, material] as const),
    modelMaterials: snapshot.modelMaterials.map((item) => ({ ...item })),
    paintRegions: snapshot.paintRegions.map((region) => ({ ...region, triangleIndices: [...region.triangleIndices] })),
    paintLayers: (snapshot.paintLayers || []).map(([plateId, layers]) => [plateId, layers.map(clonePaintLayer)] as const),
    plates: snapshot.plates.map((plate) => ({
      ...plate,
      ...(plate.localSettings ? { localSettings: { ...plate.localSettings } } : {}),
      selection: {
        ...plate.selection,
        filament_profile_ids: [...plate.selection.filament_profile_ids],
      },
      instances: plate.instances.map((item) => ({
        ...item,
        positions: new Float32Array(item.positions),
        position: [...item.position],
        rotation: [...item.rotation],
        scale: [...item.scale],
      })),
    })),
  };
}

function geometrySignature(positions: Float32Array): string {
  const words = new Uint32Array(positions.buffer, positions.byteOffset, positions.length);
  let first = 0x811c9dc5;
  let second = 0x9e3779b9;
  for (const word of words) {
    first = Math.imul(first ^ word, 0x01000193);
    second = Math.imul(second ^ word, 0x85ebca6b);
  }
  return `${positions.length}:${first >>> 0}:${second >>> 0}`;
}

export function workspaceHistorySignature(snapshot: PersistedStudioWorkspace): string {
  return JSON.stringify({
    activePlate: snapshot.activePlate,
    nextId: snapshot.nextId,
    paintCompositionVersion: snapshot.paintCompositionVersion,
    paintLegacyAmbiguousObjectIds: snapshot.paintLegacyAmbiguousObjectIds,
    assignments: snapshot.assignments,
    modelMaterials: snapshot.modelMaterials,
    paintRegions: snapshot.paintRegions.map((region) => ({ ...region, triangleIndices: [...region.triangleIndices] })),
    paintLayers: (snapshot.paintLayers || []).map(([plateId, layers]) => [plateId, layers.map(clonePaintLayer)]),
    nextPaintLayerId: snapshot.nextPaintLayerId,
    plates: snapshot.plates.map((plate) => ({
      id: plate.id,
      uid: plate.uid,
      name: plate.name,
      width: plate.width,
      depth: plate.depth,
      localSettings: plate.localSettings,
      materialSource: plate.materialSource,
      externalFilamentProfileId: plate.externalFilamentProfileId,
      selection: plate.selection,
      instances: plate.instances.map((item) => ({
        id: item.id,
        name: item.name,
        geometry: geometrySignature(item.positions),
        position: item.position,
        rotation: item.rotation,
        scale: item.scale,
        color: item.color,
        visible: item.visible,
      })),
    })),
  });
}
