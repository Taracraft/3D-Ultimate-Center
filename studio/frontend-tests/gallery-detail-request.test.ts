import "./gallery-duplicates.test.js";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";

function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { resolve, reject, promise }; }
const source = readFileSync(join(process.cwd(), "frontend", "gallery-library-pane.ts"), "utf8");
const parsed = ts.createSourceFile("gallery-library-pane.ts", source, ts.ScriptTarget.Latest, true);
const pane = parsed.statements.find((node): node is ts.ClassDeclaration => ts.isClassDeclaration(node) && node.name?.text === "Ultimate3DGalleryLibraryPane")!;
const methods = ["#showDetails", "#openFolder", "disconnectedCallback"].map((name) => pane.members.find((node) => ts.isMethodDeclaration(node) && node.name.getText(parsed) === name)!.getText(parsed)).join("\n");
const compiled = ts.transpileModule(`class Probe {
  #detailRequest = 0; #timer = null; #previewObserver = null;
  #operations = { invalidate() {} }; #selected = new Set(); #folder = ""; #query = "";
  #root = { querySelector: () => null }; #api; isConnected = true;
  opened = []; errors = [];
  constructor(api) { this.#api = api; }
  #detailDialog() { return { open: (item) => this.opened.push(item.path) }; }
  #showError(error) { this.errors.push(error); } #download() {} #openIn3DStudio() {}
  async #refresh() {} show(item) { return this.#showDetails(item); }
  navigate() { return this.#openFolder("new"); }
  disconnect() { this.isConnected = false; this.disconnectedCallback(); }
  ${methods}
} return Probe;`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
const Constructor = new Function("errorMessage", compiled)((error: unknown) => String(error));
const model = (path: string) => ({ kind: "model", path });

test("gallery details ignore an older preview after another model was selected", async () => {
  const old = deferred<null>(); const view = new Constructor({ preview: (item: { path: string }) => item.path === "old" ? old.promise : Promise.resolve(null) });
  const first = view.show(model("old")); await view.show(model("new")); old.resolve(null); await first;
  assert.deepEqual(view.opened, ["new"]);
});

test("gallery details do not reopen after navigating to another folder", async () => {
  const pending = deferred<null>(); const view = new Constructor({ preview: () => pending.promise });
  const action = view.show(model("old")); await view.navigate(); pending.resolve(null); await action;
  assert.deepEqual(view.opened, []);
});

test("gallery details ignore late previews and errors after disconnect", async () => {
  for (const failure of [false, true]) {
    const pending = deferred<null>(); const view = new Constructor({ preview: () => pending.promise });
    const action = view.show(model("old")); view.disconnect();
    if (failure) pending.reject(new Error("old preview")); else pending.resolve(null);
    await action; assert.deepEqual(view.opened, []); assert.deepEqual(view.errors, []);
  }
});
