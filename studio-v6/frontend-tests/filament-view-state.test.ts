import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import ts from "typescript";
import { preserveFilamentView } from "../frontend/filament-view-state.js";

class Group {
  constructor(readonly dataset: { filamentDetailKey: string }, public open: boolean) {}
}

class Tree {
  #scrollTop = 0;
  readonly writes: string[] = [];
  constructor(readonly key: "picker" | "sidebar", readonly groups: Group[]) {}
  closest(): object | null { return this.key === "picker" ? {} : null; }
  querySelectorAll(): Group[] { return this.groups; }
  get scrollTop(): number { return this.#scrollTop; }
  set scrollTop(value: number) {
    this.writes.push(this.groups.map((group) => String(group.open)).join(","));
    this.#scrollTop = this.groups.some((group) => group.open) ? value : 0;
  }
}

class Root {
  picker = { open: true };
  trees: Tree[];
  readonly sidebar: object;
  constructor() {
    this.trees = this.makeTrees(true);
    this.trees[0]!.scrollTop = 820;
    this.trees[1]!.scrollTop = 310;
    this.sidebar = {
      querySelector: () => null,
      querySelectorAll: (selector: string) => selector === ".filament-tree" ? this.trees.filter((tree) => tree.key === "sidebar") : [],
    };
    Object.defineProperty(this.sidebar, "innerHTML", { set: () => this.replaceSidebar() });
  }
  makeTrees(open: boolean): Tree[] {
    return ["picker", "sidebar"].map((key) => new Tree(key as "picker" | "sidebar", [
      new Group({ filamentDetailKey: "filament:source:local_standard" }, open),
      new Group({ filamentDetailKey: "filament:vendor:Brand [special]:material:PLA" }, open && key === "picker"),
    ]));
  }
  querySelector(selector: string): unknown {
    if (selector === "[data-filament-profile-picker]") return this.picker;
    if (selector === "#sidebar") return this.sidebar;
    if (selector === ".profilebar-shell") return { replaceWith: () => this.replacePicker() };
    return null;
  }
  querySelectorAll(): Tree[] { return this.trees; }
  replacePicker(): void { this.picker = { open: false }; this.trees[0] = this.makeTrees(false)[0]!; }
  replaceSidebar(): void { this.trees[1] = this.makeTrees(false)[1]!; }
  set innerHTML(_value: string) { this.replacePicker(); this.replaceSidebar(); }
}

// Execute the production render method body with explicit view/transport doubles.
// This checks state preservation around real call sites, not browser layout or touch behavior.
function methodBody(name: string): string {
  const path = process.env.STUDIO_WORKSPACE_FIXTURE || join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts");
  const source = readFileSync(path, "utf8");
  const file = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true);
  for (const statement of file.statements) {
    if (!ts.isClassDeclaration(statement)) continue;
    for (const member of statement.members) {
      if (ts.isMethodDeclaration(member) && member.name.getText(file) === `#${name}` && member.body) {
        return member.body.getText(file).replaceAll("this.#", "this.");
      }
    }
  }
  throw new Error(`Missing production method: ${name}`);
}

function runMethod(name: string, context: Record<string, unknown>): void {
  const javascript = ts.transpileModule(`function run() ${methodBody(name)}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const run = new Function("preserveFilamentView", "document", "studioProfileBarHtml", "shellHtmlV2", "queueMicrotask",
    "setBatchQueueContext", "filamentSyncActionsHtml", "filamentProfilesHtml",
    `${javascript}\nreturn run;`)(preserveFilamentView,
    { createElement: () => ({ innerHTML: "", content: { firstElementChild: {} } }) },
    () => "profilebar", () => "shell", () => {}, () => {}, () => "", () => "") as (this: Record<string, unknown>) => void;
  run.call(context);
}

function context(root: Root): Record<string, unknown> {
  return {
    root, supportWarning: null, deferredFullRender: false, viewport: null, mode: "colors",
    plate: () => ({ selection: {}, materialSource: "external_spool", externalFilamentProfileId: "" }),
    ui: () => ({}), bindUi: () => { root.picker.open = true; },
    bindProfileSelectors: () => { root.picker.open = true; },
    selectedItems: () => [], externalFilamentChoice: () => null, materialPlan: () => ({}),
    bindFilamentSyncActions: () => {}, bindFilamentDetails: () => {},
    renderSidebar: () => root.replaceSidebar(), renderSidebarContent: () => root.replaceSidebar(),
    renderStatus: () => {}, schedulePersist: () => {},
  };
}

function expectStable(root: Root): void {
  assert.equal(root.picker.open, true);
  assert.deepEqual(root.trees.map((tree) => tree.scrollTop), [820, 310]);
  assert.deepEqual(root.trees.map((tree) => tree.groups.map((group) => group.open)), [[true, true], [true, false]]);
}

test("environment refresh retains both filament trees, exact open groups and scroll positions", () => {
  const root = new Root();
  runMethod("refreshEnvironmentUi", context(root));
  expectStable(root);
});

test("full Studio render retains profile-picker state independently from the sidebar", () => {
  const root = new Root();
  runMethod("renderFull", context(root));
  expectStable(root);
});

test("sidebar-only updates retain the last scrolled filament group", () => {
  const root = new Root();
  runMethod("renderSidebar", context(root));
  expectStable(root);
});

test("a user-collapsed selected group stays closed while new catalog groups keep their defaults", () => {
  const root = new Root();
  root.trees[0]!.groups[1]!.open = false;
  preserveFilamentView(root as unknown as ShadowRoot, () => {
    root.replacePicker();
    root.trees[0]!.groups[1]!.open = true;
    root.trees[0]!.groups.push(new Group({ filamentDetailKey: "new-cloud-vendor" }, true));
  });
  assert.deepEqual(root.trees[0]!.groups.map((group) => group.open), [true, false, true]);
  assert.equal(root.trees[0]!.scrollTop, 820);
});

test("filament groups reopen before scroll restoration and a first render retains defaults", () => {
  const root = new Root();
  preserveFilamentView(root as unknown as ShadowRoot, () => root.replacePicker());
  assert.deepEqual(root.trees[0]!.writes, ["true,true"]);
  root.trees = [];
  preserveFilamentView(root as unknown as ShadowRoot, () => { root.trees = root.makeTrees(true); });
  assert.deepEqual(root.trees[0]!.groups.map((group) => group.open), [true, true]);
});

test("an explicitly closed picker stays closed after profile refresh", () => {
  const root = new Root();
  root.picker.open = false;
  preserveFilamentView(root as unknown as ShadowRoot, () => {
    root.replacePicker();
    root.picker.open = true;
  });
  assert.equal(root.picker.open, false);
});
