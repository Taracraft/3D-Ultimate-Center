type HassEntity = Readonly<{
  state?: string;
  attributes?: Readonly<Record<string, unknown>>;
}>;

type HassLike = Readonly<{
  states?: Readonly<Record<string, HassEntity>>;
}>;

const MATERIAL_SYSTEM_STATE_SUFFIXES = [
  "_configured_ams_type",
  "_detected_ams_type",
] as const;

function text(value: unknown): string {
  return String(value ?? "").trim();
}

export function materialSystemHassSignature(hass: HassLike | null): string {
  const states = hass?.states ?? {};
  return JSON.stringify(
    Object.entries(states)
      .filter(([entityId]) => MATERIAL_SYSTEM_STATE_SUFFIXES.some((suffix) => entityId.endsWith(suffix)))
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([entityId, entity]) => [
        entityId,
        text(entity.state),
        text(entity.attributes?.friendly_name),
      ]),
  );
}
