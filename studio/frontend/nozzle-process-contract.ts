export type NozzleProcessContract = Readonly<{
  diameter_mm: number;
  min_layer_height_mm: number;
  max_layer_height_mm: number;
  default_layer_height_mm: number;
  default_outer_wall_speed_mm_s: number;
  default_inner_wall_speed_mm_s: number;
  max_wall_speed_mm_s: number;
}>;

export type NozzleProcessValues = Readonly<{
  layer_height_mm: number | null;
  outer_wall_speed_mm_s: number | null;
  inner_wall_speed_mm_s: number | null;
}>;

const PROCESS_OPTIONS_KEY = "ultimate-3d-studio:slicer-process-options";
const NOZZLE_PROCESS_CONTRACTS: readonly NozzleProcessContract[] = [
  { diameter_mm: .2, min_layer_height_mm: .04, max_layer_height_mm: .14, default_layer_height_mm: .1, default_outer_wall_speed_mm_s: 120, default_inner_wall_speed_mm_s: 150, max_wall_speed_mm_s: 500 },
  { diameter_mm: .4, min_layer_height_mm: .08, max_layer_height_mm: .28, default_layer_height_mm: .2, default_outer_wall_speed_mm_s: 200, default_inner_wall_speed_mm_s: 300, max_wall_speed_mm_s: 500 },
  { diameter_mm: .6, min_layer_height_mm: .12, max_layer_height_mm: .42, default_layer_height_mm: .3, default_outer_wall_speed_mm_s: 120, default_inner_wall_speed_mm_s: 150, max_wall_speed_mm_s: 500 },
  { diameter_mm: .8, min_layer_height_mm: .16, max_layer_height_mm: .56, default_layer_height_mm: .4, default_outer_wall_speed_mm_s: 120, default_inner_wall_speed_mm_s: 150, max_wall_speed_mm_s: 500 },
];

function optionalNumber(value: unknown, minimum: number, maximum: number): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : null;
}

export function loadNozzleProcessValues(): NozzleProcessValues {
  try {
    const raw = localStorage.getItem(PROCESS_OPTIONS_KEY);
    const value = raw ? JSON.parse(raw) as Record<string, unknown> : {};
    return {
      layer_height_mm: optionalNumber(value.layer_height_mm, .04, .56),
      outer_wall_speed_mm_s: optionalNumber(value.outer_wall_speed_mm_s, 1, 500),
      inner_wall_speed_mm_s: optionalNumber(value.inner_wall_speed_mm_s, 1, 500),
    };
  } catch {
    return { layer_height_mm: null, outer_wall_speed_mm_s: null, inner_wall_speed_mm_s: null };
  }
}

export function nozzleProcessContract(diameterMm: unknown): NozzleProcessContract | null {
  const diameter = Number(diameterMm);
  return NOZZLE_PROCESS_CONTRACTS.find((item) => Math.abs(item.diameter_mm - diameter) < .000001) ?? null;
}

export function processOverrideValidationError(
  value: NozzleProcessValues,
  diameterMm: unknown,
): string | null {
  const contract = nozzleProcessContract(diameterMm);
  if (!contract) return "Für die gewählte Düse ist kein validiertes A1-Slicerprofil installiert.";
  if (value.layer_height_mm !== null && (
    !Number.isFinite(value.layer_height_mm)
    || value.layer_height_mm < contract.min_layer_height_mm
    || value.layer_height_mm > contract.max_layer_height_mm
  )) {
    return `Die Schichthöhe für ${contract.diameter_mm.toLocaleString("de-DE")} mm Düse muss zwischen ${contract.min_layer_height_mm.toLocaleString("de-DE")} und ${contract.max_layer_height_mm.toLocaleString("de-DE")} mm liegen.`;
  }
  for (const [label, speed] of [
    ["Außenwand", value.outer_wall_speed_mm_s],
    ["Innenwand", value.inner_wall_speed_mm_s],
  ] as const) {
    if (speed !== null && (!Number.isFinite(speed) || speed < 1 || speed > contract.max_wall_speed_mm_s)) {
      return `${label}: Die Geschwindigkeit muss zwischen 1 und ${contract.max_wall_speed_mm_s.toLocaleString("de-DE")} mm/s liegen.`;
    }
  }
  return null;
}
