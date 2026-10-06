import { waitForCameraImage } from "./camera-frame-loader.js";

type HassState = Readonly<{
  state: string;
  attributes: Readonly<Record<string, unknown>>;
}>;

export type CameraHassHost = Readonly<{
  states: Readonly<Record<string, unknown>>;
}>;

type CameraSelection = Readonly<{
  entityId: string;
  state: HassState;
}>;

const FRAME_INTERVAL_MS = 2_000;
const MIN_REFRESH_GAP_MS = 1_500;
const FRAME_REQUEST_TIMEOUT_MS = 8_000;

function isHassState(value: unknown): value is HassState {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const state = value as Readonly<Record<string, unknown>>;
  return typeof state.state === "string"
    && state.attributes !== null
    && typeof state.attributes === "object"
    && !Array.isArray(state.attributes);
}

function numericAttribute(state: HassState, ...names: string[]): number | null {
  for (const name of names) {
    const value = Number(state.attributes[name]);
    if (Number.isFinite(value)) return value;
  }
  return null;
}

export class PrinterCameraPanel extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #hass: CameraHassHost | null = null;
  #collapsed = false;
  #loading = false;
  #frameController: AbortController | null = null;
  #requestedEntityId = "";
  #lastSequence: number | null = null;
  #currentObjectUrl = "";
  #currentEntityId = "";
  #mounted = false;
  #frameTimer: number | null = null;
  #lastRefreshAt = 0;
  #viewportVisible = true;
  #visibilityObserver: IntersectionObserver | null = null;

  static get observedAttributes(): string[] {
    return ["collapsed", "title", "storage-key"];
  }

  set hass(value: CameraHassHost | null) {
    this.#hass = value;
    if (!this.#mounted) return;
    const camera = this.#cameraEntity();
    if ((this.#currentEntityId || this.#requestedEntityId)
      && camera?.entityId !== (this.#requestedEntityId || this.#currentEntityId)) {
      this.#clearFrame();
    }
    this.#updateMetadata();
    const sequence = camera ? this.#cameraSequence(camera.state) : null;
    if (!this.#currentObjectUrl || (sequence !== null && sequence !== this.#lastSequence)) {
      this.#requestVisibleFrame(false);
    }
  }

  get hass(): CameraHassHost | null { return this.#hass; }

  connectedCallback(): void {
    this.#collapsed = this.#initialCollapsed();
    if (!this.#mounted) this.#mount();
    this.#updateCollapsedState();
    this.#updateMetadata();
    document.addEventListener("visibilitychange", this.#visibilityChanged);
    globalThis.addEventListener?.("pageshow", this.#resumeRefresh);
    globalThis.addEventListener?.("focus", this.#resumeRefresh);
    globalThis.addEventListener?.("online", this.#resumeRefresh);
    this.#observeVisibility();
    this.#startFrameTimer();
    this.#requestVisibleFrame(true);
  }

  disconnectedCallback(): void {
    document.removeEventListener("visibilitychange", this.#visibilityChanged);
    globalThis.removeEventListener?.("pageshow", this.#resumeRefresh);
    globalThis.removeEventListener?.("focus", this.#resumeRefresh);
    globalThis.removeEventListener?.("online", this.#resumeRefresh);
    this.#visibilityObserver?.disconnect();
    this.#visibilityObserver = null;
    this.#stopFrameTimer();
    this.#clearFrame();
    this.#loading = false;
  }

  attributeChangedCallback(): void {
    if (!this.isConnected || !this.#mounted) return;
    this.#collapsed = this.#initialCollapsed();
    this.#updateCollapsedState();
    this.#updateMetadata();
    if (!this.#collapsed) this.#requestVisibleFrame(true);
  }

  toggle(): void {
    this.#collapsed = !this.#collapsed;
    this.#persist();
    this.#updateCollapsedState();
    if (!this.#collapsed) this.#requestVisibleFrame(true);
  }

  async enterFullscreen(): Promise<void> {
    const frame = this.#root.querySelector<HTMLElement>(".frame");
    if (!frame) return;
    try {
      await frame.requestFullscreen();
    } catch {
      const image = this.#root.querySelector<HTMLImageElement>("#camera-image");
      if (image?.src) window.open(image.src, "_blank", "noopener,noreferrer");
    }
  }

  readonly #visibilityChanged = (): void => {
    if (document.hidden) this.#cancelFrameRequest();
    else this.#resumeRefresh();
  };

  readonly #resumeRefresh = (): void => {
    if (!this.#canRefresh()) return;
    // A suspended fetch/image decode must not keep the resume path locked.
    this.#cancelFrameRequest();
    this.#lastRefreshAt = 0;
    this.#requestVisibleFrame(true);
  };

  #observeVisibility(): void {
    this.#visibilityObserver?.disconnect();
    this.#visibilityObserver = null;
    this.#viewportVisible = true;
    if (typeof IntersectionObserver !== "function") return;
    this.#visibilityObserver = new IntersectionObserver((entries) => {
      const visible = entries.some((entry) => entry.isIntersecting && entry.intersectionRatio > 0);
      const resumed = visible && !this.#viewportVisible;
      this.#viewportVisible = visible;
      if (resumed) this.#resumeRefresh();
    }, { threshold: [0, .01] });
    this.#visibilityObserver.observe(this);
  }

  #mount(): void {
    this.#root.innerHTML = `<style>
      :host{display:block;color:#eef5ff}*{box-sizing:border-box}.panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}.head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 13px;border-bottom:1px solid #26384f}.title{display:flex;align-items:center;gap:8px;min-width:0}.title strong{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.live{display:inline-flex;align-items:center;gap:5px;padding:3px 7px;border:1px solid #286b48;border-radius:999px;background:#102d20;color:#8ff0b5;font-size:10px;font-weight:800;text-transform:uppercase}.live::before{content:"";width:7px;height:7px;border-radius:50%;background:#55df82;box-shadow:0 0 8px #55df82}.live.offline{border-color:#704449;background:#341a1e;color:#ffc0c6}.live.offline::before{background:#d45b67;box-shadow:none}.actions{display:flex;gap:7px}button{border:1px solid #31506e;border-radius:8px;padding:7px 10px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}button:hover{border-color:#39bfff}button:disabled{opacity:.4;cursor:not-allowed}.body{padding:12px}.frame{position:relative;display:grid;place-items:center;min-height:220px;border-radius:9px;overflow:hidden;background:#04080d}.frame:fullscreen{width:100vw;height:100vh;border-radius:0;background:#000}.frame:fullscreen img{width:100%;height:100%;object-fit:contain}img{display:block;width:100%;min-height:220px;aspect-ratio:16/9;object-fit:contain;background:#04080d}.empty{padding:28px;color:#91a5bb;text-align:center}.loading{position:absolute;right:9px;bottom:9px;padding:4px 7px;border-radius:999px;background:#000a;color:#d5e4f0;font-size:10px;opacity:0;transition:opacity .2s}.loading.visible{opacity:1}.meta{display:flex;justify-content:space-between;gap:12px;margin-top:8px;color:#91a5bb;font-size:12px;overflow-wrap:anywhere}.meta span:last-child{text-align:right}
    </style><article class="panel"><div class="head"><div class="title"><strong id="title">Live-Kamera</strong><span class="live offline" id="live-state">offline</span></div><div class="actions"><button type="button" id="refresh">Aktualisieren</button><button type="button" id="toggle">Ausblenden</button><button type="button" id="fullscreen" disabled>Vollbild</button></div></div><div class="body" id="body"><div class="frame"><img id="camera-image" alt="Druckerkamera" hidden><div class="empty" id="empty">Keine Studio-Kamera verfügbar.</div><span class="loading" id="loading">Neues Bild …</span></div><div class="meta"><span id="entity"></span><span id="frame-info"></span></div></div></article>`;
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refreshFrame(true));
    this.#root.querySelector<HTMLButtonElement>("#toggle")?.addEventListener("click", () => this.toggle());
    this.#root.querySelector<HTMLButtonElement>("#fullscreen")?.addEventListener("click", () => void this.enterFullscreen());
    this.#mounted = true;
  }

  #storageKey(): string | null {
    const key = this.getAttribute("storage-key")?.trim();
    return key ? `ultimate-3d-studio-v6:camera:${key}:collapsed` : null;
  }

  #initialCollapsed(): boolean {
    const key = this.#storageKey();
    if (key) {
      try {
        const stored = localStorage.getItem(key);
        if (stored === "1") return true;
        if (stored === "0") return false;
      } catch {}
    }
    return this.hasAttribute("collapsed");
  }

  #persist(): void {
    const key = this.#storageKey();
    if (!key) return;
    try { localStorage.setItem(key, this.#collapsed ? "1" : "0"); } catch {}
  }

  #cameraEntity(): CameraSelection | null {
    const candidates = Object.entries(this.#hass?.states ?? {})
      .filter((entry): entry is [string, HassState] => entry[0].startsWith("camera.") && isHassState(entry[1]))
      .filter(([entityId, state]) => {
        const provider = String(state.attributes.provider || "").toLowerCase();
        return entityId.includes("3d_studio_v6")
          || entityId.includes("ultimate_3d_studio_v6")
          || entityId.includes("bambu_a1_native_live_camera")
          || provider === "bambu_native_tls_jpeg";
      })
      .sort((left, right) => {
        const leftAvailable = !["unavailable", "unknown"].includes(left[1].state) ? 0 : 1;
        const rightAvailable = !["unavailable", "unknown"].includes(right[1].state) ? 0 : 1;
        return leftAvailable - rightAvailable || left[0].localeCompare(right[0]);
      });
    const selected = candidates[0];
    return selected ? { entityId: selected[0], state: selected[1] } : null;
  }

  #cameraSequence(state: HassState): number | null {
    return numericAttribute(state, "sequence", "native_sequence", "frames_received", "native_frames_received");
  }

  #cameraUrl(camera: CameraSelection): string {
    const picture = camera.state.attributes.entity_picture;
    const base = typeof picture === "string" && picture.startsWith("/")
      ? picture
      : `/api/camera_proxy/${encodeURIComponent(camera.entityId)}`;
    return `${base}${base.includes("?") ? "&" : "?"}_v6_frame=${Date.now()}`;
  }

  #canRefresh(): boolean {
    return !this.#collapsed
      && !document.hidden
      && this.isConnected
      && this.#viewportVisible;
  }

  #startFrameTimer(): void {
    if (this.#frameTimer !== null) return;
    this.#frameTimer = globalThis.setInterval(() => this.#requestVisibleFrame(true), FRAME_INTERVAL_MS);
  }

  #stopFrameTimer(): void {
    if (this.#frameTimer !== null) globalThis.clearInterval(this.#frameTimer);
    this.#frameTimer = null;
  }

  #requestVisibleFrame(force = false): void {
    if (!this.#canRefresh() || this.#loading) return;
    const now = Date.now();
    if (!force && now - this.#lastRefreshAt < MIN_REFRESH_GAP_MS) return;
    if (!this.#cameraEntity()) return;
    void this.#refreshFrame(force);
  }

  async #refreshFrame(force = false): Promise<void> {
    if (this.#loading || !this.#canRefresh()) return;
    const camera = this.#cameraEntity();
    if (!camera) {
      this.#updateMetadata();
      return;
    }
    const sequence = this.#cameraSequence(camera.state);
    if (!force && this.#currentObjectUrl && sequence !== null && sequence === this.#lastSequence) return;

    this.#loading = true;
    this.#lastRefreshAt = Date.now();
    this.#setLoading(true);
    const controller = new AbortController();
    this.#frameController = controller;
    this.#requestedEntityId = camera.entityId;
    let nextUrl = "";
    const timeout = globalThis.setTimeout(() => controller.abort(), FRAME_REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(this.#cameraUrl(camera), {
        cache: "no-store",
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Kamera HTTP ${response.status}`);
      const blob = await response.blob();
      if (!blob.type.startsWith("image/") || blob.size === 0) throw new Error("Kamera lieferte kein gültiges Bild.");
      nextUrl = URL.createObjectURL(blob);
      await waitForCameraImage(new Image(), nextUrl, controller.signal);
      const image = this.#root.querySelector<HTMLImageElement>("#camera-image");
      const empty = this.#root.querySelector<HTMLElement>("#empty");
      if (!image || !this.#canRefresh() || controller.signal.aborted
        || this.#frameController !== controller || this.#cameraEntity()?.entityId !== camera.entityId) return;
      const previous = this.#currentObjectUrl;
      this.#currentObjectUrl = nextUrl;
      this.#currentEntityId = camera.entityId;
      image.src = nextUrl;
      nextUrl = ""; // The displayed frame now owns this object URL.
      image.hidden = false;
      if (empty) empty.hidden = true;
      if (previous) URL.revokeObjectURL(previous);
      this.#lastSequence = sequence;
      this.#updateMetadata();
    } catch (error) {
      if (this.#frameController !== controller || controller.signal.aborted) return;
      const empty = this.#root.querySelector<HTMLElement>("#empty");
      if (empty && !this.#currentObjectUrl) {
        empty.hidden = false;
        empty.textContent = error instanceof Error ? error.message : "Kamerabild ist vorübergehend nicht verfügbar.";
      }
    } finally {
      globalThis.clearTimeout(timeout);
      if (nextUrl) URL.revokeObjectURL(nextUrl);
      if (this.#frameController === controller) {
        this.#frameController = null;
        this.#requestedEntityId = "";
        this.#loading = false;
        this.#setLoading(false);
      }
    }
  }

  #cancelFrameRequest(): void {
    const controller = this.#frameController;
    this.#frameController = null;
    this.#requestedEntityId = "";
    controller?.abort();
    this.#loading = false;
    this.#setLoading(false);
  }

  #clearFrame(): void {
    this.#cancelFrameRequest();
    if (this.#currentObjectUrl) URL.revokeObjectURL(this.#currentObjectUrl);
    this.#currentObjectUrl = "";
    this.#currentEntityId = "";
    this.#lastSequence = null;
    const image = this.#root.querySelector<HTMLImageElement>("#camera-image");
    if (image) {
      image.removeAttribute("src");
      image.hidden = true;
    }
  }

  #updateCollapsedState(): void {
    const body = this.#root.querySelector<HTMLElement>("#body");
    const toggle = this.#root.querySelector<HTMLButtonElement>("#toggle");
    if (body) body.hidden = this.#collapsed;
    if (toggle) {
      toggle.textContent = this.#collapsed ? "Einblenden" : "Ausblenden";
      toggle.setAttribute("aria-expanded", String(!this.#collapsed));
    }
  }

  #updateMetadata(): void {
    if (!this.#mounted) return;
    const requestedTitle = this.getAttribute("title")?.trim() || "Live-Kamera";
    const camera = this.#cameraEntity();
    const available = Boolean(camera && !["unavailable", "unknown"].includes(camera.state.state));
    const sequence = camera ? this.#cameraSequence(camera.state) : null;
    const lastFrame = camera ? camera.state.attributes.last_frame_at || camera.state.attributes.native_last_frame_at : null;
    const titleNode = this.#root.querySelector<HTMLElement>("#title");
    const liveNode = this.#root.querySelector<HTMLElement>("#live-state");
    const entityNode = this.#root.querySelector<HTMLElement>("#entity");
    const frameNode = this.#root.querySelector<HTMLElement>("#frame-info");
    const fullscreen = this.#root.querySelector<HTMLButtonElement>("#fullscreen");
    const image = this.#root.querySelector<HTMLImageElement>("#camera-image");
    const empty = this.#root.querySelector<HTMLElement>("#empty");
    if (titleNode) titleNode.textContent = requestedTitle === "Kamera-Snapshot" ? "Live-Kamera" : requestedTitle;
    if (liveNode) {
      liveNode.textContent = available ? "Live" : "offline";
      liveNode.classList.toggle("offline", !available);
    }
    if (entityNode) entityNode.textContent = camera?.entityId || "";
    if (frameNode) frameNode.textContent = sequence === null ? String(lastFrame || "") : `Frame ${sequence}${lastFrame ? ` · ${String(lastFrame)}` : ""}`;
    if (fullscreen) fullscreen.disabled = !available || !image?.src;
    if (!camera && empty) {
      empty.hidden = false;
      empty.textContent = "Keine Studio-Kamera verfügbar.";
    }
  }

  #setLoading(value: boolean): void {
    this.#root.querySelector<HTMLElement>("#loading")?.classList.toggle("visible", value);
  }
}

if (!customElements.get("printer-camera-panel")) {
  customElements.define("printer-camera-panel", PrinterCameraPanel);
}

