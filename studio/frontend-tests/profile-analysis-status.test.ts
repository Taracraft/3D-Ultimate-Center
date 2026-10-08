import test from "node:test";
import assert from "node:assert/strict";
import { profileApplicationMarkup, profileApplicationSummary } from "../frontend/profile-application-status.js";
import type { SliceProfileApplication } from "../frontend/slicing-api.js";

const applied: SliceProfileApplication = {
  selected: true, applied: true, gcode_confirmed: false,
  confirmation_source: "pending_gcode_analysis",
  process: { name: '<img src=x onerror="alert(1)">', selected_setting_count: 2 },
  filament_profile_count: 1, material_channel_count: 1,
};

test("completed but unconfirmed G-code analysis is visible in summary and proof panel", () => {
  const result = { ...applied, confirmation_source: "gcode_analysis_unconfirmed" };
  assert.match(profileApplicationSummary(result), /! G-Code geprüft, Profilnachweis unvollständig/);
  const html = profileApplicationMarkup(result);
  assert.match(html, /profile-proof-step unconfirmed/);
  assert.match(html, /Die G-Code-Analyse liegt vor/);
  assert.match(html, /Abweichungen und fehlende Nachweise/);
  assert.equal((html.match(/profile-proof-step done/g) || []).length, 2);
  assert.doesNotMatch(html, /<img|onerror="/);
});

test("missing analysis stays pending and is never claimed as completed", () => {
  assert.match(profileApplicationSummary(applied), /… im Artefakt bestätigt/);
  const html = profileApplicationMarkup(applied);
  assert.match(html, /profile-proof-step pending/);
  assert.doesNotMatch(html, /Die G-Code-Analyse liegt vor|profile-proof-step unconfirmed/);
});

test("confirmed analysis retains the positive proof only with explicit confirmation", () => {
  const source = "parsed_gcode_header_and_toolpath";
  const confirmed = { ...applied, confirmation_source: source, gcode_confirmed: true };
  assert.match(profileApplicationSummary(confirmed), /✓ im Artefakt bestätigt/);
  assert.equal((profileApplicationMarkup(confirmed).match(/profile-proof-step done/g) || []).length, 3);
  assert.match(profileApplicationMarkup(confirmed), /stimmen mit analysiertem G-Code-Header/);
  assert.doesNotMatch(profileApplicationMarkup({ ...confirmed, gcode_confirmed: false }), /stimmen mit analysiertem G-Code-Header/);
});
