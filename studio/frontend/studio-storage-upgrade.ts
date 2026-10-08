/** Version-independent discovery; completed copies retain a recoverable archive. */
export const STUDIO_DATABASE = "ultimate-3d-studio";
export const STUDIO_DATABASE_VERSION = 2;
const WORKSPACE = "workspace";
const MIGRATIONS = "storage_migrations";
const RECEIPT = "workspace-import";
const PREFIX = `${STUDIO_DATABASE}:`;

type PreferenceStorage = Pick<Storage, "length" | "key" | "getItem" | "setItem" | "removeItem">;
type LegacyPreference = { key: string; version: number; value: string };
export type PreferenceUpgrade = { value: string | null; copied: boolean; error: string };

export function legacyPreferences(storage: PreferenceStorage, target: string): LegacyPreference[] {
  if (!target.startsWith(PREFIX)) return [];
  const suffix = target.slice(PREFIX.length);
  const result: LegacyPreference[] = [];
  for (let index = 0; index < storage.length; index++) {
    const key = storage.key(index);
    const match = key?.match(/^ultimate-3d-studio-v(\d+):(.*)$/);
    if (!key || !match || match[2] !== suffix) continue;
    const version = Number(match[1]);
    const value = storage.getItem(key);
    if (Number.isSafeInteger(version) && version > 0 && value !== null) result.push({ key, version, value });
  }
  return result.sort((a, b) => b.version - a.version);
}

export function upgradeStudioPreference(storage: PreferenceStorage, target: string): PreferenceUpgrade {
  const current = storage.getItem(target);
  const sources = legacyPreferences(storage, target);
  const first = sources[0];
  if (!first) return { value: current, copied: false, error: "" };
  const chosen = current ?? first.value;
  const backupKey = `${target}:migration-backup`;
  const priorBackup = storage.getItem(backupKey);
  let encoded = "";
  try {
    const prior = priorBackup ? JSON.parse(priorBackup) : { format: 1, values: [] };
    if (prior.format !== 1 || !Array.isArray(prior.values)) throw new Error("Unbekanntes Sicherungsformat.");
    const values = [...prior.values];
    for (const source of sources) {
      if (!values.some((item) => item.version === source.version && item.value === source.value)) {
        values.push({ version: source.version, value: source.value });
      }
    }
    encoded = JSON.stringify({ format: 1, values });
    storage.setItem(backupKey, encoded);
    if (storage.getItem(backupKey) !== encoded) throw new Error("Sicherung konnte nicht zurückgelesen werden.");
    if (current === null) storage.setItem(target, chosen);
    if (storage.getItem(target) !== chosen) throw new Error("Übernahme konnte nicht zurückgelesen werden.");
    if (sources.some((source) => storage.getItem(source.key) !== source.value)) throw new Error("Einstellungen wurden gleichzeitig geändert.");
    for (const source of sources) {
      storage.removeItem(source.key);
      if (storage.getItem(source.key) !== null) throw new Error("Alter Speicher konnte nicht abgeschlossen werden.");
    }
    return { value: chosen, copied: true, error: "" };
  } catch (error) {
    // Free our new copy before restoring removed originals, including quota failures.
    try { if (current === null && storage.getItem(target) === chosen) storage.removeItem(target); } catch {}
    for (const source of sources) {
      try { if (storage.getItem(source.key) === null) storage.setItem(source.key, source.value); } catch {}
    }
    try {
      if (storage.getItem(backupKey) === encoded) {
        if (priorBackup === null) storage.removeItem(backupKey);
        else storage.setItem(backupKey, priorBackup);
      }
    } catch {}
    return { value: chosen, copied: false, error: error instanceof Error ? error.message : String(error) };
  }
}

export function readStudioPreference(target: string): string | null {
  const result = upgradeStudioPreference(globalThis.localStorage, target);
  if (result.error) preferenceWarning = true;
  return result.value;
}

let preferenceWarning = false;
export function studioStorageWarning(): string {
  return preferenceWarning ? "Einige gespeicherte Einstellungen konnten nicht vollständig übernommen werden. Ihre bisherigen Werte bleiben erhalten. Bitte Browser-Speicher freigeben und erneut laden." : "";
}

export function upgradeAllStudioPreferences(storage: PreferenceStorage): PreferenceUpgrade[] {
  const targets = new Set<string>();
  for (let index = 0; index < storage.length; index++) {
    const match = storage.key(index)?.match(/^ultimate-3d-studio-v\d+:(.*)$/);
    if (match) targets.add(PREFIX + match[1]);
  }
  return [...targets].map((target) => upgradeStudioPreference(storage, target));
}

// Run before dependent modules construct stores or read per-plate selections.
try {
  if (typeof window !== "undefined" && globalThis.localStorage) {
    preferenceWarning = upgradeAllStudioPreferences(globalThis.localStorage).some((result) => Boolean(result.error));
  }
} catch { preferenceWarning = true; }

export function legacyDatabaseVersion(name: string): number | null {
  const match = name.match(/^ultimate-3d-studio-v(\d+)$/);
  const version = match ? Number(match[1]) : NaN;
  return Number.isSafeInteger(version) && version > 0 ? version : null;
}

export function storageValuesEqual(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (left instanceof ArrayBuffer && right instanceof ArrayBuffer) {
    const a = new Uint8Array(left), b = new Uint8Array(right);
    return a.length === b.length && a.every((value, index) => value === b[index]);
  }
  if (ArrayBuffer.isView(left) && ArrayBuffer.isView(right)) {
    return left.constructor === right.constructor && storageValuesEqual(
      left.buffer.slice(left.byteOffset, left.byteOffset + left.byteLength),
      right.buffer.slice(right.byteOffset, right.byteOffset + right.byteLength),
    );
  }
  if (left instanceof Date && right instanceof Date) return left.getTime() === right.getTime();
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right) && left.length === right.length
      && left.every((value, index) => storageValuesEqual(value, right[index]));
  }
  if (!left || !right || typeof left !== "object" || typeof right !== "object") return false;
  const a = left as Record<string, unknown>, b = right as Record<string, unknown>;
  const plain = (value: object) => Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null;
  if (!plain(a) || !plain(b)) return false;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length
    && keys.every((key) => Object.hasOwn(b, key) && storageValuesEqual(a[key], b[key]));
}

export type WorkspaceArchive = { legacyVersion: number; databaseVersion: number; keys: IDBValidKey[]; values: unknown[] };

/** Rebind only persisted plate foreign keys; geometry and raw archives are retained. */
export function upgradeWorkspaceJobReferences(value: unknown, legacyVersion: number): unknown {
  if (!Number.isSafeInteger(legacyVersion) || legacyVersion < 1 || !value || typeof value !== "object") return value;
  const workspace = value as { version?: unknown; plates?: unknown };
  if (workspace.version !== 1 || !Array.isArray(workspace.plates)) return value;
  const delimited = new RegExp(`(^|[^A-Za-z0-9])v${legacyVersion}(?=$|[^A-Za-z0-9])`, "gi");
  const earlyPrefix = new RegExp(`^v${legacyVersion}(?=[a-z])`, "i");
  let changed = false;
  const plates = workspace.plates.map((plate: unknown) => {
    if (!plate || typeof plate !== "object" || Array.isArray(plate)) return plate;
    const row = plate as { jobId?: unknown };
    if (typeof row.jobId !== "string" || !/^[A-Za-z0-9_-]{1,200}$/.test(row.jobId)) return plate;
    const jobId = row.jobId.replace(delimited, "$1studio").replace(earlyPrefix, "studio");
    if (jobId === row.jobId) return plate;
    changed = true;
    return { ...plate, jobId };
  });
  return changed ? { ...value, plates } : value;
}

export function latestLegacyWorkspace(archives: readonly WorkspaceArchive[]): unknown | null {
  const candidates = archives.flatMap((archive) => {
    const index = archive.keys.findIndex((key) => key === "active");
    const value = index < 0 ? null : archive.values[index];
    if (!value || typeof value !== "object") return [];
    const row = value as { version?: unknown; savedAt?: unknown };
    if (row.version !== 1 || !Number.isFinite(row.savedAt) || Number(row.savedAt) < 0) return [];
    return [{ value, savedAt: Number(row.savedAt), legacyVersion: archive.legacyVersion }];
  });
  candidates.sort((a, b) => b.savedAt - a.savedAt || b.legacyVersion - a.legacyVersion);
  const chosen = candidates[0];
  return chosen ? upgradeWorkspaceJobReferences(chosen.value, chosen.legacyVersion) : null;
}

function open(factory: IDBFactory, name: string, current: boolean): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = current ? factory.open(name, STUDIO_DATABASE_VERSION) : factory.open(name);
    let settled = false;
    const timer = setTimeout(() => fail(new Error("Browser-Speicher ist durch eine andere Sitzung blockiert.")), 15_000);
    const fail = (error: Error | DOMException) => { if (!settled) { settled = true; clearTimeout(timer); reject(error); } };
    request.onupgradeneeded = () => {
      if (!current) { request.transaction?.abort(); return; }
      const database = request.result;
      if (!database.objectStoreNames.contains(WORKSPACE)) database.createObjectStore(WORKSPACE);
      if (!database.objectStoreNames.contains(MIGRATIONS)) database.createObjectStore(MIGRATIONS);
    };
    request.onsuccess = () => {
      if (settled) { request.result.close(); return; }
      settled = true; clearTimeout(timer);
      request.result.onversionchange = () => request.result.close();
      resolve(request.result);
    };
    request.onerror = () => fail(request.error ?? new Error("Browser-Speicher konnte nicht geöffnet werden."));
    request.onblocked = () => fail(new Error("Bitte andere Studio-Sitzungen schließen und erneut laden."));
  });
}

function complete(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = transaction.onerror = () => reject(transaction.error ?? new Error("Speicherübernahme wurde abgebrochen."));
  });
}

function get<T>(database: IDBDatabase, store: string, key: IDBValidKey): Promise<T | undefined> {
  return new Promise((resolve, reject) => {
    const request = database.transaction(store, "readonly").objectStore(store).get(key);
    request.onsuccess = () => resolve(request.result as T | undefined);
    request.onerror = () => reject(request.error ?? new Error("Speicher konnte nicht gelesen werden."));
  });
}

async function archive(factory: IDBFactory, name: string, legacyVersion: number): Promise<WorkspaceArchive> {
  const database = await open(factory, name, false);
  try {
    if (database.objectStoreNames.length !== 1 || !database.objectStoreNames.contains(WORKSPACE)) {
      throw new Error("Bestehender Studio-Speicher benötigt eine gesonderte Übernahme; Daten bleiben erhalten.");
    }
    const transaction = database.transaction(WORKSPACE, "readonly");
    const done = complete(transaction);
    const store = transaction.objectStore(WORKSPACE);
    const keys = store.getAllKeys(), values = store.getAll();
    await done;
    return { legacyVersion, databaseVersion: database.version, keys: keys.result, values: values.result };
  } finally { database.close(); }
}

async function migrateWorkspace(factory: IDBFactory): Promise<void> {
  const database = await open(factory, STUDIO_DATABASE, true);
  try {
    const receipt = await get<{ phase: string; archives: WorkspaceArchive[]; importedWorkspace: boolean }>(database, MIGRATIONS, RECEIPT);
    if (receipt?.phase === "verified") return;
    if (receipt && receipt.phase !== "copied") throw new Error("Unbekannter Übernahmestand; bestehende Daten bleiben erhalten.");
    const current = await get<unknown>(database, WORKSPACE, "active");
    let archives = receipt?.archives;
    if (!archives) {
      if (typeof factory.databases !== "function" && current === undefined) {
        throw new Error("Dieser Browser kann bestehende Studio-Speicher nicht automatisch ermitteln. Bestehende Daten bleiben erhalten.");
      }
      archives = [];
      for (const info of typeof factory.databases === "function" ? await factory.databases() : []) {
        const version = info.name ? legacyDatabaseVersion(info.name) : null;
        if (info.name && version !== null) archives.push(await archive(factory, info.name, version));
      }
    }
    const chosen = latestLegacyWorkspace(archives);
    if (!receipt) {
      const transaction = database.transaction([WORKSPACE, MIGRATIONS], "readwrite");
      const done = complete(transaction);
      const request = transaction.objectStore(MIGRATIONS).get(RECEIPT);
      request.onsuccess = () => {
        if (request.result) return;
        const active = transaction.objectStore(WORKSPACE).get("active");
        active.onsuccess = () => {
          if (active.result === undefined && chosen !== null) transaction.objectStore(WORKSPACE).put(chosen, "active");
          transaction.objectStore(MIGRATIONS).put({ phase: "copied", archives, importedWorkspace: active.result === undefined && chosen !== null }, RECEIPT);
        };
      };
      await done;
    }
    const copied = await get<{ phase: string; archives: WorkspaceArchive[]; importedWorkspace: boolean }>(database, MIGRATIONS, RECEIPT);
    if (!copied || !storageValuesEqual(copied.archives, archives)) throw new Error("Projekt-Sicherung konnte nicht verifiziert werden.");
    const copiedActive = await get<unknown>(database, WORKSPACE, "active");
    if (copied.importedWorkspace && !storageValuesEqual(copiedActive, chosen)) {
      throw new Error("Projektübernahme wurde gleichzeitig geändert. Bestehende Daten bleiben erhalten.");
    }
    const transaction = database.transaction(MIGRATIONS, "readwrite");
    const done = complete(transaction);
    transaction.objectStore(MIGRATIONS).put({ ...copied, phase: "verified" }, RECEIPT);
    await done;
    // Old databases remain recoverable until real-browser acceptance is complete.
  } finally { database.close(); }
}

let upgrade: Promise<void> | null = null;
export async function openStudioWorkspaceDatabase(): Promise<IDBDatabase | null> {
  if (!("indexedDB" in globalThis)) return null;
  if (!upgrade) upgrade = migrateWorkspace(globalThis.indexedDB).catch((error) => { upgrade = null; throw error; });
  await upgrade;
  return open(globalThis.indexedDB, STUDIO_DATABASE, true);
}
