import { errorMessage } from "./ha-api-transport.js";
import type { MakerWorldDesign } from "./makerworld-api.js";
import { openMakerWorldDetailV6 } from "./makerworld-detail-dialog-v6.js";
import { MakerWorldV6Adapter2 } from "./makerworld-v6-adapter2.js";

type SortMode = "relevance" | "name-asc" | "name-desc" | "downloads" | "likes" | "newest";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

export class Ultimate3DMakerWorldWorkspace extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #api = new MakerWorldV6Adapter2();
  #items: MakerWorldDesign[] = [];
  #terms: string[] = [];
  #sort: SortMode = "relevance";
  #loading = false;
  #error = "";

  connectedCallback(): void { void this.#load(); }

  async #load(): Promise<void> {
    this.#loading = true;
    this.#error = "";
    this.#render();
    try {
      this.#items = (await this.#api.browse(this.#terms, "Trending", 0, 48)).items;
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#loading = false;
      this.#render();
    }
  }

  #add(raw: string): void {
    for (const value of raw.split(/[,;]+/).map((item) => item.trim()).filter(Boolean)) {
      if (!this.#terms.some((term) => term.localeCompare(value, "de", { sensitivity: "base" }) === 0)) this.#terms.push(value);
    }
    void this.#load();
  }

  #sorted(): MakerWorldDesign[] {
    const items = [...this.#items];
    if (this.#sort === "name-asc") items.sort((a, b) => a.title.localeCompare(b.title, "de"));
    if (this.#sort === "name-desc") items.sort((a, b) => b.title.localeCompare(a.title, "de"));
    if (this.#sort === "downloads") items.sort((a, b) => b.stats.downloads - a.stats.downloads);
    if (this.#sort === "likes") items.sort((a, b) => b.stats.likes - a.stats.likes);
    if (this.#sort === "newest") items.sort((a, b) => Date.parse(b.published_at || "") - Date.parse(a.published_at || ""));
    return items;
  }

  #render(): void {
    const items = this.#sorted();
    this.#root.innerHTML = `<style>
      :host{display:block;padding:14px;background:#08101a;color:#eef5ff;font:13px Inter,Segoe UI,sans-serif}*{box-sizing:border-box}.head{padding:16px;border:1px solid #26384f;border-radius:12px;background:#101b29}.search{display:grid;grid-template-columns:1fr auto 180px;gap:8px;margin-top:12px}input,select,button{padding:9px;border:1px solid #31506e;border-radius:8px;background:#10263a;color:#fff}button{cursor:pointer}.chips,.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.chip,.tag{border-radius:999px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:14px}.card{overflow:hidden;border:1px solid #2a3c53;border-radius:10px;background:#101925}.card img{width:100%;aspect-ratio:4/3;object-fit:cover}.body{padding:10px}.title{font-weight:800}.meta{margin-top:5px;color:#8fa4ba;font-size:11px}.error,.empty{margin-top:12px;padding:10px;border:1px solid #704449;border-radius:8px}.open{width:100%;margin-top:8px}@media(max-width:650px){.search{grid-template-columns:1fr}}
    </style><section class="head"><h1>MakerWorld</h1><p>Mehrere Suchbegriffe als anklickbare Filterchips.</p><form class="search"><input id="query" placeholder="Suchbegriff eingeben"><button>Hinzufügen</button><select id="sort"><option value="relevance">Relevanz</option><option value="name-asc">Name A–Z</option><option value="name-desc">Name Z–A</option><option value="downloads">Downloads</option><option value="likes">Likes</option><option value="newest">Neueste</option></select></form>${this.#terms.length ? `<div class="chips">${this.#terms.map((term, index) => `<button class="chip" data-remove="${index}">${esc(term)} ×</button>`).join("")}</div>` : ""}</section>${this.#error ? `<div class="error">${esc(this.#error)}</div>` : ""}${this.#loading ? '<div class="empty">Wird geladen …</div>' : `<div class="grid">${items.map((item) => `<article class="card">${item.thumbnail_url ? `<img src="${esc(item.thumbnail_url)}" alt="${esc(item.title)}" referrerpolicy="no-referrer">` : ""}<div class="body"><div class="title">${esc(item.title)}</div><div class="meta">⇩ ${item.stats.downloads} · ♥ ${item.stats.likes}</div><div class="tags">${item.tags.slice(0, 5).map((tag) => `<button class="tag" data-tag="${esc(tag)}">${esc(tag)}</button>`).join("")}</div><button class="open" data-open="${item.id}">Details und Druckprofil</button></div></article>`).join("")}</div>`}`;
    this.#root.querySelector<HTMLFormElement>("form")?.addEventListener("submit", (event) => { event.preventDefault(); this.#add(this.#root.querySelector<HTMLInputElement>("#query")?.value || ""); });
    const sort = this.#root.querySelector<HTMLSelectElement>("#sort");
    if (sort) { sort.value = this.#sort; sort.addEventListener("change", () => { this.#sort = sort.value as SortMode; this.#render(); }); }
    this.#root.querySelectorAll<HTMLButtonElement>("[data-remove]").forEach((button) => button.addEventListener("click", () => { this.#terms.splice(Number(button.dataset.remove), 1); void this.#load(); }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-tag]").forEach((button) => button.addEventListener("click", () => this.#add(button.dataset.tag || "")));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-open]").forEach((button) => button.addEventListener("click", () => void openMakerWorldDetailV6(this, button.dataset.open || "", this.#api, (tag) => this.#add(tag))));
  }
}

if (!customElements.get("ultimate-3d-makerworld-workspace")) customElements.define("ultimate-3d-makerworld-workspace", Ultimate3DMakerWorldWorkspace);