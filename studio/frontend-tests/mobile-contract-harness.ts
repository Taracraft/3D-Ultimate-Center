import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Explicit DOM boundary doubles: no layout, native focus trap, image decoding,
// touch, or browser acceptance is modelled by these controller tests.
export class MobileNode extends EventTarget {
  children: MobileNode[] = [];
  parent: MobileNode | null = null;
  shadowRoot: MobileNode | null = null;
  attributes = new Map<string, string>();
  dataset: Record<string, string> = {};
  style: Record<string, string> = {};
  className = ""; id = ""; value = ""; textContent = "";
  disabled = false; hidden = false; isConnected = true;
  #modalOpen = false;
  get open(): boolean { return this.#modalOpen; }
  set open(value: boolean) { this.#modalOpen = value; }
  scrollTop = 0; focusCount = 0; modalCalls = 0;
  activeElement: MobileNode | null = null;
  #html = "";
  static failModal = false;
  constructor(readonly tagName = "host") { super(); }
  classList = { contains: (name: string): boolean => this.className.split(" ").includes(name) };
  get childElementCount(): number { return this.children.length; }
  attachShadow(): MobileNode { this.shadowRoot = new MobileNode("root"); return this.shadowRoot; }
  get innerHTML(): string { return this.#html; }
  set innerHTML(value: string) {
    this.#html = value; this.replaceChildren();
    for (const match of value.matchAll(/<(dialog|section|button|input|select|article|div|main|span|h2)\b([^>]*)>/g)) {
      const node = new MobileNode(match[1]);
      for (const attribute of match[2].matchAll(/([\w-]+)="([^"]*)"/g)) node.setAttribute(attribute[1], attribute[2]);
      if (node.tagName === "select") {
        const body = value.slice((match.index ?? 0) + match[0].length).split("</select>")[0];
        const options = [...body.matchAll(/<option\b([^>]*)>/g)];
        const selected = options.find((option) => /\bselected\b/.test(option[1])) ?? options[0];
        node.value = selected?.[1].match(/value="([^"]*)"/)?.[1] ?? "";
      }
      this.append(node);
    }
  }
  setAttribute(name: string, value: string): void {
    this.attributes.set(name, value);
    if (name === "class") this.className = value;
    if (name === "id") this.id = value;
    if (name === "value") this.value = value;
    if (name.startsWith("data-")) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase())] = value;
  }
  getAttribute(name: string): string | null { return this.attributes.get(name) ?? null; }
  hasAttribute(name: string): boolean { return this.attributes.has(name); }
  removeAttribute(name: string): void { this.attributes.delete(name); }
  append(...nodes: MobileNode[]): void { nodes.forEach((node) => { node.parent = this; this.children.push(node); }); }
  replaceChildren(...nodes: MobileNode[]): void {
    this.children.forEach((node) => { node.parent = null; node.isConnected = false; }); this.children = []; this.append(...nodes);
  }
  remove(): void {
    if (this.parent) this.parent.children = this.parent.children.filter((node) => node !== this);
    this.parent = null; this.isConnected = false;
  }
  getRootNode(): MobileNode { return this.parent ? this.parent.getRootNode() : this; }
  focus(_options?: unknown): void { this.focusCount += 1; this.getRootNode().activeElement = this; }
  select(): void {}
  click(): void { this.dispatchEvent(new Event("click")); }
  showModal(): void { if (MobileNode.failModal) throw new Error("modal unavailable"); this.modalCalls += 1; this.open = true; }
  close(): void { this.open = false; this.dispatchEvent(new Event("close")); }
  querySelector(selector: string): MobileNode | null { return this.querySelectorAll(selector)[0] ?? null; }
  querySelectorAll(selector: string): MobileNode[] {
    const all = this.children.flatMap((node) => [node, ...node.querySelectorAll("*")]);
    const matches = (node: MobileNode, pattern: string): boolean => {
      if (pattern === "*") return true;
      if (pattern === "button:not(.mw-close)") return node.tagName === "button" && !node.classList.contains("mw-close");
      if (pattern.startsWith("#")) return node.id === pattern.slice(1);
      if (pattern.startsWith(".")) return node.classList.contains(pattern.slice(1));
      const attribute = pattern.match(/^\[([\w-]+)(?:=['"](.*?)['"])?\]$/);
      if (attribute) return attribute[2] === undefined ? node.hasAttribute(attribute[1]) : node.getAttribute(attribute[1]) === attribute[2];
      return node.tagName === pattern;
    };
    return all.filter((node) => selector.split(",").some((pattern) => matches(node, pattern.trim())));
  }
}

export function keyboard(node: MobileNode, target: MobileNode, key: string, extra: Record<string, unknown> = {}): Event {
  const event = new Event("keydown", { cancelable: true });
  Object.defineProperty(event, "target", { value: target });
  Object.assign(event, { key, isComposing: false, repeat: false, ...extra });
  node.dispatchEvent(event); return event;
}

export function loadMobileModule(file: string, options: { modules?: Record<string, unknown>; globals?: Record<string, unknown>; expose?: string } = {}) {
  const listeners = new Map<string, Set<EventListener>>();
  const urls = { made: [] as string[], revoked: [] as string[] };
  const document = { createElement: (tag: string) => new MobileNode(tag) };
  const window = {
    addEventListener: (name: string, listener: EventListener) => { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name)!.add(listener); },
    removeEventListener: (name: string, listener: EventListener) => { listeners.get(name)?.delete(listener); },
    setTimeout,
  };
  const exports: Record<string, any> = {};
  const source = readFileSync(join(process.cwd(), "frontend", file), "utf8") + (options.expose || "");
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  runInNewContext(compiled, {
    HTMLElement: MobileNode, HTMLTextAreaElement: class {}, Event, EventTarget,
    CustomEvent: class extends Event { detail: unknown; constructor(name: string, init: { detail?: unknown } = {}) { super(name); this.detail = init.detail; } },
    queueMicrotask, document, window, setTimeout, clearTimeout, WeakMap, WeakSet,
    customElements: { get: () => undefined, define: () => {} },
    URL: { createObjectURL: () => { const url = `blob:${urls.made.length + 1}`; urls.made.push(url); return url; }, revokeObjectURL: (url: string) => urls.revoked.push(url) },
    exports, require: (name: string) => { if (Object.hasOwn(options.modules || {}, name)) return options.modules![name]; throw new Error(`Unexpected module: ${name}`); },
    ...options.globals,
  });
  return { exports, listeners, urls, document };
}
