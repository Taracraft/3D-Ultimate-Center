import test from "node:test";
import assert from "node:assert/strict";
import { openSupportWarning, supportWarningHtml } from "../frontend/support-warning-dialog.js";
import type { FloatingSupportIssue } from "../frontend/floating-support-analysis.js";

const issue: FloatingSupportIssue = {
  instanceId: "support-object", name: "Überhang <img src=x onerror='run()'> & \"Teil\"",
  floatingShellCount: 1, minimumGapMm: 2, overhangTriangleCount: 5,
  maxOverhangMm: 3, maxOverhangAngleDeg: 20, bridgeOverhangMm: 2,
};

class DialogDouble extends EventTarget {
  open = false;
  removed = false;
  id = "";
  className = "";
  innerHTML = "";
  readonly events: string[] = [];
  readonly buttons = new Map(["cancel", "enable", "continue"].map((decision) => [decision, new EventTarget()]));
  setAttribute(): void {}
  querySelector(selector: string): EventTarget | null {
    return this.buttons.get(selector.match(/="(\w+)"/)?.[1] || "") ?? null;
  }
  showModal(): void { this.events.push("modal"); this.open = true; }
  close(): void { this.events.push("close"); this.open = false; queueMicrotask(() => this.dispatchEvent(new Event("close"))); }
  remove(): void { this.events.push("remove"); this.removed = true; }
}

function setup(): { dialog: DialogDouble; root: ShadowRoot } {
  const dialog = new DialogDouble();
  const root = {
    ownerDocument: { createElement: (tag: string) => { assert.equal(tag, "dialog"); return dialog; } },
    append: () => dialog.events.push("append"),
  } as unknown as ShadowRoot;
  return { dialog, root };
}

test("support dialog waits for an explicit decision and settles once after cleanup", async () => {
  for (const decision of ["cancel", "enable", "continue"] as const) {
    const { dialog, root } = setup();
    const warning = openSupportWarning(root, [issue]);
    let settled = false;
    void warning.result.then(() => { settled = true; });
    await Promise.resolve();
    assert.equal(settled, false);
    assert.deepEqual(dialog.events, ["append", "modal"]);
    dialog.buttons.get(decision)!.dispatchEvent(new Event("click"));
    dialog.buttons.get("continue")!.dispatchEvent(new Event("click"));
    warning.cancel();
    assert.equal(await warning.result, decision);
    assert.equal(dialog.removed, true);
    assert.deepEqual(dialog.events, ["append", "modal", "close", "remove"]);
  }
});

test("Escape, native close and disconnect cleanup resolve support warning as cancel", async () => {
  for (const action of ["escape", "close", "disconnect"]) {
    const { dialog, root } = setup();
    const warning = openSupportWarning(root, [issue]);
    if (action === "disconnect") warning.cancel();
    else if (action === "close") dialog.close();
    else {
      const event = new Event("cancel", { cancelable: true });
      dialog.dispatchEvent(event);
      assert.equal(event.defaultPrevented, true);
    }
    assert.equal(await warning.result, "cancel");
    assert.equal(dialog.removed, true);
    assert.equal(dialog.open, false);
  }
});

test("failure to enter the native modal layer removes the support dialog and propagates failure", () => {
  const { dialog, root } = setup();
  dialog.showModal = () => { throw new Error("modal unavailable"); };
  assert.throws(() => openSupportWarning(root, [issue]), /modal unavailable/);
  assert.equal(dialog.removed, true);
  assert.equal(dialog.open, false);
});

test("support warning preserves every affected name as escaped text", () => {
  const html = supportWarningHtml(Array.from({ length: 60 }, (_, i) => ({ ...issue, name: `${issue.name} Nr. ${i}` })));
  assert.equal((html.match(/<li>/g) || []).length, 60);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img src=x onerror=&#39;run\(\)&#39;&gt; &amp; &quot;Teil&quot; Nr. 59/);
});
