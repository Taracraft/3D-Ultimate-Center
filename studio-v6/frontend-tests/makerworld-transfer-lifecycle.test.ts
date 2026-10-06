import test from "node:test";
import assert from "node:assert/strict";
import { keyboard, loadMobileModule, MobileNode } from "./mobile-contract-harness.js";
const tick = () => new Promise<void>((resolve) => queueMicrotask(resolve));
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { resolve, reject, promise }; }
const variant = { id: "variant-b", title: "Two plates", profile_name: "A1", printer_model: "A1", plates: [], images: [], plate_count: 2, is_default: true };
const detail = { id: "model", title: "Tara", instances: [variant], stats: {}, creator: "Tara", images: [], description: "", tags: [], recommendations: [], comments: [] };
const catalog = { selection: { printer_profile_id: "printer-a" }, groups: { printer: [
  { id: "printer-a", name: "A1", source: "builtin" }, { id: "printer-b", name: "H2S", source: "builtin" },
] } };

function setup() {
  const selections: unknown[] = []; const queued: unknown[] = []; const events: Event[] = [];
  const host = new MobileNode(); host.shadowRoot = new MobileNode("root");
  host.addEventListener("gallery-open-studio", (event) => events.push(event));
  const module = loadMobileModule("makerworld-detail-dialog-v6.ts", {
    modules: {
      "./makerworld-attribution.js": { makerWorldLicenseHtml: () => "" },
      "./makerworld-description-media.js": { safeMediaUrl: (value: string) => value, descriptionImageUrls: () => [], missingDescriptionImages: () => [] },
      "./ha-api-transport.js": { errorMessage: (error: unknown) => error instanceof Error ? error.message : String(error) },
      "./gallery-api.js": { GalleryApi: class { async list() { return { tree: [{ path: "" }] }; } } },
      "./makerworld-v6-adapter2.js": {},
      "./profile-api.js": { ProfileApi: class { async saveSelection(selection: unknown) { selections.push(selection); } async getCatalog() { return catalog; } } },
      "./workspace-file-handoff.js": { queueWorkspaceFile: (...args: unknown[]) => queued.push(args) },
    },
    globals: { DOMParser: class { parseFromString() { return { body: { firstElementChild: { childNodes: [] } }, querySelectorAll: () => [] }; } } },
    expose: '\nexport const probe = { transfer, render, states: typeof dialogStates === "undefined" ? null : dialogStates, close: typeof closeMakerWorldDialog === "undefined" ? (node) => node.remove() : closeMakerWorldDialog };',
  });
  const overlay = new MobileNode("dialog"); overlay.className = "mw-overlay"; host.shadowRoot.append(overlay);
  overlay.innerHTML = '<section class="mw-dialog"><select id="target-printer"><option value="printer-b" selected>H2S</option></select></section>';
  // The boundary double keeps nodes flat: attach the target select to its dialog.
  const dialog = overlay.querySelector(".mw-dialog")!; const target = overlay.querySelector("#target-printer")!;
  overlay.children = [dialog]; dialog.append(target);
  module.exports.probe.states?.set(overlay, { busy: false, closed: false });
  return { ...module, host, overlay, dialog, selections, queued, events, probe: module.exports.probe };
}

test("MakerWorld Studio handoff preserves the selected 3MF variant and passes its file explicitly", async () => {
  const app = setup(); const formats: string[] = []; const instances: string[] = [];
  const file = { name: "Tara.3mf" };
  const api = { async save(instance: typeof variant) { instances.push(instance.id); throw new Error("already exists"); }, async download(instance: typeof variant, format: string) { instances.push(instance.id); formats.push(format); return file; } };
  await app.probe.transfer(app.host, app.overlay, detail, variant, api, "studio", [""]);
  assert.deepEqual(formats, ["3mf"]); assert.deepEqual(instances, ["variant-b", "variant-b"]);
  assert.equal(app.events.length, 1); assert.equal((app.events[0] as Event & { detail: { file: unknown } }).detail.file, file);
  assert.equal(app.queued.length, 0, "a stale global handoff must not select a different file");
});

test("MakerWorld prevents duplicate Studio actions while one variant transfer is pending", async () => {
  const app = setup(); const pending = deferred<void>(); let saves = 0; let downloads = 0;
  const api = { async save() { saves += 1; await pending.promise; }, async download() { downloads += 1; return { name: "Tara.3mf" }; } };
  const first = app.probe.transfer(app.host, app.overlay, detail, variant, api, "studio", [""]);
  const second = app.probe.transfer(app.host, app.overlay, detail, variant, api, "studio", [""]);
  await tick(); pending.resolve(); await Promise.all([first, second]);
  assert.equal(saves, 1); assert.equal(downloads, 1); assert.equal(app.events.length, 1);
});

test("closing MakerWorld during save prevents later download, profile mutation and navigation", async () => {
  const app = setup(); const pending = deferred<void>(); let downloads = 0;
  const api = { async save() { await pending.promise; }, async download() { downloads += 1; return {}; } };
  const action = app.probe.transfer(app.host, app.overlay, detail, variant, api, "studio", [""]);
  await tick(); app.probe.close(app.overlay); pending.resolve(); await action;
  assert.equal(downloads, 0); assert.equal(app.selections.length, 0); assert.equal(app.events.length, 0);
});

test("failed MakerWorld download leaves the chosen global printer profile unchanged", async () => {
  const app = setup();
  const api = { async save() { throw new Error("already exists"); }, async download() { throw new Error("network interrupted"); } };
  await app.probe.transfer(app.host, app.overlay, detail, variant, api, "studio", [""]);
  assert.equal(app.selections.length, 0); assert.equal(app.events.length, 0);
});

test("MakerWorld variant and tab redraw retains target printer choice and content position", () => {
  const app = setup(); const api = {};
  app.probe.render(app.host, app.overlay, detail, api, [""], catalog, () => {});
  const select = app.dialog.querySelector("#target-printer")!; assert.equal(select.value, "printer-b");
  const list = app.dialog.querySelector(".mw-profiles")!; list.scrollTop = 450;
  app.probe.render(app.host, app.overlay, detail, api, [""], catalog, () => {}, variant.id, "ALL", "reviews");
  assert.equal(app.dialog.querySelector("#target-printer")!.value, "printer-b");
  assert.equal(app.dialog.querySelector(".mw-profiles")!.scrollTop, 450);
});

test("MakerWorld variant cards are keyboard actionable and retain focus through redraw", () => {
  const app = setup(); app.probe.render(app.host, app.overlay, detail, {}, [""], catalog, () => {});
  const card = app.dialog.querySelector("[data-profile]")!;
  assert.equal(card.getAttribute("tabindex"), "0"); assert.equal(card.getAttribute("role"), "button");
  card.focus(); const event = keyboard(card, card, " ");
  assert.equal(event.defaultPrevented, true);
  assert.equal(app.dialog.querySelector("[data-profile]")!.focusCount, 1);
});

test("MakerWorld loading can be cancelled and a late request cannot restore the closed modal", async () => {
  const app = setup(); const pending = deferred<unknown>();
  const loading = app.exports.openMakerWorldDetailV6(app.host, "model", { detail: () => pending.promise }, () => {});
  const overlay = app.host.shadowRoot!.children.at(-1)!;
  assert.equal(overlay.tagName, "dialog"); assert.equal(overlay.modalCalls, 1);
  overlay.dispatchEvent(new Event("cancel", { cancelable: true }));
  pending.resolve(detail); await loading; assert.equal(overlay.isConnected, false);
});


test("MakerWorld reuses the confirmed 3MF server asset without downloading or queueing it twice", async () => {
  const app = setup(); let downloads = 0; let overwrite: boolean | undefined;
  const api = {
    async save(_instance: unknown, _folder: string, _name: string, replace: boolean) {
      overwrite = replace;
      return { kind: "model", asset_id: "path:confirmed-variant", name: "Two plates.3mf" };
    },
    async download() { downloads += 1; throw new Error("server asset must not be downloaded again"); },
  };
  await app.probe.transfer(app.host, app.overlay, detail, variant, api, "studio", [""]);
  assert.equal(downloads, 0); assert.equal(overwrite, false); assert.equal(app.events.length, 1); assert.equal(app.queued.length, 0);
  const handoff = (app.events[0] as Event & { detail: Record<string, unknown> }).detail;
  assert.equal(handoff.assetId, "path:confirmed-variant"); assert.equal(handoff.fileName, "Two plates.3mf"); assert.equal(handoff.file, undefined);
});

test("MakerWorld never treats an unconfirmed non-3MF asset as the selected project", async () => {
  const app = setup(); const formats: string[] = []; const file = { name: "verified-variant.3mf" };
  const api = {
    async save() { return { kind: "model", asset_id: "path:other-model", name: "old.stl" }; },
    async download(_instance: unknown, format: string) { formats.push(format); return file; },
  };
  await app.probe.transfer(app.host, app.overlay, detail, variant, api, "studio", [""]);
  assert.deepEqual(formats, ["3mf"]); assert.equal(app.events.length, 1);
  const handoff = (app.events[0] as Event & { detail: Record<string, unknown> }).detail;
  assert.equal(handoff.assetId, undefined); assert.equal(handoff.file, file);
});
