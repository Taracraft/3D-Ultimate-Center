import type { PersistedStudioWorkspace } from "./studio-persistence.js";

export function cloneWorkspaceSnapshot(snapshot: PersistedStudioWorkspace): PersistedStudioWorkspace {
  return {
    ...snapshot,
    selected: [...snapshot.selected],
    assignments: snapshot.assignments.map(([id, material]) => [id, material] as const),
    modelMaterials: snapshot.modelMaterials.map((item) => ({ ...item })),
    paintRegions: snapshot.paintRegions.map((region) => ({ ...region, triangleIndices: [...region.triangleIndices] })),
    paintLayers: snapshot.paintLayers.map(([plateId, layers]) => [plateId, layers.map((layer) => ({ ...layer, points: layer.points.map((point) => ({ ...point })) }))] as const),
    plates: snapshot.plates.map((plate) => ({
      ...plate,
      selection: {
        ...plate.selection,
        filament_profile_ids: [...plate.selection.filament_profile_ids],
      },
      instances: plate.instances.map((item) => ({
        ...item,
        positions: item.positions,
        position: [...item.position],
        rotation: [...item.rotation],
        scale: [...item.scale],
      })),
    })),
  };
}

export function workspaceHistorySignature(snapshot: PersistedStudioWorkspace): string {
  return JSON.stringify({
    activePlate: snapshot.activePlate,
    nextId: snapshot.nextId,
    assignments: snapshot.assignments,
    modelMaterials: snapshot.modelMaterials,
    paintRegions: snapshot.paintRegions.map((region) => ({ ...region, triangleIndices: [...region.triangleIndices] })),
    paintLayers: snapshot.paintLayers.map(([plateId, layers]) => [plateId, layers.map((layer) => ({ ...layer, points: layer.points.map((point) => ({ ...point })) }))]),
    nextPaintLayerId: snapshot.nextPaintLayerId,
    plates: snapshot.plates.map((plate) => ({
      id: plate.id,
      name: plate.name,
      width: plate.width,
      depth: plate.depth,
      materialSource: plate.materialSource,
      externalFilamentProfileId: plate.externalFilamentProfileId,
      selection: plate.selection,
      instances: plate.instances.map((item) => ({
        id: item.id,
        name: item.name,
        geometryLength: item.positions.length,
        position: item.position,
        rotation: item.rotation,
        scale: item.scale,
        color: item.color,
        visible: item.visible,
      })),
    })),
  });
}
