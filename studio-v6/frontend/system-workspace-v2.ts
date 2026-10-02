import "./printer-camera-panel.js";
import "./audit-log-panel.js";
import { openContextMenu, type ContextMenuAction } from "./context-menu.js";
import { errorMessage } from "./ha-api-transport.js";
import { PROGRESS_STYLES, progressMarkup, type ProgressTone } from "./progress-ui.js";
import { v6Api, type V6Printer } from "./v6-api.js";
import type { PrinterCameraPanel } from "./printer-camera-panel.js";

type HassLike = Readonly<{ states: Readonly<Record<string, unknown>> }>;
type RecordValue = Readonly<Record<string, unknown>>;

const ACTIVE_PRINT_STATES = new Set(["running", "printing", "pause", "paused", "prepare", "preparing"]);

function object(value: unknown): RecordValue {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as RecordValue : {};
}

function records(value: unknown): ReadonlyArray<RecordValue> {
  return Array.isArray(value)
    ? value.filter((item): item is RecordValue => item !== null && typeof item === "object" && !Array.isArray(item))
    : [];
}

function numberValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function text(value: unknown, fallback = "–"): string {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char] || char));
}

function temperature(current: unknown, target: unknown): string {
  const currentValue = numberValue(current);
  const targetValue = numberValue(target);
  if (currentValue === null && targetValue === null) return "–";
  return targetValue === null
    ? `${currentValue?.toFixed(1) ?? "–"} °C`
    : `${currentValue?.toFixed(1) ?? "–"} / ${targetValue.toFixed(1)} °C`;
}

function tone(status: unknown): ProgressTone {
  const value = String(status || "").toLowerCase();
  if (/failed|error|fehler/.test(value)) return "red";
  if (/pause|cancel|abbruch/.test(value)) return "amber";
  if (/finish|complete|idle|bereit/.test(value)) return "green";
  return "blue";
}

export class Ultimate3DSystemWorkspaceV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #hass: HassLike | null = null;
  #printers: V6Printer[] = [];
  #error = "";
  #timer: number | null = null;

  set hass(value: HassLike | null) {
    this.#hass = value;
    this.#forwardHass();
    this.#render();
  }

  get hass(): HassLike | null { return this.#hass; }

  connectedCallback(): void {
    if (this.#timer !== null) return;
    void this.#refresh();
    this.#timer = window.setInterval(() => void this.#refresh(), 10000);
    this.#render();
  }

  disconnectedCallback(): void {
    if (this.#timer !== null) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  async #refresh(): Promise<void> {
    try {
      this.#printers = await v6Api.getPrinters();
      this.#error = "";
    } catch (error) {
      this.#error = errorMessage(error);
    }
    this.#render();
  }

  #metric(label: string, value: string): string {
    return `<div class="metric"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></div>`;
  }

  #isActive(printer: V6Printer | undefined): boolean {
    return ACTIVE_PRINT_STATES.has(String(printer?.printer_state || "").toLowerCase());
  }

  #progress(printer: V6Printer | undefined): string {
    if (!printer) return "";
    const status = text(printer.printer_state, "Unbekannt");
    if (!this.#isActive(printer)) {
      return progressMarkup({
        label: "Kein aktiver Druckauftrag",
        detail: status,
        value: 0,
        tone: tone(status),
      });
    }
    return progressMarkup({
      label: text(printer.current_file, "Aktiver Druckauftrag"),
      detail: status,
      value: Math.max(0, Math.min(100, numberValue(printer.progress) ?? 0)),
      tone: tone(status),
    });
  }

  #telemetry(printer: V6Printer | undefined): string {
    if (!printer) return '<div class="empty">Noch kein V6-Drucker verfügbar.</div>';
    const active = this.#isActive(printer);
    const layer = numberValue(printer.current_layer);
    const layers = numberValue(printer.total_layers);
    const remaining = numberValue(printer.remaining_time_minutes);
    return `<div class="progress">${this.#progress(printer)}</div><div class="metrics">
      ${this.#metric("Status", text(printer.printer_state, "Unbekannt"))}
      ${this.#metric("Düse", temperature(printer.nozzle_temperature, printer.nozzle_target_temperature))}
      ${this.#metric("Druckbett", temperature(printer.bed_temperature, printer.bed_target_temperature))}
      ${this.#metric("Schicht", active && layer !== null ? `${layer.toFixed(0)} / ${layers?.toFixed(0) ?? "–"}` : "–")}
      ${this.#metric("Restzeit", active && remaining !== null ? `${remaining.toFixed(0)} min` : "–")}
      ${this.#metric("WLAN", printer.wifi_signal === null || printer.wifi_signal === undefined ? "–" : `${text(printer.wifi_signal)} dBm`)}
      ${this.#metric(active ? "Aktive Datei" : "Letzte Datei", text(printer.current_file))}
      ${this.#metric("Verbindung", text(printer.connection_state))}
    </div>`;
  }

  #ams(printer: V6Printer | undefined): string {
    const ams = object(printer?.ams);
    const slots = records(ams.slots);
    const units = records(ams.units);
    if (ams.available !== true || slots.length === 0) {
      return '<div class="empty">Kein AMS beziehungsweise AMS Lite erkannt.</div>';
    }
    const summaries = units.map((unit) => {
      const humidity = numberValue(unit.humidity);
      const temperatureValue = numberValue(unit.temperature);
      const detail = [
        humidity === null ? null : `Feuchte ${humidity.toFixed(0)} %`,
        temperatureValue === null ? null : `${temperatureValue.toFixed(1)} °C`,
      ].filter(Boolean).join(" · ");
      return `<span>${escapeHtml(text(unit.model, "AMS"))}${detail ? ` · ${escapeHtml(detail)}` : ""}</span>`;
    }).join("");
    return `<div class="ams-head"><strong>${escapeHtml(text(ams.kind, "AMS"))}</strong><span>${escapeHtml(text(ams.occupied_slot_count, "0"))} von ${escapeHtml(text(ams.slot_count, String(slots.length)))} belegt</span></div><div class="units">${summaries}</div><div class="slots">${slots.map((slot) => this.#slot(slot)).join("")}</div>`;
  }

  #slot(slot: RecordValue): string {
    const color = typeof slot.color === "string" && /^#[0-9a-f]{6}$/i.test(slot.color) ? slot.color : "#536273";
    const remaining = numberValue(slot.remaining_percent);
    return `<article class="slot ${slot.active === true ? "active" : ""}"><div class="color" style="--slot-color:${escapeHtml(color)}"></div><div><strong>${escapeHtml(text(slot.material, slot.present === true ? "Filament" : "Leer"))}</strong><small>Slot ${escapeHtml(text(slot.global_id, text(slot.tray_id)))}</small></div><span>${remaining === null ? "–" : `${remaining.toFixed(0)} %`}</span></article>`;
  }

  #camera(): PrinterCameraPanel | null {
    return this.#root.querySelector<PrinterCameraPanel>("printer-camera-panel");
  }

  #forwardHass(): void {
    const camera = this.#camera();
    if (camera) camera.hass = this.#hass;
  }

  #context(event: MouseEvent): void {
    const camera = this.#camera();
    const actions: ContextMenuAction[] = [
      { label: "Systemdaten aktualisieren", run: () => this.#refresh() },
      { label: "Kamera ein-/ausblenden", run: () => camera?.toggle() },
      { label: "Kamera im Vollbild", disabled: !camera, run: () => camera?.enterFullscreen() },
    ];
    openContextMenu(event, actions);
  }

  #render(): void {
    if (!this.isConnected) return;
    const printer = this.#printers[0];
    this.#root.innerHTML = `<style>${PROGRESS_STYLES}
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff}*{box-sizing:border-box}.page{padding:20px}.head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.head h1{margin:0}.head p{margin:6px 0 0;color:#91a5bb}.error,.empty{padding:14px;border:1px solid #2a3c53;border-radius:11px;background:#111b29;color:#91a5bb}.error{margin:12px 0;border-color:#8f3f4b;color:#ffd7dc}.grid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr);gap:14px;margin-top:16px}.panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}.panel h2{margin:0;padding:13px 15px;border-bottom:1px solid #26384f;font-size:15px}.body{padding:14px}.progress{margin-bottom:12px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.metric{padding:11px;border:1px solid #26384f;border-radius:9px;background:#0c1622}.metric small{display:block;color:#8298ae;text-transform:uppercase;font-size:10px}.metric strong{display:block;margin-top:5px;overflow-wrap:anywhere}.ams-head,.slot{display:flex;justify-content:space-between;gap:12px;align-items:center}.ams-head{margin-bottom:8px}.ams-head span,.units{color:#91a5bb;font-size:12px}.units{display:grid;gap:3px;margin-bottom:10px}.slots{display:grid;gap:8px}.slot{padding:10px;border:1px solid #26384f;border-radius:9px;background:#0c1622}.slot.active{border-color:#34b9ff;box-shadow:inset 3px 0 #34b9ff}.slot>div:nth-child(2){min-width:0;flex:1}.slot small{display:block;margin-top:3px;color:#8298ae}.color{width:18px;height:38px;border-radius:6px;background:var(--slot-color);box-shadow:inset 0 0 0 1px #ffffff44}.wide{grid-column:1/-1}@media(max-width:900px){.grid{grid-template-columns:1fr}.metrics{grid-template-columns:1fr 1fr}}@media(max-width:540px){.metrics{grid-template-columns:1fr}}</style>
      <section class="page" id="system-content"><div class="head"><div><h1>System</h1><p>Kamera, Live-Telemetrie, Materialsystem und Audit-Log des V6-Studios.</p></div><strong>${escapeHtml(text(printer?.name, "Drucker"))}</strong></div>${this.#error ? `<div class="error">${escapeHtml(this.#error)}</div>` : ""}<div class="grid"><printer-camera-panel title="Kamera-Snapshot" storage-key="system"></printer-camera-panel><article class="panel"><h2>Druckertelemetrie</h2><div class="body">${this.#telemetry(printer)}</div></article><article class="panel wide"><h2>AMS / AMS Lite</h2><div class="body">${this.#ams(printer)}</div></article><ultimate-3d-audit-log-panel class="wide"></ultimate-3d-audit-log-panel></div></section>`;
    this.#root.querySelector<HTMLElement>("#system-content")?.addEventListener("contextmenu", (event) => this.#context(event));
    this.#forwardHass();
  }
}

if (!customElements.get("ultimate-3d-system-workspace")) {
  customElements.define("ultimate-3d-system-workspace", Ultimate3DSystemWorkspaceV2);
}
