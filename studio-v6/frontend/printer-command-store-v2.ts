import "./v6-action-dialog.js";
import { errorMessage } from "./ha-api-transport.js";
import { jobActivityStore } from "./job-activity-store.js";
import {
  commandAvailable,
  commandConfirmation,
  commandLabel,
  type PrinterCommand,
} from "./printer-command-policy.js";
import {
  issueActionLabel,
  issueCode,
  issueMessage,
  issueRecommendedCommand,
  type PrinterIssue,
} from "./printer-issues.js";
import type { V6ActionDialog } from "./v6-action-dialog.js";
import { PRINT_SPEED_MODES, type PrintSpeedLevel } from "./print-live-telemetry.js";
import {
  v6Api,
  type V6CommandCapability,
  type V6Job,
  type V6Printer,
} from "./v6-api.js";

export type PrinterCommandSnapshot = Readonly<{
  busyPrinterId: string;
  busyCommand: PrinterCommand | "";
  message: string;
  error: string;
  updatedAt: number;
}>;

type Listener = (snapshot: PrinterCommandSnapshot) => void;
type ExecuteRequest = Readonly<{
  printer: V6Printer;
  command: PrinterCommand;
  capabilities: readonly V6CommandCapability[];
  job?: V6Job | null;
  speedLevel?: PrintSpeedLevel;
}>;

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

class PrinterCommandStore {
  readonly #listeners = new Set<Listener>();
  #snapshot: PrinterCommandSnapshot = {
    busyPrinterId: "",
    busyCommand: "",
    message: "",
    error: "",
    updatedAt: 0,
  };

  get snapshot(): PrinterCommandSnapshot { return this.#snapshot; }

  subscribe(listener: Listener): () => void {
    this.#listeners.add(listener);
    listener(this.#snapshot);
    return () => this.#listeners.delete(listener);
  }

  isBusy(printerId?: unknown): boolean {
    if (!this.#snapshot.busyPrinterId) return false;
    return printerId === undefined || String(printerId || "") === this.#snapshot.busyPrinterId;
  }

  clearFeedback(): void {
    if (!this.#snapshot.message && !this.#snapshot.error) return;
    this.#snapshot = { ...this.#snapshot, message: "", error: "", updatedAt: Date.now() };
    this.#emit();
  }

  async execute(request: ExecuteRequest): Promise<void> {
    const printerId = String(request.printer.printer_id || "").trim();
    if (!printerId) throw new Error("Der Drucker besitzt keine gültige ID.");
    if (this.isBusy()) throw new Error("Ein Druckerbefehl wird bereits verarbeitet.");
    if (!commandAvailable(request.command, request.printer, request.capabilities, request.job)) {
      throw new Error(`${commandLabel(request.command)} ist im aktuellen Druckerzustand nicht verfügbar.`);
    }
    if (request.command === "speed" && !PRINT_SPEED_MODES.some((mode) => mode.level === request.speedLevel)) {
      throw new Error("Ungültige Druckgeschwindigkeit. Erlaubt sind nur 50, 100, 125 oder 166 Prozent.");
    }

    this.#snapshot = {
      busyPrinterId: printerId,
      busyCommand: request.command,
      message: request.command === "stop"
        ? "Stopp angefordert – der Druckerstatus wird bis zur Bestätigung überwacht."
        : request.command === "retry"
          ? "Erneuter AMS-/Filamentversuch wird an den Drucker gesendet …"
          : request.command === "resume"
            ? "Fortsetzung wird an den Drucker gesendet …"
            : request.command === "speed"
              ? "Druckgeschwindigkeit wird geändert …"
              : "",
      error: "",
      updatedAt: Date.now(),
    };
    this.#emit();

    try {
      const result = await v6Api.executeCommand(printerId, request.command, request.command === "speed" ? { speed_level: request.speedLevel } : undefined);
      if (request.command === "stop" && result.confirmed !== true) {
        throw new Error("Der Stop-Befehl wurde gesendet, aber der Drucker hat den Abbruch nicht bestätigt.");
      }
      if (request.command === "retry" && result.accepted !== true) {
        throw new Error("Der Drucker hat den erneuten AMS-/Filamentversuch nicht angenommen.");
      }
      const attempts = Math.max(1, Number(result.attempts) || 1);
      const finalState = String(result.final_state || "").trim();
      const responseMessage = String(result.message || "").trim();
      this.#snapshot = {
        ...this.#snapshot,
        message: responseMessage || (request.command === "stop"
          ? `Druckabbruch bestätigt${attempts > 1 ? ` nach ${attempts} Versuchen` : ""}${finalState ? ` · Zustand: ${finalState}` : ""}.`
          : request.command === "retry"
            ? "Der Drucker hat den erneuten AMS-/Filamentversuch angenommen. Der Fehlerstatus wird weiter überwacht."
            : request.command === "resume"
              ? "Der Drucker hat die Fortsetzung angenommen. Der Druckstatus wird weiter überwacht."
              : request.command === "speed"
                ? "Die neue Druckgeschwindigkeit wurde vom Drucker angenommen."
                : `${commandLabel(request.command)} wurde vom Drucker angenommen.`),
        error: "",
        updatedAt: Date.now(),
      };
      this.#emit();
      await jobActivityStore.refresh();
    } catch (error) {
      this.#snapshot = {
        ...this.#snapshot,
        message: "",
        error: errorMessage(error),
        updatedAt: Date.now(),
      };
      this.#emit();
      throw error;
    } finally {
      this.#snapshot = {
        ...this.#snapshot,
        busyPrinterId: "",
        busyCommand: "",
        updatedAt: Date.now(),
      };
      this.#emit();
    }
  }

  #emit(): void {
    for (const listener of this.#listeners) listener(this.#snapshot);
  }
}

export const printerCommandStore = new PrinterCommandStore();

export class Ultimate3DPrinterActions extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #printer: V6Printer | null = null;
  #job: V6Job | null = null;
  #issue: PrinterIssue | null = null;
  #issueMode = false;
  #capabilities: readonly V6CommandCapability[] = [];
  #snapshot: PrinterCommandSnapshot = printerCommandStore.snapshot;
  #unsubscribe: (() => void) | null = null;
  #mounted = false;
  #confirming = false;

  set printer(value: V6Printer | null) { this.#printer = value; this.#update(); }
  set job(value: V6Job | null) { this.#job = value; this.#update(); }
  set issue(value: PrinterIssue | null) { this.#issue = value; this.#update(); }
  set issueMode(value: boolean) { this.#issueMode = Boolean(value); this.#update(); }
  set capabilities(value: readonly V6CommandCapability[]) { this.#capabilities = value; this.#update(); }

  connectedCallback(): void {
    this.#mount();
    if (this.#unsubscribe) return;
    this.#unsubscribe = printerCommandStore.subscribe((snapshot) => {
      this.#snapshot = snapshot;
      this.#update();
    });
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  async #run(command: PrinterCommand): Promise<void> {
    const printer = this.#printer;
    if (this.#confirming || !printer || !commandAvailable(command, printer, this.#capabilities, this.#job)) return;
    const requestedJob = String(this.#job?.job_id || this.#job?.id || "");
    const dialog = this.#root.querySelector<V6ActionDialog>("#printer-command-dialog");
    const issueCommand = Boolean(this.#issue && (command === "resume" || command === "retry"));
    const issueDetail = issueCommand && this.#issue
      ? `\n\nAktive/zuletzt gemeldete Störung: ${issueCode(this.#issue)}\n${issueMessage(this.#issue)}\n\nNur ausführen, wenn die physische Ursache am Drucker tatsächlich behoben wurde.`
      : "";
    const actionLabel = issueCommand && this.#issue ? issueActionLabel(this.#issue) : commandLabel(command);
    this.#confirming = true;
    const confirmed = await dialog?.confirm({
      title: actionLabel,
      message: issueCommand ? "Ist die angezeigte Störung wirklich behoben?" : `${commandLabel(command)} wirklich ausführen?`,
      detail: command === "stop"
        ? `${commandConfirmation(command, printer, this.#job)}\n\nV6 sendet den Stop-Befehl bei ausbleibender Bestätigung automatisch ein zweites Mal und meldet erst danach „gestoppt“.`
        : `${commandConfirmation(command, printer, this.#job)}${issueDetail}`,
      confirmLabel: issueCommand ? actionLabel : commandLabel(command),
      cancelLabel: "Zurück",
      danger: command === "stop",
    });
    this.#confirming = false;
    if (!confirmed) return;
    const currentPrinter = this.#printer;
    if (!this.isConnected || !currentPrinter || currentPrinter.printer_id !== printer.printer_id
      || String(this.#job?.job_id || this.#job?.id || "") !== requestedJob) return;
    try {
      await printerCommandStore.execute({
        printer: currentPrinter,
        command,
        capabilities: this.#capabilities,
        job: this.#job,
      });
    } catch {
      // Der Store hält die sichtbare Fehlermeldung.
    }
  }

  #button(command: PrinterCommand, danger = false): string {
    const printer = this.#printer;
    const busy = Boolean(printer && printerCommandStore.isBusy(printer.printer_id));
    const enabled = Boolean(
      printer && !busy && commandAvailable(command, printer, this.#capabilities, this.#job),
    );
    const issueCommand = Boolean(this.#issue && command === issueRecommendedCommand(this.#issue));
    const baseLabel = issueCommand && this.#issue ? issueActionLabel(this.#issue) : commandLabel(command);
    const label = busy && this.#snapshot.busyCommand === command
      ? command === "stop" ? "Stopp wird bestätigt …" : "Wird gesendet …"
      : baseLabel;
    return `<button type="button" class="${danger ? "danger" : issueCommand ? "resume-issue" : ""}" data-action="${command}" ${enabled ? "" : "disabled"}>${escapeHtml(label)}</button>`;
  }

  #mount(): void {
    if (this.#mounted) return;
    this.#root.innerHTML = `<style>
      :host{display:block}
      *{box-sizing:border-box}
      .actions{display:flex;gap:8px;flex-wrap:wrap}
      button{min-height:38px;padding:8px 10px;border:1px solid #32658b;border-radius:8px;background:#14324b;color:#eef5ff;font-weight:700;cursor:pointer}
      button.resume-issue{border-color:#3e9d6b;background:#123522;color:#b9ffd2}
      button.danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}
      button:disabled{opacity:.4;cursor:not-allowed}
      .feedback{margin-top:8px;padding:8px 10px;border-radius:8px;background:#102b1d;color:#8ff0b5;font-size:12px}
      .feedback.error{background:#3a171d;color:#ffd7dc}
    </style><div class="actions" id="printer-command-actions"></div><div class="feedback" id="printer-command-feedback" hidden></div><v6-action-dialog id="printer-command-dialog"></v6-action-dialog>`;
    this.#mounted = true;
    this.#update();
  }

  #update(): void {
    if (!this.isConnected) return;
    this.#mount();
    const actions = this.#root.querySelector<HTMLElement>("#printer-command-actions");
    const feedback = this.#root.querySelector<HTMLElement>("#printer-command-feedback");
    if (!actions || !feedback) return;
    if (this.#issueMode && this.#issue) {
      const recommended = issueRecommendedCommand(this.#issue);
      actions.innerHTML = `${this.#button(recommended)}${this.#button("stop", true)}`;
    } else {
      actions.innerHTML = `${this.#button("pause")}${this.#button("resume")}${this.#button("stop", true)}`;
    }
    actions.querySelectorAll<HTMLButtonElement>("[data-action]").forEach((button) => {
      button.addEventListener("click", () => void this.#run(button.dataset.action as PrinterCommand));
    });
    const message = this.#snapshot.error || this.#snapshot.message;
    feedback.hidden = !message;
    feedback.textContent = message;
    feedback.classList.toggle("error", Boolean(this.#snapshot.error));
  }
}

if (!customElements.get("ultimate-3d-printer-actions")) {
  customElements.define("ultimate-3d-printer-actions", Ultimate3DPrinterActions);
}
