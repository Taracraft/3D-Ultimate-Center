import "./v6-context-menu.js";
import { errorMessage } from "./ha-api-transport.js";
import type { MakerWorldDesign } from "./makerworld-api.js";
import { openMakerWorldDetailV6 } from "./makerworld-detail-dialog-v6.js";
import { addMakerWorldTerms, removeMakerWorldTerm } from "./makerworld-search-filters.js";
import { MakerWorldV6Adapter2 } from "./makerworld-v6-adapter2.js";
import type { V6ContextMenu, V6ContextMenuItem } from "./v6-context-menu.js";

type SortMode = "relevance" | "name" | "downloads" | "likes";
const PAGE_SIZE = 48;

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function uniqueTags(item: MakerWorldDesign): string[] {
  const result: string[] = [];
  for (const raw of Array.isArray(item.tags) ? item.tags : []) {
    const tag = String(raw || "").trim();
    if (!tag || result.some((entry) => entry.localeCompare(tag, "de", { sensitivity: "base" }) === 0)) continue;
    result.push(tag);
  }
  return result.slice(0, 8);
}

export class Ultimate3DMakerWorldWorkspaceCoreV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #api = new MakerWorldV6Adapter2();
  preferredTarget: "studio" | "slicer" = "slicer";
  #items: MakerWorldDesign[] = [];
  #terms: string[] = [];
  #draftQuery = "";
  #sort: SortMode = "relevance";
  #loading = false;
  #loadingMore = false;
  #error = "";
  #offset = 0;
  #hasMore = false;
  #knownCount = 0;
  #totalCount: number | null = null;

  connectedCallback(): void { void this.#load(false); }

  async #load(append: boolean): Promise<void> {
    if (this.#loading || this.#loadingMore) return;
    if (append && !this.#hasMore) return;
    if (append) this.#loadingMore = true; else this.#loading = true;
    this.#render();
    try {
      const offset = append ? this.#offset : 0;
      const result = await this.#api.browse(this.#terms, "Trending", offset, PAGE_SIZE);
      const merged = append ? [...this.#items, ...result.items] : result.items;
      const unique = new Map<string, MakerWorldDesign>();
      for (const item of merged) unique.set(item.id, item);
      this.#items = [...unique.values()];
      this.#offset = result.offset + result.items.length;
      this.#hasMore = Boolean(result.has_more);
      this.#knownCount = Number.isFinite(result.known_count) ? Number(result.known_count) : this.#items.length;
      this.#totalCount = Number.isFinite(result.total_count) ? Number(result.total_count) : null;
      this.#error = "";
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#loading = false;
      this.#loadingMore = false;
      this.#render();
    }
  }

  #restartSearch(): void {
    this.#offset = 0;
    this.#hasMore = false;
    this.#items = [];
    void this.#load(false);
  }

  #addTerms(value: string): void {
    const next = addMakerWorldTerms(this.#terms, value);
    this.#draftQuery = "";
    const changed = next.length !== this.#terms.length
      || next.some((term, index) => term !== this.#terms[index]);
    if (!changed) {
      this.#render();
      return;
    }
    this.#terms = next;
    this.#restartSearch();
  }

  #removeTerm(value: string): void {
    const next = removeMakerWorldTerm(this.#terms, value);
    if (next.length === this.#terms.length) return;
    this.#terms = next;
    this.#restartSearch();
  }

  #clearTerms(): void {
    if (!this.#terms.length) return;
    this.#terms = [];
    this.#draftQuery = "";
    this.#restartSearch();
  }

  #sorted(): MakerWorldDesign[] {
    const items = [...this.#items];
    if (this.#sort === "name") items.sort((a, b) => a.title.localeCompare(b.title, "de"));
    if (this.#sort === "downloads") items.sort((a, b) => b.stats.downloads - a.stats.downloads);
    if (this.#sort === "likes") items.sort((a, b) => b.stats.likes - a.stats.likes);
    return items;
  }

  #details(item: MakerWorldDesign): void {
    void openMakerWorldDetailV6(this, item.id, this.#api, (tag) => this.#addTerms(tag));
  }

  #context(event: MouseEvent, item: MakerWorldDesign): void {
    event.preventDefault();
    const menu: V6ContextMenuItem[] = [
      { label: "Details und Druckprofil", action: () => this.#details(item) },
      { label: this.preferredTarget === "studio" ? "Für CAD-Studio auswählen" : "Für Slicer auswählen", action: () => this.#details(item) },
      { label: "Ersteller als Filter hinzufügen", action: () => this.#addTerms(item.creator), disabled: !item.creator },
      ...uniqueTags(item).map((tag): V6ContextMenuItem => ({ label: `Filter hinzufügen: ${tag}`, action: () => this.#addTerms(tag) })),
    ];
    this.#root.querySelector<V6ContextMenu>("v6-context-menu")?.openAt(event.clientX, event.clientY, menu);
  }

  #render(): void {
    const filters = this.#terms.length
      ? `<div class="filters" aria-label="Aktive MakerWorld-Suchfilter">${this.#terms.map((term) => `<span class="filter-chip"><span>${escapeHtml(term)}</span><button type="button" data-remove-filter="${escapeHtml(term)}" aria-label="Filter ${escapeHtml(term)} entfernen" title="Filter entfernen">×</button></span>`).join("")}<button type="button" class="clear-filters" id="clear-filters">Alle Filter entfernen</button></div>`
      : '<div class="filter-hint">Tags aus Modellkarten werden hier als kombinierbare Filter angeheftet.</div>';
    this.#root.innerHTML = `<style>
      :host{display:block;padding:14px;background:#08101a;color:#eef5ff;font:13px Segoe UI,sans-serif}*{box-sizing:border-box}.head{padding:14px;border:1px solid #26384f;border-radius:11px;background:#101b29}.tools{display:flex;gap:7px;flex-wrap:wrap}.tools input{flex:1;min-width:180px}input,select,button{min-height:38px;padding:8px;border:1px solid #31506e;border-radius:8px;background:#10263a;color:#fff}button{cursor:pointer}.filters{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:10px}.filter-chip{display:inline-flex;align-items:center;gap:7px;min-height:31px;padding:4px 5px 4px 10px;border:1px solid #3f789d;border-radius:999px;background:#12334b;color:#d7f3ff;font-weight:700}.filter-chip button{display:grid;place-items:center;min-width:22px;width:22px;min-height:22px;height:22px;padding:0;border:0;border-radius:50%;background:#26536f;color:#fff;font-size:17px;line-height:1}.filter-chip button:hover{background:#b74552}.clear-filters{min-height:31px;padding:5px 9px;border-color:#6f4650;background:#321d25;color:#ffdce1}.filter-hint{margin-top:9px;color:#8298ae;font-size:11px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:11px;margin-top:12px}.card{display:grid;grid-template-rows:auto minmax(0,1fr);overflow:hidden;border:1px solid #2a3c53;border-radius:10px;background:#101925}.card:hover{border-color:#42c8ff}.card img{width:100%;aspect-ratio:4/3;object-fit:cover}.body{display:flex;flex-direction:column;min-height:0;padding:10px}.body small{margin:5px 0;color:#8fa4ba}.tags{display:flex;gap:5px;flex-wrap:wrap;min-height:28px;margin:2px 0 9px}.tag{min-height:25px;padding:3px 7px;border-color:#355d7c;border-radius:999px;background:#122d43;color:#b9e8ff;font-size:10px;font-weight:700}.tag:hover{border-color:#5fd3ff;background:#19415d}.open{width:100%;margin-top:auto}.message{margin-top:12px;padding:11px;border:1px solid #704449;border-radius:8px}.footer{display:flex;justify-content:center;gap:10px;align-items:center;margin:14px 0 4px}.footer small{color:#8fa4ba}.footer button{min-width:180px}.footer button:disabled{opacity:.45;cursor:not-allowed}
    </style><section class="head"><h1>MakerWorld</h1><p>Echte Folgeseiten werden vom Server nachgeladen. Mehrere Suchbegriffe und Tags wirken gemeinsam als Filter.</p><div class="tools"><input id="query" placeholder="Suchbegriff oder Tag hinzufügen" value="${escapeHtml(this.#draftQuery)}"><button id="search">Filter hinzufügen</button><button id="refresh">Aktualisieren</button><select id="sort"><option value="relevance">Relevanz</option><option value="name">Name</option><option value="downloads">Downloads</option><option value="likes">Likes</option></select></div>${filters}</section><main id="content"></main><footer class="footer" id="footer"></footer><v6-context-menu></v6-context-menu>`;
    const query = this.#root.querySelector<HTMLInputElement>("#query");
    const sort = this.#root.querySelector<HTMLSelectElement>("#sort");
    if (sort) sort.value = this.#sort;
    query?.addEventListener("input", () => { this.#draftQuery = query.value; });
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => this.#restartSearch());
    this.#root.querySelector<HTMLButtonElement>("#search")?.addEventListener("click", () => this.#addTerms(query?.value || ""));
    query?.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      this.#addTerms(query.value);
    });
    this.#root.querySelectorAll<HTMLButtonElement>("[data-remove-filter]").forEach((button) => {
      button.addEventListener("click", () => this.#removeTerm(button.dataset.removeFilter || ""));
    });
    this.#root.querySelector<HTMLButtonElement>("#clear-filters")?.addEventListener("click", () => this.#clearTerms());
    sort?.addEventListener("change", () => { this.#sort = sort.value as SortMode; this.#renderCards(); });
    this.#renderCards();
  }

  #renderCards(): void {
    const content = this.#root.querySelector<HTMLElement>("#content");
    const footer = this.#root.querySelector<HTMLElement>("#footer");
    if (!content || !footer) return;
    if (this.#error && !this.#items.length) {
      content.className = "message";
      content.textContent = this.#error;
    } else if (this.#loading && !this.#items.length) {
      content.className = "message";
      content.textContent = "MakerWorld wird geladen …";
    } else {
      content.className = "grid";
      content.replaceChildren(...this.#sorted().map((item) => this.#card(item)));
    }
    const filterLabel = this.#terms.length ? ` · ${this.#terms.length} aktive Filter` : "";
    const countLabel = this.#totalCount !== null ? ` von ${this.#totalCount}` : this.#knownCount > this.#items.length ? ` · mindestens ${this.#knownCount} bekannt` : "";
    footer.innerHTML = `<small>${this.#items.length}${countLabel} Treffer geladen${filterLabel}${this.#hasMore ? " · weitere Treffer verfügbar" : ""}${this.#error ? ` · ${escapeHtml(this.#error)}` : ""}</small><button id="more" ${this.#hasMore && !this.#loadingMore ? "" : "disabled"}>${this.#loadingMore ? "Weitere Treffer werden geladen …" : this.#hasMore ? "Mehr laden" : "Keine weiteren Treffer"}</button>`;
    footer.querySelector<HTMLButtonElement>("#more")?.addEventListener("click", () => void this.#load(true));
  }

  #card(item: MakerWorldDesign): HTMLElement {
    const card = document.createElement("article");
    card.className = "card";
    if (item.thumbnail_url) {
      const image = document.createElement("img");
      image.src = item.thumbnail_url;
      image.alt = item.title;
      image.referrerPolicy = "no-referrer";
      card.append(image);
    }
    const body = document.createElement("div");
    body.className = "body";
    const title = document.createElement("strong");
    title.textContent = item.title;
    const meta = document.createElement("small");
    meta.textContent = `⇩ ${item.stats.downloads} · ♥ ${item.stats.likes}`;
    const tags = document.createElement("div");
    tags.className = "tags";
    for (const tag of uniqueTags(item)) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tag";
      button.textContent = tag;
      button.title = `Filter „${tag}“ hinzufügen`;
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        this.#addTerms(tag);
      });
      tags.append(button);
    }
    const open = document.createElement("button");
    open.type = "button";
    open.className = "open";
    open.textContent = "Details und Druckprofil";
    open.addEventListener("click", () => this.#details(item));
    body.append(title, meta, tags, open);
    card.append(body);
    card.addEventListener("contextmenu", (event) => this.#context(event, item));
    return card;
  }
}

if (!customElements.get("ultimate-3d-makerworld-workspace")) {
  customElements.define("ultimate-3d-makerworld-workspace", Ultimate3DMakerWorldWorkspaceCoreV2);
}
