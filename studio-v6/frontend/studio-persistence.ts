import type { StudioPlateProfileSelection } from "./studio-profile-catalog.js";
import type { Vec3 } from "./webgl-studio-viewport.js";
import type { PaintRegion } from "./studio-mesh-paint.js";

export type PersistedStudioInstance = Readonly<{
  id: string;
  name: string;
  positions: Float32Array;
  position: Vec3;
  rotation: Vec3;
  scale: Vec3;
  color: string;
  visible: boolean;
}>;

export type PersistedStudioPlate = Readonly<{
  id: number;
  name: string;
  width: number;
  depth: number;
  stage?: "prepared" | "slicing" | "sliced" | "printed" | "error";
  jobId?: string;
  materialSource?: "ams" | "external_spool";
  externalFilamentProfileId?: string;
  selection: StudioPlateProfileSelection;
  instances: PersistedStudioInstance[];
}>;

export type PersistedStudioMaterial = Readonly<{
  key: string;
  name: string;
  material: string;
  color: string;
  source: "ams" | "external_spool" | "model";
  global_id?: string;
  unit_id?: string;
  slot_index?: number;
  display_slot?: number;
  tray_id?: string;
  filament_id?: string;
}>;

export type PersistedStudioPaintRegion = PaintRegion & Readonly<{ plateId: number }>;

export type PersistedStudioPaintLayerPoint = Readonly<{
  x: number;
  y: number;
  z: number;
  screenX: number;
  screenY: number;
}>;

export type PersistedStudioPaintLayer = Readonly<{
  id: string;
  plateId: number;
  objectId: string;
  kind: "stroke" | "rectangle" | "circle" | "text";
  label: string;
  color: string;
  materialKey: string;
  radiusMm: number;
  points: PersistedStudioPaintLayerPoint[];
  text?: string;
  textSizePx?: number;
}>;

export type PersistedStudioWorkspace = Readonly<{
  version: 1;
  savedAt: number;
  activePlate: number;
  mode: "prepare" | "colors";
  nextId: number;
  selected: string[];
  assignments: Array<readonly [string, string]>;
  modelMaterials: PersistedStudioMaterial[];
  paintRegions: PersistedStudioPaintRegion[];
  paintLayers: Array<readonly [number, PersistedStudioPaintLayer[]]>;
  nextPaintLayerId: number;
  plates: PersistedStudioPlate[];
}>;

const DATABASE_NAME = "ultimate-3d-studio-v6";
const DATABASE_VERSION = 1;
const STORE_NAME = "workspace";
const ACTIVE_KEY = "active";

function openDatabase(): Promise<IDBDatabase | null> {
  if (!("indexedDB" in globalThis)) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const request = globalThis.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) database.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("Studio-Speicher konnte nicht geöffnet werden."));
    request.onblocked = () => reject(new Error("Studio-Speicher ist durch eine andere Sitzung blockiert."));
  });
}

function transactionComplete(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error ?? new Error("Studio-Sitzung konnte nicht gespeichert werden."));
    transaction.onabort = () => reject(transaction.error ?? new Error("Studio-Speicherung wurde abgebrochen."));
  });
}

export async function saveStudioWorkspace(snapshot: PersistedStudioWorkspace): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  try {
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).put(snapshot, ACTIVE_KEY);
    await transactionComplete(transaction);
  } finally {
    database.close();
  }
}

export async function loadStudioWorkspace(): Promise<PersistedStudioWorkspace | null> {
  const database = await openDatabase();
  if (!database) return null;
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, "readonly");
      const request = transaction.objectStore(STORE_NAME).get(ACTIVE_KEY);
      request.onsuccess = () => {
        const value = request.result;
        resolve(value && value.version === 1 ? value as PersistedStudioWorkspace : null);
      };
      request.onerror = () => reject(request.error ?? new Error("Studio-Sitzung konnte nicht geladen werden."));
    });
  } finally {
    database.close();
  }
}

export async function clearStudioWorkspace(): Promise<void> {
  const database = await openDatabase();
  if (!database) return;
  try {
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).delete(ACTIVE_KEY);
    await transactionComplete(transaction);
  } finally {
    database.close();
  }
}
