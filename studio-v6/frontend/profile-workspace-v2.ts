import { openContextMenu, type ContextMenuAction } from "./context-menu.js";
import { errorMessage } from "./ha-api-transport.js";
import { V6ProfileEditorDialog } from "./profile-editor-dialog.js";
import {
  ProfileApi,
  type ProfileKind,
  type V6Profile,
  type V6ProfileCatalog,
  type V6ProfileSaveRequest,
  type V6ProfileSelection,
} from "./profile-api.js";

const GROUPS: ReadonlyArray<Readonly<{ kind: ProfileKind; label: string; description: string }>> = [
  { kind: "printer", label: "Drucker", description: "Druckraum, Hersteller und Maschinenmodell" },
  { kind: "nozzle", label: "Düse", description: "Durchmesser und Düsenmaterial" },
  { kind: "filament", label: "Filament", description: "Material, Temperatur, Kühlung und Volumenstrom" },
  { kind: "process", label: "Druckprofile", description: "Schichthöhe, Wände, Infill, Geschwindigkeit und Qualität" },
  { kind: "build_plate", label: "Druckplatte", description: "Oberfläche, Abmessungen und Temperaturkorrektur" },
];

type EditorSaveDetail = V6ProfileSaveRequest & Readonly<{ select_after_save?: boolean }>;

function selectedId(selection: V6ProfileSelection, kind: ProfileKind): string | null {
  if (kind === "printer") return selection.printer_profile_id;
  if (kind === "nozzle") return selection.nozzle_profile_id;
  if (kind === "process") return selection.process_profile_id;
  if (kind === "build_plate") return selection.build_plate_profile_id;
  return selection.filament_profile_ids[0] ?? null;
}

function selectionPatch(kind: ProfileKind, profileId: string): Partial<V6ProfileSelection> {
  if (kind === "printer") return { printer_profile_id: profileId };
  if (kind === "nozzle") return { nozzle_profile_id: profileId };
  if (kind === "process") return { process_profile_id: profileId };
  if (kind === "build_plate") return { build_plate_profile_id: profileId };
  return { filament_profile_ids: [profileId] };
}

function prettyValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join(" × ");
  if (value !== null && typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "Ja" : "Nein";
  return String(value ?? "–");
}

function dateLabel(value: string | null | undefined): string {
  if (!value) return "Noch nie";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("de-DE");
}

function sourceLabel(profile: V6Profile): string {
  if (profile.source === "bambu_cloud") return "Cloud";
  if (profile.source === "local") return "Eigen";
  return "Standard";
}

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function defaultPayload(kind: ProfileKind): Record<string, unknown> {
  if (kind === "filament") return {
    vendor: "Benutzer",
    material: "PLA",
    nozzle_temperature_c: [190, 230],
    bed_temperature_c: 55,
    max_volumetric_speed_mm3_s: 12,
    cooling_fan_min_percent: 30,
    cooling_fan_max_percent: 100,
  };
  if (kind === "process") return {
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
  if (kind === "printer") return {
    vendor: "Bambu Lab",
    model: "Benutzerdefiniert",
    technology: "FFF",
    build_volume_mm: [256, 256, 256],
  };
  if (kind === "nozzle") return { diameter_mm: 0.4, material: "hardened_steel" };
  return { surface: "smooth_pei", width_mm: 256, depth_mm: 256, temperature_offset_c: 0 };
}

export class Ultimate3DProfileWorkspaceV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #api = new ProfileApi();
  readonly #editor = new V6ProfileEditorDialog();
  readonly #openSections = new Set<string>(["cloud", "profiles"]);
  readonly #openProfiles = new Set<string>();
  #catalog: V6ProfileCatalog | null = null;
  #loading = false;
  #busyId = "";
  #error = "";
  #message = "";
  #activeKind: ProfileKind = "printer";

  connectedCallback(): void {
    if (!this.#editor.isConnected) document.body.append(this.#editor);
    this.#editor.addEventListener("profile-save-request", this.#onEditorSave as EventListener);
    this.#render();
    void this.#load();
  }

  disconnectedCallback(): void {
    this.#editor.removeEventListener("profile-save-request", this.#onEditorSave as EventListener);
    this.#editor.remove();
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
    } catch (error) {
      this.#catalog = null;
      this.#error = errorMessage(error);
    } finally {
      this.#loading = false;
      this.#render();
    }
  }

  #section(id: string, title: string, body: string, meta = ""): string {
    return `<details class="section" data-section="${esc(id)}" ${this.#openSections.has(id) ? "open" : ""}><summary><span>${esc(title)}</span>${meta ? `<small>${esc(meta)}</small>` : ""}</summary><div class="section-body">${body}</div></details>`;
  }

  #render(): void {
    const catalog = this.#catalog;
    const group = GROUPS.find((item) => item.kind === this.#activeKind) ?? GROUPS[0]!;
    const profiles = catalog?.groups[this.#activeKind] ?? [];
    const selected = catalog ? selectedId(catalog.selection, this.#activeKind) : null;
    const profileBody = profiles.length
      ? `<div class="grid">${profiles.map((profile) => this.#profileCard(profile, selected)).join("")}</div>`
      : '<div class="empty">Keine Profile dieser Kategorie vorhanden.</div>';

    this.#root.innerHTML = `<style>
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff}*{box-sizing:border-box}.page{padding:20px}.head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.head h1{margin:0}.head p{margin:6px 0 0;color:#91a5bb}.head-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.status{padding:8px 10px;border:1px solid #2d4d68;border-radius:999px;color:#9fc6e5;font-size:12px}.action,.tabs button{border:1px solid #31506e;border-radius:8px;padding:9px 11px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}.action:hover,.tabs button:hover{border-color:#41c5ff}.action:disabled,.tabs button:disabled{opacity:.4;cursor:not-allowed}.primary{border-color:#41c5ff;background:#17638a}.danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}.tabs{display:flex;gap:7px;flex-wrap:wrap;margin:18px 0}.tabs button[active]{border-color:#41c5ff;background:#173b58}.message,.error,.empty{margin:12px 0;padding:13px;border:1px solid #2a3c53;border-radius:10px;background:#111b29;color:#91a5bb}.message{border-color:#27734c;color:#8ff0b5}.error{border-color:#8f3f4b;color:#ffd7dc}.section{margin:12px 0;border:1px solid #2a3c53;border-radius:12px;background:#0d1723;overflow:hidden}.section>summary{display:flex;align-items:center;gap:10px;padding:13px 15px;cursor:pointer;list-style:none;background:#101c29;font-size:14px;font-weight:800}.section>summary::-webkit-details-marker,.profile-card>summary::-webkit-details-marker{display:none}.section>summary::before,.profile-card>summary::before{content:"›";font-size:20px;line-height:1;transition:transform .15s}.section[open]>summary::before,.profile-card[open]>summary::before{transform:rotate(90deg)}.section>summary span{margin-right:auto}.section>summary small{color:#8299af;font-size:11px;font-weight:500}.section-body{padding:14px}.cloud-body{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center}.cloud-body p{margin:0;color:#9eb3c7;font-size:12px;line-height:1.5}.cloud-stats{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.cloud-stat{padding:4px 7px;border:1px solid #ffffff24;border-radius:999px;font-size:10px;color:#b9d3e8}.grid{display:grid;gap:9px}.profile-card{border:1px solid #2a3c53;border-radius:10px;background:#101925;overflow:hidden}.profile-card[selected]{border-color:#45c5ff;box-shadow:inset 3px 0 #45c5ff}.profile-card.cloud-card{background:linear-gradient(145deg,#102031,#101925)}.profile-card>summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:9px;align-items:center;padding:12px 13px;cursor:pointer;list-style:none}.profile-title{min-width:0}.profile-title strong,.profile-title small{display:block}.profile-title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.profile-title small{margin-top:3px;color:#7f96ac;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.badge{padding:3px 7px;border:1px solid #385b78;border-radius:999px;color:#9cc5e4;font-size:10px;text-transform:uppercase}.profile-card[selected] .badge{border-color:#45c5ff;color:#d9f4ff}.profile-body{padding:0 13px 13px;border-top:1px solid #223449}.values{display:grid;gap:0}.value{display:grid;grid-template-columns:minmax(120px,.7fr) minmax(0,1.3fr);gap:8px;padding:7px 0;border-bottom:1px solid #223449;font-size:12px}.value span:first-child{color:#7890a8}.value span:last-child{overflow-wrap:anywhere}.more-values{padding:8px 0;color:#71899f;font-size:11px}.card-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.card-actions button{flex:1;min-width:125px}.hint{margin-top:10px;color:#70879d;font-size:11px;line-height:1.5}@media(max-width:700px){.head{display:block}.head-actions{justify-content:flex-start;margin-top:10px}.cloud-body{grid-template-columns:1fr}.value{grid-template-columns:1fr}.profile-card>summary{grid-template-columns:auto minmax(0,1fr)}}
    </style><section class="page"><div class="head"><div><h1>Profile</h1><p>Alle Parameter sind wie in einer Slicer-Profilverwaltung vollständig editierbar. Lange G-Code-Bereiche bleiben eingeklappt.</p></div><div class="head-actions"><span class="status">${catalog?.persistent ? "Lokal persistent" : "Wird geladen"}</span><button class="action primary" id="new-profile" type="button">Neues ${esc(group.label)}-Profil</button><button class="action" id="collapse-all" type="button">Alles einklappen</button></div></div>${catalog ? this.#cloudPanel(catalog) : ""}<nav class="tabs">${GROUPS.map((item) => `<button type="button" data-kind="${item.kind}" ${item.kind === this.#activeKind ? "active" : ""}>${item.label}</button>`).join("")}</nav>${this.#message ? `<div class="message">${esc(this.#message)}</div>` : ""}${this.#error ? `<div class="error">${esc(this.#error)}</div>` : ""}${this.#loading ? '<div class="empty">Profilkatalog wird geladen …</div>' : this.#section("profiles", `${group.label}: ${group.description}`, profileBody, `${profiles.length} Profile`)}</section>`;

    this.#root.querySelector<HTMLButtonElement>("#new-profile")?.addEventListener("click", () => this.#newProfile(this.#activeKind));
    this.#root.querySelector<HTMLButtonElement>("#collapse-all")?.addEventListener("click", () => {
      this.#openSections.clear();
      this.#openProfiles.clear();
      this.#render();
    });
    this.#root.querySelectorAll<HTMLDetailsElement>("details[data-section]").forEach((details) => details.addEventListener("toggle", () => {
      const id = details.dataset.section || "";
      if (details.open) this.#openSections.add(id); else this.#openSections.delete(id);
    }));
    this.#root.querySelectorAll<HTMLDetailsElement>("details[data-profile-id]").forEach((details) => {
      const profile = profiles.find((item) => item.id === details.dataset.profileId);
      if (!profile) return;
      details.addEventListener("toggle", () => { if (details.open) this.#openProfiles.add(profile.id); else this.#openProfiles.delete(profile.id); });
      details.addEventListener("contextmenu", (event) => this.#openContext(event, profile));
    });
    this.#root.querySelector<HTMLButtonElement>("#cloud-sync")?.addEventListener("click", () => void this.#syncCloud());
    this.#root.querySelectorAll<HTMLButtonElement>("[data-kind]").forEach((button) => button.addEventListener("click", () => {
      this.#activeKind = button.dataset.kind as ProfileKind;
      this.#message = "";
      this.#error = "";
      this.#openSections.add("profiles");
      this.#render();
    }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='select']").forEach((button) => button.addEventListener("click", (event) => {
      event.stopPropagation();
      const profile = profiles.find((item) => item.id === button.dataset.profileId);
      if (profile) void this.#select(profile);
    }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='edit']").forEach((button) => button.addEventListener("click", (event) => {
      event.stopPropagation();
      const profile = profiles.find((item) => item.id === button.dataset.profileId);
      if (profile) this.#editor.open(profile);
    }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-action='delete']").forEach((button) => button.addEventListener("click", (event) => {
      event.stopPropagation();
      const profile = profiles.find((item) => item.id === button.dataset.profileId);
      if (profile) void this.#remove(profile);
    }));
  }

  #cloudPanel(catalog: V6ProfileCatalog): string {
    const cloud = catalog.cloud_sync;
    const headline = cloud.syncing ? "Bambu Cloud wird synchronisiert …" : cloud.available_offline ? `${catalog.source_counts.bambu_cloud} Bambu-Cloud-Profile lokal verfügbar` : cloud.configured ? "Bambu Cloud verbunden, noch keine Profile gespeichert" : "Bambu-Cloud-Zugang wird aus der vorhandenen Integration übernommen";
    const description = cloud.last_error ? `${cloud.last_error}. Der letzte lokale Profilstand bleibt erhalten.` : cloud.available_offline ? `Letzter Abgleich: ${dateLabel(cloud.last_sync_at)}. Cloudprofile können als lokale Benutzerprofile vollständig verändert werden.` : "Beim ersten erfolgreichen Abgleich werden eigene Filament-, Druck- und Maschinenprofile dauerhaft in V6 gespiegelt.";
    const body = `<div class="cloud-body"><div><p>${esc(description)}</p><div class="cloud-stats"><span class="cloud-stat">Cloud ${catalog.source_counts.bambu_cloud}</span><span class="cloud-stat">Eigen ${catalog.source_counts.local}</span><span class="cloud-stat">Standard ${catalog.source_counts.builtin}</span><span class="cloud-stat">Offline ${cloud.available_offline ? "bereit" : "leer"}</span></div></div><button class="action" id="cloud-sync" type="button" ${this.#busyId || cloud.syncing ? "disabled" : ""}>${this.#busyId === "cloud-sync" || cloud.syncing ? "Synchronisiert …" : "Jetzt synchronisieren"}</button></div>`;
    return this.#section("cloud", headline, body, cloud.available_offline ? "offline bereit" : "nicht synchronisiert");
  }

  #profileCard(profile: V6Profile, selected: string | null): string {
    const active = profile.id === selected;
    const allValues = Object.entries(profile.payload)
      .filter(([key]) => key !== "_bambu_cloud")
      .sort(([left], [right]) => left.localeCompare(right));
    const previewValues = allValues.filter(([key]) => !key.toLowerCase().includes("gcode")).slice(0, 10);
    const hiddenCount = Math.max(0, allValues.length - previewValues.length);
    const removable = profile.source === "local";
    const editLabel = removable ? "Bearbeiten" : "Als Benutzerprofil bearbeiten";
    return `<details class="profile-card ${profile.source === "bambu_cloud" ? "cloud-card" : ""}" data-profile-id="${esc(profile.id)}" ${active ? "selected" : ""} ${this.#openProfiles.has(profile.id) ? "open" : ""}><summary><span></span><span class="profile-title"><strong>${esc(profile.name)}</strong><small>${esc(profile.id)}${profile.base_id ? ` · Basis ${esc(profile.base_id)}` : ""}</small></span><span class="badge">${active ? `Aktiv · ${sourceLabel(profile)}` : sourceLabel(profile)}</span></summary><div class="profile-body"><div class="values">${previewValues.map(([key, value]) => `<div class="value"><span>${esc(key)}</span><span>${esc(prettyValue(value))}</span></div>`).join("")}</div>${hiddenCount ? `<div class="more-values">${hiddenCount} weitere Parameter einschließlich möglicher G-Code-Felder sind im Editor verfügbar.</div>` : ""}<div class="card-actions"><button class="action" type="button" data-action="select" data-profile-id="${esc(profile.id)}" ${active || this.#busyId ? "disabled" : ""}>${active ? "Ausgewählt" : "Auswählen"}</button><button class="action primary" type="button" data-action="edit" data-profile-id="${esc(profile.id)}" ${this.#busyId ? "disabled" : ""}>${editLabel}</button>${removable ? `<button class="action danger" type="button" data-action="delete" data-profile-id="${esc(profile.id)}" ${this.#busyId ? "disabled" : ""}>Löschen</button>` : ""}</div></div></details>`;
  }

  #newProfile(kind: ProfileKind): void {
    const now = new Date().toISOString();
    const profile: V6Profile = {
      id: `template.${kind}`,
      kind,
      name: `Neues ${GROUPS.find((item) => item.kind === kind)?.label ?? "Benutzer"}-Profil`,
      source: "builtin",
      payload: defaultPayload(kind),
      builtin: true,
      base_id: null,
      version: null,
      created_at: now,
      updated_at: now,
    };
    this.#editor.open(profile);
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
      if (detail.select_after_save) await this.#select(profile);
      this.#activeKind = profile.kind;
      this.#openSections.add("profiles");
      this.#openProfiles.add(profile.id);
      this.#message = `${profile.name} wurde vollständig gespeichert${detail.select_after_save ? " und ausgewählt" : ""}.`;
      this.#editor.close();
    } catch (error) {
      const message = errorMessage(error);
      this.#error = message;
      window.alert(`Profil konnte nicht gespeichert werden:\n\n${message}`);
    } finally {
      this.#busyId = "";
      this.#render();
    }
  }

  async #syncCloud(): Promise<void> {
    if (this.#busyId) return;
    this.#busyId = "cloud-sync"; this.#error = ""; this.#message = ""; this.#render();
    try {
      const result = await this.#api.syncCloudProfiles();
      await this.#load();
      if (result.status.last_error) this.#error = result.status.last_error;
      else this.#message = `${result.profile_count} Bambu-Cloud-Profile wurden synchronisiert und lokal gespeichert.`;
    } catch (error) { this.#error = errorMessage(error); }
    finally { this.#busyId = ""; this.#render(); }
  }

  async #select(profile: V6Profile): Promise<void> {
    if (!this.#catalog || (this.#busyId && this.#busyId !== "profile-editor")) return;
    const previousBusy = this.#busyId;
    this.#busyId = profile.id;
    this.#error = "";
    this.#render();
    try {
      const selection = await this.#api.saveSelection(selectionPatch(profile.kind, profile.id));
      this.#catalog = { ...this.#catalog, selection };
      this.#message = `${profile.name} ist jetzt ausgewählt.`;
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#busyId = previousBusy === "profile-editor" ? previousBusy : "";
      this.#render();
    }
  }

  async #remove(profile: V6Profile): Promise<void> {
    if (profile.source !== "local" || this.#busyId) return;
    if (!window.confirm(`Eigenes Profil löschen?\n\n${profile.name}`)) return;
    this.#busyId = profile.id; this.#error = ""; this.#message = ""; this.#render();
    try { await this.#api.removeProfile(profile.id); await this.#load(); this.#message = `${profile.name} wurde gelöscht.`; }
    catch (error) { this.#error = errorMessage(error); }
    finally { this.#busyId = ""; this.#render(); }
  }

  #openContext(event: MouseEvent, profile: V6Profile): void {
    const actions: ContextMenuAction[] = [
      { label: "Profil bearbeiten", disabled: this.#busyId !== "", run: () => this.#editor.open(profile) },
      { label: "Profil auswählen", disabled: this.#busyId !== "", run: () => this.#select(profile) },
      { label: "Profil-ID kopieren", run: async () => { await navigator.clipboard?.writeText(profile.id); this.#message = "Profil-ID wurde kopiert."; this.#render(); } },
      { label: "Profilwerte kopieren", run: async () => { await navigator.clipboard?.writeText(JSON.stringify(profile.payload, null, 2)); this.#message = "Profilwerte wurden kopiert."; this.#render(); } },
    ];
    if (profile.source === "local") actions.push({ label: "Eigenes Profil löschen", danger: true, separatorBefore: true, run: () => this.#remove(profile) });
    openContextMenu(event, actions);
  }
}

if (!customElements.get("ultimate-3d-profile-workspace")) {
  customElements.define("ultimate-3d-profile-workspace", Ultimate3DProfileWorkspaceV2);
}
