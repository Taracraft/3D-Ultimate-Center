export type ContextMenuAction = Readonly<{
  label: string;
  run: () => void | Promise<void>;
  disabled?: boolean;
  danger?: boolean;
  separatorBefore?: boolean;
}>;

let activeMenu: HTMLElement | null = null;
let cleanupActive: (() => void) | null = null;

export function closeContextMenu(): void {
  cleanupActive?.();
  cleanupActive = null;
  activeMenu?.remove();
  activeMenu = null;
}

export function openContextMenu(
  event: MouseEvent,
  actions: readonly ContextMenuAction[],
): void {
  event.preventDefault();
  event.stopPropagation();
  closeContextMenu();

  const available = actions.filter((action) => action.label.trim());
  if (!available.length) return;

  const menu = document.createElement("div");
  menu.setAttribute("role", "menu");
  menu.tabIndex = -1;
  menu.style.cssText = [
    "position:fixed",
    "z-index:2147483000",
    "min-width:220px",
    "max-width:min(320px,calc(100vw - 16px))",
    "padding:6px",
    "border:1px solid #35506d",
    "border-radius:10px",
    "background:#101a27",
    "box-shadow:0 18px 48px rgba(0,0,0,.5)",
    "color:#eef6ff",
    "font:13px/1.35 system-ui,sans-serif",
  ].join(";");

  for (const action of available) {
    if (action.separatorBefore) {
      const separator = document.createElement("div");
      separator.setAttribute("role", "separator");
      separator.style.cssText = "height:1px;margin:5px 3px;background:#2a3c52";
      menu.append(separator);
    }

    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.textContent = action.label;
    button.disabled = action.disabled === true;
    button.style.cssText = [
      "display:block",
      "width:100%",
      "padding:9px 10px",
      "border:0",
      "border-radius:7px",
      "background:transparent",
      `color:${action.danger ? "#ff9aa8" : "#eef6ff"}`,
      "text-align:left",
      "cursor:pointer",
    ].join(";");

    button.addEventListener("pointerenter", () => {
      if (!button.disabled) button.style.background = action.danger ? "#3d1d25" : "#193149";
    });
    button.addEventListener("pointerleave", () => {
      button.style.background = "transparent";
    });
    button.addEventListener("click", () => {
      if (button.disabled) return;
      closeContextMenu();
      void action.run();
    });
    menu.append(button);
  }

  document.body.append(menu);
  activeMenu = menu;

  const margin = 8;
  const width = menu.offsetWidth;
  const height = menu.offsetHeight;
  menu.style.left = `${Math.max(margin, Math.min(event.clientX, window.innerWidth - width - margin))}px`;
  menu.style.top = `${Math.max(margin, Math.min(event.clientY, window.innerHeight - height - margin))}px`;

  const close = (closeEvent: Event): void => {
    const path = closeEvent.composedPath();
    if (!path.includes(menu)) closeContextMenu();
  };
  const onKey = (keyEvent: KeyboardEvent): void => {
    if (keyEvent.key === "Escape") closeContextMenu();
  };
  const onScroll = (): void => closeContextMenu();

  window.addEventListener("pointerdown", close, true);
  window.addEventListener("contextmenu", close, true);
  window.addEventListener("keydown", onKey, true);
  window.addEventListener("scroll", onScroll, true);
  window.addEventListener("resize", onScroll, true);

  cleanupActive = () => {
    window.removeEventListener("pointerdown", close, true);
    window.removeEventListener("contextmenu", close, true);
    window.removeEventListener("keydown", onKey, true);
    window.removeEventListener("scroll", onScroll, true);
    window.removeEventListener("resize", onScroll, true);
  };

  menu.focus({ preventScroll: true });
}
