export const STUDIO_OPERATION_EVENT = "ultimate-3d-studio-operation";

export type StudioOperationKind = "import" | "export";
export type StudioOperationStatus = "info" | "running" | "success" | "warning" | "error";
export type StudioOperationMetrics = Readonly<Record<string, unknown>>;
export type StudioOperationDetail = Readonly<{
  active: boolean;
  traceId: string;
  kind: StudioOperationKind;
  fileName: string;
  source?: string;
  code: string;
  label: string;
  detail?: string;
  progress?: number | null;
  status: StudioOperationStatus;
  metrics?: StudioOperationMetrics;
  at?: string;
}>;

export function emitStudioOperation(detail: Omit<StudioOperationDetail, "at"> & Partial<Pick<StudioOperationDetail, "at">>): void {
  globalThis.dispatchEvent(new CustomEvent<StudioOperationDetail>(STUDIO_OPERATION_EVENT, {
    detail: { ...detail, at: detail.at || new Date().toISOString() },
  }));
}