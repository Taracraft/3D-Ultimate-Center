import test from "node:test";
import assert from "node:assert/strict";
import { legacyDatabaseVersion, latestLegacyWorkspace, storageValuesEqual, upgradeStudioPreference, upgradeWorkspaceJobReferences, type WorkspaceArchive } from "../frontend/studio-storage-upgrade.js";

class Preferences {
  readonly data = new Map<string, string>();
  failWrite = "";
  ignoreWrite = "";
  failRemove = "";
  constructor(entries: Array<[string, string]>) { this.data = new Map(entries); }
  get length() { return this.data.size; }
  key(index: number) { return [...this.data.keys()][index] ?? null; }
  getItem(key: string) { return this.data.get(key) ?? null; }
  setItem(key: string, value: string) {
    if (key === this.failWrite) throw new Error("quota");
    if (key !== this.ignoreWrite) this.data.set(key, value);
  }
  removeItem(key: string) {
    if (key === this.failRemove) throw new Error("blocked");
    this.data.delete(key);
  }
}
const target = "ultimate-3d-studio:last-route";
const old = "ultimate-3d-studio-v" + 6 + ":last-route";

test("preference migration archives all earlier values and selects the latest namespace", () => {
  const earlier = "ultimate-3d-studio-v5:last-route";
  const storage = new Preferences([[old, "#/galerie"], [earlier, "#/profile"], ["other:last-route", "safe"]]);
  assert.deepEqual(upgradeStudioPreference(storage, target), { value: "#/galerie", copied: true, error: "" });
  assert.equal(storage.getItem(target), "#/galerie");
  assert.equal(storage.getItem(old), null);
  assert.equal(storage.getItem(earlier), null);
  assert.equal(storage.getItem("other:last-route"), "safe");
  assert.deepEqual(JSON.parse(storage.getItem(target + ":migration-backup")!).values,
    [{ version: 6, value: "#/galerie" }, { version: 5, value: "#/profile" }]);
});

test("new preferences win and repeated reads do not revive an old selection", () => {
  const storage = new Preferences([[old, "#/profile"], [target, "#/system"]]);
  assert.deepEqual(upgradeStudioPreference(storage, target), { value: "#/system", copied: true, error: "" });
  assert.equal(storage.getItem(old), null);
  const clean = new Preferences([[old, "#/profile"]]);
  upgradeStudioPreference(clean, target);
  clean.removeItem(target);
  assert.equal(upgradeStudioPreference(clean, target).value, null);
});

test("a quota failure preserves the old value and restores the prior backup", () => {
  const prior = JSON.stringify({ format: 1, values: [{ version: 4, value: "#/ams" }] });
  const storage = new Preferences([[old, "#/profile"], [target + ":migration-backup", prior]]);
  storage.failWrite = target;
  assert.match(upgradeStudioPreference(storage, target).error, /quota/);
  assert.equal(storage.getItem(old), "#/profile");
  assert.equal(storage.getItem(target), null);
  assert.equal(storage.getItem(target + ":migration-backup"), prior);
});

test("failed readback never removes the original preference", () => {
  const storage = new Preferences([[old, "#/profile"]]);
  storage.ignoreWrite = target;
  assert.match(upgradeStudioPreference(storage, target).error, /zurückgelesen/);
  assert.equal(storage.getItem(old), "#/profile");
  assert.equal(storage.getItem(target), null);
});

test("failure during removal rolls back a partially migrated preference group", () => {
  const earlier = "ultimate-3d-studio-v5:last-route";
  const storage = new Preferences([[old, "#/galerie"], [earlier, "#/profile"]]);
  storage.failRemove = earlier;
  assert.match(upgradeStudioPreference(storage, target).error, /blocked/);
  assert.equal(storage.getItem(old), "#/galerie");
  assert.equal(storage.getItem(earlier), "#/profile");
  assert.equal(storage.getItem(target), null);
});

test("unknown backup formats are preserved and foreign preference keys are untouched", () => {
  const storage = new Preferences([[old, "#/profile"], [target + ":migration-backup", "invalid"]]);
  assert.ok(upgradeStudioPreference(storage, target).error);
  assert.equal(storage.getItem(target + ":migration-backup"), "invalid");
  assert.equal(upgradeStudioPreference(storage, "another:route").value, null);
});

test("database discovery accepts earlier numeric studio versions and rejects unrelated databases", () => {
  assert.equal(legacyDatabaseVersion("ultimate-3d-studio-v" + 6), 6);
  for (const name of ["ultimate-3d-studio", "other-v6", "ultimate-3d-studio-v0", "ultimate-3d-studio-v6-backup"]) {
    assert.equal(legacyDatabaseVersion(name), null);
  }
});

test("workspace selection uses save time and preserves geometry and job references unchanged", () => {
  const newer = { version: 1, savedAt: 200, positions: new Float32Array([1, 2, 3]), jobId: "existing-job" };
  const archives: WorkspaceArchive[] = [
    { legacyVersion: 6, databaseVersion: 1, keys: ["active"], values: [{ version: 1, savedAt: 100 }] },
    { legacyVersion: 5, databaseVersion: 1, keys: ["active"], values: [newer] },
  ];
  assert.equal(latestLegacyWorkspace(archives), newer);
  assert.equal(storageValuesEqual(newer, structuredClone(newer)), true);
});

test("workspace selection rejects invalid snapshots and resolves equal save times deterministically", () => {
  const chosen = { version: 1, savedAt: 200 };
  const rows: WorkspaceArchive[] = [
    { legacyVersion: 5, databaseVersion: 1, keys: ["active"], values: [{ version: 1, savedAt: 200 }] },
    { legacyVersion: 6, databaseVersion: 1, keys: ["active"], values: [chosen] },
    { legacyVersion: 7, databaseVersion: 1, keys: ["active"], values: [{ version: 2, savedAt: 900 }] },
  ];
  assert.equal(latestLegacyWorkspace(rows), chosen);
  assert.equal(latestLegacyWorkspace([{ legacyVersion: 9, databaseVersion: 1, keys: ["active"], values: [{ version: 1, savedAt: NaN }] }]), null);
});

test("readback comparison detects changed mesh bytes, array shapes and missing keys", () => {
  assert.equal(storageValuesEqual(new Float32Array([1, 2]), new Float32Array([1, 3])), false);
  assert.equal(storageValuesEqual(new Uint8Array([1]), new Int8Array([1])), false);
  assert.equal(storageValuesEqual([1, 2], [1]), false);
  assert.equal(storageValuesEqual({ item: undefined }, {}), false);
  assert.equal(storageValuesEqual(new Date(1), new Date(1)), true);
});

test("workspace migration rebinds only plate job references and preserves the archived original", () => {
  const prefix = "v" + 6;
  const mesh = new Float32Array([1, 2, 3]);
  const original = { version: 1, savedAt: 200, name: `${prefix} user title`, plates: [
    { jobId: `${prefix}-one`, name: `${prefix} plate`, instances: [{ positions: mesh }], selection: { id: `${prefix}-profile` } },
    { jobId: "studio-current" },
  ], paintLayers: [[1, { text: prefix, jobId: `${prefix}-untouched` }]] };
  const before = structuredClone(original);
  const upgraded = upgradeWorkspaceJobReferences(original, 6) as typeof original;
  assert.equal(upgraded.plates[0]!.jobId, "studio-one");
  assert.equal(upgraded.plates[1], original.plates[1]);
  assert.equal(upgraded.plates[0]!.instances, original.plates[0]!.instances);
  assert.equal(upgraded.plates[0]!.selection, original.plates[0]!.selection);
  assert.equal(upgraded.paintLayers, original.paintLayers);
  assert.equal(upgraded.name, original.name);
  assert.equal(storageValuesEqual(original, before), true);
});

test("workspace worker identifiers match delimited and early diagnostic names", () => {
  const prefix = "v" + 6;
  const source = { version: 1, plates: [
    { jobId: `${prefix}-abc123` }, { jobId: `codex-${prefix}-probe` }, { jobId: `${prefix}test1783740501` },
    { jobId: "IPv6-probe" }, { jobId: "riscv64-probe" }, { jobId: "v5-test" },
  ] };
  const upgraded = upgradeWorkspaceJobReferences(source, 6) as typeof source;
  assert.deepEqual(upgraded.plates.map((plate) => plate.jobId), ["studio-abc123", "codex-studio-probe", "studiotest1783740501", "IPv6-probe", "riscv64-probe", "v5-test"]);
  assert.equal(upgradeWorkspaceJobReferences(upgraded, 6), upgraded);
});

test("workspace selection performs reference migration while keeping raw recovery archives", () => {
  const original = { version: 1, savedAt: 200, plates: [{ jobId: "v" + 6 + "-saved" }] };
  const archives: WorkspaceArchive[] = [{ legacyVersion: 6, databaseVersion: 1, keys: ["active"], values: [original] }];
  const selected = latestLegacyWorkspace(archives) as typeof original;
  assert.equal(selected.plates[0]!.jobId, "studio-saved");
  assert.equal(archives[0]!.values[0], original);
  assert.equal(original.plates[0]!.jobId, "v" + 6 + "-saved");
});

test("unknown workspace shapes and invalid job identifiers are retained without guessing", () => {
  for (const value of [null, "text", { version: 2, plates: [] }, { version: 1, plates: "invalid" }]) {
    assert.equal(upgradeWorkspaceJobReferences(value, 6), value);
  }
  const value = { version: 1, plates: [null, { jobId: "../v" + 6 + "-other" }, { jobId: 123 }, { jobId: "v" + 6 + ":user" }] };
  assert.equal(upgradeWorkspaceJobReferences(value, 6), value);
  assert.equal(upgradeWorkspaceJobReferences(value, NaN), value);
});
