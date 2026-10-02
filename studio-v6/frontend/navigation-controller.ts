import type { WorkspaceRoute } from "./router.js";

export type Navigator = (route: WorkspaceRoute) => void;

type MakerWorldImportDetail = Readonly<{
  destination: "gallery" | "studio" | "slicer";
  result: unknown;
}>;

export class WorkspaceNavigationController {
  readonly #host: HTMLElement;
  readonly #navigate: Navigator;

  constructor(host: HTMLElement, navigate: Navigator) {
    this.#host = host;
    this.#navigate = navigate;
  }

  connect(): void {
    document.addEventListener("makerworld-import-complete", this.#onMakerWorldImport as EventListener);
    this.#host.addEventListener("gallery-open-studio", this.#onGalleryOpenStudio as EventListener);
    this.#host.addEventListener("gallery-open-slicer", this.#onGalleryOpenSlicer as EventListener);
  }

  disconnect(): void {
    document.removeEventListener("makerworld-import-complete", this.#onMakerWorldImport as EventListener);
    this.#host.removeEventListener("gallery-open-studio", this.#onGalleryOpenStudio as EventListener);
    this.#host.removeEventListener("gallery-open-slicer", this.#onGalleryOpenSlicer as EventListener);
  }

  readonly #onMakerWorldImport = (event: CustomEvent<MakerWorldImportDetail>): void => {
    const detail = event.detail;
    const result = detail.result as {
      project_id?: string | null;
      slice_job_id?: string | null;
    };
    if (detail.destination === "studio" && result.project_id) {
      this.#navigate({ name: "studio", projectId: result.project_id });
      return;
    }
    if (detail.destination === "slicer" && result.slice_job_id) {
      this.#navigate({ name: "slicer", jobId: result.slice_job_id });
      return;
    }
    this.#navigate({ name: "galerie" });
  };

  readonly #onGalleryOpenStudio = (event: CustomEvent<{ assetId: string }>): void => {
    void this.#openGalleryAsset(event.detail.assetId, "studio");
  };

  readonly #onGalleryOpenSlicer = (event: CustomEvent<{ assetId: string }>): void => {
    void this.#openGalleryAsset(event.detail.assetId, "slicer");
  };

  async #openGalleryAsset(assetId: string, target: "studio" | "slicer"): Promise<void> {
    const response = await fetch(
      `/api/printer_control_center/v1/handoffs/gallery/${encodeURIComponent(assetId)}/studio`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      },
    );
    const envelope = await response.json() as {
      data: { project?: { id?: string }; project_id?: string } | null;
      error: { message?: string } | null;
    };
    if (!response.ok || envelope.error || !envelope.data) {
      throw new Error(envelope.error?.message ?? "Gallery handoff failed");
    }
    const projectId = envelope.data.project_id ?? envelope.data.project?.id;
    if (!projectId) throw new Error("Gallery handoff returned no project id");
    this.#navigate({ name: "studio", projectId });
    if (target === "slicer") {
      document.dispatchEvent(new CustomEvent("studio-request-slicing", {
        detail: { projectId, assetId },
      }));
    }
  }
}

