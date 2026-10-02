export type V6DialogOption = Readonly<{
  value: string;
  label: string;
  description?: string;
}>;

export type V6ActionDialogRequest = Readonly<{
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
    options: readonly V6DialogOption[];
  }>;
}>;

export type V6ActionDialogResult = Readonly<{
  inputValue: string;
  selectedValue: string;
}>;

type PendingDialog = Readonly<{
  resolve: (value: V6ActionDialogResult | null) => void;
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

export class V6ActionDialog extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #request: V6ActionDialogRequest | null = null;
  #pending: PendingDialog | null = null;

  connectedCallback(): void {
    this.hidden = true;
  }

  open(request: V6ActionDialogRequest): Promise<V6ActionDialogResult | null> {
    this.#finish(null);
    this.#request = request;
    this.hidden = false;
    this.#render();
    return new Promise<V6ActionDialogResult | null>((resolve) => {
      this.#pending = { resolve };
      queueMicrotask(() => {
        const input = this.#root.querySelector<HTMLInputElement>("#dialog-input");
        const select = this.#root.querySelector<HTMLSelectElement>("#dialog-select");
        if (input) {
          input.focus();
          input.select();
        } else if (select) {
          select.focus();
        } else {
          this.#root.querySelector<HTMLButtonElement>("[data-action='confirm']")?.focus();
        }
      });
    });
  }

  async confirm(request: Omit<V6ActionDialogRequest, "input" | "select">): Promise<boolean> {
    return (await this.open(request)) !== null;
  }

  async requestText(request: Omit<V6ActionDialogRequest, "input" | "select"> & Readonly<{
    input: NonNullable<V6ActionDialogRequest["input"]>;
  }>): Promise<string | null> {
    const result = await this.open(request);
    return result?.inputValue ?? null;
  }

  async choose(request: Omit<V6ActionDialogRequest, "input" | "select"> & Readonly<{
    select: NonNullable<V6ActionDialogRequest["select"]>;
  }>): Promise<string | null> {
    const result = await this.open(request);
    return result?.selectedValue ?? null;
  }

  close(): void {
    this.#finish(null);
  }

  #finish(result: V6ActionDialogResult | null): void {
    const pending = this.#pending;
    this.#pending = null;
    this.#request = null;
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
      :host{position:fixed;inset:0;z-index:2147483200;display:grid;place-items:center;padding:18px;background:#02070dc9;color:#eff7ff;font:13px/1.45 Inter,Segoe UI,sans-serif;backdrop-filter:blur(6px)}
      :host([hidden]){display:none}
      *{box-sizing:border-box}
      .dialog{width:min(560px,calc(100vw - 36px));overflow:hidden;border:1px solid #3e6b90;border-radius:15px;background:#0d1824;box-shadow:0 28px 90px #000c}
      .head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:16px 18px;border-bottom:1px solid #293d51;background:#111f2d}
      .head h2{margin:0;font-size:18px}.head button{width:34px;height:34px;padding:0;border:1px solid #45627b;border-radius:50%;background:#142536;color:#fff;font-size:20px;cursor:pointer}
      .body{display:grid;gap:13px;padding:18px}.message{font-size:15px;font-weight:700}.detail{padding:11px;border:1px solid #2a4056;border-radius:9px;background:#09131e;color:#9eb3c7;white-space:pre-wrap;overflow-wrap:anywhere}
      .field{display:grid;gap:6px;color:#a8bfd3;font-size:11px;font-weight:700}.field input,.field select{width:100%;min-height:42px;padding:9px 10px;border:1px solid #31506e;border-radius:8px;background:#07111c;color:#fff;font:inherit}.field input:focus,.field select:focus{outline:2px solid #42c8ff66;border-color:#42c8ff}
      .error{padding:9px;border:1px solid #8f3f4b;border-radius:8px;background:#351b21;color:#ffd7dc}
      .footer{display:flex;justify-content:flex-end;gap:8px;padding:13px 18px;border-top:1px solid #293d51;background:#0a1520}.footer button{min-width:110px;padding:9px 12px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef6ff;cursor:pointer;font-weight:800}.footer .confirm{border-color:#45c5ff;background:#17638a}.footer .confirm.danger{border-color:#a74653;background:#4a1d25;color:#ffe3e6}
      @media(max-width:620px){:host{padding:7px}.dialog{width:100%;border-radius:10px}.footer button{flex:1;min-width:0}}
    </style><section class="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><header class="head"><div><h2 id="dialog-title">${escapeHtml(request.title)}</h2></div><button type="button" data-action="cancel" aria-label="Schließen">×</button></header><main class="body"><div class="message">${escapeHtml(request.message)}</div>${request.detail ? `<div class="detail">${escapeHtml(request.detail)}</div>` : ""}${input}${select}<div class="error" id="dialog-error" hidden></div></main><footer class="footer"><button type="button" data-action="cancel">${escapeHtml(request.cancelLabel ?? "Abbrechen")}</button><button type="button" class="confirm ${request.danger ? "danger" : ""}" data-action="confirm">${escapeHtml(request.confirmLabel ?? "Bestätigen")}</button></footer></section>`;

    this.#root.querySelectorAll<HTMLElement>("[data-action='cancel']").forEach((element) => {
      element.addEventListener("click", () => this.#finish(null));
    });
    this.#root.querySelector<HTMLElement>("[data-action='confirm']")?.addEventListener("click", () => this.#confirm());
    this.#root.querySelector<HTMLElement>(".dialog")?.addEventListener("keydown", (event) => {
      const keyboard = event as KeyboardEvent;
      if (keyboard.key === "Escape") {
        keyboard.preventDefault();
        this.#finish(null);
      }
      if (keyboard.key === "Enter" && !(keyboard.target instanceof HTMLTextAreaElement)) {
        keyboard.preventDefault();
        this.#confirm();
      }
    });
    this.#root.addEventListener("click", (event) => {
      if (event.target === this.#root.querySelector(".dialog")) return;
    }, { once: true });
  }
}

if (!customElements.get("v6-action-dialog")) {
  customElements.define("v6-action-dialog", V6ActionDialog);
}
