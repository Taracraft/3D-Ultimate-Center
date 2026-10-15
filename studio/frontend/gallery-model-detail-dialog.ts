import type { GalleryItem } from "./gallery-api.js";

export type GalleryDetailActions = Readonly<{
  download: () => void;
  openStudio: () => void;
}>;

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function sizeLabel(value: number | undefined): string {
  const size = Number(value || 0);
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 ** 3) return `${(size / 1024 ** 2).toFixed(1)} MB`;
  return `${(size / 1024 ** 3).toFixed(2)} GB`;
}

function dateLabel(value: number | string | undefined): string {
  if (value === undefined || value === null || value === "") return "Unbekannt";
  const numeric = Number(value);
  const date = Number.isFinite(numeric)
    ? new Date(numeric > 10_000_000_000 ? numeric : numeric * 1000)
    : new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("de-DE");
}

export class GalleryModelDetailDialog extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #previewUrl = "";
  #actions: GalleryDetailActions | null = null;

  connectedCallback(): void {
    if (!this.#root.childElementCount) this.#renderClosed();
  }

  disconnectedCallback(): void {
    this.close();
  }

  open(item: GalleryItem, preview: Blob | null, actions: GalleryDetailActions): void {
    this.close();
    this.#actions = actions;
    this.style.display = "contents";
    if (preview) this.#previewUrl = URL.createObjectURL(preview);
    this.#root.innerHTML = `<style>
      :host{display:contents;color:#eef6ff;font:13px/1.4 Inter,Segoe UI,sans-serif}
      *{box-sizing:border-box}.dialog{width:min(980px,calc(100vw - 24px));max-height:calc(100dvh - 24px);margin:auto;padding:0;overflow:auto;overscroll-behavior:contain;color:#eef6ff;font:inherit;border:1px solid #355773;border-radius:10px;background:linear-gradient(180deg,#111f2d,#08131d);box-shadow:0 24px 80px #000}.dialog::backdrop{background:#000a}.head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:15px 17px;border-bottom:1px solid #294157}.head h2{margin:0;font-size:20px}.head p{margin:4px 0 0;color:#86a0b7}.close{width:34px;height:34px;border:1px solid #3a566e;border-radius:5px;background:#122538;color:#fff;font-size:20px}.content{display:grid;grid-template-columns:minmax(320px,1.25fr) minmax(260px,.75fr);gap:16px;padding:16px}.preview{display:grid;place-items:center;min-height:430px;border:1px solid #294157;border-radius:8px;background:radial-gradient(circle at 50% 45%,#182b3b,#050b11 70%);overflow:hidden}.preview img{display:block;max-width:100%;max-height:70dvh;object-fit:contain}.placeholder{font-size:64px;color:#5b7890}.meta{display:grid;align-content:start;gap:8px}.row{display:grid;grid-template-columns:110px minmax(0,1fr);gap:8px;padding:9px 0;border-bottom:1px solid #22384b}.row span:first-child{color:#7890a6}.row span:last-child{overflow-wrap:anywhere}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.actions button{flex:1;min-width:130px;padding:10px;border:1px solid #31506e;border-radius:5px;background:linear-gradient(180deg,#19324a,#102335);color:#eef6ff;font-weight:700}.actions .primary{border-color:#45caff;background:linear-gradient(180deg,#187aa5,#115574)}@media(max-width:760px){.content{grid-template-columns:1fr}.preview{min-height:280px}}
    </style><dialog class="dialog" aria-modal="true" aria-label="Modelldetails"><header class="head"><div><h2>${esc(item.title || item.name)}</h2><p>${esc(item.file_name || item.name)}</p></div><button class="close" type="button" aria-label="Schließen">×</button></header><div class="content"><div class="preview">${this.#previewUrl ? `<img src="${esc(this.#previewUrl)}" alt="${esc(item.title || item.name)}">` : '<span class="placeholder">◇</span>'}</div><aside class="meta"><div class="row"><span>Format</span><span>${esc(String(item.format || "unbekannt").toUpperCase())}</span></div><div class="row"><span>Dateigröße</span><span>${esc(sizeLabel(item.size_bytes))}</span></div><div class="row"><span>Geändert</span><span>${esc(dateLabel(item.modified ?? item.updated_at))}</span></div><div class="row"><span>Pfad</span><span>${esc(item.relative_path || item.path)}</span></div><div class="row"><span>Asset-ID</span><span>${esc(item.asset_id)}</span></div><div class="actions"><button type="button" id="download">Download</button><button type="button" class="primary" id="studio">Im 3D-Studio öffnen</button></div></aside></div></dialog>`;
    this.#root.querySelector<HTMLButtonElement>(".close")?.addEventListener("click", () => this.close());
    this.#root.querySelector<HTMLButtonElement>("#download")?.addEventListener("click", () => this.#actions?.download());
    this.#root.querySelector<HTMLButtonElement>("#studio")?.addEventListener("click", () => { const action = this.#actions?.openStudio; this.close(); action?.(); });
    const dialog = this.#root.querySelector<HTMLDialogElement>("dialog");
    dialog?.addEventListener("cancel", (event) => { event.preventDefault(); this.close(); });
    dialog?.addEventListener("close", () => {
      if (this.#root.querySelector("dialog") === dialog) this.close();
    });
    try {
      if (!dialog) throw new Error("Modelldialog fehlt");
      dialog.showModal();
    } catch (error) {
      this.close();
      throw error;
    }
  }

  close(): void {
    const dialog = this.#root.querySelector<HTMLDialogElement>("dialog");
    this.#actions = null;
    if (dialog?.open) dialog.close();
    this.#releasePreview();
    this.#renderClosed();
  }

  #releasePreview(): void {
    if (this.#previewUrl) URL.revokeObjectURL(this.#previewUrl);
    this.#previewUrl = "";
  }

  #renderClosed(): void {
    this.#root.innerHTML = "";
    this.style.display = "none";
  }
}

if (!customElements.get("gallery-model-detail-dialog")) {
  customElements.define("gallery-model-detail-dialog", GalleryModelDetailDialog);
}
