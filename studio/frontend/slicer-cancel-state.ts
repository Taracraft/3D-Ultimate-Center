import type { SliceJob } from "./slicing-api.js";

/** An old worker or an unowned native process must never display a working stop button. */
export function canCancelSliceJob(job: Pick<SliceJob, "status" | "cancellation_available" | "cancel_requested">): boolean {
  return job.cancellation_available === true && job.cancel_requested !== true
    && (job.status === "queued" || job.status === "running");
}

export function cancellationMessage(status: string): string {
  if (status === "cancelled") return "Slicerauftrag wurde abgebrochen. Die Quelldatei bleibt erhalten.";
  if (status === "cancelling") return "Abbruch angefordert. Der Worker beendet den Slicer und bereinigt Teilresultate.";
  throw new Error("Der Worker hat den Abbruch nicht bestätigt.");
}
