import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Execute the actual dialog renderers and event binders. The tiny controls below
// replace only browser event targets; sorting, visibility and markup stay real.
const source = readFileSync(join(process.cwd(), "frontend", "makerworld-detail-dialog-studio.ts"), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
} }).outputText
  .replace(/^import .*;\r?\n/gm, "")
  .replace(/^export /gm, "");
const sandbox: any = { console, descriptionImageUrls: () => [], makerWorldLicenseHtml: () => "" };
runInNewContext(`${compiled}\nglobalThis.discussion = { commentHtml, reviewsPanel,
  createDiscussionState: typeof createDiscussionState === "function" ? createDiscussionState : undefined,
  bindDiscussionControls: typeof bindDiscussionControls === "function" ? bindDiscussionControls : undefined,
  statButtons,
  shareMakerWorldLink: typeof shareMakerWorldLink === "function" ? shareMakerWorldLink : undefined,
  render, register: (overlay, state) => dialogStates.set(overlay, state) };`, sandbox);
const production = sandbox.discussion;

function comment(id: string, changes: any = {}): any {
  return { id, author: id, avatar_url: null, content: `content-${id}`, created_at: "2026-10-01T12:00:00Z",
    like_count: 0, reply_count: 0, rating: 0, boosted: false, original_available: false, replies: [], ...changes };
}
function replies(count: number, prefix = "reply"): any[] {
  return Array.from({ length: count }, (_, index) => comment(`${prefix}-${index + 1}`));
}
function detail(comments: any[]): any {
  return { comments, comment_count: comments.length, stats: { comments: comments.length } };
}
function state(): any {
  return production.createDiscussionState?.() ?? { sort: "all", expandedReplies: new Set<string>(), originalComments: new Set<string>() };
}
function controlsFrom(html: string, attribute: string): any[] {
  return [...html.matchAll(new RegExp(`<button[^>]*${attribute}="([^"]+)"[^>]*>`, "g"))].map((match) => {
    const key = attribute === "data-review-sort" ? "reviewSort" : attribute === "data-original-toggle" ? "originalToggle" : "repliesToggle";
    const value = match[1]!.replace(/&(?:amp|quot|#39|lt|gt);/g, (entity) =>
      ({ "&amp;": "&", "&quot;": '"', "&#39;": "'", "&lt;": "<", "&gt;": ">" }[entity] || entity));
    const handlers: (() => void)[] = [];
    return { dataset: { [key]: value }, addEventListener: (_name: string, handler: () => void) => handlers.push(handler),
      click: () => handlers.forEach((handler) => handler()) };
  });
}
function mount(comments: any[]): any {
  assert.equal(typeof production.bindDiscussionControls, "function", "dialog must bind real discussion controls");
  const current = state();
  let html = "", sortControls: any[] = [], replyControls: any[] = [], originalControls: any[] = [], active = true;
  const dialog = { querySelectorAll: (selector: string) => selector === "[data-review-sort]" ? sortControls
    : selector === "[data-replies-toggle]" ? replyControls : originalControls };
  const render = () => {
    html = production.reviewsPanel(detail(comments), current);
    sortControls = controlsFrom(html, "data-review-sort");
    replyControls = controlsFrom(html, "data-replies-toggle");
    originalControls = controlsFrom(html, "data-original-toggle");
    production.bindDiscussionControls(dialog, current, render, () => active);
  };
  render();
  return { current, html: () => html,
    toggle: (key = "0") => {
      const button = replyControls.find((item) => item.dataset.repliesToggle === key);
      assert.ok(button, `missing reply toggle ${key}`); button.click();
    },
    sort: (key: string) => {
      const button = sortControls.find((item) => item.dataset.reviewSort === key);
      assert.ok(button, `missing sort ${key}`); button.click();
    },
    original: (identity: string[]) => {
      const button = originalControls.find((item) => item.dataset.originalToggle === JSON.stringify(identity));
      assert.ok(button, `missing original toggle ${JSON.stringify(identity)}`); button.click();
    },
    oldOriginal: () => originalControls[0],
    oldToggle: () => replyControls[0], stop: () => { active = false; } };
}
function visible(html: string, id: string): boolean { return html.includes(`content-${id}<`); }

test("fully loaded six replies expose two hidden replies even when provider remaining is zero", () => {
  const html = production.reviewsPanel(detail([comment("parent", { replies: replies(6), reply_count: 6 })]), state());
  assert.equal(visible(html, "reply-4"), true);
  assert.equal(visible(html, "reply-5"), false);
  assert.match(html, /data-replies-toggle="0"[^>]*aria-expanded="false"/);
  assert.match(html, /2 weitere geladene Antworten anzeigen/);
  assert.doesNotMatch(html, /noch nicht geladen/);
});

test("actual expand and collapse clicks show all loaded replies then restore the initial four", () => {
  const ui = mount([comment("parent", { replies: replies(6), reply_count: 6 })]);
  ui.toggle();
  assert.equal(visible(ui.html(), "reply-6"), true);
  assert.match(ui.html(), /data-replies-toggle="0"[^>]*aria-expanded="true"/);
  assert.match(ui.html(), /Antworten einklappen/);
  ui.toggle();
  assert.equal(visible(ui.html(), "reply-5"), false);
  assert.equal(visible(ui.html(), "reply-4"), true);
});

test("provider unloaded count stays separate from the expandable loaded count", () => {
  const ui = mount([comment("parent", { replies: replies(6), reply_count: 10 })]);
  assert.match(ui.html(), /2 weitere geladene Antworten anzeigen/);
  assert.match(ui.html(), /4 weitere Antworten wurden vom Anbieter noch nicht geladen/);
  assert.doesNotMatch(ui.html(), /data-noop="more-replies"/);
  ui.toggle();
  assert.equal(visible(ui.html(), "reply-6"), true);
  assert.match(ui.html(), /4 weitere Antworten wurden vom Anbieter noch nicht geladen/);
});

test("four loaded replies need no expansion and missing replies never become a fake load button", () => {
  const complete = production.reviewsPanel(detail([comment("parent", { replies: replies(4), reply_count: 4 })]), state());
  assert.doesNotMatch(complete, /data-replies-toggle/);
  const missing = production.reviewsPanel(detail([comment("parent", { reply_count: 3 })]), state());
  assert.match(missing, /3 weitere Antworten wurden vom Anbieter noch nicht geladen/);
  assert.doesNotMatch(missing, /data-replies-toggle|data-noop="more-replies"/);
});

test("stale or non-finite provider counts never hide loaded replies or fabricate a negative remainder", () => {
  for (const reply_count of [-2, 1, NaN, Infinity]) {
    const ui = mount([comment("parent", { replies: replies(6), reply_count })]);
    assert.match(ui.html(), /2 weitere geladene Antworten anzeigen/);
    assert.doesNotMatch(ui.html(), /(?:NaN|Infinity|-\d+) weitere/);
    ui.toggle(); assert.equal(visible(ui.html(), "reply-6"), true);
  }
});

test("nested replies expand independently and state survives sorting", () => {
  const branch = comment("branch", { replies: replies(6, "nested"), reply_count: 6 });
  const ui = mount([comment("parent", { replies: [branch, ...replies(5)], reply_count: 6 })]);
  ui.toggle("0.0");
  assert.equal(visible(ui.html(), "nested-6"), true);
  assert.equal(visible(ui.html(), "reply-5"), false);
  ui.sort("top");
  assert.equal(visible(ui.html(), "nested-6"), true);
  ui.toggle("0");
  assert.equal(visible(ui.html(), "reply-5"), true);
  assert.equal(visible(ui.html(), "nested-6"), true);
  ui.toggle("0.0");
  assert.equal(visible(ui.html(), "nested-5"), false);
});

test("review sort clicks are stable, local and preserve the original array and comments", () => {
  const comments = [comment("first", { like_count: 1, reply_count: 9, created_at: "2026-10-01" }),
    comment("second", { like_count: 4, reply_count: 2, created_at: "2026-10-03" }),
    comment("third", { like_count: 4, reply_count: 3, created_at: "not-a-date" })];
  const before = JSON.stringify(comments);
  const ui = mount(comments);
  ui.sort("top");
  assert.ok(ui.html().indexOf("content-second") < ui.html().indexOf("content-third"));
  assert.ok(ui.html().indexOf("content-third") < ui.html().indexOf("content-first"));
  ui.sort("new");
  assert.ok(ui.html().indexOf("content-second") < ui.html().indexOf("content-first"));
  assert.ok(ui.html().indexOf("content-first") < ui.html().indexOf("content-third"));
  ui.sort("answers");
  assert.ok(ui.html().indexOf("content-first") < ui.html().indexOf("content-third"));
  ui.sort("all");
  assert.ok(ui.html().indexOf("content-first") < ui.html().indexOf("content-second"));
  assert.equal(JSON.stringify(comments), before);
  assert.match(ui.html(), /data-review-sort="all"[^>]*aria-pressed="true"/);
});

test("closed or busy dialog guard prevents stale controls from mutating discussion state", () => {
  const ui = mount([comment("parent", { replies: replies(6), reply_count: 6 })]);
  const stale = ui.oldToggle(); ui.stop(); stale.click();
  assert.equal(ui.current.expandedReplies.size, 0);
  assert.equal(visible(ui.html(), "reply-5"), false);
});

test("a translated flag without original text is explicitly disabled rather than a fake action", () => {
  const html = production.reviewsPanel(detail([comment("parent", { original_available: true })]), state());
  assert.match(html, /<button[^>]*disabled[^>]*>Original nicht verfügbar<\/button>/);
  assert.doesNotMatch(html, /data-noop="original"/);
  assert.match(html, /Originaltext wurde vom Anbieter nicht mitgeliefert/);
});

test("expanded provider content remains escaped and cannot create executable markup", () => {
  const dangerous = comment("unsafe", { content: '<img src=x onerror="bad()"> & <script>bad()</script>' });
  const ui = mount([comment("parent", { replies: [...replies(4), dangerous], reply_count: 5 })]);
  ui.toggle();
  assert.match(ui.html(), /&lt;img src=x onerror=&quot;bad\(\)&quot;&gt;/);
  assert.doesNotMatch(ui.html(), /<script>|<img src=x/);
});

test("discussion controls never pretend to fetch provider replies or send social writes", () => {
  const ui = mount([comment("parent", { replies: replies(8), reply_count: 12 })]);
  ui.sort("answers"); ui.toggle(); ui.toggle();
  assert.doesNotMatch(ui.html(), /data-noop="(?:more-replies|all|top|new|answers|original)"/);
  assert.match(ui.html(), /4 weitere Antworten wurden vom Anbieter noch nicht geladen/);
  assert.match(ui.html(), /data-noop="publish"/); // Provider write support remains explicitly outside this block.
});

test("the real dialog render wires reply clicks and retains expansion, focus and scroll across rerenders", () => {
  let activeElement: any = null;
  let markup = "";
  let buttons: any[] = [];
  let panes: Record<string, any> = {};
  const target = { value: "printer-profile" };
  const dialog: any = {
    get innerHTML() { return markup; },
    set innerHTML(html: string) {
      markup = html;
      panes = Object.fromEntries([".mw-shell", ".mw-content", ".mw-left", ".mw-right", ".mw-profiles", ".mw-info",
        ".mw-recommendations", ".mw-target", ".mw-thumbs", ".mw-filters"].map((key) => [key, { scrollTop: 0, scrollLeft: 0 }]));
      buttons = [...html.matchAll(/<button\b([^>]*)>/g)].map((match) => {
        const attrs = new Map([...match[1]!.matchAll(/([\w-]+)="([^"]*)"/g)].map((attr) => [attr[1], attr[2]]));
        const handlers: (() => void)[] = [];
        const dataset = Object.fromEntries([...attrs].filter(([key]) => key?.startsWith("data-")).map(([key, value]) =>
          [key!.slice(5).replace(/-([a-z])/g, (_: string, letter: string) => letter.toUpperCase()), value]));
        const button: any = { dataset, id: attrs.get("id") || "",
          classList: { contains: (name: string) => (attrs.get("class") || "").split(" ").includes(name) },
          hasAttribute: (name: string) => attrs.has(name), getAttribute: (name: string) => attrs.get(name) ?? null,
          addEventListener: (_name: string, handler: () => void) => handlers.push(handler),
          focus: () => { activeElement = button; },
          click: () => { activeElement = button; handlers.forEach((handler) => handler()); } };
        return button;
      });
    },
    getRootNode: () => ({ activeElement }),
    querySelectorAll: (selector: string) => {
      const name = selector.match(/^\[([^\]]+)\]$/)?.[1];
      return name ? buttons.filter((button) => button.hasAttribute(name)) : [];
    },
    querySelector: (selector: string) => {
      if (selector === "#target-printer") return target;
      if (panes[selector]) return panes[selector];
      if (selector === ".mw-close") return buttons.find((button) => button.classList.contains("mw-close"));
      const attr = selector.match(/^\[([^=]+)="([^"]+)"\]$/);
      return attr ? buttons.find((button) => button.getAttribute(attr[1]!) === attr[2]) : null;
    },
  };
  const overlay: any = { isConnected: true, querySelector: () => dialog };
  const dialogState: any = { busy: false, closed: false };
  production.register(overlay, dialogState);
  const model = { ...detail([comment("parent", { replies: replies(6), reply_count: 6 })]),
    title: "Model", creator: "Creator", license: "", description: "", images: [],
    instances: [], instance_count: 0, recommendations: [], stats: { likes: 0, collects: 0, comments: 1, downloads: 0, prints: 0 } };
  production.render({}, overlay, model, {}, [], { groups: { printer: [] }, selection: { printer_profile_id: "printer-profile" } }, () => {}, "", "ALL", "reviews", "");
  panes[".mw-info"].scrollTop = 123;
  dialog.querySelector('[data-replies-toggle="0"]').click();
  assert.equal(visible(markup, "reply-6"), true);
  assert.equal(panes[".mw-info"].scrollTop, 123);
  assert.equal(activeElement.getAttribute("data-replies-toggle"), "0");
  dialog.querySelector('[data-printer="ALL"]').click();
  assert.equal(visible(markup, "reply-6"), true);
  assert.equal(dialogState.discussion.expandedReplies.has("0"), true);
  dialog.querySelector('[data-replies-toggle="0"]').click();
  assert.equal(visible(markup, "reply-5"), false);
  assert.equal(panes[".mw-info"].scrollTop, 123);
});


function shareDetail(id = "123"): any {
  return { id, title: "Public model", model_url: "https://private.invalid/model?token=fixture",
    stats: { likes: 0, collects: 0, downloads: 0, comments: 0, prints: 0 }, comments: [] };
}

test("the model share control is a local action rather than a provider-write placeholder", () => {
  const html = production.statButtons(shareDetail());
  assert.match(html, /data-model-share="true"/);
  assert.doesNotMatch(html, /data-noop="share"/);
});

test("native sharing receives only the canonical public design URL and selected model title", async () => {
  assert.equal(typeof production.shareMakerWorldLink, "function");
  const shared: any[] = [], copied: string[] = [];
  const message = await production.shareMakerWorldLink(shareDetail(), {
    async share(value: any) { shared.push(plainShare(value)); },
    clipboard: { async writeText(value: string) { copied.push(value); } },
  }, () => true);
  assert.deepEqual(shared, [{ title: "Public model", url: "https://makerworld.com/de/models/123" }]);
  assert.deepEqual(copied, []);
  assert.match(message, /übergeben/);
  assert.doesNotMatch(JSON.stringify(shared), /private\.invalid|token/);
});

function plainShare(value: any): any { return JSON.parse(JSON.stringify(value)); }

test("without native sharing the explicit click copies only the public model URL", async () => {
  const copied: string[] = [];
  const message = await production.shareMakerWorldLink(shareDetail(), {
    clipboard: { async writeText(value: string) { copied.push(value); } },
  }, () => true);
  assert.deepEqual(copied, ["https://makerworld.com/de/models/123"]);
  assert.match(message, /Zwischenablage kopiert/);
});

test("cancelled native sharing never silently copies the link or claims successful sharing", async () => {
  let copied = false;
  const message = await production.shareMakerWorldLink(shareDetail(), {
    async share() { throw { name: "AbortError" }; },
    clipboard: { async writeText() { copied = true; } },
  }, () => true);
  assert.equal(copied, false);
  assert.match(message, /abgebrochen/);
  assert.doesNotMatch(message, /kopiert|übergeben/);
});

test("denied native sharing keeps the result explicit and does not attempt another browser action", async () => {
  let copied = false;
  const message = await production.shareMakerWorldLink(shareDetail(), {
    async share() { throw { name: "NotAllowedError", message: "private fixture" }; },
    clipboard: { async writeText() { copied = true; } },
  }, () => true);
  assert.equal(copied, false);
  assert.match(message, /nicht abgeschlossen/);
  assert.match(message, /https:\/\/makerworld\.com\/de\/models\/123/);
  assert.doesNotMatch(message, /private fixture|kopiert/);
});

test("a rejected clipboard write never claims that copying succeeded", async () => {
  const message = await production.shareMakerWorldLink(shareDetail(), {
    clipboard: { async writeText() { throw { name: "NotAllowedError" }; } },
  }, () => true);
  assert.match(message, /nicht verfügbar/);
  assert.match(message, /Modelllink zum Kopieren/);
  assert.doesNotMatch(message, /Zwischenablage kopiert/);
});

test("unsupported browser capabilities expose a manual public link without an API request", async () => {
  const message = await production.shareMakerWorldLink(shareDetail(), undefined, () => true);
  assert.equal(message, "Modelllink zum Kopieren: https://makerworld.com/de/models/123");
});

test("closed dialog and invalid design identities cannot start native sharing or clipboard writes", async () => {
  let actions = 0;
  const browser = { async share() { actions++; }, clipboard: { async writeText() { actions++; } } };
  assert.equal(await production.shareMakerWorldLink(shareDetail(), browser, () => false), "");
  for (const id of ["", "123/../private", "123?token=fixture", "１２３", "1".repeat(21)]) {
    await assert.rejects(production.shareMakerWorldLink(shareDetail(id), browser, () => true));
  }
  assert.equal(actions, 0);
});


test("only an explicitly supplied nonempty original string enables local original-text toggling", () => {
  for (const original_content of [undefined, null, "", "  \n  ", true, { text: "not a string" }]) {
    const html = production.reviewsPanel(detail([comment("flag-only", { original_available: true, original_content })]), state());
    assert.doesNotMatch(html, /data-original-toggle/);
    assert.match(html, /Original nicht verfügbar/);
  }
  const ui = mount([comment("provided", { original_available: false, original_content: "Explicit original" })]);
  ui.original(["provided"]);
  assert.match(ui.html(), /Explicit original/);
  assert.doesNotMatch(ui.html(), /content-provided</);
  ui.original(["provided"]);
  assert.match(ui.html(), /content-provided</);
});

test("original text and its toggle state stay bound to comment identities across sorting and rerender", () => {
  const comments = [comment("first", { original_content: "Original first", like_count: 1 }),
    comment("second", { original_content: "Original second", like_count: 9 })];
  const before = JSON.stringify(comments);
  const ui = mount(comments);
  ui.original(["first"]);
  ui.sort("top");
  assert.match(ui.html(), /Original first/); assert.doesNotMatch(ui.html(), /Original second/);
  assert.match(ui.html(), /content-second</);
  assert.equal(JSON.stringify(comments), before);
  comments.reverse(); ui.sort("all");
  assert.match(ui.html(), /Original first/); assert.doesNotMatch(ui.html(), /Original second/);
  ui.original(["first"]);
  assert.doesNotMatch(ui.html(), /Original first/);
});

test("nested comments with the same leaf ID keep independent original state under different parents", () => {
  const leaf = (text: string) => comment("same-leaf", { original_content: text });
  const ui = mount([comment("parent-a", { replies: [leaf("Original A")] }),
    comment("parent-b", { replies: [leaf("Original B")] })]);
  ui.original(["parent-a", "same-leaf"]);
  assert.match(ui.html(), /Original A/); assert.doesNotMatch(ui.html(), /Original B/);
  ui.sort("answers");
  assert.match(ui.html(), /Original A/); assert.doesNotMatch(ui.html(), /Original B/);
});

test("a nested original survives reply collapse and expansion without a provider request", () => {
  const loaded = replies(6); loaded[4] = comment("reply-5", { original_content: "Nested original" });
  const ui = mount([comment("parent", { replies: loaded, reply_count: 6 })]);
  ui.toggle(); ui.original(["parent", "reply-5"]);
  assert.match(ui.html(), /Nested original/);
  ui.toggle(); assert.doesNotMatch(ui.html(), /Nested original/);
  ui.toggle(); assert.match(ui.html(), /Nested original/);
});

test("original provider text is bounded and escaped when displayed", () => {
  const ui = mount([comment("unsafe-original", {
    original_content: '<img src=x onerror="bad()">\n<script>bad()</script>' + "x".repeat(5000) + "OMITTEDTAIL",
  })]);
  ui.original(["unsafe-original"]);
  assert.match(ui.html(), /&lt;img src=x onerror=&quot;bad\(\)&quot;&gt;<br>&lt;script&gt;/);
  assert.doesNotMatch(ui.html(), /<script>|<img src=x|OMITTEDTAIL/);
});

test("original toggle keys escape unusual provider IDs and still use the correct identity", () => {
  const id = 'comment-"<&';
  const ui = mount([comment(id, { original_content: "Safe original" })]);
  assert.doesNotMatch(ui.html(), /data-original-toggle="\["comment-/);
  ui.original([id]); assert.match(ui.html(), /Safe original/);
});

test("closed or busy discussion controls cannot toggle original text", () => {
  const ui = mount([comment("provided", { original_content: "Never shown" })]);
  const old = ui.oldOriginal(); ui.stop(); old.click();
  assert.equal(ui.current.originalComments.size, 0);
  assert.doesNotMatch(ui.html(), /Never shown/);
});


test("original text bounds preserve Unicode code points", () => {
  const ui = mount([comment("unicode", { original_content: "😀".repeat(5000) + "OMITTEDTAIL" })]);
  ui.original(["unicode"]);
  const displayed = ui.html().match(/<p id="mw-comment-text-0">([^<]*)<\/p>/)?.[1];
  assert.equal(Array.from(displayed || "").length, 5000);
  assert.equal(displayed, "😀".repeat(5000));
});
