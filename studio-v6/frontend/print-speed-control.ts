import { commandAvailable } from "./printer-command-policy.js";
import { printerCommandStore, type PrinterCommandSnapshot } from "./printer-command-store.js";
import {
  PRINT_SPEED_MODES,
  printSpeedLevel,
  type PrintSpeedLevel,
} from "./print-live-telemetry.js";
import type { V6CommandCapability, V6Job, V6Printer } from "./v6-api.js";

export class Ultimate3DPrintSpeedControl extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #printer: V6Printer | null = null;
  #job: V6Job | null = null;
  #capabilities: readonly V6CommandCapability[] = [];
  #snapshot: PrinterCommandSnapshot = printerCommandStore.snapshot;
  #unsubscribe: (() => void) | null = null;

  set printer(value: V6Printer | null) {
    this.#printer = value;
    this.#update();
  }

  set job(value: V6Job | null) {
    this.#job = value;
    this.#update();
  }

  set capabilities(value: readonly V6CommandCapability[]) {
    this.#capabilities = value;
    this.#update();
  }

  connectedCallback(): void {
    if (!this.#unsubscribe) {
      this.#unsubscribe = printerCommandStore.subscribe((snapshot) => {
        this.#snapshot = snapshot;
        this.#update();
      });
    }
    this.#update();
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  async #setSpeed(level: PrintSpeedLevel): Promise<void> {
    const printer = this.#printer;
    if (!printer || !commandAvailable("speed", printer, this.#capabilities, this.#job)) return;
    try {
      await printerCommandStore.execute({
        printer,
        command: "speed",
        capabilities: this.#capabilities,
        job: this.#job,
        speedLevel: level,
      });
    } catch {
      // Der zentrale Store hält die sichtbare Fehlermeldung.
    }
  }

  #update(): void {
    if (!this.isConnected) return;
    const current = printSpeedLevel(this.#printer);
    const busy = Boolean(this.#printer && printerCommandStore.isBusy(this.#printer.printer_id));
    const enabled = Boolean(
      this.#printer
      && !busy
      && commandAvailable("speed", this.#printer, this.#capabilities, this.#job),
    );
    this.#root.innerHTML = `<style>
      :host{display:block}
      *{box-sizing:border-box}
      .speed{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
      .speed>span{color:#91a5b9;font-size:10px;font-weight:800;text-transform:uppercase}
      button{min-height:32px;padding:6px 9px;border:1px solid #355773;border-radius:8px;background:#102131;color:#b9cada;font-weight:800;cursor:pointer}
      button.active{border-color:#42c8ff;background:#12314a;color:#fff}
      button:disabled{opacity:.4;cursor:not-allowed}
    </style><div class="speed"><span>Drucktempo</span>${PRINT_SPEED_MODES.map((mode) => `<button type="button" data-speed="${mode.level}" class="${current === mode.level ? "active" : ""}" ${enabled ? "" : "disabled"}>${mode.label}</button>`).join("")}</div>`;
    this.#root.querySelectorAll<HTMLButtonElement>("[data-speed]").forEach((button) => {
      button.addEventListener("click", () => void this.#setSpeed(Number(button.dataset.speed) as PrintSpeedLevel));
    });
  }
}

if (!customElements.get("ultimate-3d-print-speed-control")) {
  customElements.define("ultimate-3d-print-speed-control", Ultimate3DPrintSpeedControl);
}
