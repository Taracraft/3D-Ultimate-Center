import type { V6Profile } from "./profile-api.js";

export type StudioBuildPlateVisual = Readonly<{
  id: string;
  name: string;
  shortName: string;
  widthMm: number;
  depthMm: number;
  surface: "cool" | "engineering" | "high_temp" | "smooth" | "textured" | "smooth_cool" | "textured_cool" | "supertack" | "custom";
  baseColor: string;
  minorGridColor: string;
  majorGridColor: string;
  accentColor: string;
  footer: string;
}>;

const DEFAULT_WIDTH = 256;
const DEFAULT_DEPTH = 256;
const CREATED_AT = "2026-07-05T00:00:00+02:00";

function plate(id: string, name: string, surface: StudioBuildPlateVisual["surface"], footer: string): V6Profile {
  return {
    id,
    kind: "build_plate",
    name,
    source: "builtin",
    builtin: true,
    payload: { width_mm: DEFAULT_WIDTH, depth_mm: DEFAULT_DEPTH, surface, footer },
    created_at: CREATED_AT,
    updated_at: CREATED_AT,
  };
}

const BUILTIN_PLATES: readonly V6Profile[] = [
  plate("build-plate-cool", "Bambu Cool Plate", "cool", "BAMBU COOL PLATE / PLA PLATE"),
  plate("build-plate-engineering", "Bambu Engineering Plate", "engineering", "BAMBU ENGINEERING PLATE"),
  plate("build-plate-high-temp", "Bambu High Temp Plate", "high_temp", "BAMBU SMOOTH PEI PLATE / HIGH TEMP PLATE"),
  plate("build-plate-smooth-pei", "Bambu Smooth PEI Plate", "smooth", "BAMBU SMOOTH PEI PLATE"),
  plate("build-plate-textured-pei", "Bambu Textured PEI Plate", "textured", "BAMBU TEXTURED PEI PLATE"),
  plate("build-plate-smooth-cool", "Bambu Smooth Cool Plate", "smooth_cool", "BAMBU SMOOTH COOL PLATE"),
  plate("build-plate-textured-cool", "Bambu Textured Cool Plate", "textured_cool", "BAMBU TEXTURED COOL PLATE"),
  plate("build-plate-supertack", "Bambu Cool Plate SuperTack", "supertack", "BAMBU COOL PLATE SUPERTACK"),
];

function numeric(payload: Readonly<Record<string, unknown>>, keys: readonly string[], fallback: number): number {
  for (const key of keys) {
    const raw = payload[key];
    const value = Array.isArray(raw) ? Number(raw[0]) : Number(raw);
    if (Number.isFinite(value) && value > 0) return value;
  }
  return fallback;
}

function surfaceFrom(profile: V6Profile): StudioBuildPlateVisual["surface"] {
  const payloadSurface = String(profile.payload.surface || "").toLowerCase();
  const text = `${profile.id} ${profile.name} ${payloadSurface}`.toLowerCase();
  if (text.includes("supertack") || text.includes("super tack")) return "supertack";
  if (text.includes("textured cool") || text.includes("strukturierte cool")) return "textured_cool";
  if (text.includes("smooth cool") || text.includes("glatte cool")) return "smooth_cool";
  if (text.includes("high temp") || text.includes("hochtemperatur") || text.includes("ultra smooth") || text.includes("ultraglatt")) return "high_temp";
  if (text.includes("textured") || text.includes("struktur")) return "textured";
  if (text.includes("engineering")) return "engineering";
  if (text.includes("cool") || text.includes("pla plate")) return "cool";
  if (text.includes("smooth") || text.includes("pei")) return "smooth";
  return "custom";
}

function colors(surface: StudioBuildPlateVisual["surface"]): Pick<StudioBuildPlateVisual, "baseColor" | "minorGridColor" | "majorGridColor" | "accentColor" | "footer"> {
  if (surface === "cool") return { baseColor: "#465156", minorGridColor: "#747f84", majorGridColor: "#a8b4b8", accentColor: "#d9e0e2", footer: "BAMBU COOL PLATE / PLA PLATE" };
  if (surface === "engineering") return { baseColor: "#414647", minorGridColor: "#6e7475", majorGridColor: "#9da4a6", accentColor: "#d5dadd", footer: "BAMBU ENGINEERING PLATE" };
  if (surface === "high_temp") return { baseColor: "#3c4143", minorGridColor: "#6f7678", majorGridColor: "#a8afb1", accentColor: "#e1e5e6", footer: "BAMBU SMOOTH PEI PLATE / HIGH TEMP PLATE" };
  if (surface === "textured") return { baseColor: "#424747", minorGridColor: "#6c7273", majorGridColor: "#9ca2a3", accentColor: "#d5dadb", footer: "BAMBU TEXTURED PEI PLATE" };
  if (surface === "smooth_cool") return { baseColor: "#3e4c51", minorGridColor: "#6d7d83", majorGridColor: "#a1b5bc", accentColor: "#d7e6eb", footer: "BAMBU SMOOTH COOL PLATE" };
  if (surface === "textured_cool") return { baseColor: "#414d51", minorGridColor: "#707d82", majorGridColor: "#a3b4ba", accentColor: "#d8e4e8", footer: "BAMBU TEXTURED COOL PLATE" };
  if (surface === "supertack") return { baseColor: "#39463a", minorGridColor: "#667568", majorGridColor: "#96aa98", accentColor: "#d3dfd4", footer: "BAMBU COOL PLATE SUPERTACK" };
  if (surface === "smooth") return { baseColor: "#3c4143", minorGridColor: "#6f7678", majorGridColor: "#a8afb1", accentColor: "#e1e5e6", footer: "BAMBU SMOOTH PEI PLATE" };
  return { baseColor: "#3d4448", minorGridColor: "#69757b", majorGridColor: "#9bacb4", accentColor: "#d5e0e5", footer: "CUSTOM BUILD PLATE" };
}

export function studioBuildPlateVisual(profile: V6Profile | null | undefined): StudioBuildPlateVisual {
  const payload = profile?.payload ?? {};
  const surface = profile ? surfaceFrom(profile) : "smooth";
  const palette = colors(surface);
  const name = profile?.name || "Bambu Smooth PEI Plate";
  const footer = String(payload.footer || "").trim();
  return {
    id: profile?.id || "build-plate-smooth-pei",
    name,
    shortName: name.replace(/^Bambu\s+/i, "").replace(/\s+Plate$/i, " Plate"),
    widthMm: numeric(payload, ["width_mm", "bed_width", "printable_width", "x_size"], DEFAULT_WIDTH),
    depthMm: numeric(payload, ["depth_mm", "bed_depth", "printable_depth", "y_size"], DEFAULT_DEPTH),
    surface,
    ...palette,
    footer: footer || palette.footer,
  };
}

function uniqueKey(profile: V6Profile): string {
  const id = String(profile.id || "").trim().toLowerCase();
  if (id) return `id:${id}`;
  return `name:${String(profile.name || "").trim().toLowerCase()}`;
}

export function buildPlateProfiles(profiles: readonly V6Profile[]): V6Profile[] {
  const merged = new Map<string, V6Profile>();
  for (const fallback of BUILTIN_PLATES) merged.set(uniqueKey(fallback), fallback);
  for (const profile of profiles) {
    if (profile.kind !== "build_plate") continue;
    merged.set(uniqueKey(profile), profile);
  }
  return [...merged.values()].sort((left, right) => left.name.localeCompare(right.name, "de", { sensitivity: "base" }));
}
