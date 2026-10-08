import test from "node:test";
import assert from "node:assert/strict";
import { ContractElement, loadElementContract } from "./element-contract-harness.js";

type Request = { signal: AbortSignal; resolve: (response: unknown) => void };
function setup() {
  const requests: Request[] = [];
  const revoked: string[] = [];
  const intervals = new Map<number, () => void>();
  const timeouts = new Map<number, () => void>();
  let timerId = 0;
  let objectId = 0;
  class LoadedImage extends EventTarget {
    complete = false;
    naturalWidth = 0;
    #src = "";
    get src(): string { return this.#src; }
    set src(value: string) {
      this.#src = value;
      this.complete = true;
      this.naturalWidth = 640;
      this.dispatchEvent(new Event("load"));
    }
  }
  const host = loadElementContract("printer-camera-panel.ts", {
    Image: LoadedImage,
    fetch: (_url: string, options: { signal: AbortSignal }) => new Promise((resolve) => {
      // Deliberately permit completion after abort to verify stale-request guards.
      requests.push({ signal: options.signal, resolve });
    }),
    URL: {
      createObjectURL: () => `blob:frame-${++objectId}`,
      revokeObjectURL: (url: string) => { revoked.push(url); },
    },
    setInterval: (callback: () => void) => { const id = ++timerId; intervals.set(id, callback); return id; },
    clearInterval: (id: number) => { intervals.delete(id); },
    setTimeout: (callback: () => void) => { const id = ++timerId; timeouts.set(id, callback); return id; },
    clearTimeout: (id: number) => { timeouts.delete(id); },
  });
  const Constructor = host.exported.PrinterCameraPanel as new () => ContractElement & {
    hass: unknown;
    connectedCallback(): void;
    disconnectedCallback(): void;
    toggle(): void;
  };
  const camera = new Constructor();
  const states = { "camera.studio": { state: "idle", attributes: { provider: "bambu_native_tls_jpeg", sequence: 1 } } };
  camera.hass = { states };
  camera.isConnected = true;
  camera.connectedCallback();
  const complete = async (request: Request): Promise<void> => {
    request.resolve({ ok: true, blob: async () => new Blob(["jpeg"], { type: "image/jpeg" }) });
    await new Promise<void>((resolve) => setImmediate(resolve));
  };
  const disconnect = (): void => { camera.isConnected = false; camera.disconnectedCallback(); };
  return { ...host, camera, requests, revoked, intervals, timeouts, complete, disconnect,
    image: camera.shadowRoot!.querySelector("#camera-image")!,
    loading: camera.shadowRoot!.querySelector("#loading")!,
    tick: (): void => { for (const callback of intervals.values()) callback(); },
  };
}

for (const event of ["online", "pageshow", "focus"]) {
  test(`camera ${event} replaces a stalled request without waiting for its timeout`, async () => {
    const app = setup();
    assert.equal(app.requests.length, 1);
    app.events.dispatchEvent(new Event(event));
    assert.equal(app.requests[0].signal.aborted, true);
    assert.equal(app.requests.length, 2, "resume must start a fresh request immediately");
    await app.complete(app.requests[0]);
    assert.equal(app.loading.classes.has("visible"), true, "old cleanup must not unlock the new request");
    assert.equal(app.image.src, "");
    await app.complete(app.requests[1]);
    assert.match(app.image.src, /^blob:frame-/);
    assert.equal(app.image.hidden, false);
    app.tick();
    assert.equal(app.requests.length, 3, "automatic frame polling must continue after recovery");
    app.disconnect();
  });
}

test("camera suspends a background request and starts fresh when the document becomes visible", async () => {
  const app = setup();
  app.document.hidden = true;
  app.document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(app.requests[0].signal.aborted, true);
  app.events.dispatchEvent(new Event("online"));
  app.tick();
  assert.equal(app.requests.length, 1, "hidden cameras must not start network work");
  app.document.hidden = false;
  app.document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(app.requests.length, 2);
  await app.complete(app.requests[1]);
  const visible = app.image.src;
  await app.complete(app.requests[0]);
  assert.equal(app.image.src, visible, "late background completion must never replace a recovered frame");
  app.disconnect();
});

test("camera recovery preserves the displayed frame until its replacement has loaded", async () => {
  const app = setup();
  await app.complete(app.requests[0]);
  const original = app.image.src;
  app.tick();
  app.events.dispatchEvent(new Event("online"));
  assert.equal(app.image.src, original);
  assert.equal(app.image.hidden, false);
  assert.equal(app.revoked.includes(original), false);
  assert.equal(app.requests.length, 3);
  await app.complete(app.requests[2]);
  assert.notEqual(app.image.src, original);
  assert.equal(app.revoked.filter((url) => url === original).length, 1);
  await app.complete(app.requests[1]);
  app.disconnect();
});

test("collapsed and detached cameras ignore resume notifications", () => {
  const app = setup();
  app.camera.toggle();
  for (const event of ["online", "pageshow", "focus"]) app.events.dispatchEvent(new Event(event));
  assert.equal(app.requests.length, 1);
  app.disconnect();
  assert.equal(app.requests[0].signal.aborted, true);
  for (const event of ["online", "pageshow", "focus"]) app.events.dispatchEvent(new Event(event));
  assert.equal(app.requests.length, 1);
  assert.equal(app.intervals.size, 0);
});

test("camera disconnect and reconnect releases the old request and resumes polling", async () => {
  const app = setup();
  app.disconnect();
  app.camera.isConnected = true;
  app.camera.connectedCallback();
  assert.equal(app.requests.length, 2);
  assert.equal(app.requests[0].signal.aborted, true);
  assert.equal(app.intervals.size, 1);
  await app.complete(app.requests[1]);
  assert.equal(app.image.hidden, false);
  app.disconnect();
});
