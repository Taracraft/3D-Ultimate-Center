import type { SlicerBackend } from "./slicing-api.js";

const LEGACY_PREFIX = "ultimate-3d-studio-v6:slicer-backend:plate:";

export function loadPlateSlicerBackend(plateId: number | string): SlicerBackend {
  localStorage.removeItem(`${LEGACY_PREFIX}${plateId}`);
  return "server";
}

export function savePlateSlicerBackend(plateId: number | string, _value: SlicerBackend): void {
  localStorage.removeItem(`${LEGACY_PREFIX}${plateId}`);
}
