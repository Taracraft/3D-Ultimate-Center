import { sceneStore } from "./scene-store.js";
import { getStudioGeometry } from "./studio-session.js";
import {
  export3mf,
  type ThreeMfMesh,
  type ThreeMfMetadata,
} from "./three-mf-export.js";

function safeName(value: string): string {
  const cleaned = value.replace(/[\\/:*?"<>|]+/g, "_").trim();
  return `${cleaned || "3D-Studio-Projekt"}.3mf`;
}

export function createActiveStudio3mf(): File {
  const state = sceneStore.getState();
  const plate = state.plates.find((item) => item.id === state.activePlateId)
    ?? state.plates[0]
    ?? null;
  if (!plate) throw new Error("Es ist keine aktive Druckplatte vorhanden.");

  const meshes: ThreeMfMesh[] = plate.objects.flatMap((object) => {
    const record = getStudioGeometry(object.id);
    if (!record || !object.visible) return [];
    return [{
      name: object.name,
      geometry: record.geometry,
      transform: object.transform,
      color: object.color || "#38AEE8",
    }];
  });

  const metadata: ThreeMfMetadata = {
    title: plate.name,
    description: `${meshes.length} Objekt(e) aus Ultimate 3D Studio V6`,
    buildPlateName: plate.name,
    ...(plate.buildPlateProfileId
      ? { buildPlateProfileId: plate.buildPlateProfileId }
      : {}),
    ...(plate.widthMm !== undefined
      ? { plateWidthMm: plate.widthMm }
      : {}),
    ...(plate.depthMm !== undefined
      ? { plateDepthMm: plate.depthMm }
      : {}),
  };
  const buffer = export3mf(meshes, metadata);
  return new File([buffer], safeName(plate.name), { type: "model/3mf" });
}

export function downloadActiveStudio3mf(): File {
  const file = createActiveStudio3mf();
  const url = URL.createObjectURL(file);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.name;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  return file;
}