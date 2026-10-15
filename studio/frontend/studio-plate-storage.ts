import { PROCESS_OPTIONS_PLATE_PREFIX, PURGE_TOWER_PLATE_PREFIX } from "./studio-plate-storage-keys.js";

export type StudioPlateLocalSettings = Readonly<{ processOptions: string | null; purgeTower: string | null }>;

export function readPlateLocalSettings(plateId: number): StudioPlateLocalSettings | undefined {
  if (!("localStorage" in globalThis)) return undefined;
  return {
    processOptions: localStorage.getItem(PROCESS_OPTIONS_PLATE_PREFIX + plateId),
    purgeTower: localStorage.getItem(PURGE_TOWER_PLATE_PREFIX + plateId),
  };
}

/** Stage every key before writing: a shifted plate must never read its predecessor's options. */
export function writePlateLocalSettings(
  entries: readonly (readonly [number, StudioPlateLocalSettings])[],
  removedPlateIds: readonly number[] = [],
): void {
  if (!("localStorage" in globalThis)) return;
  const changes = new Map<string, string | null>();
  for (const id of removedPlateIds) {
    changes.set(PROCESS_OPTIONS_PLATE_PREFIX + id, null);
    changes.set(PURGE_TOWER_PLATE_PREFIX + id, null);
  }
  for (const [id, settings] of entries) {
    changes.set(PROCESS_OPTIONS_PLATE_PREFIX + id, settings.processOptions);
    changes.set(PURGE_TOWER_PLATE_PREFIX + id, settings.purgeTower);
  }
  const previous = new Map([...changes.keys()].map((key) => [key, localStorage.getItem(key)]));
  const put = (key: string, value: string | null): void => {
    if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value);
  };
  try {
    for (const [key, value] of changes) put(key, value);
  } catch (error) {
    for (const [key, value] of previous) put(key, value);
    throw error;
  }
}

export function reindexPlateLocalSettings(previousIds: readonly number[], survivingIds: readonly number[]): void {
  const staged = survivingIds.map((id, index) => [index, readPlateLocalSettings(id)] as const)
    .filter((entry): entry is readonly [number, StudioPlateLocalSettings] => entry[1] !== undefined);
  writePlateLocalSettings(staged, previousIds);
}
