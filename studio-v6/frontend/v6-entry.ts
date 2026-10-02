import { V6_BRANDING } from "./branding.js";
import "./app-shell.js";
import "./global-job-popup.js";
import "./studio-paint-ui.js";
import {
  configureHomeAssistantApi,
  writeFrontendAudit,
  type HomeAssistantApiHost,
} from "./ha-api-transport.js";

type HassLike = HomeAssistantApiHost & Readonly<Record<string, unknown>>;

type JobNavigateDetail = Readonly<{
  name: "slicer" | "aufgaben";
  id?: string | null;
}>;

type StudioShell = HTMLElement & { hass?: HassLike };

type PersistentRegistry = {
  studio: StudioShell | null;
  owner: Ultimate3DStudioV6Card | null;
  cards: Set<Ultimate3DStudioV6Card>;
  moduleLoads: number;
};

type LifecycleEntry = Readonly<{
  at: string;
  event: string;
  detail?: string;
}>;

const REGISTRY_KEY = "__ultimate3dStudioV6PersistentRegistry";
const LIFECYCLE_KEY = "ultimate-3d-studio-v6:lifecycle";
const ERROR_HOOK_KEY = "__ultimate3dStudioV6ErrorHooks";

function lifecycle(event: string, detail = ""): void {
  try {
    const current = JSON.parse(sessionStorage.getItem(LIFECYCLE_KEY) || "[]") as LifecycleEntry[];
    current.push({ at: new Date().toISOString(), event, ...(detail ? { detail } : {}) });
    sessionStorage.setItem(LIFECYCLE_KEY, JSON.stringify(current.slice(-120)));
  } catch {}
  writeFrontendAudit({
    category: "Lifecycle",
    component: "v6-entry",
    event,
    status: event.includes("denied") ? "warning" : "info",
    details: detail ? { detail } : {},
  });
}

function installGlobalErrorHooks(): void {
  const globalRecord = globalThis as typeof globalThis & Record<string, unknown>;
  if (globalRecord[ERROR_HOOK_KEY]) return;
  globalRecord[ERROR_HOOK_KEY] = true;
  globalThis.addEventListener("error", (event) => {
    const errorEvent = event as ErrorEvent;
    writeFrontendAudit({
      category: "System",
      component: "browser",
      event: "window_error",
      status: "error",
      details: {
        message: errorEvent.message,
        filename: errorEvent.filename,
        line: errorEvent.lineno,
        column: errorEvent.colno,
        stack: errorEvent.error instanceof Error ? errorEvent.error.stack : undefined,
      },
    });
  });
  globalThis.addEventListener("unhandledrejection", (event) => {
    const rejection = event as PromiseRejectionEvent;
    writeFrontendAudit({
      category: "System",
      component: "browser",
      event: "unhandled_promise_rejection",
      status: "error",
      details: {
        reason: rejection.reason instanceof Error
          ? { message: rejection.reason.message, stack: rejection.reason.stack }
          : String(rejection.reason),
      },
    });
  });
}

function registry(): PersistentRegistry {
  const globalRecord = globalThis as typeof globalThis & Record<string, unknown>;
  const existing = globalRecord[REGISTRY_KEY] as PersistentRegistry | undefined;
  if (existing?.cards instanceof Set) return existing;
  const created: PersistentRegistry = {
    studio: null,
    owner: null,
    cards: new Set<Ultimate3DStudioV6Card>(),
    moduleLoads: 0,
  };
  globalRecord[REGISTRY_KEY] = created;
  return created;
}

installGlobalErrorHooks();
const persistent = registry();
persistent.moduleLoads += 1;
lifecycle("module-load", `count=${persistent.moduleLoads}`);

function studioShell(): StudioShell {
  if (!persistent.studio) {
    persistent.studio = document.createElement("ultimate-3d-studio") as StudioShell;
    lifecycle("studio-created");
  }
  return persistent.studio;
}

function claimNextConnectedCard(): void {
  if (persistent.owner?.isConnected) return;
  persistent.owner = null;
  for (const card of persistent.cards) {
    if (!card.isConnected) continue;
    card.adoptPersistentStudio();
    if (persistent.owner === card) return;
  }
}

export class Ultimate3DStudioV6Card extends HTMLElement {
  private readonly rootElement = this.attachShadow({ mode: "open" });
  private hassValue: HassLike | null = null;
  private configValue: Readonly<Record<string, unknown>> = {};
  private mounted = false;

  setConfig(config: Readonly<Record<string, unknown>>): void {
    this.configValue = config || {};
    if (!this.isConnected) return;
    this.ensureMounted();
    this.updateTitle();
  }

  set hass(value: HassLike) {
    this.hassValue = value;
    configureHomeAssistantApi(value);
    this.ensureMounted();
    this.forwardHass();
  }

  connectedCallback(): void {
    lifecycle("card-connected");
    persistent.cards.add(this);
    this.removeEventListener("v6-job-navigate", this.onJobNavigate as EventListener);
    this.addEventListener("v6-job-navigate", this.onJobNavigate as EventListener);
    this.ensureMounted();
    this.updateTitle();
    this.forwardHass();
  }

  disconnectedCallback(): void {
    lifecycle("card-disconnected", persistent.owner === this ? "owner" : "non-owner");
    this.removeEventListener("v6-job-navigate", this.onJobNavigate as EventListener);
    persistent.cards.delete(this);
    if (persistent.owner === this) {
      persistent.owner = null;
      queueMicrotask(claimNextConnectedCard);
    }
  }

  getCardSize(): number { return 12; }

  getGridOptions(): Readonly<Record<string, number>> {
    return { columns: 12, rows: 12, min_columns: 8, min_rows: 8 };
  }

  adoptPersistentStudio(): void {
    if (!this.isConnected) return;
    const currentOwner = persistent.owner;
    if (currentOwner && currentOwner !== this && currentOwner.isConnected) {
      lifecycle("studio-claim-denied", "connected owner exists");
      return;
    }
    const host = this.rootElement.querySelector<HTMLElement>("#studio-host");
    if (!host) return;
    const studio = studioShell();
    persistent.owner = this;
    if (studio.parentElement !== host) host.append(studio);
    if (this.hassValue) studio.hass = this.hassValue;
    lifecycle("studio-claimed");
  }

  private readonly onJobNavigate = (event: CustomEvent<JobNavigateDetail>): void => {
    const detail = event.detail;
    if (!detail) return;
    const suffix = detail.id && (detail.name === "slicer" || detail.name === "aufgaben")
      ? `/${encodeURIComponent(detail.id)}`
      : "";
    const hash = `#/${detail.name}${suffix}`;
    writeFrontendAudit({
      category: "Lifecycle",
      component: "global_job_popup",
      event: "job_navigation",
      status: "info",
      job_id: detail.id || undefined,
      details: { target: detail.name, hash },
    });
    if (globalThis.location.hash !== hash) globalThis.location.hash = hash;
  };

  private ensureMounted(): void {
    if (!this.mounted && this.rootElement.childElementCount === 0) {
      this.rootElement.innerHTML = `
        <style>
          :host{display:block;min-height:calc(100vh - 88px);color:#f4f7fb;background:#08101a}
          *{box-sizing:border-box}
          ha-card{position:relative;display:block;min-height:calc(100vh - 88px);border:0;border-radius:0;overflow:hidden;background:#08101a}
          header{display:flex;align-items:center;min-height:68px;padding:12px 16px;border-bottom:1px solid #26384f;background:#0a111b;color:#f4f7fb}
          .marke{display:flex;align-items:center;gap:12px;min-width:0}
          .logo{display:grid;place-items:center;flex:0 0 42px;width:42px;height:42px;border:1px solid #4bc2ff88;border-radius:12px;background:#13263a;color:#34b9ff;font-weight:800}
          .marke div:last-child{min-width:0}.marke strong,.marke small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.marke small{margin-top:3px;color:#91a4bc}
          #studio-host,ultimate-3d-studio{display:block;width:100%;min-height:calc(100vh - 156px)}
          @media(max-width:800px){header{min-height:56px;padding:8px 10px}.logo{width:36px;height:36px;flex-basis:36px;border-radius:10px}.marke{gap:9px}.marke strong{font-size:14px}.marke small{font-size:10px}#studio-host,ultimate-3d-studio{min-height:calc(100dvh - 112px)}}
        </style>
        <ha-card>
          <header><div class="marke"><div class="logo">3D</div><div><strong id="card-title">${V6_BRANDING.productName}</strong><small>Druckersteuerung, Modelle, Slicing und Aufgaben</small></div></div></header>
          <div id="studio-host"></div>
        </ha-card>
        <ultimate-3d-global-job-popup></ultimate-3d-global-job-popup>`;
      this.mounted = true;
      lifecycle("card-mounted");
    }
    this.adoptPersistentStudio();
  }

  private updateTitle(): void {
    const title = this.rootElement.querySelector<HTMLElement>("#card-title");
    if (title) title.textContent = String(this.configValue.title || V6_BRANDING.productName);
  }

  private forwardHass(): void {
    if (!this.hassValue || !this.mounted) return;
    if (persistent.owner === this) studioShell().hass = this.hassValue;
    const popup = this.rootElement.querySelector<HTMLElement & { hass?: HassLike }>("ultimate-3d-global-job-popup");
    if (popup) popup.hass = this.hassValue;
  }
}

if (!customElements.get("ultimate-3d-studio-v6-card")) {
  customElements.define("ultimate-3d-studio-v6-card", Ultimate3DStudioV6Card);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((entry) => entry.type === "ultimate-3d-studio-v6-card")) {
  window.customCards.push({
    type: "ultimate-3d-studio-v6-card",
    name: V6_BRANDING.productName,
    description: V6_BRANDING.cardDescription,
    preview: false,
  });
}

declare global {
  interface Window {
    customCards?: Array<Record<string, unknown>>;
  }
}
