import "./audit-log-panel.js";
import "./printer-camera-panel.js";
import "./printer-command-store.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import { printStatusLabel } from "./printer-command-policy.js";
import type { Ultimate3DPrinterActions } from "./printer-command-store.js";
import { PROGRESS_STYLES, progressMarkup } from "./progress-ui.js";
import type { PrinterCameraPanel } from "./printer-camera-panel.js";
import type { V6Job, V6Printer } from "./v6-api.js";

type HassLike = Readonly<{ states: Readonly<Record<string, unknown>> }>;
type DataRecord = Readonly<Record<string, unknown>>;

const esc = (value: unknown): string => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[char] || char));

function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function record(value: unknown): DataRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as DataRecord : {};
}

function records(value: unknown): readonly DataRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is DataRecord => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    : [];
}

function temperature(current: unknown, target: unknown): string {
  const actual = numberValue(current);
  const goal = numberValue(target);
  if (actual === null && goal === null) return "–";
  return goal === null
    ? `${actual?.toFixed(1) ?? "–"} °C`
    : `${actual?.toFixed(1) ?? "–"} / ${goal.toFixed(1)} °C`;
}

export class Ultimate3DSystemWorkspaceV3 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #state: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #hass: HassLike | null = null;

  set hass(value: HassLike | null) {
    this.#hass = value;
    this.#forwardHass();
  }

  connectedCallback(): void {
    if (this.#unsubscribe) return;
    this.#unsubscribe = jobActivityStore.subscribe((state) => {
      this.#state = state;
      this.#render();
    });
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  #printer(): V6Printer | null {
    return this.#state.printers[0] ?? null;
  }

  #job(printer: V6Printer | null): V6Job | null {
    const current = this.#state.jobs.current || [];
    const printerId = String(printer?.printer_id || "");
    return current.find((job) => String(job.printer_id || "") === printerId) ?? current[0] ?? null;
  }

  #metric(label: string, value: unknown): string {
    return `<div class="metric"><small>${esc(label)}</small><strong>${esc(value ?? "–")}</strong></div>`;
  }

  #ams(printer: V6Printer | null): string {
    const ams = record(printer?.ams);
    const slots = records(ams.slots);
    if (ams.available !== true || !slots.length) {
      return '<div class="empty">Kein AMS beziehungsweise AMS Lite erkannt.</div>';
    }
    return `<div class="ams-head"><strong>${esc(ams.kind || "AMS")}</strong><span>${esc(ams.occupied_slot_count || 0)} von ${esc(ams.slot_count || slots.length)} belegt</span></div><div class="slots">${slots.map((slot) => {
      const color = typeof slot.color === "string" && /^#[0-9a-f]{6}$/i.test(slot.color) ? slot.color : "#536273";
      const remaining = numberValue(slot.remaining_percent);
      return `<article class="slot ${slot.active === true ? "active" : ""}"><i style="--slot-color:${esc(color)}"></i><div><strong>${esc(slot.material || (slot.present === true ? "Filament" : "Leer"))}</strong><small>Slot ${esc(slot.global_id || slot.tray_id || "–")}</small></div><span>${remaining === null ? "–" : `${remaining.toFixed(0)} %`}</span></article>`;
    }).join("")}</div>`;
  }

  #forwardHass(): void {
    const camera = this.#root.querySelector<PrinterCameraPanel>("printer-camera-panel");
    if (camera) camera.hass = this.#hass;
  }

  #render(): void {
    if (!this.isConnected) return;
    const printer = this.#printer();
    const job = this.#job(printer);
    const progress = Math.max(0, Math.min(100, numberValue(job?.progress ?? printer?.progress) ?? 0));
    const status = printStatusLabel(job?.status || printer?.printer_state || "Unbekannt");
    const filename = String(job?.file || job?.model_name || printer?.current_file || "Kein aktiver Druckauftrag");
    const layer = job?.current_layer ?? printer?.current_layer ?? "–";
    const layers = job?.total_layers ?? printer?.total_layers ?? "–";
    const remaining = numberValue(job?.remaining_time_minutes ?? printer?.remaining_time_minutes);

    this.#root.innerHTML = `<style>${PROGRESS_STYLES}
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff}*{box-sizing:border-box}.page{padding:20px}.head{display:flex;justify-content:space-between;gap:14px}.head h1{margin:0}.head p{margin:6px 0 0;color:#91a5bb}.error,.empty{padding:12px;border:1px solid #2a3c53;border-radius:10px;background:#111b29;color:#91a5bb}.error{margin-top:12px;border-color:#8f3f4b;color:#ffd7dc}.grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(320px,.9fr);gap:14px;margin-top:15px}.panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}.panel h2{margin:0;padding:13px 15px;border-bottom:1px solid #26384f;font-size:15px}.body{padding:14px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:11px 0}.metric{padding:10px;border:1px solid #26384f;border-radius:9px;background:#0c1622}.metric small{display:block;color:#8298ae;font-size:10px;text-transform:uppercase}.metric strong{display:block;margin-top:4px;overflow-wrap:anywhere}.wide{grid-column:1/-1}.ams-head,.slot{display:flex;align-items:center;justify-content:space-between;gap:10px}.ams-head{margin-bottom:10px;color:#91a5bb}.slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.slot{padding:10px;border:1px solid #26384f;border-radius:9px;background:#0c1622}.slot.active{border-color:#34b9ff}.slot i{width:16px;height:36px;border-radius:5px;background:var(--slot-color)}.slot div{min-width:0;flex:1}.slot small{display:block;color:#8298ae}@media(max-width:900px){.grid{grid-template-columns:1fr}}@media(max-width:560px){.metrics{grid-template-columns:1fr}}
    </style><section class="page"><div class="head"><div><h1>System</h1><p>Kamera, Live-Telemetrie, sichere Drucksteuerung, Materialsystem und Audit-Log.</p></div><strong>${esc(printer?.name || "Drucker")}</strong></div>${this.#state.error ? `<div class="error">${esc(this.#state.error)}</div>` : ""}<div class="grid"><printer-camera-panel title="Kamera-Snapshot" storage-key="system"></printer-camera-panel><article class="panel"><h2>Druckertelemetrie und Steuerung</h2><div class="body">${progressMarkup({ label: filename, detail: status, value: progress })}<div class="metrics">${this.#metric("Status", status)}${this.#metric("Verbindung", printer?.connection_state || "–")}${this.#metric("Düse", temperature(printer?.nozzle_temperature, printer?.nozzle_target_temperature))}${this.#metric("Druckbett", temperature(printer?.bed_temperature, printer?.bed_target_temperature))}${this.#metric("Schicht", `${layer} / ${layers}`)}${this.#metric("Restzeit", remaining === null ? "–" : `${remaining.toFixed(0)} min`)}</div><ultimate-3d-printer-actions id="printer-actions"></ultimate-3d-printer-actions></div></article><article class="panel wide"><h2>AMS / AMS Lite</h2><div class="body">${this.#ams(printer)}</div></article><ultimate-3d-audit-log-panel class="wide"></ultimate-3d-audit-log-panel></div></section>`;

    const actions = this.#root.querySelector<Ultimate3DPrinterActions>("#printer-actions");
    if (actions) {
      actions.printer = printer;
      actions.job = job;
      actions.capabilities = this.#state.capabilities;
    }
    this.#forwardHass();
  }
}

if (!customElements.get("ultimate-3d-system-workspace")) {
  customElements.define("ultimate-3d-system-workspace", Ultimate3DSystemWorkspaceV3);
}
