import { authenticatedFetch, callEnvelopeApi } from "./ha-api-transport.js";

export type ApiError = Readonly<{
  code: string;
  message: string;
  details?: Record<string, unknown>;
}>;

export type ApiResponse<T> = Readonly<{
  data: T | null;
  error: ApiError | null;
  request_id?: string;
  version: string;
}>;

export class StudioApiClient {
  constructor(
    private readonly baseUrl = "printer_control_center/v1",
    private readonly fetchImpl: typeof fetch | null = null,
  ) {}

  async getProject(projectId: string): Promise<unknown> {
    return this.#request("GET", `/projects/${encodeURIComponent(projectId)}`);
  }

  async executeSceneCommand(projectId: string, payload: object): Promise<unknown> {
    return this.#request("POST", `/projects/${encodeURIComponent(projectId)}/commands`, payload);
  }

  async createUpload(payload: object): Promise<unknown> {
    return this.#request("POST", "/assets/uploads", payload);
  }

  async writeUploadChunk(uploadId: string, offset: number, chunk: Blob): Promise<unknown> {
    const path = `/assets/uploads/${encodeURIComponent(uploadId)}/chunks?offset=${offset}`;
    const response = this.fetchImpl
      ? await this.fetchImpl(`${this.baseUrl}${path}`, {
          method: "POST",
          body: chunk,
          credentials: "same-origin",
          headers: { "Content-Type": "application/octet-stream" },
        })
      : await authenticatedFetch(
          `/api/${this.#normalizedBase()}${path}`,
          {
            method: "POST",
            body: chunk,
            headers: { "Content-Type": "application/octet-stream" },
          },
        );

    const payload = await response.json() as ApiResponse<unknown>;
    if (!response.ok || payload.error) {
      throw new Error(payload.error?.message ?? `Upload fehlgeschlagen: HTTP ${response.status}`);
    }
    return payload.data;
  }

  async finalizeUpload(uploadId: string): Promise<unknown> {
    return this.#request("POST", `/assets/uploads/${encodeURIComponent(uploadId)}/complete`);
  }

  #normalizedBase(): string {
    return this.baseUrl.replace(/^\/+/, "").replace(/^api\//, "");
  }

  async #request(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
  ): Promise<unknown> {
    if (!this.fetchImpl) {
      return callEnvelopeApi<unknown>(method, `${this.#normalizedBase()}${path}`, body, true);
    }

    const headers = new Headers();
    const init: RequestInit = {
      method,
      credentials: "same-origin",
      headers,
    };

    if (body !== undefined) {
      headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(body);
    }

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, init);
    const payload = await response.json() as ApiResponse<unknown>;
    if (!response.ok || payload.error) {
      throw new Error(payload.error?.message ?? `Request failed with ${response.status}`);
    }
    return payload.data;
  }
}