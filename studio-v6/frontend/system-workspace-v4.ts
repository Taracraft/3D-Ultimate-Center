import "./audit-log-panel.js";
import "./printer-camera-panel.js";
import "./printer-command-store.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import { printStatusLabel } from "./printer-command-policy.js";
import type { Ultimate3DPrinterActions } from "./printer-command-store.js";
import type { PrinterCameraPanel } from "./printer-camera-panel.js";
import type { V6Job, V6Printer } from "./v6-api.js";

type HassLike = Readonly<{ states: Readonly<Record<string, unknown>> }>;
type DataRecord = Readonly<Record<string, unknown>>;

function numberValue(value: unknown): number | null {
  const parsed = Number(value);
  return value === null || value === undefined || value === "" || !Number.isFinite(parsed)
    ? null
    : parsed;
}

function record(value: unknown): DataRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as DataRecord
    : {};
}

function records(value: unknown): readonly DataRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is DataRecord => Boolean(item && typeof item === "object" && !Array.isArray(item)))
    : [];
}

function text(value: unknown, fallback = "–"): string {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function temperature(current: unknown, target: unknown): string {
  const actual = numberValue(current);
  const goal = numberValue(target);
  if (actual === null && goal === null) return "–";
  return goal === null
    ? `${actual?.toFixed(1) ?? "–"} °C`
    : `${actual?.toFixed(1) ?? "–"} / ${goal.toFixed(1)} °C`;
}

export class Ultimate3DSystemWorkspaceV4 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #state: JobActivitySnapshot = jobActivityStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #hass: HassLike | null = null;
  #mounted = false;
  #amsSignature = "";

  set hass(value: HassLike | null) {
    this.#hass = value;
    this.#forwardHass();
  }

  connectedCallback(): void {
    if (!this.#mounted) this.#mount();
    if (this.#unsubscribe) return;
    this.#unsubscribe = jobActivityStore.subscribe((state) => {
      this.#state = state;
      this.#update();
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
    return current.find((job) => String(job.printer_id || "") === printerId)
      ?? current[0]
      ?? null;
  }

  #mount(): void {
    this.#root.innerHTML = `<style>
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff}
      *{box-sizing:border-box}.page{padding:20px}.head{display:flex;justify-content:space-between;gap:12px}.head h1{margin:0}.head p{margin:5px 0 0;color:#91a5bb}.grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(320px,.9fr);gap:14px;margin-top:14px}.panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}.panel h2{margin:0;padding:12px 14px;border-bottom:1px solid #26384f;font-size:15px}.body{padding:13px}.summary{padding:11px;border:1px solid #26384f;border-radius:9px;background:#0c1622}.summary strong,.summary small{display:block}.summary small{margin-top:4px;color:#8298ae}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:10px 0}.metric{padding:9px;border:1px solid #26384f;border-radius:8px;background:#0c1622}.metric small,.metric strong{display:block}.metric small{color:#8298ae;font-size:10px;text-transform:uppercase}.metric strong{margin-top:4px}.wide{grid-column:1/-1}.slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px}.slot{display:flex;align-items:center;gap:9px;padding:9px;border:1px solid #26384f;border-radius:8px;background:#0c1622}.slot.active{border-color:#34b9ff}.slot i{width:15px;height:34px;border-radius:5px;background:var(--slot-color)}.slot div{min-width:0;flex:1}.slot small{display:block;color:#8298ae}.error{display:none;margin-top:10px;padding:10px;border:1px solid #8f3f4b;border-radius:9px;background:#351b21;color:#ffd7dc}.error.visible{display:block}.empty{color:#8298ae}@media(max-width:900px){.grid{grid-template-columns:1fr}}@media(max-width:560px){.metrics{grid-template-columns:1fr}}
    </style><section class="page"><header class="head"><div><h1>System</h1><p>Livewerte ohne periodischen Neuaufbau der Oberfläche.</p></div><strong id="printer-name">V6</strong></header><div class="error" id="error"></div><div class="grid"><printer-camera-panel title="Kamera-Snapshot" storage-key="system"></printer-camera-panel><article class="panel"><h2>Druckertelemetrie und Steuerung</h2><div class="body"><div class="summary"><strong id="job-name">Kein aktiver Druckauftrag</strong><small id="job-status">–</small></div><div class="metrics"><div class="metric"><small>Verbindung</small><strong id="connection">–</strong></div><div class="metric"><small>Fortschritt</small><strong id="progress">0 %</strong></div><div class="metric"><small>Düse</small><strong id="nozzle">–</strong></div><div class="metric"><small>Druckbett</small><strong id="bed">–</strong></div><div class="metric"><small>Schicht</small><strong id="layer">–</strong></div><div class="metric"><small>Restzeit</small><strong id="remaining">–</strong></div></div><ultimate-3d-printer-actions id="actions"></ultimate-3d-printer-actions></div></article><article class="panel wide"><h2>AMS / AMS Lite</h2><div class="body" id="ams"><span class="empty">Materialsystem wird geladen …</span></div></article><ultimate-3d-audit-log-panel class="wide"></ultimate-3d-audit-log-panel></div></section>`;
    this.#mounted = true;
    this.#forwardHass();
  }

  #set(id: string, value: unknown): void {
    const node = this.#root.querySelector<HTMLElement>(`#${id}`);
    const next = String(value);
    if (node && node.textContent !== next) node.textContent = next;
  }

  #update(): void {
    const printer = this.#printer();
    const job = this.#job(printer);
    const status = printStatusLabel(job?.status || printer?.printer_state || "Bereit");
    const progress = Math.max(0, Math.min(100, numberValue(job?.progress ?? printer?.progress) ?? 0));
    this.#set("printer-name", printer?.name || "V6");
    this.#set("job-name", job ? text(job.file || job.model_name, "Aktiver Druckauftrag") : "Kein aktiver Druckauftrag");
    this.#set("job-status", job ? status : `Druckerstatus: ${status}`);
    this.#set("connection", printer?.connection_state || "–");
    this.#set("progress", `${job ? progress : 0} %`);
    this.#set("nozzle", temperature(printer?.nozzle_temperature, printer?.nozzle_target_temperature));
    this.#set("bed", temperature(printer?.bed_temperature, printer?.bed_target_temperature));
    const layer = job?.current_layer ?? printer?.current_layer;
    const total = job?.total_layers ?? printer?.total_layers;
    this.#set("layer", layer === null || layer === undefined ? "–" : `${layer} / ${total ?? "–"}`);
    const remaining = numberValue(job?.remaining_time_minutes ?? printer?.remaining_time_minutes);
    this.#set("remaining", remaining === null ? "–" : `${remaining.toFixed(0)} min`);

    const error = this.#root.querySelector<HTMLElement>("#error");
    if (error) {
      error.textContent = this.#state.error;
      error.classList.toggle("visible", Boolean(this.#state.error));
    }

    const actions = this.#root.querySelector<Ultimate3DPrinterActions>("#actions");
    if (actions) {
      actions.printer = printer;
      actions.job = job;
      actions.capabilities = this.#state.capabilities;
    }

    const signature = JSON.stringify(printer?.ams ?? null);
    if (signature !== this.#amsSignature) {
      this.#renderAms(printer);
      this.#amsSignature = signature;
    }
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
      return `<article class="slot ${slot.active === true ? "active" : ""}"><i style="--slot-color:${color}"></i><div><strong>${text(slot.material, slot.present === true ? "Filament" : "Leer")}</strong><small>Slot ${text(slot.global_id, text(slot.tray_id))}</small></div><span>${remaining === null ? "–" : `${remaining.toFixed(0)} %`}</span></article>`;
    }).join("")}</div>`;
  }

  #forwardHass(): void {
    const camera = this.#root.querySelector<PrinterCameraPanel>("printer-camera-panel");
    if (camera) camera.hass = this.#hass;
  }
}

if (!customElements.get("ultimate-3d-system-workspace")) {
  customElements.define("ultimate-3d-system-workspace", Ultimate3DSystemWorkspaceV4);
}
