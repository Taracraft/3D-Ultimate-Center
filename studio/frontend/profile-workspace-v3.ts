import { openContextMenu, type ContextMenuAction } from "./context-menu.js";
import { errorMessage } from "./ha-api-transport.js";
import { StudioProfileEditorDialog } from "./profile-editor-dialog.js";
import {
  ProfileApi,
  type ProfileKind,
  type StudioProfile,
  type StudioProfileCatalog,
  type StudioProfileSaveRequest,
  type StudioProfileSelection,
} from "./profile-api.js";
import { StudioActionDialog } from "./studio-action-dialog.js";

type GcodeSlotKey = "start_sound" | "end_sound" | "gcode_1" | "gcode_2";

type ProfileGroup = Readonly<{
  id: string;
  kind: ProfileKind;
  label: string;
  description: string;
  slot?: GcodeSlotKey;
}>;

const GCODE_SLOT_KEYS: Readonly<Record<GcodeSlotKey, readonly string[]>> = {
  start_sound: ["start_sound_gcode", "start_sound", "startsound"],
  end_sound: ["end_sound_gcode", "end_sound", "endsound"],
  gcode_1: ["custom_gcode_1", "gcode_1", "before_layer_change_gcode"],
  gcode_2: ["custom_gcode_2", "gcode_2", "after_layer_change_gcode"],
};

const GCODE_TEMPLATE_KEY: Readonly<Record<GcodeSlotKey, string>> = {
  start_sound: "start_sound_gcode",
  end_sound: "end_sound_gcode",
  gcode_1: "custom_gcode_1",
  gcode_2: "custom_gcode_2",
};

const GROUPS: readonly ProfileGroup[] = [
  { id: "printer", kind: "printer", label: "Drucker", description: "Druckraum, Hersteller und Maschinenmodell" },
  { id: "nozzle", kind: "nozzle", label: "Düse", description: "Durchmesser und Düsenmaterial" },
  { id: "filament", kind: "filament", label: "Filamentprofile", description: "Hersteller, Material, Variante und vollständige Druckeigenschaften" },
  { id: "process", kind: "process", label: "Druckprofile", description: "Schichthöhe, Wände, Infill, Geschwindigkeit und Qualität" },
  { id: "start_sound", kind: "process", label: "Startsound", description: "Startsound-Bausteine für den Druckstart", slot: "start_sound" },
  { id: "end_sound", kind: "process", label: "Endsound", description: "Endsound-Bausteine für das Druckende", slot: "end_sound" },
  { id: "gcode_1", kind: "process", label: "G-Code 1", description: "Maschinen-Start mit separatem Startsound", slot: "gcode_1" },
  { id: "gcode_2", kind: "process", label: "G-Code 2", description: "Maschinen-Ende mit separatem Endsound", slot: "gcode_2" },
  { id: "build_plate", kind: "build_plate", label: "Druckplatten", description: "Oberflächen, Abmessungen und Temperaturkorrekturen" },
];

type EditorSaveDetail = StudioProfileSaveRequest & Readonly<{ select_after_save?: boolean }>;

type FilamentHierarchy = ReadonlyMap<string, ReadonlyMap<string, readonly StudioProfile[]>>;

function selectedId(selection: StudioProfileSelection, kind: ProfileKind): string | null {
  if (kind === "printer") return selection.printer_profile_id;
  if (kind === "nozzle") return selection.nozzle_profile_id;
  if (kind === "process") return selection.process_profile_id;
  if (kind === "build_plate") return selection.build_plate_profile_id;
  return selection.filament_profile_ids[0] ?? null;
}

function payloadText(payload: Readonly<Record<string, unknown>>, key: string): string {
  return String(payload[key] ?? "").trim();
}

function gcodeSlot(profile: StudioProfile): GcodeSlotKey | null {
  const explicit = profile.payload.gcode_slot;
  if (explicit === "start_sound" || explicit === "end_sound" || explicit === "gcode_1" || explicit === "gcode_2") return explicit;
  for (const slot of Object.keys(GCODE_SLOT_KEYS) as GcodeSlotKey[]) {
    if (GCODE_SLOT_KEYS[slot].some((key) => payloadText(profile.payload, key))) return slot;
  }
  return null;
}

function profilesForGroup(catalog: StudioProfileCatalog | null, group: ProfileGroup): StudioProfile[] {
  const profiles = catalog?.groups[group.kind] ?? [];
  if (group.kind !== "process") return profiles;
  return profiles.filter((profile) => group.slot ? gcodeSlot(profile) === group.slot : gcodeSlot(profile) === null);
}

function groupIdForProfile(profile: StudioProfile): string {
  if (profile.kind !== "process") return profile.kind;
  return gcodeSlot(profile) ?? "process";
}

function selectionPatch(kind: ProfileKind, profileId: string): Partial<StudioProfileSelection> {
  if (kind === "printer") return { printer_profile_id: profileId };
  if (kind === "nozzle") return { nozzle_profile_id: profileId };
  if (kind === "process") return { process_profile_id: profileId };
  if (kind === "build_plate") return { build_plate_profile_id: profileId };
  return { filament_profile_ids: [profileId] };
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

function sourceLabel(profile: StudioProfile): string {
  if (profile.source === "bambu_cloud") return "Cloud";
  if (profile.source === "local") return "Lokal";
  return "Standard";
}

function prettyValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join(" × ");
  if (value !== null && typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "Ja" : "Nein";
  return String(value ?? "–");
}

function parameterLabel(key: string): string {
  const labels: Record<string, string> = {
    vendor: "Hersteller",
    material: "Material",
    sub_brand: "Variante",
    diameter_mm: "Filamentdurchmesser",
    nozzle_temperature_c: "Düsentemperaturbereich",
    recommended_nozzle_temperature_c: "Drucktemperatur",
    first_layer_nozzle_temperature_c: "Düsentemperatur erste Schicht",
    bed_temperature_c: "Druckbetttemperatur",
    first_layer_bed_temperature_c: "Druckbett erste Schicht",
    max_volumetric_speed_mm3_s: "Maximaler Volumenstrom",
    flow_ratio: "Flussverhältnis",
    cooling_fan_min_percent: "Bauteillüfter Minimum",
    cooling_fan_max_percent: "Bauteillüfter Maximum",
    fan_full_speed_layer: "Volle Lüfterleistung ab Layer",
    bridge_fan_percent: "Brückenlüfter",
    overhang_fan_percent: "Überhanglüfter",
    minimum_layer_time_s: "Minimale Layerzeit",
    retraction_length_mm: "Retract-Länge",
    retraction_speed_mm_s: "Retract-Geschwindigkeit",
    deretraction_speed_mm_s: "Deretract-Geschwindigkeit",
    wipe_distance_mm: "Wipe-Distanz",
    z_hop_mm: "Z-Hop",
    pressure_advance: "Pressure Advance",
    drying_temperature_c: "Trocknungstemperatur",
    drying_time_hours: "Trocknungsdauer",
    first_layer_speed_mm_s: "Geschwindigkeit erste Schicht",
    enclosure: "Bauraumanforderung",
    abrasive: "Abrasiv",
    hardened_nozzle_required: "Gehärtete Düse erforderlich",
    ams_lite_compatible: "AMS-Lite-kompatibel",
    target_printer: "Zieldrucker",
    bambu_a1_compatibility: "Bambu-Lab-A1-Kompatibilität",
    native_profile_name: "Native Slicerbasis",
    slicing_supported: "Slicing auf A1 freigegeben",
    cloud_sync_protected: "Vor Cloud-Sync geschützt",
    profile_completeness: "Profilvollständigkeit",
  };
  return labels[key] ?? key;
}

function formattedValue(key: string, value: unknown): string {
  if (key === "nozzle_temperature_c" && Array.isArray(value) && value.length === 2) {
    return `${String(value[0])}–${String(value[1])} °C`;
  }
  if ([
    "recommended_nozzle_temperature_c",
    "first_layer_nozzle_temperature_c",
    "bed_temperature_c",
    "first_layer_bed_temperature_c",
    "drying_temperature_c",
  ].includes(key)) return `${prettyValue(value)} °C`;
  if ([
    "cooling_fan_min_percent",
    "cooling_fan_max_percent",
    "bridge_fan_percent",
    "overhang_fan_percent",
  ].includes(key)) return `${prettyValue(value)} %`;
  if (key === "max_volumetric_speed_mm3_s") return `${prettyValue(value)} mm³/s`;
  if (key === "drying_time_hours") return `${prettyValue(value)} h`;
  if (key === "minimum_layer_time_s") return `${prettyValue(value)} s`;
  if (key.endsWith("_mm_s")) return `${prettyValue(value)} mm/s`;
  if (key.endsWith("_mm")) return `${prettyValue(value)} mm`;
  return prettyValue(value);
}

function profileVendor(profile: StudioProfile): string {
  const payloadVendor = String(profile.payload.vendor ?? "").trim();
  if (payloadVendor) return payloadVendor;
  if (profile.source === "bambu_cloud") return "Bambu Lab Cloud";
  return profile.name.split(/\s+/)[0] || "Sonstige";
}

function profileMaterial(profile: StudioProfile): string {
  return String(profile.payload.material ?? "Sonstige").trim() || "Sonstige";
}

function profileVariant(profile: StudioProfile): string {
  const subBrand = String(profile.payload.sub_brand ?? "").trim();
  if (subBrand) return subBrand;
  const material = profileMaterial(profile);
  const withoutVendor = profile.name.replace(new RegExp(`^${profileVendor(profile)}\\s*`, "i"), "").trim();
  return withoutVendor.replace(new RegExp(`^${material}\\s*`, "i"), "").trim() || profile.name;
}

function buildFilamentHierarchy(profiles: readonly StudioProfile[]): FilamentHierarchy {
  const vendors = new Map<string, Map<string, StudioProfile[]>>();
  for (const profile of profiles) {
    const vendor = profileVendor(profile);
    const material = profileMaterial(profile);
    const materials = vendors.get(vendor) ?? new Map<string, StudioProfile[]>();
    const variants = materials.get(material) ?? [];
    variants.push(profile);
    materials.set(material, variants);
    vendors.set(vendor, materials);
  }
  return new Map(
    [...vendors.entries()]
      .sort(([left], [right]) => left.localeCompare(right, "de"))
      .map(([vendor, materials]) => [
        vendor,
        new Map(
          [...materials.entries()]
            .sort(([left], [right]) => left.localeCompare(right, "de"))
            .map(([material, variants]) => [
              material,
              [...variants].sort((left, right) => profileVariant(left).localeCompare(profileVariant(right), "de")),
            ]),
        ),
      ]),
  );
}

function removalDescription(profile: StudioProfile): string {
  if (profile.source === "local") return "Dieses lokale Profil wirklich dauerhaft löschen?";
  if (profile.source === "bambu_cloud") {
    return "Dieses synchronisierte Cloudprofil dauerhaft aus dem lokalen Studio-Katalog ausblenden?";
  }
  return "Dieses eingebaute Profil dauerhaft aus dem lokalen Studio-Katalog ausblenden?";
}

function defaultPayload(kind: ProfileKind): Record<string, unknown> {
  if (kind === "filament") {
    return {
      vendor: "Benutzer",
      material: "PLA",
      sub_brand: "Standard",
      nozzle_temperature_c: [190, 230],
      recommended_nozzle_temperature_c: 210,
      first_layer_nozzle_temperature_c: 215,
      bed_temperature_c: 55,
      first_layer_bed_temperature_c: 60,
      max_volumetric_speed_mm3_s: 12,
      flow_ratio: 1,
      cooling_fan_min_percent: 30,
      cooling_fan_max_percent: 100,
    };
  }
  if (kind === "process") {
    return {
      layer_height_mm: 0.2,
      first_layer_height_mm: 0.2,
      walls: 3,
      top_shell_layers: 5,
      bottom_shell_layers: 4,
      infill_percent: 15,
      infill_pattern: "grid",
      outer_wall_speed_mm_s: 60,
      inner_wall_speed_mm_s: 150,
      travel_speed_mm_s: 500,
    };
  }
  if (kind === "printer") {
    return {
      vendor: "Bambu Lab",
      model: "A1",
      technology: "FFF",
      build_volume_mm: [256, 256, 256],
    };
  }
  if (kind === "nozzle") return { diameter_mm: 0.4, material: "hardened_steel" };
  return { surface: "smooth_pei", width_mm: 256, depth_mm: 256, temperature_offset_c: 0 };
}

function templateProfile(group: ProfileGroup, catalog: StudioProfileCatalog | null): StudioProfile {
  if (group.slot) {
    const preset = catalog?.profiles.find((item) => item.kind === "process" && item.builtin && item.payload.gcode_slot === group.slot);
    if (!preset) throw new Error("Die A1-G-Code-Vorlage ist nicht verfügbar.");
    return { ...preset, payload: { ...preset.payload } };
  }
  const now = new Date().toISOString();
  const payload = defaultPayload(group.kind);
  if (group.kind === "filament") {
    const source = catalog?.groups.filament.find((item) => typeof item.payload.filament_start_gcode === "string");
    payload.filament_start_gcode = source?.payload.filament_start_gcode ?? "; filament start gcode";
    payload.filament_end_gcode = source?.payload.filament_end_gcode ?? "; filament end gcode";
  }
  return {
    id: `template.${group.id}`,
    kind: group.kind,
    name: `Neues ${group.label}-Profil`,
    source: "builtin",
    payload,
    builtin: true,
    base_id: null,
    version: null,
    created_at: now,
    updated_at: now,
  };
}

export class Ultimate3DProfileWorkspaceV3 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #api = new ProfileApi();
  readonly #editor = new StudioProfileEditorDialog();
  readonly #dialog = new StudioActionDialog();
  readonly #openProfiles = new Set<string>();
  readonly #openGroups = new Set<string>();
  #catalog: StudioProfileCatalog | null = null;
  #loading = false;
  #busyId = "";
  #error = "";
  #message = "";
  #activeGroupId = "printer";

  connectedCallback(): void {
    if (!this.#editor.isConnected) document.body.append(this.#editor);
    if (!this.#dialog.isConnected) document.body.append(this.#dialog);
    this.#editor.addEventListener("profile-save-request", this.#onEditorSave as EventListener);
    this.#render();
    void this.#load();
  }

  disconnectedCallback(): void {
    this.#editor.removeEventListener("profile-save-request", this.#onEditorSave as EventListener);
    this.#editor.remove();
    this.#dialog.remove();
  }

  readonly #onEditorSave = (event: CustomEvent<EditorSaveDetail>): void => {
    void this.#saveEditorProfile(event.detail);
  };

  async #load(): Promise<void> {
    this.#loading = true;
    this.#error = "";
    this.#render();
    try {
      this.#catalog = await this.#api.getCatalog();
      this.#openSelectedHierarchy();
    } catch (error) {
      this.#catalog = null;
      this.#error = errorMessage(error);
    } finally {
      this.#loading = false;
      this.#render();
    }
  }

  #activeGroup(): ProfileGroup {
    return GROUPS.find((item) => item.id === this.#activeGroupId) ?? GROUPS[0]!;
  }

  #openSelectedHierarchy(): void {
    if (!this.#catalog || this.#activeGroup().kind !== "filament") return;
    const selected = selectedId(this.#catalog.selection, "filament");
    const profile = this.#catalog.groups.filament.find((item) => item.id === selected);
    if (!profile) return;
    const vendor = profileVendor(profile);
    const material = profileMaterial(profile);
    this.#openGroups.add(`vendor:${vendor}`);
    this.#openGroups.add(`material:${vendor}:${material}`);
  }

  #render(): void {
    if (!this.isConnected) return;
    const catalog = this.#catalog;
    const group = this.#activeGroup();
    const profiles = profilesForGroup(catalog, group);
    const selected = catalog && !group.slot ? selectedId(catalog.selection, group.kind) : null;
    const cloud = catalog?.cloud_sync;
    const body = this.#loading
      ? '<div class="empty">Profilkatalog wird geladen …</div>'
      : `<div class="count">${profiles.length} Profile</div><section class="grid">${profiles.length ? this.#profilesHtml(profiles, selected) : '<div class="empty">Keine Profile dieser Kategorie vorhanden.</div>'}</section>`;

    this.#root.innerHTML = `<style>
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff}*{box-sizing:border-box}
      .page{padding:20px}.head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.head h1{margin:0}.head p{margin:6px 0 0;color:#91a5bb}.actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
      button{border:1px solid #31506e;border-radius:8px;padding:9px 11px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}button:hover{border-color:#41c5ff}button:disabled{opacity:.4;cursor:not-allowed}.primary{border-color:#41c5ff;background:#17638a}.danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}
      .status{padding:8px 10px;border:1px solid #2d4d68;border-radius:999px;color:#9fc6e5;font-size:12px}.tabs{display:flex;gap:7px;flex-wrap:wrap;margin:18px 0}.tabs button[aria-current=true]{border-color:#41c5ff;background:#173b58}
      .message,.error,.empty{margin:12px 0;padding:13px;border:1px solid #2a3c53;border-radius:10px;background:#111b29;color:#91a5bb}.message{border-color:#27734c;color:#8ff0b5}.error{border-color:#8f3f4b;color:#ffd7dc}
      .cloud{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;margin:14px 0;padding:13px;border:1px solid #2a3c53;border-radius:11px;background:#0d1723}.cloud strong,.cloud small{display:block}.cloud small{margin-top:5px;color:#8ea5ba}.count{margin:8px 0;color:#8299af;font-size:12px}.grid{display:grid;gap:9px}
      .group{border:1px solid #29415a;border-radius:11px;background:#0b1521;overflow:hidden}.group>summary{cursor:pointer;padding:11px 13px;font-weight:800;color:#b9d7ee;list-style:none}.group>summary::-webkit-details-marker{display:none}.group>summary::before{content:"›";display:inline-block;margin-right:8px;transition:transform .15s}.group[open]>summary::before{transform:rotate(90deg)}.group-body{display:grid;gap:8px;padding:0 10px 10px}.subgroup{border:1px solid #22374c;border-radius:9px;background:#0e1926;overflow:hidden}.subgroup>summary{cursor:pointer;padding:9px 11px;color:#9fc6e5;font-weight:750}.subgroup-body{display:grid;gap:7px;padding:0 8px 8px}
      .card{border:1px solid #2a3c53;border-radius:10px;background:#101925;overflow:hidden}.card[selected]{border-color:#45c5ff;box-shadow:inset 3px 0 #45c5ff}.card>summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:9px;align-items:center;padding:12px 13px;cursor:pointer;list-style:none}.card>summary::-webkit-details-marker{display:none}.card>summary::before{content:"›";font-size:20px;line-height:1;transition:transform .15s}.card[open]>summary::before{transform:rotate(90deg)}
      .title{min-width:0}.title strong,.title small{display:block}.title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.title small{margin-top:3px;color:#7f96ac;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.badge{padding:3px 7px;border:1px solid #385b78;border-radius:999px;color:#9cc5e4;font-size:10px;text-transform:uppercase}.card[selected] .badge{border-color:#45c5ff;color:#d9f4ff}
      .body{padding:0 13px 13px;border-top:1px solid #223449}.values{display:grid}.value{display:grid;grid-template-columns:minmax(170px,.85fr) minmax(0,1.15fr);gap:8px;padding:7px 0;border-bottom:1px solid #223449;font-size:12px}.value span:first-child{color:#7890a8}.value span:last-child{overflow-wrap:anywhere}.more{padding:8px 0;color:#71899f;font-size:11px}.card-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.card-actions button{flex:1;min-width:130px}
      @media(max-width:700px){.head{display:block}.actions{justify-content:flex-start;margin-top:10px}.cloud{grid-template-columns:1fr}.value{grid-template-columns:1fr}.card>summary{grid-template-columns:auto minmax(0,1fr)}}
    </style><section class="page"><header class="head"><div><h1>Profile</h1><p>${esc(group.description)}. Lokale Profile bleiben vom Bambu-Cloud-Sync unabhängig.</p></div><div class="actions"><span class="status">${catalog?.persistent ? "Lokal persistent" : "Wird geladen"}</span><button class="primary" id="new-profile" type="button" ${this.#busyId ? "disabled" : ""}>Neues ${esc(group.label)}-Profil</button><button id="collapse-all" type="button">Alles einklappen</button></div></header>${catalog ? `<section class="cloud"><div><strong>${cloud?.available_offline ? `${catalog.source_counts.bambu_cloud} Cloud-Profile lokal verfügbar` : "Bambu-Cloud-Profile"}</strong><small>${cloud?.last_error ? esc(cloud.last_error) : cloud?.available_offline ? "Der synchronisierte Stand bleibt offline verfügbar. Lokale Profile werden durch Cloud-Sync weder gelöscht noch überschrieben." : "Cloudprofile können synchronisiert und als lokale Profile übernommen werden."}</small></div><button id="cloud-sync" type="button" ${this.#busyId || cloud?.syncing ? "disabled" : ""}>${cloud?.syncing || this.#busyId === "cloud-sync" ? "Synchronisiert …" : "Cloud synchronisieren"}</button></section>` : ""}<nav class="tabs">${GROUPS.map((item) => `<button type="button" data-group-id="${esc(item.id)}" aria-current="${item.id === this.#activeGroupId}">${esc(item.label)}</button>`).join("")}</nav>${this.#message ? `<div class="message">${esc(this.#message)}</div>` : ""}${this.#error ? `<div class="error">${esc(this.#error)}</div>` : ""}${body}</section>`;

    this.#bind(profiles);
  }

  #profilesHtml(profiles: readonly StudioProfile[], selected: string | null): string {
    if (this.#activeGroup().kind !== "filament") {
      return profiles.map((profile) => this.#profileCard(profile, selected)).join("");
    }
    const hierarchy = buildFilamentHierarchy(profiles);
    return [...hierarchy.entries()].map(([vendor, materials]) => {
      const vendorKey = `vendor:${vendor}`;
      const materialHtml = [...materials.entries()].map(([material, variants]) => {
        const materialKey = `material:${vendor}:${material}`;
        return `<details class="subgroup" data-group-key="${esc(materialKey)}" ${this.#openGroups.has(materialKey) ? "open" : ""}><summary>${esc(material)} · ${variants.length}</summary><div class="subgroup-body">${variants.map((profile) => this.#profileCard(profile, selected, profileVariant(profile))).join("")}</div></details>`;
      }).join("");
      return `<details class="group" data-group-key="${esc(vendorKey)}" ${this.#openGroups.has(vendorKey) ? "open" : ""}><summary>${esc(vendor)} · ${[...materials.values()].reduce((sum, variants) => sum + variants.length, 0)}</summary><div class="group-body">${materialHtml}</div></details>`;
    }).join("");
  }

  #profileCard(profile: StudioProfile, selected: string | null, displayName = profile.name): string {
    const group = this.#activeGroup();
    const selectable = !group.slot;
    const active = selectable && profile.id === selected;
    const priority = [
      "vendor", "material", "sub_brand", "diameter_mm", "nozzle_temperature_c",
      "recommended_nozzle_temperature_c", "first_layer_nozzle_temperature_c",
      "bed_temperature_c", "first_layer_bed_temperature_c", "max_volumetric_speed_mm3_s",
      "flow_ratio", "cooling_fan_min_percent", "cooling_fan_max_percent", "fan_full_speed_layer",
      "bridge_fan_percent", "overhang_fan_percent", "minimum_layer_time_s",
      "retraction_length_mm", "retraction_speed_mm_s", "deretraction_speed_mm_s",
      "wipe_distance_mm", "z_hop_mm", "pressure_advance", "drying_temperature_c",
      "drying_time_hours", "first_layer_speed_mm_s", "enclosure", "abrasive",
      "hardened_nozzle_required", "ams_lite_compatible", "target_printer",
      "bambu_a1_compatibility", "native_profile_name", "slicing_supported",
      "cloud_sync_protected", "profile_completeness",
    ];
    const entries = Object.entries(profile.payload)
      .filter(([key]) => key !== "_bambu_cloud" && (group.slot ? true : !key.toLowerCase().includes("gcode")))
      .sort(([left], [right]) => {
        const leftIndex = priority.indexOf(left);
        const rightIndex = priority.indexOf(right);
        if (leftIndex >= 0 || rightIndex >= 0) return (leftIndex < 0 ? 999 : leftIndex) - (rightIndex < 0 ? 999 : rightIndex);
        return left.localeCompare(right, "de");
      });
    const preview = entries.slice(0, 28);
    const hiddenCount = Math.max(0, entries.length - preview.length);
    const editLabel = profile.source === "local" ? "Bearbeiten" : "Als lokales Profil bearbeiten";
    return `<details class="card" data-profile-id="${esc(profile.id)}" ${active ? "selected" : ""} ${this.#openProfiles.has(profile.id) ? "open" : ""}><summary><span></span><span class="title"><strong>${esc(displayName)}</strong><small>${esc(profile.id)}${profile.base_id ? ` · Basis ${esc(profile.base_id)}` : ""}</small></span><span class="badge">${active ? `Aktiv · ${sourceLabel(profile)}` : group.slot ? `Baustein · ${sourceLabel(profile)}` : sourceLabel(profile)}</span></summary><div class="body"><div class="values">${preview.map(([key, value]) => `<div class="value"><span>${esc(parameterLabel(key))}</span><span>${esc(formattedValue(key, value))}</span></div>`).join("")}</div>${hiddenCount ? `<div class="more">${hiddenCount} weitere Parameter sind im Editor verfügbar.</div>` : ""}<div class="card-actions">${selectable ? `<button type="button" data-action="select" data-profile-id="${esc(profile.id)}" ${active || this.#busyId ? "disabled" : ""}>${active ? "Ausgewählt" : "Auswählen"}</button>` : ""}<button class="primary" type="button" data-action="edit" data-profile-id="${esc(profile.id)}" ${this.#busyId ? "disabled" : ""}>${editLabel}</button><button class="danger" type="button" data-action="delete" data-profile-id="${esc(profile.id)}" ${this.#busyId ? "disabled" : ""}>Löschen</button></div></div></details>`;
  }

  #bind(profiles: readonly StudioProfile[]): void {
    this.#root.querySelector<HTMLButtonElement>("#new-profile")?.addEventListener("click", () => this.#openEditor(templateProfile(this.#activeGroup(), this.#catalog)));
    this.#root.querySelector<HTMLButtonElement>("#collapse-all")?.addEventListener("click", () => {
      this.#openProfiles.clear();
      this.#openGroups.clear();
      this.#render();
    });
    this.#root.querySelector<HTMLButtonElement>("#cloud-sync")?.addEventListener("click", () => void this.#syncCloud());
    this.#root.querySelectorAll<HTMLButtonElement>("[data-group-id]").forEach((button) => {
      button.addEventListener("click", () => {
        this.#activeGroupId = button.dataset.groupId || "printer";
        this.#message = "";
        this.#error = "";
        this.#openSelectedHierarchy();
        this.#render();
      });
    });
    this.#root.querySelectorAll<HTMLDetailsElement>("details[data-group-key]").forEach((details) => {
      details.addEventListener("toggle", () => {
        const key = details.dataset.groupKey || "";
        if (!key) return;
        if (details.open) this.#openGroups.add(key);
        else this.#openGroups.delete(key);
      });
    });
    this.#root.querySelectorAll<HTMLDetailsElement>("details[data-profile-id]").forEach((details) => {
      const profile = profiles.find((item) => item.id === details.dataset.profileId);
      if (!profile) return;
      details.addEventListener("toggle", () => {
        if (details.open) this.#openProfiles.add(profile.id);
        else this.#openProfiles.delete(profile.id);
      });
      details.addEventListener("contextmenu", (event) => this.#openContext(event, profile));
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='select']").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const profile = profiles.find((item) => item.id === button.dataset.profileId);
        if (profile) void this.#select(profile);
      });
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='edit']").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const profile = profiles.find((item) => item.id === button.dataset.profileId);
        if (profile) this.#openEditor(profile);
      });
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='delete']").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const profile = profiles.find((item) => item.id === button.dataset.profileId);
        if (profile) void this.#remove(profile);
      });
    });
  }

  #openEditor(profile: StudioProfile): void {
    const nozzle = this.#catalog?.profiles.find((item) => item.id === this.#catalog?.selection.nozzle_profile_id && item.kind === "nozzle");
    this.#editor.open(profile, nozzle?.payload.diameter_mm);
  }

  async #saveEditorProfile(detail: EditorSaveDetail): Promise<void> {
    if (this.#busyId) return;
    this.#busyId = "profile-editor";
    this.#error = "";
    this.#message = "";
    this.#render();
    try {
      const profile = await this.#api.saveProfile({
        id: detail.id,
        kind: detail.kind,
        name: detail.name,
        payload: detail.payload,
        base_id: detail.base_id,
        version: detail.version,
        origin_profile_id: detail.origin_profile_id,
      });
      await this.#load();
      const savedSlot = gcodeSlot(profile);
      if (detail.select_after_save && !savedSlot) {
        const selection = await this.#api.saveSelection(selectionPatch(profile.kind, profile.id));
        if (this.#catalog) this.#catalog = { ...this.#catalog, selection };
        this.#openSelectedHierarchy();
      }
      this.#activeGroupId = groupIdForProfile(profile);
      this.#openProfiles.add(profile.id);
      this.#message = `${profile.name} wurde gespeichert${detail.select_after_save ? " und ausgewählt" : ""}.`;
      this.#editor.close();
    } catch (error) {
      this.#error = `Profil konnte nicht gespeichert werden: ${errorMessage(error)}`;
    } finally {
      this.#busyId = "";
      this.#render();
    }
  }

  async #syncCloud(): Promise<void> {
    if (this.#busyId) return;
    this.#busyId = "cloud-sync";
    this.#error = "";
    this.#message = "";
    this.#render();
    try {
      const result = await this.#api.syncCloudProfiles();
      await this.#load();
      if (result.status.last_error) this.#error = result.status.last_error;
      else this.#message = `${result.profile_count} Bambu-Cloud-Profile wurden synchronisiert.`;
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#busyId = "";
      this.#render();
    }
  }

  async #select(profile: StudioProfile): Promise<void> {
    if (!this.#catalog || this.#busyId || this.#activeGroup().slot) return;
    this.#busyId = profile.id;
    this.#error = "";
    this.#render();
    try {
      const selection = await this.#api.saveSelection(selectionPatch(profile.kind, profile.id));
      this.#catalog = { ...this.#catalog, selection };
      this.#message = `${profile.name} ist jetzt ausgewählt.`;
      this.#openSelectedHierarchy();
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#busyId = "";
      this.#render();
    }
  }

  async #remove(profile: StudioProfile): Promise<void> {
    if (this.#busyId) return;
    const confirmed = await this.#dialog.confirm({
      title: "Profil löschen",
      message: removalDescription(profile),
      detail: `${profile.name}\n${profile.id}\nKategorie: ${profile.kind}\nQuelle: ${sourceLabel(profile)}`,
      confirmLabel: "Profil löschen",
      cancelLabel: "Behalten",
      danger: true,
    });
    if (!confirmed) return;
    this.#busyId = profile.id;
    this.#error = "";
    this.#message = "";
    this.#render();
    try {
      await this.#api.removeProfile(profile.id);
      this.#openProfiles.delete(profile.id);
      await this.#load();
      this.#message = `${profile.name} wurde aus dem lokalen Profilkatalog gelöscht.`;
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#busyId = "";
      this.#render();
    }
  }

  #openContext(event: MouseEvent, profile: StudioProfile): void {
    const actions: ContextMenuAction[] = [
      { label: "Profil bearbeiten", disabled: this.#busyId !== "", run: () => this.#openEditor(profile) },
      { label: "Profil auswählen", disabled: this.#busyId !== "" || this.#activeGroup().slot !== undefined, run: () => this.#select(profile) },
      {
        label: "Profil-ID kopieren",
        run: async () => {
          await navigator.clipboard?.writeText(profile.id);
          this.#message = "Profil-ID wurde kopiert.";
          this.#render();
        },
      },
      {
        label: "Profilwerte kopieren",
        run: async () => {
          await navigator.clipboard?.writeText(JSON.stringify(profile.payload, null, 2));
          this.#message = "Profilwerte wurden kopiert.";
          this.#render();
        },
      },
      {
        label: "Profil löschen",
        danger: true,
        separatorBefore: true,
        disabled: this.#busyId !== "",
        run: () => this.#remove(profile),
      },
    ];
    openContextMenu(event, actions);
  }
}

if (!customElements.get("ultimate-3d-profile-workspace")) {
  customElements.define("ultimate-3d-profile-workspace", Ultimate3DProfileWorkspaceV3);
}
