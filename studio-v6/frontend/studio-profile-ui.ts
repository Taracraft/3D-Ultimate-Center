import type { DetailedDirectPrintPrinter } from "./direct-print-status-api.js";
import type { ProfileKind, V6Profile, V6ProfileCatalog } from "./profile-api.js";
import { loadNozzleProcessValues, nozzleProcessContract } from "./nozzle-process-contract.js";
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

function group(catalog: V6ProfileCatalog | null, kind: ProfileKind): V6Profile[] {
  return uniqueStudioProfiles(catalog, kind);
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
  _externalFilamentProfileId = "",
): string {
  const processOverrides = loadNozzleProcessValues();
  const nozzle = nozzleProcessContract(nozzleDiameter(catalog, selection.nozzle_profile_id));
  const summary = [
    selectedProfileName(catalog, selection.nozzle_profile_id),
    materialSource === "ams" ? "AMS Lite" : "Externe Spule",
    selectedProfileName(catalog, selection.process_profile_id),
    selectedProfileName(catalog, selection.build_plate_profile_id),
  ].join(" · ");
  return `<details class="profilebar-shell" open>
    <summary><span>Profile</span><strong>${esc(summary)}</strong><i>Auf-/einklappen</i></summary>
    <section class="profilebar">
      <label><span>Drucker</span><select data-profile-field="target_printer_id">
        <option value="" ${selection.target_printer_id ? "" : "selected"}>Kein Drucker gebunden</option>
        ${printers.map((printer) => `<option value="${esc(printer.printer_id)}" ${printer.printer_id === selection.target_printer_id ? "selected" : ""}>${esc(printer.name)} · ${esc(printerConnectionLabel(printer))}${printer.ams.available ? ` · AMS ${printer.ams.occupied_slot_count}/${printer.ams.slot_count}` : ""}</option>`).join("")}
      </select></label>
      <label><span>Materialquelle</span><select data-material-source>
        <option value="ams" ${materialSource === "ams" ? "selected" : ""}>AMS Lite</option>
        <option value="external_spool" ${materialSource === "external_spool" ? "selected" : ""}>Externe Spule</option>
      </select></label>
      <label><span>Düse</span><select data-profile-field="nozzle_profile_id">${options(group(catalog, "nozzle"), selection.nozzle_profile_id, "Kein Düsenprofil")}</select></label>
      <label><span>Druckprofil</span><select data-profile-field="process_profile_id">${options(group(catalog, "process"), selection.process_profile_id, "Kein Prozessprofil")}</select></label>
      <label><span>Druckplatte</span><select data-profile-field="build_plate_profile_id">${options(group(catalog, "build_plate"), selection.build_plate_profile_id, "Kein Druckplattenprofil")}</select></label>
      <label><span>Schichthöhe</span><input data-process-override="layer_height_mm" type="number" inputmode="decimal" min="${nozzle?.min_layer_height_mm ?? .04}" max="${nozzle?.max_layer_height_mm ?? .56}" step="0.01" value="${esc(inputValue(processOverrides.layer_height_mm))}" placeholder="${nozzle ? `Standard · ${germanNumber(nozzle.default_layer_height_mm)} mm` : "Standard"}" title="${esc(nozzle ? `Leer = Standardprofil · Zulässig: ${germanNumber(nozzle.min_layer_height_mm)}–${germanNumber(nozzle.max_layer_height_mm)} mm` : "Validierte A1-Düse wählen")}"></label>
      <label><span>Außenwand</span><input data-process-override="outer_wall_speed_mm_s" type="number" inputmode="numeric" min="1" max="${nozzle?.max_wall_speed_mm_s ?? 500}" step="1" value="${esc(inputValue(processOverrides.outer_wall_speed_mm_s))}" placeholder="${nozzle ? `Standard · ${germanNumber(nozzle.default_outer_wall_speed_mm_s)} mm/s` : "Standard"}" title="Leer = Standardprofil · Zulässig: 1–${nozzle?.max_wall_speed_mm_s ?? 500} mm/s"></label>
      <label><span>Innenwand</span><input data-process-override="inner_wall_speed_mm_s" type="number" inputmode="numeric" min="1" max="${nozzle?.max_wall_speed_mm_s ?? 500}" step="1" value="${esc(inputValue(processOverrides.inner_wall_speed_mm_s))}" placeholder="${nozzle ? `Standard · ${germanNumber(nozzle.default_inner_wall_speed_mm_s)} mm/s` : "Standard"}" title="Leer = Standardprofil · Zulässig: 1–${nozzle?.max_wall_speed_mm_s ?? 500} mm/s"></label>
    </section>
  </details>`;
}

export function filamentProfilesHtml(
  catalog: V6ProfileCatalog | null,
  selectedIds: readonly string[],
): string {
  const selected = new Set(selectedIds);
  const cloudProfiles = cloudFilamentProfiles(catalog);
  const standardProfiles = group(catalog, "filament").filter((profile) => profile.source !== "bambu_cloud");
  const profileButton = (profile: V6Profile): string => {
    const active = selected.has(profile.id);
    return `<button type="button" class="filament-profile ${active ? "active" : ""}" data-filament-profile="${esc(profile.id)}"><span class="profile-dot"></span><span><b>${esc(profile.name)}</b><small>${esc(profileSource(profile))}</small></span></button>`;
  };
  const hierarchyHtml = (profiles: readonly V6Profile[]): string => {
    if (!profiles.length) return '<div class="empty-profile">Keine Profile in diesem Bereich vorhanden.</div>';
    const hierarchy = groupedFilaments(profiles);
    return [...hierarchy.entries()].map(([vendor, materials]) => {
      const vendorSelected = [...materials.values()].flat().some((profile) => selected.has(profile.id));
      return `<details class="filament-vendor" ${vendorSelected ? "open" : ""}><summary><b>${esc(vendor)}</b><span>${[...materials.values()].reduce((sum, values) => sum + values.length, 0)} Profile</span></summary><div>${[...materials.entries()].map(([material, variants]) => {
        const materialSelected = variants.some((profile) => selected.has(profile.id));
        return `<details class="filament-material" ${materialSelected ? "open" : ""}><summary><b>${esc(material)}</b><span>${variants.length} Varianten</span></summary><div class="filament-profiles">${variants.map(profileButton).join("")}</div></details>`;
      }).join("")}</div></details>`;
    }).join("");
  };
  const cloudSelected = cloudProfiles.some((profile) => selected.has(profile.id));
  const standardSelected = standardProfiles.some((profile) => selected.has(profile.id));
  return `<div class="filament-tree-scroll"><div class="filament-tree"><details class="filament-vendor filament-source" ${cloudSelected || cloudProfiles.length ? "open" : ""}><summary><b>BambuLab Cloud</b><span>${cloudProfiles.length} Profile</span></summary><div>${cloudProfiles.length ? hierarchyHtml(cloudProfiles) : '<div class="empty-profile">Keine synchronisierten BambuLab-Cloud-Filamentprofile verfügbar.</div>'}</div></details><details class="filament-vendor filament-source" ${standardSelected ? "open" : ""}><summary><b>Lokal & Standard</b><span>${standardProfiles.length} Profile</span></summary><div>${hierarchyHtml(standardProfiles)}</div></details></div></div>`;
}

export function externalFilamentProfileSelectHtml(
  catalog: V6ProfileCatalog | null,
  selectedId: string,
): string {
  const profiles = group(catalog, "filament");
  const sources = [
    ["BambuLab Cloud", profiles.filter((profile) => profile.source === "bambu_cloud")],
    ["Lokal & Standard", profiles.filter((profile) => profile.source !== "bambu_cloud")],
  ] as const;
  const groups = sources.map(([label, entries]) => {
    const sorted = [...entries].sort((left, right) => {
      const materialOrder = filamentMaterial(left).localeCompare(filamentMaterial(right), "de-DE", { numeric: true });
      return materialOrder || left.name.localeCompare(right.name, "de-DE", { numeric: true });
    });
    if (!sorted.length) return "";
    return `<optgroup label="${esc(label)}">${sorted.map((profile) => `<option value="${esc(profile.id)}" ${profile.id === selectedId ? "selected" : ""}>${esc(filamentMaterial(profile))} · ${esc(profileDisplayName(profile))}</option>`).join("")}</optgroup>`;
  }).join("");
  return `<label class="external-filament-picker"><span>Filamentprofil</span><select data-external-filament-sidebar><option value="" ${selectedId ? "" : "selected"}>Filamentprofil wählen</option>${groups}</select><small>Alle Profile bleiben verfügbar; gruppiert nach Quelle und Material.</small></label>`;
}

export const STUDIO_PROFILE_CSS = `
.profilebar-shell{border-bottom:1px solid #24384c;background:linear-gradient(180deg,#0d1925,#09131d)}.profilebar-shell>summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;min-height:30px;padding:5px 9px;cursor:pointer;list-style:none}.profilebar-shell>summary::-webkit-details-marker{display:none}.profilebar-shell>summary span{color:#8ba1b5;font-size:9px;text-transform:uppercase;letter-spacing:.05em}.profilebar-shell>summary strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#dbeaff;font-size:10px}.profilebar-shell>summary i{font-style:normal;color:#6f879b;font-size:9px}.profilebar-shell>summary:before{content:"▸";color:#53d1ff}.profilebar-shell[open]>summary:before{content:"▾"}
.profilebar{display:grid;grid-template-columns:minmax(180px,1.1fr) repeat(3,minmax(150px,1fr));gap:6px;padding:6px 9px}.profilebar label{display:grid;gap:2px;min-width:0}.profilebar label>span{font-size:9px;color:#7890a6;text-transform:uppercase;letter-spacing:.04em}.profilebar select,.profilebar input{min-width:0;width:100%;height:30px;padding:4px 7px;border:1px solid #31506e;border-radius:3px;background:#0a1722;color:#eef6ff;font-weight:700}.profilebar input::placeholder{color:#91a8bc;opacity:1}.profilebar input:invalid{border-color:#ff6676;box-shadow:0 0 0 1px #ff667633}
.filament-tree-scroll{max-height:min(42vh,460px);overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding-right:2px}.filament-tree{display:grid;gap:5px;min-height:0}.filament-vendor,.filament-material{border:1px solid #29445c;border-radius:4px;background:#0b1722;overflow:hidden}.filament-vendor>summary,.filament-material>summary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;padding:7px 8px;cursor:pointer;list-style:none}.filament-vendor>summary::-webkit-details-marker,.filament-material>summary::-webkit-details-marker{display:none}.filament-vendor>summary:before,.filament-material>summary:before{content:"▸";color:#53d1ff;margin-right:5px;grid-column:1;position:absolute}.filament-vendor[open]>summary:before,.filament-material[open]>summary:before{content:"▾"}.filament-vendor>summary b,.filament-material>summary b{padding-left:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.filament-vendor>summary span,.filament-material>summary span{font-size:9px;color:#7f96aa}.filament-vendor>div{display:grid;gap:4px;padding:0 5px 5px}.filament-material{background:#0e1c29}.filament-material>summary{padding:6px 7px}.filament-profiles{display:grid;gap:4px;padding:0 5px 5px}.filament-profile{display:grid;grid-template-columns:12px minmax(0,1fr);gap:7px;align-items:center;width:100%;padding:7px;border:1px solid #29445c;border-radius:3px;background:#102131;color:#eef6ff;text-align:left}.filament-profile.active{border-color:#45caff;background:#123f5a}.filament-profile b,.filament-profile small{display:block}.filament-profile small{font-size:9px;color:#7f96aa}.profile-dot{width:10px;height:10px;border-radius:50%;background:#718096}.filament-profile.active .profile-dot{background:#53d1ff;box-shadow:0 0 8px #53d1ff}.empty-profile{padding:8px;color:#8297aa}
.external-filament-picker{display:grid;gap:5px}.external-filament-picker>span{color:#8ba1b5;font-size:9px;text-transform:uppercase;letter-spacing:.04em}.external-filament-picker select{width:100%;height:32px;padding:5px 7px;border:1px solid #31506e;border-radius:3px;background:#0a1722;color:#eef6ff;font-weight:700}.external-filament-picker small{color:#7f96aa}
.preview-summary{display:grid;grid-template-columns:1fr 1fr;gap:5px}.preview-summary span{padding:6px;border:1px solid #29445c;border-radius:3px;background:#0c1a26;color:#b9c9d6;text-align:center}.preview-toggle{display:grid;grid-template-columns:1fr 1fr;gap:5px}.preview-toggle button.active{border-color:#53d1ff;background:linear-gradient(180deg,#1979a5,#115575)}.preview-check{display:flex!important;grid-template-columns:auto 1fr!important;align-items:center;gap:7px!important}.preview-check input{width:auto!important}.feature-legend{display:flex;flex-wrap:wrap;gap:5px}.feature-chip{display:inline-flex;align-items:center;gap:5px;padding:4px 6px;border:1px solid #29445c;border-radius:999px;background:#0c1a26;color:#c9d7e1;font-size:9px}.feature-chip i{width:9px;height:9px;border-radius:50%}
:host{height:auto;min-height:100%;overflow:visible}.app{height:auto;min-height:100%;grid-template-rows:auto auto auto auto auto auto minmax(560px,1fr);grid-auto-rows:max-content;align-content:start;overflow:visible}.titlebar{grid-row:1}.toolstrip{grid-row:2}.modebar{grid-row:3}.profilebar-shell{grid-row:4}.direct-print-top{grid-row:5;min-height:0}.plate-strip{grid-row:6;min-height:62px}.body{grid-row:7;min-height:560px}
@media(max-width:1250px){.profilebar{grid-template-columns:repeat(3,minmax(160px,1fr))}}@media(max-width:850px){.profilebar{grid-template-columns:1fr 1fr}.profilebar-shell>summary{grid-template-columns:auto minmax(0,1fr)}}
`;