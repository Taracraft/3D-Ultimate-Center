import { callEnvelopeApi } from "./ha-api-transport.js";
import type { SliceJob } from "./slicing-api.js";

export async function listNativeSliceJobs(): Promise<SliceJob[]> {
  const data = await callEnvelopeApi<{ items?: SliceJob[] }>(
    "GET",
    "ultimate_3d_studio/v1/slicer/jobs-list",
  );
  return Array.isArray(data?.items) ? data.items : [];
}
