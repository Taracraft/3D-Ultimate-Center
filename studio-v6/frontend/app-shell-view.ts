import type { WorkspaceRoute } from "./router.js";

/**
 * Route metadata is retained for callers that need stable workspace labels.
 * The Studio no longer renders its own navigation; Home Assistant remains the
 * single visible navigation authority.
 */
export const APP_NAV: ReadonlyArray<readonly [WorkspaceRoute["name"], string, string]> = [
  ["steuerung", "Steuerzentrale", "◉"],
  ["galerie", "Galerie", "▦"],
  ["studio", "3D-Studio", "◇"],
  ["ams", "Materialsysteme", "◫"],
  ["profile", "Profile", "⚙"],
  ["aufgaben", "Aufgaben", "☷"],
  ["verlauf", "Verlauf", "◷"],
  ["system", "System", "⌁"],
  ["slicing-server", "Slicing-Server", "≋"],
];

export function mountAppShell(root: ShadowRoot): void {
  root.innerHTML = `<style>
    :host{display:block;width:100%;height:calc(100dvh - 124px);min-height:640px;color:#f4f7fb;overflow:hidden}
    *{box-sizing:border-box}
    .shell{display:grid;grid-template-columns:minmax(0,1fr);height:100%;background:#08101a}
    .content{display:grid;grid-template-rows:auto minmax(0,1fr);min-width:0;min-height:0}
    .tools{display:none;gap:7px;align-items:center;flex-wrap:wrap;padding:8px 11px;border-bottom:1px solid #26384f;background:#0c1723}
    .tools.visible{display:flex}
    .tools strong{margin-right:auto;color:#9eb3c8}
    .tools button{padding:8px 10px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;font-weight:700}
    .tools .storage{border-color:#d1a94b;background:#4a3814;color:#fff1c6}
    .host{min-width:0;min-height:0;overflow:auto}
    .host>*{display:block;width:100%;min-width:0}
    .host>[hidden]{display:none!important}
    @media(max-width:800px){
      :host{height:calc(100dvh - 108px);min-height:520px}
      .tools strong{width:100%}
    }
  </style><section class="shell"><section class="content"><div class="tools" id="tools"></div><main class="host" id="host"></main></section></section>`;
}
