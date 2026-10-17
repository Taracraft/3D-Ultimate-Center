import test from "node:test";
import assert from "node:assert/strict";
import { ContractElement, loadElementContract } from "./element-contract-harness.js";
import { filamentsForTarget, resolveFilamentSelection, vendorsForTarget } from "../frontend/filament-catalog-selection.js";

const items = [
  { id: "GFL99", name: "Generic PLA", vendor: "Generic", material_type: "PLA", targets: ["external_spool", "ams_slot"] },
  { id: "GFG99", name: "Generic PETG", vendor: "Generic", material_type: "PETG", targets: ["external_spool", "ams_slot"] },
  { id: "GFU99", name: "Generic TPU", vendor: "Generic", material_type: "TPU", targets: ["external_spool"] },
] as any[];

async function render(options: {loaded?: boolean; available?: boolean; rfid?: boolean; ready?: boolean; catalog?: any[]; material?: string} = {}) {
  let commands = 0;
  const external = {available: options.available ?? true, loaded: options.loaded ?? false,
    material: options.material ?? "PLA", color: "#123456", filament_id: "GFL99", rfid_detected: options.rfid ?? false};
  const host = loadElementContract("ams-workspace.ts", {}, {
    "./direct-print-status-api.js": {fetchDetailedDirectPrintStatus: async () => ({
      items: [{printer_id: "test-a1", name: "Test A1", ready: options.ready ?? true, external_spool: external,
        ams: {available: true, kind: "ams_lite", slots: [{global_id: "0:0", display_slot: 1, present: true,
          active: false, material: "PLA", filament_id: "GFL99", color: "#123456", rfid_detected: false}]} }],
      filament_catalog: {items: options.catalog ?? items},
    }), previewFilamentSetting: async () => { commands += 1; throw new Error("unexpected preview"); },
    applyFilamentSetting: async () => { commands += 1; throw new Error("unexpected apply"); }},
    "./profile-api.js": {ProfileApi: class {async getCatalog() {return {};}}},
    "./studio-profile-catalog.js": {filamentColor: () => "#123456", profileById: () => null},
    "./studio-profile-ui.js": {filamentMaterial: () => "PLA"},
    "./studio-persistence.js": {loadStudioWorkspace: async () => ({plates: [], activePlate: 0})},
    "./details-open-state.js": {detailsOpenAttribute: () => "", updateDetailsOpenState: () => {}},
    "./material-system-hass-signature.js": {materialSystemHassSignature: () => "test"},
    "./filament-catalog-selection.js": {filamentsForTarget, resolveFilamentSelection, vendorsForTarget},
  });
  const Constructor = host.exported.Ultimate3DAmsWorkspace as new () => ContractElement & {connectedCallback(): void};
  const element = new Constructor(); element.isConnected = true; element.connectedCallback();
  await new Promise<void>((resolve) => setImmediate(resolve));
  return {html: element.shadowRoot!.innerHTML, commands};
}

for (const loaded of [false, true]) test(`external spool has the same actual catalog and color control, loaded=${loaded}`, async () => {
  const {html, commands} = await render({loaded});
  assert.match(html, /data-setting-kind="external_spool"/);
  assert.match(html, /data-setting-kind="ams_slot"/);
  assert.equal((html.match(/type="color" value="#123456"/g) ?? []).length, 2);
  assert.equal((html.match(/Generic PLA/g) ?? []).length, 2);
  assert.equal((html.match(/Generic PETG/g) ?? []).length, 2);
  assert.equal((html.match(/Generic TPU/g) ?? []).length, 1, "normal TPU is external only");
  assert.equal(commands, 0, "render/refresh never write to a printer");
});

test("missing catalog never invents a fallback list of filament types", async () => {
  const {html, commands} = await render({loaded: true, catalog: []});
  assert.doesNotMatch(html, /<option value="(?:PLA|PETG|TPU|PVA)"/);
  assert.doesNotMatch(html, /data-setting-apply/);
  assert.equal(commands, 0);
});

test("unavailable external telemetry does not create writable targets", async () => {
  const {html, commands} = await render({available: false});
  assert.doesNotMatch(html, /data-setting-kind="external_spool"/);
  assert.equal(commands, 0);
});

test("unknown material is not silently assigned an unrelated catalog profile", () => {
  assert.equal(resolveFilamentSelection(items, "external_spool", "", ""), null);
  assert.equal(resolveFilamentSelection(items, "external_spool", "", "unknown-material"), null);
  assert.equal(resolveFilamentSelection(items, "external_spool", "", "", "", "GFG99")?.id, "GFG99");
});
