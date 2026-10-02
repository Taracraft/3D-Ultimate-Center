import {
  fetchDetailedDirectPrintStatus,
  type DetailedAmsSlot,
  type DetailedDirectPrintPrinter,
} from "./direct-print-status-api.js";
import { ProfileApi, type V6Profile, type V6ProfileCatalog } from "./profile-api.js";
import { filamentColor, profileById } from "./studio-profile-catalog.js";
import { filamentMaterial } from "./studio-profile-ui.js";
import { loadStudioWorkspace, type PersistedStudioWorkspace } from "./studio-persistence.js";

type HassEntity = Readonly<{
  state?: string;
  attributes?: Readonly<Record<string, unknown>>;
}>;

type HassLike = Readonly<{
  states?: Readonly<Record<string, HassEntity>>;
}>;

type LiveExternalSpool = Readonly<{
  material: string;
  brand: string;
  color: string;
  trayId: string;
  loaded: boolean;
  active: boolean;
}>;

const MATERIAL_SYSTEMS = [
  "AMS Lite",
  "AMS (Original / Gen 1)",
  "AMS 2 Pro",
  "AMS HT",
  "BMCU-370 / BCMU-370 (Drittanbieter)",
  "AMS-/BMCU-kompatibel (4 Slots erkannt)",
  "Externe Spule",
] as const;

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function text(value: unknown): string {
  if (Array.isArray(value)) return String(value.find((item) => String(item ?? "").trim()) ?? "").trim();
  return String(value ?? "").trim();
}

function safeColor(value: string | null): string {
  return /^#[0-9a-f]{6}$/i.test(String(value || "")) ? String(value) : "#56616b";
}

function value(value: number | null, suffix: string, digits = 0): string {
  return Number.isFinite(value) ? `${Number(value).toFixed(digits)}${suffix}` : "–";
}

function normalized(value: unknown): string {
  return text(value).toLocaleLowerCase("de-DE").replace(/[^a-z0-9]+/g, "");
}

function entityState(entity: HassEntity | undefined): string {
  const state = text(entity?.state);
  return ["", "unknown", "unavailable", "none", "null"].includes(state.toLocaleLowerCase("de-DE")) ? "" : state;
}

function entityBoolean(value: unknown): boolean {
  return value === true || ["true", "on", "yes", "1"].includes(text(value).toLocaleLowerCase("de-DE"));
}

function rfidLabel(slot: DetailedAmsSlot): string {
  return slot.rfid_detected ? "RFID erkannt" : "Vom Materialsystem nicht erkannt";
}

function telemetrySystemLabel(printer: DetailedDirectPrintPrinter | null): string {
  const kind = normalized(printer?.ams.kind);
  if (kind === "amslite") return "AMS Lite";
  if (kind === "amslitecompatible") return "AMS-/BMCU-kompatibel (4 Slots erkannt)";
  if (kind === "ams") return "AMS (Original / Gen 1)";
  return printer?.ams.available ? text(printer.ams.kind) || "Materialsystem erkannt" : "Kein Materialsystem erkannt";
}

export class Ultimate3DAmsWorkspace extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #profileApi = new ProfileApi();
  #hass: HassLike | null = null;
  #printers: DetailedDirectPrintPrinter[] = [];
  #printerId = "";
  #catalog: V6ProfileCatalog | null = null;
  #workspace: PersistedStudioWorkspace | null = null;
  #loading = false;
  #error = "";
  #updatedAt = 0;

  set hass(value: HassLike | null) {
    this.#hass = value;
    if (this.isConnected) this.#render();
  }

  get hass(): HassLike | null { return this.#hass; }

  connectedCallback(): void {
    this.#render();
    void this.#refresh();
  }

  async #refresh(): Promise<void> {
    if (this.#loading) return;
    this.#loading = true;
    this.#error = "";
    this.#render();
    try {
      const [status, catalog, workspace] = await Promise.all([
        fetchDetailedDirectPrintStatus(),
        this.#profileApi.getCatalog(),
        loadStudioWorkspace(),
      ]);
      this.#printers = [...status.items];
      this.#catalog = catalog;
      this.#workspace = workspace;
      if (!this.#printers.some((item) => item.printer_id === this.#printerId)) {
        this.#printerId = this.#printers.find((item) => item.ams.available)?.printer_id
          ?? this.#printers[0]?.printer_id
          ?? "";
      }
      this.#updatedAt = Date.now();
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    } finally {
      this.#loading = false;
      this.#render();
    }
  }

  #printer(): DetailedDirectPrintPrinter | null {
    return this.#printers.find((item) => item.printer_id === this.#printerId) ?? null;
  }

  #activePlate() {
    const plates = this.#workspace?.plates ?? [];
    return plates[this.#workspace?.activePlate ?? 0] ?? plates[0] ?? null;
  }

  #externalProfile(): V6Profile | null {
    const id = text(this.#activePlate()?.externalFilamentProfileId);
    return id ? profileById(this.#catalog, id) : null;
  }

  #stateForPrinter(suffix: string): string {
    const printer = this.#printer();
    const states = this.#hass?.states ?? {};
    if (!printer) return "";
    const slug = printer.name.toLocaleLowerCase("de-DE").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    const exact = entityState(states[`sensor.${slug}_${suffix}`]);
    if (exact) return exact;
    const candidates = Object.entries(states).filter(([entityId, entity]) => {
      if (!entityId.endsWith(`_${suffix}`)) return false;
      const friendly = text(entity.attributes?.friendly_name).toLocaleLowerCase("de-DE");
      return !friendly || friendly.includes(printer.name.toLocaleLowerCase("de-DE"));
    });
    return candidates.length === 1 ? entityState(candidates[0]?.[1]) : "";
  }

  #configuredSystem(): string {
    return this.#stateForPrinter("configured_ams_type") || "Nicht separat konfiguriert";
  }

  #detectedSystem(): string {
    return this.#stateForPrinter("detected_ams_type") || telemetrySystemLabel(this.#printer());
  }

  #sourceLabel(): string {
    return this.#activePlate()?.materialSource === "external_spool" ? "Externe Spule" : "AMS / Materialsystem";
  }

  #externalSpoolTelemetry(): LiveExternalSpool | null {
    const states = this.#hass?.states ?? {};
    const printer = this.#printer();
    if (!printer) return null;
    const activeTray = this.#stateForPrinter("active_ams_slot");
    const candidates = Object.entries(states).filter(([entityId, entity]) => {
      if (!entityId.endsWith("_external_spool_external_spool")) return false;
      const attributes = entity.attributes ?? {};
      return text(attributes.id) === "254" && entityBoolean(attributes.normalized_loaded);
    });
    if (!candidates.length) return null;
    const printerName = printer.name.toLocaleLowerCase("de-DE");
    const named = candidates.filter(([, entity]) => text(entity.attributes?.friendly_name).toLocaleLowerCase("de-DE").includes(printerName));
    const entity = named.length === 1
      ? named[0]?.[1]
      : this.#printers.length === 1 && candidates.length === 1
        ? candidates[0]?.[1]
        : undefined;
    if (!entity) return null;
    const attributes = entity.attributes ?? {};
    const trayId = text(attributes.id);
    const material = text(attributes.normalized_material) || text(attributes.tray_type) || entityState(entity);
    const brand = text(attributes.normalized_brand) || text(attributes.tray_sub_brands);
    const normalizedColor = text(attributes.normalized_color);
    const rawColor = text(attributes.tray_color).replace(/^#/, "").slice(0, 6);
    return {
      material: material || "Filament",
      brand,
      color: safeColor(normalizedColor || (/^[0-9a-f]{6}$/i.test(rawColor) ? `#${rawColor}` : "")),
      trayId,
      loaded: true,
      active: activeTray === trayId,
    };
  }

  #slot(slot: DetailedAmsSlot): string {
    return `<article class="slot ${slot.present ? "present" : "empty"} ${slot.active ? "active" : ""}">
      <header><span class="color" style="--slot:${safeColor(slot.color)}"></span><span><b>Fach ${slot.display_slot}</b><small>${esc(slot.sub_brand || slot.material || "Leer")}</small></span><em>${slot.active ? "zur Düse geladen" : slot.present ? "belegt" : "leer"}</em></header>
      <div class="facts">
        <span>Material<b>${esc(slot.material || "–")}</b></span>
        <span>Farbe<b>${esc(slot.color || "–")}</b></span>
        <span>Rest<b>${slot.remaining_reliable ? value(slot.remaining_percent, " %") : "nicht zuverlässig"}</b></span>
        <span>Gewicht<b>${value(slot.weight, " g")}</b></span>
        <span>Durchmesser<b>${value(slot.diameter, " mm", 2)}</b></span>
        <span>Düse<b>${Number.isFinite(slot.nozzle_temp_min) || Number.isFinite(slot.nozzle_temp_max) ? `${slot.nozzle_temp_min ?? "–"}–${slot.nozzle_temp_max ?? "–"} °C` : "–"}</b></span>
        <span>Druckbett<b>${value(slot.bed_temp, " °C")}</b></span>
        <span>RFID<b class="${slot.rfid_detected ? "ok" : "warn"}">${rfidLabel(slot)}</b></span>
      </div>
      <footer><span>Tray-ID: ${esc(slot.tray_id || "–")}</span><span>RFID-UID: ${esc(slot.tag_uid || "–")}</span></footer>
    </article>`;
  }

  #spool(label: string, material: string, color: string, status: string, active: boolean): string {
    return `<article class="spool-feed ${active ? "active" : ""}"><div class="spool" style="--filament:${safeColor(color)}"><i></i><strong>${esc(material || "–")}</strong><i></i></div><b>${esc(label)}</b><span>${esc(status)}</span><div class="feed-line"></div></article>`;
  }

  #feedDiagram(slots: readonly DetailedAmsSlot[], external: V6Profile | null, liveExternal: LiveExternalSpool | null): string {
    const feeds = slots.filter((slot) => slot.present).map((slot) => this.#spool(
      `Fach ${slot.display_slot}`,
      slot.sub_brand || slot.material || "Filament",
      safeColor(slot.color),
      slot.active ? "zur Düse geladen" : "im System belegt",
      slot.active,
    ));
    if (liveExternal) {
      feeds.push(this.#spool(
        "EXT",
        liveExternal.brand ? `${liveExternal.brand} ${liveExternal.material}` : liveExternal.material,
        liveExternal.color,
        liveExternal.active ? "zur Düse geladen" : "extern eingelegt",
        liveExternal.active,
      ));
    } else if (external) {
      feeds.push(this.#spool(
        "EXT",
        filamentMaterial(external),
        filamentColor(external, "#56616b"),
        "Studio-Profil · nicht als geladen gemeldet",
        false,
      ));
    }
    if (!feeds.length) return '<div class="notice">Aktuell meldet der Drucker weder belegte Materialfächer noch eine geladene externe Spule.</div>';
    return `<section class="material-flow"><div class="spool-row">${feeds.join("")}</div><div class="collector"></div><div class="extruder"><i></i><b>Extruder</b><span>Grün = vom Drucker als aktiver Zuführweg gemeldet</span></div></section>`;
  }

  #systemCards(configured: string, detected: string, externalSelected: boolean, liveExternal: LiveExternalSpool | null): string {
    const configuredKey = normalized(configured);
    const detectedKey = normalized(detected);
    return MATERIAL_SYSTEMS.map((label) => {
      const key = normalized(label);
      const isConfigured = configuredKey === key;
      const isDetected = detectedKey === key;
      const isExternal = label === "Externe Spule" && externalSelected;
      const isExternalLoaded = label === "Externe Spule" && Boolean(liveExternal?.loaded);
      const isExternalActive = label === "Externe Spule" && Boolean(liveExternal?.active);
      const statuses = [
        isConfigured ? '<span class="configured">konfiguriert</span>' : "",
        isDetected ? '<span class="detected">live erkannt</span>' : "",
        isExternal ? '<span class="selected">im Studio gewählt</span>' : "",
        isExternalLoaded ? '<span class="detected">geladen</span>' : "",
        isExternalActive ? '<span class="selected">zur Düse</span>' : "",
      ].filter(Boolean).join("");
      return `<article class="system-card ${statuses ? "marked" : ""}"><div class="system-icon"><i></i><i></i><b>${label === "Externe Spule" ? "EXT" : "AMS"}</b></div><strong>${esc(label)}</strong><div>${statuses || '<span class="supported">unterstützt</span>'}</div></article>`;
    }).join("");
  }

  #render(): void {
    const printer = this.#printer();
    const slots = printer?.ams.slots ?? [];
    const configured = this.#configuredSystem();
    const detected = this.#detectedSystem();
    const external = this.#externalProfile();
    const liveExternal = this.#externalSpoolTelemetry();
    const externalSelected = this.#activePlate()?.materialSource === "external_spool";
    const telemetryAvailable = Boolean(printer?.ams.available);
    this.#root.innerHTML = `<style>
      :host{display:block;min-height:100%;background:#071018;color:#eef6ff;font:13px/1.4 Inter,Segoe UI,sans-serif}*{box-sizing:border-box}.page{display:grid;gap:14px;padding:18px}.head{display:flex;align-items:flex-start;gap:12px}.head>div:first-child{margin-right:auto}.head h2{margin:0 0 3px}.head p{margin:0;color:#8ca2b7}.actions{display:flex;gap:8px;align-items:center}select,button{min-height:36px;padding:7px 10px;border:1px solid #31506e;border-radius:6px;background:#12263a;color:#eef6ff;font-weight:700}button{cursor:pointer}.summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.metric{padding:12px;border:1px solid #29445c;border-radius:8px;background:#0c1925}.metric span,.metric b{display:block}.metric span{color:#8197aa;font-size:10px;text-transform:uppercase}.metric b{margin-top:3px;font-size:15px}.systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.system-card{display:grid;grid-template-columns:48px minmax(0,1fr);grid-template-rows:auto auto;gap:4px 10px;align-items:center;padding:10px;border:1px solid #29445c;border-radius:8px;background:#0c1925}.system-card.marked{border-color:#3a93bd;background:linear-gradient(180deg,#102b3a,#0c1925)}.system-card>strong{align-self:end}.system-card>div:last-child{display:flex;flex-wrap:wrap;gap:4px;align-self:start}.system-card span{padding:2px 5px;border-radius:999px;font-size:9px}.supported{background:#192a38;color:#91a5b9}.configured{background:#473813;color:#ffd978}.detected,.selected{background:#123d2a;color:#7df0ab}.system-icon{grid-row:1/3;position:relative;width:46px;height:46px;border-radius:50%;border:6px solid #8792a0;background:#17232d}.system-icon i{position:absolute;inset:9px;border:2px solid #657381;border-radius:50%}.system-icon b{position:absolute;inset:0;display:grid;place-items:center;font-size:9px}.material-flow{padding:14px;border:1px solid #29445c;border-radius:9px;background:linear-gradient(180deg,#101d29,#0a151f);overflow:auto}.spool-row{display:flex;justify-content:center;gap:24px;min-width:max-content}.spool-feed{display:grid;justify-items:center;min-width:112px;color:#91a5b9}.spool-feed.active{color:#69e79b}.spool{display:grid;grid-template-columns:13px 60px 13px;align-items:center;height:66px}.spool>i{height:60px;border:3px solid #d9e0e6;border-radius:50%;background:#54606c}.spool>strong{display:grid;place-items:center;height:54px;margin:0 -3px;background:var(--filament);border:3px solid #cbd5dd;border-radius:4px;color:#fff;font-size:10px;text-shadow:0 1px 3px #000}.spool-feed>b{color:#eef6ff}.spool-feed>span{font-size:10px}.feed-line{width:5px;height:34px;margin-top:5px;border-radius:4px;background:#4f5e6b}.spool-feed.active .feed-line{background:#26d36f;box-shadow:0 0 8px #26d36f88}.collector{width:min(85%,720px);height:5px;margin:-5px auto 0;border-radius:4px;background:#4f5e6b}.extruder{display:grid;justify-items:center;gap:3px;margin-top:8px}.extruder i{width:28px;height:36px;border:3px solid #d9e0e6;border-radius:8px;background:radial-gradient(circle,#27d16f 0 5px,#31404c 6px)}.extruder span{color:#8197aa;font-size:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}.slot{padding:12px;border:1px solid #29445c;border-radius:9px;background:linear-gradient(180deg,#10202e,#0a151f)}.slot.active{border-color:#54d66c}.slot.empty{opacity:.65}.slot header{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:9px;align-items:center}.slot header b,.slot header small{display:block}.slot header small{color:#91a5b9}.slot em{font-style:normal;color:#75dca0;font-size:10px}.color{width:18px;height:34px;border-radius:4px;background:var(--slot)}.facts{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-top:11px}.facts span{padding:7px;border:1px solid #22384b;border-radius:5px;color:#8197aa;font-size:10px}.facts b{display:block;margin-top:2px;color:#eef6ff;font-size:12px}.facts .ok{color:#73dfa0}.facts .warn{color:#f4bd63}.slot footer{display:grid;gap:3px;margin-top:9px;color:#71879b;font:10px Consolas,monospace}.notice,.error{padding:12px;border:1px solid #29445c;border-radius:8px;background:#0d1a27}.notice strong{color:#eef6ff}.error{border-color:#8f3f4b;background:#31171c;color:#ffd7dc}@media(max-width:1100px){.summary{grid-template-columns:repeat(3,1fr)}}@media(max-width:760px){.head{display:grid}.actions{flex-wrap:wrap}.summary{grid-template-columns:repeat(2,1fr)}}
    </style><section class="page"><header class="head"><div><h2>Materialsysteme & Filamente</h2><p>Konfiguration, Live-Erkennung, geladene Filamente und RFID-Daten getrennt und ohne automatische Annahmen.</p></div><div class="actions"><select id="printer">${this.#printers.map((item) => `<option value="${esc(item.printer_id)}" ${item.printer_id === this.#printerId ? "selected" : ""}>${esc(item.name)}</option>`).join("") || '<option value="">Kein Drucker</option>'}</select><button id="refresh" ${this.#loading ? "disabled" : ""}>${this.#loading ? "Synchronisiere …" : "Materialsysteme synchronisieren"}</button></div></header>${this.#error ? `<div class="error">${esc(this.#error)}</div>` : ""}<section class="summary"><div class="metric"><span>Konfiguriertes System</span><b>${esc(configured)}</b></div><div class="metric"><span>Live erkannt</span><b>${esc(detected)}</b></div><div class="metric"><span>Geladener Zuführweg</span><b>${liveExternal ? `EXT · ${esc(liveExternal.material)}${liveExternal.active ? " · zur Düse" : ""}` : "–"}</b></div><div class="metric"><span>Aktive Studio-Quelle</span><b>${esc(this.#sourceLabel())}</b></div><div class="metric"><span>Belegte Fächer</span><b>${printer?.ams.occupied_slot_count ?? 0} / ${printer?.ams.slot_count ?? 0}</b></div></section><section class="systems">${this.#systemCards(configured, detected, externalSelected, liveExternal)}</section>${this.#feedDiagram(slots, external, liveExternal)}${telemetryAvailable ? `<section class="grid">${slots.map((slot) => this.#slot(slot)).join("")}</section>` : `<div class="notice"><strong>${esc(configured)}</strong> ist konfiguriert. Der Drucker meldet aktuell keine Materialsystem-Fächer. Eine geladene externe Spule wird unabhängig davon oben als eigener EXT-Zuführweg angezeigt.</div>`}<div class="notice">RFID- und Ladezustände stammen ausschließlich aus der regulären Druckertelemetrie. Diese Übersicht sendet keine Lade-, Entlade-, RFID-Schreib- oder Scanbefehle. Letzte Synchronisation: ${this.#updatedAt ? new Date(this.#updatedAt).toLocaleTimeString("de-DE") : "–"}.</div></section>`;
    this.#root.querySelector<HTMLSelectElement>("#printer")?.addEventListener("change", (event) => {
      this.#printerId = (event.currentTarget as HTMLSelectElement).value;
      this.#render();
    });
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refresh());
  }
}

if (!customElements.get("ultimate-3d-ams-workspace")) {
  customElements.define("ultimate-3d-ams-workspace", Ultimate3DAmsWorkspace);
}