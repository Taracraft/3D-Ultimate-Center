import { readFileSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { runInNewContext } from "node:vm";
import { ModuleKind, ScriptTarget, transpileModule } from "typescript";

// Minimal host doubles for lifecycle contracts. They do not model browser layout,
// scrolling, rendering, image decoding or touch behavior and are not UI acceptance.
export class ContractElement extends EventTarget {
  readonly attributes = new Map<string, string>();
  readonly dataset: Record<string, string> = {};
  readonly children: ContractElement[] = [];
  readonly classes = new Set<string>();
  readonly classList = {
    add: (name: string): void => { this.classes.add(name); },
    remove: (name: string): void => { this.classes.delete(name); },
    toggle: (name: string, enabled?: boolean): boolean => {
      const value = enabled ?? !this.classes.has(name);
      if (value) this.classes.add(name); else this.classes.delete(name);
      return value;
    },
  };
  parentElement: ContractElement | null = null;
  shadowRoot: ContractElement | null = null;
  isConnected = false;
  hidden = false;
  disabled = false;
  textContent = "";
  src = "";
  id = "";
  tagName = "";
  scrollLeft = 0;
  scrollTop = 0;
  #html = "";

  get childElementCount(): number { return this.children.length; }
  get innerHTML(): string { return this.#html; }
  set innerHTML(value: string) {
    this.#html = value;
    this.replaceChildren();
    for (const match of value.matchAll(/\bid="([^"]+)"/g)) {
      const element = new ContractElement();
      element.id = match[1];
      this.append(element);
    }
  }
  attachShadow(): ContractElement {
    this.shadowRoot = new ContractElement();
    this.shadowRoot.isConnected = true;
    return this.shadowRoot;
  }
  append(...nodes: ContractElement[]): void {
    for (const node of nodes) {
      node.remove();
      node.parentElement = this;
      node.isConnected = this.isConnected;
      this.children.push(node);
    }
  }
  remove(): void {
    if (this.parentElement) {
      const index = this.parentElement.children.indexOf(this);
      if (index >= 0) this.parentElement.children.splice(index, 1);
    }
    this.parentElement = null;
    this.isConnected = false;
  }
  replaceChildren(...nodes: ContractElement[]): void {
    for (const node of [...this.children]) node.remove();
    this.append(...nodes);
  }
  getAttribute(name: string): string | null { return this.attributes.get(name) ?? null; }
  hasAttribute(name: string): boolean { return this.attributes.has(name); }
  setAttribute(name: string, value: string): void { this.attributes.set(name, value); }
  removeAttribute(name: string): void {
    this.attributes.delete(name);
    if (name === "src") this.src = "";
  }
  querySelector(selector: string): ContractElement | null { return this.querySelectorAll(selector)[0] ?? null; }
  querySelectorAll(selector: string): ContractElement[] {
    const all = this.children.flatMap((node) => [node, ...node.querySelectorAll("*")]);
    return all.filter((node) => selector === "*"
      || (selector.startsWith("#") && node.id === selector.slice(1))
      || (selector === "[data-route]" && Boolean(node.dataset.route)));
  }
}

export function loadElementContract(fileName: string, overrides: Record<string, unknown> = {}, modules: Record<string, unknown> = {}) {
  const events = new EventTarget();
  const document = Object.assign(new EventTarget(), {
    hidden: false,
    createElement: (tag: string): ContractElement => {
      const element = new ContractElement(); element.tagName = tag; return element;
    },
  });
  const values = new Map<string, string>();
  const storage = {
    getItem: (key: string): string | null => values.get(key) ?? null,
    setItem: (key: string, value: string): void => { values.set(key, value); },
  };
  let currentHash = "";
  let queuedHashes = 0;
  const location = {
    get hash(): string { return currentHash; },
    set hash(value: string) { if (value !== currentHash) { currentHash = value; queuedHashes += 1; } },
  };
  const registry = new Map<string, unknown>();
  const globals: Record<string, unknown> = {
    HTMLElement: ContractElement,
    Event, EventTarget, AbortController, DOMException, Blob, URL,
    CustomEvent: class extends Event {
      readonly detail: unknown;
      constructor(type: string, options: { detail?: unknown } = {}) { super(type); this.detail = options.detail; }
    },
    document, location, localStorage: storage,
    customElements: { get: (key: string): unknown => registry.get(key), define: (key: string, value: unknown): void => { registry.set(key, value); } },
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
    queueMicrotask,
    setTimeout, clearTimeout, setInterval, clearInterval,
    ...overrides,
  };
  const loaded = new Map<string, Record<string, unknown>>();
  const frontendRoot = join(process.cwd(), "frontend");
  const load = (filename: string): Record<string, unknown> => {
    const cached = loaded.get(filename);
    if (cached) return cached;
    const exports: Record<string, unknown> = {};
    loaded.set(filename, exports);
    const source = readFileSync(filename, "utf8");
    const compiled = transpileModule(source, {
      compilerOptions: { target: ScriptTarget.ES2022, module: ModuleKind.CommonJS },
      fileName: filename,
    }).outputText;
    runInNewContext(compiled, {
      ...globals, exports,
      require: (specifier: string): unknown => {
        if (Object.hasOwn(modules, specifier)) return modules[specifier];
        if (!specifier.startsWith("./")) throw new Error(`Unexpected dependency: ${specifier}`);
        const target = resolve(dirname(filename), specifier.replace(/\.js$/, ".ts"));
        const localPath = relative(frontendRoot, target);
        if (isAbsolute(localPath) || localPath === ".." || localPath.startsWith(".." + sep)) throw new Error(`Unexpected path: ${target}`);
        return load(target);
      },
    }, { filename });
    return exports;
  };
  const exported = load(join(frontendRoot, fileName));
  return {
    exported, events, document, location, storage, globals,
    flushHashes: (): void => {
      while (queuedHashes > 0) { queuedHashes -= 1; events.dispatchEvent(new Event("hashchange")); }
    },
  };
}
