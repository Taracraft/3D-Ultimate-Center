import "./makerworld-workspace.js";
import "./printer-storage-workspace.js";
import "./v6-action-dialog.js";
import { errorMessage } from "./ha-api-transport.js";
import {
  GalleryApi,
  type GalleryImportSummary,
  type GalleryItem,
  type GalleryLibrary,
  type GalleryTreeItem,
} from "./gallery-api.js";
import type { V6ActionDialog } from "./v6-action-dialog.js";
import {
  queueWorkspaceFile,
  type WorkspaceFileTarget,
} from "./workspace-file-handoff.js";

type GalleryTab = "library" | "storage" | "makerworld";
type ViewMode = "grid" | "list";
type SortMode = "name" | "newest" | "size";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function fileSize(value: unknown): string {
  const size = Number(value);
  if (!Number.isFinite(size) || size < 0) return "–";
  if (size < 1024) return `${size.toFixed(0)} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`;
  return `${(size / 1024 ** 3).toFixed(2)} GB`;
}

function dateLabel(value: unknown): string {
  const numeric = Number(value);
  const date = Number.isFinite(numeric)
    ? new Date(numeric > 10_000_000_000 ? numeric : numeric * 1000)
    : new Date(String(value ?? ""));
  return Number.isNaN(date.getTime()) ? "–" : date.toLocaleString("de-DE");
}

export class Ultimate3DGalleryWorkspaceV3 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #api = new GalleryApi();
  readonly #selected = new Set<string>();
  readonly #previewUrls = new Map<string, string>();
  #tab: GalleryTab = "library";
  #library: GalleryLibrary | null = null;
  #folder = "";
  #query = "";
  #sort: SortMode = "name";
  #view: ViewMode = "grid";
  #loading = false;
  #busy = false;
  #message = "";
  #error = "";
  #detail: GalleryItem | null = null;

  connectedCallback(): void {
    this.#render();
    void this.#load();
  }

  disconnectedCallback(): void {
    for (const url of this.#previewUrls.values()) URL.revokeObjectURL(url);
    this.#previewUrls.clear();
  }

  #dialog(): V6ActionDialog | null {
    return this.#root.querySelector<V6ActionDialog>("v6-action-dialog");
  }

  async #load(folder = this.#folder): Promise<void> {
    if (this.#busy) return;
    this.#loading = true;
    this.#error = "";
    this.#render();
    try {
      this.#library = await this.#api.list(
        folder,
        this.#query,
        Boolean(this.#query),
      );
      this.#folder = this.#library.folder;
      this.#selected.clear();
      for (const url of this.#previewUrls.values()) URL.revokeObjectURL(url);
      this.#previewUrls.clear();
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#loading = false;
      this.#render();
    }
  }

  #items(): GalleryItem[] {
    const items = [...(this.#library?.items ?? [])];
    items.sort((left, right) => {
      if (left.kind !== right.kind) return left.kind === "folder" ? -1 : 1;
      if (this.#sort === "newest") {
        return Number(right.modified ?? 0) - Number(left.modified ?? 0);
      }
      if (this.#sort === "size") {
        return Number(right.size_bytes ?? 0) - Number(left.size_bytes ?? 0);
      }
      return left.name.localeCompare(right.name, "de", { sensitivity: "base" });
    });
    return items;
  }

  #render(): void {
    if (!this.isConnected) return;
    this.#root.innerHTML = `<style>
      :host{display:block;min-height:calc(100vh - 88px);background:#08101a;color:#eef5ff}
      *{box-sizing:border-box}.tabs{display:flex;gap:8px;padding:11px 14px;border-bottom:1px solid #2a3d53;background:#0d1622}.tabs button,.button,button,select,input{border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff}.tabs button,button{min-height:38px;padding:8px 11px;cursor:pointer;font-weight:700}.tabs button.active,.primary{border-color:#42c8ff;background:#17638a}.danger{border-color:#8f3f4b!important;background:#3a171d!important;color:#ffd7dc!important}button:disabled{opacity:.42;cursor:not-allowed}.pane{padding:14px}.layout{display:grid;grid-template-columns:230px minmax(0,1fr);gap:12px}.sidebar{align-self:start;max-height:calc(100vh - 180px);overflow:auto;padding:9px;border:1px solid #26384f;border-radius:11px;background:#0e1824}.sidebar h3{margin:0 0 8px;color:#8ca2b8;font-size:11px;text-transform:uppercase}.tree{display:grid;gap:3px}.tree button{width:100%;min-height:34px;padding:6px 7px;border-color:transparent;background:transparent;text-align:left;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.tree button.active{border-color:#42c8ff;background:#173b58}.content{min-width:0}.head{display:flex;justify-content:space-between;gap:12px}.head h1{margin:0}.head p{margin:5px 0 0;color:#8fa4ba}.stats{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.stat{padding:6px 8px;border:1px solid #29425c;border-radius:999px;background:#0d1a28;color:#a5bdd3;font-size:11px}.toolbar,.bulk{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-top:10px;padding:8px;border:1px solid #26384f;border-radius:9px;background:#0d1723}.toolbar input{min-width:220px;flex:1;padding:9px}.toolbar select{min-height:38px;padding:8px}.bulk strong{margin-right:auto}.path{padding:9px 2px;color:#8097ad;font-size:12px;overflow-wrap:anywhere}.notice,.empty{margin-top:10px;padding:12px;border:1px solid #2a3c53;border-radius:10px;background:#111b29;color:#91a5bb}.notice.ok{border-color:#27734c;color:#8ff0b5}.notice.error{border-color:#8f3f4b;color:#ffd7dc}.items{display:grid;gap:10px}.items.grid{grid-template-columns:repeat(auto-fill,minmax(230px,1fr))}.card{position:relative;overflow:hidden;border:1px solid #2a3c53;border-radius:11px;background:#101925}.grid .card{display:grid;grid-template-rows:150px minmax(0,1fr) auto;min-height:300px}.list .card{display:grid;grid-template-columns:110px minmax(0,1fr) auto;align-items:center;min-height:92px}.card.selected{border-color:#45c5ff;box-shadow:inset 3px 0 #45c5ff}.preview{display:grid;place-items:center;overflow:hidden;background:linear-gradient(145deg,#09111a,#152334)}.list .preview{height:90px}.preview img{width:100%;height:100%;object-fit:contain}.icon{font-size:50px;color:#5f7891}.folder .icon{color:#e5bd63}.select{position:absolute;top:8px;left:8px;width:23px;height:23px;z-index:2}.body{min-width:0;padding:10px}.body strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.body small{display:block;margin-top:5px;color:#8399ae;line-height:1.45;overflow-wrap:anywhere}.card-actions{display:grid;grid-template-columns:1fr 1fr;gap:6px;padding:0 9px 9px}.list .card-actions{display:flex;padding:9px}.card-actions button{min-height:34px;padding:6px;font-size:11px}.modal-backdrop{position:fixed;inset:0;z-index:2147482000;display:grid;place-items:center;padding:18px;background:#000b;backdrop-filter:blur(5px)}.modal{width:min(1050px,calc(100vw - 36px));max-height:calc(100vh - 36px);overflow:auto;display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;padding:14px;border:1px solid #3e6b90;border-radius:14px;background:#0e1824}.stage{display:grid;place-items:center;min-height:430px;border:1px solid #263f58;border-radius:10px;background:#03070c}.stage img{max-width:96%;max-height:70vh;object-fit:contain}.modal-side{display:grid;align-content:start;gap:9px}.modal-side h2{margin:0;overflow-wrap:anywhere}.modal-side .actions{display:grid;gap:7px}.close{position:fixed;right:25px;top:22px;z-index:2147482100;width:38px;height:38px;padding:0;border-radius:50%;font-size:20px}@media(max-width:900px){.layout{grid-template-columns:1fr}.sidebar{max-height:170px}.modal{grid-template-columns:1fr}.stage{min-height:280px}}@media(max-width:620px){.tabs{overflow-x:auto}.head{display:block}.stats{justify-content:flex-start;margin-top:8px}.toolbar,.bulk{display:grid}.items.grid{grid-template-columns:1fr}.list .card{grid-template-columns:80px minmax(0,1fr)}.modal-backdrop{padding:7px}.modal{width:100%;max-height:100%;border-radius:9px}}
    </style><nav class="tabs"><button type="button" data-tab="library" class="${this.#tab === "library" ? "active" : ""}">Bibliothek</button><button type="button" data-tab="storage" class="${this.#tab === "storage" ? "active" : ""}">SD-Karte</button><button type="button" data-tab="makerworld" class="${this.#tab === "makerworld" ? "active" : ""}">MakerWorld</button></nav><main class="pane" id="pane"></main><v6-action-dialog></v6-action-dialog>`;

    this.#root.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        this.#tab = button.dataset.tab as GalleryTab;
        this.#detail = null;
        this.#render();
      });
    });
    this.#renderPane();
  }

  #renderPane(): void {
    const pane = this.#root.querySelector<HTMLElement>("#pane");
    if (!pane) return;
    if (this.#tab === "storage") {
      pane.replaceChildren(document.createElement("ultimate-3d-printer-storage-workspace"));
      return;
    }
    if (this.#tab === "makerworld") {
      pane.replaceChildren(document.createElement("ultimate-3d-makerworld-workspace"));
      return;
    }
    this.#renderLibrary(pane);
  }

  #renderLibrary(pane: HTMLElement): void {
    const library = this.#library;
    const items = this.#items();
    pane.innerHTML = `<section class="layout"><aside class="sidebar"><h3>Ordner</h3><div class="tree">${(library?.tree ?? []).map((folder) => `<button type="button" data-folder="${esc(folder.path)}" class="${folder.path === this.#folder ? "active" : ""}" style="padding-left:${7 + folder.depth * 12}px">📁 ${esc(folder.name)}</button>`).join("")}</div></aside><section class="content"><header class="head"><div><h1>Galerie</h1><p>Lokale Modellbibliothek mit nativer V6-Dateiverwaltung.</p></div><div class="stats"><span class="stat">${library?.stats.files ?? 0} Modelle</span><span class="stat">${library?.stats.folders ?? 0} Ordner</span><span class="stat">${fileSize(library?.stats.bytes ?? 0)}</span></div></header><div class="toolbar"><input id="search" type="search" placeholder="Modelle und Ordner durchsuchen …" value="${esc(this.#query)}"><button id="search-button" type="button">Suchen</button><select id="sort"><option value="name" ${this.#sort === "name" ? "selected" : ""}>Name A–Z</option><option value="newest" ${this.#sort === "newest" ? "selected" : ""}>Neueste zuerst</option><option value="size" ${this.#sort === "size" ? "selected" : ""}>Größte zuerst</option></select><button id="new-folder" type="button">Neuer Ordner</button><button class="primary" id="upload" type="button">Hochladen</button><button id="export" type="button">Export</button><button id="import" type="button">Import</button><button type="button" data-view="grid" class="${this.#view === "grid" ? "active" : ""}">Raster</button><button type="button" data-view="list" class="${this.#view === "list" ? "active" : ""}">Liste</button></div><div class="bulk"><strong>${this.#selected.size} ausgewählt</strong><button id="select-all" type="button" ${items.length ? "" : "disabled"}>Alle auswählen</button><button id="clear" type="button" ${this.#selected.size ? "" : "disabled"}>Auswahl aufheben</button><button id="copy-selected" type="button" ${this.#selected.size ? "" : "disabled"}>Kopieren</button><button id="move-selected" type="button" ${this.#selected.size ? "" : "disabled"}>Verschieben</button><button class="danger" id="delete-selected" type="button" ${this.#selected.size ? "" : "disabled"}>Löschen</button></div><div class="path">${this.#folder ? `Hauptordner / ${esc(this.#folder)}` : "Hauptordner"}</div>${this.#message ? `<div class="notice ok">${esc(this.#message)}</div>` : ""}${this.#error ? `<div class="notice error">${esc(this.#error)}</div>` : ""}${this.#loading ? '<div class="empty">Galerie wird geladen …</div>' : items.length ? `<section class="items ${this.#view}" id="items"></section>` : '<div class="empty">Keine passenden Dateien oder Ordner vorhanden.</div>'}</section></section><input id="upload-input" type="file" accept=".3mf,.stl,.obj" multiple hidden><input id="import-input" type="file" accept=".zip,application/zip" hidden>`;

    const host = pane.querySelector<HTMLElement>("#items");
    if (host) host.replaceChildren(...items.map((item) => this.#card(item)));
    this.#bindLibrary(pane, items);
    if (this.#detail) this.#renderDetail();
  }

  #card(item: GalleryItem): HTMLElement {
    const card = document.createElement("article");
    card.className = `card ${item.kind === "folder" ? "folder" : ""} ${this.#selected.has(item.path) ? "selected" : ""}`;
    card.dataset.path = item.path;
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "select";
    checkbox.checked = this.#selected.has(item.path);
    checkbox.addEventListener("change", () => {
      checkbox.checked ? this.#selected.add(item.path) : this.#selected.delete(item.path);
      this.#render();
    });
    const preview = document.createElement("div");
    preview.className = "preview";
    const icon = document.createElement("span");
    icon.className = "icon";
    icon.textContent = item.kind === "folder" ? "📁" : "◇";
    preview.append(icon);
    if (item.kind === "model") void this.#loadPreview(item, preview);
    const body = document.createElement("div");
    body.className = "body";
    body.innerHTML = `<strong title="${esc(item.name)}">${esc(item.name)}</strong><small>${item.kind === "folder" ? "Ordner" : `${esc(String(item.format || "").toUpperCase())} · ${fileSize(item.size_bytes)}`}<br>${dateLabel(item.modified)}</small>`;
    const actions = document.createElement("div");
    actions.className = "card-actions";
    if (item.kind === "folder") {
      actions.append(this.#button("Öffnen", () => void this.#load(item.path)));
    } else {
      actions.append(
        this.#button("Vorschau", () => { this.#detail = item; this.#render(); }),
        this.#button("CAD-Studio", () => void this.#open(item, "studio")),
        this.#button("Slicer", () => void this.#open(item, "slicer")),
        this.#button("Download", () => void this.#download(item)),
      );
    }
    actions.append(
      this.#button("Umbenennen", () => void this.#rename(item)),
      this.#button("Kopieren", () => void this.#transfer(item, "copy")),
      this.#button("Verschieben", () => void this.#transfer(item, "move")),
      this.#button("Löschen", () => void this.#remove(item), true),
    );
    card.append(checkbox, preview, body, actions);
    return card;
  }

  #button(label: string, action: () => void, danger = false): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (danger) button.classList.add("danger");
    button.addEventListener("click", action);
    return button;
  }

  #bindLibrary(pane: HTMLElement, items: readonly GalleryItem[]): void {
    pane.querySelectorAll<HTMLButtonElement>("[data-folder]").forEach((button) => button.addEventListener("click", () => void this.#load(button.dataset.folder || "")));
    pane.querySelector<HTMLInputElement>("#search")?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        this.#query = (event.currentTarget as HTMLInputElement).value.trim();
        void this.#load(this.#folder);
      }
    });
    pane.querySelector<HTMLButtonElement>("#search-button")?.addEventListener("click", () => {
      this.#query = pane.querySelector<HTMLInputElement>("#search")?.value.trim() || "";
      void this.#load(this.#folder);
    });
    pane.querySelector<HTMLSelectElement>("#sort")?.addEventListener("change", (event) => { this.#sort = (event.currentTarget as HTMLSelectElement).value as SortMode; this.#render(); });
    pane.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.addEventListener("click", () => { this.#view = button.dataset.view as ViewMode; this.#render(); }));
    pane.querySelector<HTMLButtonElement>("#new-folder")?.addEventListener("click", () => void this.#createFolder());
    pane.querySelector<HTMLButtonElement>("#upload")?.addEventListener("click", () => pane.querySelector<HTMLInputElement>("#upload-input")?.click());
    pane.querySelector<HTMLInputElement>("#upload-input")?.addEventListener("change", (event) => void this.#upload((event.currentTarget as HTMLInputElement).files));
    pane.querySelector<HTMLButtonElement>("#export")?.addEventListener("click", () => void this.#export());
    pane.querySelector<HTMLButtonElement>("#import")?.addEventListener("click", () => pane.querySelector<HTMLInputElement>("#import-input")?.click());
    pane.querySelector<HTMLInputElement>("#import-input")?.addEventListener("change", (event) => void this.#import((event.currentTarget as HTMLInputElement).files?.[0] ?? null));
    pane.querySelector<HTMLButtonElement>("#select-all")?.addEventListener("click", () => { for (const item of items) this.#selected.add(item.path); this.#render(); });
    pane.querySelector<HTMLButtonElement>("#clear")?.addEventListener("click", () => { this.#selected.clear(); this.#render(); });
    pane.querySelector<HTMLButtonElement>("#copy-selected")?.addEventListener("click", () => void this.#bulkTransfer("copy", items));
    pane.querySelector<HTMLButtonElement>("#move-selected")?.addEventListener("click", () => void this.#bulkTransfer("move", items));
    pane.querySelector<HTMLButtonElement>("#delete-selected")?.addEventListener("click", () => void this.#bulkRemove(items));
  }

  async #loadPreview(item: GalleryItem, host: HTMLElement): Promise<void> {
    const existing = this.#previewUrls.get(item.asset_id);
    if (existing) return this.#showPreview(host, existing, item.name);
    try {
      const blob = await this.#api.preview(item);
      if (!blob || !host.isConnected) return;
      const url = URL.createObjectURL(blob);
      this.#previewUrls.set(item.asset_id, url);
      this.#showPreview(host, url, item.name);
    } catch {}
  }

  #showPreview(host: HTMLElement, url: string, name: string): void {
    const image = document.createElement("img");
    image.src = url;
    image.alt = name;
    image.loading = "lazy";
    host.replaceChildren(image);
  }

  async #chooseFolder(title: string): Promise<string | null> {
    const tree = this.#library?.tree ?? [];
    return await this.#dialog()?.choose({
      title,
      message: "Zielordner in der Galerie auswählen.",
      confirmLabel: "Übernehmen",
      select: {
        label: "Zielordner",
        value: this.#folder,
        options: tree.map((folder) => ({
          value: folder.path,
          label: `${"  ".repeat(folder.depth)}${folder.name}`,
          description: folder.path || "Hauptordner",
        })),
      },
    }) ?? null;
  }

  async #createFolder(): Promise<void> {
    const name = await this.#dialog()?.requestText({
      title: "Neuen Galerieordner erstellen",
      message: this.#folder ? `Unterordner in ${this.#folder}` : "Ordner im Hauptverzeichnis",
      confirmLabel: "Ordner erstellen",
      input: { label: "Ordnername", placeholder: "Neuer Ordner" },
    });
    if (!name) return;
    await this.#run(async () => {
      await this.#api.createFolder(this.#folder, name);
      this.#message = `Ordner „${name}“ wurde erstellt.`;
    });
  }

  async #rename(item: GalleryItem): Promise<void> {
    const name = await this.#dialog()?.requestText({
      title: "Galerieeintrag umbenennen",
      message: item.path,
      confirmLabel: "Umbenennen",
      input: { label: "Neuer Name", value: item.name },
    });
    if (!name || name === item.name) return;
    await this.#run(async () => {
      await this.#api.rename(item.path, name);
      this.#message = `${item.name} wurde umbenannt.`;
    });
  }

  async #transfer(item: GalleryItem, action: "copy" | "move"): Promise<void> {
    const target = await this.#chooseFolder(action === "copy" ? "Eintrag kopieren" : "Eintrag verschieben");
    if (target === null) return;
    await this.#run(async () => {
      await this.#transferWithOverwrite(item, action, target);
      this.#message = `${item.name} wurde ${action === "copy" ? "kopiert" : "verschoben"}.`;
    });
  }

  async #transferWithOverwrite(item: GalleryItem, action: "copy" | "move", target: string): Promise<void> {
    try {
      if (action === "copy") await this.#api.copy(item.path, target, false);
      else await this.#api.move(item.path, target, false);
    } catch (error) {
      if (!errorMessage(error).toLowerCase().includes("exist")) throw error;
      const overwrite = await this.#dialog()?.confirm({
        title: "Vorhandenes Ziel ersetzen",
        message: `„${item.name}“ existiert im Zielordner bereits.`,
        detail: target || "Hauptordner",
        confirmLabel: "Ersetzen",
        danger: true,
      });
      if (!overwrite) return;
      if (action === "copy") await this.#api.copy(item.path, target, true);
      else await this.#api.move(item.path, target, true);
    }
  }

  async #remove(item: GalleryItem): Promise<void> {
    const confirmed = await this.#dialog()?.confirm({
      title: item.kind === "folder" ? "Galerieordner löschen" : "Modell löschen",
      message: "Diesen Eintrag dauerhaft aus der Galerie löschen?",
      detail: item.path,
      confirmLabel: "Dauerhaft löschen",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run(async () => {
      await this.#api.remove(item.path);
      this.#selected.delete(item.path);
      this.#message = `${item.name} wurde gelöscht.`;
    });
  }

  async #bulkTransfer(action: "copy" | "move", items: readonly GalleryItem[]): Promise<void> {
    const selected = items.filter((item) => this.#selected.has(item.path));
    if (!selected.length) return;
    const target = await this.#chooseFolder(action === "copy" ? "Auswahl kopieren" : "Auswahl verschieben");
    if (target === null) return;
    await this.#run(async () => {
      for (const item of selected) await this.#transferWithOverwrite(item, action, target);
      this.#message = `${selected.length} Einträge wurden ${action === "copy" ? "kopiert" : "verschoben"}.`;
    });
  }

  async #bulkRemove(items: readonly GalleryItem[]): Promise<void> {
    const selected = items.filter((item) => this.#selected.has(item.path));
    if (!selected.length) return;
    const confirmed = await this.#dialog()?.confirm({
      title: "Galerieauswahl löschen",
      message: `${selected.length} Einträge dauerhaft löschen?`,
      detail: selected.map((item) => item.path).join("\n"),
      confirmLabel: "Alle löschen",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run(async () => {
      for (const item of selected) await this.#api.remove(item.path);
      this.#message = `${selected.length} Einträge wurden gelöscht.`;
    });
  }

  async #upload(files: FileList | null): Promise<void> {
    const queue = files ? Array.from(files) : [];
    if (!queue.length) return;
    await this.#run(async () => {
      for (const file of queue) {
        try {
          await this.#api.upload(file, this.#folder, false);
        } catch (error) {
          if (!errorMessage(error).toLowerCase().includes("exist")) throw error;
          const overwrite = await this.#dialog()?.confirm({
            title: "Galeriedatei ersetzen",
            message: `„${file.name}“ existiert bereits.`,
            confirmLabel: "Ersetzen",
            danger: true,
          });
          if (overwrite) await this.#api.upload(file, this.#folder, true);
        }
      }
      this.#message = `${queue.length} Datei${queue.length === 1 ? "" : "en"} wurde${queue.length === 1 ? "" : "n"} hochgeladen.`;
    });
  }

  async #download(item: GalleryItem): Promise<void> {
    await this.#run(async () => {
      const file = await this.#api.download(item);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.#message = `${item.name} wurde heruntergeladen.`;
    }, false);
  }

  async #open(item: GalleryItem, target: WorkspaceFileTarget): Promise<void> {
    await this.#run(async () => {
      const file = target === "studio"
        ? await this.#api.downloadForCad(item)
        : await this.#api.download(item);
      queueWorkspaceFile(target, file);
      this.#detail = null;
      this.dispatchEvent(new CustomEvent(
        target === "studio" ? "gallery-open-studio" : "gallery-open-slicer",
        {
          bubbles: true,
          composed: true,
          detail: { source: "gallery", assetId: item.asset_id, fileName: file.name },
        },
      ));
    }, false);
  }

  async #export(): Promise<void> {
    await this.#run(async () => {
      const file = await this.#api.exportZip();
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.#message = "Galerie wurde exportiert.";
    }, false);
  }

  async #import(file: File | null): Promise<void> {
    if (!file) return;
    try {
      const summary: GalleryImportSummary = await this.#api.inspectImport(file);
      const confirmed = await this.#dialog()?.confirm({
        title: "Galerie-ZIP importieren",
        message: `${summary.files} Dateien und ${summary.folders} Ordner importieren?`,
        detail: summary.conflicts.length ? `${summary.conflicts.length} vorhandene Dateien werden ersetzt.` : fileSize(summary.bytes),
        confirmLabel: "Importieren",
        danger: summary.conflicts.length > 0,
      });
      if (!confirmed) return;
      await this.#run(async () => {
        await this.#api.importZip(file, summary.conflicts.length > 0);
        this.#message = "Galerie wurde erfolgreich importiert.";
      });
    } catch (error) {
      this.#error = errorMessage(error);
      this.#render();
    }
  }

  async #run(operation: () => Promise<void>, reload = true): Promise<void> {
    if (this.#busy) return;
    this.#busy = true;
    this.#message = "";
    this.#error = "";
    this.#render();
    try {
      await operation();
      if (reload) {
        this.#library = await this.#api.list(this.#folder, this.#query, Boolean(this.#query));
        this.#selected.clear();
      }
    } catch (error) {
      this.#error = errorMessage(error);
    } finally {
      this.#busy = false;
      this.#render();
    }
  }

  #renderDetail(): void {
    const item = this.#detail;
    if (!item) return;
    const existing = this.#previewUrls.get(item.asset_id);
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `<section class="modal"><div class="stage" id="detail-stage">${existing ? `<img src="${esc(existing)}" alt="${esc(item.name)}">` : '<span class="icon">◇</span>'}</div><aside class="modal-side"><h2>${esc(item.title)}</h2><small>${esc(item.path)}<br>${fileSize(item.size_bytes)} · ${dateLabel(item.modified)}</small><div class="actions" id="detail-actions"></div></aside></section>`;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "close";
    close.textContent = "×";
    const closeModal = (): void => { this.#detail = null; this.#render(); };
    close.addEventListener("click", closeModal);
    backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModal(); });
    const actions = backdrop.querySelector<HTMLElement>("#detail-actions")!;
    actions.append(
      this.#button("Im CAD-Studio öffnen", () => void this.#open(item, "studio")),
      this.#button("An Slicer übergeben", () => void this.#open(item, "slicer")),
      this.#button("Originaldatei herunterladen", () => void this.#download(item)),
      this.#button("Kopieren", () => void this.#transfer(item, "copy")),
      this.#button("Verschieben", () => void this.#transfer(item, "move")),
      this.#button("Löschen", () => void this.#remove(item), true),
    );
    this.#root.append(backdrop, close);
    if (!existing) void this.#loadPreview(item, backdrop.querySelector<HTMLElement>("#detail-stage")!);
  }
}

if (!customElements.get("ultimate-3d-gallery-workspace")) {
  customElements.define(
    "ultimate-3d-gallery-workspace",
    Ultimate3DGalleryWorkspaceV3,
  );
}