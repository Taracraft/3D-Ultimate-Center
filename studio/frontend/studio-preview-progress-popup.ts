import {
  SLICE_ACTIVITY_EVENT,
  type SliceActivityDetail,
  type SliceActivityMetrics,
} from "./slice-activity-events.js";

const PREVIEW_CODES = new Set([
  "toolpath_parse_started",
  "toolpath_summary_ready",
  "preview_chunk_loaded",
  "render_data_ready",
  "preview_ready",
  "slice_pipeline_failed",
]);

function positive(value: unknown): number | null {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : null;
}

function nonNegative(value: unknown): number | null {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue >= 0 ? numberValue : null;
}

function formatDuration(value: number): string {
  const seconds = Math.max(0, Math.round(value));
  if (seconds < 60) return `${seconds} Sek.`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  if (minutes < 60) return remainder ? `${minutes} Min. ${remainder} Sek.` : `${minutes} Min.`;
  const hours = Math.floor(minutes / 60);
  const minuteRemainder = minutes % 60;
  return minuteRemainder ? `${hours} Std. ${minuteRemainder} Min.` : `${hours} Std.`;
}

function previewProgress(detail: SliceActivityDetail): number | null {
  if (detail.code === "render_data_ready" || detail.code === "preview_ready") return 100;
  if (detail.code === "toolpath_summary_ready") return 0;
  if (detail.code !== "preview_chunk_loaded") return null;
  const loadedLayers = nonNegative(detail.metrics?.loadedLayers);
  const layerCount = positive(detail.metrics?.layerCount);
  if (loadedLayers !== null && layerCount !== null) {
    return Math.min(100, Math.max(0, (loadedLayers / layerCount) * 100));
  }
  const loadedSegments = nonNegative(detail.metrics?.loadedSegmentCount);
  const segmentCount = positive(detail.metrics?.segmentCount);
  if (loadedSegments !== null && segmentCount !== null) {
    return Math.min(100, Math.max(0, (loadedSegments / segmentCount) * 100));
  }
  return null;
}

function remainingSeconds(metrics?: SliceActivityMetrics): number | null {
  const reportedEta = positive(metrics?.etaSeconds);
  if (reportedEta !== null) return reportedEta;

  const segmentCount = positive(metrics?.segmentCount);
  const loadedSegments = nonNegative(metrics?.loadedSegmentCount);
  const segmentRate = positive(metrics?.segmentRatePerSecond);
  if (segmentCount !== null && loadedSegments !== null && segmentRate !== null) {
    return Math.max(0, (segmentCount - loadedSegments) / segmentRate);
  }

  const layerCount = positive(metrics?.layerCount);
  const loadedLayers = nonNegative(metrics?.loadedLayers);
  const layerRate = positive(metrics?.layerRatePerSecond);
  if (layerCount !== null && loadedLayers !== null && layerRate !== null) {
    return Math.max(0, (layerCount - loadedLayers) / layerRate);
  }
  return null;
}

function metricText(detail: SliceActivityDetail): string {
  const metrics = detail.metrics;
  const parts: string[] = [];
  const loadedLayers = nonNegative(metrics?.loadedLayers);
  const layerCount = positive(metrics?.layerCount);
  if (loadedLayers !== null && layerCount !== null) {
    parts.push(`${Math.min(loadedLayers, layerCount).toLocaleString("de-DE")} / ${layerCount.toLocaleString("de-DE")} Layer`);
  } else if (layerCount !== null) {
    parts.push(`${layerCount.toLocaleString("de-DE")} Layer erkannt`);
  }
  const loadedSegments = nonNegative(metrics?.loadedSegmentCount);
  const segmentCount = positive(metrics?.segmentCount);
  if (loadedSegments !== null && segmentCount !== null) {
    parts.push(`${Math.min(loadedSegments, segmentCount).toLocaleString("de-DE")} / ${segmentCount.toLocaleString("de-DE")} Bahnen`);
  } else if (segmentCount !== null) {
    parts.push(`${segmentCount.toLocaleString("de-DE")} Bahnen erkannt`);
  }
  return parts.join(" · ");
}

function rateText(metrics?: SliceActivityMetrics): string {
  const parts: string[] = [];
  const layerRate = positive(metrics?.layerRatePerSecond);
  const segmentRate = positive(metrics?.segmentRatePerSecond);
  const elapsed = nonNegative(metrics?.elapsedSeconds);
  if (layerRate !== null) parts.push(`${layerRate.toLocaleString("de-DE", { maximumFractionDigits: 1 })} Layer/s`);
  if (segmentRate !== null) parts.push(`${Math.round(segmentRate).toLocaleString("de-DE")} Bahnen/s`);
  if (elapsed !== null) parts.push(`Laufzeit ${formatDuration(elapsed)}`);
  return parts.join(" · ");
}

class StudioPreviewProgressPopup extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #traceId = "";
  #detail: SliceActivityDetail | null = null;
  #collapsed = false;
  #dismissed = false;

  constructor() {
    super();
    this.#root.innerHTML = `
      <style>
        :host {
          position: fixed;
          right: 18px;
          bottom: 18px;
          z-index: 2147483000;
          width: min(460px, calc(100vw - 36px));
          color: #eef8ff;
          font: 600 13px/1.35 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          filter: drop-shadow(0 16px 40px rgba(0, 0, 0, .42));
        }
        :host([hidden]) { display: none !important; }
        :host([data-stacked]) {
          position: static;
          right: auto;
          bottom: auto;
          z-index: auto;
          width: 100%;
          max-width: 460px;
        }
        .panel {
          overflow: hidden;
          border: 1px solid rgba(44, 188, 255, .55);
          border-radius: 14px;
          background: linear-gradient(155deg, rgba(7, 28, 43, .98), rgba(5, 17, 29, .98));
          box-shadow: inset 0 1px 0 rgba(255, 255, 255, .05);
        }
        .panel.success { border-color: rgba(54, 215, 132, .58); }
        .panel.error { border-color: rgba(255, 91, 104, .72); }
        header { display: flex; align-items: flex-start; gap: 10px; padding: 14px 14px 11px; }
        .heading { min-width: 0; flex: 1; }
        .eyebrow { color: #66d1ff; font-size: 10px; letter-spacing: .13em; text-transform: uppercase; }
        h2 { margin: 3px 0 0; color: #f5fbff; font-size: 16px; line-height: 1.2; }
        button {
          appearance: none;
          border: 1px solid rgba(133, 205, 236, .26);
          border-radius: 8px;
          background: rgba(12, 43, 62, .72);
          color: #dff5ff;
          cursor: pointer;
          font: inherit;
          padding: 6px 8px;
        }
        button:hover { border-color: rgba(102, 209, 255, .72); }
        .close { width: 31px; padding-inline: 0; }
        .body { padding: 0 14px 14px; }
        .panel.collapsed .body { display: none; }
        .file { overflow: hidden; margin: 0 0 10px; color: #b9d5e4; text-overflow: ellipsis; white-space: nowrap; }
        .phase { margin: 0 0 4px; color: #fff; font-size: 14px; }
        .detail { min-height: 18px; margin: 0 0 10px; color: #9fc0d1; font-weight: 500; }
        .progress { position: relative; overflow: hidden; height: 8px; border-radius: 999px; background: rgba(126, 177, 202, .16); }
        .progress > i { display: block; height: 100%; width: 0; border-radius: inherit; background: linear-gradient(90deg, #19aee7, #55e3bd); transition: width .22s ease; }
        .progress.indeterminate > i { width: 100%; transform-origin: left; animation: preview-fill 1.15s linear infinite; }
        .error .progress > i { background: #ff6572; }
        @keyframes preview-fill { from { transform: scaleX(0); } to { transform: scaleX(1); } }
        .status { display: flex; justify-content: space-between; gap: 12px; margin-top: 9px; }
        .percent { color: #d8f4ff; }
        .eta { color: #7ff0c4; text-align: right; }
        .eta.pending { color: #a6bdca; }
        .metrics, .rates { margin-top: 7px; color: #a8c9da; font-size: 12px; font-weight: 500; }
        .rates:empty, .metrics:empty { display: none; }
        @media (max-width: 620px) {
          :host { right: 10px; bottom: 10px; width: calc(100vw - 20px); }
          :host([data-stacked]) { right: auto; bottom: auto; width: 100%; }
        }
      </style>
      <section class="panel" aria-live="polite" aria-atomic="true">
        <header>
          <div class="heading"><div class="eyebrow">Layeransicht</div><h2>Druckvorschau wird erzeugt</h2></div>
          <button class="collapse" type="button">Minimieren</button>
          <button class="close" type="button" aria-label="Popup schließen">×</button>
        </header>
        <div class="body">
          <p class="file"></p>
          <p class="phase"></p>
          <p class="detail"></p>
          <div class="progress"><i></i></div>
          <div class="status"><span class="percent"></span><span class="eta"></span></div>
          <div class="metrics"></div>
          <div class="rates"></div>
        </div>
      </section>`;
    this.#root.querySelector(".collapse")?.addEventListener("click", () => {
      this.#collapsed = !this.#collapsed;
      this.#render();
    });
    this.#root.querySelector(".close")?.addEventListener("click", () => {
      this.#dismissed = true;
      this.#render();
    });
  }

  connectedCallback(): void {
    globalThis.addEventListener(SLICE_ACTIVITY_EVENT, this.#onSliceActivity as EventListener);
    this.#render();
  }

  disconnectedCallback(): void {
    globalThis.removeEventListener(SLICE_ACTIVITY_EVENT, this.#onSliceActivity as EventListener);
  }

  readonly #onSliceActivity = (event: CustomEvent<SliceActivityDetail>): void => {
    const detail = event.detail;
    if (!detail?.traceId || !PREVIEW_CODES.has(detail.code)) return;

    if (detail.code === "toolpath_parse_started") {
      this.#traceId = detail.traceId;
      this.#detail = detail;
      this.#collapsed = false;
      this.#dismissed = false;
      this.#render();
      return;
    }

    if (!this.#traceId || detail.traceId !== this.#traceId) return;
    this.#detail = detail;
    this.#render();
  };

  #render(): void {
    const detail = this.#detail;
    this.hidden = !detail || this.#dismissed;
    if (!detail) return;

    const failed = detail.code === "slice_pipeline_failed" || detail.status === "error";
    const ready = detail.code === "preview_ready" && !failed;
    const panel = this.#root.querySelector<HTMLElement>(".panel");
    panel?.classList.toggle("collapsed", this.#collapsed);
    panel?.classList.toggle("success", ready);
    panel?.classList.toggle("error", failed);

    const title = this.#root.querySelector<HTMLElement>("h2");
    if (title) title.textContent = failed ? "Druckvorschau fehlgeschlagen" : ready ? "Druckvorschau fertig" : "Druckvorschau wird erzeugt";
    const file = this.#root.querySelector<HTMLElement>(".file");
    if (file) file.textContent = [detail.fileName, detail.plateName].filter(Boolean).join(" · ") || "Aktuelle Druckplatte";
    const phase = this.#root.querySelector<HTMLElement>(".phase");
    if (phase) phase.textContent = detail.label || "Layeransicht wird vorbereitet";
    const phaseDetail = this.#root.querySelector<HTMLElement>(".detail");
    if (phaseDetail) phaseDetail.textContent = detail.detail || (ready ? "Alle Layer sind geladen und darstellbar." : "Die Layerdaten werden verarbeitet.");

    const progressValue = previewProgress(detail);
    const progress = this.#root.querySelector<HTMLElement>(".progress");
    progress?.classList.toggle("indeterminate", progressValue === null && !failed);
    const bar = this.#root.querySelector<HTMLElement>(".progress > i");
    if (bar) bar.style.width = progressValue === null ? "100%" : `${progressValue}%`;
    const percentLabel = this.#root.querySelector<HTMLElement>(".percent");
    if (percentLabel) percentLabel.textContent = progressValue === null ? "Fortschritt wird ermittelt" : `${Math.round(progressValue)} %`;

    const eta = remainingSeconds(detail.metrics);
    const etaLabel = this.#root.querySelector<HTMLElement>(".eta");
    if (etaLabel) {
      etaLabel.classList.toggle("pending", !ready && !failed && eta === null);
      etaLabel.textContent = failed
        ? "Abgebrochen"
        : ready
          ? "Fertig"
          : eta !== null
            ? `Noch ca. ${formatDuration(eta)}`
            : "ETA wird nach dem ersten Datenblock berechnet";
    }
    const metrics = this.#root.querySelector<HTMLElement>(".metrics");
    if (metrics) metrics.textContent = metricText(detail);
    const rates = this.#root.querySelector<HTMLElement>(".rates");
    if (rates) rates.textContent = rateText(detail.metrics);
    const collapse = this.#root.querySelector<HTMLButtonElement>(".collapse");
    if (collapse) collapse.textContent = this.#collapsed ? "Anzeigen" : "Minimieren";
  }
}

if (!customElements.get("studio-preview-progress-popup")) {
  customElements.define("studio-preview-progress-popup", StudioPreviewProgressPopup);
}
