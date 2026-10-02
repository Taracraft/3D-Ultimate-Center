import type { V6Job, V6Printer } from "./v6-api.js";

type CapabilityMap = readonly Readonly<Record<string, unknown>>[] | Readonly<Record<string, unknown>> | null | undefined;

export class Ultimate3DPrintSpeedControl extends HTMLElement {
  #printer: V6Printer | null = null;
  #job: V6Job | null = null;
  #capabilities: CapabilityMap = null;

  set printer(value: V6Printer | null) { this.#printer = value; this.#render(); }
  get printer(): V6Printer | null { return this.#printer; }
  set job(value: V6Job | null) { this.#job = value; this.#render(); }
  get job(): V6Job | null { return this.#job; }
  set capabilities(value: CapabilityMap) { this.#capabilities = value; this.#render(); }
  get capabilities(): CapabilityMap { return this.#capabilities; }

  connectedCallback(): void { this.#render(); }

  #render(): void {
    const speed = String((this.#printer as unknown as Record<string, unknown> | null)?.speed_profile || "standard");
    const disabled = !this.#job || !this.#printer;
    this.innerHTML = `<style>:host{display:block}.speed{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.speed button{border:1px solid rgba(125,211,252,.45);background:rgba(15,23,42,.72);color:#dff7ff;border-radius:6px;padding:4px 8px;font:inherit}.speed button[disabled]{opacity:.45}.speed .active{background:rgba(34,197,94,.22);border-color:#22c55e}</style><div class="speed" aria-label="Druckgeschwindigkeit"><span>Tempo</span>${["silent","standard","sport","ludicrous"].map((item) => `<button type="button" data-speed="${item}" class="${speed === item ? "active" : ""}" ${disabled ? "disabled" : ""}>${item === "silent" ? "50%" : item === "standard" ? "100%" : item === "sport" ? "125%" : "166%"}</button>`).join("")}</div>`;
  }
}

if (!customElements.get("ultimate-3d-print-speed-control")) {
  customElements.define("ultimate-3d-print-speed-control", Ultimate3DPrintSpeedControl);
}