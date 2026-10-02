import "./upload-dialog.js";
import { StudioApiClient } from "./api-client.js";
import { sceneStore, type SceneState } from "./scene-store.js";

export type StudioCommandDetail = Readonly<{
  command: string;
  projectId: string | null;
  plateId: string | null;
  objectIds: readonly string[];
}>;

export class StudioCommandController {
  readonly #api = new StudioApiClient();
  readonly #host: HTMLElement;
  readonly #listener = (event: Event): void => {
    const custom = event as CustomEvent<StudioCommandDetail>;
    void this.#handle(custom.detail);
  };

  constructor(host: HTMLElement) {
    this.#host = host;
  }

  connect(): void {
    this.#host.addEventListener("studio-command", this.#listener);
  }

  disconnect(): void {
    this.#host.removeEventListener("studio-command", this.#listener);
  }

  async loadProject(projectId: string): Promise<void> {
    const project = await this.#api.getProject(projectId);
    sceneStore.dispatch({ type: "load", state: this.#toSceneState(project) });
  }

  async #handle(detail: StudioCommandDetail): Promise<void> {
    if (detail.command === "upload") {
      this.#openUploadDialog();
      return;
    }
    const projectId = detail.projectId;
    const plateId = detail.plateId;
    if (!projectId || !plateId) {
      throw new Error("project and active plate are required");
    }

    if (detail.command === "undo" || detail.command === "redo") {
      const project = await this.#requestProjectAction(projectId, detail.command);
      sceneStore.dispatch({ type: "load", state: this.#toSceneState(project) });
      return;
    }

    const payload = this.#commandPayload(detail, plateId);
    const project = await this.#api.executeSceneCommand(projectId, payload);
    sceneStore.dispatch({ type: "load", state: this.#toSceneState(project) });
  }

  #commandPayload(detail: StudioCommandDetail, plateId: string): object {
    const firstObjectId = detail.objectIds[0];
    switch (detail.command) {
      case "duplicate":
        return {
          command: "duplicate_objects",
          plate_id: plateId,
          object_ids: detail.objectIds,
          offset: [10, 10, 0],
        };
      case "delete":
        if (!firstObjectId) throw new Error("an object must be selected");
        return { command: "remove_object", plate_id: plateId, object_id: firstObjectId };
      case "center":
        if (!firstObjectId) throw new Error("an object must be selected");
        return { command: "center_object", plate_id: plateId, object_id: firstObjectId };
      case "place_on_bed":
        if (!firstObjectId) throw new Error("an object must be selected");
        return { command: "place_on_bed", plate_id: plateId, object_id: firstObjectId };
      default:
        throw new Error(`unsupported studio command: ${detail.command}`);
    }
  }

  async #requestProjectAction(projectId: string, action: "undo" | "redo"): Promise<unknown> {
    const response = await fetch(
      `/api/printer_control_center/v1/projects/${encodeURIComponent(projectId)}/${action}`,
      { method: "POST", credentials: "same-origin" },
    );
    const payload = await response.json() as { data?: unknown; error?: { message?: string } | null };
    if (!response.ok || payload.error) throw new Error(payload.error?.message ?? `${action} failed`);
    return payload.data;
  }

  #openUploadDialog(): void {
    let dialog = document.querySelector<HTMLElement>("ultimate-3d-upload-dialog[data-owner='studio']");
    if (!dialog) {
      dialog = document.createElement("ultimate-3d-upload-dialog");
      dialog.dataset.owner = "studio";
      dialog.setAttribute("source", "studio");
      dialog.setAttribute("target", "studio");
      document.body.append(dialog);
    }
    (dialog as HTMLElement & { open(): void }).open();
  }

  #toSceneState(value: unknown): SceneState {
    const project = value as {
      id: string;
      revision: number;
      plates: Array<{
        id: string;
        name: string;
        order_index: number;
        objects: Array<{
          id: string;
          asset_id: string;
          name: string;
          transform: { position: [number, number, number]; rotation: [number, number, number]; scale: [number, number, number] };
          visible: boolean;
          locked: boolean;
          color: string | null;
        }>;
      }>;
    };
    return {
      projectId: project.id,
      revision: project.revision,
      activePlateId: project.plates[0]?.id ?? null,
      selectedObjectIds: [],
      plates: project.plates.map((plate) => ({
        id: plate.id,
        name: plate.name,
        orderIndex: plate.order_index,
        objects: plate.objects.map((item) => ({
          id: item.id,
          assetId: item.asset_id,
          name: item.name,
          transform: item.transform,
          visible: item.visible,
          locked: item.locked,
          color: item.color,
        })),
      })),
    };
  }
}