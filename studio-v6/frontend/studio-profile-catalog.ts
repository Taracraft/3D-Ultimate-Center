import type {
  ProfileKind,
  V6Profile,
  V6ProfileCatalog,
  V6ProfileSelection,
} from "./profile-api.js";
import {
  studioBuildPlateVisual,
  type StudioBuildPlateVisual,
} from "./studio-build-plates.js";

export type StudioPlateProfileSelection = {
  target_printer_id: string;
  printer_profile_id: string;
  nozzle_profile_id: string;
  process_profile_id: string;
  build_plate_profile_id: string;
  filament_profile_ids: string[];
};

export type CatalogBuildPlateProfile = Readonly<{
  id: string;
  name: string;
  widthMm: number;
  depthMm: number;
}>;

function text(value: unknown): string {
  return String(value ?? "").trim();
}

function numberValue(value: unknown, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => text(item)).filter(Boolean);
}

function canonicalKey(profile: V6Profile): string {
  const payload = profile.payload;
  if (profile.kind === "build_plate") {
    return [
      profile.kind,
      text(payload.surface || payload.plate_type || payload.type || profile.name).toLocaleLowerCase("de-DE"),
      numberValue(payload.width_mm, 256),
      numberValue(payload.depth_mm, 256),
    ].join("|");
  }
  if (profile.kind === "nozzle") {
    return [profile.kind, numberValue(payload.diameter_mm, .4), text(payload.material).toLocaleLowerCase("de-DE")].join("|");
  }
  if (profile.kind === "printer") {
    return [profile.kind, text(payload.vendor), text(payload.model || profile.name)].join("|").toLocaleLowerCase("de-DE");
  }
  if (profile.kind === "filament") {
    return [profile.kind, text(payload.vendor), text(payload.material), text(payload.sub_brand || profile.name)].join("|").toLocaleLowerCase("de-DE");
  }
  return [profile.kind, text(profile.name)].join("|").toLocaleLowerCase("de-DE");
}

function sourcePriority(profile: V6Profile): number {
  if (profile.source === "local") return 0;
  if (profile.source === "bambu_cloud") return 1;
  if (profile.builtin) return 2;
  return 3;
}

export function uniqueStudioProfiles(catalog: V6ProfileCatalog | null, kind: ProfileKind): V6Profile[] {
  const input = catalog?.groups[kind] ?? [];
  const selected = new Map<string, V6Profile>();
  for (const profile of input) {
    const key = canonicalKey(profile);
    const existing = selected.get(key);
    if (!existing || sourcePriority(profile) < sourcePriority(existing)) selected.set(key, profile);
  }
  return [...selected.values()].sort((left, right) => left.name.localeCompare(right.name, "de-DE", { numeric: true }));
}

export function profileById(catalog: V6ProfileCatalog | null, id: string): V6Profile | null {
  return catalog?.profiles.find((profile) => profile.id === id) ?? null;
}

export function initialStudioSelection(catalog: V6ProfileCatalog | null): StudioPlateProfileSelection {
  const selection = catalog?.selection;
  return {
    target_printer_id: "",
    printer_profile_id: selection?.printer_profile_id ?? "",
    nozzle_profile_id: selection?.nozzle_profile_id ?? "",
    process_profile_id: selection?.process_profile_id ?? "",
    build_plate_profile_id: selection?.build_plate_profile_id ?? "",
    filament_profile_ids: [...(selection?.filament_profile_ids ?? [])],
  };
}

export function selectionPatch(selection: StudioPlateProfileSelection): V6ProfileSelection {
  return {
    printer_profile_id: selection.printer_profile_id || null,
    nozzle_profile_id: selection.nozzle_profile_id || null,
    process_profile_id: selection.process_profile_id || null,
    build_plate_profile_id: selection.build_plate_profile_id || null,
    filament_profile_ids: [...selection.filament_profile_ids],
  };
}

export function buildPlateProfileFromCatalog(profile: V6Profile): CatalogBuildPlateProfile {
  const visual = studioBuildPlateVisual(profile);
  return {
    id: profile.id,
    name: profile.name,
    widthMm: visual.widthMm,
    depthMm: visual.depthMm,
  };
}

export function plateVisualFromCatalog(catalog: V6ProfileCatalog | null, profileId: string): StudioBuildPlateVisual {
  const profiles = uniqueStudioProfiles(catalog, "build_plate");
  const profile = profiles.find((item) => item.id === profileId) ?? profiles[0] ?? null;
  return studioBuildPlateVisual(profile);
}

export function profileDisplayName(profile: V6Profile): string {
  const source = profile.source === "local" ? "Lokal" : profile.source === "bambu_cloud" ? "Cloud" : "Standard";
  return `${profile.name} · ${source}`;
}

export function filamentColor(profile: V6Profile, fallback: string): string {
  const payload = profile.payload;
  const values = [
    payload.color,
    payload.colour,
    payload.default_color,
    payload.display_color,
    ...stringList(payload.colors),
    ...stringList(payload.filament_colour),
  ];
  for (const value of values) {
    const raw = text(value).replace(/^#/, "");
    if (/^[0-9a-f]{6}([0-9a-f]{2})?$/i.test(raw)) return `#${raw.slice(0, 6).toLowerCase()}`;
  }
  return fallback;
}

export function printerBuildVolume(profile: V6Profile | null): readonly [number, number, number] {
  const payload = profile?.payload ?? {};
  const volume = Array.isArray(payload.build_volume_mm) ? payload.build_volume_mm : [];
  return [
    numberValue(volume[0] ?? payload.width_mm, 256),
    numberValue(volume[1] ?? payload.depth_mm, 256),
    numberValue(volume[2] ?? payload.height_mm, 256),
  ];
}