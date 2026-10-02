import type { ProfileKind, V6Profile } from "./profile-api.js";

type ProfileDraft = {
  id?: string | undefined;
  kind: ProfileKind;
  name: string;
  payload: Record<string, unknown>;
  base_id?: string | null;
  version?: string | null;
  origin_profile_id?: string | null;
};

type FieldCategory = Readonly<{
  id: string;
  label: string;
  order: number;
}>;

const CATEGORIES: readonly FieldCategory[] = [
  { id: "machine", label: "Maschine und Druckraum", order: 10 },
  { id: "quality", label: "Qualität und Struktur", order: 20 },
  { id: "speed", label: "Geschwindigkeit und Beschleunigung", order: 30 },
  { id: "temperature", label: "Temperatur und Kühlung", order: 40 },
  { id: "extrusion", label: "Extrusion und Rückzug", order: 50 },
  { id: "support", label: "Support und Haftung", order: 60 },
  { id: "gcode", label: "Start-, End- und benutzerdefinierter G-Code", order: 70 },
  { id: "general", label: "Weitere Parameter", order: 80 },
];

function clonePayload(payload: Readonly<Record<string, unknown>>): Record<string, unknown> {
  return JSON.parse(JSON.stringify(payload)) as Record<string, unknown>;
}

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function categoryFor(key: string): FieldCategory {
  const value = key.toLowerCase();
  if (/(start_gcode|end_gcode|machine_gcode|filament_gcode|gcode)/.test(value)) return CATEGORIES[6]!;
  if (/(temperature|temp_|bed_temp|nozzle_temp|fan|cool|chamber)/.test(value)) return CATEGORIES[3]!;
  if (/(speed|velocity|accel|jerk|volumetric)/.test(value)) return CATEGORIES[2]!;
  if (/(retract|flow|pressure|extrusion|extruder|linear_advance|k_value)/.test(value)) return CATEGORIES[4]!;
  if (/(support|raft|brim|skirt|adhesion|overhang)/.test(value)) return CATEGORIES[5]!;
  if (/(layer|wall|shell|infill|seam|ironing|quality|resolution|precision|top_|bottom_)/.test(value)) return CATEGORIES[1]!;
  if (/(printer|machine|build_volume|bed_|nozzle|diameter|technology|vendor|model)/.test(value)) return CATEGORIES[0]!;
  return CATEGORIES[7]!;
}

function fieldType(value: unknown): "boolean" | "number" | "string" | "array" | "json" {
  if (typeof value === "boolean") return "boolean";
  if (typeof value === "number") return "number";
  if (typeof value === "string") return "string";
  if (Array.isArray(value) && value.every((item) => ["string", "number", "boolean"].includes(typeof item))) return "array";
  return "json";
}

function fieldLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\bmm3\b/gi, "mm³")
    .replace(/\bmm\b/gi, "mm")
    .replace(/\bc\b/g, "°C")
    .replace(/\b([a-z])/g, (value) => value.toUpperCase());
}

function parseArray(raw: string, original: readonly unknown[]): unknown[] {
  const trimmed = raw.trim();
  if (!trimmed) return [];
  if (trimmed.startsWith("[")) {
    const parsed = JSON.parse(trimmed) as unknown;
    if (!Array.isArray(parsed)) throw new Error("Der Wert muss ein JSON-Array sein.");
    return parsed;
  }
  const values = trimmed.split(/[\n,;]/).map((item) => item.trim()).filter(Boolean);
  const sample = original.find((item) => item !== null);
  if (typeof sample === "number") return values.map((item) => {
    const number = Number(item.replace(",", "."));
    if (!Number.isFinite(number)) throw new Error(`Ungültige Zahl: ${item}`);
    return number;
  });
  if (typeof sample === "boolean") return values.map((item) => ["1", "true", "ja", "yes", "on"].includes(item.toLowerCase()));
  return values;
}

export class V6ProfileEditorDialog extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #source: V6Profile | null = null;
  #draft: ProfileDraft | null = null;
  #search = "";
  #jsonError = "";
  #fieldErrors = new Map<string, string>();
  #selectAfterSave = true;

  open(profile: V6Profile): void {
    this.#source = profile;
    const local = profile.source === "local";
    this.#draft = {
      id: local ? profile.id : undefined,
      kind: profile.kind,
      name: local ? profile.name : `${profile.name} – Benutzerprofil`,
      payload: clonePayload(profile.payload),
      base_id: profile.base_id ?? profile.id,
      version: profile.version ?? null,
      origin_profile_id: profile.id,
    };
    this.#search = "";
    this.#jsonError = "";
    this.#fieldErrors.clear();
    this.#selectAfterSave = true;
    this.hidden = false;
    this.#render();
  }

  close(): void {
    this.hidden = true;
    this.#source = null;
    this.#draft = null;
    this.#root.replaceChildren();
  }

  connectedCallback(): void {
    this.hidden = true;
  }

  #render(): void {
    const source = this.#source;
    const draft = this.#draft;
    if (!source || !draft) return;
    const entries = Object.entries(draft.payload)
      .filter(([key]) => !this.#search || `${key} ${fieldLabel(key)}`.toLowerCase().includes(this.#search.toLowerCase()))
      .sort(([left], [right]) => left.localeCompare(right));
    const grouped = new Map<string, Array<[string, unknown]>>();
    for (const entry of entries) {
      const category = categoryFor(entry[0]);
      const items = grouped.get(category.id) ?? [];
      items.push(entry);
      grouped.set(category.id, items);
    }
    const categories = CATEGORIES
      .filter((category) => (grouped.get(category.id)?.length ?? 0) > 0)
      .sort((left, right) => left.order - right.order);
    const isClone = source.source !== "local";

    this.#root.innerHTML = `<style>
      :host{position:fixed;inset:0;z-index:2147483000;display:grid;place-items:center;background:#02070dbd;color:#eff7ff;font:13px/1.45 Inter,Segoe UI,sans-serif}:host([hidden]){display:none}*{box-sizing:border-box}.dialog{width:min(1180px,96vw);height:min(900px,94vh);display:grid;grid-template-rows:auto auto minmax(0,1fr) auto;border:1px solid #31506e;border-radius:14px;background:#08121d;box-shadow:0 30px 90px #000b;overflow:hidden}.head{display:flex;justify-content:space-between;gap:16px;padding:15px 18px;border-bottom:1px solid #26394d;background:#0e1b29}.head h2{margin:0;font-size:18px}.head p{margin:4px 0 0;color:#91a8bd}.close{border:1px solid #425b72;border-radius:8px;background:#142536;color:#fff;padding:8px 11px;cursor:pointer}.toolbar{display:grid;grid-template-columns:minmax(260px,1fr) minmax(240px,1fr) auto;gap:9px;padding:11px 16px;border-bottom:1px solid #26394d;background:#0a1622}.toolbar input,.toolbar select,.field input,.field textarea,.add-row input,.add-row select,.raw textarea{width:100%;border:1px solid #31506e;border-radius:7px;background:#07111c;color:#fff;padding:8px}.toolbar label{display:grid;gap:4px;color:#91a8bd;font-size:11px}.badge{align-self:end;padding:8px 10px;border:1px solid #2f6d8e;border-radius:999px;color:#9edfff;white-space:nowrap}.body{overflow:auto;padding:14px 16px}.category,.raw,.add-parameter{margin:0 0 10px;border:1px solid #263a4e;border-radius:10px;background:#0c1723;overflow:hidden}.category summary,.raw summary,.add-parameter summary{display:flex;align-items:center;gap:8px;padding:10px 12px;cursor:pointer;list-style:none;background:#101e2c;font-weight:800}.category summary::-webkit-details-marker,.raw summary::-webkit-details-marker,.add-parameter summary::-webkit-details-marker{display:none}.category summary::before,.raw summary::before,.add-parameter summary::before{content:'›';font-size:20px;transition:transform .15s}.category[open] summary::before,.raw[open] summary::before,.add-parameter[open] summary::before{transform:rotate(90deg)}.category summary small{margin-left:auto;color:#7f96aa;font-weight:500}.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:8px;padding:10px}.field{display:grid;grid-template-columns:minmax(145px,.8fr) minmax(0,1.2fr) auto;gap:8px;align-items:start;padding:9px;border:1px solid #22364a;border-radius:8px;background:#09131e}.field-label strong,.field-label small{display:block}.field-label small{color:#6f879c;font:10px ui-monospace,Consolas,monospace;margin-top:3px;overflow-wrap:anywhere}.field textarea{min-height:74px;resize:vertical;font-family:ui-monospace,Consolas,monospace}.field.gcode{grid-column:1/-1}.field.gcode textarea{min-height:130px}.remove{border:1px solid #76424a;border-radius:7px;background:#351b20;color:#ffc3ca;padding:7px;cursor:pointer}.boolean{display:flex;align-items:center;gap:8px;min-height:36px}.boolean input{width:auto}.field-error{grid-column:2/-1;color:#ffadb8;font-size:11px}.raw-body,.add-body{padding:11px}.raw textarea{min-height:320px;resize:vertical;font-family:ui-monospace,Consolas,monospace}.raw-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:8px}.error{color:#ffadb8;margin-top:6px}.add-row{display:grid;grid-template-columns:1fr 170px 1fr auto;gap:8px}.footer{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px;border-top:1px solid #26394d;background:#0e1a27}.footer-left{display:flex;align-items:center;gap:8px;color:#9bb0c3}.footer-actions{display:flex;gap:8px}.button{border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef6ff;padding:9px 12px;cursor:pointer;font-weight:700}.primary{border-color:#48c9ff;background:#17658b}.warning{color:#ffd588}.empty{padding:22px;text-align:center;color:#8298ad}@media(max-width:760px){.dialog{width:100vw;height:100vh;border-radius:0}.toolbar{grid-template-columns:1fr}.fields{grid-template-columns:1fr}.field{grid-template-columns:1fr auto}.field-label{grid-column:1/-1}.field input,.field textarea,.field .boolean{grid-column:1}.add-row{grid-template-columns:1fr}.footer{align-items:flex-start;flex-direction:column}.footer-actions{width:100%}.footer-actions .button{flex:1}}
    </style><section class="dialog"><header class="head"><div><h2>${escapeHtml(isClone ? "Benutzerprofil aus Vorlage erstellen" : "Benutzerprofil bearbeiten")}</h2><p>${escapeHtml(source.name)} · ${escapeHtml(source.kind)} · ${escapeHtml(sourceLabel(source))}</p></div><button class="close" type="button" data-action="close">Schließen</button></header><section class="toolbar"><label>Profilname<input id="profile-name" maxlength="160" value="${escapeHtml(draft.name)}"></label><label>Parameter suchen<input id="parameter-search" placeholder="z. B. Temperatur, Geschwindigkeit oder G-Code" value="${escapeHtml(this.#search)}"></label><span class="badge">${entries.length} von ${Object.keys(draft.payload).length} Parametern</span></section><main class="body">${categories.length ? categories.map((category, index) => this.#category(category, grouped.get(category.id) ?? [], index === 0 && category.id !== "gcode")).join("") : '<div class="empty">Keine Parameter entsprechen der Suche.</div>'}${this.#addParameter()}${this.#rawJson()}</main><footer class="footer"><label class="footer-left"><input id="select-after-save" type="checkbox" ${this.#selectAfterSave ? "checked" : ""}><span>Nach dem Speichern direkt auswählen</span></label><div class="footer-actions"><button class="button" type="button" data-action="close">Abbrechen</button><button class="button primary" type="button" data-action="save">${isClone ? "Als Benutzerprofil speichern" : "Änderungen speichern"}</button></div></footer></section>`;

    this.#bind();
  }

  #category(category: FieldCategory, fields: readonly [string, unknown][], open: boolean): string {
    return `<details class="category" ${open ? "open" : ""}><summary><span>${escapeHtml(category.label)}</span><small>${fields.length} Parameter</small></summary><div class="fields">${fields.map(([key, value]) => this.#field(key, value, category.id === "gcode")).join("")}</div></details>`;
  }

  #field(key: string, value: unknown, gcode: boolean): string {
    const type = fieldType(value);
    const error = this.#fieldErrors.get(key) || "";
    let editor = "";
    if (type === "boolean") {
      editor = `<label class="boolean"><input type="checkbox" data-field="${escapeHtml(key)}" data-type="boolean" ${value ? "checked" : ""}><span>${value ? "Aktiviert" : "Deaktiviert"}</span></label>`;
    } else if (type === "number") {
      editor = `<input type="number" step="any" data-field="${escapeHtml(key)}" data-type="number" value="${escapeHtml(value)}">`;
    } else if (type === "string") {
      const multiline = gcode || String(value).length > 100 || String(value).includes("\n");
      editor = multiline
        ? `<textarea data-field="${escapeHtml(key)}" data-type="string">${escapeHtml(value)}</textarea>`
        : `<input type="text" data-field="${escapeHtml(key)}" data-type="string" value="${escapeHtml(value)}">`;
    } else if (type === "array") {
      editor = `<textarea data-field="${escapeHtml(key)}" data-type="array">${escapeHtml((value as readonly unknown[]).join(", "))}</textarea>`;
    } else {
      editor = `<textarea data-field="${escapeHtml(key)}" data-type="json">${escapeHtml(JSON.stringify(value, null, 2))}</textarea>`;
    }
    return `<div class="field ${gcode ? "gcode" : ""}"><span class="field-label"><strong>${escapeHtml(fieldLabel(key))}</strong><small>${escapeHtml(key)}</small></span>${editor}<button class="remove" type="button" data-remove="${escapeHtml(key)}" title="Parameter entfernen">×</button>${error ? `<div class="field-error">${escapeHtml(error)}</div>` : ""}</div>`;
  }

  #addParameter(): string {
    return `<details class="add-parameter"><summary>Neuen Parameter hinzufügen</summary><div class="add-body"><div class="add-row"><input id="new-key" placeholder="parameter_name"><select id="new-type"><option value="string">Text</option><option value="number">Zahl</option><option value="boolean">Ja/Nein</option><option value="array">Liste</option><option value="json">JSON-Struktur</option></select><input id="new-value" placeholder="Startwert"><button class="button" type="button" data-action="add">Hinzufügen</button></div></div></details>`;
  }

  #rawJson(): string {
    return `<details class="raw"><summary>Roh-JSON – Expertenansicht</summary><div class="raw-body"><textarea id="raw-json">${escapeHtml(JSON.stringify(this.#draft?.payload ?? {}, null, 2))}</textarea>${this.#jsonError ? `<div class="error">${escapeHtml(this.#jsonError)}</div>` : ""}<div class="raw-actions"><button class="button" type="button" data-action="apply-json">JSON übernehmen</button></div></div></details>`;
  }

  #bind(): void {
    this.#root.querySelectorAll<HTMLElement>('[data-action="close"]').forEach((button) => button.addEventListener("click", () => this.close()));
    this.#root.querySelector<HTMLInputElement>("#profile-name")?.addEventListener("input", (event) => {
      if (this.#draft) this.#draft.name = (event.currentTarget as HTMLInputElement).value;
    });
    this.#root.querySelector<HTMLInputElement>("#parameter-search")?.addEventListener("input", (event) => {
      this.#search = (event.currentTarget as HTMLInputElement).value;
      this.#render();
      queueMicrotask(() => this.#root.querySelector<HTMLInputElement>("#parameter-search")?.focus());
    });
    this.#root.querySelector<HTMLInputElement>("#select-after-save")?.addEventListener("change", (event) => {
      this.#selectAfterSave = (event.currentTarget as HTMLInputElement).checked;
    });
    this.#root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("[data-field]").forEach((input) => {
      const eventName = input.dataset.type === "boolean" ? "change" : "change";
      input.addEventListener(eventName, () => this.#updateField(input));
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-remove]").forEach((button) => button.addEventListener("click", () => {
      if (!this.#draft) return;
      delete this.#draft.payload[button.dataset.remove || ""];
      this.#render();
    }));
    this.#root.querySelector<HTMLButtonElement>('[data-action="add"]')?.addEventListener("click", () => this.#add());
    this.#root.querySelector<HTMLButtonElement>('[data-action="apply-json"]')?.addEventListener("click", () => this.#applyRawJson());
    this.#root.querySelector<HTMLButtonElement>('[data-action="save"]')?.addEventListener("click", () => this.#save());
  }

  #updateField(input: HTMLInputElement | HTMLTextAreaElement): void {
    const draft = this.#draft;
    const key = input.dataset.field || "";
    if (!draft || !key) return;
    try {
      const type = input.dataset.type;
      const original = draft.payload[key];
      if (type === "boolean" && input instanceof HTMLInputElement) draft.payload[key] = input.checked;
      else if (type === "number") {
        const value = Number(input.value);
        if (!Number.isFinite(value)) throw new Error("Bitte eine gültige Zahl eingeben.");
        draft.payload[key] = value;
      } else if (type === "array") draft.payload[key] = parseArray(input.value, Array.isArray(original) ? original : []);
      else if (type === "json") draft.payload[key] = JSON.parse(input.value) as unknown;
      else draft.payload[key] = input.value;
      this.#fieldErrors.delete(key);
    } catch (error) {
      this.#fieldErrors.set(key, error instanceof Error ? error.message : String(error));
    }
  }

  #add(): void {
    const draft = this.#draft;
    if (!draft) return;
    const key = this.#root.querySelector<HTMLInputElement>("#new-key")?.value.trim() || "";
    const type = this.#root.querySelector<HTMLSelectElement>("#new-type")?.value || "string";
    const raw = this.#root.querySelector<HTMLInputElement>("#new-value")?.value || "";
    if (!/^[A-Za-z0-9_.-]+$/.test(key)) {
      this.#jsonError = "Der Parametername darf nur Buchstaben, Zahlen, Punkt, Unterstrich und Bindestrich enthalten.";
      this.#render();
      return;
    }
    try {
      if (type === "number") {
        const value = Number(raw);
        if (!Number.isFinite(value)) throw new Error("Ungültige Zahl.");
        draft.payload[key] = value;
      } else if (type === "boolean") draft.payload[key] = ["1", "true", "ja", "yes", "on"].includes(raw.toLowerCase());
      else if (type === "array") draft.payload[key] = parseArray(raw, []);
      else if (type === "json") draft.payload[key] = JSON.parse(raw || "{}") as unknown;
      else draft.payload[key] = raw;
      this.#jsonError = "";
      this.#search = "";
      this.#render();
    } catch (error) {
      this.#jsonError = error instanceof Error ? error.message : String(error);
      this.#render();
    }
  }

  #applyRawJson(): void {
    const draft = this.#draft;
    if (!draft) return;
    const raw = this.#root.querySelector<HTMLTextAreaElement>("#raw-json")?.value || "{}";
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Das Profil muss ein JSON-Objekt sein.");
      draft.payload = parsed as Record<string, unknown>;
      this.#jsonError = "";
      this.#fieldErrors.clear();
      this.#render();
    } catch (error) {
      this.#jsonError = error instanceof Error ? error.message : String(error);
      this.#render();
    }
  }

  #save(): void {
    const draft = this.#draft;
    if (!draft) return;
    this.#root.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>("[data-field]").forEach((input) => this.#updateField(input));
    if (this.#fieldErrors.size) {
      this.#render();
      return;
    }
    const name = draft.name.trim();
    if (!name) {
      this.#jsonError = "Der Profilname darf nicht leer sein.";
      this.#render();
      return;
    }
    this.dispatchEvent(new CustomEvent("profile-save-request", {
      bubbles: true,
      composed: true,
      detail: { ...draft, name, select_after_save: this.#selectAfterSave },
    }));
  }
}

function sourceLabel(profile: V6Profile): string {
  if (profile.source === "bambu_cloud") return "Bambu Cloud";
  if (profile.source === "local") return "Lokales Benutzerprofil";
  return "Standardprofil";
}

if (!customElements.get("v6-profile-editor-dialog")) {
  customElements.define("v6-profile-editor-dialog", V6ProfileEditorDialog);
}