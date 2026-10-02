import "./audit-log-panel.js";
import "./printer-camera-panel.js";
import "./printer-command-store.js";
import { Ultimate3DPrintSpeedControl } from "./print-speed-control.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import { printStatusLabel } from "./printer-command-policy.js";
import type { Ultimate3DPrinterActions } from "./printer-command-store.js";
import {
  issueMarkup,
  PRINTER_ISSUE_STYLES,
  primaryPrinterIssue,
  printerIssues,
} from "./printer-issues.js";
import { remainingTimeLabel } from "./print-remaining-time.js";
import type { PrinterCameraPanel } from "./printer-camera-panel.js";
import type { V6Job, V6Printer } from "./v6-api.js";
import { printLayerLabel, printSpeedLabel } from "./print-live-telemetry.js";

type HassState = Readonly<{
  state?: string;
  attributes?: Readonly<Record<string, unknown>>;
  last_changed?: string;
  last_updated?: string;
}>;
type HassLike = Readonly<{
  states: Readonly<Record<string, HassState>>;
}>;
type DataRecord = Readonly<Record<string, unknown>>;

function record(value: unknown): DataRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as DataRecord
    : {};
}

function records(value: unknown): DataRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is DataRecord => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    : [];
}

function text(value: unknown, fallback = "–"): string {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function numberValue(value: unknown): number | null {
  const parsed = Number(value);
  return value === null || value === undefined || value === "" || !Number.isFinite(parsed)
    ? null
    : parsed;
}

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function temperature(current: unknown, target: unknown): string {
  const actual = numberValue(current);
  const goal = numberValue(target);
  if (actual === null && goal === null) return "–";
  return goal === null
    ? `${actual?.toFixed(1) ?? "–"} °C`
    : `${actual?.toFixed(1) ?? "–"} / ${goal.toFixed(1)} °C`;
}

function metric(label: string, value: unknown, detail = ""): string {
  return `<article class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong>${detail ? `<span>${esc(detail)}</span>` : ""}</article>`;
}

function lifecycleEntries(): unknown[] {
  try {
    const value = JSON.parse(sessionStorage.getItem("ultimate-3d-studio-v6:lifecycle") || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

export class Ultimate3DSystemWorkspaceV5 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #state: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #hass: HassLike | null = null;
  #mounted = false;

  set hass(value: HassLike | null) {
    this.#hass = value;
    this.#forwardHass();
    this.#updateOverview();
  }

  connectedCallback(): void {
    if (!this.#mounted) this.#mount();
    if (!this.#unsubscribe) {
      this.#unsubscribe = jobActivityStore.subscribe((state) => {
        this.#state = state;
        this.#updateOverview();
      });
    }
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  #mount(): void {
    this.#root.innerHTML = `<style>${PRINTER_ISSUE_STYLES}
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff;font:13px/1.4 Segoe UI,sans-serif}*{box-sizing:border-box}.page{padding:18px}.head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.head h1{margin:0}.head p{margin:4px 0 0;color:#91a5bb}.grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(320px,.85fr);gap:14px;margin-top:14px}.panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}.panel h2{margin:0;padding:12px 14px;border-bottom:1px solid #26384f;font-size:15px}.body{padding:13px}.wide{grid-column:1/-1}.summary{padding:11px;border:1px solid #26384f;border-radius:9px;background:#0c1622}.summary strong,.summary small{display:block}.summary small{margin-top:4px;color:#8298ae}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.metric{min-width:0;padding:9px;border:1px solid #26384f;border-radius:8px;background:#0c1622}.metric small,.metric strong,.metric span{display:block;overflow:hidden;text-overflow:ellipsis}.metric small{color:#8298ae;font-size:10px;text-transform:uppercase}.metric strong{margin-top:3px}.metric span{margin-top:2px;color:#8198ad;font-size:10px}.slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.slot{display:flex;align-items:center;gap:9px;padding:9px;border:1px solid #26384f;border-radius:8px;background:#0c1622}.slot.active{border-color:#34b9ff}.slot i{width:15px;height:34px;border-radius:5px;background:var(--slot-color)}.slot div{min-width:0;flex:1}.slot small{display:block;color:#8298ae}.empty{padding:18px;color:#8298ae;text-align:center}.raw{max-height:360px;overflow:auto;padding:10px;border:1px solid #26384f;border-radius:8px;background:#07111b;color:#b8c9d8;font:10px/1.4 Consolas,monospace;white-space:pre-wrap}.issue-list{display:grid;gap:10px}.issue-clear{padding:12px;border:1px solid #27734c;border-radius:9px;background:#102b1d;color:#8ff0b5}@media(max-width:1100px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:850px){.grid{grid-template-columns:1fr}.wide{grid-column:auto}}@media(max-width:560px){.page{padding:10px}.metrics{grid-template-columns:1fr}}
    </style><section class="page"><header class="head"><div><h1>System</h1><p>Studio-Laufzeit, Druckertelemetrie, Störungen, Home Assistant und Frontend-Lifecycle.</p></div><strong id="printer-name">Drucker</strong></header><div class="grid"><printer-camera-panel title="Kamera-Snapshot" storage-key="system"></printer-camera-panel><article class="panel"><h2>Druckertelemetrie und Steuerung</h2><div class="body"><div class="summary"><strong id="job-name">Kein aktiver Druckauftrag</strong><small id="job-status">–</small></div><div class="metrics" id="printer-metrics"></div><ultimate-3d-printer-actions id="actions"></ultimate-3d-printer-actions><div style="margin-top:10px"><ultimate-3d-print-speed-control id="system-speed"></ultimate-3d-print-speed-control></div></div></article><article class="panel wide"><h2>Aktive Druckerstörungen</h2><div class="body" id="printer-issues"><span class="empty">Störungsstatus wird geladen …</span></div></article><article class="panel wide"><h2>Studio- und Home-Assistant-Laufzeit</h2><div class="body"><div class="metrics" id="runtime-metrics"></div></div></article><article class="panel wide"><h2>AMS / AMS Lite</h2><div class="body" id="ams"><span class="empty">Materialsystem wird geladen …</span></div></article><article class="panel wide"><h2>Diagnosedaten</h2><div class="body"><details><summary>Aktuellen Studio-Zustand anzeigen</summary><pre class="raw" id="raw-diagnostics"></pre></details></div></article><ultimate-3d-audit-log-panel class="wide"></ultimate-3d-audit-log-panel></div></section>`;
    this.#mounted = true;
    this.#forwardHass();
    this.#updateOverview();
  }

  #printer(): V6Printer | null {
    return this.#state.printers[0] ?? null;
  }

  #job(printer: V6Printer | null): V6Job | null {
    const current = this.#state.jobs.current || [];
    const printerId = String(printer?.printer_id || "");
    return current.find((job) => String(job.printer_id || "") === printerId) ?? current[0] ?? null;
  }

  #set(id: string, value: unknown): void {
    const node = this.#root.querySelector<HTMLElement>(`#${id}`);
    const next = String(value);
    if (node && node.textContent !== next) node.textContent = next;
  }

  #updateOverview(): void {
    if (!this.#mounted) return;
    const printer = this.#printer();
    const job = this.#job(printer);
    const issues = printerIssues(printer);
    const status = printStatusLabel(job?.status || printer?.printer_state || "Bereit");
    const progress = Math.max(0, Math.min(100, numberValue(job?.progress ?? printer?.progress) ?? 0));
    this.#set("printer-name", printer?.name || "V6");
    this.#set("job-name", job ? text(job.file || job.model_name, "Aktiver Druckauftrag") : "Kein aktiver Druckauftrag");
    this.#set("job-status", issues.length ? `${issues.length} aktive Störung${issues.length === 1 ? "" : "en"} · Drucker ${status}` : job ? status : `Druckerstatus: ${status}`);

    const metrics = this.#root.querySelector<HTMLElement>("#printer-metrics");
    if (metrics) metrics.innerHTML = [
      metric("Verbindung", printer?.connection_state),
      metric("Druckerzustand", printer?.printer_state),
      metric("Aktive Störungen", issues.length, issues[0] ? String(issues[0].code || "") : "keine"),
      metric("Druckphase", printer?.print_stage_label, text(printer?.print_stage_detail, "")),
      metric("Fortschritt", `${progress.toFixed(0)} %`),
      metric("Düse", temperature(printer?.nozzle_temperature, printer?.nozzle_target_temperature)),
      metric("Druckbett", temperature(printer?.bed_temperature, printer?.bed_target_temperature)),
      metric("Bauraum", temperature(printer?.chamber_temperature, printer?.chamber_target_temperature)),
      metric("Schicht", printLayerLabel(job, printer).replace(/^Layer\s*/, "")),
      metric("Restzeit", remainingTimeLabel(job, printer)),
      metric("Aktuelle Datei", job?.file || job?.model_name || printer?.current_file),
      metric("Anbieter", printer?.provider),
      metric("Druckgeschwindigkeit", printSpeedLabel(printer)),
    ].join("");

    const issueHost = this.#root.querySelector<HTMLElement>("#printer-issues");
    if (issueHost) issueHost.innerHTML = issues.length
      ? `<div class="issue-list">${issues.map((issue) => issueMarkup(issue)).join("")}</div>`
      : '<div class="issue-clear">Keine aktive Druckerstörung. Behobene Störungen bleiben im System- und Audit-Log nachvollziehbar.</div>';

    const states = this.#hass?.states ?? {};
    const entityValues = Object.values(states);
    const unavailable = entityValues.filter((item) => item.state === "unavailable").length;
    const unknown = entityValues.filter((item) => item.state === "unknown").length;
    const v6Entities = Object.keys(states).filter((id) => id.includes("ultimate_3d") || id.includes("printer_slicing_server")).length;
    const lifecycle = lifecycleEntries();
    const runtime = this.#root.querySelector<HTMLElement>("#runtime-metrics");
    if (runtime) runtime.innerHTML = [
      metric("V6-Aktualisierung", this.#state.updatedAt ? new Date(this.#state.updatedAt).toLocaleTimeString("de-DE") : "–"),
      metric("Aktiver Slicer", this.#state.slicer?.status || "kein Auftrag", this.#state.slicer?.id || ""),
      metric("Druckaufträge", this.#state.jobs.current?.length ?? 0, `${this.#state.jobs.queue?.length ?? 0} Warteschlange · ${this.#state.jobs.history?.length ?? 0} Verlauf`),
      metric("Befehlsfunktionen", this.#state.capabilities.length),
      metric("HA-Entitäten", entityValues.length, `${v6Entities} V6/Slicing-Server`),
      metric("Nicht verfügbar", unavailable, `${unknown} unbekannt`),
      metric("V6-API", this.#state.error ? "Fehler" : "bereit", this.#state.error),
      metric("Frontend-Lifecycle", lifecycle.length, text(record(lifecycle.at(-1)).event, "keine Ereignisse")),
      metric("Browser", navigator.userAgent.split(" ").slice(-2).join(" ")),
    ].join("");

    this.#renderAms(printer);
    const actions = this.#root.querySelector<Ultimate3DPrinterActions>("#actions");
    const speed = this.#root.querySelector<Ultimate3DPrintSpeedControl>("#system-speed");
    if (actions) {
      actions.printer = printer;
      actions.job = job;
      actions.issue = primaryPrinterIssue(printer);
      actions.issueMode = false;
      actions.capabilities = this.#state.capabilities;
    }
    if (speed) {
      speed.printer = printer;
      speed.job = job;
      speed.capabilities = this.#state.capabilities;
    }
    const raw = this.#root.querySelector<HTMLElement>("#raw-diagnostics");
    if (raw) raw.textContent = JSON.stringify({
      printer,
      active_issues: issues,
      active_job: job,
      slicer: this.#state.slicer,
      jobs: this.#state.jobs,
      capabilities: this.#state.capabilities,
      frontend_lifecycle: lifecycle,
    }, null, 2);
    this.#forwardHass();
  }

  #renderAms(printer: V6Printer | null): void {
    const host = this.#root.querySelector<HTMLElement>("#ams");
    if (!host) return;
    const ams = record(printer?.ams);
    const slots = records(ams.slots);
    if (ams.available !== true || !slots.length) {
      host.innerHTML = '<span class="empty">Kein AMS beziehungsweise AMS Lite erkannt.</span>';
      return;
    }
    host.innerHTML = `<div class="slots">${slots.map((slot) => {
      const color = typeof slot.color === "string" && /^#[0-9a-f]{6}$/i.test(slot.color) ? slot.color : "#536273";
      const remaining = numberValue(slot.remaining_percent);
      return `<article class="slot ${slot.active === true ? "active" : ""}"><i style="--slot-color:${color}"></i><div><strong>${esc(text(slot.sub_brand || slot.material, slot.present === true ? "Filament" : "Leer"))}</strong><small>AMS ${esc(slot.display_slot || slot.global_id || slot.tray_id)} · ${esc(text(slot.material))}</small><small>${slot.rfid_detected === true ? "RFID erkannt" : "Manuelles Profil"}</small></div><span>${remaining === null ? "–" : `${remaining.toFixed(0)} %`}</span></article>`;
    }).join("")}</div>`;
  }

  #forwardHass(): void {
    const camera = this.#root.querySelector<PrinterCameraPanel>("printer-camera-panel");
    if (camera) camera.hass = this.#hass;
  }
}

if (!customElements.get("ultimate-3d-system-workspace")) {
  customElements.define("ultimate-3d-system-workspace", Ultimate3DSystemWorkspaceV5);
}
