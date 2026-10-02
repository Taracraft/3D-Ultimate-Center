import type { WorkspaceRoute } from "./router.js";

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
    :host{display:block;width:100%;height:calc(100dvh - 124px);min-height:640px;color:#f4f7fb;overflow:hidden}*{box-sizing:border-box}.shell{display:grid;grid-template-columns:220px minmax(0,1fr);height:100%;background:#08101a}nav{padding:12px 9px;border-right:1px solid #26384f;background:#0a1119;overflow:auto}nav h3{margin:5px 10px 10px;color:#70849b;font-size:10px;text-transform:uppercase}nav button{display:grid;grid-template-columns:25px 1fr;gap:8px;width:100%;min-height:42px;margin:3px 0;padding:8px 10px;border:1px solid transparent;border-radius:9px;background:transparent;color:#91a4bc;text-align:left}.nav-buttons{display:contents}.nav-live{display:grid;gap:3px;margin:10px 4px 2px;padding:9px;border:1px solid #2e6687;border-radius:9px;background:#10263a}.nav-live[hidden]{display:none}.nav-live strong{color:#eefaff;font-size:11px}.nav-live span{color:#8fdcff;font-size:10px}.nav-live small{color:#91a5b9;font-size:9px}nav button.active{border-color:#2d7098;background:#13263a;color:#fff;box-shadow:inset 3px 0 #34b9ff}.content{display:grid;grid-template-rows:auto minmax(0,1fr);min-width:0;min-height:0}.tools{display:none;gap:7px;align-items:center;flex-wrap:wrap;padding:8px 11px;border-bottom:1px solid #26384f;background:#0c1723}.tools.visible{display:flex}.tools strong{margin-right:auto;color:#9eb3c8}.tools button{padding:8px 10px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;font-weight:700}.tools .storage{border-color:#d1a94b;background:#4a3814;color:#fff1c6}.host{min-width:0;min-height:0;overflow:auto}.host>*{display:block;width:100%;min-width:0}.host>[hidden]{display:none!important}@media(max-width:800px){:host{height:calc(100dvh - 108px);min-height:520px}.shell{grid-template-columns:1fr;grid-template-rows:auto minmax(0,1fr)}nav{display:flex;overflow-x:auto;overflow-y:hidden;border-right:0;border-bottom:1px solid #26384f}nav h3{display:none}nav button{width:auto;min-width:max-content}.tools strong{width:100%}}
  </style><section class="shell"><nav><h3>Arbeitsbereiche</h3><div class="nav-buttons" id="nav-buttons"></div><div class="nav-live" id="nav-live" hidden><strong id="nav-live-title"></strong><span id="nav-live-meta"></span><small id="nav-live-detail"></small></div></nav><section class="content"><div class="tools" id="tools"></div><main class="host" id="host"></main></section></section>`;
}