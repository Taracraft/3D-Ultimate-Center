import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));

function read(path) {
  return readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
}

function write(path, text) {
  writeFileSync(path, `\uFEFF${text}`, "utf8");
}

function replaceExact(text, oldValue, newValue, label) {
  if (text.includes(newValue)) return text;
  if (!text.includes(oldValue)) throw new Error(`Quellmarker fehlt: ${label}`);
  return text.replace(oldValue, newValue);
}

const workspacePath = join(root, "frontend", "studio-mega-workspace-v2.ts");
const workspace = read(workspacePath);
for (const marker of ["#amsMaterialChoices", "#modalError", "#occupiedAmsSlots", "global_id: choice.global_id"]) {
  if (!workspace.includes(marker)) throw new Error(`Workspace-Migration fehlt: ${marker}`);
}

const uiPath = join(root, "frontend", "studio-mega-ui-v2.ts");
let ui = read(uiPath);
ui = replaceExact(ui, `  error: string;
  loading: boolean;`, `  error: string;
  modalError: string;
  loading: boolean;`, "UI-Modaltyp");
ui = replaceExact(ui, `.direct-print-top{display:block}\${STUDIO_PROFILE_CSS}
@media(max-width:1100px)`, `.direct-print-top{display:block}.error-modal{position:fixed;inset:0;z-index:10000;display:grid;place-items:center;padding:24px;background:#000b}.error-modal-panel{width:min(560px,calc(100vw - 32px));overflow:hidden;border:1px solid #d65763;border-radius:12px;background:linear-gradient(180deg,#27131a,#130b10);box-shadow:0 22px 70px #000d}.error-modal-head{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid #74313a}.error-modal-head strong{font-size:17px;color:#ffd6da}.error-modal-body{padding:18px 16px;color:#fff1f2;font-size:14px;line-height:1.5}.error-modal-actions{display:flex;justify-content:flex-end;padding:0 16px 16px}.error-modal-actions button{min-width:120px;padding:8px 13px;border:1px solid #d65763;border-radius:5px;background:#6a222c;color:#fff;font-weight:800}\${STUDIO_PROFILE_CSS}
@media(max-width:1100px)`, "Modal-CSS");
ui = replaceExact(ui, `<div id="sidebar"></div>\${state.error ? \`<div class="error-box">\${esc(state.error)}</div>\` : ""}</aside>`, `<div id="sidebar"></div>\${state.error ? \`<div class="error-box" id="global-error-box">\${esc(state.error)}</div>\` : ""}</aside>`, "Inline-Fehler-ID");
ui = replaceExact(ui, `<input id="local-file" type="file" accept=".stl,.3mf" hidden></section>\`;`, `<input id="local-file" type="file" accept=".stl,.3mf" hidden></section>\${state.modalError ? \`<div class="error-modal" id="error-modal" role="dialog" aria-modal="true" aria-labelledby="error-modal-title"><section class="error-modal-panel"><header class="error-modal-head"><strong id="error-modal-title">Slicing nicht möglich</strong></header><div class="error-modal-body">\${esc(state.modalError)}</div><footer class="error-modal-actions"><button id="error-modal-close" type="button">Schließen</button></footer></section></div>\` : ""}\`;`, "Modal-HTML");
write(uiPath, ui);

const slicingPath = join(root, "frontend", "slicing-api.ts");
let slicing = read(slicingPath);
slicing = replaceExact(slicing, `export type SliceProjectFilament = Readonly<{
  extruder: number;
  name: string;
  material: string;
  color: string | null;
}>;`, `export type SliceProjectFilament = Readonly<{
  extruder: number;
  name: string;
  material: string;
  color: string | null;
  global_id?: string;
  unit_id?: string;
  slot_index?: number;
  display_slot?: number;
  tray_id?: string;
  filament_id?: string;
  source?: "ams" | "profile" | "model";
}>;`, "Filament-Metadaten");
write(slicingPath, slicing);

console.log("AMS-/Modal-Quelländerung vollständig angewendet.");
