import { StudioApiClient } from "./api-client.js";
import { PROGRESS_STYLES, progressMarkup } from "./progress-ui.js";
import { UploadController, type UploadSource, type UploadTarget } from "./upload-controller.js";

export class Ultimate3DUploadDialog extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #controller = new UploadController(new StudioApiClient());
  #source: UploadSource = "studio";
  #target: UploadTarget = "gallery";
  #busy = false;

  connectedCallback(): void {
    this.#source = (this.getAttribute("source") as UploadSource | null) ?? "studio";
    this.#target = (this.getAttribute("target") as UploadTarget | null) ?? "gallery";
    this.#render();
  }

  open(): void {
    this.hidden = false;
    this.#root.querySelector<HTMLInputElement>("input[type=file]")?.focus();
  }

  close(): void {
    if (this.#busy) return;
    this.hidden = true;
  }

  #render(): void {
    const style = document.createElement("style");
    style.textContent = `
      :host{position:fixed;inset:0;z-index:90;display:grid;place-items:center;color:#eef5ff}
      :host([hidden]){display:none}.backdrop{position:absolute;inset:0;background:#000b;z-index:80}
      .dialog{position:relative;z-index:90;width:min(680px,calc(100vw - 2rem));padding:1rem;border:1px solid #45536a;border-radius:14px;background:#101923;box-shadow:0 24px 80px #000b}
      .drop{display:grid;place-items:center;min-height:220px;padding:22px;border:2px dashed #4f6f91;border-radius:12px;background:#0b141f;text-align:center;color:#b7c8d8;transition:border-color .2s,background .2s}
      .drop:hover{border-color:#43c5ff;background:#0e1b29}.drop input{margin-top:12px;color:#dbeaff}.progress-wrap{margin-top:14px}.actions{display:flex;justify-content:flex-end;gap:.5rem;margin-top:1rem}
      button{padding:9px 12px;border:1px solid #315f83;border-radius:8px;background:#15334d;color:#eef5ff;cursor:pointer;font-weight:700}button:disabled{opacity:.45;cursor:not-allowed}
      ${PROGRESS_STYLES}
    `;
    const backdrop = document.createElement("div");
    backdrop.className = "backdrop";
    backdrop.addEventListener("click", () => this.close());

    const dialog = document.createElement("section");
    dialog.className = "dialog";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("aria-label", "3D-Modell hochladen");

    const drop = document.createElement("label");
    drop.className = "drop";
    drop.innerHTML = '<strong>STL, 3MF, OBJ, STEP oder G-Code hier ablegen</strong><span>oder eine Datei auswählen</span>';
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".stl,.3mf,.obj,.step,.stp,.gcode";
    input.disabled = this.#busy;
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) void this.#upload(file);
    });
    drop.append(input);
    drop.addEventListener("dragover", (event) => event.preventDefault());
    drop.addEventListener("drop", (event) => {
      event.preventDefault();
      if (this.#busy) return;
      const file = event.dataTransfer?.files[0];
      if (file) void this.#upload(file);
    });

    const progressHost = document.createElement("div");
    progressHost.className = "progress-wrap";
    progressHost.id = "progress-host";
    progressHost.innerHTML = progressMarkup({
      label: "Bereit zum Hochladen",
      detail: `Quelle: ${this.#source} · Ziel: ${this.#target}`,
      value: 0,
      tone: "blue",
    });

    const actions = document.createElement("div");
    actions.className = "actions";
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Schließen";
    close.disabled = this.#busy;
    close.addEventListener("click", () => this.close());
    actions.append(close);

    dialog.append(drop, progressHost, actions);
    this.#root.replaceChildren(style, backdrop, dialog);
  }

  #setProgress(label: string, detail: string, value: number | null, indeterminate = false, tone: "blue" | "green" | "amber" | "red" = "blue"): void {
    const host = this.#root.querySelector<HTMLElement>("#progress-host");
    if (!host) return;
    host.innerHTML = progressMarkup({ label, detail, value, indeterminate, tone });
  }

  async #upload(file: File): Promise<void> {
    if (this.#busy) return;
    this.#busy = true;
    this.#render();
    this.#setProgress("Upload wird vorbereitet …", file.name, 2, true, "blue");
    try {
      const result = await this.#controller.upload(
        file,
        this.#source,
        this.#target,
        (update) => {
          const megabytes = `${(update.uploadedBytes / 1024 / 1024).toFixed(1)} / ${(update.totalBytes / 1024 / 1024).toFixed(1)} MB`;
          this.#setProgress(update.fileName, megabytes, update.percent, false, "blue");
        },
      );
      this.#setProgress("Upload abgeschlossen", file.name, 100, false, "green");
      this.dispatchEvent(new CustomEvent("upload-complete", {
        bubbles: true,
        composed: true,
        detail: result,
      }));
      window.setTimeout(() => {
        this.#busy = false;
        this.close();
        this.#render();
      }, 650);
    } catch (error) {
      this.#busy = false;
      const message = error instanceof Error ? error.message : String(error);
      this.#render();
      this.#setProgress("Upload fehlgeschlagen", message, 100, false, "red");
      this.dispatchEvent(new CustomEvent("upload-error", {
        bubbles: true,
        composed: true,
        detail: error,
      }));
    }
  }
}

if (!customElements.get("ultimate-3d-upload-dialog")) {
  customElements.define("ultimate-3d-upload-dialog", Ultimate3DUploadDialog);
}
