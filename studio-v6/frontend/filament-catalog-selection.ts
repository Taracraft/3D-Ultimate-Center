import type { ManualA1FilamentProfile, FilamentSettingTargetKind } from "./direct-print-status-api.js";

export function filamentsForTarget(
  items: readonly ManualA1FilamentProfile[],
  kind: FilamentSettingTargetKind,
): ManualA1FilamentProfile[] {
  return items.filter((item) => item.targets.includes(kind));
}

export function vendorsForTarget(
  items: readonly ManualA1FilamentProfile[],
  kind: FilamentSettingTargetKind,
): string[] {
  return [...new Set(filamentsForTarget(items, kind).map((item) => item.vendor))]
    .sort((left, right) => left.localeCompare(right, "de-DE"));
}

export function resolveFilamentSelection(
  items: readonly ManualA1FilamentProfile[],
  kind: FilamentSettingTargetKind,
  currentId: string,
  currentMaterial: string,
  requestedVendor = "",
  requestedId = "",
): ManualA1FilamentProfile | null {
  const allowed = filamentsForTarget(items, kind);
  return allowed.find((item) => item.id === requestedId)
    ?? allowed.find((item) => item.id === currentId)
    ?? allowed.find((item) => item.vendor === requestedVendor)
    ?? allowed.find((item) => item.material_type.toUpperCase() === currentMaterial.trim().toUpperCase())
    ?? allowed[0]
    ?? null;
}
