export const DIRECT_PRINT_TRANSFER_EVENT = "ultimate-3d-direct-print-transfer";

export type DirectPrintTransferEventStatus = "running" | "success" | "error";

export type DirectPrintTransferDetail = Readonly<{
  traceId: string;
  jobId: string;
  printerId: string;
  printerName: string;
  fileName: string;
  stage: string;
  message: string;
  active: boolean;
  status: DirectPrintTransferEventStatus;
  progress: number;
  loadedBytes: number;
  totalBytes: number;
  rateBytesPerSecond: number;
  etaSeconds?: number | undefined;
  elapsedSeconds?: number | undefined;
  at: string;
}>;

export function dispatchDirectPrintTransfer(
  detail: DirectPrintTransferDetail,
): void {
  globalThis.dispatchEvent?.(new CustomEvent(DIRECT_PRINT_TRANSFER_EVENT, {
    detail,
  }));
}
