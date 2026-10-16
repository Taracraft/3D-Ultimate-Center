import test from "node:test";
import assert from "node:assert/strict";
import { ContractElement, loadElementContract } from "./element-contract-harness.js";

function setup(savedRoute?: string) {
  const subscribers = new Set<(snapshot: unknown) => void>();
  const snapshot = { printers: [], jobs: { current: [] } };
  let workspaceClears = 0;
  const host = loadElementContract("app-shell-v4.ts", {}, {
    "./control-workspace.js": {}, "./gallery-workspace.js": {},
    "./studio-unified-workspace.js": {}, "./ams-workspace.js": {},
    "./profile-workspace.js": {}, "./job-workspaces.js": {}, "./system-workspace.js": {},
    "./ha-api-transport.js": { writeFrontendAudit: () => {} },
    "./workspace-file-handoff.js": { consumeWorkspaceFiles: () => [] },
    "./studio-persistence.js": { clearStudioWorkspace: async () => { workspaceClears += 1; } },
    "./job-activity-store.js": { jobActivityStore: {
      snapshot,
      subscribe(callback: (value: unknown) => void) { subscribers.add(callback); callback(snapshot); return () => subscribers.delete(callback); },
    } },
    "./print-live-telemetry.js": { printLayerLabel: () => "", printSpeedLabel: () => "" },
    "./print-remaining-time.js": { remainingTimeLabel: () => "" },
  });
  if (savedRoute) host.storage.setItem("ultimate-3d-studio:last-route", savedRoute);
  const Constructor = host.exported.Ultimate3DStudioShellV4 as new () => ContractElement & {
    connectedCallback(): void;
    disconnectedCallback(): void;
    navigate(route: { name: string; jobId?: string }): void;
  };
  const shell = new Constructor();
  shell.isConnected = true;
  shell.connectedCallback();
  const content = shell.shadowRoot!.querySelector("#host")!;
  const navigation = shell.shadowRoot!.querySelector("#nav-buttons")!;
  const disconnect = (): void => { shell.isConnected = false; shell.disconnectedCallback(); };
  const connect = (): void => { shell.isConnected = true; shell.connectedCallback(); };
  return { ...host, shell, content, navigation, subscribers, workspaceClears: () => workspaceClears, connect, disconnect };
}

test("navigation commits a clicked route once and keeps its workspace through its own hash event", () => {
  const app = setup();
  app.navigation.scrollLeft = 360;
  const profileButton = app.navigation.children.find((node) => node.dataset.route === "profile")!;
  profileButton.dispatchEvent(new Event("click"));
  const profile = app.content.children[0];
  profile.scrollTop = 280;
  app.flushHashes();
  assert.equal(app.content.children[0], profile, "own hash event must not recreate the workspace");
  assert.equal(profile.scrollTop, 280);
  assert.equal(app.navigation.scrollLeft, 360);
  app.disconnect();
});

test("external hashes including Back/Forward switch once while equivalent hashes preserve the workspace", () => {
  const app = setup();
  for (const route of ["#/profile", "#/galerie", "#/profile", "#/galerie"]) {
    app.location.hash = route;
    app.flushHashes();
    const expected = route === "#/profile" ? "ultimate-3d-profile-workspace" : "ultimate-3d-gallery-workspace";
    assert.equal(app.content.children[0].tagName, expected);
  }
  const gallery = app.content.children[0];
  app.location.hash = "#/galerie/";
  app.flushHashes();
  assert.equal(app.content.children[0], gallery, "equivalent route must preserve the mounted workspace");
  app.disconnect();
});

test("reconnected persistent shell restores hash and gallery listeners exactly once", async () => {
  const app = setup();
  app.disconnect();
  assert.equal(app.subscribers.size, 0);
  app.connect();
  app.disconnect();
  app.connect();
  assert.equal(app.subscribers.size, 1);
  app.location.hash = "#/profile";
  app.flushHashes();
  assert.equal(app.content.children[0].tagName, "ultimate-3d-profile-workspace");
  const file = new File(["project"], "selected.3mf");
  app.shell.dispatchEvent(Object.assign(new Event("gallery-open-studio"), { detail: { file } }));
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(app.workspaceClears(), 0, "the shell must not destroy the saved session before import");
  assert.equal(app.content.children[0].tagName, "ultimate-3d-unified-studio");
  assert.equal((app.content.children[0] as ContractElement & { file?: File }).file, file);
  app.disconnect();
});

test("reconnect catches a route changed while detached without remounting unchanged routes", () => {
  const app = setup();
  const control = app.content.children[0];
  app.disconnect();
  app.connect();
  assert.equal(app.content.children[0], control);
  app.disconnect();
  app.location.hash = "#/system";
  app.flushHashes();
  assert.equal(app.content.children[0], control, "detached shell must not process navigation");
  app.connect();
  assert.equal(app.content.children[0].tagName, "ultimate-3d-system-workspace");
  app.disconnect();
});

test("source requests after reconnect retain the requested gallery tab", () => {
  const app = setup();
  app.disconnect(); app.connect();
  app.shell.dispatchEvent(Object.assign(new Event("workspace-source-request"), { detail: { source: "makerworld" } }));
  const gallery = app.content.children[0] as ContractElement & { selectedTab?: string };
  assert.equal(gallery.tagName, "ultimate-3d-gallery-workspace");
  assert.equal(gallery.selectedTab, "makerworld");
  app.flushHashes();
  assert.equal(app.content.children[0], gallery);
  app.disconnect();
});

test("reconnect observes a hash cleared while detached and retains an unchanged empty-hash preference", () => {
  const app = setup("#/profile");
  assert.equal(app.content.children[0].tagName, "ultimate-3d-profile-workspace");
  const profile = app.content.children[0];
  app.disconnect(); app.connect();
  assert.equal(app.content.children[0], profile, "an unchanged empty hash must retain the restored preference");
  app.shell.navigate({ name: "system" }); app.flushHashes();
  app.disconnect();
  app.location.hash = ""; app.flushHashes();
  app.connect();
  assert.equal(app.content.children[0].tagName, "ultimate-3d-steuerung-workspace");
  app.disconnect();
});

test("slicer alias normalizes once and does not replace the persistent studio", () => {
  const app = setup();
  app.shell.navigate({ name: "studio" }); app.flushHashes();
  const studio = app.content.children[0];
  app.location.hash = "#/slicer/old-job"; app.flushHashes();
  assert.equal(app.location.hash, "#/studio");
  assert.equal(app.content.children[0], studio);
  assert.equal(app.content.children.length, 1);
  app.disconnect();
});

test("external job-specific routes retain their distinction while duplicate notifications do not remount", () => {
  const app = setup();
  app.location.hash = "#/aufgaben/job-a"; app.flushHashes();
  const first = app.content.children[0];
  app.location.hash = "#/aufgaben/job-b"; app.flushHashes();
  const second = app.content.children[0];
  assert.notEqual(second, first);
  app.events.dispatchEvent(new Event("hashchange"));
  assert.equal(app.content.children[0], second);
  app.disconnect();
});

test("navigation announces exactly the current workspace without changing scroll position", () => {
  const app = setup(); app.navigation.scrollLeft = 380;
  app.shell.navigate({ name: "profile" }); app.flushHashes();
  const current = app.navigation.children.filter((node) => node.getAttribute("aria-current") === "page");
  assert.equal(current.length, 1); assert.equal(current[0].dataset.route, "profile"); assert.equal(app.navigation.scrollLeft, 380);
  app.shell.navigate({ name: "system" }); app.flushHashes();
  assert.equal(current[0].getAttribute("aria-current"), null);
  app.disconnect();
});


test("repeated active tab clicks preserve workspace state and navigation scroll", () => {
  const app = setup();
  const button = app.navigation.children.find((node) => node.dataset.route === "profile")!;
  button.dispatchEvent(new Event("click")); app.flushHashes();
  const profile = app.content.children[0]; profile.scrollTop = 280;
  app.navigation.scrollLeft = 360;
  button.dispatchEvent(new Event("click")); app.flushHashes();
  assert.equal(app.content.children[0], profile);
  assert.equal(profile.scrollTop, 280);
  assert.equal(app.navigation.scrollLeft, 360);
  app.disconnect();
});

test("source requests can switch tabs inside an already mounted gallery", () => {
  const app = setup();
  app.shell.navigate({ name: "galerie" }); app.flushHashes();
  for (const source of ["makerworld", "storage"]) {
    app.shell.dispatchEvent(Object.assign(new Event("workspace-source-request"), { detail: { source } }));
    const gallery = app.content.children[0] as ContractElement & { selectedTab?: string };
    assert.equal(gallery.selectedTab, source);
  }
  app.disconnect();
});


test("replacing a project while already in Studio preserves the workspace until transactional import", async () => {
  const app = setup(); app.shell.navigate({ name: "studio" }); app.flushHashes();
  const old = app.content.children[0];
  const file = new File(["replacement"], "new.3mf");
  const calls: unknown[][] = [];
  (old as ContractElement & { openProject: (...args: unknown[]) => void }).openProject = (...args) => { calls.push(args); };
  app.shell.dispatchEvent(Object.assign(new Event("gallery-open-studio"), { detail: { file } }));
  await new Promise<void>((resolve) => setImmediate(resolve));
  assert.equal(app.workspaceClears(), 0);
  assert.equal(app.content.children.length, 1);
  assert.equal(app.content.children[0], old);
  assert.equal(calls.length, 1);
  assert.equal(calls[0]![0], file);
  assert.equal((calls[0]![1] as { replaceWorkspace: boolean }).replaceWorkspace, true);
  assert.equal(app.content.children[0].tagName, "ultimate-3d-unified-studio");
  app.disconnect();
});
