import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

test("Studio shell has no duplicate internal navigation on desktop or mobile", () => {
  const view = readFileSync(join(process.cwd(), "frontend", "app-shell-view.ts"), "utf8");
  assert.ok(!view.includes("<nav"));
  assert.ok(!view.includes('id="nav-buttons"'));
  assert.ok(!view.includes('id="nav-live"'));
  assert.ok(!view.includes(".nav-buttons"));
  assert.ok(!view.includes("overflow-x:auto"));
  assert.ok(view.includes('.shell{display:grid;grid-template-columns:minmax(0,1fr)'));
  assert.ok(view.includes('.host{min-width:0;min-height:0;overflow:auto}'));
});
