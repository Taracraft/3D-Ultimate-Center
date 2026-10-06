import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

test("mobile navigation stays horizontally scrollable without stretching active tabs", () => {
  const view = readFileSync(join(process.cwd(), "frontend", "app-shell-view.ts"), "utf8");
  const marker = "@media(max-width:800px){";
  const mobile = view.slice(view.indexOf(marker));
  assert.ok(mobile.startsWith(marker));
  assert.ok(mobile.includes("nav{display:grid;grid-template-columns:minmax(0,1fr);padding:0;overflow:hidden;grid-template-rows:58px auto;align-content:start"));
  assert.ok(mobile.includes(".nav-buttons{display:flex;width:100%;min-width:0;height:58px;max-height:58px;align-items:center"));
  assert.ok(mobile.includes("overflow-x:auto;overflow-y:hidden"));
  assert.ok(mobile.includes("overscroll-behavior-x:contain"));
  assert.ok(mobile.includes("overscroll-behavior-inline:contain"));
  assert.ok(mobile.includes("overflow-anchor:none"));
  assert.ok(mobile.includes(".nav-buttons button{flex:0 0 auto;align-self:center;width:auto;height:42px;min-height:42px;max-height:42px"));
  assert.ok(mobile.includes(".nav-live{grid-row:2;align-self:start"));
});
