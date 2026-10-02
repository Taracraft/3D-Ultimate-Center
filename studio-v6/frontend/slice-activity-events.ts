export const SLICE_ACTIVITY_EVENT = "ultimate-3d-slice-activity";

export type SliceActivityStatus = "info" | "running" | "success" | "warning" | "error";
export type SliceActivityMetrics = Readonly<Record<string, unknown>>;
export type SliceActivityDetail = Readonly<{
  active: boolean;
  traceId: string;
  jobId?: string;
  fileName?: string;
  plateName?: string;
  plateId?: number;
  code: string;
  label: string;
  detail?: string;
  progress?: number | null;
  status: SliceActivityStatus;
  metrics?: SliceActivityMetrics;
  at?: string;
}>;

export function emitSliceActivity(detail: Omit<SliceActivityDetail, "at"> & Partial<Pick<SliceActivityDetail, "at">>): void {
  globalThis.dispatchEvent(new CustomEvent<SliceActivityDetail>(SLICE_ACTIVITY_EVENT, {
    detail: { ...detail, at: detail.at || new Date().toISOString() },
  }));
}