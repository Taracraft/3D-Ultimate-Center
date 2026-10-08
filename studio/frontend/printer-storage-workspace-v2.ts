import "./studio-action-dialog.js";
import "./studio-context-menu.js";
import { errorMessage } from "./ha-api-transport.js";
import {
  PrinterStorageApi,
  type PrinterStorageFolder,
  type PrinterStorageItem,
  type PrinterStorageListing,
  type PrinterStorageSummary,
} from "./printer-storage-api.js";
import { STORAGE_WORKSPACE_STYLE } from "./storage-workspace-style.js";
import type { StudioActionDialog } from "./studio-action-dialog.js";
import type {
  StudioContextMenu,
  StudioContextMenuItem,
} from "./studio-context-menu.js";
import {
  queueWorkspaceFile,
  type WorkspaceFileTarget,
} from "./workspace-file-handoff.js";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function sizeLabel(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function modifiedLabel(value: string): string {
  const raw = String(value || "").trim();
  const match = raw.match(
    /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/,
  );
  if (match) {
    const [, year, month, day, hour, minute, second] = match;
    return `${day}.${month}.${year}, ${hour}:${minute}:${second}`;
  }
  if (!raw) return "Änderungszeit unbekannt";
  const date = new Date(raw);
  return Number.isNaN(date.getTime())
    ? raw
    : date.toLocaleString("de-DE");
}

function fingerprint(
  listing: PrinterStorageListing | null,
  tree: readonly PrinterStorageFolder[],
): string {
  return JSON.stringify({ listing, tree });
}

export class Ultimate3DPrinterStorageWorkspaceV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #api = new PrinterStorageApi();
  #printers: PrinterStorageSummary[] = [];
  #printerId = "";
  #listing: PrinterStorageListing | null = null;
  #tree: PrinterStorageFolder[] = [];
  #timer: number | null = null;
  #fingerprint = "";
  #reading = false;
  #actionBusy = false;
  #pendingRead: { folder: string; silent: boolean } | null = null;
  #query = "";
  #lastReadAt: Date | null = null;

  connectedCallback(): void {
    if (!this.#root.childElementCount) this.#mount();
    void this.#initialize();
    if (this.#timer === null) {
      this.#timer = window.setInterval(
        () => void this.#refresh(true),
        10000,
      );
    }
  }

  disconnectedCallback(): void {
    if (this.#timer !== null) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  #dialog(): StudioActionDialog | null {
    return this.#root.querySelector<StudioActionDialog>("studio-action-dialog");
  }

  #menu(): StudioContextMenu | null {
    return this.#root.querySelector<StudioContextMenu>("studio-context-menu");
  }

  #mount(): void {
    this.#root.innerHTML = `<style>
      ${STORAGE_WORKSPACE_STYLE}
      .search{
        flex:1;
        min-width:190px;
        min-height:38px;
        padding:9px;
        border:1px solid #31506e;
        border-radius:8px;
        background:#09131f;
        color:#fff;
      }
      .read-status{
        display:flex;
        align-items:center;
        gap:8px;
        min-height:38px;
        padding:7px 10px;
        border:1px solid #31506e;
        border-radius:8px;
        background:#0d1723;
        color:#9eb3c8;
        font-size:11px;
        white-space:nowrap;
      }
      .read-status::before{
        width:8px;
        height:8px;
        border-radius:999px;
        background:#58d879;
        box-shadow:0 0 8px #58d879;
        content:"";
      }
      .read-status.reading::before{
        background:#42c8ff;
        box-shadow:0 0 8px #42c8ff;
        animation:sd-pulse 1s ease-in-out infinite;
      }
      .read-status.error::before{
        background:#ff6b78;
        box-shadow:0 0 8px #ff6b78;
      }
      @keyframes sd-pulse{
        0%,100%{opacity:.35;transform:scale(.8)}
        50%{opacity:1;transform:scale(1.15)}
      }
      .body small + small{margin-top:3px}
      @media(max-width:850px){
        .read-status{white-space:normal}
      }
    </style>
    <section class="page">
      <header class="head">
        <div>
          <h1>Drucker-SD-Karte</h1>
          <p>Direkter Studio-Dateizugriff in derselben Ansicht wie die Galerie.</p>
        </div>
        <div class="actions">
          <select id="printer" aria-label="Drucker auswählen"></select>
          <button id="refresh">Aktualisieren</button>
          <span class="read-status" id="read-status">Noch nicht ausgelesen</span>
        </div>
      </header>
      <div id="notice"></div>
      <div class="layout">
        <aside class="sidebar">
          <strong>Ordner</strong>
          <div class="tree" id="tree"></div>
        </aside>
        <main>
          <div class="toolbar">
            <input
              class="search"
              id="search"
              type="search"
              placeholder="SD-Karte durchsuchen"
            >
            <button id="search-button">Suchen</button>
            <button class="primary" id="upload">Hochladen</button>
            <button id="new-folder">Neuer Ordner</button>
            <button id="up">Eine Ebene hoch</button>
          </div>
          <div class="path" id="path">Hauptordner</div>
          <section class="items" id="items"></section>
        </main>
      </div>
      <input id="upload-input" type="file" multiple hidden>
      <studio-action-dialog></studio-action-dialog>
      <studio-context-menu></studio-context-menu>
    </section>`;

    this.#root
      .querySelector<HTMLButtonElement>("#refresh")
      ?.addEventListener("click", () => void this.#refresh(false));
    this.#root
      .querySelector<HTMLButtonElement>("#upload")
      ?.addEventListener("click", () => {
        this.#root
          .querySelector<HTMLInputElement>("#upload-input")
          ?.click();
      });
    this.#root
      .querySelector<HTMLInputElement>("#upload-input")
      ?.addEventListener("change", (event) => {
        void this.#upload((event.currentTarget as HTMLInputElement).files);
      });
    this.#root
      .querySelector<HTMLButtonElement>("#new-folder")
      ?.addEventListener("click", () => void this.#createFolder());
    this.#root
      .querySelector<HTMLButtonElement>("#up")
      ?.addEventListener("click", () => {
        void this.#openFolder(this.#listing?.parent || "/");
      });
    this.#root
      .querySelector<HTMLButtonElement>("#search-button")
      ?.addEventListener("click", () => this.#applySearch());
    this.#root
      .querySelector<HTMLInputElement>("#search")
      ?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") this.#applySearch();
      });
    this.#root
      .querySelector<HTMLSelectElement>("#printer")
      ?.addEventListener("change", (event) => {
        this.#printerId = (event.currentTarget as HTMLSelectElement).value;
        this.#query = "";
        const search = this.#root.querySelector<HTMLInputElement>("#search");
        if (search) search.value = "";
        void this.#openFolder("/");
      });
  }

  async #initialize(): Promise<void> {
    try {
      this.#printers = (await this.#api.summaries()).filter(
        (item) => item.storage_supported,
      );
      this.#printerId = this.#printers.find(
        (item) => item.connection_state === "connected",
      )?.printer_id || this.#printers[0]?.printer_id || "";
      this.#renderPrinters();
      if (this.#printerId) {
        await this.#openFolder("/");
      } else {
        this.#showError(
          "Kein Studio-Drucker mit SD-Kartenunterstützung verfügbar.",
        );
      }
    } catch (error) {
      this.#showError(errorMessage(error));
      this.#setReadState("error", "Auslesen fehlgeschlagen");
    }
  }

  #applySearch(): void {
    this.#query = this.#root
      .querySelector<HTMLInputElement>("#search")
      ?.value.trim() || "";
    this.#renderData();
  }

  async #refresh(silent: boolean): Promise<void> {
    await this.#readFolder(this.#listing?.folder || "/", silent);
  }

  async #openFolder(folder: string): Promise<void> {
    this.#query = "";
    const search = this.#root.querySelector<HTMLInputElement>("#search");
    if (search) search.value = "";
    await this.#readFolder(folder, true);
    this.#clearNotice();
  }

  async #readFolder(folder: string, silent: boolean): Promise<void> {
    if (!this.#printerId) return;
    if (this.#reading) {
      this.#pendingRead = { folder, silent };
      return;
    }

    this.#reading = true;
    this.#setReadState(
      "reading",
      `SD-Karte wird ausgelesen · ${new Date().toLocaleTimeString("de-DE")}`,
    );
    try {
      const [listing, tree] = await Promise.all([
        this.#api.list(this.#printerId, folder, true),
        this.#api.tree(this.#printerId),
      ]);
      const next = fingerprint(listing, tree);
      this.#listing = listing;
      this.#tree = tree;
      if (next !== this.#fingerprint) {
        this.#fingerprint = next;
        this.#renderData();
      }
      this.#lastReadAt = new Date();
      this.#setReadState(
        "ready",
        `Zuletzt ausgelesen: ${this.#lastReadAt.toLocaleString("de-DE")}`,
      );
      if (!silent) this.#showMessage("SD-Karte wurde aktualisiert.");
    } catch (error) {
      this.#showError(errorMessage(error));
      this.#setReadState(
        "error",
        `Auslesen fehlgeschlagen: ${new Date().toLocaleTimeString("de-DE")}`,
      );
    } finally {
      this.#reading = false;
      const pending = this.#pendingRead;
      this.#pendingRead = null;
      if (pending) {
        void this.#readFolder(pending.folder, pending.silent);
      }
    }
  }

  #renderPrinters(): void {
    const select = this.#root.querySelector<HTMLSelectElement>("#printer");
    if (!select) return;
    select.innerHTML = this.#printers.map((printer) => (
      `<option value="${esc(printer.printer_id)}" ${
        printer.printer_id === this.#printerId ? "selected" : ""
      }>${esc(printer.printer_name)} · ${esc(printer.connection_state)}</option>`
    )).join("");
  }

  #treeItems(): PrinterStorageFolder[] {
    const items = [...this.#tree];
    if (!items.some((folder) => folder.path === "/")) {
      items.unshift({ path: "/", name: "Hauptordner", depth: 0 });
    }
    return items;
  }

  #visibleItems(): PrinterStorageItem[] {
    const entries = this.#listing?.items || [];
    const query = this.#query.toLocaleLowerCase("de-DE");
    if (!query) return entries;
    return entries.filter((item) => (
      item.name.toLocaleLowerCase("de-DE").includes(query)
      || item.kind.toLocaleLowerCase("de-DE").includes(query)
    ));
  }

  #renderData(): void {
    const tree = this.#root.querySelector<HTMLElement>("#tree");
    const items = this.#root.querySelector<HTMLElement>("#items");
    const path = this.#root.querySelector<HTMLElement>("#path");
    const up = this.#root.querySelector<HTMLButtonElement>("#up");
    if (!tree || !items || !path || !up) return;

    const treeScroll = tree.parentElement?.scrollTop || 0;
    tree.innerHTML = this.#treeItems().map((folder) => (
      `<button
        data-folder="${esc(folder.path)}"
        class="${folder.path === this.#listing?.folder ? "active" : ""}"
        style="padding-left:${7 + folder.depth * 12}px"
      >📁 ${esc(folder.name)}</button>`
    )).join("");
    tree.querySelectorAll<HTMLButtonElement>("[data-folder]").forEach(
      (button) => button.addEventListener("click", () => {
        void this.#openFolder(button.dataset.folder || "/");
      }),
    );
    if (tree.parentElement) tree.parentElement.scrollTop = treeScroll;

    const currentFolder = this.#listing?.folder || "/";
    path.textContent = currentFolder === "/"
      ? "Hauptordner"
      : `Hauptordner / ${currentFolder.replace(/^\/+/, "")}`;
    up.disabled = currentFolder === "/";

    const entries = this.#visibleItems();
    items.replaceChildren(...entries.map((item) => this.#card(item)));
    if (!entries.length) {
      items.innerHTML = this.#query
        ? '<div class="empty">Keine passenden Dateien oder Ordner vorhanden.</div>'
        : '<div class="empty">Dieser Ordner ist leer.</div>';
    }
    this.#setActionDisabled(this.#actionBusy);
  }

  #card(item: PrinterStorageItem): HTMLElement {
    const card = document.createElement("article");
    card.className = "card";

    const preview = document.createElement("div");
    preview.className = "preview";
    if (item.preview_data_url) {
      preview.innerHTML = `<img src="${esc(item.preview_data_url)}" alt="${esc(item.name)}">`;
    } else {
      preview.innerHTML = `<span class="icon">${
        item.kind === "folder" ? "📁" : item.kind === "gcode" ? "≋" : "◇"
      }</span>`;
    }

    const body = document.createElement("div");
    body.className = "body";
    body.innerHTML = `
      <strong title="${esc(item.name)}">${esc(item.name)}</strong>
      <small>${
        item.kind === "folder"
          ? "Ordner"
          : `${esc(item.kind.toUpperCase())} · ${sizeLabel(item.size_bytes)}`
      }</small>
      ${item.kind === "folder" ? "" : `<small>${esc(modifiedLabel(item.modified))}</small>`}
    `;

    const actions = document.createElement("div");
    actions.className = "card-actions";
    if (item.kind === "folder") {
      actions.append(
        this.#button("Öffnen", () => void this.#openFolder(item.path)),
      );
    } else {
      actions.append(
        this.#button("Download", () => void this.#download(item)),
      );
      if (item.kind === "project" || item.kind === "model") {
        actions.append(
          this.#button(
            "CAD-Studio",
            () => void this.#openWorkspace(item, "studio"),
          ),
          this.#button(
            "Slicer",
            () => void this.#openWorkspace(item, "slicer"),
          ),
        );
      }
    }
    actions.append(
      this.#button("Umbenennen", () => void this.#rename(item)),
      this.#button("Kopieren", () => void this.#transfer(item, "copy")),
      this.#button("Verschieben", () => void this.#transfer(item, "move")),
      this.#button("Löschen", () => void this.#remove(item), true),
    );
    card.append(preview, body, actions);
    card.addEventListener(
      "contextmenu",
      (event) => this.#openContext(event, item),
    );
    return card;
  }

  #button(
    label: string,
    action: () => void,
    danger = false,
  ): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.disabled = this.#actionBusy;
    if (danger) button.classList.add("danger");
    button.addEventListener("click", action);
    return button;
  }

  #openContext(event: MouseEvent, item: PrinterStorageItem): void {
    event.preventDefault();
    if (this.#actionBusy) return;
    const menu: StudioContextMenuItem[] = item.kind === "folder" ? [
      { label: "Ordner öffnen", action: () => this.#openFolder(item.path) },
      { label: "Umbenennen", action: () => this.#rename(item) },
      { label: "Kopieren", action: () => this.#transfer(item, "copy") },
      { label: "Verschieben", action: () => this.#transfer(item, "move") },
      { label: "Löschen", action: () => this.#remove(item), danger: true },
    ] : [
      { label: "Herunterladen", action: () => this.#download(item) },
      {
        label: "Im CAD-Studio öffnen",
        action: () => this.#openWorkspace(item, "studio"),
        disabled: item.kind !== "project" && item.kind !== "model",
      },
      {
        label: "Im Slicer öffnen",
        action: () => this.#openWorkspace(item, "slicer"),
        disabled: item.kind !== "project" && item.kind !== "model",
      },
      { label: "Umbenennen", action: () => this.#rename(item) },
      { label: "Kopieren", action: () => this.#transfer(item, "copy") },
      { label: "Verschieben", action: () => this.#transfer(item, "move") },
      { label: "Löschen", action: () => this.#remove(item), danger: true },
    ];
    this.#menu()?.openAt(event.clientX, event.clientY, menu);
  }

  async #chooseFolder(title: string): Promise<string | null> {
    return await this.#dialog()?.choose({
      title,
      message: "Zielordner auf der Drucker-SD-Karte auswählen.",
      confirmLabel: "Übernehmen",
      select: {
        label: "Zielordner",
        value: this.#listing?.folder || "/",
        options: this.#treeItems().map((folder) => ({
          value: folder.path,
          label: `${"  ".repeat(folder.depth)}${folder.name}`,
          description: folder.path,
        })),
      },
    }) ?? null;
  }

  async #createFolder(): Promise<void> {
    const name = await this.#dialog()?.requestText({
      title: "Neuen SD-Ordner erstellen",
      message: this.#listing?.folder || "/",
      confirmLabel: "Erstellen",
      input: { label: "Ordnername" },
    });
    if (!name) return;
    await this.#run(async () => {
      await this.#api.action(this.#printerId, "create_folder", {
        target_folder: this.#listing?.folder || "/",
        name,
      });
    });
  }

  async #rename(item: PrinterStorageItem): Promise<void> {
    const name = await this.#dialog()?.requestText({
      title: "SD-Eintrag umbenennen",
      message: item.path,
      confirmLabel: "Umbenennen",
      input: { label: "Neuer Name", value: item.name },
    });
    if (!name || name === item.name) return;
    await this.#run(async () => {
      await this.#api.action(this.#printerId, "rename", {
        path: item.path,
        name,
      });
    });
  }

  async #transfer(
    item: PrinterStorageItem,
    action: "copy" | "move",
  ): Promise<void> {
    const target = await this.#chooseFolder(
      action === "copy" ? "SD-Datei kopieren" : "SD-Eintrag verschieben",
    );
    if (target === null) return;
    await this.#run(async () => {
      await this.#api.action(this.#printerId, action, {
        path: item.path,
        target_folder: target,
      });
    });
  }

  async #remove(item: PrinterStorageItem): Promise<void> {
    const confirmed = await this.#dialog()?.confirm({
      title: "Von SD-Karte löschen",
      message: "Diesen Eintrag dauerhaft löschen?",
      detail: item.path,
      confirmLabel: "Löschen",
      danger: true,
    });
    if (!confirmed) return;
    await this.#run(async () => {
      await this.#api.action(this.#printerId, "delete", { path: item.path });
    });
  }

  async #download(item: PrinterStorageItem): Promise<void> {
    try {
      const file = await this.#api.download(this.#printerId, item);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      this.#showError(errorMessage(error));
    }
  }

  async #openWorkspace(
    item: PrinterStorageItem,
    target: WorkspaceFileTarget,
  ): Promise<void> {
    try {
      const file = await this.#api.download(this.#printerId, item);
      queueWorkspaceFile(target, file);
      this.dispatchEvent(new CustomEvent(
        target === "studio" ? "gallery-open-studio" : "gallery-open-slicer",
        { bubbles: true, composed: true },
      ));
    } catch (error) {
      this.#showError(errorMessage(error));
    }
  }

  async #upload(files: FileList | null): Promise<void> {
    const queue = files ? Array.from(files) : [];
    if (!queue.length) return;
    await this.#run(async () => {
      for (const file of queue) {
        await this.#api.upload(
          this.#printerId,
          file,
          this.#listing?.folder || "/",
          false,
        );
      }
    });
    const input = this.#root.querySelector<HTMLInputElement>("#upload-input");
    if (input) input.value = "";
  }

  async #run(operation: () => Promise<void>): Promise<void> {
    if (this.#actionBusy) return;
    this.#actionBusy = true;
    this.#setActionDisabled(true);
    let succeeded = false;
    try {
      await operation();
      succeeded = true;
    } catch (error) {
      this.#showError(errorMessage(error));
    } finally {
      this.#actionBusy = false;
      this.#setActionDisabled(false);
    }
    if (!succeeded) return;
    await this.#refresh(true);
    this.#showMessage("Änderung wurde übernommen; die SD-Karte wird neu gelesen.");
  }

  #setActionDisabled(value: boolean): void {
    this.#root
      .querySelectorAll<HTMLButtonElement>(
        "#upload,#new-folder,.card-actions button",
      )
      .forEach((element) => {
        element.disabled = value;
      });
  }

  #setReadState(
    state: "reading" | "ready" | "error",
    value: string,
  ): void {
    const node = this.#root.querySelector<HTMLElement>("#read-status");
    if (!node) return;
    node.className = `read-status ${state}`;
    node.textContent = value;
  }

  #clearNotice(): void {
    const node = this.#root.querySelector<HTMLElement>("#notice");
    if (node) node.replaceChildren();
  }

  #showMessage(value: string): void {
    const node = this.#root.querySelector<HTMLElement>("#notice");
    if (node) node.innerHTML = `<div class="notice ok">${esc(value)}</div>`;
  }

  #showError(value: string): void {
    const node = this.#root.querySelector<HTMLElement>("#notice");
    if (node) node.innerHTML = `<div class="notice error">${esc(value)}</div>`;
  }
}

if (!customElements.get("ultimate-3d-printer-storage-workspace")) {
  customElements.define(
    "ultimate-3d-printer-storage-workspace",
    Ultimate3DPrinterStorageWorkspaceV2,
  );
}
