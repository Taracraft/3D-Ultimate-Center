import test from "node:test";
import assert from "node:assert/strict";
import { errorMessage, configureHomeAssistantApi, callHomeAssistantApi } from "../frontend/ha-api-transport.js";

const detail = "Druckjob nicht freigegeben: konkrete Artefaktprüfung fehlgeschlagen.";
const failure = { error: "Response error: 502", status_code: 502, body: { data: null, error: { code: "printer_upload_error", message: detail } } };

test("structured server failure is not hidden by Home Assistant HTTP 502 wrapper", () => {
  assert.equal(errorMessage(failure), detail);
});
test("structured server failure also survives an Error instance wrapper", () => {
  assert.equal(errorMessage(Object.assign(new Error("Response error: 502"), { body: failure.body })), detail);
});
test("malformed or empty error bodies retain existing fallback handling", () => {
  for (const body of [undefined, null, "<html>Bad Gateway</html>", { error: { message: "" } }, { error: { message: 502 } }]) {
    assert.equal(errorMessage({ error: "Response error: 502", body }), "Response error: 502");
  }
  assert.equal(errorMessage(new Error("Netzwerkfehler")), "Netzwerkfehler");
  assert.equal(errorMessage({ error: { message: detail } }), detail);
});
test("failed print preparation surfaces the body without retrying its POST", async () => {
  let preparationRequests = 0;
  configureHomeAssistantApi({ callApi: async <T>(_method: string, path: string): Promise<T> => {
    if (path.endsWith("system/audit")) return {} as T;
    preparationRequests += 1;
    throw failure;
  } });
  try {
    await assert.rejects(callHomeAssistantApi("POST", "ultimate_3d_studio_v6/v1/slicer/jobs/test/print/prepare", { printer_id: "test" }), { message: detail });
    assert.equal(preparationRequests, 1);
  } finally {
    configureHomeAssistantApi(null);
  }
});
