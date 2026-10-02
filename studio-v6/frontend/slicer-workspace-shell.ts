import "./slicer-workspace-v3.js";
import "./slicer-process-options.js";
import "./slicer-job-manager.js";
import "./slicer-toolpath-viewer.js";
import "./v6-context-menu.js";
import { requestWorkspaceSource } from "./workspace-source-request.js";
import { fetchSliceJob, inspectSliceModel, type SliceJob, type SliceModelInspection } from "./slicing-api.js";
import {
  bindMultimaterialPanel,
  createMultimaterialState,
  loadAmsIntoState,
  materialPlan,
  renderMultimaterialPanel,
  type MultimaterialState,
} from "./slicer-multimaterial.js";
import { setActiveSliceMaterialPlan } from "./plate-slice-api.js";
import type { V6ContextMenu, V6ContextMenuItem } from "./v6-context-menu.js";
import type { Ultimate3DToolpathViewer } from "./slicer-toolpath-viewer.js";

type SlicerCore = HTMLElement & { file: File | null };
type SlicerTab = "prepare" | "materials" | "preview" | "jobs";
type SliceJobCreatedDetail = Readonly<{ jobId: string; fileName: string; plateIndex: number }>;

const ACTIVE = new Set(["queued", "running", "cancelling"]);

export class Ultimate3DSlicerWorkspaceShell extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #core: SlicerCore | null = null;
  #viewer: Ultimate3DToolpathViewer | null = null;
  #file: File | null = null;
  #tab: SlicerTab = "prepare";
  #inspection: SliceModelInspection | null = null;
  #materials: MultimaterialState = createMultimaterialState(null);
  #generation = 0;
  #previewStatus = "Nach dem Slicen erscheint hier das echte 3D-Druckergebnis aus dem erzeugten G-Code.";
  #previewJobId = "";

  set file(value: File | null) {
    this.#file = value;
    if (value && this.#core) this.#core.file = value;
    const label = this.#root.querySelector<HTMLElement>("#file-name");
    if (label) label.textContent = value?.name || "Kein Modell geladen";
    if (value) {
      this.#setTab("prepare");
      void this.#inspect(value);
    } else {
      this.#inspection = null;
      this.#materials = createMultimaterialState(null);
      setActiveSliceMaterialPlan(undefined);
      this.#renderMaterials();
    }
  }

  get file(): File | null { return this.#file; }

  connectedCallback(): void {
    if (!this.#core) this.#mount();
    window.addEventListener("ultimate-3d-slice-job-created", this.#onSliceJobCreated as EventListener);
    if (this.#file) void this.#inspect(this.#file);
  }

  disconnectedCallback(): void {
    this.#generation += 1;
    window.removeEventListener("ultimate-3d-slice-job-created", this.#onSliceJobCreated as EventListener);
  }

  readonly #onSliceJobCreated = (event: CustomEvent<SliceJobCreatedDetail>): void => {
    const detail = event.detail;
    if (!detail?.jobId) return;
    this.#previewJobId = detail.jobId;
    this.#previewStatus = `Druckplatte ${detail.plateIndex + 1} wird geslicet. Die echte 3D-Vorschau wird anschließend automatisch geöffnet.`;
    this.#renderPreviewStatus();
    void this.#waitForPreview(detail.jobId);
  };

  async #waitForPreview(jobId: string): Promise<void> {
    const generation = ++this.#generation;
    try {
      let job: SliceJob = await fetchSliceJob(jobId);
      while (generation === this.#generation && ACTIVE.has(job.status)) {
        this.#previewStatus = job.status === "queued" ? "Slicer wartet auf die Ausführung …" : "G-Code wird erzeugt und für die 3D-Vorschau vorbereitet …";
        this.#renderPreviewStatus();
        await new Promise((resolve) => window.setTimeout(resolve, 700));
        job = await fetchSliceJob(jobId);
      }
      if (generation !== this.#generation) return;
      if (job.status !== "succeeded") {
        this.#previewStatus = job.error || "Slicing wurde nicht erfolgreich abgeschlossen.";
        this.#renderPreviewStatus();
        return;
      }
      this.#previewStatus = "Slicing abgeschlossen. Reale Extrusionsbahnen werden als WebGL-3D-Mesh geladen.";
      if (this.#viewer) this.#viewer.jobId = jobId;
      this.#setTab("preview");
      this.#renderPreviewStatus();
    } catch (error) {
      this.#previewStatus = error instanceof Error ? error.message : String(error);
      this.#renderPreviewStatus();
    }
  }

  async #inspect(file: File): Promise<void> {
    const generation = ++this.#generation;
    this.#inspection = null;
    this.#materials = createMultimaterialState(null);
    this.#renderMaterials();
    try {
      const inspection = await inspectSliceModel(file);
      if (generation !== this.#generation) return;
      this.#inspection = inspection;
      this.#materials = createMultimaterialState(inspection);
      setActiveSliceMaterialPlan(materialPlan(this.#materials));
      this.#renderMaterials();
      if (inspection.format === "3mf" && inspection.objects.length) void this.#reloadAms();
    } catch {
      if (generation !== this.#generation) return;
      this.#inspection = null;
      this.#materials = createMultimaterialState(null);
      setActiveSliceMaterialPlan(undefined);
      this.#renderMaterials();
    }
  }

  async #reloadAms(): Promise<void> {
    await loadAmsIntoState(this.#materials);
    setActiveSliceMaterialPlan(materialPlan(this.#materials));
    this.#renderMaterials();
  }

  #mount(): void {
    const style = document.createElement("style");
    style.textContent = `:host{display:block;width:100%;height:100%;min-width:0;min-height:0;overflow:hidden;background:#08101a;color:#eef5ff}*{box-sizing:border-box}.root{display:grid;grid-template-rows:auto auto minmax(0,1fr);width:100%;height:100%;min-height:720px;overflow:hidden}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:8px 12px;border-bottom:1px solid #26384f;background:#0d1723}.toolbar strong{margin-right:auto;color:#9eb3c8}.toolbar button,.tabs button{min-height:36px;padding:7px 10px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}.toolbar .danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}.file{max-width:min(34vw,420px);overflow:hidden;color:#8298ae;font-size:11px;text-overflow:ellipsis;white-space:nowrap}.tabs{display:flex;gap:8px;padding:8px 12px;overflow-x:auto;border-bottom:1px solid #26384f;background:#0a141f}.tabs button{flex:0 0 auto;white-space:nowrap}.tabs button.active{border-color:#42c8ff;background:#17638a}.stage{position:relative;width:100%;height:100%;min-width:0;min-height:0;overflow:hidden}.panel{display:none;width:100%;height:100%;min-width:0;min-height:0}.panel.active{display:block}.prepare{overflow:auto}.prepare-controls{display:grid;grid-template-columns:minmax(300px,36%) minmax(0,1fr);min-height:620px}.prepare-controls>ultimate-3d-slicer-process-options{border-right:1px solid #26384f}.prepare-controls>ultimate-3d-slicer-workspace{min-width:0}.materials{overflow:auto;padding:12px}.preview{overflow:hidden}.preview-status{padding:8px 12px;border-bottom:1px solid #26384f;background:#0e1a25;color:#8fa6ba}.jobs{padding:10px;overflow:hidden}.jobs>ultimate-3d-slicer-job-manager,.preview>ultimate-3d-toolpath-viewer{display:block;width:100%;height:100%;min-height:0}.materials .multimaterial-panel{display:grid;gap:12px}.mm-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.mm-head b,.mm-head small{display:block}.mm-head small{color:#8096aa}.ams-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px}.ams-slot,.material-row,.purge-card{border:1px solid #29445d;border-radius:9px;background:#0f1d2a;padding:9px}.ams-slot{display:grid;grid-template-columns:18px 1fr;gap:4px 8px;align-items:center}.ams-slot small,.ams-slot span:last-child{grid-column:2;color:#8298ad}.material-node{margin-left:calc(var(--depth) * 16px)}.material-row{display:grid;grid-template-columns:18px minmax(0,1fr) minmax(160px,240px);gap:8px;align-items:center;margin-bottom:7px}.material-color{width:14px;height:14px;border-radius:4px;border:1px solid #ffffff44}.material-name b,.material-name small{display:block}.material-name small{color:#8298ad}.material-row select,.purge-card input{min-height:34px;border:1px solid #31506e;border-radius:7px;background:#091520;color:#eef5ff}.purge-card{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.purge-card label,.purge-card div{display:grid;gap:5px}.loading{color:#8298ad}.error{padding:9px;border:1px solid #753d47;border-radius:8px;background:#351d23;color:#ffbdc4}@media(max-width:1100px){.prepare-controls{grid-template-columns:1fr}.prepare-controls>ultimate-3d-slicer-process-options{border-right:0;border-bottom:1px solid #26384f}}@media(max-width:700px){:host{overflow:auto}.root{height:auto;min-height:0;overflow:visible}.toolbar strong{width:100%}.file{width:100%;max-width:100%}.stage,.panel{height:auto;min-height:520px;overflow:visible}.material-row{grid-template-columns:18px 1fr}.material-row select{grid-column:1/-1}}`;
    const root = document.createElement("section"); root.className = "root";
    root.innerHTML = `<header class="toolbar"><strong>Vorbereiten und Slicen</strong><button id="download">Quelldatei herunterladen</button><button class="danger" id="clear">Modell entfernen</button><span class="file" id="file-name">${this.#file?.name || "Kein Modell geladen"}</span></header><nav class="tabs"><button data-tab="prepare">Vorbereiten</button><button data-tab="materials">Mehrmaterial & AMS</button><button data-tab="preview">Vorschau</button><button data-tab="jobs">Aufträge und GCode-Artefakte</button></nav><main class="stage"><section class="panel prepare" data-panel="prepare"><div class="prepare-controls" id="prepare-controls"></div></section><section class="panel materials" data-panel="materials"><div id="materials-host"></div></section><section class="panel preview" data-panel="preview"><div class="preview-status" id="preview-status"></div><ultimate-3d-toolpath-viewer></ultimate-3d-toolpath-viewer></section><section class="panel jobs" data-panel="jobs"></section></main>`;
    const controls = root.querySelector<HTMLElement>("#prepare-controls")!;
    const jobs = root.querySelector<HTMLElement>('[data-panel="jobs"]')!;
    controls.append(document.createElement("ultimate-3d-slicer-process-options"), this.#createCore());
    jobs.append(document.createElement("ultimate-3d-slicer-job-manager"));
    this.#root.replaceChildren(style, root, document.createElement("v6-context-menu"));
    this.#viewer = this.#root.querySelector<Ultimate3DToolpathViewer>("ultimate-3d-toolpath-viewer");
    this.#root.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach((button) => button.addEventListener("click", () => this.#setTab(button.dataset.tab as SlicerTab)));
    this.#root.querySelector<HTMLButtonElement>("#download")?.addEventListener("click", () => this.#downloadSource());
    this.#root.querySelector<HTMLButtonElement>("#clear")?.addEventListener("click", () => this.#clear());
    this.#setTab(this.#tab);
    this.#renderMaterials();
    this.#renderPreviewStatus();
  }

  #createCore(): SlicerCore {
    const core = document.createElement("ultimate-3d-slicer-workspace") as SlicerCore;
    core.addEventListener("contextmenu", (event) => this.#openContext(event));
    this.#core = core;
    if (this.#file) core.file = this.#file;
    return core;
  }

  #renderMaterials(): void {
    const host = this.#root.querySelector<HTMLElement>("#materials-host");
    if (!host) return;
    host.innerHTML = renderMultimaterialPanel(this.#inspection, this.#materials);
    bindMultimaterialPanel(host, this.#materials, () => {
      setActiveSliceMaterialPlan(materialPlan(this.#materials)); this.#renderMaterials();
    }, async () => this.#reloadAms());
  }

  #renderPreviewStatus(): void {
    const status = this.#root.querySelector<HTMLElement>("#preview-status");
    if (status) status.textContent = this.#previewStatus;
  }

  #setTab(tab: SlicerTab): void {
    this.#tab = tab;
    this.#root.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
    this.#root.querySelectorAll<HTMLElement>("[data-panel]").forEach((panel) => panel.classList.toggle("active", panel.dataset.panel === tab));
    if (tab === "preview" && this.#previewJobId && this.#viewer) this.#viewer.jobId = this.#previewJobId;
  }

  #downloadSource(): void {
    if (!this.#file) return;
    const url = URL.createObjectURL(this.#file); const anchor = document.createElement("a"); anchor.href = url; anchor.download = this.#file.name; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  #clear(): void {
    this.#generation += 1; this.#file = null; this.#inspection = null; this.#materials = createMultimaterialState(null); this.#previewJobId = ""; this.#previewStatus = "Nach dem Slicen erscheint hier das echte 3D-Druckergebnis aus dem erzeugten G-Code."; setActiveSliceMaterialPlan(undefined);
    const previous = this.#core; const next = this.#createCore(); previous?.replaceWith(next);
    const file = this.#root.querySelector<HTMLElement>("#file-name"); if (file) file.textContent = "Kein Modell geladen";
    this.#setTab("prepare"); this.#renderMaterials(); this.#renderPreviewStatus();
  }

  #openContext(event: Event): void {
    event.preventDefault(); const mouse = event as MouseEvent;
    const items: V6ContextMenuItem[] = [
      { label: "Modell aus Galerie vorbereiten", action: () => requestWorkspaceSource(this, "slicer", "gallery") },
      { label: "Modell von SD-Karte vorbereiten", action: () => requestWorkspaceSource(this, "slicer", "storage") },
      { label: "Modell aus MakerWorld vorbereiten", action: () => requestWorkspaceSource(this, "slicer", "makerworld") },
      { label: "Mehrmaterial & AMS öffnen", action: () => this.#setTab("materials") },
      { label: "Echte G-Code-Vorschau öffnen", action: () => this.#setTab("preview"), disabled: !this.#previewJobId },
      { label: "Quelldatei herunterladen", action: () => this.#downloadSource(), disabled: !this.#file },
      { label: "Modell entfernen", action: () => this.#clear(), disabled: !this.#file, danger: true },
    ];
    this.#root.querySelector<V6ContextMenu>("v6-context-menu")?.openAt(mouse.clientX, mouse.clientY, items);
  }
}

if (!customElements.get("ultimate-3d-slicer-shell")) customElements.define("ultimate-3d-slicer-shell", Ultimate3DSlicerWorkspaceShell);
