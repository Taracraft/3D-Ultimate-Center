import { callEnvelopeApi } from "./ha-api-transport.js";

export type V6Printer = Readonly<Record<string, unknown>>;
export type V6CommandCapability = Readonly<Record<string, unknown>>;
export type V6Job = Readonly<Record<string, unknown>>;
export type V6Jobs = Readonly<{
  current?: V6Job[];
  queue?: V6Job[];
  history?: V6Job[];
  read_only?: boolean;
  persistent?: boolean;
  repeat_supported?: boolean;
  queue_remove_supported?: boolean;
  queue_execution_enabled?: boolean;
}>;

export type V6Health = Readonly<Record<string, unknown>>;

export class V6Api {
  readonly #base = "ultimate_3d_studio_v6/v1";

  async getHealth(): Promise<V6Health> {
    return this.#request<V6Health>("GET", "health");
  }

  async getPrinters(): Promise<V6Printer[]> {
    const response = await this.#request<{ items?: V6Printer[] }>(
      "GET",
      "printers",
    );
    return Array.isArray(response.items) ? response.items : [];
  }

  async getJobs(): Promise<V6Jobs> {
    return this.#request<V6Jobs>("GET", "jobs");
  }

  async repeatJob(jobId: string): Promise<V6Job> {
    return this.#request<V6Job>(
      "POST",
      `jobs/${encodeURIComponent(jobId)}/repeat`,
      { confirmed: true },
    );
  }

  async removeQueuedJob(jobId: string): Promise<V6Job> {
    return this.#request<V6Job>(
      "POST",
      `jobs/queue/${encodeURIComponent(jobId)}/remove`,
      { confirmed: true },
    );
  }

  async removeHistoryJob(jobId: string): Promise<V6Job> {
    return this.#request<V6Job>(
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

  async getCapabilities(): Promise<V6CommandCapability[]> {
    const response = await this.#request<{
      commands?: V6CommandCapability[];
    }>("GET", "capabilities");
    return Array.isArray(response.commands) ? response.commands : [];
  }

  async executeCommand(
    printerId: unknown,
    command: string,
  ): Promise<Record<string, unknown>> {
    return this.#request<Record<string, unknown>>(
      "POST",
      "commands",
      {
        printer_id: printerId,
        command,
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
    if (data === null) throw new Error("Leere V6-API-Antwort.");
    return data;
  }
}

export const v6Api = new V6Api();