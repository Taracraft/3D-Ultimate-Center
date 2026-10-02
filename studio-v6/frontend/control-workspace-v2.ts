import "./printer-camera-panel.js";
import "./printer-command-store.js";
import { Ultimate3DPrintSpeedControl } from "./print-speed-control.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import { isActivePrintState, printStatusLabel } from "./printer-command-policy.js";
import type { Ultimate3DPrinterActions } from "./printer-command-store.js";
import {
  issueMarkup,
  PRINTER_ISSUE_STYLES,
  primaryPrinterIssue,
  printerIssues,
} from "./printer-issues.js";
import { remainingTimeLabel } from "./print-remaining-time.js";
import { PROGRESS_STYLES, progressMarkup, type ProgressTone } from "./progress-ui.js";
import type { PrinterCameraPanel } from "./printer-camera-panel.js";
import type { V6Job, V6Printer } from "./v6-api.js";
import { PRINT_PHASES } from "./print-phase-progress.js";
import { printLayerLabel, printSpeedLabel, resolveLivePrintPhase } from "./print-live-telemetry.js";

type HassLike = Readonly<{ states: Readonly<Record<string, unknown>> }>;

function clamp(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : 0;
}

function tone(status: unknown): ProgressTone {
  const value = String(status || "").toLowerCase();
  if (/fehler|failed|error|interrupted/.test(value)) return "red";
  if (/pause|cancel|abbruch|stopp/.test(value)) return "amber";
  if (/fertig|complete|success|idle|bereit/.test(value)) return "green";
  return "blue";
}

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

export class Ultimate3DSteuerungWorkspaceV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #hass: HassLike | null = null;
  #activity: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #mounted = false;

  set hass(value: HassLike | null) {
    this.#hass = value;
    this.#forwardHass();
  }

  get hass(): HassLike | null { return this.#hass; }

  connectedCallback(): void {
    this.#mount();
    if (!this.#unsubscribe) {
      this.#unsubscribe = jobActivityStore.subscribe((snapshot) => {
        this.#activity = snapshot;
        this.#update();
      });
    }
    this.#update();
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  #mount(): void {
    if (this.#mounted) return;
    this.#root.innerHTML = `<style>${PROGRESS_STYLES}${PRINTER_ISSUE_STYLES}
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff}*{box-sizing:border-box}.page{padding:20px}.stats{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:12px;margin:16px 0}.stat,.panel{border:1px solid #26384f;border-radius:12px;background:#101925}.stat{padding:14px}.stat label{display:block;color:#91a4bc;font-size:10px;text-transform:uppercase}.stat b{display:block;margin-top:7px;font-size:22px}.progress{margin-bottom:14px}.panel{margin-bottom:14px}.panel h2{margin:0;padding:14px;border-bottom:1px solid #26384f;font-size:15px}.body{padding:14px}.row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:11px;border:1px solid #25374d;border-radius:9px;background:#0d1622}.row small{display:block;margin-top:4px;color:#8399ae;overflow-wrap:anywhere}.status{align-self:start;padding:5px 8px;border:1px solid #31506e;border-radius:999px;color:#a7c8e2}.status.active{border-color:#3e9d6b;color:#9af0bb}.status.problem{border-color:#b64d5a;background:#35171d;color:#ffdce1}.commands{margin-top:14px}.device-actions{display:flex;justify-content:flex-end;margin-top:12px}.device-actions button{min-height:38px;padding:8px 11px;border:1px solid #8f3f4b;border-radius:8px;background:#3a171d;color:#ffd7dc;cursor:pointer;font-weight:700}.device-actions button:disabled{opacity:.45;cursor:not-allowed}.notice{padding:11px;margin:12px 0;border-radius:10px}.error{background:#3a171d;color:#ffd9dd}.camera{margin-top:14px}.current-stage{padding:12px;border:1px solid #2e5d7c;border-radius:10px;background:#10263a}.current-stage strong{display:block;font-size:16px;color:#8fe3ff}.current-stage small{display:block;margin-top:5px;color:#a5b9cb}.stages ol{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0 0;padding:0;list-style:none}.stages li{display:flex;align-items:center;gap:8px;min-height:44px;padding:9px;border:1px solid #26384f;border-radius:9px;color:#8195aa;background:#0d1622}.stages li.active{border-color:#42c8ff;background:#12314a;color:#eefaff}.stages li.done{border-color:#27734c;background:#102b1d;color:#8ff0b5}.stages li span{font-size:15px}.issue-list{display:grid;gap:10px}.issue-instruction{margin:10px 0 0;color:#ffd9dd;font-weight:700}@media(max-width:1100px){.stats{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:900px){.stages ol{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:800px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.stages ol,.stats{grid-template-columns:1fr}}
    </style><section class="page"><h1>Steuerzentrale</h1><p>Liveübersicht und sichere Steuerung des aktuell verbundenen Druckers.</p><div id="dynamic"></div><article class="panel" id="printer-panel"><h2>Drucker</h2><div class="body"><div id="printer-summary">Kein Drucker erkannt.</div><div class="commands" id="printer-commands"><ultimate-3d-printer-actions id="printer-actions"></ultimate-3d-printer-actions></div><div class="commands"><ultimate-3d-print-speed-control id="print-speed"></ultimate-3d-print-speed-control></div><div class="device-actions"><button id="remove-printer" type="button" disabled>Drucker entfernen</button></div></div></article><div class="camera"><printer-camera-panel title="Druckerkamera" storage-key="steuerzentrale" collapsed></printer-camera-panel></div></section>`;
    this.#root.querySelector<HTMLButtonElement>("#remove-printer")?.addEventListener("click", () => this.#openPrinterManagement());
    this.#mounted = true;
    this.#forwardHass();
  }

  #printer(): V6Printer | null { return this.#activity.printers[0] ?? null; }

  #currentJob(printer: V6Printer | null): V6Job | null {
    const current = this.#activity.jobs.current || [];
    const printerId = String(printer?.printer_id || "");
    return current.find((job) => String(job.printer_id || "") === printerId) ?? current[0] ?? null;
  }

  #progress(printer: V6Printer | null, job: V6Job | null): string {
    const remaining = remainingTimeLabel(job, printer);
    if (job) {
      const status = String(printer?.print_stage_label || printStatusLabel(job.status || printer?.printer_state || "Unbekannt"));
      return progressMarkup({
        label: String(job.file || job.model_name || printer?.current_file || "Aktiver Druckauftrag"),
        detail: `${status} · Restzeit ${remaining}`,
        value: clamp(job.progress ?? printer?.progress),
        tone: printerIssues(printer).length ? "red" : tone(status),
      });
    }
    const printerState = printStatusLabel(printer?.printer_state || "Bereit");
    return progressMarkup({
      label: "Kein aktiver Druckauftrag",
      detail: printer ? `Druckerstatus: ${printerState} · Restzeit ${remaining}` : "Kein Drucker erkannt",
      value: 0,
      tone: printerIssues(printer).length ? "red" : isActivePrintState(printer?.printer_state) ? "blue" : tone(printerState),
    });
  }

  #phaseMarkup(printer: V6Printer | null, job: V6Job | null): string {
    if (!printer) return "";
    const progress = resolveLivePrintPhase(job, printer);
    const seen = new Set(progress.seenKeys);
    const state = String(job?.status || printer.printer_state || "").toLowerCase();
    const jobEnded = ["completed", "complete", "finished", "finish"].includes(state) || clamp(job?.progress ?? printer.progress) >= 100;
    const labels = PRINT_PHASES.map((phase, index) => {
      const active = index === progress.activeIndex;
      const observed = seen.has(phase.key);
      const done = observed && !active && (!phase.doneOnlyWhenJobEnds || jobEnded);
      const visited = observed && !active && !done;
      const unreported = !active && !observed && progress.activeIndex > index;
      const className = active ? "active" : done ? "done" : visited ? "active" : "";
      const icon = active ? "●" : done ? "✓" : visited ? "◐" : unreported ? "–" : "○";
      const title = unreported ? ' title="Vom Drucker nicht als eigener Status gemeldet"' : "";
      return `<li class="${className}"${title}><span>${icon}</span><b>${esc(phase.label)}</b></li>`;
    }).join("");
    const stageCode = printer.print_stage_code === null || printer.print_stage_code === undefined ? "" : ` · Stufe ${esc(printer.print_stage_code)}`;
    return `<article class="panel stages"><h2>Aktueller Druckablauf</h2><div class="body"><div class="current-stage"><strong>${esc(progress.currentLabel)}</strong><small>${esc(progress.detail)}${stageCode}<br>${esc(printLayerLabel(job, printer))} · Tempo ${esc(printSpeedLabel(printer))}</small></div><ol>${labels}</ol></div></article>`;
  }

  #issueMarkup(printer: V6Printer | null): string {
    const issues = printerIssues(printer);
    if (!issues.length) return "";
    return `<article class="panel"><h2>Aktive Druckerstörung${issues.length > 1 ? `en · ${issues.length}` : ""}</h2><div class="body"><div class="issue-list">${issues.map((issue) => issueMarkup(issue)).join("")}</div><p class="issue-instruction">Ursache am Drucker beheben und anschließend unten ausdrücklich fortsetzen.</p></div></article>`;
  }

  #update(): void {
    if (!this.isConnected) return;
    this.#mount();
    const host = this.#root.querySelector<HTMLElement>("#dynamic");
    const summary = this.#root.querySelector<HTMLElement>("#printer-summary");
    const commands = this.#root.querySelector<HTMLElement>("#printer-commands");
    const removeButton = this.#root.querySelector<HTMLButtonElement>("#remove-printer");
    const actions = this.#root.querySelector<Ultimate3DPrinterActions>("#printer-actions");
    const speed = this.#root.querySelector<Ultimate3DPrintSpeedControl>("#print-speed");
    if (!host || !summary || !commands || !removeButton || !actions || !speed) return;
    const printer = this.#printer();
    const job = this.#currentJob(printer);
    const issues = printerIssues(printer);
    const remaining = remainingTimeLabel(job, printer);
    const ready = this.#activity.health?.status === "ready";
    const online = this.#activity.printers.filter((item) => item.connection_state === "connected").length;
    const printerStatus = printStatusLabel(printer?.printer_state || "Unbekannt");
    const active = Boolean(job) || isActivePrintState(printer?.printer_state);
    host.innerHTML = `${this.#activity.error ? `<div class="notice error">${esc(this.#activity.error)}</div>` : ""}<div class="stats"><div class="stat"><label>Laufzeit</label><b>${ready ? "Bereit" : "Wartet"}</b></div><div class="stat"><label>Drucker</label><b>${this.#activity.printers.length}</b></div><div class="stat"><label>Online</label><b>${online}</b></div><div class="stat"><label>Störungen</label><b>${issues.length}</b></div><div class="stat"><label>Restzeit</label><b>${esc(remaining)}</b></div><div class="stat"><label>Layer</label><b>${esc(printLayerLabel(job, printer).replace(/^Layer\s*/, ""))}</b></div><div class="stat"><label>Tempo</label><b>${esc(printSpeedLabel(printer))}</b></div></div>${this.#issueMarkup(printer)}<div class="progress">${this.#progress(printer, job)}</div>${this.#phaseMarkup(printer, job)}`;
    summary.innerHTML = printer
      ? `<div class="row"><div><b>${esc(printer.name || printer.printer_id)}</b><small>${job ? `Aktiver Auftrag: ${esc(job.file || job.model_name || printer.current_file || "Unbenannt")}` : `Letzte gemeldete Datei: ${esc(printer.current_file || "–")}`}<br>Restzeit: ${esc(remaining)}</small></div><span class="status ${issues.length ? "problem" : active ? "active" : ""}">${issues.length ? `${issues.length} Störung${issues.length === 1 ? "" : "en"}` : esc(printerStatus)}</span></div>`
      : "Kein Drucker erkannt.";
    commands.hidden = !printer;
    removeButton.disabled = !printer || active;
    actions.printer = printer;
    actions.job = job;
    actions.issue = primaryPrinterIssue(printer);
    actions.issueMode = false;
    actions.capabilities = this.#activity.capabilities;
    speed.printer = printer;
    speed.job = job;
    speed.capabilities = this.#activity.capabilities;
    this.#forwardHass();
  }

  #forwardHass(): void {
    const camera = this.#root.querySelector<PrinterCameraPanel>("printer-camera-panel");
    if (camera) camera.hass = this.#hass;
  }

  #openPrinterManagement(): void {
    const path = "/config/integrations/integration/ultimate_3d_studio_v6";
    window.history.pushState(null, "", path);
    window.dispatchEvent(new Event("location-changed"));
    window.dispatchEvent(new PopStateEvent("popstate"));
  }
}

if (!customElements.get("ultimate-3d-steuerung-workspace")) {
  customElements.define("ultimate-3d-steuerung-workspace", Ultimate3DSteuerungWorkspaceV2);
}
