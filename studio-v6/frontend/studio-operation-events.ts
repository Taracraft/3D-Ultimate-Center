export const STUDIO_OPERATION_EVENT = "ultimate-3d-studio-operation";

export type StudioOperationKind = "import" | "export";
export type StudioOperationStatus = "running" | "success" | "error";

export type StudioOperationMetrics = Readonly<{
  plateCount?: number | undefined;
  loadedPlates?: number | undefined;
  objectCount?: number | undefined;
  loadedObjects?: number | undefined;
  triangleCount?: number | undefined;
  materialCount?: number | undefined;
  inputSizeBytes?: number | undefined;
  outputSizeBytes?: number | undefined;
}>;

export type StudioOperationDetail = Readonly<{
  active: boolean;
  traceId: string;
  kind: StudioOperationKind;
  fileName: string;
  source?: string | undefined;
  code: string;
  label: string;
  detail?: string | undefined;
  progress?: number | null | undefined;
  status: StudioOperationStatus;
  metrics?: StudioOperationMetrics | undefined;
  at?: string | undefined;
}>;

export function emitStudioOperation(detail: StudioOperationDetail): void {
  globalThis.dispatchEvent(new CustomEvent<StudioOperationDetail>(STUDIO_OPERATION_EVENT, {
    detail: { ...detail, at: detail.at || new Date().toISOString() },
  }));
}
