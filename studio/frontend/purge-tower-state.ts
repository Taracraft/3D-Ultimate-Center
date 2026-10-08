import { PURGE_TOWER_PLATE_PREFIX } from "./studio-plate-storage-keys.js";
import type { SliceMaterialPlan } from "./plate-slice-api.js";
import type { SlicePurgeTower } from "./slicing-api.js";

const PREFIX = PURGE_TOWER_PLATE_PREFIX;

function numberInRange(value: unknown, fallback: number, minimum: number, maximum: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(minimum, Math.min(maximum, parsed)) : fallback;
}

export function loadPlatePurgeTower(plateId: number | string): SlicePurgeTower {
  try {
    const raw = localStorage.getItem(`${PREFIX}${plateId}`);
    const value = raw ? JSON.parse(raw) as Record<string, unknown> : {};
    return {
      enabled: value.enabled !== false,
      width_mm: numberInRange(value.width_mm, 35, 10, 80),
      brim_width_mm: numberInRange(value.brim_width_mm, 3, 0, 20),
      position_x: numberInRange(value.position_x, 205, 0, 256),
      position_y: numberInRange(value.position_y, 205, 0, 256),
      flush_multiplier: numberInRange(value.flush_multiplier, 1, .1, 3),
    };
  } catch {
    return {
      enabled: true,
      width_mm: 35,
      brim_width_mm: 3,
      position_x: 205,
      position_y: 205,
      flush_multiplier: 1,
    };
  }
}

export function savePlatePurgeTower(plateId: number | string, value: SlicePurgeTower): void {
  localStorage.setItem(`${PREFIX}${plateId}`, JSON.stringify(value));
}

export function mergePlatePurgeTower(
  plan: SliceMaterialPlan | undefined,
  plateId: number | string | undefined,
): SliceMaterialPlan | undefined {
  if (!plan || plateId === undefined) return plan;

  const usedExtruders = new Set(
    Object.values(plan.assignments).filter((value) => Number(value) > 0),
  );
  const stored = loadPlatePurgeTower(plateId);
  const position = {
    ...(stored.position_x !== undefined ? { position_x: stored.position_x } : {}),
    ...(stored.position_y !== undefined ? { position_y: stored.position_y } : {}),
  };

  return {
    ...plan,
    purge_tower: {
      ...stored,
      ...plan.purge_tower,
      ...position,
      enabled: usedExtruders.size > 1 && stored.enabled !== false,
    },
  };
}
