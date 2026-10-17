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
  return production.createDiscussionState?.() ?? { sort: "all", expandedReplies: new Set<string>() };
}
function controlsFrom(html: string, attribute: string): any[] {
  return [...html.matchAll(new RegExp(`<button[^>]*${attribute}="([^"]+)"[^>]*>`, "g"))].map((match) => {
    const key = attribute === "data-review-sort" ? "reviewSort" : "repliesToggle";
    const handlers: (() => void)[] = [];
    return { dataset: { [key]: match[1] }, addEventListener: (_name: string, handler: () => void) => handlers.push(handler),
      click: () => handlers.forEach((handler) => handler()) };
  });
}
function mount(comments: any[]): any {
  assert.equal(typeof production.bindDiscussionControls, "function", "dialog must bind real discussion controls");
  const current = state();
  let html = "", sortControls: any[] = [], replyControls: any[] = [], active = true;
  const dialog = { querySelectorAll: (selector: string) => selector === "[data-review-sort]" ? sortControls : replyControls };
  const render = () => {
    html = production.reviewsPanel(detail(comments), current);
    sortControls = controlsFrom(html, "data-review-sort");
    replyControls = controlsFrom(html, "data-replies-toggle");
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
  assert.match(html, /<button[^>]*disabled[^>]*>Original nicht geladen<\/button>/);
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
