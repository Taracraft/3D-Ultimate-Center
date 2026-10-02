import { authenticatedFetch, errorMessage } from "./ha-api-transport.js";
import type { PersistedStudioWorkspace } from "./studio-persistence.js";

const API_PATH = "/api/ultimate_3d_studio_v6/v1/studio/projects";

export type StudioProjectSummary = Readonly<{
  id: string;
  name: string;
  revision: number;
  created_at: string;
  updated_at: string;
}>;

export type StudioProject = StudioProjectSummary & Readonly<{
  snapshot: PersistedStudioWorkspace;
}>;

export type StudioProjectRevision = Readonly<{
  revision: number;
  created_at: string;
}>;

type Envelope<T> = Readonly<{
  data: T | null;
  error?: Readonly<{ code?: string; message?: string; current_revision?: number | null }> | null;
}>;

function plainSnapshot(snapshot: PersistedStudioWorkspace): unknown {
  return {
    ...snapshot,
    assignments: snapshot.assignments.map(([id, material]) => [id, material]),
    modelMaterials: snapshot.modelMaterials.map((item) => ({ ...item })),
    paintRegions: snapshot.paintRegions.map((region) => ({ ...region, triangleIndices: [...region.triangleIndices] })),
    plates: snapshot.plates.map((plate) => ({
      ...plate,
      selection: {
        ...plate.selection,
        filament_profile_ids: [...plate.selection.filament_profile_ids],
      },
      instances: plate.instances.map((item) => ({
        ...item,
        positions: Array.from(item.positions),
        position: [...item.position],
        rotation: [...item.rotation],
        scale: [...item.scale],
      })),
    })),
  };
}

function workspaceSnapshot(value: unknown): PersistedStudioWorkspace {
  if (!value || typeof value !== "object") throw new Error("Projekt enthält keinen gültigen Studio-Snapshot.");
  const source = value as PersistedStudioWorkspace;
  if (source.version !== 1 || !Array.isArray(source.plates) || source.plates.length === 0) {
    throw new Error("Projekt-Snapshot Version 1 mit mindestens einer Druckplatte wird benötigt.");
  }
  return {
    ...source,
    assignments: source.assignments.map(([id, material]) => [String(id), String(material)] as const),
    modelMaterials: source.modelMaterials.map((item) => ({ ...item })),
    paintRegions: Array.isArray(source.paintRegions) ? source.paintRegions.map((region) => ({
      plateId: Number(region.plateId), objectId: String(region.objectId || ""), color: String(region.color || "#6b7785"),
      materialKey: String(region.materialKey || ""), triangleIndices: [...(region.triangleIndices || [])].filter((item) => Number.isInteger(item) && item >= 0),
    })).filter((region) => Number.isInteger(region.plateId) && region.objectId) : [],
    plates: source.plates.map((plate) => ({
      ...plate,
      selection: {
        ...plate.selection,
        filament_profile_ids: [...plate.selection.filament_profile_ids],
      },
      instances: plate.instances.map((item) => ({
        ...item,
        positions: item.positions instanceof Float32Array
          ? new Float32Array(item.positions)
          : new Float32Array(item.positions as unknown as number[]),
        position: [...item.position],
        rotation: [...item.rotation],
        scale: [...item.scale],
      })),
    })),
  };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");
  const response = await authenticatedFetch(path, { ...init, headers });
  let envelope: Envelope<T>;
  try {
    envelope = await response.json() as Envelope<T>;
  } catch {
    throw new Error(`Projekt-API HTTP ${response.status}: ungültige Serverantwort`);
  }
  if (!response.ok || envelope.data === null) {
    const failure = new Error(errorMessage(envelope, `Projekt-API HTTP ${response.status}`));
    if (envelope.error?.code === "revision_conflict") {
      Object.assign(failure, {
        code: "revision_conflict",
        currentRevision: envelope.error.current_revision ?? null,
      });
    }
    throw failure;
  }
  return envelope.data;
}

export async function listStudioProjects(): Promise<readonly StudioProjectSummary[]> {
  const result = await request<{ items: StudioProjectSummary[] }>(API_PATH);
  return result.items;
}

export async function createStudioProject(
  name: string,
  snapshot: PersistedStudioWorkspace,
): Promise<StudioProject> {
  const result = await request<Omit<StudioProject, "snapshot"> & { snapshot: unknown }>(API_PATH, {
    method: "POST",
    body: JSON.stringify({ name, snapshot: plainSnapshot(snapshot) }),
  });
  return { ...result, snapshot: workspaceSnapshot(result.snapshot) };
}

export async function getStudioProject(projectId: string): Promise<StudioProject> {
  const result = await request<Omit<StudioProject, "snapshot"> & { snapshot: unknown }>(
    `${API_PATH}/${encodeURIComponent(projectId)}`,
  );
  return { ...result, snapshot: workspaceSnapshot(result.snapshot) };
}

export async function saveStudioProject(
  projectId: string,
  name: string,
  revision: number,
  snapshot: PersistedStudioWorkspace,
): Promise<StudioProject> {
  const result = await request<Omit<StudioProject, "snapshot"> & { snapshot: unknown }>(
    `${API_PATH}/${encodeURIComponent(projectId)}`,
    {
      method: "POST",
      body: JSON.stringify({
        name,
        expected_revision: revision,
        snapshot: plainSnapshot(snapshot),
      }),
    },
  );
  return { ...result, snapshot: workspaceSnapshot(result.snapshot) };
}

export async function listStudioProjectRevisions(
  projectId: string,
): Promise<readonly StudioProjectRevision[]> {
  const result = await request<{ items: StudioProjectRevision[] }>(
    `${API_PATH}/${encodeURIComponent(projectId)}/revisions`,
  );
  return result.items;
}

export async function restoreStudioProjectRevision(
  projectId: string,
  revision: number,
  sourceRevision: number,
): Promise<StudioProject> {
  const result = await request<Omit<StudioProject, "snapshot"> & { snapshot: unknown }>(
    `${API_PATH}/${encodeURIComponent(projectId)}/restore`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_revision: revision,
        source_revision: sourceRevision,
      }),
    },
  );
  return { ...result, snapshot: workspaceSnapshot(result.snapshot) };
}
