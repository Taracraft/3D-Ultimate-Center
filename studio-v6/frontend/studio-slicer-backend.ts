const LEGACY_PREFIX = "ultimate-3d-studio-v6:slicer-backend:plate:";

export function removeLegacyPlateSlicerBackend(plateId: number | string): void {
  localStorage.removeItem(`${LEGACY_PREFIX}${plateId}`);
}
