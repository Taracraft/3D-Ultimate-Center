// Keep the MakerWorld dialog, return-from-cache and standalone material-viewer
// contracts in the standard frontend test graph, not only in an optional run.
import "./viewer-modal-contract.test.mjs";
import "./makerworld-resume.test.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makerWorldLicenseHtml } from "../frontend/makerworld-attribution.js";

test("MakerWorld preserves the supplied license text without interpreting permissions", () => {
  assert.match(makerWorldLicenseHtml("CC BY-NC 4.0"), /CC BY-NC 4\.0/);
});
test("MakerWorld missing licenses are explicitly unknown", () => {
  for (const value of [undefined, null, "", "  ", {}, false]) {
    assert.match(makerWorldLicenseHtml(value), /Keine Lizenzangabe/);
    assert.doesNotMatch(makerWorldLicenseHtml(value), /kommerziell erlaubt|gemeinfrei/);
  }
});
test("MakerWorld license metadata cannot inject markup", () => {
  const html = makerWorldLicenseHtml('<img src=x onerror="alert(1)"> & test');
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
  assert.match(html, /&quot;/);
  assert.match(html, /&amp; test/);
});
test("MakerWorld shows attribution next to transfer actions and never a fabricated verification badge", () => {
  const source = readFileSync("frontend/makerworld-detail-dialog-studio.ts", "utf8");
  assert.doesNotMatch(source, /mw-verified/);
  // The responsive layout owns a semantic footer outside the scrolling columns.
  const start = source.indexOf('<footer class="mw-target">');
  const end = source.indexOf('</footer>', start);
  assert.ok(start >= 0 && end > start, "transfer footer must be present and closed");
  const target = source.slice(start, end);
  assert.ok(target.includes("makerWorldLicenseHtml(detail.license)"));
  for (const action of ["studio", "save", "download"]) {
    assert.ok(target.includes(`data-action="${action}"`), `${action} must remain next to attribution`);
  }
});
