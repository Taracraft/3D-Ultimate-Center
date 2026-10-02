export type V6ContextMenuItem = Readonly<{
  label: string;
  action: () => void | Promise<void>;
  disabled?: boolean;
  danger?: boolean;
  detail?: string | undefined;
}>;

export class V6ContextMenu extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });

  connectedCallback(): void {
    this.hidden = true;
  }

  openAt(x: number, y: number, items: readonly V6ContextMenuItem[]): void {
    this.hidden = false;
    const menu = document.createElement("div");
    menu.style.cssText = `position:fixed;left:${x}px;top:${y}px;min-width:220px;padding:6px;border:1px solid #3a5874;border-radius:10px;background:#0d1825;z-index:2147483000`;
    for (const item of items) {
      const button = document.createElement("button");
      button.type = "button";
      button.disabled = Boolean(item.disabled);
      button.textContent = item.detail ? `${item.label}  ${item.detail}` : item.label;
      button.style.cssText = "display:block;width:100%;padding:9px;border:0;background:transparent;color:#eef5ff;text-align:left";
      if (item.danger) button.style.color = "#ffb7bd";
      button.addEventListener("click", async () => {
        this.close();
        await item.action();
      });
      menu.append(button);
    }
    const backdrop = document.createElement("div");
    backdrop.style.cssText = "position:fixed;inset:0;z-index:2147482999";
    backdrop.addEventListener("pointerdown", () => this.close());
    this.#root.replaceChildren(backdrop, menu);
  }

  close(): void {
    this.hidden = true;
    this.#root.replaceChildren();
  }
}

if (!customElements.get("v6-context-menu")) {
  customElements.define("v6-context-menu", V6ContextMenu);
}
