import "./studio-workspace-shell-v3.js";
import "./slicer-workspace-shell.js";
import { createActiveStudio3mf, downloadActiveStudio3mf } from "./studio-export-service.js";
import { sceneStore } from "./scene-store.js";
import type { WorkspaceSourceRequest } from "./workspace-source-request.js";

export type StudioMode = "cad" | "split" | "slicer";

type StudioShell = HTMLElement & { files: readonly File[] };
type SlicerShell = HTMLElement & { file: File | null };

export class Ultimate3DStudioWorkspace extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #studio: StudioShell | null = null;
  #slicer: SlicerShell | null = null;
  #mode: StudioMode = "cad";
  #sourceFile: File | null = null;
  #generatedFile: File | null = null;
  #unsubscribe: (() => void) | null = null;
  #status = "CAD-Szene, Vorbereitung, Slicer und Vorschau sind verbunden.";
  #error = "";

  set files(value: readonly File[]) {
    if (!value.length) return;
    this.#sourceFile = value[0] ?? null;
    if (this.#studio) this.#studio.files = value;
    this.#mode = "cad";
    this.#status = `${value.length} Quelldatei(en) wurden in das 3D-Studio geladen und automatisch auf der aktiven Druckplatte angeordnet.`;
    this.#error = "";
    this.#applyMode();
    this.#renderHeader();
  }

  set file(value: File | null) {
    if (!value) return;
    this.#sourceFile = value;
    if (this.#slicer) this.#slicer.file = value;
    this.#mode = "slicer";
    this.#status = `${value.name} wurde im 3D-Studio unter Vorbereiten geöffnet.`;
    this.#error = "";
    this.#applyMode();
    this.#renderHeader();
  }

  get file(): File | null { return this.#sourceFile; }

  connectedCallback(): void {
    if (!this.#root.childElementCount) this.#mount();
    if (!this.#unsubscribe) this.#unsubscribe = sceneStore.subscribe(() => this.#renderHeader());
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  #mount(): void {
    const style = document.createElement("style");
    style.textContent = `
      :host{display:block;width:100%;height:100%;min-width:0;min-height:720px;background:#08101a;color:#eef5ff}*{box-sizing:border-box}.studio{display:grid;grid-template-rows:auto minmax(0,1fr);width:100%;height:100%;min-height:720px}.bar{display:grid;grid-template-columns:minmax(260px,1fr) auto;gap:10px 18px;align-items:center;padding:10px 12px;border-bottom:1px solid #26384f;background:#0d1723}.title strong,.title span{display:block}.title strong{font-size:15px;color:#f4f8fc}.title span{margin-top:3px;color:#8398ad;font-size:10px}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.group{display:flex;gap:5px;align-items:center;padding:4px;border:1px solid #243b50;border-radius:10px;background:#0a131d}.controls button{min-height:34px;padding:7px 10px;border:1px solid #31506e;border-radius:7px;background:#14263a;color:#eef5ff;font-weight:700;cursor:pointer;white-space:nowrap}.controls button.active{border-color:#42c8ff;background:#17638a}.controls .source{background:#102131}.controls .storage{border-color:#c99a43;background:#493512}.controls .handoff{border-color:#49a86a;background:#17462a}.controls .export{border-color:#9b7a38;background:#33270f}.controls button:disabled{opacity:.4;cursor:not-allowed}.status{grid-column:1/-1;display:flex;justify-content:space-between;gap:10px;padding-top:2px;color:#7890a8;font-size:10px}.status .error{color:#ffb8c1}.work{min-width:0;min-height:0;overflow:auto}.work.split{display:grid;grid-template-columns:minmax(0,62%) minmax(520px,38%)}.pane{min-width:0;min-height:0;overflow:auto}.cad{border-right:1px solid #26384f}.pane[hidden]{display:none}.work.cad-only,.work.slicer-only{display:block}.work.cad-only .cad,.work.slicer-only .slicer{border:0}.pane>ultimate-3d-arranged-studio,.pane>ultimate-3d-slicer-shell{display:block;width:100%;height:100%;min-height:700px}@media(max-width:1899px){.work.split{grid-template-columns:1fr;grid-template-rows:auto auto}.work.split .cad{border-right:0;border-bottom:1px solid #26384f}.work.split .pane{min-height:700px}.bar{grid-template-columns:1fr}.controls{justify-content:flex-start}}@media(max-width:900px){.controls{align-items:stretch}.group{width:100%;overflow-x:auto}.controls button{flex:0 0 auto}.status{display:block}.status span{display:block;margin-top:3px}}`;

    const wrapper = document.createElement("section");
    wrapper.className = "studio";
    wrapper.innerHTML = `<header class="bar"><div class="title"><strong>Ultimate 3D-Studio V6</strong><span>CAD, Druckplatten, Mehrfarben, Vorbereitung, Slicing und echte G-Code-Vorschau</span></div><div class="controls"><div class="group sources"><button class="source" data-source="gallery">Galerie</button><button class="source storage" data-source="storage">SD-Karte</button><button class="source" data-source="makerworld">MakerWorld</button></div><div class="group modes"><button data-mode="cad">CAD</button><button data-mode="split">CAD + Vorbereiten</button><button data-mode="slicer">Vorbereiten</button></div><div class="group actions"><button class="handoff" id="handoff">Aktive Platte vorbereiten</button><button class="export" id="export">3MF exportieren</button></div></div><div class="status"><span id="status"></span><span id="scene"></span></div></header><main class="work cad-only" id="work"><section class="pane cad" id="cad"></section><section class="pane slicer" id="slicer"></section></main>`;

    const studio = document.createElement("ultimate-3d-arranged-studio") as StudioShell;
    const slicer = document.createElement("ultimate-3d-slicer-shell") as SlicerShell;
    this.#studio = studio;
    this.#slicer = slicer;
    wrapper.querySelector("#cad")?.append(studio);
    wrapper.querySelector("#slicer")?.append(slicer);
    this.#root.replaceChildren(style, wrapper);

    this.#root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((button) => button.addEventListener("click", () => {
      this.#mode = button.dataset.mode as StudioMode;
      this.#applyMode();
    }));
    this.#root.querySelectorAll<HTMLButtonElement>("[data-source]").forEach((button) => button.addEventListener("click", () => {
      const source = button.dataset.source as WorkspaceSourceRequest["source"];
      this.dispatchEvent(new CustomEvent<WorkspaceSourceRequest>("workspace-source-request", {
        detail: { target: "studio", source }, bubbles: true, composed: true,
      }));
    }));
    this.#root.querySelector<HTMLButtonElement>("#handoff")?.addEventListener("click", () => this.#handoffToSlicer());
    this.#root.querySelector<HTMLButtonElement>("#export")?.addEventListener("click", () => this.#exportActivePlate());
    this.#applyMode();
    this.#renderHeader();
  }

  #handoffToSlicer(): void {
    try {
      const file = createActiveStudio3mf();
      this.#generatedFile = file;
      this.#sourceFile = file;
      if (this.#slicer) this.#slicer.file = file;
      this.#mode = window.innerWidth >= 1900 ? "split" : "slicer";
      this.#status = `${file.name} wurde aus der aktiven CAD-Druckplatte erzeugt und unter Vorbereiten geöffnet.`;
      this.#error = "";
      this.#applyMode();
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    }
    this.#renderHeader();
  }

  #exportActivePlate(): void {
    try {
      const file = downloadActiveStudio3mf();
      this.#generatedFile = file;
      this.#status = `${file.name} wurde als 3MF exportiert.`;
      this.#error = "";
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    }
    this.#renderHeader();
  }

  #applyMode(): void {
    const work = this.#root.querySelector<HTMLElement>("#work");
    const cad = this.#root.querySelector<HTMLElement>("#cad");
    const slicer = this.#root.querySelector<HTMLElement>("#slicer");
    if (!work || !cad || !slicer) return;
    work.className = `work ${this.#mode === "cad" ? "cad-only" : this.#mode === "slicer" ? "slicer-only" : "split"}`;
    cad.hidden = this.#mode === "slicer";
    slicer.hidden = this.#mode === "cad";
    this.#root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((button) => button.classList.toggle("active", button.dataset.mode === this.#mode));
  }

  #renderHeader(): void {
    const state = sceneStore.getState();
    const plate = state.plates.find((item) => item.id === state.activePlateId) ?? state.plates[0] ?? null;
    const status = this.#root.querySelector<HTMLElement>("#status");
    const scene = this.#root.querySelector<HTMLElement>("#scene");
    const handoff = this.#root.querySelector<HTMLButtonElement>("#handoff");
    if (status) {
      status.textContent = this.#error || this.#status;
      status.classList.toggle("error", Boolean(this.#error));
    }
    if (scene) scene.textContent = plate ? `${plate.name} · ${plate.objects.length} Objekt(e)${this.#generatedFile ? ` · letzte Übergabe: ${this.#generatedFile.name}` : ""}` : "Keine aktive Druckplatte";
    if (handoff) handoff.disabled = !plate || !plate.objects.some((object) => object.visible);
  }
}

if (!customElements.get("ultimate-3d-merge-studio")) {
  customElements.define("ultimate-3d-merge-studio", Ultimate3DStudioWorkspace);
}