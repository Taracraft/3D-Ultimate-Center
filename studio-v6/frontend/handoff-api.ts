import { callEnvelopeApi } from "./ha-api-transport.js";

export type HandoffProject = Readonly<{
  id: string;
  revision: number;
  plates: readonly { id: string; name: string }[];
}>;

export class HandoffApi {
  constructor(private readonly baseUrl = "printer_control_center/v1") {}

  async galleryToStudio(
    assetId: string,
    projectId?: string,
    plateId?: string,
  ): Promise<{ project: HandoffProject }> {
    const data = await callEnvelopeApi<{ project: HandoffProject }>(
      "POST",
      `${this.baseUrl}/handoffs/gallery/${encodeURIComponent(assetId)}/studio`,
      {
        project_id: projectId,
        plate_id: plateId,
      },
    );
    if (!data) throw new Error("Leere Handoff-Antwort.");
    return data;
  }

  async queueToStudio(
    queueItemId: string,
    projectId?: string,
  ): Promise<{ project: HandoffProject }> {
    const data = await callEnvelopeApi<{ project: HandoffProject }>(
      "POST",
      `${this.baseUrl}/handoffs/queue/${encodeURIComponent(queueItemId)}/studio`,
      { project_id: projectId },
    );
    if (!data) throw new Error("Leere Handoff-Antwort.");
    return data;
  }
}