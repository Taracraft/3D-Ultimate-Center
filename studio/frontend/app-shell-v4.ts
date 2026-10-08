import "./control-workspace.js";
import "./gallery-workspace.js";
import "./studio-unified-workspace.js";
import "./ams-workspace.js";
import "./profile-workspace.js";
import "./job-workspaces.js";
import "./system-workspace.js";
import { APP_NAV, mountAppShell } from "./app-shell-view.js";
import { parseRoute, routeToHash, type WorkspaceRoute } from "./router.js";
import { writeFrontendAudit } from "./ha-api-transport.js";
import { consumeWorkspaceFiles } from "./workspace-file-handoff.js";
import { clearStudioWorkspace } from "./studio-persistence.js";
import { readStudioPreference } from "./studio-storage-upgrade.js";
import { jobActivityStore, type JobActivitySnapshot } from "./job-activity-store.js";
import { printLayerLabel, printSpeedLabel } from "./print-live-telemetry.js";
import { remainingTimeLabel } from "./print-remaining-time.js";
import type { WorkspaceSourceRequest } from "./workspace-source-request.js";

type HassLike = Readonly<{
  callApi: (method: string, path: string, parameters?: unknown) => Promise<unknown>;
  states?: Readonly<Record<string, unknown>>;
}>;
type StudioShell = HTMLElement & {
  files: readonly File[];
  file: File | null;
  hass?: HassLike | null;
  openProject?: (file: File, options?: Readonly<{ replaceWorkspace?: boolean }>) => void;
  openGalleryProject?: (assetId: string, fileName: string, options?: Readonly<{ replaceWorkspace?: boolean }>) => void;
};
type GalleryShell = HTMLElement & {
  selectedTab?: "library" | "storage" | "makerworld";
  preferredTarget?: "studio" | "slicer";
};
type GalleryOpenDetail = Readonly<{
  file?: File;
  assetId?: string;
  fileName?: string;
  replaceWorkspace?: boolean;
}>;

const STORAGE_KEY = "ultimate-3d-studio:last-route";

function normalizedRoute(route: WorkspaceRoute): WorkspaceRoute {
  return route.name === "slicer" ? { name: "studio" } : route;
}

function initialRoute(): WorkspaceRoute {
  if (location.hash) return normalizedRoute(parseRoute(location.hash));
  try {
    return normalizedRoute(parseRoute(readStudioPreference(STORAGE_KEY) || "#/steuerung"));
  } catch {
    return { name: "steuerung" };
  }
}

export class Ultimate3DStudioShellV4 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #route = initialRoute();
  #transient: HTMLElement | null = null;
  #studio: StudioShell | null = null;
  #source: WorkspaceSourceRequest | null = null;
  #hass: HassLike | null = null;
  #projectOpenGeneration = 0;
  #activity: JobActivitySnapshot = jobActivityStore.snapshot;
  #activityUnsubscribe: (() => void) | null = null;
  #disconnectedHash: string | null = null;

  set hass(value: HassLike | null) {
    this.#hass = value;
    if (this.#studio) this.#studio.hass = value;
    this.#forwardHass();
  }

  get hass(): HassLike | null { return this.#hass; }

  connectedCallback(): void {
    this.addEventListener("gallery-open-studio", this.#openStudio as EventListener);
    this.addEventListener("gallery-open-slicer", this.#openStudio as EventListener);
    this.addEventListener("workspace-source-request", this.#sourceRequest as EventListener);
    addEventListener("hashchange", this.#hashChanged);
    if (!this.#activityUnsubscribe) {
      this.#activityUnsubscribe = jobActivityStore.subscribe((snapshot) => {
        this.#activity = snapshot;
        this.#updateNavLive();
      });
    }
    if (this.#root.childElementCount) {
      if (location.hash || (this.#disconnectedHash !== null && location.hash !== this.#disconnectedHash)) this.#hashChanged();
      this.#updateNavLive();
      return;
    }
    mountAppShell(this.#root);
    this.#mountNavigation();
    this.#render();
  }

  disconnectedCallback(): void {
    this.#disconnectedHash = location.hash;
    this.#activityUnsubscribe?.();
    this.#activityUnsubscribe = null;
    removeEventListener("hashchange", this.#hashChanged);
    this.removeEventListener("gallery-open-studio", this.#openStudio as EventListener);
    this.removeEventListener("gallery-open-slicer", this.#openStudio as EventListener);
    this.removeEventListener("workspace-source-request", this.#sourceRequest as EventListener);
  }

  navigate(route: WorkspaceRoute): void {
    const previous = this.#route.name;
    this.#route = normalizedRoute(route);
    const hash = routeToHash(this.#route);
    writeFrontendAudit({ category: "Lifecycle", component: "app-shell", event: "navigation", status: "info", details: { from: previous, to: this.#route.name, hash } });
    try { localStorage.setItem(STORAGE_KEY, hash); } catch {}
    if (location.hash !== hash) location.hash = hash;
    this.#render();
  }

  readonly #hashChanged = (): void => {
    const requested = parseRoute(location.hash);
    const parsed = normalizedRoute(requested);
    if (requested.name === "slicer" && location.hash !== "#/studio") location.hash = "#/studio";
    // navigate() already mounted its target before the asynchronous hash event.
    if (routeToHash(parsed) === routeToHash(this.#route)) return;
    this.#route = parsed;
    this.#render();
  };

  readonly #sourceRequest = (event: CustomEvent<WorkspaceSourceRequest>): void => {
    this.#source = event.detail;
    this.navigate({ name: "galerie" });
  };

  readonly #openStudio = (event: CustomEvent<GalleryOpenDetail>): void => {
    void this.#openStudioProject(event.detail ?? {});
  };

  async #openStudioProject(detail: GalleryOpenDetail): Promise<void> {
    const generation = ++this.#projectOpenGeneration;
    const replaceWorkspace = detail.replaceWorkspace !== false;
    this.#source = null;

    if (replaceWorkspace) {
      await clearStudioWorkspace();
      if (generation !== this.#projectOpenGeneration) return;
      this.#studio?.remove();
      this.#studio = null;
      writeFrontendAudit({
        category: "Lifecycle",
        component: "app-shell",
        event: "studio_project_session_reset",
        status: "success",
        details: {
          source: detail.assetId ? "gallery_server_asset" : "browser_file",
          filename: detail.fileName || detail.file?.name || null,
        },
      });
    }

    this.navigate({ name: "studio" });
    await new Promise<void>((resolve) => queueMicrotask(resolve));
    if (generation !== this.#projectOpenGeneration) return;

    const studio = this.#studioNode();
    if (detail.assetId && detail.fileName && studio.openGalleryProject) {
      studio.openGalleryProject(detail.assetId, detail.fileName, { replaceWorkspace });
      return;
    }
    const queuedFile = consumeWorkspaceFiles("slicer")[0] ?? consumeWorkspaceFiles("studio")[0];
    const file = detail.file ?? queuedFile;
    if (!file) return;
    if (replaceWorkspace && studio.openProject) studio.openProject(file, { replaceWorkspace: true });
    else studio.file = file;
  }

  #mountNavigation(): void {
    const nav = this.#root.querySelector<HTMLElement>("#nav-buttons");
    if (!nav) return;
    for (const [name, label, icon] of APP_NAV) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.route = name;
      button.innerHTML = `<span>${icon}</span><span>${label}</span>`;
      button.addEventListener("click", () => {
        this.#source = null;
        this.navigate({ name } as WorkspaceRoute);
      });
      nav.append(button);
    }
  }

  #updateNavLive(): void {
    const host = this.#root.querySelector<HTMLElement>("#nav-live");
    const title = this.#root.querySelector<HTMLElement>("#nav-live-title");
    const meta = this.#root.querySelector<HTMLElement>("#nav-live-meta");
    const detail = this.#root.querySelector<HTMLElement>("#nav-live-detail");
    if (!host || !title || !meta || !detail) return;
    const printer = this.#activity.printers[0] ?? null;
    const jobs = this.#activity.jobs.current || [];
    const printerId = String(printer?.printer_id || "");
    const job = jobs.find((item) => String(item.printer_id || "") === printerId) ?? jobs[0] ?? null;
    host.hidden = !printer || !job;
    if (host.hidden || !printer || !job) return;
    const progress = Math.max(0, Math.min(100, Number(job.progress ?? printer.progress) || 0));
    title.textContent = `${String(printer.print_stage_label || "Aktiver Druck")} · ${Math.round(progress)} %`;
    meta.textContent = `${printLayerLabel(job, printer)} · Tempo ${printSpeedLabel(printer)}`;
    detail.textContent = `Restzeit ${remainingTimeLabel(job, printer)}`;
  }

  #renderTools(): void {
    const tools = this.#root.querySelector<HTMLElement>("#tools");
    if (!tools) return;
    tools.replaceChildren();
    tools.classList.remove("visible");
  }

  #studioNode(): StudioShell {
    if (this.#studio) return this.#studio;
    this.#studio = document.createElement("ultimate-3d-unified-studio") as StudioShell;
    this.#studio.hass = this.#hass;
    return this.#studio;
  }

  #galleryNode(): HTMLElement {
    const node = document.createElement("ultimate-3d-gallery-workspace") as GalleryShell;
    node.selectedTab = this.#source?.source === "storage"
      ? "storage"
      : this.#source?.source === "makerworld"
        ? "makerworld"
        : "library";
    node.preferredTarget = "slicer";
    return node;
  }

  #transientNode(): HTMLElement {
    if (this.#route.name === "galerie") return this.#galleryNode();
    const tags: Partial<Record<WorkspaceRoute["name"], string>> = {
      steuerung: "ultimate-3d-steuerung-workspace",
      ams: "ultimate-3d-ams-workspace",
      profile: "ultimate-3d-profile-workspace",
      aufgaben: "ultimate-3d-aufgaben-workspace",
      verlauf: "ultimate-3d-verlauf-workspace",
      system: "ultimate-3d-system-workspace",
      "slicing-server": "ultimate-3d-slicing-server-workspace",
    };
    return document.createElement(tags[this.#route.name] || "ultimate-3d-steuerung-workspace");
  }

  #render(): void {
    const host = this.#root.querySelector<HTMLElement>("#host");
    if (!host) return;
    this.#root.querySelectorAll<HTMLButtonElement>("[data-route]").forEach((button) => {
      const active = button.dataset.route === this.#route.name;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    this.#renderTools();
    this.#updateNavLive();
    if (this.#studio) this.#studio.hidden = true;
    this.#transient?.remove();
    this.#transient = null;
    if (this.#route.name === "studio") {
      const studio = this.#studioNode();
      if (!studio.isConnected) host.append(studio);
      studio.hidden = false;
    } else {
      this.#transient = this.#transientNode();
      host.append(this.#transient);
    }
    this.#forwardHass();
  }

  #forwardHass(): void {
    if (!this.#hass) return;
    this.#root.querySelectorAll<HTMLElement>("*").forEach((node) => {
      if ("hass" in node) (node as HTMLElement & { hass: HassLike }).hass = this.#hass!;
    });
  }
}

if (!customElements.get("ultimate-3d-studio")) {
  customElements.define("ultimate-3d-studio", Ultimate3DStudioShellV4);
}
