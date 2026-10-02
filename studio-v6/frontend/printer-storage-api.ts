import {
  authenticatedFetch,
  callEnvelopeApi,
  errorMessage,
} from "./ha-api-transport.js";

export type PrinterStorageSummary = Readonly<{
  printer_id: string;
  printer_name: string;
  provider: string;
  connection_state: string;
  storage_supported: boolean;
}>;

export type PrinterStorageItem = Readonly<{
  path: string;
  name: string;
  kind: "folder" | "project" | "gcode" | "model" | "file";
  size_bytes: number;
  modified: string;
  preview_data_url?: string;
}>;

export type PrinterStorageFolder = Readonly<{
  path: string;
  name: string;
  depth: number;
}>;

export type PrinterStorageListing = Readonly<{
  folder: string;
  parent: string;
  items: PrinterStorageItem[];
}>;

type Action = "create_folder" | "rename" | "move" | "copy" | "delete";

function endpoint(printerId: string, suffix = ""): string {
  return `ultimate_3d_studio_v6/v1/storage/${encodeURIComponent(printerId)}${suffix}`;
}

async function responseError(response: Response): Promise<Error> {
  try {
    const payload = await response.json() as unknown;
    return new Error(errorMessage(payload, `SD-Karte HTTP ${response.status}`));
  } catch {
    return new Error(`SD-Karte HTTP ${response.status}: ${response.statusText}`);
  }
}

function downloadName(response: Response, fallback: string): string {
  const disposition = response.headers.get("Content-Disposition") || "";
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  const raw = utf8 ? decodeURIComponent(utf8) : plain;
  return String(raw || fallback || "printer-file.bin").replace(/[\\/]/g, "_");
}

export class PrinterStorageApi {
  static readonly #queues = new Map<string, Promise<void>>();

  async #serialized<T>(printerId: string, operation: () => Promise<T>): Promise<T> {
    const previous = PrinterStorageApi.#queues.get(printerId) ?? Promise.resolve();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => { release = resolve; });
    const tail = previous.catch(() => undefined).then(() => gate);
    PrinterStorageApi.#queues.set(printerId, tail);
    await previous.catch(() => undefined);
    try {
      return await operation();
    } finally {
      release();
      if (PrinterStorageApi.#queues.get(printerId) === tail) {
        PrinterStorageApi.#queues.delete(printerId);
      }
    }
  }

  async summaries(): Promise<PrinterStorageSummary[]> {
    const data = await callEnvelopeApi<{ items?: PrinterStorageSummary[] }>(
      "GET",
      "ultimate_3d_studio_v6/v1/storage",
    );
    return Array.isArray(data?.items) ? data.items : [];
  }

  async list(
    printerId: string,
    folder = "/",
    previews = true,
  ): Promise<PrinterStorageListing> {
    return await this.#serialized(printerId, async () => {
      const query = new URLSearchParams({
        folder,
        previews: previews ? "1" : "0",
      });
      return await callEnvelopeApi<PrinterStorageListing>(
        "GET",
        `${endpoint(printerId)}?${query}`,
      ) as PrinterStorageListing;
    });
  }

  async tree(printerId: string): Promise<PrinterStorageFolder[]> {
    return await this.#serialized(printerId, async () => {
      const data = await callEnvelopeApi<{ items?: PrinterStorageFolder[] }>(
        "GET",
        endpoint(printerId, "/tree"),
      );
      return Array.isArray(data?.items) ? data.items : [];
    });
  }

  async download(printerId: string, item: PrinterStorageItem): Promise<File> {
    return await this.#serialized(printerId, async () => {
      const query = new URLSearchParams({ path: item.path });
      const response = await authenticatedFetch(
        `/api/${endpoint(printerId, "/download")}?${query}`,
      );
      if (!response.ok) throw await responseError(response);
      const blob = await response.blob();
      return new File(
        [blob],
        downloadName(response, item.name),
        { type: blob.type || "application/octet-stream" },
      );
    });
  }

  async upload(
    printerId: string,
    file: File,
    folder: string,
    overwrite = false,
  ): Promise<PrinterStorageItem> {
    return await this.#serialized(printerId, async () => {
      const query = new URLSearchParams({
        filename: file.name,
        folder,
        overwrite: overwrite ? "1" : "0",
        confirmed: "1",
      });
      const response = await authenticatedFetch(
        `/api/${endpoint(printerId, "/upload")}?${query}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/octet-stream" },
          body: file,
        },
      );
      if (!response.ok) throw await responseError(response);
      const envelope = await response.json() as Readonly<{
        data?: PrinterStorageItem;
        error?: unknown;
      }>;
      if (envelope.error || !envelope.data) {
        throw new Error(errorMessage(envelope.error));
      }
      return envelope.data;
    });
  }

  async action(
    printerId: string,
    action: Action,
    parameters: Readonly<{
      path?: string;
      target_folder?: string;
      name?: string;
      overwrite?: boolean;
    }>,
  ): Promise<Readonly<Record<string, unknown>>> {
    return await this.#serialized(printerId, async () => (
      await callEnvelopeApi<Readonly<Record<string, unknown>>>(
        "POST",
        endpoint(printerId, "/actions"),
        {
          confirmed: true,
          action,
          ...parameters,
        },
      ) as Readonly<Record<string, unknown>>
    ));
  }
}