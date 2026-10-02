import "./direct-print-panel.js";
import "./slice-analysis-panel.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import type { SliceJob } from "./slicing-api.js";
import type { V6Job, V6Printer } from "./v6-api.js";

type DirectPrintPanel = HTMLElement & {
  job: SliceJob | null;
  enabled: boolean;
};
type AnalysisPanel = HTMLElement & {
  job: SliceJob | null;
  printJob: V6Job | null;
  printer: V6Printer | null;
};

export class StudioDirectPrintStrip extends HTMLElement {
  static get observedAttributes(): string[] {
    return ["plate-id", "job-id", "has-model"];
  }

  readonly #root = this.attachShadow({ mode: "open" });
  readonly #analysis = document.createElement(
    "slice-analysis-panel",
  ) as AnalysisPanel;
  readonly #panel = document.createElement(
    "ultimate-3d-direct-print-panel",
  ) as DirectPrintPanel;
  #snapshot: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #activeJobId = "";

  connectedCallback(): void {
    if (!this.#root.childElementCount) {
      const style = document.createElement("style");
      style.textContent = `:host{display:block;position:relative;width:100%;min-width:0;margin:0;color:#eef6ff}:host([hidden]){display:none}.strip{display:grid;grid-template-columns:minmax(0,1fr);align-items:start;gap:7px;width:100%;min-width:0;padding:5px 9px;border-bottom:1px solid #24384c;background:linear-gradient(180deg,#0c1823,#08111a)}@media(max-width:760px){.strip{padding:5px}}`;
      const strip = document.createElement("section");
      strip.className = "strip";
      this.#panel.setAttribute("compact", "");
      strip.append(this.#panel, this.#analysis);
      this.#root.append(style, strip);
    }
    if (!this.#unsubscribe) {
      this.#unsubscribe = jobActivityStore.subscribe((snapshot) => {
        this.#snapshot = snapshot;
        this.#sync();
      });
    }
    this.#sync();
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  attributeChangedCallback(): void {
    if (this.isConnected) this.#sync();
  }

  #printer(printJob: V6Job | null): V6Printer | null {
    const printerId = String(printJob?.printer_id || "");
    return this.#snapshot.printers.find(
      (item) => String(item.printer_id || "") === printerId,
    ) ?? this.#snapshot.printers[0] ?? null;
  }

  #sync(): void {
    const candidate = this.#snapshot.slicer;
    const expectedJobId = String(this.getAttribute("job-id") || "").trim();
    const job = candidate?.status === "succeeded" && expectedJobId && candidate.id === expectedJobId
      ? candidate
      : null;
    const printJob = this.#snapshot.printJobs[0] ?? null;
    const nextJobId = job?.id || "";
    this.hidden = !job;

    this.#analysis.job = job;
    this.#analysis.printJob = printJob;
    this.#analysis.printer = this.#printer(printJob);

    if (nextJobId !== this.#activeJobId) {
      this.#activeJobId = nextJobId;
      this.#panel.job = job;
    }
    this.#panel.enabled = Boolean(job);
  }
}

if (!customElements.get("studio-direct-print-strip")) {
  customElements.define("studio-direct-print-strip", StudioDirectPrintStrip);
}
