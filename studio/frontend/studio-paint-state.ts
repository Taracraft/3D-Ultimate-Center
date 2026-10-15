import { validatePaintMask } from "./studio-paint-mask.js";
import type { PaintRegion } from "./studio-mesh-paint.js";
import type { PersistedStudioPaintLayer, PersistedStudioWorkspace } from "./studio-persistence.js";

/** Paint data is owned by a globally unique object, independently of a plate's display index. */
export function clonePaintLayer<T extends PersistedStudioPaintLayer>(layer: T): T {
  if (layer.mask) validatePaintMask(layer.mask);
  for (const point of layer.points) {
    if (point.normal && (!Array.isArray(point.normal) || point.normal.length !== 3 || !point.normal.every(Number.isFinite))) throw new Error("Die gespeicherte Flächennormale ist ungültig.");
  }
  return {
    ...layer,
    points: layer.points.map((point) => ({ ...point, ...(point.normal ? { normal: [...point.normal] } : {}) })),
    ...(layer.mask ? { mask: {
      ...layer.mask,
      matrix: [...layer.mask.matrix],
      ...(layer.mask.runs ? { runs: [...layer.mask.runs] } : {}),
    } } : {}),
  };
}

export function restoreStudioPaintState(snapshot: PersistedStudioWorkspace): Readonly<{
  regions: PaintRegion[];
  layers: Map<number, PersistedStudioPaintLayer[]>;
  legacyAmbiguousObjectIds: Set<string>;
}> {
  if (snapshot.paintCompositionVersion !== undefined && snapshot.paintCompositionVersion !== 1) {
    throw new Error("Die gespeicherte Bemalung verwendet eine noch nicht unterstützte Version.");
  }
  const objectPlate = new Map<string, number>();
  snapshot.plates.forEach((plate, index) => {
    for (const item of plate.instances) {
      if (objectPlate.has(item.id)) throw new Error("Gespeicherte Objekte haben doppelte Kennungen; Bemalung wird nicht mehrdeutig zugeordnet.");
      objectPlate.set(item.id, index);
    }
  });
  const regions = (snapshot.paintRegions || [])
    .filter((region) => objectPlate.has(region.objectId))
    .map((region) => ({ objectId: region.objectId, triangleIndices: [...region.triangleIndices], color: region.color, materialKey: region.materialKey, ...(region.label ? { label: region.label } : {}) }));
  const layers = new Map<number, PersistedStudioPaintLayer[]>();
  for (const [, entries] of snapshot.paintLayers || []) {
    for (const entry of entries || []) {
      const plateId = objectPlate.get(entry.objectId);
      if (plateId === undefined) continue;
      const bucket = layers.get(plateId) || [];
      bucket.push(clonePaintLayer({ ...entry, plateId, points: entry.points || [] }));
      layers.set(plateId, bucket);
    }
  }
  const paintedObjects = new Set(regions.filter((region) => region.triangleIndices.length > 0).map((region) => region.objectId));
  const legacyAmbiguousObjectIds = snapshot.paintCompositionVersion === 1
    ? new Set((snapshot.paintLegacyAmbiguousObjectIds || []).filter((id) => objectPlate.has(id)))
    : new Set([...layers.values()].flat().filter((layer) => layer.points.length > 0 && paintedObjects.has(layer.objectId)).map((layer) => layer.objectId));
  return { regions, layers, legacyAmbiguousObjectIds };
}

export function remapPaintLayerPlates<T extends PersistedStudioPaintLayer>(
  layers: ReadonlyMap<number, readonly T[]>,
  plates: readonly Readonly<{ id: number; instances: readonly Readonly<{ id: string }>[] }>[],
): Map<number, T[]> {
  const objectPlate = new Map(plates.flatMap((plate) => plate.instances.map((item) => [item.id, plate.id] as const)));
  const result = new Map<number, T[]>();
  for (const entries of layers.values()) {
    for (const layer of entries) {
      const plateId = objectPlate.get(layer.objectId);
      if (plateId === undefined) continue;
      const bucket = result.get(plateId) || [];
      bucket.push(clonePaintLayer({ ...layer, plateId }));
      result.set(plateId, bucket);
    }
  }
  return result;
}

export function paintEditConflict(objectId: string, ambiguous: ReadonlySet<string>): string | null {
  return ambiguous.has(objectId)
    ? "Dieser ältere Malstand enthält Basisflächen und Malebenen ohne Herkunftskennzeichnung. Beide bleiben erhalten. Einzelne Malbereiche können erst nach bewusster Auflösung bearbeitet werden; Speichern, Kopieren und der bisherige Export bleiben möglich."
    : null;
}

/** Map known source faces only; collapsed duplicate faces must not hide material conflicts. */
export function remapObjectPaintRegions(
  source: readonly PaintRegion[],
  objectId: string,
  triangleIndexMap: ReadonlyMap<number, readonly number[]>,
): PaintRegion[] {
  const owners = new Map<number, string>();
  return source.flatMap((region) => {
    const triangleIndices = [...new Set(region.triangleIndices.flatMap((index) => {
      if (!Number.isInteger(index) || index < 0 || !triangleIndexMap.has(index)) throw new Error("Bemalung enthält eine unbekannte ursprüngliche Dreiecksreferenz; Geometrie blieb unverändert.");
      return [...triangleIndexMap.get(index)!];
    }))];
    const material = JSON.stringify([region.materialKey, region.color]);
    for (const index of triangleIndices) {
      const previous = owners.get(index);
      if (previous !== undefined && previous !== material) throw new Error("Doppelte Flächen tragen unterschiedliche Materialien; die automatische Reparatur würde Bemalung überschreiben.");
      owners.set(index, material);
    }
    return triangleIndices.length ? [{ ...region, objectId, triangleIndices }] : [];
  });
}

export function mirrorPaintLayer<T extends PersistedStudioPaintLayer>(layer: T, axis: "x" | "y" | "z", center = 0): T {
  const mirrored = clonePaintLayer(layer);
  const coordinate = axis === "x" ? 0 : axis === "y" ? 1 : 2;
  for (const point of mirrored.points) {
    // Reflection is its own inverse; preserve the captured local-to-clip mask.
    (point as { x: number; y: number; z: number })[axis] = center * 2 - point[axis];
    if (point.normal) point.normal[coordinate] = -point.normal[coordinate]!;
  }
  if (mirrored.mask) {
    for (let row = 0; row < 4; row++) {
      mirrored.mask.matrix[12 + row] = mirrored.mask.matrix[12 + row]! + center * 2 * mirrored.mask.matrix[coordinate * 4 + row]!;
      mirrored.mask.matrix[coordinate * 4 + row] = -mirrored.mask.matrix[coordinate * 4 + row]!;
    }
  }
  return mirrored;
}
