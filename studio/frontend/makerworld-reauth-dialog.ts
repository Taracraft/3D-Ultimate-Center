import { callHomeAssistantOptionsFlow } from "./ha-api-transport.js";

type Flow = Readonly<{
  type: string;
  flow_id?: string;
  step_id?: string;
  data_schema?: readonly Readonly<{ name: string; required?: boolean; default?: unknown }>[];
  errors?: Readonly<Record<string, string>>;
}>;
type FlowCall = (method: "POST" | "DELETE", flowId: string | null, input?: unknown) => Promise<Flow>;
const identifier = /^[A-Za-z0-9_-]{1,128}$/;

/** Only a classified cloud-account rejection during this import may open login. */
export function makerWorldReauthenticationEntry(error: unknown): string | null {
  if (error === null || typeof error !== "object") return null;
  const value = error as { code?: unknown; details?: { upstream_status?: unknown; config_entry_id?: unknown } };
  const entry = value.details?.config_entry_id;
  return value.code === "makerworld_account_unauthorized" && value.details?.upstream_status === 401
    && typeof entry === "string" && identifier.test(entry) ? entry : null;
}

/** Existing HA options-flow API; this object never retains passwords or codes. */
export class MakerWorldReauthenticationFlow {
  private flowId: string | null = null;
  private closed = false;
  constructor(private readonly entryId: string, private readonly call: FlowCall = callHomeAssistantOptionsFlow<Flow>) {
    if (!identifier.test(entryId)) throw new Error("Ungültiger Studio-Kontozugang.");
  }
  private async accept(flow: Flow): Promise<Flow> {
    if (typeof flow.flow_id === "string" && identifier.test(flow.flow_id)) {
      if (this.flowId && this.flowId !== flow.flow_id) {
        await this.cancel(); throw new Error("Der Home-Assistant-Anmeldedialog hat sich geändert. Bitte erneut öffnen.");
      }
      this.flowId = flow.flow_id;
    }
    if (this.closed) {
      if (flow.type !== "create_entry" && this.flowId) await this.call("DELETE", this.flowId).catch(() => {});
      return { type: "abort" };
    }
    if (flow.type === "create_entry" || flow.type === "abort") { this.closed = true; return flow; }
    if (flow.type !== "form" || !this.flowId || !["init", "cloud_reauthenticate", "cloud_code"].includes(flow.step_id || "")) {
      await this.cancel();
      throw new Error("Der Home-Assistant-Anmeldedialog ist nicht verfügbar. Bitte die Studio-Integration konfigurieren.");
    }
    return flow;
  }
  async start(): Promise<Flow> {
    if (this.closed || this.flowId) throw new Error("Der Anmeldedialog wurde bereits gestartet.");
    const initial = await this.accept(await this.call("POST", null, { handler: this.entryId }));
    if (initial.type !== "form" || initial.step_id !== "init") return initial;
    const schema = initial.data_schema;
    if (!schema?.some((field) => field.name === "cloud_reauthenticate")) {
      await this.cancel(); throw new Error("Bitte die Studio-Integration aktualisieren, um den Anmeldedialog zu verwenden.");
    }
    const input: Record<string, unknown> = { cloud_reauthenticate: true };
    const sensitive = /password|verification|token|secret|access_code/i;
    for (const field of schema) {
      if (!field.required || field.name === "cloud_reauthenticate") continue;
      if (sensitive.test(field.name) || field.default === undefined || field.default === null) {
        await this.cancel(); throw new Error("Bitte die Studio-Integration konfigurieren, um dich erneut anzumelden.");
      }
      input[field.name] = field.default;
    }
    return this.accept(await this.call("POST", this.flowId, input));
  }
  async submit(input: Readonly<Record<string, string>>): Promise<Flow> {
    if (this.closed || !this.flowId) throw new Error("Der Anmeldedialog ist nicht mehr aktiv.");
    return this.accept(await this.call("POST", this.flowId, input));
  }
  async cancel(): Promise<void> {
    if (this.closed) return;
    this.closed = true;
    if (this.flowId) await this.call("DELETE", this.flowId).catch(() => {});
  }
}

export function openMakerWorldReauthentication(parent: HTMLElement, entryId: string, signal?: AbortSignal): Promise<boolean> {
  if (signal?.aborted || !parent.isConnected) return Promise.resolve(false);
  const document = parent.ownerDocument;
  const dialog = document.createElement("dialog");
  dialog.className = "mw-reauth-dialog";
  dialog.setAttribute("aria-label", "Bambu-Konto erneut anmelden");
  dialog.innerHTML = `<style>
.mw-reauth-dialog{color-scheme:dark;box-sizing:border-box;width:min(440px,calc(100vw - 24px));max-height:calc(100dvh - 24px);overflow:auto;border:1px solid #626262;border-radius:12px;padding:22px;background:#242424;color:#f5f5f5;font:14px/1.5 Inter,Segoe UI,sans-serif}.mw-reauth-dialog::backdrop{background:#000b}.mw-reauth-dialog h2{font-size:20px;margin:0 0 8px}.mw-reauth-dialog p{margin:8px 0 16px}.mw-reauth-dialog label{display:grid;gap:5px;margin:12px 0}.mw-reauth-dialog input,.mw-reauth-dialog select,.mw-reauth-dialog button{box-sizing:border-box;min-height:44px;font:inherit;border:1px solid #686868;border-radius:7px;padding:9px;background:#171717;color:#fff}.mw-reauth-dialog input,.mw-reauth-dialog select{width:100%}.mw-reauth-dialog .actions{display:flex;gap:10px;justify-content:flex-end;margin-top:18px}.mw-reauth-dialog button{cursor:pointer}.mw-reauth-dialog button[type=submit]{background:#00c90e;color:#071b08;font-weight:700}.mw-reauth-dialog .error{color:#ffc9ce}
    </style><h2>Bambu-Konto erneut anmelden</h2><p>Deine Anmeldung wurde nicht mehr akzeptiert. Melde dich erneut an und wähle danach den gewünschten Import noch einmal aus.</p><form><div class="fields"></div><p class="status" role="status" aria-live="polite">Anmeldedialog wird geöffnet …</p><div class="actions"><button type="button" data-cancel>Abbrechen</button><button type="submit" disabled>Weiter</button></div></form>`;
  parent.append(dialog);
  const flow = new MakerWorldReauthenticationFlow(entryId);
  const form = dialog.querySelector<HTMLFormElement>("form")!;
  const fields = dialog.querySelector<HTMLElement>(".fields")!;
  const status = dialog.querySelector<HTMLElement>(".status")!;
  const submit = dialog.querySelector<HTMLButtonElement>('button[type="submit"]')!;
  let busy = true, settled = false, step = "";
  return new Promise<boolean>((resolve) => {
    const clear = (): void => { form.querySelectorAll<HTMLInputElement>("input").forEach((input) => { input.value = ""; }); };
    const finish = (connected: boolean): void => {
      if (settled) return;
      settled = true;
      clear(); signal?.removeEventListener("abort", cancel);
      if (dialog.open) dialog.close();
      dialog.remove();
      if (!connected) void flow.cancel();
      resolve(connected);
    };
    const cancel = (): void => finish(false);
    const render = (result: Flow): void => {
      if (settled || signal?.aborted || !parent.isConnected) { finish(false); return; }
      if (result.type === "create_entry") { finish(true); return; }
      if (result.type === "abort") { finish(false); return; }
      step = result.step_id || "";
      clear(); fields.replaceChildren();
      const add = (name: string, labelText: string, type: string, autocomplete: string): void => {
        const label = document.createElement("label"); label.textContent = labelText;
        const input = document.createElement("input"); input.name = name; input.type = type; input.required = true; input.setAttribute("autocomplete", autocomplete);
        if (type !== "password" && name !== "verification_code") {
          const value = result.data_schema?.find((field) => field.name === name)?.default;
          if (typeof value === "string") input.value = value;
        }
        if (name === "verification_code") input.inputMode = "numeric";
        label.append(input); fields.append(label);
      };
      if (step === "cloud_code") add("verification_code", "Verifikationscode aus deiner E-Mail", "text", "one-time-code");
      else if (step === "cloud_reauthenticate") {
        add("cloud_email", "Bambu-E-Mail-Adresse", "email", "username");
        add("password", "Bambu-Passwort", "password", "current-password");
        const label = document.createElement("label"); label.textContent = "Kontoregion";
        const region = document.createElement("select"); region.name = "cloud_region";
        for (const [value, text] of [["global", "Global"], ["china", "China"]]) { const option = document.createElement("option"); option.value = value!; option.textContent = text!; region.append(option); }
        const defaultRegion = result.data_schema?.find((field) => field.name === "cloud_region")?.default;
        region.value = defaultRegion === "china" ? "china" : "global"; label.append(region); fields.append(label);
      } else { status.textContent = "Bitte die Studio-Integration konfigurieren."; return; }
      status.textContent = Object.keys(result.errors || {}).length
        ? "Anmeldung nicht erfolgreich. Bitte deine Eingabe prüfen und erneut versuchen."
        : step === "cloud_code" ? "Bambu hat dir einen Verifikationscode gesendet." : "Die Anmeldung erfolgt über Home Assistant.";
      busy = false; submit.disabled = false;
      fields.querySelector<HTMLInputElement>("input")?.focus();
    };
    signal?.addEventListener("abort", cancel, { once: true });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); cancel(); });
    dialog.querySelector("[data-cancel]")!.addEventListener("click", cancel);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (busy || settled || !form.reportValidity()) return;
      busy = true; submit.disabled = true; status.textContent = "Anmeldung wird geprüft …";
      const input: Record<string, string> = {};
      const names = step === "cloud_code" ? ["verification_code"] : ["cloud_email", "password", "cloud_region"];
      for (const name of names) input[name] = form.querySelector<HTMLInputElement | HTMLSelectElement>(`[name="${name}"]`)?.value || "";
      clear();
      void flow.submit(input).then(render, () => {
        if (!settled) { busy = false; submit.disabled = false; status.textContent = "Die Anmeldung konnte nicht fortgesetzt werden. Bitte erneut versuchen."; }
      }).finally(() => { for (const name of Object.keys(input)) delete input[name]; });
    });
    try { dialog.showModal(); }
    catch { finish(false); return; }
    void flow.start().then(render, () => {
      if (!settled) { status.textContent = "Der Anmeldedialog konnte nicht geöffnet werden. Bitte die Studio-Integration konfigurieren."; }
    });
  });
}
