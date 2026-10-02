export class MakerWorldInfoPopover extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });

  connectedCallback(): void {
    this.#root.innerHTML = `
      <style>:host{display:contents}</style>
      <slot></slot>`;
  }
}

if (!customElements.get("makerworld-info-popover")) {
  customElements.define("makerworld-info-popover", MakerWorldInfoPopover);
}