import { StudioApiClient } from "./api-client.js";

export type UploadSource = "control_center" | "gallery" | "studio";
export type UploadTarget = "gallery" | "studio" | "queue" | "slice" | "printer";

export type UploadProgress = Readonly<{
  fileName: string;
  uploadedBytes: number;
  totalBytes: number;
  percent: number;
}>;

export class UploadController {
  constructor(
    private readonly api: StudioApiClient,
    private readonly chunkSize = 4 * 1024 * 1024,
  ) {}

  async upload(
    file: File,
    sourceUi: UploadSource,
    target: UploadTarget,
    onProgress?: (progress: UploadProgress) => void,
  ): Promise<unknown> {
    const session = (await this.api.createUpload({
      original_name: file.name,
      expected_size: file.size,
      source_ui: sourceUi,
      target,
      chunk_size: this.chunkSize,
    })) as { id: string };

    let offset = 0;
    while (offset < file.size) {
      const chunk = file.slice(offset, Math.min(offset + this.chunkSize, file.size));
      await this.api.writeUploadChunk(session.id, offset, chunk);
      offset += chunk.size;
      onProgress?.({
        fileName: file.name,
        uploadedBytes: offset,
        totalBytes: file.size,
        percent: file.size === 0 ? 100 : Math.min(100, (offset / file.size) * 100),
      });
    }
    return this.api.finalizeUpload(session.id);
  }
}