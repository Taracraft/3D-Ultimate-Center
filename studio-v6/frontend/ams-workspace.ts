import {
  applyFilamentSetting,
  fetchDetailedDirectPrintStatus,
  previewFilamentSetting,
  type DetailedAmsSlot,
  type FilamentSettingTargetKind,
  type ManualA1FilamentProfile,
  type ManualA1FilamentType,
  type DetailedDirectPrintPrinter,
  type DetailedExternalSpool,
} from "./direct-print-status-api.js";
import { ProfileApi, type V6Profile, type V6ProfileCatalog } from "./profile-api.js";
import { filamentColor, profileById } from "./studio-profile-catalog.js";
import { filamentMaterial } from "./studio-profile-ui.js";
import { loadStudioWorkspace, type PersistedStudioWorkspace } from "./studio-persistence.js";
import { detailsOpenAttribute, updateDetailsOpenState } from "./details-open-state.js";
import { materialSystemHassSignature } from "./material-system-hass-signature.js";
import { filamentsForTarget, resolveFilamentSelection, vendorsForTarget } from "./filament-catalog-selection.js";

type HassEntity = Readonly<{
  state?: string;
  attributes?: Readonly<Record<string, unknown>>;
}>;

type HassLike = Readonly<{
  states?: Readonly<Record<string, HassEntity>>;
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
  readonly #openDetailKeys = new Set<string>();
  #hass: HassLike | null = null;
  #hassRenderSignature: string | null = null;
  #printers: DetailedDirectPrintPrinter[] = [];
  #printerId = "";
  #catalog: V6ProfileCatalog | null = null;
  #filamentCatalog: ManualA1FilamentProfile[] = [];
  readonly #filamentSelections = new Map<string, Readonly<{ vendor: string; filamentId: string }>>();
  #workspace: PersistedStudioWorkspace | null = null;
  #loading = false;
  #error = "";
  #settingStatus = "";
  #settingBusy = "";
  #updatedAt = 0;

  set hass(value: HassLike | null) {
    const nextSignature = materialSystemHassSignature(value);
    const materialStateChanged = nextSignature !== this.#hassRenderSignature;
    this.#hass = value;
    this.#hassRenderSignature = nextSignature;
    if (this.isConnected && materialStateChanged) this.#render();
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
      this.#filamentCatalog = [...(status.filament_catalog?.items ?? [])];
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

  #manualMaterialOptions(kind: FilamentSettingTargetKind, current: string): string {
    const allowed: readonly ManualA1FilamentType[] = kind === "external_spool"
      ? ["PLA", "PETG", "TPU", "PVA"]
      : ["PLA", "PETG", "PVA"];
    const normalizedCurrent = current.trim().toUpperCase();
    return allowed.map((material) => `<option value="${material}" ${material === normalizedCurrent ? "selected" : ""}>${material}</option>`).join("");
  }

  #filamentSelection(
    kind: FilamentSettingTargetKind,
    key: string,
    currentFilamentId: string,
    currentMaterial: string,
  ): ManualA1FilamentProfile | null {
    const requested = this.#filamentSelections.get(key);
    return resolveFilamentSelection(
      this.#filamentCatalog,
      kind,
      currentFilamentId,
      currentMaterial,
      requested?.vendor,
      requested?.filamentId,
    );
  }

  #manufacturerOptions(kind: FilamentSettingTargetKind, selected: string): string {
    return vendorsForTarget(this.#filamentCatalog, kind)
      .map((vendor) => `<option value="${esc(vendor)}" ${vendor === selected ? "selected" : ""}>${esc(vendor)}</option>`)
      .join("");
  }

  #filamentOptions(kind: FilamentSettingTargetKind, vendor: string, selectedId: string): string {
    return filamentsForTarget(this.#filamentCatalog, kind)
      .filter((item) => item.vendor === vendor)
      .map((item) => `<option value="${esc(item.id)}" ${item.id === selectedId ? "selected" : ""}>${esc(item.name)} · ${esc(item.material_type)}</option>`)
      .join("");
  }

  #materialControls(
    kind: FilamentSettingTargetKind,
    targetId: string,
    material: string,
    currentFilamentId: string,
    color: string | null,
    rfidDetected: boolean,
    present: boolean,
  ): string {
    if (!present) return "";
    const key = `${kind}:${targetId}`;
    const printerBlocked = this.#printer() !== null && !this.#printer()?.ready;
    const locked = rfidDetected || printerBlocked;
    const busy = this.#settingBusy === key;
    const selected = this.#filamentSelection(kind, key, currentFilamentId, material);
    if (!selected) return `<section class="material-setting ${locked ? "locked" : ""}">
      <label><span>Filamentart</span><select data-setting-material data-setting-key="${esc(key)}" ${locked || busy ? "disabled" : ""}>${this.#manualMaterialOptions(kind, material)}</select></label>
      <label><span>Farbe</span><input type="color" value="${safeColor(color)}" data-setting-color data-setting-key="${esc(key)}" ${locked || busy ? "disabled" : ""}></label>
      <button type="button" data-setting-apply data-setting-kind="${kind}" data-setting-target="${esc(targetId)}" data-setting-key="${esc(key)}" ${locked || busy ? "disabled" : ""}>${busy ? "Wird gesetzt …" : "Am Drucker setzen"}</button>
      <small>${printerBlocked ? "Während eines laufenden Drucks gesperrt; Materialart und Farbe können erst danach geändert werden." : locked ? "RFID erkannt: Materialart und Farbe kommen verbindlich vom Tag und können hier nicht überschrieben werden." : "Kompatibilitätsmodus bis zur nächsten Home-Assistant-Kernaktivierung: Materialart und Farbe bleiben vollständig bedienbar; Herstellerprofile werden erst angeboten, sobald das validierende Backend aktiv ist."}</small>
    </section>`;
    return `<section class="material-setting ${locked ? "locked" : ""}">
      <label><span>Hersteller</span><select data-setting-vendor data-setting-kind="${kind}" data-setting-key="${esc(key)}" ${locked || busy ? "disabled" : ""}>${this.#manufacturerOptions(kind, selected.vendor)}</select></label>
      <label><span>Filament</span><select data-setting-filament data-setting-kind="${kind}" data-setting-key="${esc(key)}" ${locked || busy ? "disabled" : ""}>${this.#filamentOptions(kind, selected.vendor, selected.id)}</select></label>
      <label><span>Farbe</span><input type="color" value="${safeColor(color)}" data-setting-color data-setting-key="${esc(key)}" ${locked || busy ? "disabled" : ""}></label>
      <button type="button" data-setting-apply data-setting-kind="${kind}" data-setting-target="${esc(targetId)}" data-setting-key="${esc(key)}" ${locked || busy ? "disabled" : ""}>${busy ? "Wird gesetzt …" : "Am Drucker setzen"}</button>
      <small>${printerBlocked ? "Während eines laufenden Drucks gesperrt; Hersteller, Filamentart und Farbe können erst danach geändert werden." : locked ? "RFID erkannt: Hersteller, Filamentart und Farbe kommen verbindlich vom Tag und können hier nicht überschrieben werden." : "Auswahl ausschließlich aus dem offiziellen, für Bambu Lab A1 instanziierten Systemkatalog. Reguläres TPU bleibt auf die externe Spule begrenzt; TPU for AMS ist im Materialsystem zulässig."}</small>
    </section>`;
  }

  #slot(slot: DetailedAmsSlot): string {
    const detailKey = `slot:${slot.global_id}`;
    return `<details data-detail-key="${esc(detailKey)}"${detailsOpenAttribute(this.#openDetailKeys, detailKey)} class="slot ${slot.present ? "present" : "empty"} ${slot.active ? "active" : ""}">
      <summary><span class="color" style="--slot:${safeColor(slot.color)}"></span><span><b>Fach ${slot.display_slot}</b><small>${esc(slot.sub_brand || slot.material || "Leer")}</small></span><em>${slot.active ? "zur Düse geladen" : slot.present ? "belegt" : "leer"}</em><i class="chevron">⌄</i></summary>
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
      ${this.#materialControls("ams_slot", slot.global_id, slot.material, slot.filament_id, slot.color, slot.rfid_detected, slot.present)}
      <footer><span>Tray-ID: ${esc(slot.tray_id || "–")}</span><span>Filament-ID: ${esc(slot.filament_id || "–")}</span><span>RFID-UID: ${esc(slot.tag_uid || "–")}</span></footer>
    </details>`;
  }

  #spool(detailKey: string, label: string, material: string, color: string, status: string, active: boolean, details: string): string {
    return `<details data-detail-key="${esc(detailKey)}"${detailsOpenAttribute(this.#openDetailKeys, detailKey)} class="spool-feed ${active ? "active" : ""}"><summary><div class="spool" style="--filament:${safeColor(color)}"><i></i><strong>${esc(material || "–")}</strong><i></i></div><b>${esc(label)}</b><span>${esc(status)}</span><small>Details aufklappen</small></summary><div class="spool-more">${details}</div><div class="feed-line"></div></details>`;
  }

  #feedDiagram(slots: readonly DetailedAmsSlot[], profile: V6Profile | null, external: DetailedExternalSpool | null): string {
    const feeds = slots.filter((slot) => slot.present).map((slot) => this.#spool(
      `spool:ams:${slot.global_id}`,
      `Fach ${slot.display_slot}`,
      slot.sub_brand || slot.material || "Filament",
      safeColor(slot.color),
      slot.active ? "zur Düse geladen" : "im System belegt",
      slot.active,
      `<span>Material<b>${esc(slot.material || "–")}</b></span><span>Farbe<b>${esc(slot.color || "–")}</b></span><span>Rest<b>${slot.remaining_reliable ? value(slot.remaining_percent, " %") : "nicht zuverlässig"}</b></span><span>RFID<b>${esc(rfidLabel(slot))}</b></span>`,
    ));
    if (external?.available || profile) {
      const selected = this.#activePlate()?.materialSource === "external_spool";
      const loaded = Boolean(external?.loaded);
      const material = external?.material || (profile ? filamentMaterial(profile) : "") || "Filament";
      const color = external?.color || (profile ? filamentColor(profile, "#56616b") : "#56616b");
      const status = loaded ? "am Drucker geladen" : selected ? "im Studio gewählt" : "Profil gespeichert";
      feeds.push(this.#spool(
        "spool:external",
        "EXT",
        material,
        color,
        status,
        loaded,
        `<span>Material<b>${esc(material)}</b></span><span>Farbe<b>${esc(external?.color || color || "–")}</b></span><span>Tray-ID<b>${esc(external?.tray_id || "EXT")}</b></span><span>Filament-ID<b>${esc(external?.filament_id || "–")}</b></span><span>RFID<b>${external?.rfid_detected ? "erkannt" : "nicht erkannt"}</b></span>${this.#materialControls("external_spool", "external", material, external?.filament_id || "", external?.color || color, Boolean(external?.rfid_detected), Boolean(external?.loaded))}`,
      ));
    }
    if (!feeds.length) return '<div class="notice">Aktuell werden weder belegte Materialfächer noch eine externe Spule gemeldet.</div>';
    return `<section class="material-flow"><div class="spool-row">${feeds.join("")}</div><div class="extruder"><i></i><b>Extruder</b><span>Grün = laut Druckertelemetrie tatsächlich geladener Zuführweg</span></div></section>`;
  }

  #systemCards(configured: string, detected: string, externalSelected: boolean, externalLoaded: boolean): string {
    const configuredKey = normalized(configured);
    const detectedKey = normalized(detected);
    const descriptions: Readonly<Record<string, string>> = {
      "AMS Lite": "Vier offene Spulenplätze für A1- und A1-mini-Systeme.",
      "AMS (Original / Gen 1)": "Geschlossenes Vierfach-Materialsystem der ersten Generation.",
      "AMS 2 Pro": "Vierfach-Materialsystem mit erweiterten Materialfunktionen.",
      "AMS HT": "Einzelmaterialsystem für temperaturkritische Filamente.",
      "BMCU-370 / BCMU-370 (Drittanbieter)": "Kompatibles Drittanbieter-System mit bis zu vier gemeldeten Fächern.",
      "AMS-/BMCU-kompatibel (4 Slots erkannt)": "Generische Darstellung für vier live erkannte Materialfächer.",
      "Externe Spule": "Einzelspule am externen Druckerzuführweg.",
    };
    return MATERIAL_SYSTEMS.map((label) => {
      const key = normalized(label);
      const isConfigured = configuredKey === key;
      const isDetected = detectedKey === key;
      const isExternal = label === "Externe Spule";
      const statuses = [
        isConfigured ? '<span class="configured">konfiguriert</span>' : "",
        isDetected ? '<span class="detected">live erkannt</span>' : "",
        isExternal && externalLoaded ? '<span class="detected">am Drucker geladen</span>' : "",
        isExternal && externalSelected ? '<span class="selected">im Studio gewählt</span>' : "",
      ].filter(Boolean).join("");
      const detailKey = `system:${key}`;
      return `<details data-detail-key="${esc(detailKey)}"${detailsOpenAttribute(this.#openDetailKeys, detailKey)} class="system-card ${statuses ? "marked" : ""}"><summary><div class="system-icon"><i></i><i></i><b>${isExternal ? "EXT" : "AMS"}</b></div><span><strong>${esc(label)}</strong><span class="badges">${statuses || '<span class="supported">unterstützt</span>'}</span></span><i class="chevron">⌄</i></summary><div class="system-more">${esc(descriptions[label] || "")}</div></details>`;
    }).join("");
  }

  async #setFilament(
    kind: FilamentSettingTargetKind,
    targetId: string,
    key: string,
  ): Promise<void> {
    const printer = this.#printer();
    const filamentId = this.#root.querySelector<HTMLSelectElement>(`[data-setting-filament][data-setting-key="${CSS.escape(key)}"]`)?.value;
    const material = this.#root.querySelector<HTMLSelectElement>(`[data-setting-material][data-setting-key="${CSS.escape(key)}"]`)?.value as ManualA1FilamentType | undefined;
    const color = this.#root.querySelector<HTMLInputElement>(`[data-setting-color][data-setting-key="${CSS.escape(key)}"]`)?.value;
    if (!printer || (!filamentId && !material) || !color || this.#settingBusy) return;
    this.#settingBusy = key;
    this.#settingStatus = "Filamenteinstellung wird gegen die Live-Telemetrie geprüft …";
    this.#error = "";
    this.#render();
    try {
      const preview = await previewFilamentSetting({
        printer_id: printer.printer_id,
        target_kind: kind,
        target_id: targetId,
        color,
        ...(filamentId ? { filament_id: filamentId } : { material_type: material! }),
      });
      if (!globalThis.confirm(preview.confirmation_message)) {
        this.#settingStatus = "Änderung abgebrochen; es wurde nichts an den Drucker gesendet.";
        return;
      }
      const result = await applyFilamentSetting(preview.token);
      this.#settingStatus = result.telemetry_confirmed
        ? `${result.target_label}: ${result.new_material} / ${result.new_color} wurde am Drucker gesetzt und per Telemetrie bestätigt.`
        : `${result.target_label}: Der Drucker hat die Einstellung angenommen; die Telemetrieaktualisierung steht noch aus.`;
      await this.#refresh();
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    } finally {
      this.#settingBusy = "";
      this.#render();
    }
  }

  #render(): void {
    const printer = this.#printer();
    const slots = printer?.ams.slots ?? [];
    const configured = this.#configuredSystem();
    const detected = this.#detectedSystem();
    const external = this.#externalProfile();
    const externalTelemetry = printer?.external_spool ?? null;
    const externalSelected = this.#activePlate()?.materialSource === "external_spool";
    const sourceMismatch = Boolean(externalTelemetry?.loaded && !externalSelected);
    const telemetryAvailable = Boolean(printer?.ams.available || externalTelemetry?.available);
    this.#root.innerHTML = `<style>
      :host{display:block;min-height:100%;background:#071018;color:#eef6ff;font:13px/1.4 Inter,Segoe UI,sans-serif}*{box-sizing:border-box}.page{display:grid;gap:14px;padding:18px}.head{display:flex;align-items:flex-start;gap:12px}.head>div:first-child{margin-right:auto}.head h2{margin:0 0 3px}.head p{margin:0;color:#8ca2b7}.actions{display:flex;gap:8px;align-items:center}select,button{min-height:36px;padding:7px 10px;border:1px solid #31506e;border-radius:6px;background:#12263a;color:#eef6ff;font-weight:700}button{cursor:pointer}.summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.metric{padding:12px;border:1px solid #29445c;border-radius:8px;background:#0c1925}.metric span,.metric b{display:block}.metric span{color:#8197aa;font-size:10px;text-transform:uppercase}.metric b{margin-top:3px;font-size:15px}.systems{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}.system-card{padding:10px;border:1px solid #29445c;border-radius:8px;background:#0c1925}.system-card.marked{border-color:#3a93bd;background:linear-gradient(180deg,#102b3a,#0c1925)}.system-card summary{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:10px;align-items:center;cursor:pointer;list-style:none}.system-card summary::-webkit-details-marker,.slot summary::-webkit-details-marker,.spool-feed summary::-webkit-details-marker{display:none}.system-card summary>span>strong,.badges{display:block}.badges{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}.system-card span{padding:2px 5px;border-radius:999px;font-size:9px}.system-card strong{font-size:12px}.system-more{margin:10px 0 0 58px;padding-top:8px;border-top:1px solid #22384b;color:#91a5b9}.chevron{font-style:normal;color:#91a5b9;transition:transform .15s}.system-card[open] .chevron,.slot[open] .chevron{transform:rotate(180deg)}.supported{background:#192a38;color:#91a5b9}.configured{background:#473813;color:#ffd978}.detected,.selected{background:#123d2a;color:#7df0ab}.system-icon{position:relative;width:46px;height:46px;border-radius:50%;border:6px solid #8792a0;background:#17232d}.system-icon i{position:absolute;inset:9px;border:2px solid #657381;border-radius:50%}.system-icon b{position:absolute;inset:0;display:grid;place-items:center;font-size:9px}.material-flow{padding:14px;border:1px solid #29445c;border-radius:9px;background:linear-gradient(180deg,#101d29,#0a151f);overflow:auto}.spool-row{display:flex;justify-content:center;gap:24px;min-width:max-content}.spool-feed{display:grid;justify-items:center;align-content:start;min-width:130px;color:#91a5b9}.spool-feed summary{display:grid;justify-items:center;cursor:pointer;list-style:none}.spool-feed.active{color:#69e79b}.spool{display:grid;grid-template-columns:13px 60px 13px;align-items:center;height:66px}.spool>i{height:60px;border:3px solid #d9e0e6;border-radius:50%;background:#54606c}.spool>strong{display:grid;place-items:center;height:54px;margin:0 -3px;background:var(--filament);border:3px solid #cbd5dd;border-radius:4px;color:#fff;font-size:10px;text-shadow:0 1px 3px #000}.spool-feed summary>b{color:#eef6ff}.spool-feed summary>span,.spool-feed summary>small{font-size:10px}.spool-feed summary>small{color:#607a90}.spool-more{display:grid;gap:4px;width:100%;margin-top:7px;padding:7px;border:1px solid #22384b;border-radius:6px;background:#0b1722}.spool-more span{display:flex;justify-content:space-between;gap:8px;font-size:10px}.spool-more b{color:#eef6ff}.feed-line{width:5px;height:34px;margin-top:5px;border-radius:4px;background:transparent}.spool-feed.active .feed-line{background:#26d36f;box-shadow:0 0 8px #26d36f88}.extruder{display:grid;justify-items:center;gap:3px;margin-top:8px}.extruder i{width:28px;height:36px;border:3px solid #d9e0e6;border-radius:8px;background:radial-gradient(circle,#27d16f 0 5px,#31404c 6px)}.extruder span{color:#8197aa;font-size:10px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}.slot{padding:12px;border:1px solid #29445c;border-radius:9px;background:linear-gradient(180deg,#10202e,#0a151f)}.slot.active{border-color:#54d66c}.slot.empty{opacity:.65}.slot summary{display:grid;grid-template-columns:18px minmax(0,1fr) auto auto;gap:9px;align-items:center;cursor:pointer;list-style:none}.slot summary b,.slot summary small{display:block}.slot summary small{color:#91a5b9}.slot em{font-style:normal;color:#75dca0;font-size:10px}.color{width:18px;height:34px;border-radius:4px;background:var(--slot)}.facts{display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-top:11px}.facts span{padding:7px;border:1px solid #22384b;border-radius:5px;color:#8197aa;font-size:10px}.facts b{display:block;margin-top:2px;color:#eef6ff;font-size:12px}.facts .ok{color:#73dfa0}.facts .warn{color:#f4bd63}.slot footer{display:grid;gap:3px;margin-top:9px;color:#71879b;font:10px Consolas,monospace}.material-setting{display:grid;grid-template-columns:minmax(120px,.8fr) minmax(180px,1.4fr) 82px auto;gap:7px;align-items:end;margin-top:10px;padding:9px;border:1px solid #2d506a;border-radius:7px;background:#0b1a26}.material-setting label{display:grid;gap:3px}.material-setting label span{color:#8197aa;font-size:9px;text-transform:uppercase}.material-setting select,.material-setting input,.material-setting button{width:100%;min-height:34px}.material-setting input{padding:2px;border:1px solid #31506e;border-radius:5px;background:#12263a}.material-setting small{grid-column:1/-1;color:#8097aa}.material-setting.locked{opacity:.72}.notice,.error{padding:12px;border:1px solid #29445c;border-radius:8px;background:#0d1a27}.notice strong{color:#eef6ff}.source-warning{display:flex;align-items:center;gap:12px;padding:12px;border:1px solid #9b6a24;border-radius:8px;background:#2b2212;color:#ffe3a3}.source-warning strong{display:block;color:#fff0c7}.source-warning span{display:block;margin-top:2px;font-size:11px}.source-warning a{margin-left:auto;white-space:nowrap;padding:8px 10px;border:1px solid #c58a32;border-radius:6px;background:#493315;color:#fff0c7;font-weight:800;text-decoration:none}.error{border-color:#8f3f4b;background:#31171c;color:#ffd7dc}@media(max-width:760px){.head{display:grid}.actions{flex-wrap:wrap}.summary{grid-template-columns:repeat(2,1fr)}}
    </style><section class="page"><header class="head"><div><h2>Materialsysteme & Filamente</h2><p>Konfiguration, Live-Erkennung, geladene Filamente und RFID-Daten getrennt und ohne automatische Annahmen.</p></div><div class="actions"><select id="printer">${this.#printers.map((item) => `<option value="${esc(item.printer_id)}" ${item.printer_id === this.#printerId ? "selected" : ""}>${esc(item.name)}</option>`).join("") || '<option value="">Kein Drucker</option>'}</select><button id="refresh" ${this.#loading ? "disabled" : ""}>${this.#loading ? "Synchronisiere …" : "Materialsysteme synchronisieren"}</button></div></header>${this.#error ? `<div class="error">${esc(this.#error)}</div>` : ""}${this.#settingStatus ? `<div class="notice"><strong>${esc(this.#settingStatus)}</strong></div>` : ""}<section class="summary"><div class="metric"><span>Konfiguriertes System</span><b>${esc(configured)}</b></div><div class="metric"><span>Live erkannt</span><b>${esc(detected)}</b></div><div class="metric"><span>Aktive Studio-Quelle</span><b>${esc(this.#sourceLabel())}</b></div><div class="metric"><span>Belegte Fächer</span><b>${printer?.ams.occupied_slot_count ?? 0} / ${printer?.ams.slot_count ?? 0}</b></div></section>${sourceMismatch ? `<div class="source-warning"><div><strong>Geladene externe Spule ist noch nicht die Studio-Quelle</strong><span>Der Drucker meldet ${esc(externalTelemetry?.material || "Filament")} in ${esc(externalTelemetry?.color || "unbekannter Farbe")}; die aktive Druckplatte verwendet weiterhin AMS / Materialsystem. Deshalb folgt die Modellfarbe der AMS-/Modellzuordnung.</span></div><a href="#/studio">Im Studio „Externe Spule“ wählen</a></div>` : ""}<section class="systems">${this.#systemCards(configured, detected, externalSelected, Boolean(externalTelemetry?.loaded))}</section>${this.#feedDiagram(slots, external, externalTelemetry)}${telemetryAvailable ? `<section class="grid">${slots.map((slot) => this.#slot(slot)).join("")}</section>` : `<div class="notice"><strong>${esc(configured)}</strong> ist konfiguriert. Der Drucker meldet aktuell keine Materialfächer; deshalb werden keine Slots, RFID-Daten oder geladenen AMS-Filamente erfunden.</div>`}<div class="notice">RFID- und Ladezustände stammen ausschließlich aus der regulären Druckertelemetrie. Materialart und Farbe werden nur nach Vorschau und ausdrücklicher Bestätigung geschrieben. Diese Seite sendet keine Lade-, Entlade-, RFID-Schreib- oder Scanbefehle. Letzte Synchronisation: ${this.#updatedAt ? new Date(this.#updatedAt).toLocaleTimeString("de-DE") : "–"}.</div></section>`;
    this.#root.querySelectorAll<HTMLDetailsElement>("details[data-detail-key]").forEach((details) => {
      details.addEventListener("toggle", () => updateDetailsOpenState(
        this.#openDetailKeys,
        details.dataset.detailKey || "",
        details.open,
      ));
    });
    this.#root.querySelector<HTMLSelectElement>("#printer")?.addEventListener("change", (event) => {
      this.#printerId = (event.currentTarget as HTMLSelectElement).value;
      this.#render();
    });
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refresh());
    this.#root.querySelectorAll<HTMLSelectElement>("[data-setting-vendor]").forEach((select) => {
      select.addEventListener("change", () => {
        const key = select.dataset.settingKey || "";
        const kind = select.dataset.settingKind as FilamentSettingTargetKind;
        const first = filamentsForTarget(this.#filamentCatalog, kind).find((item) => item.vendor === select.value);
        if (!key || !first) return;
        this.#filamentSelections.set(key, { vendor: select.value, filamentId: first.id });
        this.#render();
      });
    });
    this.#root.querySelectorAll<HTMLSelectElement>("[data-setting-filament]").forEach((select) => {
      select.addEventListener("change", () => {
        const key = select.dataset.settingKey || "";
        const item = this.#filamentCatalog.find((candidate) => candidate.id === select.value);
        if (key && item) this.#filamentSelections.set(key, { vendor: item.vendor, filamentId: item.id });
      });
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-setting-apply]").forEach((button) => {
      button.addEventListener("click", () => void this.#setFilament(
        button.dataset.settingKind as FilamentSettingTargetKind,
        button.dataset.settingTarget || "",
        button.dataset.settingKey || "",
      ));
    });
  }
}

if (!customElements.get("ultimate-3d-ams-workspace")) {
  customElements.define("ultimate-3d-ams-workspace", Ultimate3DAmsWorkspace);
}
