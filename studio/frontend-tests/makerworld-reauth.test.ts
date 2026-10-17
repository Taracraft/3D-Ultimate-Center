import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";

function production(path: string, globals: Record<string, unknown> = {}, expose = "") {
  const source = readFileSync(join(process.cwd(), "frontend", path), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
  } }).outputText.replace(/^import .*;\r?\n/gm, "").replace(/^export /gm, "");
  const sandbox: any = { console, ...globals };
  runInNewContext(`${compiled}\n${expose}`, sandbox);
  return sandbox;
}
function authModule() {
  return production("makerworld-reauth-dialog.ts", { callHomeAssistantOptionsFlow: () => { throw new Error("No real API"); } },
    "globalThis.api = { makerWorldReauthenticationEntry, MakerWorldReauthenticationFlow };").api;
}
const form = (step = "cloud_reauthenticate") => ({ type: "form", flow_id: "flow-fixture", step_id: step,
  data_schema: step === "init" ? [{ name: "cloud_reauthenticate", required: false, default: false },
    { name: "cloud_enabled", required: true, default: true }, { name: "password", required: false }] : [] });

test("MakerWorld login requires classified import account401 and bound config entry", () => {
  const { makerWorldReauthenticationEntry: entry } = authModule();
  const valid = { code: "makerworld_account_unauthorized", details: { upstream_status: 401, config_entry_id: "studio-entry" } };
  assert.equal(entry(valid), "studio-entry");
  for (const error of [new Error("HTTP 401"), null, { ...valid, code: "makerworld_signed_download_denied" },
    { ...valid, details: { ...valid.details, upstream_status: 403 } },
    { ...valid, details: { ...valid.details, config_entry_id: "../other-entry?token=x" } },
    { ...valid, details: { upstream_status: 401 } }]) assert.equal(entry(error), null);
});

test("MakerWorld reconnect uses only the existing HA optionsflow and verification-code steps", async () => {
  const { MakerWorldReauthenticationFlow: Flow } = authModule();
  const calls: any[] = [];
  const responses = [form("init"), form(), form("cloud_code"), { type: "create_entry" }];
  const flow = new Flow("studio-entry", async (...args: any[]) => { calls.push(args); return responses.shift(); });
  assert.equal((await flow.start()).step_id, "cloud_reauthenticate");
  const password = { cloud_email: "private@example.test", password: "SYNTHETIC-PRIVATE", cloud_region: "global" };
  assert.equal((await flow.submit(password)).step_id, "cloud_code");
  assert.equal((await flow.submit({ verification_code: "654321" })).type, "create_entry");
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
    ["POST", null, { handler: "studio-entry" }], ["POST", "flow-fixture", { cloud_reauthenticate: true, cloud_enabled: true }],
    ["POST", "flow-fixture", password], ["POST", "flow-fixture", { verification_code: "654321" }],
  ]);
  assert.equal(JSON.stringify(flow).includes("SYNTHETIC"), false);
  assert.equal(JSON.stringify(flow).includes("654321"), false);
  await flow.cancel(); assert.equal(calls.length, 4, "completed flow must not be deleted or replayed");
  await assert.rejects(() => flow.submit({ password: "never sent" }));
});

test("aborted and cancelled login never count as saved authorization", async () => {
  const { MakerWorldReauthenticationFlow: Flow } = authModule();
  const calls: any[] = [];
  const flow = new Flow("studio-entry", async (...args: any[]) => { calls.push(args); return args[0] === "DELETE" ? {} : form(args[1] ? "cloud_reauthenticate" : "init"); });
  await flow.start(); await flow.cancel(); await flow.cancel();
  assert.equal(calls.filter((call) => call[0] === "DELETE").length, 1);
  await assert.rejects(() => flow.submit({ verification_code: "never sent" }));
  const aborted = new Flow("studio-entry", async () => ({ type: "abort" }));
  assert.equal((await aborted.start()).type, "abort");
});

test("closing during flow creation removes the late pending HA flow without login submission", async () => {
  const { MakerWorldReauthenticationFlow: Flow } = authModule();
  let release!: (value: unknown) => void; const calls: any[] = [];
  const pending = new Promise((resolve) => { release = resolve; });
  const flow = new Flow("studio-entry", async (...args: any[]) => { calls.push(args); return args[0] === "DELETE" ? {} : pending; });
  const starting = flow.start(); await flow.cancel(); release(form("init"));
  assert.equal((await starting).type, "abort");
  assert.equal(calls.length, 2); assert.equal(calls[1][0], "DELETE");
});

test("an unrelated HA options step is rejected and cancelled", async () => {
  const { MakerWorldReauthenticationFlow: Flow } = authModule(); const methods: string[] = [];
  const flow = new Flow("studio-entry", async (method: string) => { methods.push(method); return form("unrelated_secret_step"); });
  await assert.rejects(() => flow.start(), /nicht verfügbar/);
  assert.deepEqual(methods, ["POST", "DELETE"]);
});

test("the dedicated HAflow transport never audits or exposes form secrets", async () => {
  const audits: any[] = [], calls: any[] = [];
  const sandbox = production("ha-api-transport.ts", { performance: { now: () => 0 },
    dispatchEvent: () => {}, Event: class {},
  }, "globalThis.probe = { set: (value) => homeAssistant = value, callHomeAssistantOptionsFlow };");
  sandbox.probe.set({ callApi: async (...args: any[]) => { calls.push(args); if (args[1].includes("audit")) audits.push(args); throw new Error("SYNTHETIC-PASSWORD-AND-CODE"); } });
  await assert.rejects(() => sandbox.probe.callHomeAssistantOptionsFlow("POST", "fixture", { password: "SECRET", verification_code: "123456" }),
    (error: any) => !error.message.includes("SYNTHETIC") && !error.message.includes("SECRET"));
  assert.equal(calls.length, 1); assert.equal(audits.length, 0);
  assert.equal(calls[0][1], "config/config_entries/options/flow/fixture");
});

test("MakerWorld import failure opens login once and requires a separate import click afterward", async () => {
  const error = { code: "makerworld_account_unauthorized", details: { upstream_status: 401, config_entry_id: "fixture" } };
  let resolve!: (value: boolean) => void; let popups = 0, imports = 0;
  const login = new Promise<boolean>((done) => { resolve = done; });
  const modal = { isConnected: true, querySelectorAll: () => [], setAttribute() {}, removeAttribute() {}, querySelector: () => modal };
  const state = { busy: false, closed: false };
  const sandbox = production("makerworld-detail-dialog-studio.ts", { AbortController,
    makerWorldReauthenticationEntry: authModule().makerWorldReauthenticationEntry,
    openMakerWorldReauthentication: async () => { popups += 1; return login; },
  }, "globalThis.probe = { runMakerWorldAction, register: (overlay, state) => dialogStates.set(overlay,state), silence: () => show = () => {} };");
  sandbox.probe.register(modal, state); sandbox.probe.silence();
  const action = async () => { imports += 1; throw error; };
  const pending = sandbox.probe.runMakerWorldAction(modal, action);
  await Promise.resolve(); await sandbox.probe.runMakerWorldAction(modal, action);
  assert.equal(popups, 1); assert.equal(imports, 1);
  resolve(true); await pending;
  assert.equal(imports, 1, "successful login must not replay the import"); assert.equal(state.busy, false);
});


test("HA required defaults are submitted only when schema-valid and never for secret fields", async () => {
  const { MakerWorldReauthenticationFlow: Flow } = authModule();
  for (const field of [{ name: "printer_name", required: true },
    { name: "password", required: true, default: "SECRET" },
    { name: "slicer_api_secret", required: true, default: "SECRET" }]) {
    const calls: any[] = [];
    const flow = new Flow("studio-entry", async (...args: any[]) => {
      calls.push(args); return { ...form("init"), data_schema: [
        { name: "cloud_reauthenticate", default: false }, field] };
    });
    await assert.rejects(() => flow.start());
    assert.equal(calls.length, 2); assert.equal(calls[1][0], "DELETE");
    assert.equal(JSON.stringify(calls).includes("SECRET"), false);
  }
});

test("a changed HAflow identifier cannot redirect password or code submission", async () => {
  const { MakerWorldReauthenticationFlow: Flow } = authModule();
  const calls: any[] = []; let request = 0;
  const flow = new Flow("studio-entry", async (...args: any[]) => {
    calls.push(args); request += 1;
    return request === 1 ? form("init") : { ...form(), flow_id: "other-flow" };
  });
  await assert.rejects(() => flow.start(), /geändert/);
  assert.equal(calls.at(-1)[0], "DELETE"); assert.equal(calls.at(-1)[1], "flow-fixture");
  await assert.rejects(() => flow.submit({ password: "never sent" }));
});

test("structured account401 survives the ordinary HA API and MakerWorld binary download paths", async () => {
  const error = { code: "makerworld_account_unauthorized", message: "Login required", details: { upstream_status: 401, config_entry_id: "studio-entry" } };
  const transport = production("ha-api-transport.ts", { performance: { now: () => 0 } },
    "globalThis.probe = { set: (value) => homeAssistant = value, callHomeAssistantApi, ApiResponseError };").probe;
  transport.set({ callApi: async (_method: string, path: string) => { if (path.includes("audit")) return {}; throw { body: { error } }; } });
  await assert.rejects(() => transport.callHomeAssistantApi("POST", "ultimate_3d_studio/v1/makerworld/instance/1/save", {}),
    (caught: any) => authModule().makerWorldReauthenticationEntry(caught) === "studio-entry");
  const binary = production("makerworld-api.ts", { ApiResponseError: transport.ApiResponseError,
    URLSearchParams, authenticatedFetch: async () => ({ ok: false, status: 502, json: async () => ({ error }) }),
  }, "globalThis.Api = MakerWorldApi;");
  await assert.rejects(() => new binary.Api().downloadInstance("instance", "3mf", "Fixture"),
    (caught: any) => authModule().makerWorldReauthenticationEntry(caught) === "studio-entry");
});
