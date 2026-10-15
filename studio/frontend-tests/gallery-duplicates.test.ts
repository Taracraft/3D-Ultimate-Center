import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import { MobileNode, loadMobileModule } from "./mobile-contract-harness.js";
import * as contract from "../frontend/gallery-duplicate-contract.js";

function report(folder = "", paths = ["a.stl", "sub/b.stl"]): contract.GalleryDuplicateReport {
  return { complete: true, scope: "byte_identical_models_in_folder", folder, recursive: true, read_only: true,
    files_examined: paths.length, files_hashed: paths.length, bytes_hashed: paths.length * 7, skipped_links: 0,
    groups: [{ sha256: "a".repeat(64), size_bytes: 7, paths,
      independent_copies: paths.length, hardlink_aliases: 0, redundant_content_bytes: (paths.length - 1) * 7 }],
    duplicate_groups: 1, disk_space_savings_verified: false, deletion_authorized: false };
}
function empty(): contract.GalleryDuplicateReport {
  return { ...report(), files_examined: 0, files_hashed: 0, bytes_hashed: 0, groups: [], duplicate_groups: 0 };
}
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { resolve, reject, promise }; }
async function settle() { for (let i = 0; i < 6; i++) await Promise.resolve(); }
function setup() {
  const host = new MobileNode("gallery-toolbar");
  const focus = new MobileNode("button"); host.shadowRoot = new MobileNode("root"); host.shadowRoot.activeElement = focus;
  const document = { activeElement: host, createElement: (tag: string) => new MobileNode(tag) };
  const module = loadMobileModule("gallery-duplicates-dialog.ts", { globals: { AbortController, Error, document } });
  const view = new module.exports.GalleryDuplicatesDialog();
  const root = view.shadowRoot as MobileNode;
  return { view, root, focus };
}
function control(root: MobileNode, label: string) {
  const result = root.querySelectorAll("button").find((node) => node.textContent === label);
  assert.ok(result, `button ${label} missing`); return result;
}
function text(root: MobileNode) { return root.querySelectorAll("*").map((node) => node.textContent).join("\n"); }

test("duplicate report requires complete scoped evidence and preserves independent copies", () => {
  const original = report(); const value = contract.parseGalleryDuplicateReport(original, "");
  assert.deepEqual(value, original); assert.notEqual(value, original); assert.notEqual(value.groups[0], original.groups[0]);
  assert.equal(contract.parseGalleryDuplicateReport(empty(), "").duplicate_groups, 0);
  const links = { ...original, groups: [{ ...original.groups[0]!, independent_copies: 1, hardlink_aliases: 1, redundant_content_bytes: 0 }] };
  assert.equal(contract.parseGalleryDuplicateReport(links, "").groups[0]?.independent_copies, 1);
});

for (const [name, change] of Object.entries({ partial: { complete: false }, writable: { read_only: false },
  wrongFolder: { folder: "other" }, wrongScope: { scope: "geometry" }, nonrecursive: { recursive: false },
  invalidCount: { files_examined: -1 }, inconsistentCount: { duplicate_groups: 0 }, nonnumeric: { bytes_hashed: "14" },
  overbudget: { bytes_hashed: 2 * 1024 ** 3 + 1 }, guessedSavings: { disk_space_savings_verified: true },
  deletion: { deletion_authorized: true }, absentGroups: { groups: null }, hashedMoreThanExamined: { files_hashed: 3 },
  tooFewHashed: { files_hashed: 1 }, tooFewBytes: { bytes_hashed: 13 } })) {
  test(`duplicate report rejects ${name} instead of displaying false success`, () => {
    assert.throws(() => contract.parseGalleryDuplicateReport({ ...report(), ...change }, ""), /vollständigen/);
  });
}

for (const path of ["../a.stl", "/a.stl", "a//b.stl", "a/../b.stl", "a\\b.stl", "file.txt", "a\x00.stl"]) {
  test(`duplicate report refuses unsafe or unsupported path ${JSON.stringify(path)}`, () => {
    assert.throws(() => contract.parseGalleryDuplicateReport(report("", [path, "safe.stl"]), ""), /vollständigen/);
  });
}

test("duplicate report binds every path to its requested folder and rejects duplicate identities", () => {
  assert.throws(() => contract.parseGalleryDuplicateReport(report("inside", ["inside/a.stl", "outside/b.stl"]), "inside"), /vollständigen/);
  assert.throws(() => contract.parseGalleryDuplicateReport(report("", ["same.stl", "same.stl"]), ""), /vollständigen/);
  const value = report("inside", ["inside/a.stl", "inside/b.obj"]);
  assert.equal(contract.parseGalleryDuplicateReport(value, "inside").duplicate_groups, 1);
});

function api(fetch: (url: string, options: RequestInit) => Promise<Response>) {
  return loadMobileModule("gallery-duplicate-api.ts", { modules: {
    "./ha-api-transport.js": { authenticatedFetch: fetch }, "./gallery-duplicate-contract.js": contract,
  }, globals: { URLSearchParams, DOMException, Error } }).exports.fetchGalleryDuplicates;
}

test("duplicate API uses its existing API base, one authenticated GET, encoded folder and abort signal", async () => {
  const folder = "Modelle & Teile"; const data = report(folder, [`${folder}/a.stl`, `${folder}/b.stl`]);
  const calls: { url: string; options: RequestInit }[] = [];
  const fetch = api(async (url, options) => { calls.push({url, options}); return Response.json({ data, error: null }); });
  const controller = new AbortController();
  const result = await fetch("studio/v1", folder, controller.signal);
  assert.equal(result.folder, folder); assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, "/api/studio/v1/gallery/duplicates?folder=Modelle+%26+Teile");
  assert.equal(calls[0]?.options.method, "GET"); assert.equal(calls[0]?.options.cache, "no-store");
  assert.equal(calls[0]?.options.signal, controller.signal); assert.equal(calls[0]?.options.body, undefined);
});

for (const status of [401, 403, 409, 422, 500]) {
  test(`duplicate API retains HTTP ${status} failure and never retries`, async () => {
    let calls = 0; const fetch = api(async () => { calls++; return Response.json({ error: { message: "Prüfung nicht vollständig" }, data: null }, { status }); });
    await assert.rejects(fetch("studio/v1", ""), /Prüfung nicht vollständig/); assert.equal(calls, 1);
  });
}

test("duplicate API recognizes missing backend and malformed success without fabricating an empty result", async () => {
  await assert.rejects(api(async () => new Response("Not found", { status: 404 }))("studio/v1", ""), /noch nicht verfügbar/);
  await assert.rejects(api(async () => new Response("not-json", { status: 200 }))("studio/v1", ""), /keine gültige/);
  await assert.rejects(api(async () => Response.json({ data: { groups: [] } }))("studio/v1", ""), /vollständigen/);
});

test("duplicate API does not start after cancellation and rejects invalid folders before fetch", async () => {
  let calls = 0; const fetch = api(async () => { calls++; return Response.json({data: empty()}); });
  const controller = new AbortController(); controller.abort();
  await assert.rejects(fetch("studio/v1", "", controller.signal), { name: "AbortError" });
  await assert.rejects(fetch("studio/v1", "../outside"), /Ungültiger/); assert.equal(calls, 0);
});

test("duplicate modal opens native top layer and double click does not start a second scan", async () => {
  const { view, root } = setup(); let calls = 0; const pending = deferred<contract.GalleryDuplicateReport>();
  const scan = () => { calls++; return pending.promise; };
  assert.equal(view.open("", scan, () => {}), true);
  assert.equal(view.open("", scan, () => {}), true);
  assert.equal(calls, 1); assert.equal(root.querySelector("dialog")?.modalCalls, 1);
  assert.equal(root.querySelector("dialog")?.getAttribute("aria-labelledby"), "duplicates-heading");
  assert.equal(root.querySelector(".results")?.getAttribute("aria-busy"), "true");
  assert.ok(control(root, "Schließen").focusCount >= 1);
  pending.resolve(report()); await settle();
  assert.equal(root.querySelector(".results")?.getAttribute("aria-busy"), "false");
  assert.equal(root.querySelectorAll(".group").length, 1); view.close();
});

for (const reason of ["button", "cancel", "native-close", "disconnect"]) {
  test(`duplicate modal ${reason} aborts request and ignores late completion`, async () => {
    const { view, root, focus } = setup(); const pending = deferred<contract.GalleryDuplicateReport>(); let signal!: AbortSignal;
    view.open("", (_folder: string, value: AbortSignal) => { signal = value; return pending.promise; }, () => assert.fail("navigation"));
    const dialog = root.querySelector("dialog")!;
    if (reason === "button") control(root, "Schließen").click();
    else if (reason === "cancel") {
      const event = new Event("cancel", { cancelable: true }); dialog.dispatchEvent(event); assert.equal(event.defaultPrevented, true);
    } else if (reason === "native-close") dialog.close();
    else { view.isConnected = false; view.disconnectedCallback(); }
    assert.equal(signal.aborted, true); assert.equal(root.querySelector("dialog"), null);
    pending.resolve(report()); await settle(); assert.equal(root.querySelector("dialog"), null);
    if (reason !== "disconnect") assert.ok(focus.focusCount >= 1);
  });
}

test("duplicate modal rejects late errors and old close events without damaging a replacement", async () => {
  const { view, root } = setup(); const old = deferred<contract.GalleryDuplicateReport>();
  view.open("old", () => old.promise, () => {}); const oldDialog = root.querySelector("dialog")!;
  view.open("new", () => Promise.resolve(report("new", ["new/a.stl", "new/b.stl"])), () => {});
  const current = root.querySelector("dialog")!;
  oldDialog.dispatchEvent(new Event("close")); old.reject(new Error("obsolete error")); await settle();
  assert.equal(root.querySelector("dialog"), current); assert.ok(current.open);
  assert.ok(text(root).includes("new/a.stl")); assert.ok(!text(root).includes("obsolete error")); view.close();
});

test("duplicate modal unavailable top layer or detached host never starts the scanner", () => {
  const { view, root } = setup(); let calls = 0; const scan = () => { calls++; return Promise.resolve(empty()); };
  MobileNode.failModal = true;
  try { assert.equal(view.open("", scan, () => {}), false); }
  finally { MobileNode.failModal = false; }
  assert.equal(root.querySelector("dialog"), null); view.isConnected = false;
  assert.equal(view.open("", scan, () => {}), false); assert.equal(calls, 0);
});

test("duplicate modal distinguishes scan failure from proven absence", async () => {
  const { view, root } = setup();
  view.open("", () => Promise.reject(new Error("Server ist noch nicht aktualisiert")), () => {}); await settle();
  assert.equal(root.querySelector(".status")?.getAttribute("role"), "alert");
  assert.ok(text(root).includes("Server ist noch nicht aktualisiert"));
  assert.equal(root.querySelectorAll(".empty").length, 0); view.close();
  view.open("", () => Promise.resolve(empty()), () => {}); await settle();
  assert.ok(text(root).includes("Keine bytegleichen Modelldateien")); view.close();
});

test("duplicate modal prints untrusted file paths as text and folder navigation is non-destructive", async () => {
  const { view, root } = setup(); const name = '<img onerror="bad">'; const folders: string[] = [];
  const data = contract.parseGalleryDuplicateReport(report("", [`${name}/a.stl`, `${name}/b.stl`]), "");
  view.open("", () => Promise.resolve(data), (folder: string) => folders.push(folder)); await settle();
  assert.equal(root.querySelectorAll("img").length, 0); assert.ok(text(root).includes(name));
  assert.ok(root.querySelectorAll("*").every((node) => !node.innerHTML.includes(name)));
  control(root, "Ordner öffnen").click();
  assert.deepEqual(folders, [name]); assert.equal(root.querySelector("dialog"), null);
  assert.ok(root.querySelectorAll("button").every((node) => !/löschen|zusammenführen/i.test(node.textContent)));
});

test("duplicate modal paginates groups, filters locally and does not rerun the scan", async () => {
  const { view, root } = setup(); const groups = Array.from({length: 43}, (_, i) => report("", [`${i}/a.stl`, `${i}/b.stl`]).groups[0]!);
  const data = { ...report(), groups, files_examined: 86, files_hashed: 86, bytes_hashed: 602, duplicate_groups: 43 };
  let calls = 0; view.open("", () => { calls++; return Promise.resolve(data); }, () => {}); await settle();
  assert.equal(root.querySelectorAll(".group").length, 20);
  control(root, "Nächste Gruppen").click(); assert.ok(text(root).includes("Gruppen 21–40 von 43"));
  control(root, "Nächste Gruppen").click(); assert.equal(root.querySelectorAll(".group").length, 3);
  assert.equal(control(root, "Nächste Gruppen").disabled, true);
  const filter = root.querySelector("input")!; filter.value = "42/"; filter.dispatchEvent(new Event("input"));
  assert.equal(root.querySelectorAll(".group").length, 1); assert.ok(text(root).includes("42/a.stl"));
  filter.value = "absent"; filter.dispatchEvent(new Event("input"));
  assert.ok(text(root).includes("Keine Duplikatgruppe passt")); assert.equal(calls, 1); view.close();
});

test("duplicate modal keeps large individual groups bounded and distinguishes hardlinks", async () => {
  const { view, root } = setup(); const data = report("", Array.from({ length: 57 }, (_, i) => `part-${i}.stl`));
  view.open("", () => Promise.resolve(data), () => {}); await settle();
  assert.equal(root.querySelectorAll(".file-path").length, 20);
  control(root, "Weitere Dateipfade").click(); assert.ok(text(root).includes("Dateipfade 21–40 von 57"));
  control(root, "Weitere Dateipfade").click(); assert.equal(root.querySelectorAll(".file-path").length, 17);
  assert.equal(control(root, "Weitere Dateipfade").disabled, true); view.close();
  const links = { ...report(), groups: [{ ...report().groups[0]!, independent_copies: 1, hardlink_aliases: 1, redundant_content_bytes: 0 }] };
  view.open("", () => Promise.resolve(links), () => {}); await settle();
  assert.ok(text(root).includes("1 unabhängige Dateikopien · 1 zusätzliche Hardlink-Verweise"));
  assert.ok(!text(root).includes("freigeben")); view.close();
});

// The production mount method is exercised with only its surrounding element
// and gallery dependencies doubled. No copy of its wiring is executed.
test("gallery production toolbar opens the actual duplicate dialog with current folder and no mutation", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "gallery-library-pane.ts"), "utf8");
  const ast = ts.createSourceFile("pane.ts", source, ts.ScriptTarget.Latest, true);
  const cls = ast.statements.find((node): node is ts.ClassDeclaration => ts.isClassDeclaration(node) && node.name?.text === "Ultimate3DGalleryLibraryPane")!;
  const mount = cls.members.find((node) => ts.isMethodDeclaration(node) && node.name.getText(ast) === "#mount")!;
  assert.ok(mount); assert.match(source, /import .*gallery-duplicates-dialog/);
  const injected = `class Probe {
    #root; #library = null; #folder = "picked/folder"; #operations = { busy: false }; #api; #selected = new Set(); #sort; #view;
    opened = []; errors = []; constructor(root, api) { this.#root=root; this.#api=api; }
    #refresh(){} #upload(){} #createFolder(){} #search(){} #renderData(){} #setView(){} #export(){} #import(){}
    #visibleItems(){return [];} #renderSelection(){} #bulkTransfer(){} #bulkRemove(){} #renderRecent(){}
    #openFolder(folder){this.opened.push(folder);} #showError(message){this.errors.push(message);}
    mount(){this.#mount();} busy(){this.#operations.busy=true;}
    ${mount.getText(ast)}
  } return Probe;`;
  const code = ts.transpileModule(injected, {compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
  const Constructor = new Function("STORAGE_WORKSPACE_STYLE", code)("");
  const { view: dialog, root: dialogRoot } = setup();
  const root = new MobileNode("root"); const query = root.querySelector.bind(root);
  root.querySelector = (selector: string) => selector === "gallery-duplicates-dialog" ? dialog : query(selector);
  let calls = 0;
  const instance = new Constructor(root, { duplicates: () => { calls++; return new Promise(() => {}); } });
  instance.mount(); const trigger = root.querySelector("#duplicates")!; assert.ok(trigger);
  trigger.click(); assert.ok(text(dialogRoot).includes("picked/folder")); assert.equal(calls, 1);
  dialog.close(); instance.busy(); trigger.click(); assert.equal(calls, 1);
  assert.equal(instance.errors.length, 1); assert.equal(dialogRoot.querySelector("dialog"), null);
  assert.match(source, /<gallery-duplicates-dialog><\/gallery-duplicates-dialog>/);
});


test("gallery API forwards its configured base and cancellation signal through the real duplicate transport", async () => {
  const calls: { url: string; options: RequestInit }[] = [];
  const fetch = api(async (url, options) => { calls.push({url, options}); return Response.json({ data: report("sub", ["sub/a.stl", "sub/b.stl"]), error: null }); });
  const module = loadMobileModule("gallery-api-v2.ts", { modules: {
    "./api-client.js": { StudioApiClient: class {} },
    "./upload-controller.js": { UploadController: class {} },
    "./ha-api-transport.js": {},
    "./gallery-duplicate-api.js": { fetchGalleryDuplicates: fetch },
  } });
  const controller = new AbortController();
  const result = await new module.exports.GalleryApi("candidate/v1").duplicates("sub", controller.signal);
  assert.equal(result.folder, "sub"); assert.equal(calls.length, 1);
  assert.equal(calls[0]?.url, "/api/candidate/v1/gallery/duplicates?folder=sub");
  assert.equal(calls[0]?.options.signal, controller.signal);
});
