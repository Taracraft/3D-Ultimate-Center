export const SLICE_ACTIVITY_EVENT = "ultimate-3d-slice-activity";

export type SliceActivityStatus = "info" | "running" | "success" | "warning" | "error";

export type SliceActivityMetrics = Readonly<{
  layerCount?: number | undefined;
  loadedLayers?: number | undefined;
  segmentCount?: number | undefined;
  loadedSegmentCount?: number | undefined;
  materialCount?: number | undefined;
  outputSizeBytes?: number | undefined;
  processedBytes?: number | undefined;
  totalBytes?: number | undefined;
  rateBytesPerSecond?: number | undefined;
  elapsedSeconds?: number | undefined;
  etaSeconds?: number | undefined;
  layerRatePerSecond?: number | undefined;
  segmentRatePerSecond?: number | undefined;
  features?: readonly string[] | undefined;
}>;

export type SliceActivityDetail = Readonly<{
  active: boolean;
  traceId: string;
  jobId?: string | undefined;
  fileName?: string | undefined;
  plateName?: string | undefined;
  plateId?: number | undefined;
  code: string;
  label: string;
  detail?: string | undefined;
  progress?: number | null | undefined;
  status?: SliceActivityStatus | undefined;
  metrics?: SliceActivityMetrics | undefined;
  at?: string | undefined;
}>;

export function emitSliceActivity(detail: SliceActivityDetail): void {
  globalThis.dispatchEvent(new CustomEvent<SliceActivityDetail>(SLICE_ACTIVITY_EVENT, {
    detail: { ...detail, at: detail.at || new Date().toISOString() },
  }));
}
