import type { PaintRegion } from "./studio-mesh-paint.js";
import { composePaintLayers, refinePaintLayers, type MaterialPaintLayer } from "./studio-paint-layers.js";
import { geometryFromPositions } from "./studio-mesh-tools.js";
import type { MeshInstance } from "./webgl-studio-viewport.js";
import type { ThreeMfMesh } from "./three-mf-export.js";

/** Prepare an export on private geometry/region values; never bake into the editing session. */
export function preparePaintedExport(
  selected: readonly MeshInstance[],
  baseRegions: readonly PaintRegion[],
  layers: readonly MaterialPaintLayer[],
  legacyIds: ReadonlySet<string>,
): Readonly<{ instances: MeshInstance[]; regions: readonly PaintRegion[] }> {
  const selectedIds = new Set(selected.map((item) => item.id));
  const selectedLayers = layers.filter((layer) => selectedIds.has(layer.objectId));
  let regions: readonly PaintRegion[] = baseRegions.filter((region) => selectedIds.has(region.objectId));
  const instances = selected.map((item) => {
    if (legacyIds.has(item.id)) return { ...item };
    const scale = Math.max(...item.scale.map(Math.abs));
    if (!Number.isFinite(scale) || scale <= 0) throw new Error("Ein ausgewähltes Objekt hat eine ungültige Skalierung.");
    const refined = refinePaintLayers(item.id, item.geometry, regions, selectedLayers, .35 / scale);
    regions = refined.regions;
    return { ...item, geometry: refined.changed ? geometryFromPositions(refined.positions) : item.geometry };
  });
  const normal = instances.filter((item) => !legacyIds.has(item.id));
  const legacy = instances.filter((item) => legacyIds.has(item.id));
  return {
    instances,
    regions: [
      ...composePaintLayers(normal, regions, selectedLayers),
      ...composePaintLayers(legacy, [], selectedLayers, { legacy: true }),
    ],
  };
}

/** One face/material contract for selected-object downloads and printer-bound plate exports. */
export function buildPaintedExportMeshes(
  instances: readonly MeshInstance[],
  regions: readonly PaintRegion[],
  objectMaterials: ReadonlyMap<string, number>,
  paintMaterials: ReadonlyMap<string, number>,
  materialCount: number,
): ThreeMfMesh[] {
  const validMaterial = (index: number | undefined): index is number => Number.isInteger(index) && index! >= 0 && index! < materialCount;
  const byObject = new Map<string, PaintRegion[]>();
  for (const region of regions) {
    const entries = byObject.get(region.objectId) || [];
    entries.push(region); byObject.set(region.objectId, entries);
  }
  return instances.map((item): ThreeMfMesh => {
    const materialIndex = objectMaterials.get(item.id);
    if (!validMaterial(materialIndex)) throw new Error(`Objekt ${item.name} hat keine gültige Exportmaterialzuordnung.`);
    if (!Number.isInteger(item.geometry.triangleCount) || item.geometry.positions.length !== item.geometry.triangleCount * 9) throw new Error(`Objekt ${item.name} enthält unvollständige Dreiecke.`);
    const triangleMaterialIndices: Array<number | null> = Array.from({ length: item.geometry.triangleCount }, () => null);
    for (const region of byObject.get(item.id) || []) {
      const mapped = paintMaterials.get(region.materialKey);
      if (!validMaterial(mapped)) throw new Error("Ein Malbereich verweist auf kein eindeutig zugeordnetes Exportmaterial.");
      for (const triangle of region.triangleIndices) {
        if (!Number.isInteger(triangle) || triangle < 0 || triangle >= item.geometry.triangleCount) throw new Error(`Malbereich von ${item.name} enthält eine ungültige Dreiecksreferenz.`);
        const previous = triangleMaterialIndices[triangle];
        if (previous !== null && previous !== mapped) throw new Error("Eine Dreiecksfläche verweist auf mehrere Exportmaterialien.");
        triangleMaterialIndices[triangle] = mapped;
      }
    }
    return { name: item.name, geometry: item.geometry, transform: { position: [...item.position], rotation: [...item.rotation], scale: [...item.scale] }, color: item.color, materialIndex, triangleMaterialIndices };
  });
}

/** A portable file palette preserves known identities/colors without assigning any printer job. */
export function localExportMaterialPlan(
  instances: readonly MeshInstance[],
  regions: readonly PaintRegion[],
  assignments: ReadonlyMap<string, string>,
  choices: readonly Readonly<{ key: string; name: string; color: string }>[],
): Readonly<{ materials: Array<{ name: string; color: string }>; objectMaterials: Map<string, number>; paintMaterials: Map<string, number> }> {
  const available = new Map(choices.map((choice) => [choice.key, choice]));
  const materials: Array<{ name: string; color: string }> = [];
  const indexes = new Map<string, number>();
  const register = (key: string, fallbackName: string, fallbackColor: string): number => {
    const choice = available.get(key);
    const color = (choice?.color || fallbackColor).toLowerCase();
    if (!/^#[0-9a-f]{6}$/.test(color)) throw new Error("Ein Exportmaterial enthält keine gültige gespeicherte Farbe.");
    const previous = indexes.get(key);
    if (previous !== undefined) {
      if (materials[previous]!.color !== color) throw new Error("Eine gespeicherte Materialkennung enthält widersprüchliche Farben. Vor dem Export eindeutig zuordnen.");
      return previous;
    }
    const index = materials.length;
    indexes.set(key, index);
    materials.push({ name: choice?.name || fallbackName, color });
    return index;
  };
  const objectMaterials = new Map(instances.map((item) => {
    const key = assignments.get(item.id) || `object\u0000${item.id}`;
    return [item.id, register(key, item.name, item.color)] as const;
  }));
  const paintMaterials = new Map<string, number>();
  for (const region of regions) {
    const key = String(region.materialKey || "").trim();
    if (!key) throw new Error("Ein Malbereich hat keine eindeutige gespeicherte Materialkennung.");
    paintMaterials.set(key, register(key, `${region.label || "Malbereich"} · ${key}`, region.color));
  }
  return { materials, objectMaterials, paintMaterials };
}
