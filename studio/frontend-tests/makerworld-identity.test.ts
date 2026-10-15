import test from "node:test";
import assert from "node:assert/strict";
import { loadMobileModule } from "./mobile-contract-harness.js";

function fixture() {
  const calls: { method: string; url: string; body?: any }[] = [];
  let detail: any = { id: "123", instances: [{ id: "instance-A", design_id: "123", profile_id: "profile-A", model_id: "ModelAAA" }] };
  const loaded = loadMobileModule("makerworld-api.ts", {
    modules: { "./ha-api-transport.js": {
      async callEnvelopeApi(method: string, url: string, body?: any) {
        calls.push({ method, url, body });
        return method === "GET" ? detail : { asset_id: "fixture" };
      },
      async authenticatedFetch(url: string) {
        calls.push({ method: "FILE", url });
        return { ok: true, headers: { get: () => null }, blob: async () => ({ type: "model/3mf" }) };
      },
    }},
    globals: { URLSearchParams, File: class { constructor(readonly parts: any[], readonly name: string, readonly options: any) {} } },
  });
  const api = new loaded.exports.MakerWorldApi();
  return { api, calls, setDetail(value: any) { detail = value; } };
}
test("MakerWorld file and save use distinct design instance profile and model identities", async () => {
  const f = fixture(); await f.api.detail("123");
  await f.api.downloadInstance("instance-A", "3mf", "fixture");
  await f.api.saveInstance("instance-A", "", "fixture");
  const url = new URL(f.calls[1].url, "https://fixture.invalid");
  assert.match(url.pathname, /instance\/instance-A\/download$/);
  assert.equal(url.searchParams.get("design_id"), "123");
  assert.equal(url.searchParams.get("profile_id"), "profile-A");
  assert.equal(url.searchParams.get("model_id"), "ModelAAA");
  assert.equal(f.calls[2].body.profile_id, "profile-A");
  assert.equal(f.calls[2].body.model_id, "ModelAAA");
});
test("MakerWorld selected dialog instance retains its identity after another detail response", async () => {
  const f = fixture();
  const first = await f.api.detail("123");
  f.setDetail({ id: "456", instances: [{ id: "instance-A", design_id: "456", profile_id: "profile-B", model_id: "ModelBBB" }] });
  await f.api.detail("456");
  await f.api.downloadInstance("instance-A", "3mf", "fixture", first.instances[0]);
  await f.api.saveInstance("instance-A", "", "fixture", false, first.instances[0]);
  const url = new URL(f.calls[2].url, "https://fixture.invalid");
  assert.equal(url.searchParams.get("design_id"), "123");
  assert.equal(url.searchParams.get("profile_id"), "profile-A");
  assert.equal(f.calls[3].body.model_id, "ModelAAA");
});
test("MakerWorld mismatched selected instance is rejected before any transport", async () => {
  const f = fixture();
  const wrong = { id: "other", design_id: "123", profile_id: "profile-A", model_id: "ModelAAA" };
  await assert.rejects(f.api.downloadInstance("instance-A", "3mf", "fixture", wrong));
  await assert.rejects(f.api.saveInstance("instance-A", "", "fixture", false, wrong));
  assert.equal(f.calls.length, 0);
});
