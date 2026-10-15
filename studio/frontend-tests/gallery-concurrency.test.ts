import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import * as ts from "typescript";
import { GalleryOperationState } from "../frontend/gallery-operation-state.js";

type Library = { folder: string; parent: string; items: { path: string }[]; tree: unknown[] };
const library = (folder: string, ...names: string[]): Library => ({
  folder, parent: "", items: names.map((path) => ({ path })), tree: [],
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

// Execute the real asynchronous methods with API and rendering ports. This is a
// controller contract test, not a DOM, browser, or mobile interaction test.
const source = readFileSync(join(process.cwd(), "frontend", "gallery-library-pane.ts"), "utf8");
const parsed = ts.createSourceFile("gallery-library-pane.ts", source, ts.ScriptTarget.Latest, true);
const pane = parsed.statements.find((node): node is ts.ClassDeclaration =>
  ts.isClassDeclaration(node) && node.name?.text === "Ultimate3DGalleryLibraryPane");
assert.ok(pane);
const methodNames = ["#refresh", "#openFolder", "#upload", "#run", "disconnectedCallback"];
const methods = methodNames.map((name) => {
  const method = pane.members.find((node) => ts.isMethodDeclaration(node) && node.name.getText(parsed) === name);
  assert.ok(method, `Gallery controller method ${name} is missing`);
  return method.getText(parsed);
}).join("\n");
const compiled = ts.transpileModule(`class GalleryProbe {
  #api; #library = null; #folder = ""; #query = ""; #signature = "";
  #busy = false; #operations = new GalleryOperationState();
  #selected = new Set(); #detailRequest = 0; #timer = null; #previewObserver = null;
  #root = { querySelector: () => null };
  messages = []; errors = []; progress = []; rendered = [];
  constructor(api) { this.#api = api; }
  #renderData() { this.rendered.push(this.#library); }
  #renderRecent() {} #setLive() {}
  #showMessage(value) { this.messages.push(value); }
  #showError(value) { this.errors.push(value); }
  #dialog() { return { confirm: async () => false }; }
  #renderUploadProgress(title, current, bytes, total, successful, error = false) {
    this.progress.push({ title, current, bytes, total, successful: [...successful], error });
  }
  get current() { return this.#library; }
  get folder() { return this.#folder; }
  refresh() { return this.#refresh(false); }
  open(folder) { return this.#openFolder(folder); }
  search(query) { this.#query = query; return this.#refresh(false); }
  upload(files) { return this.#upload(files); }
  run(operation) { return this.#run(operation); }
  ${methods}
}
return GalleryProbe;`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;

function probe(api: Record<string, unknown>) {
  const cached: Library[] = [];
  const Probe = new Function("GalleryOperationState", "saveCachedLibrary", "errorMessage", "sizeLabel", compiled)(
    GalleryOperationState,
    (value: Library) => cached.push(value),
    (error: unknown) => error instanceof Error ? error.message : String(error),
    (bytes: number) => `${bytes} B`,
  );
  return { view: new Probe(api), cached };
}

test("gallery ignores a slow previous folder response after a newer navigation", async () => {
  const old = deferred<Library>();
  const { view } = probe({ list: (folder: string) => folder === "old" ? old.promise : Promise.resolve(library(folder, "new.stl")) });
  const pending = view.open("old");
  await view.open("new");
  old.resolve(library("old", "old.stl"));
  await pending;
  assert.equal(view.folder, "new");
  assert.deepEqual(view.current.items, [{ path: "new.stl" }]);
  assert.equal(view.rendered.length, 1);
});

test("gallery ignores an obsolete error without replacing the current success", async () => {
  const old = deferred<Library>();
  const { view } = probe({ list: (folder: string) => folder === "old" ? old.promise : Promise.resolve(library(folder)) });
  const pending = view.open("old");
  await view.open("new");
  old.reject(new Error("old request failed"));
  await pending;
  assert.deepEqual(view.errors, []);
});

test("gallery never caches a superseded search result as the unfiltered root", async () => {
  const search = deferred<Library>();
  const { view, cached } = probe({ list: (_folder: string, query: string) => query ? search.promise : Promise.resolve(library("", "all.stl")) });
  const pending = view.search("filtered");
  await view.search("");
  search.resolve(library("", "filtered.stl"));
  await pending;
  assert.deepEqual(cached.map((value) => value.items), [[{ path: "all.stl" }]]);
  assert.deepEqual(view.current.items, [{ path: "all.stl" }]);
});

test("gallery refreshes the completed upload immediately after releasing the mutation lock", async () => {
  let stored = false;
  const { view } = probe({ upload: async () => { stored = true; }, list: async () => library("", ...(stored ? ["new.stl"] : [])) });
  await view.upload([{ name: "new.stl", size: 42 }]);
  assert.deepEqual(view.current?.items, [{ path: "new.stl" }]);
  assert.equal(view.progress.at(-1).bytes, 42);
  assert.match(view.messages.at(-1), /1 Datei/);
});

test("gallery refreshes successful files when a later upload in the batch fails", async () => {
  const stored: string[] = [];
  const { view } = probe({
    upload: async (file: { name: string }) => { if (file.name === "bad.stl") throw new Error("upload failed"); stored.push(file.name); },
    list: async () => library("", ...stored),
  });
  await view.upload([{ name: "ok.stl", size: 20 }, { name: "bad.stl", size: 10 }]);
  assert.deepEqual(view.current?.items, [{ path: "ok.stl" }]);
  assert.deepEqual(view.progress.at(-1).successful, ["ok.stl"]);
  assert.equal(view.progress.at(-1).error, true);
  assert.deepEqual(view.errors, ["upload failed"]);
});

test("gallery binds all files in an upload batch to its original destination", async () => {
  const first = deferred<void>();
  const destinations: string[] = [];
  const { view } = probe({ list: async (folder: string) => library(folder), upload: async (_file: unknown, folder: string) => {
    destinations.push(folder);
    if (destinations.length === 1) await first.promise;
  } });
  await view.open("original");
  const pending = view.upload([{ name: "first.stl", size: 1 }, { name: "second.stl", size: 1 }]);
  await view.open("next");
  first.resolve();
  await pending;
  assert.deepEqual(destinations, ["original", "original"]);
  assert.equal(view.current.folder, "next");
});

test("gallery refreshes partially completed move/delete operations even on failure", async () => {
  let removed = false;
  const { view } = probe({ list: async () => library("", ...(removed ? [] : ["first.stl"])) });
  await view.refresh();
  await view.run(async () => { removed = true; throw new Error("second removal failed"); });
  assert.deepEqual(view.current.items, []);
  assert.deepEqual(view.errors, ["second removal failed"]);
  assert.equal(view.messages.filter((value: string) => value.includes("Änderung wurde")).length, 0);
});

test("gallery mutation invalidates a list loaded before its write", async () => {
  const old = deferred<Library>();
  const write = deferred<void>();
  let calls = 0;
  const { view } = probe({ list: () => ++calls === 1 ? old.promise : Promise.resolve(library("", "new.stl")) });
  const read = view.refresh();
  const mutation = view.run(() => write.promise);
  old.resolve(library("", "old.stl"));
  await read;
  assert.equal(view.current, null);
  write.resolve();
  await mutation;
  assert.deepEqual(view.current.items, [{ path: "new.stl" }]);
});

test("gallery stops an in-flight list from committing after disconnection", async () => {
  const pending = deferred<Library>();
  const { view } = probe({ list: () => pending.promise });
  const refresh = view.refresh();
  view.disconnectedCallback();
  pending.resolve(library("old"));
  await refresh;
  assert.equal(view.current, null);
});

test("gallery still reports the current request failure", async () => {
  const { view } = probe({ list: async () => { throw new Error("current failure"); } });
  await view.refresh();
  assert.deepEqual(view.errors, ["current failure"]);
});

test("gallery serializes mutations and resumes automatic refresh afterwards", async () => {
  const state = new GalleryOperationState();
  const pending = deferred<void>();
  let writes = 0;
  let reads = 0;
  const first = state.mutate(async () => { writes += 1; await pending.promise; }, async () => { reads += 1; });
  assert.equal(await state.mutate(async () => { writes += 1; }, async () => { reads += 1; }), false);
  assert.equal(await state.refresh(async () => ++reads, () => undefined), false);
  pending.resolve();
  assert.equal(await first, true);
  assert.equal(state.busy, false);
  assert.equal(writes, 1);
  assert.equal(reads, 1);
  assert.equal(await state.refresh(async () => ++reads, () => undefined), true);
});
