import { callEnvelopeApi } from "./ha-api-transport.js";

type AuditEvent = Readonly<Record<string, unknown>>;
type SeverityFilter = "all" | "info" | "warning" | "error";
type SortDirection = "desc" | "asc";
type HealthData = Readonly<{
  status?: unknown;
  entries?: readonly Readonly<Record<string, unknown>>[];
}>;
type AuditResponse = Readonly<{
  items?: AuditEvent[];
  total?: number;
  maximum?: number;
  categories?: readonly Readonly<{ name?: unknown; count?: unknown }>[];
}>;

const DEFAULT_CATEGORIES = [
  "Studio", "Slicer", "Slicing-Server", "MakerWorld", "Galerie", "Druck",
  "AMS", "Profile", "Kamera", "System", "API", "Lifecycle",
] as const;

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function record(value: unknown): Readonly<Record<string, unknown>> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Readonly<Record<string, unknown>>
    : {};
}

function records(value: unknown): readonly Readonly<Record<string, unknown>>[] {
  return Array.isArray(value)
    ? value.filter((item): item is Readonly<Record<string, unknown>> => (
      Boolean(item && typeof item === "object" && !Array.isArray(item))
    ))
    : [];
}

function levelOf(event: AuditEvent): Exclude<SeverityFilter, "all"> {
  const source = [event.level, event.severity, event.status, event.event]
    .map((value) => String(value || "").toLowerCase()).join(" ");
  if (source.includes("error") || source.includes("fail") || source.includes("reject") || source.includes("exception")) return "error";
  if (source.includes("warn") || source.includes("cancel")) return "warning";
  return "info";
}

function categoryOf(event: AuditEvent): string {
  const explicit = String(event.category || "").trim();
  if (explicit) return explicit;
  const source = `${String(event.component || "")} ${String(event.event || "")}`.toLocaleLowerCase("de-DE");
  if (source.includes("makerworld")) return "MakerWorld";
  if (source.includes("gallery") || source.includes("galerie")) return "Galerie";
  if (source.includes("profile") || source.includes("profil")) return "Profile";
  if (source.includes("camera") || source.includes("kamera")) return "Kamera";
  if (source.includes("ams") || source.includes("filament")) return "AMS";
  if (source.includes("slicing-server") || source.includes("printer_slicing_server")) return "Slicing-Server";
  if (source.includes("slicer") || source.includes("slice") || source.includes("gcode")) return "Slicer";
  if (source.includes("print") || source.includes("druck") || source.includes("printer")) return "Druck";
  if (source.includes("studio") || source.includes("scene") || source.includes("model")) return "Studio";
  if (source.includes("lifecycle") || source.includes("card-") || source.includes("module-load")) return "Lifecycle";
  return "System";
}

function healthEvents(data: HealthData): AuditEvent[] {
  const result: AuditEvent[] = [];
  for (const runtime of records(data.entries)) {
    for (const provider of records(runtime.providers)) {
      const providerId = String(provider.provider_id || "printer");
      const timestamp = String(provider.updated_at || runtime.started_at || new Date().toISOString());
      const lastError = String(provider.last_error || "").trim();
      if (lastError) {
        result.push({
          id: `health-error-${providerId}-${timestamp}`,
          timestamp,
          category: "Druck",
          component: providerId,
          event: "provider_error",
          status: "error",
          printer_id: provider.serial,
          source: "health",
          details: { message: lastError },
        });
      }
      const command = record(provider.last_command);
      if (Object.keys(command).length) {
        const accepted = command.printer_accepted === true;
        result.push({
          id: `health-command-${providerId}-${String(command.sequence_id || timestamp)}`,
          timestamp,
          category: "Druck",
          component: providerId,
          event: `Druckerkommando: ${String(command.command || "unbekannt")}`,
          status: accepted ? "success" : "error",
          printer_id: provider.serial,
          source: "health",
          details: {
            message: [
              `Sequenz ${String(command.sequence_id || "–")}`,
              `PUBACK ${command.mqtt_puback_received === true ? "ja" : "nein"}`,
              `Druckerantwort ${command.response_received === true ? "ja" : "nein"}`,
              `Ergebnis ${String(command.result || command.reason || "–")}`,
            ].join(" · "),
            command,
          },
        });
      }
    }
  }
  return result;
}

function signature(events: readonly AuditEvent[]): string {
  return events.map((event) => [
    event.id, event.timestamp, event.category, event.level, event.event,
    event.message, event.action, event.status, JSON.stringify(event.details || {}),
  ].join("|")).join("\n");
}

function eventTime(event: AuditEvent): number {
  const value = new Date(String(event.timestamp || event.created_at || "")).getTime();
  return Number.isFinite(value) ? value : 0;
}

function normalizedTerms(value: string): string[] {
  return value.split(/[,;\n]+/).map((item) => item.trim()).filter(Boolean);
}

export class Ultimate3DAuditLogPanelV3 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #events: readonly AuditEvent[] = [];
  #severity: SeverityFilter = "all";
  #categories = new Set<string>();
  #terms: string[] = [];
  #availableCategories = new Map<string, number>();
  #sort: SortDirection = "desc";
  #timer: number | null = null;
  #signature = "";
  #error = "";
  #total = 0;
  #maximum = 10_000;

  connectedCallback(): void {
    this.#mount();
    void this.#refresh();
    if (this.#timer === null) this.#timer = window.setInterval(() => void this.#refresh(), 5000);
  }

  disconnectedCallback(): void {
    if (this.#timer !== null) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  async #refresh(): Promise<void> {
    try {
      const [auditData, healthData] = await Promise.all([
        callEnvelopeApi<AuditResponse>("GET", "ultimate_3d_studio_v6/v1/system/audit?limit=2000"),
        callEnvelopeApi<HealthData>("GET", "ultimate_3d_studio_v6/v1/health"),
      ]);
      const persisted = Array.isArray(auditData?.items) ? auditData.items : [];
      const events = [...healthEvents(healthData || {}), ...persisted];
      this.#total = Number(auditData?.total ?? events.length) || events.length;
      this.#maximum = Number(auditData?.maximum ?? 10_000) || 10_000;
      this.#availableCategories.clear();
      for (const category of DEFAULT_CATEGORIES) this.#availableCategories.set(category, 0);
      for (const item of auditData?.categories || []) {
        const name = String(item.name || "").trim();
        if (name) this.#availableCategories.set(name, Number(item.count || 0));
      }
      for (const event of events) {
        const category = categoryOf(event);
        if (!this.#availableCategories.has(category)) this.#availableCategories.set(category, 0);
      }
      const next = signature(events);
      this.#error = "";
      if (next !== this.#signature) {
        this.#events = events;
        this.#signature = next;
      }
      this.#renderDynamic();
      this.#setStatus(`${this.#filteredEvents().length} angezeigt · ${this.#total}/${this.#maximum} gespeichert · ${new Date().toLocaleTimeString("de-DE")}`);
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#setStatus(this.#error, true);
    }
  }

  #mount(): void {
    this.#root.innerHTML = `<style>
      :host{display:block;color:#eef5ff}*{box-sizing:border-box}.panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}.head,.toolbar,.filter-dock,.category-bar{display:flex;align-items:center;gap:8px;padding:10px 12px;border-bottom:1px solid #26384f}.head{justify-content:space-between}.head h2{margin:0;font-size:15px}.toolbar,.category-bar{flex-wrap:wrap;background:#0c1622}.toolbar button,.category-bar button{border:1px solid #31506e;border-radius:8px;padding:7px 9px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}.toolbar button.active,.category-bar button.active{border-color:#41c5ff;background:#173b58}.toolbar input{min-width:230px;flex:1;padding:7px 9px;border:1px solid #31506e;border-radius:8px;background:#091522;color:#eef5ff}.sort{min-width:138px}.status{margin-left:auto;color:#8298ad;font-size:11px}.status.error{color:#ffb7c0}.category-bar{padding-top:8px;padding-bottom:8px}.category-bar button{padding:5px 8px;font-size:10px}.category-bar small{color:#7890a8}.filter-dock{display:none;flex-wrap:wrap;background:#0a131e}.filter-dock.visible{display:flex}.chip{display:inline-flex;align-items:center;gap:6px;padding:5px 7px;border:1px solid #3b6383;border-radius:999px;background:#153149;color:#dff3ff;font-size:11px}.chip button{border:0;background:transparent;color:#dff3ff;cursor:pointer;font-size:14px;line-height:1;padding:0}.clear{margin-left:auto}.list{max-height:620px;overflow:auto;padding:10px;scrollbar-gutter:stable}.entry{display:grid;grid-template-columns:154px 76px 116px minmax(0,1fr);gap:10px;padding:9px;border-bottom:1px solid #223449}.entry:last-child{border-bottom:0}.entry time{color:#7890a8;font-size:11px}.badge,.category{padding:3px 6px;border:1px solid #31506e;border-radius:999px;text-align:center;font-size:9px;text-transform:uppercase}.badge.warning{border-color:#9c7330;color:#ffd589}.badge.error{border-color:#8f3f4b;color:#ffb9c2}.category{color:#b9def8}.message small{display:block;margin-top:3px;color:#7f95aa}.message code{display:block;margin-top:5px;padding:6px;border:1px solid #26384f;border-radius:6px;background:#09131f;color:#d9e9f8;white-space:pre-wrap;overflow-wrap:anywhere}.details{margin-top:6px}.details summary{cursor:pointer;color:#9bc7e6;font-size:11px}.details pre{max-height:300px;overflow:auto;padding:8px;border:1px solid #26384f;border-radius:6px;background:#07111b;color:#c7d7e5;font:10px/1.4 Consolas,monospace;white-space:pre-wrap}.empty{padding:24px;text-align:center;color:#8298ad}@media(max-width:850px){.entry{grid-template-columns:1fr 1fr}.message{grid-column:1/-1}.status{width:100%;margin-left:0}}@media(max-width:520px){.entry{grid-template-columns:1fr}.message{grid-column:auto}.toolbar input{min-width:100%}}
    </style><section class="panel"><header class="head"><h2>System- und Audit-Log</h2><small>Live</small></header><div class="toolbar"><button data-severity="all" class="active">Alle</button><button data-severity="info">Info</button><button data-severity="warning">Warnungen</button><button data-severity="error">Fehler</button><input id="filter-input" type="search" placeholder="Suchfilter eingeben und Enter drücken"><button id="add-filter">Filter hinzufügen</button><button id="sort" class="sort">Neueste zuerst ↓</button><button id="refresh">Aktualisieren</button><span class="status" id="status">Wird geladen …</span></div><div class="category-bar" id="category-bar"></div><div class="filter-dock" id="filter-dock"></div><div class="list" id="list"><div class="empty">System-Log wird geladen …</div></div></section>`;
    this.#root.querySelectorAll<HTMLButtonElement>("[data-severity]").forEach((button) => {
      button.addEventListener("click", () => {
        this.#severity = button.dataset.severity as SeverityFilter;
        this.#root.querySelectorAll<HTMLButtonElement>("[data-severity]").forEach((item) => item.classList.toggle("active", item === button));
        this.#renderDynamic();
      });
    });
    const addTerms = (): void => {
      const input = this.#root.querySelector<HTMLInputElement>("#filter-input");
      if (!input) return;
      for (const term of normalizedTerms(input.value)) {
        if (!this.#terms.some((item) => item.localeCompare(term, "de", { sensitivity: "accent" }) === 0)) this.#terms.push(term);
      }
      input.value = "";
      this.#renderDynamic();
    };
    this.#root.querySelector<HTMLInputElement>("#filter-input")?.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === ",") { event.preventDefault(); addTerms(); }
    });
    this.#root.querySelector<HTMLButtonElement>("#add-filter")?.addEventListener("click", addTerms);
    this.#root.querySelector<HTMLButtonElement>("#sort")?.addEventListener("click", () => {
      this.#sort = this.#sort === "desc" ? "asc" : "desc";
      this.#renderDynamic();
    });
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refresh());
  }

  #filteredEvents(): AuditEvent[] {
    const terms = this.#terms.map((item) => item.toLocaleLowerCase("de-DE"));
    const selectedCategories = new Set([...this.#categories].map((item) => item.toLocaleLowerCase("de-DE")));
    return [...this.#events].filter((event) => {
      if (this.#severity !== "all" && levelOf(event) !== this.#severity) return false;
      if (selectedCategories.size && !selectedCategories.has(categoryOf(event).toLocaleLowerCase("de-DE"))) return false;
      if (!terms.length) return true;
      const haystack = [
        event.category, event.component, event.event, event.message, event.action,
        event.status, event.actor, event.printer_id, event.job_id,
        JSON.stringify(event.details || {}),
      ].join(" ").toLocaleLowerCase("de-DE");
      return terms.every((term) => haystack.includes(term));
    }).sort((left, right) => this.#sort === "desc" ? eventTime(right) - eventTime(left) : eventTime(left) - eventTime(right));
  }

  #renderDynamic(): void {
    this.#renderCategories();
    this.#renderChips();
    this.#renderRows();
    const sort = this.#root.querySelector<HTMLButtonElement>("#sort");
    if (sort) sort.textContent = this.#sort === "desc" ? "Neueste zuerst ↓" : "Älteste zuerst ↑";
  }

  #renderCategories(): void {
    const host = this.#root.querySelector<HTMLElement>("#category-bar");
    if (!host) return;
    const categories = [...this.#availableCategories.entries()].sort((a, b) => a[0].localeCompare(b[0], "de"));
    host.innerHTML = `<small>Kategorien:</small>${categories.map(([name, count]) => `<button type="button" data-category="${esc(name)}" class="${this.#categories.has(name) ? "active" : ""}">${esc(name)}${count ? ` · ${count}` : ""}</button>`).join("")}`;
    host.querySelectorAll<HTMLButtonElement>("[data-category]").forEach((button) => {
      button.addEventListener("click", () => {
        const category = button.dataset.category || "";
        if (!category) return;
        if (this.#categories.has(category)) this.#categories.delete(category);
        else this.#categories.add(category);
        this.#renderDynamic();
      });
    });
  }

  #renderChips(): void {
    const dock = this.#root.querySelector<HTMLElement>("#filter-dock");
    if (!dock) return;
    const chips = [
      ...[...this.#categories].map((value) => `<span class="chip">Kategorie: ${esc(value)}<button type="button" data-remove-category="${esc(value)}">×</button></span>`),
      ...this.#terms.map((value) => `<span class="chip">${esc(value)}<button type="button" data-remove-term="${esc(value)}">×</button></span>`),
    ];
    dock.classList.toggle("visible", chips.length > 0);
    dock.innerHTML = chips.length ? `${chips.join("")}<button class="chip clear" id="clear-filters" type="button">Alle Filter entfernen ×</button>` : "";
    dock.querySelectorAll<HTMLButtonElement>("[data-remove-category]").forEach((button) => button.addEventListener("click", () => {
      this.#categories.delete(button.dataset.removeCategory || "");
      this.#renderDynamic();
    }));
    dock.querySelectorAll<HTMLButtonElement>("[data-remove-term]").forEach((button) => button.addEventListener("click", () => {
      const value = button.dataset.removeTerm || "";
      this.#terms = this.#terms.filter((item) => item !== value);
      this.#renderDynamic();
    }));
    dock.querySelector<HTMLButtonElement>("#clear-filters")?.addEventListener("click", () => {
      this.#categories.clear();
      this.#terms = [];
      this.#severity = "all";
      this.#root.querySelectorAll<HTMLButtonElement>("[data-severity]").forEach((item) => item.classList.toggle("active", item.dataset.severity === "all"));
      this.#renderDynamic();
    });
  }

  #renderRows(): void {
    const list = this.#root.querySelector<HTMLElement>("#list");
    if (!list) return;
    const scrollTop = list.scrollTop;
    const filtered = this.#filteredEvents();
    list.innerHTML = filtered.length ? filtered.map((event) => {
      const level = levelOf(event);
      const category = categoryOf(event);
      const date = new Date(String(event.timestamp || event.created_at || ""));
      const timestamp = Number.isNaN(date.getTime()) ? "–" : date.toLocaleString("de-DE");
      const details = record(event.details);
      const title = event.message || event.event || event.action || "V6-Ereignis";
      const detail = [event.component, event.status, event.source, event.actor, event.printer_id, event.job_id]
        .filter(Boolean).join(" · ");
      const diagnostic = details.message || details.error || details.reason || details.code || "";
      const raw = Object.keys(details).length ? JSON.stringify(details, null, 2) : "";
      return `<article class="entry"><time>${esc(timestamp)}</time><span class="badge ${level}">${esc(level)}</span><span class="category">${esc(category)}</span><span class="message"><strong>${esc(title)}</strong>${detail ? `<small>${esc(detail)}</small>` : ""}${diagnostic ? `<code>${esc(diagnostic)}</code>` : ""}${raw ? `<details class="details"><summary>Details anzeigen</summary><pre>${esc(raw)}</pre></details>` : ""}</span></article>`;
    }).join("") : '<div class="empty">Keine passenden System- oder Audit-Einträge vorhanden.</div>';
    list.scrollTop = Math.min(scrollTop, list.scrollHeight);
    this.#setStatus(`${filtered.length} angezeigt · ${this.#total}/${this.#maximum} gespeichert`);
  }

  #setStatus(value: string, error = false): void {
    const status = this.#root.querySelector<HTMLElement>("#status");
    if (!status) return;
    status.textContent = value;
    status.classList.toggle("error", error);
  }
}

if (!customElements.get("ultimate-3d-audit-log-panel")) {
  customElements.define("ultimate-3d-audit-log-panel", Ultimate3DAuditLogPanelV3);
}
