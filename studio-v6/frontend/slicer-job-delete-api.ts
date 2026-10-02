import { callEnvelopeApi } from "./ha-api-transport.js";

export type SlicerJobDeleteResult = Readonly<{
  job_id: string;
  status: string;
  deleted: boolean;
  artifact_deleted: boolean;
}>;

export async function deleteTerminalSliceJob(
  jobId: string,
): Promise<SlicerJobDeleteResult> {
  const requested = String(jobId || "").trim();
  if (!requested) throw new Error("Slicerauftrag-ID fehlt.");
  const result = await callEnvelopeApi<SlicerJobDeleteResult>(
    "POST",
    `ultimate_3d_studio_v6/v1/slicer/jobs/${encodeURIComponent(requested)}/delete`,
    { confirmed: true },
  );
  if (!result?.deleted) {
    throw new Error("Die Löschung des Slicerauftrags wurde nicht bestätigt.");
  }
  return result;
}