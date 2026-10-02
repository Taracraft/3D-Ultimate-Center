import "./v6-action-dialog.js";
import "./v6-context-menu.js";
import "./gallery-model-detail-dialog.js";
import { GalleryApi, type GalleryItem, type GalleryLibrary } from "./gallery-api.js";
import { errorMessage } from "./ha-api-transport.js";
import { STORAGE_WORKSPACE_STYLE } from "./storage-workspace-style.js";
import type { V6ActionDialog } from "./v6-action-dialog.js";
import type { V6ContextMenu, V6ContextMenuItem } from "./v6-context-menu.js";
import type { GalleryModelDetailDialog } from "./gallery-model-detail-dialog.js";

const RECENT_KEY = "ultimate-3d-studio-v6:gallery-recent-opened";
const LIBRARY_CACHE_KEY = "ultimate-3d-studio-v6:gallery-library-cache-v1";

type RecentOpened = Readonly<{
  path: string;
  name: string;
  title: string;
  format: string;
  size_bytes: number;
  opened_at: string;
}>;

type CachedLibrary = Readonly<{
  version: 1;
  savedAt: string;
  library: GalleryLibrary;
}>;

function loadCachedLibrary(): GalleryLibrary | null {
  try {
    const raw = localStorage.getItem(LIBRARY_CACHE_KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw) as Partial<CachedLibrary>;
    const library = cached.library as Partial<GalleryLibrary> | undefined;
    if (cached.version !== 1 || !library || !Array.isArray(library.items) || !Array.isArray(library.tree)) return null;
    if (String(library.folder || "") || String((library as { parent?: string }).parent || "")) return null;
    return library as GalleryLibrary;
  } catch {
    return null;
  }
}

function saveCachedLibrary(library: GalleryLibrary): void {
  if (library.folder) return;
  try {
    localStorage.setItem(LIBRARY_CACHE_KEY, JSON.stringify({
      version: 1,
      savedAt: new Date().toISOString(),
      library,
    } satisfies CachedLibrary));
  } catch {}
}

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function sizeLabel(value: number | undefined): string {
  const size = Number(value || 0);
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 ** 2).toFixed(1)} MB`;
}

function loadRecent(): RecentOpened | null {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<RecentOpened>;
    if (!value.path || !value.name) return null;
    return {
      path: String(value.path),
      name: String(value.name),
      title: String(value.title || value.name),
      format: String(value.format || ""),
      size_bytes: Number(value.size_bytes || 0),
      opened_at: String(value.opened_at || ""),
    };
  } catch {
    return null;
  }
}

export class Ultimate3DGalleryLibraryPane extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #api = new GalleryApi();
  #library: GalleryLibrary | null = null;
  #folder = "";
  #query = "";
  #timer: number | null = null;
  #signature = "";
  #busy = false;
  readonly #previewItems = new WeakMap<Element, GalleryItem>();
  #previewObserver: IntersectionObserver | null = null;

  connectedCallback(): void {
    if (!this.#root.childElementCount) this.#mount();
    this.#ensurePreviewObserver();
    this.#restoreCachedLibrary();
    void this.#refresh(true);
    if (this.#timer === null) this.#timer = window.setInterval(() => void this.#refresh(true), 10000);
  }

  disconnectedCallback(): void {
    if (this.#timer !== null) window.clearInterval(this.#timer);
    this.#timer = null;
    this.#previewObserver?.disconnect();
    this.#previewObserver = null;
  }

  #dialog(): V6ActionDialog | null { return this.#root.querySelector<V6ActionDialog>("v6-action-dialog"); }
  #menu(): V6ContextMenu | null { return this.#root.querySelector<V6ContextMenu>("v6-context-menu"); }
  #detailDialog(): GalleryModelDetailDialog | null { return this.#root.querySelector<GalleryModelDetailDialog>("gallery-model-detail-dialog"); }

  #ensurePreviewObserver(): void {
    if (this.#previewObserver || !("IntersectionObserver" in globalThis)) return;
    this.#previewObserver = new IntersectionObserver((entries, observer) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        const item = this.#previewItems.get(entry.target);
        if (item) void this.#loadPreview(item, entry.target as HTMLElement);
      }
    }, { rootMargin: "320px 0px" });
  }

  #restoreCachedLibrary(): void {
    if (this.#library || this.#folder || this.#query) return;
    const cached = loadCachedLibrary();
    if (!cached) return;
    this.#library = cached;
    this.#folder = cached.folder;
    this.#signature = JSON.stringify(cached);
    this.#renderData();
    this.#setLive("Galerie sofort aus Cache · Aktualisierung läuft");
  }

  #mount(): void {
    this.#root.innerHTML = `<style>${STORAGE_WORKSPACE_STYLE}.search{flex:1;min-width:190px;padding:9px;border:1px solid #31506e;border-radius:8px;background:#09131f;color:#fff}.live{color:#8ff0b5;font-size:11px}.recent{display:none;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;margin:0 0 12px;padding:11px 13px;border:1px solid #31506e;border-radius:9px;background:linear-gradient(180deg,#102334,#0a1723)}.recent.visible{display:grid}.recent strong,.recent small{display:block}.recent small{margin-top:3px;color:#849bb0}.recent button{white-space:nowrap}.preview.clickable{cursor:pointer}.preview.clickable:hover{outline:1px solid #45caff;box-shadow:0 0 0 2px #45caff22}.upload-status{display:none;margin:0 0 12px;padding:12px 13px;border:1px solid #31506e;border-radius:9px;background:#091722}.upload-status.visible{display:block}.upload-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:8px}.upload-head strong{color:#e8f4ff}.upload-head span{color:#8ff0b5;font-weight:800}.upload-track{height:10px;overflow:hidden;border:1px solid #284765;border-radius:999px;background:#06101a}.upload-bar{height:100%;width:0;background:linear-gradient(90deg,#1595d3,#39d884);transition:width .2s ease}.upload-current{display:block;margin-top:7px;color:#a8bfd2}.upload-success{margin:8px 0 0;padding-left:20px;color:#79ef9f}.upload-success li{margin:3px 0}.upload-status.error{border-color:#9a3f4a}.upload-status.error .upload-head span,.upload-status.error .upload-current{color:#ff9ca7}</style><section class="page"><header class="head"><div><h1>Galerie</h1><p>Lokale V6-Modellbibliothek mit automatischer Aktualisierung.</p></div><div class="actions"><button id="refresh">Aktualisieren</button><span class="live" id="live">Live alle 10 s</span></div></header><div id="notice"></div><section class="upload-status" id="upload-status" aria-live="polite"><div class="upload-head"><strong id="upload-title">Dateien werden hochgeladen</strong><span id="upload-percent">0 %</span></div><div class="upload-track"><div class="upload-bar" id="upload-bar"></div></div><small class="upload-current" id="upload-current"></small><ul class="upload-success" id="upload-success"></ul></section><div class="layout"><aside class="sidebar"><strong>Ordner</strong><div class="tree" id="tree"></div></aside><main><div class="toolbar"><input class="search" id="search" type="search" placeholder="Galerie durchsuchen"><button id="search-button">Suchen</button><button class="primary" id="upload">Hochladen</button><button id="new-folder">Neuer Ordner</button><button id="up">Eine Ebene hoch</button></div><div class="path" id="path">Hauptordner</div><section class="recent" id="recent"></section><section class="items" id="items"></section></main></div><input id="upload-input" type="file" accept=".3mf,.stl,.obj" multiple hidden><v6-action-dialog></v6-action-dialog><v6-context-menu></v6-context-menu><gallery-model-detail-dialog></gallery-model-detail-dialog></section>`;
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refresh(false));
    this.#root.querySelector<HTMLButtonElement>("#upload")?.addEventListener("click", () => this.#root.querySelector<HTMLInputElement>("#upload-input")?.click());
    this.#root.querySelector<HTMLInputElement>("#upload-input")?.addEventListener("change", (event) => void this.#upload((event.currentTarget as HTMLInputElement).files));
    this.#root.querySelector<HTMLButtonElement>("#new-folder")?.addEventListener("click", () => void this.#createFolder());
    this.#root.querySelector<HTMLButtonElement>("#up")?.addEventListener("click", () => void this.#openFolder(this.#library?.parent || ""));
    this.#root.querySelector<HTMLButtonElement>("#search-button")?.addEventListener("click", () => this.#search());
    this.#root.querySelector<HTMLInputElement>("#search")?.addEventListener("keydown", (event) => { if (event.key === "Enter") this.#search(); });
    this.#renderRecent();
  }

  #search(): void {
    this.#query = this.#root.querySelector<HTMLInputElement>("#search")?.value.trim() || "";
    void this.#refresh(false);
  }

  async #refresh(silent: boolean): Promise<void> {
    if (this.#busy) return;
    try {
      const library = await this.#api.list(this.#folder, this.#query, Boolean(this.#query));
      const signature = JSON.stringify(library);
      this.#library = library;
      this.#folder = library.folder;
      if (!this.#query && !library.folder) saveCachedLibrary(library);
      if (signature !== this.#signature) {
        this.#signature = signature;
        this.#renderData();
      }
      this.#renderRecent();
      this.#setLive(`Aktualisiert ${new Date().toLocaleTimeString("de-DE")}`);
      if (!silent) this.#showMessage("Galerie wurde aktualisiert.");
    } catch (error) {
      this.#showError(errorMessage(error));
    }
  }

  async #openFolder(folder: string): Promise<void> {
    this.#folder = folder;
    this.#query = "";
    const input = this.#root.querySelector<HTMLInputElement>("#search");
    if (input) input.value = "";
    await this.#refresh(true);
  }

  #renderRecent(): void {
    const host = this.#root.querySelector<HTMLElement>("#recent");
    if (!host) return;
    const recent = loadRecent();
    if (!recent) {
      host.classList.remove("visible");
      host.replaceChildren();
      return;
    }
    const matching = this.#library?.items.find((item) => item.kind === "model" && item.path === recent.path) ?? null;
    host.classList.add("visible");
    host.innerHTML = `<span><strong>Zuletzt geöffnet: ${esc(recent.title)}</strong><small>${esc(recent.format.toUpperCase())} · ${sizeLabel(recent.size_bytes)}${recent.opened_at ? ` · ${esc(new Date(recent.opened_at).toLocaleString("de-DE"))}` : ""}</small></span><button type="button" ${matching ? "" : "disabled"}>Details</button>`;
    if (matching) host.querySelector<HTMLButtonElement>("button")?.addEventListener("click", () => void this.#showDetails(matching));
  }

  #renderData(): void {
    this.#previewObserver?.disconnect();
    this.#ensurePreviewObserver();
    const tree = this.#root.querySelector<HTMLElement>("#tree");
    const items = this.#root.querySelector<HTMLElement>("#items");
    const path = this.#root.querySelector<HTMLElement>("#path");
    const up = this.#root.querySelector<HTMLButtonElement>("#up");
    if (!tree || !items || !path || !up) return;
    tree.innerHTML = (this.#library?.tree || []).map((folder) => `<button data-folder="${esc(folder.path)}" class="${folder.path === this.#folder ? "active" : ""}" style="padding-left:${7 + folder.depth * 12}px">📁 ${esc(folder.name)}</button>`).join("");
    tree.querySelectorAll<HTMLButtonElement>("[data-folder]").forEach((button) => button.addEventListener("click", () => void this.#openFolder(button.dataset.folder || "")));
    path.textContent = this.#folder ? `Hauptordner / ${this.#folder}` : "Hauptordner";
    up.disabled = !this.#folder;
    const entries = this.#library?.items || [];
    items.replaceChildren(...entries.map((item) => this.#card(item)));
    if (!entries.length) items.innerHTML = '<div class="empty">Keine passenden Dateien oder Ordner vorhanden.</div>';
    this.#renderRecent();
  }

  #card(item: GalleryItem): HTMLElement {
    const card = document.createElement("article");
    card.className = "card";
    const preview = document.createElement("div");
    preview.className = `preview${item.kind === "model" ? " clickable" : ""}`;
    preview.innerHTML = `<span class="icon">${item.kind === "folder" ? "📁" : "◇"}</span>`;
    if (item.kind === "model") {
      this.#observePreview(item, preview);
      preview.title = "Details öffnen";
      preview.addEventListener("click", () => void this.#showDetails(item));
    }
    const body = document.createElement("div");
    body.className = "body";
    body.innerHTML = `<strong title="${esc(item.name)}">${esc(item.name)}</strong><small>${item.kind === "folder" ? "Ordner" : `${esc(String(item.format || "").toUpperCase())} · ${sizeLabel(item.size_bytes)}`}</small>`;
    const actions = document.createElement("div");
    actions.className = "card-actions";
    if (item.kind === "folder") {
      actions.append(this.#button("Öffnen", () => void this.#openFolder(item.path)));
    } else {
      actions.append(
        this.#button("Details", () => void this.#showDetails(item)),
        this.#button("Download", () => void this.#download(item)),
        this.#button("3D-Studio", () => void this.#openIn3DStudio(item)),
      );
    }
    actions.append(
      this.#button("Umbenennen", () => void this.#rename(item)),
      this.#button("Kopieren", () => void this.#transfer(item, "copy")),
      this.#button("Verschieben", () => void this.#transfer(item, "move")),
      this.#button("Löschen", () => void this.#remove(item), true),
    );
    card.append(preview, body, actions);
    card.addEventListener("contextmenu", (event) => this.#context(event, item));
    return card;
  }

  #observePreview(item: GalleryItem, host: HTMLElement): void {
    this.#previewItems.set(host, item);
    if (this.#previewObserver) this.#previewObserver.observe(host);
    else void this.#loadPreview(item, host);
  }

  async #loadPreview(item: GalleryItem, host: HTMLElement): Promise<void> {
    try {
      const blob = await this.#api.preview(item);
      if (!blob || !host.isConnected) return;
      const url = URL.createObjectURL(blob);
      const image = document.createElement("img");
      image.src = url;
      image.alt = item.name;
      const release = (): void => URL.revokeObjectURL(url);
      image.onload = release;
      image.onerror = release;
      host.replaceChildren(image);
    } catch {}
  }

  async #showDetails(item: GalleryItem): Promise<void> {
    if (item.kind !== "model") return;
    try {
      const preview = await this.#api.preview(item);
      this.#detailDialog()?.open(item, preview, {
        download: () => void this.#download(item),
        openStudio: () => void this.#openIn3DStudio(item),
      });
    } catch (error) {
      this.#showError(errorMessage(error));
    }
  }

  #button(label: string, action: () => void, danger = false): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (danger) button.classList.add("danger");
    button.addEventListener("click", action);
    return button;
  }

  #context(event: MouseEvent, item: GalleryItem): void {
    event.preventDefault();
    const menu: V6ContextMenuItem[] = item.kind === "folder" ? [
      { label: "Ordner öffnen", action: () => this.#openFolder(item.path) },
      { label: "Umbenennen", action: () => this.#rename(item) },
      { label: "Kopieren", action: () => this.#transfer(item, "copy") },
      { label: "Verschieben", action: () => this.#transfer(item, "move") },
      { label: "Löschen", action: () => this.#remove(item), danger: true },
    ] : [
      { label: "Details", action: () => this.#showDetails(item) },
      { label: "Im 3D-Studio öffnen", action: () => this.#openIn3DStudio(item) },
      { label: "Herunterladen", action: () => this.#download(item) },
      { label: "Umbenennen", action: () => this.#rename(item) },
      { label: "Kopieren", action: () => this.#transfer(item, "copy") },
      { label: "Verschieben", action: () => this.#transfer(item, "move") },
      { label: "Löschen", action: () => this.#remove(item), danger: true },
    ];
    this.#menu()?.openAt(event.clientX, event.clientY, menu);
  }

  async #chooseFolder(title: string): Promise<string | null> {
    return await this.#dialog()?.choose({ title, message: "Zielordner auswählen.", confirmLabel: "Übernehmen", select: { label: "Zielordner", value: this.#folder, options: (this.#library?.tree || []).map((folder) => ({ value: folder.path, label: `${"  ".repeat(folder.depth)}${folder.name}`, description: folder.path || "Hauptordner" })) } }) ?? null;
  }

  async #createFolder(): Promise<void> {
    const name = await this.#dialog()?.requestText({ title: "Neuen Galerieordner erstellen", message: this.#folder || "Hauptordner", confirmLabel: "Erstellen", input: { label: "Ordnername" } });
    if (name) await this.#run(() => this.#api.createFolder(this.#folder, name).then(() => undefined));
  }

  async #rename(item: GalleryItem): Promise<void> {
    const name = await this.#dialog()?.requestText({ title: "Galerieeintrag umbenennen", message: item.path, confirmLabel: "Umbenennen", input: { label: "Neuer Name", value: item.name } });
    if (name && name !== item.name) await this.#run(() => this.#api.rename(item.path, name).then(() => undefined));
  }

  async #transfer(item: GalleryItem, action: "copy" | "move"): Promise<void> {
    const target = await this.#chooseFolder(action === "copy" ? "Eintrag kopieren" : "Eintrag verschieben");
    if (target === null) return;
    await this.#run(() => (action === "copy" ? this.#api.copy(item.path, target, false) : this.#api.move(item.path, target, false)).then(() => undefined));
  }

  async #remove(item: GalleryItem): Promise<void> {
    const confirmed = await this.#dialog()?.confirm({ title: "Galerieeintrag löschen", message: "Diesen Eintrag dauerhaft löschen?", detail: item.path, confirmLabel: "Löschen", danger: true });
    if (confirmed) await this.#run(() => this.#api.remove(item.path).then(() => undefined));
  }

  async #download(item: GalleryItem): Promise<void> {
    try {
      const file = await this.#api.download(item);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { this.#showError(errorMessage(error)); }
  }

  #rememberRecent(item: GalleryItem): void {
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify({
        path: item.path,
        name: item.name,
        title: item.title || item.name,
        format: String(item.format || ""),
        size_bytes: Number(item.size_bytes || 0),
        opened_at: new Date().toISOString(),
      } satisfies RecentOpened));
    } catch {}
    this.#renderRecent();
  }

  async #openIn3DStudio(item: GalleryItem): Promise<void> {
    try {
      this.#rememberRecent(item);
      if (String(item.format || "").toLowerCase() === "3mf") {
        this.dispatchEvent(new CustomEvent("gallery-open-studio", {
          detail: {
            assetId: item.asset_id,
            fileName: item.file_name || item.name,
            replaceWorkspace: true,
          },
          bubbles: true,
          composed: true,
        }));
        return;
      }
      const file = await this.#api.download(item);
      this.dispatchEvent(new CustomEvent("gallery-open-studio", {
        detail: { file, replaceWorkspace: true },
        bubbles: true,
        composed: true,
      }));
    } catch (error) {
      this.#showError(errorMessage(error));
    }
  }

  #renderUploadProgress(title: string, current: string, completedBytes: number, totalBytes: number, successful: readonly string[], error = false): void {
    const host = this.#root.querySelector<HTMLElement>("#upload-status");
    const titleNode = this.#root.querySelector<HTMLElement>("#upload-title");
    const percentNode = this.#root.querySelector<HTMLElement>("#upload-percent");
    const bar = this.#root.querySelector<HTMLElement>("#upload-bar");
    const currentNode = this.#root.querySelector<HTMLElement>("#upload-current");
    const successNode = this.#root.querySelector<HTMLElement>("#upload-success");
    if (!host || !titleNode || !percentNode || !bar || !currentNode || !successNode) return;
    const percent = totalBytes > 0 ? Math.max(0, Math.min(100, Math.round(completedBytes / totalBytes * 100))) : 100;
    host.classList.add("visible");
    host.classList.toggle("error", error);
    titleNode.textContent = title;
    percentNode.textContent = `${percent} %`;
    bar.style.width = `${percent}%`;
    currentNode.textContent = current;
    successNode.innerHTML = successful.map((name) => `<li>✓ ${esc(name)} erfolgreich hochgeladen</li>`).join("");
  }

  async #upload(files: FileList | null): Promise<void> {
    const queue = files ? Array.from(files) : [];
    if (!queue.length || this.#busy) return;
    this.#busy = true;
    const input = this.#root.querySelector<HTMLInputElement>("#upload-input");
    const totalBytes = queue.reduce((sum, file) => sum + Math.max(0, file.size), 0);
    let completedBytes = 0;
    const successful: string[] = [];
    this.#renderUploadProgress("Upload wird vorbereitet …", `${queue.length} Datei(en)`, 0, totalBytes, successful);
    try {
      for (let index = 0; index < queue.length; index += 1) {
        const file = queue[index]!;
        this.#renderUploadProgress(
          `Datei ${index + 1} von ${queue.length} wird hochgeladen`,
          `${file.name} · ${sizeLabel(file.size)}`,
          completedBytes,
          totalBytes,
          successful,
        );
        await this.#api.upload(file, this.#folder, false);
        completedBytes += Math.max(0, file.size);
        successful.push(file.name);
        this.#renderUploadProgress(
          index + 1 === queue.length ? "Upload abgeschlossen" : "Datei erfolgreich hochgeladen",
          `${file.name} wurde in die Galerie übernommen.`,
          completedBytes,
          totalBytes,
          successful,
        );
      }
      await this.#refresh(true);
      this.#showMessage(`${successful.length} Datei(en) erfolgreich hochgeladen.`);
    } catch (error) {
      const message = errorMessage(error);
      this.#renderUploadProgress("Upload fehlgeschlagen", message, completedBytes, totalBytes, successful, true);
      this.#showError(message);
    } finally {
      this.#busy = false;
      if (input) input.value = "";
    }
  }

  async #run(operation: () => Promise<void>): Promise<void> {
    if (this.#busy) return;
    this.#busy = true;
    try {
      await operation();
      this.#busy = false;
      await this.#refresh(true);
      this.#showMessage("Änderung wurde übernommen.");
    } catch (error) {
      this.#showError(errorMessage(error));
    } finally {
      this.#busy = false;
    }
  }

  #setLive(value: string): void { const node = this.#root.querySelector<HTMLElement>("#live"); if (node) node.textContent = value; }
  #showMessage(value: string): void { const node = this.#root.querySelector<HTMLElement>("#notice"); if (node) node.innerHTML = `<div class="notice ok">${esc(value)}</div>`; }
  #showError(value: string): void { const node = this.#root.querySelector<HTMLElement>("#notice"); if (node) node.innerHTML = `<div class="notice error">${esc(value)}</div>`; }
}

if (!customElements.get("ultimate-3d-gallery-library-pane")) {
  customElements.define("ultimate-3d-gallery-library-pane", Ultimate3DGalleryLibraryPane);
}