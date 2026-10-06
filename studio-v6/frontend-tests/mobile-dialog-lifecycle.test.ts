import test from "node:test";
import assert from "node:assert/strict";
import { keyboard, loadMobileModule, MobileNode } from "./mobile-contract-harness.js";
const tick = () => new Promise<void>((resolve) => queueMicrotask(resolve));
function actionDialog() {
  const module = loadMobileModule("v6-action-dialog.ts");
  const dialog = new module.exports.V6ActionDialog(); dialog.connectedCallback();
  return { ...module, dialog, root: dialog.shadowRoot as MobileNode };
}
const request = { title: "Auswahl löschen", message: "Dauerhaft löschen?", danger: true };

test("action dialog Enter on Cancel keeps the native cancellation action", async () => {
  const { dialog, root } = actionDialog();
  const result = dialog.confirm(request); await tick();
  const cancel = root.querySelector("[data-action='cancel']")!;
  const key = keyboard(root.querySelector(".dialog")!, cancel, "Enter");
  if (!key.defaultPrevented) cancel.click();
  assert.equal(await result, false, "Enter on Cancel must never confirm deletion");
});

test("action dialog disconnect settles the pending decision once as cancellation", async () => {
  const { dialog, root } = actionDialog(); let settled = false;
  const result = dialog.confirm(request).then((value: boolean) => { settled = true; return value; });
  dialog.disconnectedCallback?.(); await tick();
  assert.equal(settled, true); assert.equal(await result, false); assert.equal(root.childElementCount, 0);
});

test("action dialog uses native modal and handles its cancellation event", async () => {
  const { dialog, root } = actionDialog(); let value: boolean | undefined;
  dialog.confirm(request).then((result: boolean) => { value = result; });
  const modal = root.querySelector("dialog"); assert.ok(modal); assert.equal(modal.modalCalls, 1);
  modal.dispatchEvent(new Event("cancel", { cancelable: true })); await tick();
  assert.equal(value, false); assert.equal(dialog.hidden, true);
});

test("destructive action dialog initially focuses Cancel", async () => {
  const { dialog, root } = actionDialog(); const result = dialog.confirm(request); await tick();
  assert.equal(root.querySelector("[data-action='cancel']")?.focusCount, 1);
  dialog.close(); assert.equal(await result, false);
});

test("action dialog Enter validates input but composition and other controls do not submit", async () => {
  const { dialog, root } = actionDialog();
  let resolved = false;
  const result = dialog.requestText({ title: "Name", message: "Umbenennen", input: { label: "Name" } }).then((value: string) => { resolved = true; return value; });
  const input = root.querySelector("#dialog-input")!; const modal = root.querySelector(".dialog")!;
  keyboard(modal, input, "Enter"); await tick(); assert.equal(resolved, false);
  assert.match(root.querySelector("#dialog-error")!.textContent, /nicht leer/);
  input.value = "  Tara  "; keyboard(modal, input, "Enter", { isComposing: true }); await tick(); assert.equal(resolved, false);
  keyboard(modal, input, "Enter"); assert.equal(await result, "Tara");
});

test("action dialog handles modal failure without leaving an unresolved confirmation", async () => {
  const { dialog } = actionDialog(); let settled = false; MobileNode.failModal = true;
  try {
    const result = dialog.confirm(request).then((value: boolean) => { settled = true; return value; });
    await tick(); assert.equal(settled, true); assert.equal(await result, false); assert.equal(dialog.hidden, true);
  } finally { MobileNode.failModal = false; dialog.close(); }
});

test("replacement dialog cancels the old decision and ignores its queued focus callback", async () => {
  const { dialog, root } = actionDialog();
  const old = dialog.confirm(request);
  const current = dialog.requestText({ title: "Neuer Name", message: "", input: { label: "Name", value: "Tara" } });
  await tick(); assert.equal(await old, false); assert.equal(root.querySelector("#dialog-input")!.focusCount, 1);
  dialog.close(); assert.equal(await current, null);
});

test("native close settles action dialog without a second action", async () => {
  const { dialog, root } = actionDialog(); let value: boolean | undefined;
  dialog.confirm(request).then((result: boolean) => { value = result; });
  const modal = root.querySelector("dialog"); assert.ok(modal); modal.close(); await tick(); assert.equal(value, false);
});

const item = { kind: "model", path: "Tara.3mf", name: "Tara.3mf", title: "Tara", format: "3mf", asset_id: "asset" };
function galleryDialog() {
  const module = loadMobileModule("gallery-model-detail-dialog.ts");
  const dialog = new module.exports.GalleryModelDetailDialog(); dialog.connectedCallback();
  return { ...module, dialog, root: dialog.shadowRoot as MobileNode };
}

test("gallery model details use the native top-layer modal and cancel releases preview", () => {
  const { dialog, root, urls } = galleryDialog();
  dialog.open(item, {}, { download() {}, openStudio() {} });
  const modal = root.querySelector("dialog"); assert.ok(modal); assert.equal(modal.modalCalls, 1);
  modal.dispatchEvent(new Event("cancel", { cancelable: true }));
  assert.deepEqual(urls.revoked, ["blob:1"]); assert.equal(root.childElementCount, 0);
});

test("gallery model details disconnect cleans modal, preview and global listeners", () => {
  const { dialog, root, urls, listeners } = galleryDialog();
  dialog.open(item, {}, { download() {}, openStudio() {} }); dialog.disconnectedCallback();
  assert.deepEqual(urls.revoked, ["blob:1"]); assert.equal(root.childElementCount, 0);
  assert.equal(listeners.get("keydown")?.size ?? 0, 0);
});

test("gallery model details opening a replacement releases only the old preview", () => {
  const { dialog, root, urls } = galleryDialog(); let opened = 0;
  dialog.open(item, {}, { download() {}, openStudio() { opened += 100; } });
  dialog.open(item, {}, { download() {}, openStudio() { opened += 1; } });
  assert.deepEqual(urls.revoked, ["blob:1"]);
  root.querySelector("#studio")!.click(); assert.equal(opened, 1);
  assert.deepEqual(urls.revoked, ["blob:1", "blob:2"]);
});
