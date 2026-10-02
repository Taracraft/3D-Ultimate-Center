export const DIRECT_PRINT_TRANSFER_EVENT = "ultimate-3d-direct-print-transfer";

export type DirectPrintTransferStatus = "queued" | "preparing" | "uploading" | "uploaded" | "starting" | "started" | "success" | "warning" | "error" | "cancelled";
export type DirectPrintTransferDetail = Readonly<{
  active: boolean;
  traceId: string;
  jobId: string;
  printerId: string;
  printerName?: string | undefined;
  fileName?: string | undefined;
  stage?: string | undefined;
  status: DirectPrintTransferStatus | string;
  label: string;
  detail?: string | undefined;
  progress?: number | null | undefined;
  transferredBytes?: number | null | undefined;
  totalBytes?: number | null | undefined;
  rateBytesPerSecond?: number | null | undefined;
  etaSeconds?: number | null | undefined;
  elapsedSeconds?: number | null | undefined;
  at?: string | undefined;
}>;

export function dispatchDirectPrintTransfer(detail: Omit<DirectPrintTransferDetail, "at"> & Partial<Pick<DirectPrintTransferDetail, "at">>): void {
  globalThis.dispatchEvent(new CustomEvent<DirectPrintTransferDetail>(DIRECT_PRINT_TRANSFER_EVENT, {
    detail: { ...detail, at: detail.at || new Date().toISOString() },
  }));
}