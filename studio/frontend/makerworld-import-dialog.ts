import type { MakerWorldDesign } from "./makerworld-api.js";

export class MakerWorldImportDialog extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #model: MakerWorldDesign | null = null;

  set model(value: MakerWorldDesign | null) {
    this.#model = value;
    this.#render();
  }

  get model(): MakerWorldDesign | null {
    return this.#model;
  }

  connectedCallback(): void {
    this.#render();
  }

  #render(): void {
    if (!this.isConnected) return;
    const model = this.#model;
    this.#root.innerHTML = `
      <style>
        :host{position:fixed;inset:0;z-index:2147482000;display:grid;place-items:center;background:#0009;color:#eef5ff}
        .dialog{width:min(520px,calc(100vw - 32px));padding:18px;border:1px solid #36516e;border-radius:14px;background:#101a27;box-shadow:0 24px 70px #0009}
        h2{margin:0 0 8px}p{color:#a0b4c8;line-height:1.5}.actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}
        button,a{padding:9px 12px;border:1px solid #315f83;border-radius:8px;background:#15334d;color:#eef5ff;text-decoration:none;cursor:pointer;font-weight:700}
      </style>
      <section class="dialog" role="dialog" aria-modal="true">
        <h2>${this.#escape(model?.title || "MakerWorld")}</h2>
        <p>Das Modell wird über den nativen MakerWorld-Browser geladen. Druckprofil und Platten werden im großen Detaildialog ausgewählt.</p>
        <div class="actions">
          ${model?.model_url ? `<a href="${this.#escape(model.model_url)}" target="_blank" rel="noopener noreferrer">MakerWorld öffnen ↗</a>` : ""}
          <button type="button" id="close">Schließen</button>
        </div>
      </section>`;
    this.#root.querySelector<HTMLButtonElement>("#close")?.addEventListener("click", () => this.remove());
  }

  #escape(value: unknown): string {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[character] || character));
  }
}

if (!customElements.get("makerworld-import-dialog")) {
  customElements.define("makerworld-import-dialog", MakerWorldImportDialog);
}
