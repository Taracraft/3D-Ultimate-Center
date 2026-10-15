import test from "node:test";
import assert from "node:assert/strict";
import { activePrintJobs } from "../frontend/job-activity-store.js";

test("offline or unknown printers never expose preserved current jobs as active", () => {
  const jobs: any = {
    current: [
      { job_id: "job-offline", printer_id: "a1", status: "running", progress: 42 },
      { job_id: "job-missing-printer", printer_id: "missing", status: "running", progress: 10 },
    ],
    queue: [],
  };
  const printers: any[] = [
    { printer_id: "a1", printer_state: "unknown", connection_state: "offline" },
  ];

  assert.deepEqual(activePrintJobs(jobs, printers), []);
});

test("only genuinely active printer jobs stay current while queued jobs remain visible", () => {
  const active = { job_id: "job-active", printer_id: "a1", status: "running", progress: 42 };
  const paused = { job_id: "job-paused", printer_id: "a2", status: "paused", progress: 55 };
  const stale = { job_id: "job-stale", printer_id: "a3", status: "running", progress: 12 };
  const queued = { job_id: "job-queued", printer_id: "a3", status: "queued", progress: 0 };
  const jobs: any = { current: [active, paused, stale], queue: [queued] };
  const printers: any[] = [
    { printer_id: "a1", printer_state: "printing", connection_state: "connected" },
    { printer_id: "a2", printer_state: "paused", connection_state: "connected" },
    { printer_id: "a3", printer_state: "unknown", connection_state: "offline" },
  ];

  assert.deepEqual(activePrintJobs(jobs, printers), [active, paused, queued]);
});
