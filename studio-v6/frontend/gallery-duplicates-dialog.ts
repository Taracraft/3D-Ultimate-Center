import type { GalleryDuplicateGroup, GalleryDuplicateReport } from "./gallery-duplicate-contract.js";

type Scan = (folder: string, signal: AbortSignal) => Promise<GalleryDuplicateReport>;
type Session = {
  folder: string; dialog: HTMLDialogElement; close: HTMLButtonElement;
  status: HTMLElement; content: HTMLElement; filter: HTMLInputElement;
  previous: HTMLButtonElement; next: HTMLButtonElement; pageLabel: HTMLElement;
  controller: AbortController; focus: HTMLElement | null;
  report: GalleryDuplicateReport | null; page: number;
  openFolder: (folder: string) => void;
};
const GROUPS_PER_PAGE = 20;
const PATHS_PER_PAGE = 20;

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text = "", className = ""): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text: string, action: () => void): HTMLButtonElement {
  const node = element("button", text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}
function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  return `${(value / 1024 ** 3).toFixed(2)} GiB`;
}
function focusedElement(): HTMLElement | null {
  let active = document.activeElement;
  while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
  return active instanceof HTMLElement ? active : null;
}

/** Native modal, manual scans only; its contents never execute file mutations. */
export class GalleryDuplicatesDialog extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #current: Session | null = null;
  #styled = false;

  disconnectedCallback(): void { this.close(); }

  open(folder: string, scan: Scan, openFolder: (folder: string) => void): boolean {
    if (!this.isConnected) return false;
    if (this.#current?.folder === folder) {
      this.#current.close.focus({ preventScroll: true });
      return true;
    }
    this.close();
    this.#style();
    const focus = focusedElement();
    const dialog = element("dialog");
    dialog.setAttribute("aria-labelledby", "duplicates-heading");
    dialog.setAttribute("aria-describedby", "duplicates-scope");
    const header = element("header");
    const heading = element("h2", "Duplikate prüfen"); heading.id = "duplicates-heading";
    const scope = element("p", `${folder || "Hauptordner"} · mit allen Unterordnern`, "scope");
    scope.id = "duplicates-scope";
    const note = element("p", "Verglichen werden Dateiinhalte, nicht ähnliche Geometrien. Galerie-Suchfilter gelten hier nicht. Keine Datei wird verändert.", "note");
    const status = element("p", "Prüfung läuft …", "status");
    status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
    const filter = element("input"); filter.type = "search"; filter.disabled = true;
    filter.placeholder = "Treffer nach Dateipfad filtern";
    filter.setAttribute("aria-label", "Duplikatgruppen nach Dateipfad filtern");
    const content = element("section", "", "results");
    content.setAttribute("aria-label", "Ergebnisse der Duplikatprüfung"); content.setAttribute("aria-busy", "true");
    const pageLabel = element("span", "", "page-label"); pageLabel.setAttribute("aria-live", "polite");
    const previous = button("Vorherige Gruppen", () => this.#page(session, -1));
    const next = button("Nächste Gruppen", () => this.#page(session, 1));
    previous.disabled = true; next.disabled = true;
    const close = button("Schließen", () => this.#dispose(session));
    close.setAttribute("aria-label", "Duplikatprüfung schließen");
    const session: Session = { folder, dialog, close, status, content, filter, previous, next,
      pageLabel, controller: new AbortController(), focus, report: null, page: 0, openFolder };
    filter.addEventListener("input", () => { session.page = 0; this.#render(session); });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); this.#dispose(session); });
    dialog.addEventListener("close", () => this.#dispose(session));
    const footer = element("footer"); footer.append(previous, pageLabel, next, close);
    header.append(heading, scope, note, status, filter);
    dialog.append(header, content, footer);
    this.#root.append(dialog); this.#current = session;
    try { dialog.showModal(); }
    catch { this.#dispose(session); return false; }
    close.focus({ preventScroll: true });
    void this.#load(session, scan);
    return true;
  }

  close(): void { if (this.#current) this.#dispose(this.#current); }

  #dispose(session: Session): void {
    if (this.#current !== session) return;
    this.#current = null;
    session.controller.abort();
    if (session.dialog.open) session.dialog.close();
    session.dialog.remove();
    if (this.isConnected && session.focus?.isConnected) session.focus.focus({ preventScroll: true });
  }

  async #load(session: Session, scan: Scan): Promise<void> {
    try {
      const report = await scan(session.folder, session.controller.signal);
      if (this.#current !== session || session.controller.signal.aborted || !this.isConnected) return;
      session.report = report;
      session.filter.disabled = false;
      session.content.setAttribute("aria-busy", "false");
      const observed = new Date().toLocaleTimeString("de-DE");
      session.status.textContent = `${report.duplicate_groups} Duplikatgruppen · ${report.files_examined} Modelle geprüft · ${bytes(report.bytes_hashed)} verglichen · ${report.skipped_links} Verknüpfungen ausgelassen. Ergebnis empfangen um ${observed}; der Bestand kann sich danach ändern.`;
      this.#render(session);
    } catch (error) {
      if (this.#current !== session || session.controller.signal.aborted || !this.isConnected) return;
      session.content.setAttribute("aria-busy", "false");
      session.content.replaceChildren();
      session.status.setAttribute("role", "alert");
      session.status.textContent = error instanceof Error ? error.message : "Die Duplikatprüfung konnte nicht abgeschlossen werden.";
      session.status.className = "status error";
    }
  }

  #matching(session: Session): readonly GalleryDuplicateGroup[] {
    const needle = session.filter.value.trim().toLocaleLowerCase("de-DE");
    return session.report?.groups.filter((group) => !needle
      || group.paths.some((path) => path.toLocaleLowerCase("de-DE").includes(needle))) || [];
  }

  #page(session: Session, delta: number): void {
    if (this.#current !== session) return;
    const last = Math.max(0, Math.ceil(this.#matching(session).length / GROUPS_PER_PAGE) - 1);
    session.page = Math.max(0, Math.min(last, session.page + delta));
    this.#render(session);
  }

  #render(session: Session): void {
    if (this.#current !== session || !session.report) return;
    const groups = this.#matching(session);
    const start = session.page * GROUPS_PER_PAGE;
    session.content.replaceChildren(); session.content.scrollTop = 0;
    for (const group of groups.slice(start, start + GROUPS_PER_PAGE)) session.content.append(this.#group(session, group));
    if (!groups.length) session.content.append(element("p", session.report.duplicate_groups
      ? "Keine Duplikatgruppe passt zu diesem Filter."
      : "Keine bytegleichen Modelldateien im geprüften Ordnerbestand gefunden.", "empty"));
    session.previous.disabled = session.page === 0;
    session.next.disabled = start + GROUPS_PER_PAGE >= groups.length;
    session.pageLabel.textContent = groups.length
      ? `Gruppen ${start + 1}–${Math.min(start + GROUPS_PER_PAGE, groups.length)} von ${groups.length}` : "0 Gruppen";
  }

  #group(session: Session, group: GalleryDuplicateGroup): HTMLElement {
    const card = element("article", "", "group");
    const title = element("h3", `${group.paths.length} Dateipfade · ${bytes(group.size_bytes)} je Datei`);
    const detail = element("p", `${group.independent_copies} unabhängige Dateikopien · ${group.hardlink_aliases} zusätzliche Hardlink-Verweise`, "note");
    const fingerprint = element("code", `SHA-256 ${group.sha256}`);
    const list = element("ul");
    const label = element("span");
    let page = 0;
    const draw = (): void => {
      if (this.#current !== session) return;
      const start = page * PATHS_PER_PAGE;
      list.replaceChildren();
      for (const path of group.paths.slice(start, start + PATHS_PER_PAGE)) {
        const row = element("li"); row.append(element("span", path, "file-path"));
        const go = button("Ordner öffnen", () => {
          if (this.#current !== session) return;
          this.#dispose(session);
          session.openFolder(path.slice(0, Math.max(0, path.lastIndexOf("/"))));
        });
        go.setAttribute("aria-label", `Ordner von ${path} öffnen`);
        row.append(go); list.append(row);
      }
      previous.disabled = page === 0;
      next.disabled = start + PATHS_PER_PAGE >= group.paths.length;
      label.textContent = `Dateipfade ${start + 1}–${Math.min(start + PATHS_PER_PAGE, group.paths.length)} von ${group.paths.length}`;
    };
    const previous = button("Vorherige Dateipfade", () => { page = Math.max(0, page - 1); draw(); });
    const next = button("Weitere Dateipfade", () => {
      page = Math.min(Math.ceil(group.paths.length / PATHS_PER_PAGE) - 1, page + 1); draw();
    });
    const pager = element("div", "", "file-pager");
    pager.append(previous, label, next); pager.hidden = group.paths.length <= PATHS_PER_PAGE;
    card.append(title, detail, fingerprint, list, pager); draw();
    return card;
  }

  #style(): void {
    if (this.#styled) return;
    const style = element("style");
    style.textContent = `:host{display:contents}*{box-sizing:border-box}dialog{width:min(900px,calc(100vw - 24px));max-width:none;max-height:90vh;max-height:calc(100dvh - 32px);padding:0;border:1px solid #36516c;border-radius:14px;background:#0c1724;color:#e8f4ff;font:14px/1.5 system-ui;box-shadow:0 18px 80px #0009}dialog[open]{display:grid;grid-template-rows:auto minmax(80px,1fr) auto}dialog::backdrop{background:#020912bc}header{padding:18px 20px 12px;border-bottom:1px solid #263d53}h2{font-size:21px;margin:0}h3{font-size:15px;margin:0 0 6px}.scope,.file-path,code{overflow-wrap:anywhere;word-break:break-word}.scope{margin:5px 0;color:#a9d6f0}.note{color:#a9bfd2;font-size:12px;margin:6px 0}.status{margin:10px 0;font-size:13px}.error{color:#ffb3bb}input{display:block;width:100%;min-width:0;background:#07111c;color:inherit;border:1px solid #3b536b;border-radius:8px;padding:10px;font:inherit}.results{overflow:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;min-height:0;padding:14px 20px}.group{border:1px solid #2c455d;border-radius:10px;padding:14px;margin-bottom:12px;background:#102031}code{display:block;color:#9eb4ca;font-size:11px}ul{list-style:none;margin:12px 0 0;padding:0}li{display:flex;align-items:center;gap:12px;justify-content:space-between;border-top:1px solid #294157;padding:9px 0}.file-path{min-width:0}button{flex-shrink:0;min-height:44px;border:1px solid #3b5770;border-radius:8px;background:#17334b;color:inherit;font:inherit;padding:7px 12px;cursor:pointer}button:disabled{opacity:.4;cursor:default}:focus-visible{outline:2px solid #7bd6ff;outline-offset:2px}footer,.file-pager{display:flex;flex-wrap:wrap;align-items:center;gap:8px}footer{padding:12px 20px;border-top:1px solid #263d53}footer button:last-child{margin-left:auto}.page-label,.file-pager span{font-size:12px;color:#a9bfd2}.file-pager{margin-top:8px}.file-pager[hidden]{display:none}.empty{color:#c2d4e3}@media(max-width:520px){header{padding:14px}.results{padding:10px 14px}footer{padding:10px 14px}li{display:block}li button{margin-top:8px;width:100%}footer button:last-child{margin-left:0}h2{font-size:18px}}`;
    this.#root.append(style); this.#styled = true;
  }
}

if (!customElements.get("gallery-duplicates-dialog")) customElements.define("gallery-duplicates-dialog", GalleryDuplicatesDialog);
