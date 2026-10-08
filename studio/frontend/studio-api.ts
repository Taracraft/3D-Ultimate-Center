import { callEnvelopeApi } from "./ha-api-transport.js";

export type StudioPrinter = Readonly<Record<string, unknown>>;
export type StudioCommandCapability = Readonly<Record<string, unknown>>;
export type StudioJob = Readonly<Record<string, unknown>>;
export type StudioJobs = Readonly<{
  current?: StudioJob[];
  queue?: StudioJob[];
  history?: StudioJob[];
  read_only?: boolean;
  persistent?: boolean;
  repeat_supported?: boolean;
  queue_remove_supported?: boolean;
  queue_execution_enabled?: boolean;
}>;

export type StudioHealth = Readonly<Record<string, unknown>>;

export class StudioApi {
  readonly #base = "ultimate_3d_studio/v1";

  async getHealth(): Promise<StudioHealth> {
    return this.#request<StudioHealth>("GET", "health");
  }

  async getPrinters(): Promise<StudioPrinter[]> {
    const response = await this.#request<{ items?: StudioPrinter[] }>(
      "GET",
      "printers",
    );
    return Array.isArray(response.items) ? response.items : [];
  }

  async getJobs(): Promise<StudioJobs> {
    return this.#request<StudioJobs>("GET", "jobs");
  }

  async repeatJob(jobId: string): Promise<StudioJob> {
    return this.#request<StudioJob>(
      "POST",
      `jobs/${encodeURIComponent(jobId)}/repeat`,
      { confirmed: true },
    );
  }

  async removeQueuedJob(jobId: string): Promise<StudioJob> {
    return this.#request<StudioJob>(
      "POST",
      `jobs/queue/${encodeURIComponent(jobId)}/remove`,
      { confirmed: true },
    );
  }

  async removeHistoryJob(jobId: string): Promise<StudioJob> {
    return this.#request<StudioJob>(
      "POST",
      `jobs/history/${encodeURIComponent(jobId)}/remove`,
      { confirmed: true },
    );
  }

  async clearHistory(): Promise<Readonly<{ removed: number }>> {
    return this.#request<Readonly<{ removed: number }>>(
      "POST",
      "jobs/history/clear",
      { confirmed: true },
    );
  }

  async getCapabilities(): Promise<StudioCommandCapability[]> {
    const response = await this.#request<{
      commands?: StudioCommandCapability[];
    }>("GET", "capabilities");
    return Array.isArray(response.commands) ? response.commands : [];
  }

  async executeCommand(
    printerId: unknown,
    command: string,
    parameters?: Readonly<Record<string, unknown>>,
  ): Promise<Record<string, unknown>> {
    return this.#request<Record<string, unknown>>(
      "POST",
      "commands",
      {
        printer_id: printerId,
        command,
        ...(parameters ?? {}),
        confirmed: true,
      },
    );
  }

  async #request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
  ): Promise<T> {
    const data = await callEnvelopeApi<T>(
      method,
      `${this.#base}/${path}`,
      body,
    );
    if (data === null) throw new Error("Leere Studio-API-Antwort.");
    return data;
  }
}

export const studioApi = new StudioApi();
