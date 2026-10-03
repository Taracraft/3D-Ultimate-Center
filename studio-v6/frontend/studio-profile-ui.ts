import type { DetailedDirectPrintPrinter } from "./direct-print-status-api.js";
import type { ProfileKind, V6Profile, V6ProfileCatalog } from "./profile-api.js";
import { loadNozzleProcessValues, nozzleProcessContract } from "./nozzle-process-contract.js";
import { detailsOpenAttribute } from "./details-open-state.js";
import {
  profileDisplayName,
  uniqueStudioProfiles,
  type StudioPlateProfileSelection,
} from "./studio-profile-catalog.js";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function text(value: unknown): string {
  return String(value ?? "").trim();
}

function options(
  profiles: readonly V6Profile[],
  selected: string,
  emptyLabel: string,
): string {
  const empty = `<option value="" ${selected ? "" : "selected"}>${esc(emptyLabel)}</option>`;
  return empty + profiles.map((profile) => (
    `<option value="${esc(profile.id)}" ${profile.id === selected ? "selected" : ""}>${esc(profileDisplayName(profile))}</option>`
  )).join("");
}

type GcodeSlot = Readonly<{
  key: "start_sound" | "end_sound" | "gcode_1" | "gcode_2";
  label: string;
  empty: string;
}>;

const GCODE_SLOTS: readonly GcodeSlot[] = [
  { key: "start_sound", label: "Startsound", empty: "Kein Startsound-Profil" },
  { key: "end_sound", label: "Endsound", empty: "Kein Endsound-Profil" },
  { key: "gcode_1", label: "G-Code 1", empty: "Kein G-Code-1-Profil" },
  { key: "gcode_2", label: "G-Code 2", empty: "Kein G-Code-2-Profil" },
];

const GCODE_SLOT_KEYS: Readonly<Record<GcodeSlot["key"], readonly string[]>> = {
  start_sound: ["start_sound_gcode", "start_sound", "startsound"],
  end_sound: ["end_sound_gcode", "end_sound", "endsound"],
  gcode_1: ["custom_gcode_1", "gcode_1", "before_layer_change_gcode"],
  gcode_2: ["custom_gcode_2", "gcode_2", "after_layer_change_gcode"],
};

function payloadText(payload: Readonly<Record<string, unknown>>, key: string): string {
  return String(payload[key] ?? "").trim();
}

function gcodeSlotProfiles(catalog: V6ProfileCatalog | null, slot: GcodeSlot["key"], model: string): V6Profile[] {
  const keys = GCODE_SLOT_KEYS[slot];
  return (catalog?.groups.process ?? [])
    .filter((profile) => profile.kind === "process" && profile.payload.gcode_slot === slot && String(profile.payload.printer_model || "").toLowerCase() === model)
    .sort((left, right) => left.name.localeCompare(right.name, "de-DE", { numeric: true }));
}

function gcodeSlotSelect(catalog: V6ProfileCatalog | null, slot: GcodeSlot, selection: StudioPlateProfileSelection): string {
  const printer = catalog?.profiles.find((item) => item.id === selection.printer_profile_id);
  const model = String(printer?.payload.model || "").toLowerCase();
  const selected = selection.gcode_preset_ids?.[slot.key] ?? (["a1", "h2s"].includes(model) ? "builtin." + model + "." + slot.key : "");
  return `<label><span>${esc(slot.label)}</span><select data-gcode-preset="${esc(slot.key)}" title="${esc(slot.label)}-Baustein aus Profile verwalten."><option value="" ${selected ? "" : "selected"}>${esc(slot.empty)}</option>${gcodeSlotProfiles(catalog, slot.key, model).map((profile) => `<option value="${esc(profile.id)}" ${profile.id === selected ? "selected" : ""}>${esc(profileDisplayName(profile))}</option>`).join("")}</select></label>`;
}

function group(catalog: V6ProfileCatalog | null, kind: ProfileKind): V6Profile[] {
  return uniqueStudioProfiles(catalog, kind).filter((profile) => kind !== "process" || !profile.payload.gcode_slot);
}

function cloudFilamentProfiles(catalog: V6ProfileCatalog | null): V6Profile[] {
  return [...(catalog?.groups.filament ?? [])]
    .filter((profile) => profile.source === "bambu_cloud")
    .sort((left, right) => left.name.localeCompare(right.name, "de-DE", { numeric: true }));
}

function selectedProfileName(catalog: V6ProfileCatalog | null, id: string): string {
  return catalog?.profiles.find((profile) => profile.id === id)?.name ?? "Nicht gewählt";
}

function nozzleDiameter(catalog: V6ProfileCatalog | null, id: string): number | null {
  const profile = catalog?.profiles.find((item) => item.id === id);
  const diameter = Number(profile?.payload.diameter_mm);
  return Number.isFinite(diameter) ? diameter : null;
}

function inputValue(value: number | null): string {
  return value === null ? "" : String(value);
}

function germanNumber(value: number): string {
  return value.toLocaleString("de-DE", { maximumFractionDigits: 3 });
}

type ProfileSummaryField = "layer_height_mm" | "outer_wall_speed_mm_s" | "inner_wall_speed_mm_s";
const NATIVE_SUMMARY_KEYS: Readonly<Record<ProfileSummaryField, string>> = {
  layer_height_mm: "layer_height",
  outer_wall_speed_mm_s: "outer_wall_speed",
  inner_wall_speed_mm_s: "inner_wall_speed",
};

function selectedProcessPlaceholder(profile: V6Profile | undefined, key: ProfileSummaryField, unit: string): string {
  if (!profile || profile.kind !== "process" || profile.payload.gcode_slot || profile.payload.slicing_supported === false) return "Standardprofil";
  // These source/key rules match the existing native process contract.
  const sourceKey = profile.source === "bambu_cloud" ? NATIVE_SUMMARY_KEYS[key] : key;
  if (!["builtin", "local", "bambu_cloud"].includes(profile.source)) return "Standardprofil";
  const raw = profile.payload[sourceKey];
  if (typeof raw !== "number" && !(typeof raw === "string" && raw.trim())) return "Standardprofil";
  const value = Number(raw);
  // Missing, inherited, relative or invalid values must not invent nozzle defaults.
  return Number.isFinite(value) && value > 0 ? `Standard · ${germanNumber(value)} ${unit}` : "Standardprofil";
}

function printerConnectionLabel(printer: DetailedDirectPrintPrinter): string {
  return String(printer.connection_state || "").toLowerCase() === "connected" ? "LAN verbunden" : "LAN getrennt";
}

function filamentVendor(profile: V6Profile): string {
  const vendor = text(profile.payload.vendor);
  if (vendor) return vendor;
  const first = profile.name.split(/\s+/)[0];
  return first || "Sonstige";
}

const MATERIAL_ORDER = ["PLA", "PETG", "ABS", "ASA", "TPU", "TPE", "PEBA", "PA", "PC", "PP", "PVB", "PVA", "HIPS", "PEEK", "PET"];

export function filamentMaterial(profile: V6Profile): string {
  const explicit = text(profile.payload.material) || text(profile.payload.filament_type);
  const raw = `${explicit} ${profile.name}`.toUpperCase();
  for (const material of MATERIAL_ORDER) {
    if (new RegExp(`(^|[^A-Z])${material}([^A-Z]|$)`).test(raw)) return material;
  }
  return explicit || "Sonstige";
}

function profileSource(profile: V6Profile): string {
  if (profile.source === "local") return "Lokal";
  if (profile.source === "bambu_cloud") return "BambuLab Cloud";
  return "Standard";
}

function groupedFilaments(profiles: readonly V6Profile[]): Map<string, Map<string, V6Profile[]>> {
  const vendors = new Map<string, Map<string, V6Profile[]>>();
  for (const profile of profiles) {
    const vendor = filamentVendor(profile);
    const material = filamentMaterial(profile);
    const materials = vendors.get(vendor) ?? new Map<string, V6Profile[]>();
    const variants = materials.get(material) ?? [];
    variants.push(profile);
    materials.set(material, variants);
    vendors.set(vendor, materials);
  }
  for (const materials of vendors.values()) {
    for (const variants of materials.values()) {
      variants.sort((left, right) => left.name.localeCompare(right.name, "de-DE", { numeric: true }));
    }
  }
  return new Map([...vendors.entries()].sort(([left], [right]) => left.localeCompare(right, "de-DE", { numeric: true })));
}

export function studioProfileBarHtml(
  catalog: V6ProfileCatalog | null,
  printers: readonly DetailedDirectPrintPrinter[],
  selection: StudioPlateProfileSelection,
  materialSource: "ams" | "external_spool" = "ams",
  externalFilamentProfileId = "",
  profileBarOpen = true,
): string {
  const selectedFilaments = materialSource === "external_spool"
    ? (externalFilamentProfileId ? [externalFilamentProfileId] : [])
    : selection.filament_profile_ids;
  const selectedNames = selectedFilaments.map((id) => selectedProfileName(catalog, id));
  const filamentSummary = selectedNames.join(" · ") || "Filamentprofile wählen";
  const processOverrides = loadNozzleProcessValues();
  const nozzle = nozzleProcessContract(nozzleDiameter(catalog, selection.nozzle_profile_id));
  const selectedProcess = catalog?.profiles.find((profile) => profile.id === selection.process_profile_id && profile.kind === "process");
  const summary = [
    selectedProfileName(catalog, selection.printer_profile_id),
    selectedProfileName(catalog, selection.process_profile_id),
    selectedProfileName(catalog, selection.build_plate_profile_id),
    filamentSummary,
  ].join(" · ");
  return `<details class="profilebar-shell"${profileBarOpen ? " open" : ""}>
    <summary><span>Profile</span><strong>${esc(summary)}</strong><i>Auf-/einklappen</i></summary>
    <section class="profilebar">
      <label><span>Zieldrucker</span><select data-profile-field="target_printer_id">
        <option value="" ${selection.target_printer_id ? "" : "selected"}>Kein Drucker gebunden</option>
        ${printers.map((printer) => `<option value="${esc(printer.printer_id)}" ${printer.printer_id === selection.target_printer_id ? "selected" : ""}>${esc(printer.name)} · ${esc(printerConnectionLabel(printer))}${printer.ams.available ? ` · AMS ${printer.ams.occupied_slot_count}/${printer.ams.slot_count}` : ""}</option>`).join("")}
      </select></label>
      <div class="filament-profile-field"><span>Filamentprofile</span><details class="filament-profile-picker" data-filament-profile-picker><summary>${esc(filamentSummary)}</summary><div class="filament-profile-popover"><b>Filamentprofile</b><small>AMS und externe Spule nutzen denselben Profilkatalog; die aktive Zuführung kommt aus der Drucker-/Spulentelemetrie.</small>${filamentProfilesHtml(catalog, selectedFilaments)}</div></details></div>
      <label><span>Düse</span><select data-profile-field="nozzle_profile_id">${options(group(catalog, "nozzle"), selection.nozzle_profile_id, "Kein Düsenprofil")}</select></label>
      <label><span>Druckprofil</span><select data-profile-field="process_profile_id">${options(group(catalog, "process"), selection.process_profile_id, "Kein Prozessprofil")}</select></label>
      <label><span>Druckplatte</span><select data-profile-field="build_plate_profile_id">${options(group(catalog, "build_plate"), selection.build_plate_profile_id, "Kein Druckplattenprofil")}</select></label>
      <label><span>Schichthöhe</span><input data-process-override="layer_height_mm" type="number" inputmode="decimal" min="${nozzle?.min_layer_height_mm ?? .04}" max="${nozzle?.max_layer_height_mm ?? .56}" step="0.01" value="${esc(inputValue(processOverrides.layer_height_mm))}" placeholder="${esc(selectedProcessPlaceholder(selectedProcess, "layer_height_mm", "mm"))}" title="${esc(nozzle ? `Leer = Standardprofil · Zulässig: ${germanNumber(nozzle.min_layer_height_mm)}–${germanNumber(nozzle.max_layer_height_mm)} mm` : "Validierte A1-Düse wählen")}"></label>
      <label><span>Außenwand</span><input data-process-override="outer_wall_speed_mm_s" type="number" inputmode="numeric" min="1" max="${nozzle?.max_wall_speed_mm_s ?? 500}" step="1" value="${esc(inputValue(processOverrides.outer_wall_speed_mm_s))}" placeholder="${esc(selectedProcessPlaceholder(selectedProcess, "outer_wall_speed_mm_s", "mm/s"))}" title="Leer = Standardprofil · Zulässig: 1–${nozzle?.max_wall_speed_mm_s ?? 500} mm/s"></label>
      <label><span>Innenwand</span><input data-process-override="inner_wall_speed_mm_s" type="number" inputmode="numeric" min="1" max="${nozzle?.max_wall_speed_mm_s ?? 500}" step="1" value="${esc(inputValue(processOverrides.inner_wall_speed_mm_s))}" placeholder="${esc(selectedProcessPlaceholder(selectedProcess, "inner_wall_speed_mm_s", "mm/s"))}" title="Leer = Standardprofil · Zulässig: 1–${nozzle?.max_wall_speed_mm_s ?? 500} mm/s"></label>
      ${GCODE_SLOTS.map((slot) => gcodeSlotSelect(catalog, slot, selection)).join("")}
    </section>
  </details>`;
}

export function filamentProfilesHtml(
  catalog: V6ProfileCatalog | null,
  selectedIds: readonly string[],
  openKeys: ReadonlySet<string> | null = null,
): string {
  const selected = new Set(selectedIds);
  const cloudProfiles = cloudFilamentProfiles(catalog);
  const standardProfiles = (catalog?.groups.filament ?? []).filter((profile) => profile.source !== "bambu_cloud");
  const openAttribute = (key: string, selectedWithin: boolean): string => (
    openKeys === null ? (selectedWithin ? " open" : "") : detailsOpenAttribute(openKeys, key)
  );
  const profileButton = (profile: V6Profile): string => {
    const active = selected.has(profile.id);
    return `<button type="button" class="filament-profile ${active ? "active" : ""}" aria-pressed="${active}" data-filament-profile="${esc(profile.id)}"><span class="profile-dot"></span><span><b>${esc(profile.name)}</b><small>${esc(profileSource(profile))}</small></span></button>`;
  };
  const hierarchyHtml = (profiles: readonly V6Profile[], sourceKey: string): string => {
    if (!profiles.length) return '<div class="empty-profile">Keine Profile in diesem Bereich vorhanden.</div>';
    const hierarchy = groupedFilaments(profiles);
    return [...hierarchy.entries()].map(([vendor, materials]) => {
      const vendorSelected = [...materials.values()].flat().some((profile) => selected.has(profile.id));
      const vendorKey = `filament:${sourceKey}:vendor:${vendor}`;
      return `<details class="filament-vendor" data-filament-detail-key="${esc(vendorKey)}"${openAttribute(vendorKey, vendorSelected)}><summary><b>${esc(vendor)}</b><span>${[...materials.values()].reduce((sum, values) => sum + values.length, 0)} Profile</span></summary><div>${[...materials.entries()].map(([material, variants]) => {
        const materialSelected = variants.some((profile) => selected.has(profile.id));
        const materialKey = `${vendorKey}:material:${material}`;
        return `<details class="filament-material" data-filament-detail-key="${esc(materialKey)}"${openAttribute(materialKey, materialSelected)}><summary><b>${esc(material)}</b><span>${variants.length} Varianten</span></summary><div class="filament-profiles">${variants.map(profileButton).join("")}</div></details>`;
      }).join("")}</div></details>`;
    }).join("");
  };
  const cloudSelected = cloudProfiles.some((profile) => selected.has(profile.id));
  const standardSelected = standardProfiles.some((profile) => selected.has(profile.id));
  const cloudKey = "filament:source:bambu_cloud";
  const standardKey = "filament:source:local_standard";
  return `<div class="filament-tree"><details class="filament-vendor filament-source" data-filament-detail-key="${cloudKey}"${openAttribute(cloudKey, cloudSelected)}><summary><b>BambuLab Cloud</b><span>${cloudProfiles.length} Profile</span></summary><div>${cloudProfiles.length ? hierarchyHtml(cloudProfiles, "bambu_cloud") : '<div class="empty-profile">Keine synchronisierten BambuLab-Cloud-Filamentprofile verfügbar.</div>'}</div></details><details class="filament-vendor filament-source" data-filament-detail-key="${standardKey}"${openAttribute(standardKey, standardSelected)}><summary><b>Lokal & Standard</b><span>${standardProfiles.length} Profile</span></summary><div>${hierarchyHtml(standardProfiles, "local_standard")}</div></details></div>`;
}

export const STUDIO_PROFILE_CSS = `
.filament-profile-field{display:grid;gap:2px;min-width:0}.filament-profile-field>span{font-size:9px;color:#7890a6;text-transform:uppercase;letter-spacing:.04em}.filament-profile-picker{position:relative;min-width:0}.filament-profile-picker>summary{height:30px;padding:5px 7px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;border:1px solid #31506e;border-radius:3px;background:#0a1722;color:#eef6ff;font-weight:700}.filament-profile-popover{position:absolute;top:100%;left:0;z-index:40;width:min(420px,70vw);padding:10px;border:1px solid #31506e;border-radius:4px;background:#0a1722;box-shadow:0 12px 30px #000b;display:grid;gap:7px}.filament-profile-popover>small{color:#91a8bc}

.profilebar-shell{border-bottom:1px solid #24384c;background:linear-gradient(180deg,#0d1925,#09131d)}.profilebar-shell>summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;min-height:30px;padding:5px 9px;cursor:pointer;list-style:none}.profilebar-shell>summary::-webkit-details-marker{display:none}.profilebar-shell>summary span{color:#8ba1b5;font-size:9px;text-transform:uppercase;letter-spacing:.05em}.profilebar-shell>summary strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#dbeaff;font-size:10px}.profilebar-shell>summary i{font-style:normal;color:#6f879b;font-size:9px}.profilebar-shell>summary:before{content:"▸";color:#53d1ff}.profilebar-shell[open]>summary:before{content:"▾"}
.profilebar{display:grid;grid-template-columns:minmax(180px,1.1fr) repeat(6,minmax(150px,1fr));gap:6px;padding:6px 9px}.profilebar label{display:grid;gap:2px;min-width:0}.profilebar label>span{font-size:9px;color:#7890a6;text-transform:uppercase;letter-spacing:.04em}.profilebar select,.profilebar input{min-width:0;width:100%;height:30px;padding:4px 7px;border:1px solid #31506e;border-radius:3px;background:#0a1722;color:#eef6ff;font-weight:700}.profilebar input::placeholder{color:#91a8bc;opacity:1}.profilebar input:invalid{border-color:#ff6676;box-shadow:0 0 0 1px #ff667633}
.filament-tree{display:grid;grid-template-columns:minmax(0,1fr);grid-auto-rows:max-content;align-content:start;gap:5px;min-height:0;max-height:460px;max-height:min(44vh,460px);overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;touch-action:pan-y;padding-right:5px;scrollbar-gutter:stable}.filament-tree::-webkit-scrollbar{width:8px}.filament-tree::-webkit-scrollbar-thumb{border-radius:8px;background:#31506e}.filament-tree::-webkit-scrollbar-track{background:#07111a}.side #sidebar{min-height:0}.side #sidebar .section{min-height:0}.side #sidebar .section .filament-tree{max-height:min(38vh,360px)}.filament-vendor,.filament-material{border:1px solid #29445c;border-radius:4px;background:#0b1722;overflow:hidden}.filament-vendor>summary,.filament-material>summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;padding:7px 8px;cursor:pointer;list-style:none}.filament-vendor>summary::-webkit-details-marker,.filament-material>summary::-webkit-details-marker{display:none}.filament-vendor>summary:before,.filament-material>summary:before{content:"▸";color:#53d1ff;margin-right:5px;grid-column:1;position:absolute}.filament-vendor[open]>summary:before,.filament-material[open]>summary:before{content:"▾"}.filament-vendor>summary b,.filament-material>summary b{padding-left:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.filament-vendor>summary span,.filament-material>summary span{font-size:9px;color:#7f96aa}.filament-vendor>div{display:grid;gap:4px;padding:0 5px 5px}.filament-material{background:#0e1c29}.filament-material>summary{padding:6px 7px}.filament-profiles{display:grid;gap:4px;padding:0 5px 5px}.filament-profile{display:grid;grid-template-columns:12px minmax(0,1fr);gap:7px;align-items:center;width:100%;padding:7px;border:1px solid #29445c;border-radius:3px;background:#102131;color:#eef6ff;text-align:left}.filament-profile.active{border-color:#45caff;background:#123f5a}.filament-profile b,.filament-profile small{display:block}.filament-profile small{font-size:9px;color:#7f96aa}.profile-dot{width:10px;height:10px;border-radius:50%;background:#718096}.filament-profile.active .profile-dot{background:#53d1ff;box-shadow:0 0 8px #53d1ff}.empty-profile{padding:8px;color:#8297aa}
.preview-summary{display:grid;grid-template-columns:1fr 1fr;gap:5px}.preview-summary span{padding:6px;border:1px solid #29445c;border-radius:3px;background:#0c1a26;color:#b9c9d6;text-align:center}.preview-toggle{display:grid;grid-template-columns:1fr 1fr;gap:5px}.preview-toggle button.active{border-color:#53d1ff;background:linear-gradient(180deg,#1979a5,#115575)}.preview-check{display:flex!important;grid-template-columns:auto 1fr!important;align-items:center;gap:7px!important}.preview-check input{width:auto!important}.feature-legend{display:flex;flex-wrap:wrap;gap:5px}.feature-chip{display:inline-flex;align-items:center;gap:5px;padding:4px 6px;border:1px solid #29445c;border-radius:999px;background:#0c1a26;color:#c9d7e1;font-size:9px}.feature-chip i{width:9px;height:9px;border-radius:50%}
:host{height:auto;min-height:100%;overflow:visible}.app{height:auto;min-height:100%;grid-template-rows:auto auto auto auto auto auto minmax(560px,1fr);grid-auto-rows:max-content;align-content:start;overflow:visible}.titlebar{grid-row:1}.toolstrip{grid-row:2}.modebar{grid-row:3}.profilebar-shell{grid-row:4}.direct-print-top{grid-row:5;min-height:0}.plate-strip{grid-row:6;min-height:62px}.body{grid-row:7;min-height:560px}
@media(max-width:1250px){.profilebar{grid-template-columns:repeat(3,minmax(160px,1fr))}}@media(max-width:850px){.profilebar{grid-template-columns:1fr 1fr}.profilebar-shell>summary{grid-template-columns:auto minmax(0,1fr)}}
`;
