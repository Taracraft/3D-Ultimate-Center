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
  const material = currentMaterial.trim().toUpperCase();
  const matchesMaterial = (item: ManualA1FilamentProfile): boolean => {
    const candidate = item.material_type.trim().toUpperCase();
    return !material || candidate === material || (material === "TPU" && candidate === "TPU-AMS");
  };
  const explicit = allowed.find((item) => item.id === requestedId);
  if (explicit) return explicit;
  if (requestedVendor) {
    return allowed.find((item) => item.vendor === requestedVendor && matchesMaterial(item))
      ?? (material ? null : allowed.find((item) => item.vendor === requestedVendor))
      ?? null;
  }
  const compatible = allowed.filter(matchesMaterial);
  return compatible.find((item) => item.id === currentId) ?? compatible[0] ?? null;
}
