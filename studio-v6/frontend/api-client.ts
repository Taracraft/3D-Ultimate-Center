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

async function readApiResponse<T>(response: Response, fallback: string): Promise<ApiResponse<T>> {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error(response.ok ? fallback : `${fallback}: HTTP ${response.status}`);
  }
  try {
    return JSON.parse(text) as ApiResponse<T>;
  } catch {
    const message = text.trim().replace(/\s+/g, " ").slice(0, 500);
    if (response.status === 413 || /maximum request body|request entity too large/i.test(message)) {
      throw new Error("Upload-Chunk wurde vom Server als zu groß abgewiesen.");
    }
    throw new Error(message || `${fallback}: HTTP ${response.status}`);
  }
}

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

    const payload = await readApiResponse<unknown>(response, "Upload fehlgeschlagen");
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
    const payload = await readApiResponse<unknown>(response, "API-Anfrage fehlgeschlagen");
    if (!response.ok || payload.error) {
      throw new Error(payload.error?.message ?? `Request failed with ${response.status}`);
    }
    return payload.data;
  }
}
