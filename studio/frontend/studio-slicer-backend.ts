const LEGACY_PREFIX = "ultimate-3d-studio:slicer-backend:plate:";

export function removeLegacyPlateSlicerBackend(plateId: number | string): void {
  localStorage.removeItem(`${LEGACY_PREFIX}${plateId}`);
}
