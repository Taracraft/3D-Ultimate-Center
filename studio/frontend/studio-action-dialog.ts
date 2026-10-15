export type StudioDialogOption = Readonly<{
  value: string;
  label: string;
  description?: string;
}>;

export type StudioActionDialogRequest = Readonly<{
  title: string;
  message: string;
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  input?: Readonly<{
    label: string;
    value?: string;
    placeholder?: string;
    maxLength?: number;
  }>;
  select?: Readonly<{
    label: string;
    value?: string;
    options: readonly StudioDialogOption[];
  }>;
}>;

export type StudioActionDialogResult = Readonly<{
  inputValue: string;
  selectedValue: string;
}>;

type PendingDialog = Readonly<{
  resolve: (value: StudioActionDialogResult | null) => void;
}>;

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

export class StudioActionDialog extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #request: StudioActionDialogRequest | null = null;
  #pending: PendingDialog | null = null;

  connectedCallback(): void {
    if (!this.#pending) this.hidden = true;
  }

  disconnectedCallback(): void {
    this.#finish(null);
  }

  open(request: StudioActionDialogRequest): Promise<StudioActionDialogResult | null> {
    this.#finish(null);
    this.#request = request;
    this.hidden = false;
    return new Promise<StudioActionDialogResult | null>((resolve) => {
      const pending = { resolve };
      this.#pending = pending;
      this.#render();
      const dialog = this.#root.querySelector<HTMLDialogElement>("dialog");
      try {
        if (!dialog) throw new Error("Dialog fehlt");
        dialog.showModal();
      } catch {
        this.#finish(null);
        return;
      }
      queueMicrotask(() => {
        if (this.#pending !== pending) return;
        const input = this.#root.querySelector<HTMLInputElement>("#dialog-input");
        const select = this.#root.querySelector<HTMLSelectElement>("#dialog-select");
        if (input) {
          input.focus();
          input.select();
        } else if (select) {
          select.focus();
        } else {
          this.#root.querySelector<HTMLButtonElement>(request.danger ? "[data-action='cancel']" : "[data-action='confirm']")?.focus();
        }
      });
    });
  }

  async confirm(request: Omit<StudioActionDialogRequest, "input" | "select">): Promise<boolean> {
    return (await this.open(request)) !== null;
  }

  async requestText(request: Omit<StudioActionDialogRequest, "input" | "select"> & Readonly<{
    input: NonNullable<StudioActionDialogRequest["input"]>;
  }>): Promise<string | null> {
    const result = await this.open(request);
    return result?.inputValue ?? null;
  }

  async choose(request: Omit<StudioActionDialogRequest, "input" | "select"> & Readonly<{
    select: NonNullable<StudioActionDialogRequest["select"]>;
  }>): Promise<string | null> {
    const result = await this.open(request);
    return result?.selectedValue ?? null;
  }

  close(): void {
    this.#finish(null);
  }

  #finish(result: StudioActionDialogResult | null): void {
    const pending = this.#pending;
    this.#pending = null;
    this.#request = null;
    const dialog = this.#root.querySelector<HTMLDialogElement>("dialog");
    if (dialog?.open) dialog.close();
    this.hidden = true;
    this.#root.replaceChildren();
    pending?.resolve(result);
  }

  #confirm(): void {
    const request = this.#request;
    if (!request) return;
    const input = this.#root.querySelector<HTMLInputElement>("#dialog-input");
    const select = this.#root.querySelector<HTMLSelectElement>("#dialog-select");
    const inputValue = input?.value.trim() ?? "";
    if (request.input && !inputValue) {
      const error = this.#root.querySelector<HTMLElement>("#dialog-error");
      if (error) {
        error.textContent = `${request.input.label} darf nicht leer sein.`;
        error.hidden = false;
      }
      input?.focus();
      return;
    }
    this.#finish({
      inputValue,
      selectedValue: select?.value ?? "",
    });
  }

  #render(): void {
    const request = this.#request;
    if (!request) return;
    const input = request.input
      ? `<label class="field"><span>${escapeHtml(request.input.label)}</span><input id="dialog-input" type="text" value="${escapeHtml(request.input.value ?? "")}" placeholder="${escapeHtml(request.input.placeholder ?? "")}" maxlength="${request.input.maxLength ?? 160}" autocomplete="off"></label>`
      : "";
    const select = request.select
      ? `<label class="field"><span>${escapeHtml(request.select.label)}</span><select id="dialog-select">${request.select.options.map((option) => `<option value="${escapeHtml(option.value)}" ${option.value === request.select?.value ? "selected" : ""}>${escapeHtml(option.label)}${option.description ? ` — ${escapeHtml(option.description)}` : ""}</option>`).join("")}</select></label>`
      : "";

    this.#root.innerHTML = `<style>
      :host{display:contents;color:#eff7ff;font:13px/1.45 Inter,Segoe UI,sans-serif}
      :host([hidden]){display:none}
      *{box-sizing:border-box}
      .dialog{width:min(560px,calc(100vw - 24px));max-height:calc(100dvh - 24px);margin:auto;padding:0;display:grid;grid-template-rows:auto minmax(0,1fr) auto;overflow:hidden;color:#eff7ff;font:inherit;border:1px solid #3e6b90;border-radius:15px;background:#0d1824;box-shadow:0 28px 90px #000c}
      .dialog:not([open]){display:none}.dialog::backdrop{background:#02070dc9;backdrop-filter:blur(6px)}
      .head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:16px 18px;border-bottom:1px solid #293d51;background:#111f2d}
      .head h2{margin:0;font-size:18px}.head button{width:34px;height:34px;padding:0;border:1px solid #45627b;border-radius:50%;background:#142536;color:#fff;font-size:20px;cursor:pointer}
      .body{display:grid;gap:13px;padding:18px;min-height:0;overflow:auto;overscroll-behavior:contain}.message{font-size:15px;font-weight:700}.detail{padding:11px;border:1px solid #2a4056;border-radius:9px;background:#09131e;color:#9eb3c7;white-space:pre-wrap;overflow-wrap:anywhere}
      .field{display:grid;gap:6px;color:#a8bfd3;font-size:11px;font-weight:700}.field input,.field select{width:100%;min-height:42px;padding:9px 10px;border:1px solid #31506e;border-radius:8px;background:#07111c;color:#fff;font:inherit}.field input:focus,.field select:focus{outline:2px solid #42c8ff66;border-color:#42c8ff}
      .error{padding:9px;border:1px solid #8f3f4b;border-radius:8px;background:#351b21;color:#ffd7dc}
      .footer{display:flex;justify-content:flex-end;gap:8px;padding:13px 18px;border-top:1px solid #293d51;background:#0a1520}.footer button{min-width:110px;padding:9px 12px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef6ff;cursor:pointer;font-weight:800}.footer .confirm{border-color:#45c5ff;background:#17638a}.footer .confirm.danger{border-color:#a74653;background:#4a1d25;color:#ffe3e6}
      @media(max-width:620px){.dialog{width:calc(100vw - 14px);max-height:calc(100dvh - 14px);border-radius:10px}.footer button{flex:1;min-width:0}}
    </style><dialog class="dialog" aria-modal="true" aria-labelledby="dialog-title"><header class="head"><div><h2 id="dialog-title">${escapeHtml(request.title)}</h2></div><button type="button" data-action="cancel" aria-label="Schließen">×</button></header><main class="body"><div class="message">${escapeHtml(request.message)}</div>${request.detail ? `<div class="detail">${escapeHtml(request.detail)}</div>` : ""}${input}${select}<div class="error" id="dialog-error" hidden></div></main><footer class="footer"><button type="button" data-action="cancel">${escapeHtml(request.cancelLabel ?? "Abbrechen")}</button><button type="button" class="confirm ${request.danger ? "danger" : ""}" data-action="confirm">${escapeHtml(request.confirmLabel ?? "Bestätigen")}</button></footer></dialog>`;

    this.#root.querySelectorAll<HTMLElement>("[data-action='cancel']").forEach((element) => {
      element.addEventListener("click", () => this.#finish(null));
    });
    this.#root.querySelector<HTMLElement>("[data-action='confirm']")?.addEventListener("click", () => this.#confirm());
    const dialog = this.#root.querySelector<HTMLDialogElement>("dialog");
    dialog?.addEventListener("cancel", (event) => {
      event.preventDefault();
      this.#finish(null);
    });
    dialog?.addEventListener("close", () => {
      if (this.#root.querySelector("dialog") === dialog) this.#finish(null);
    });
    dialog?.addEventListener("keydown", (event) => {
      // Let each native button keep its own Enter/Space action, including Cancel.
      if (event.key === "Enter" && !event.isComposing && event.target === this.#root.querySelector("#dialog-input")) {
        event.preventDefault();
        this.#confirm();
      }
    });
  }
}

if (!customElements.get("studio-action-dialog")) {
  customElements.define("studio-action-dialog", StudioActionDialog);
}
