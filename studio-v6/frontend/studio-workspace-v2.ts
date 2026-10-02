import { V6_BRANDING } from "./branding.js";
import {
  bestFlatRotation,
  exportBinaryStl,
  positionCenteredOnPlate,
  positionOnBed,
  type ExportMesh,
} from "./mesh-export.js";
import { ProfileApi, type V6ProfileCatalog } from "./profile-api.js";
import { sceneStore, type PlateState, type SceneObject, type SceneState } from "./scene-store.js";
import {
  buildPlateProfiles,
  studioBuildPlateVisual,
  type StudioBuildPlateVisual,
} from "./studio-build-plates.js";
import { StudioPlateViewport } from "./studio-plate-viewport.js";
import {
  getStudioGeometry,
  removeStudioGeometry,
  setStudioGeometry,
} from "./studio-session.js";
import {
  StudioTransformTools,
  type StudioTransformInteractionState,
} from "./studio-transform-tools.js";
import { parseStl, type MeshInstance } from "./webgl-studio-viewport.js";
import { consumeWorkspaceFiles, queueWorkspaceFile } from "./workspace-file-handoff.js";

const DEFAULT_PLATE_ID = "plate-1";
const DEFAULT_PLATE_PROFILE_ID = "build-plate-smooth";
const DEFAULT_PLATE_SIZE = 256;

type StudioPointerState = {
  id: number;
  button: 0 | 2;
  x: number;
  y: number;
};

function objectId(): string {
  return `object-${crypto.randomUUID()}`;
}

function plateId(): string {
  return `plate-${crypto.randomUUID()}`;
}

function defaultPlate(id = DEFAULT_PLATE_ID, name = "Druckplatte 1", orderIndex = 0): PlateState {
  return {
    id,
    name,
    orderIndex,
    objects: [],
    buildPlateProfileId: DEFAULT_PLATE_PROFILE_ID,
    widthMm: DEFAULT_PLATE_SIZE,
    depthMm: DEFAULT_PLATE_SIZE,
  };
}

function defaultScene(): SceneState {
  return {
    projectId: `project-${crypto.randomUUID()}`,
    revision: 0,
    activePlateId: DEFAULT_PLATE_ID,
    plates: [defaultPlate()],
    selectedObjectIds: [],
  };
}

function isTextInputTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLInputElement
    || target instanceof HTMLTextAreaElement
    || target instanceof HTMLSelectElement
    || (target instanceof HTMLElement && target.isContentEditable);
}

function snapped(value: number, step: number): number {
  return step > 0 ? Math.round(value / step) * step : value;
}

function safeProjectFileName(value: string): string {
  const cleaned = value.replace(/[\\/:*?"<>|]+/g, "_").trim();
  return `${cleaned || "3D-Studio-Projekt"}.stl`;
}

function fixed(value: number): string {
  return Number.isFinite(value) ? value.toFixed(2) : "0.00";
}

export class Ultimate3DStudioWorkspaceV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #profileApi = new ProfileApi();
  #profileCatalog: V6ProfileCatalog | null = null;
  #unsubscribe: (() => void) | null = null;
  #viewport: StudioPlateViewport | null = null;
  #fileInput: HTMLInputElement | null = null;
  #transformTools: StudioTransformTools | null = null;
  #studioPointer: StudioPointerState | null = null;
  #renderedPlateKey = "";
  #status = "";
  #error = "";

  connectedCallback(): void {
    if (this.#unsubscribe) return;
    if (!sceneStore.getState().plates.length) {
      sceneStore.dispatch({ type: "load", state: defaultScene() });
    }
    this.tabIndex = 0;
    this.addEventListener("keydown", this.#onKeyDown);
    this.#mount();
    this.#unsubscribe = sceneStore.subscribe((state) => this.#render(state));
    void this.#loadProfiles();
    const pending = consumeWorkspaceFiles("studio");
    if (pending.length) void this.#importFiles(pending);
  }

  disconnectedCallback(): void {
    this.removeEventListener("keydown", this.#onKeyDown);
    this.#unsubscribe?.();
    this.#unsubscribe = null;
    this.#studioPointer = null;
    this.#viewport?.dispose();
    this.#viewport = null;
    this.#transformTools = null;
  }

  readonly #onKeyDown = (event: KeyboardEvent): void => {
    if (isTextInputTarget(event.composedPath()[0] ?? event.target)) return;
    const key = event.key.toLowerCase();
    if ((event.ctrlKey || event.metaKey) && key === "d") {
      event.preventDefault();
      this.#duplicateSelected();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && key === "e") {
      event.preventDefault();
      this.#exportToSlicer();
      return;
    }
    if (event.key === "Delete") {
      event.preventDefault();
      this.#deleteSelected();
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      this.#transformTools?.setMode("direct");
      return;
    }
    if (key === "g" || key === "r" || key === "s") {
      event.preventDefault();
      this.#transformTools?.setMode(key === "g" ? "translate" : key === "r" ? "rotate" : "scale");
      return;
    }
    if (key === "x" || key === "y" || key === "z") {
      event.preventDefault();
      this.#transformTools?.setAxis(key);
      return;
    }
    if (["ArrowRight", "ArrowUp", "ArrowLeft", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      this.#transformTools?.step(event.key === "ArrowRight" || event.key === "ArrowUp" ? 1 : -1);
    }
  };

  async #loadProfiles(): Promise<void> {
    try {
      this.#profileCatalog = await this.#profileApi.getCatalog();
      const state = sceneStore.getState();
      const plate = this.#activePlate(state);
      const selectedProfileId = plate?.buildPlateProfileId
        || this.#profileCatalog.selection.build_plate_profile_id
        || DEFAULT_PLATE_PROFILE_ID;
      const profile = this.#profileCatalog.profiles.find((item) => item.id === selectedProfileId)
        || buildPlateProfiles(this.#profileCatalog.profiles)[0];
      if (plate && profile) {
        const visual = studioBuildPlateVisual(profile);
        sceneStore.dispatch({
          type: "set_plate_profile",
          plateId: plate.id,
          profileId: profile.id,
          widthMm: visual.widthMm,
          depthMm: visual.depthMm,
        });
      }
    } catch (error) {
      this.#error = `Druckplattenprofile konnten nicht geladen werden: ${error instanceof Error ? error.message : String(error)}`;
      this.#render(sceneStore.getState());
    }
  }

  #mount(): void {
    const style = document.createElement("style");
    style.textContent = `
      :host{display:block;min-height:720px;color:#edf6ff;outline:none}
      :host(:focus-visible){box-shadow:inset 0 0 0 1px #36bfff}
      *{box-sizing:border-box}.layout{display:grid;grid-template-columns:300px minmax(0,1fr) 330px;min-height:720px;background:#08101a}.panel{border-color:#24364b;background:#0c1622}.left{border-right:1px solid #24364b;overflow:auto}.right{border-left:1px solid #24364b;padding:14px;overflow:auto}.toolbar{display:flex;flex-wrap:wrap;gap:7px;padding:10px;border-bottom:1px solid #24364b;background:#0f1b29}.toolbar-section{display:flex;flex-wrap:wrap;gap:7px;width:100%}.toolbar-section+.toolbar-section{padding-top:7px;border-top:1px solid #26394f}button{border:1px solid #31506e;border-radius:8px;padding:8px 10px;background:#14263a;color:#edf6ff;cursor:pointer;font-weight:650}button:hover{border-color:#36bfff}.primary{border-color:#35a9e8;background:#176187}.danger{border-color:#7c3441;background:#321820}button:disabled{opacity:.4;cursor:not-allowed}.plate-panel{padding:10px;border-bottom:1px solid #24364b;background:#0a141f}.plate-panel h3{margin:0 0 8px;font-size:12px;color:#94abc2;text-transform:uppercase;letter-spacing:.08em}.plate-tabs{display:flex;gap:5px;overflow:auto;padding-bottom:7px}.plate-tab{min-width:42px;padding:7px 9px}.plate-tab.active{border-color:#49c8ff;background:#163d58}.plate-actions{display:grid;grid-template-columns:1fr auto auto;gap:6px}.plate-actions select{min-width:0;width:100%;padding:8px;border:1px solid #31506e;border-radius:8px;background:#09131f;color:#fff}.plate-preview{display:grid;grid-template-columns:50px 1fr;gap:9px;align-items:center;margin-top:8px;padding:8px;border:1px solid #2d455d;border-radius:8px;background:#101b28}.plate-swatch{width:50px;height:43px;border:1px solid #ffffff42;border-radius:5px;background-color:var(--plate-base);background-image:linear-gradient(var(--plate-grid) 1px,transparent 1px),linear-gradient(90deg,var(--plate-grid) 1px,transparent 1px);background-size:8px 8px}.plate-preview strong,.plate-preview small{display:block}.plate-preview small{color:#8ca1b8;margin-top:2px}.tree{padding:10px;display:grid;gap:6px;overflow:auto;max-height:460px}.tree h3{margin:4px 0 8px;font-size:13px;color:#94abc2;text-transform:uppercase}.row{width:100%;display:grid;grid-template-columns:1fr auto;text-align:left;gap:8px;align-items:center}.row[selected]{border-color:#ffad42;background:#2b251a}.row small{color:#8ca1b8}.status{margin:10px;padding:9px;border:1px solid #2c684b;border-radius:8px;background:#10261b;color:#92e7b4;font-size:12px}.status.error{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}.viewport{position:relative;min-width:0;overflow:hidden;background:#050a10}canvas{display:block;width:100%;height:100%;min-height:720px;touch-action:none;cursor:grab;user-select:none;-webkit-user-select:none}canvas[dragging]{cursor:grabbing}.help-overlay{position:absolute;right:14px;bottom:14px;padding:8px 10px;border:1px solid #2b4967;border-radius:8px;background:#09121dcc;color:#8fb0ce;font-size:12px;pointer-events:none}.plate-badge{position:absolute;left:14px;top:14px;min-width:230px;padding:9px 11px;border:1px solid var(--plate-accent,#45bdf5);border-radius:9px;background:#09121de8;pointer-events:none}.plate-badge strong,.plate-badge span{display:block}.plate-badge span{margin-top:3px;color:#9db2c7;font-size:11px}.coordinate-gizmo{position:absolute;left:14px;bottom:14px;width:205px;padding:9px;border:1px solid #314a62;border-radius:9px;background:#09121de8;pointer-events:none}.coordinate-title{margin-bottom:6px;color:#9db2c7;font-size:10px;text-transform:uppercase;letter-spacing:.1em}.axis-row{display:grid;grid-template-columns:32px 24px 1fr;gap:7px;align-items:center;margin:3px 0}.axis-arrow{font-size:21px;font-weight:900}.axis-row.x .axis-arrow,.axis-row.x b{color:#ef5350}.axis-row.y .axis-arrow,.axis-row.y b{color:#66bb6a}.axis-row.z .axis-arrow,.axis-row.z b{color:#42a5f5}.axis-row code{color:#edf6ff;font:12px ui-monospace,SFMono-Regular,Consolas,monospace}.drop{position:absolute;inset:18px;display:none;place-items:center;border:2px dashed #40c7ff;border-radius:16px;background:#0c1d2ed9;font-size:22px;font-weight:700;z-index:5}.viewport[dragging] .drop{display:grid}.right h2{margin:0 0 6px}.right p{color:#91a5bb}.field{display:grid;grid-template-columns:80px 1fr;gap:8px;align-items:center;margin:8px 0}.field input{width:100%;padding:7px;border:1px solid #2d4662;border-radius:7px;background:#09121c;color:#fff}.color-row{display:grid;grid-template-columns:1fr 54px;gap:8px;align-items:center;margin:12px 0}.color-row input{width:54px;height:36px;padding:2px;border:1px solid #31506e;border-radius:7px;background:#09121c}.stats{margin-top:16px;padding-top:12px;border-top:1px solid #26394f;color:#9cb1c7;font-size:12px;line-height:1.7}.help{margin-top:10px;color:#71869c;font-size:11px;line-height:1.5}@media(max-width:1100px){.layout{grid-template-columns:250px minmax(0,1fr)}.right{display:none}}@media(max-width:760px){.layout{grid-template-columns:1fr}.left{display:none}canvas{min-height:620px}.plate-badge{min-width:180px}.coordinate-gizmo{width:180px}}
    `;
    const layout = document.createElement("section");
    layout.className = "layout";
    layout.addEventListener("contextmenu", (event) => event.preventDefault());

    const left = document.createElement("aside");
    left.className = "panel left";
    const toolbar = document.createElement("div");
    toolbar.className = "toolbar";
    const fileActions = document.createElement("div");
    fileActions.className = "toolbar-section";
    fileActions.append(
      this.#button("STL importieren", () => this.#fileInput?.click()),
      this.#button("Im Slicer öffnen", () => this.#exportToSlicer(), "primary"),
      this.#button("Alles einpassen", () => this.#viewport?.frameAll()),
    );
    const objectActions = document.createElement("div");
    objectActions.className = "toolbar-section";
    objectActions.append(
      this.#button("Duplizieren", () => this.#duplicateSelected()),
      this.#button("Zentrieren", () => this.#centerSelected()),
      this.#button("Flach legen", () => this.#layFlatSelected()),
      this.#button("Auf Druckbett", () => this.#placeSelectedOnBed()),
      this.#button("Löschen", () => this.#deleteSelected(), "danger"),
    );
    toolbar.append(fileActions, objectActions);
    const platePanel = document.createElement("section");
    platePanel.className = "plate-panel";
    platePanel.id = "plate-panel";
    const status = document.createElement("div");
    status.id = "status";
    const tree = document.createElement("div");
    tree.className = "tree";
    tree.id = "tree";
    left.append(toolbar, platePanel, status, tree);

    const viewportHost = document.createElement("main");
    viewportHost.className = "viewport";
    viewportHost.addEventListener("pointerdown", () => this.focus({ preventScroll: true }));
    const canvas = document.createElement("canvas");
    this.#bindStudioPointerControls(canvas);
    const drop = document.createElement("div");
    drop.className = "drop";
    drop.textContent = "STL hier ablegen";
    const plateBadge = document.createElement("div");
    plateBadge.className = "plate-badge";
    plateBadge.id = "plate-badge";
    const coordinateGizmo = document.createElement("div");
    coordinateGizmo.className = "coordinate-gizmo";
    coordinateGizmo.id = "coordinate-gizmo";
    const help = document.createElement("div");
    help.className = "help-overlay";
    help.textContent = "Links: Objekt drehen · Rechts: Objekt verschieben · Mausrad: Zoom";
    viewportHost.append(canvas, drop, plateBadge, coordinateGizmo, help);

    const right = document.createElement("aside");
    right.className = "panel right";
    const inspectorDetails = document.createElement("div");
    inspectorDetails.id = "inspector-details";
    const transformTools = document.createElement("studio-transform-tools") as StudioTransformTools;
    transformTools.addEventListener("studio-place-on-bed", () => this.#placeSelectedOnBed());
    this.#transformTools = transformTools;
    right.append(inspectorDetails, transformTools);

    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".stl,model/stl,application/sla";
    input.multiple = true;
    input.hidden = true;
    input.addEventListener("change", () => void this.#importFiles(input.files));
    this.#fileInput = input;

    viewportHost.addEventListener("dragenter", (event) => {
      event.preventDefault();
      viewportHost.setAttribute("dragging", "");
    });
    viewportHost.addEventListener("dragover", (event) => event.preventDefault());
    viewportHost.addEventListener("dragleave", (event) => {
      if (event.target === viewportHost) viewportHost.removeAttribute("dragging");
    });
    viewportHost.addEventListener("drop", (event) => {
      event.preventDefault();
      viewportHost.removeAttribute("dragging");
      void this.#importFiles(event.dataTransfer?.files ?? null);
    });

    layout.append(left, viewportHost, right);
    this.#root.replaceChildren(style, layout, input);
    this.#viewport = new StudioPlateViewport(canvas, this.#currentPlateVisual(sceneStore.getState()));
  }

  #button(label: string, action: () => void, className = ""): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.className = className;
    button.addEventListener("click", action);
    return button;
  }

  #bindStudioPointerControls(canvas: HTMLCanvasElement): void {
    canvas.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
    }, { capture: true });
    canvas.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 && event.button !== 2) return;
      if (!this.#selectedContext()) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      this.#studioPointer = { id: event.pointerId, button: event.button, x: event.clientX, y: event.clientY };
      canvas.setAttribute("dragging", "");
      try { canvas.setPointerCapture(event.pointerId); } catch (_error) {}
    }, { capture: true });
    canvas.addEventListener("pointermove", (event) => {
      const pointer = this.#studioPointer;
      if (!pointer || pointer.id !== event.pointerId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const dx = event.clientX - pointer.x;
      const dy = event.clientY - pointer.y;
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      this.#applyStudioPointerDrag(pointer.button, dx, dy);
    }, { capture: true });
    const finish = (event: PointerEvent): void => {
      const pointer = this.#studioPointer;
      if (!pointer || pointer.id !== event.pointerId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      this.#studioPointer = null;
      canvas.removeAttribute("dragging");
      try { canvas.releasePointerCapture(event.pointerId); } catch (_error) {}
    };
    canvas.addEventListener("pointerup", finish, { capture: true });
    canvas.addEventListener("pointercancel", finish, { capture: true });
  }

  #applyStudioPointerDrag(button: 0 | 2, dx: number, dy: number): void {
    if (dx === 0 && dy === 0) return;
    const selected = this.#selectedContext();
    if (!selected) return;
    const interaction: StudioTransformInteractionState = this.#transformTools?.getInteractionState()
      ?? { mode: "direct", axis: "x", snap: 1 };
    const position = [...selected.object.transform.position] as [number, number, number];
    const rotation = [...selected.object.transform.rotation] as [number, number, number];
    const scale = [...selected.object.transform.scale] as [number, number, number];
    if (button === 2) {
      position[0] += dx * 0.35;
      position[1] -= dy * 0.35;
    } else if (interaction.mode === "direct") {
      rotation[2] += dx * 0.32;
      rotation[0] -= dy * 0.22;
    } else {
      const index = interaction.axis === "x" ? 0 : interaction.axis === "y" ? 1 : 2;
      const dragDelta = Math.abs(dx) >= Math.abs(dy) ? dx : -dy;
      if (interaction.mode === "translate") position[index] = snapped(position[index] + dragDelta * 0.35, interaction.snap);
      else if (interaction.mode === "rotate") rotation[index] = snapped(rotation[index] + dragDelta * 0.32, interaction.snap);
      else scale[index] = Math.max(0.001, snapped(scale[index] + dragDelta * 0.005, interaction.snap));
    }
    sceneStore.dispatch({
      type: "set_transform",
      plateId: selected.plateId,
      objectId: selected.object.id,
      transform: { position, rotation, scale },
    });
  }

  #activePlate(state: Readonly<SceneState>): PlateState | null {
    return state.plates.find((plate) => plate.id === state.activePlateId) ?? state.plates[0] ?? null;
  }

  #currentPlateVisual(state: Readonly<SceneState>): StudioBuildPlateVisual {
    const plate = this.#activePlate(state);
    const profileId = plate?.buildPlateProfileId
      || this.#profileCatalog?.selection.build_plate_profile_id
      || DEFAULT_PLATE_PROFILE_ID;
    const profile = this.#profileCatalog?.profiles.find((item) => item.id === profileId);
    const visual = studioBuildPlateVisual(profile);
    return {
      ...visual,
      widthMm: plate?.widthMm || visual.widthMm,
      depthMm: plate?.depthMm || visual.depthMm,
    };
  }

  async #setBuildPlateProfile(profileId: string): Promise<void> {
    const catalog = this.#profileCatalog;
    const state = sceneStore.getState();
    const plate = this.#activePlate(state);
    const profile = catalog?.profiles.find((item) => item.id === profileId);
    if (!catalog || !plate || !profile) return;
    const visual = studioBuildPlateVisual(profile);
    sceneStore.dispatch({
      type: "set_plate_profile",
      plateId: plate.id,
      profileId: profile.id,
      widthMm: visual.widthMm,
      depthMm: visual.depthMm,
    });
    try {
      const selection = await this.#profileApi.saveSelection({
        ...catalog.selection,
        build_plate_profile_id: profile.id,
      });
      this.#profileCatalog = { ...catalog, selection };
      this.#status = `Druckplatte gewählt: ${profile.name}`;
      this.#error = "";
    } catch (error) {
      this.#error = `Druckplattenauswahl konnte nicht gespeichert werden: ${error instanceof Error ? error.message : String(error)}`;
    }
    this.#render(sceneStore.getState());
  }

  #addPlate(): void {
    const state = sceneStore.getState();
    const current = this.#activePlate(state);
    const next = defaultPlate(plateId(), `Druckplatte ${state.plates.length + 1}`, state.plates.length);
    sceneStore.dispatch({
      type: "add_plate",
      plate: {
        ...next,
        buildPlateProfileId: current?.buildPlateProfileId || this.#profileCatalog?.selection.build_plate_profile_id || DEFAULT_PLATE_PROFILE_ID,
        widthMm: current?.widthMm || DEFAULT_PLATE_SIZE,
        depthMm: current?.depthMm || DEFAULT_PLATE_SIZE,
      },
    });
    this.#status = `${next.name} wurde angelegt.`;
  }

  #removeActivePlate(): void {
    const state = sceneStore.getState();
    const plate = this.#activePlate(state);
    if (!plate || state.plates.length <= 1) return;
    for (const object of plate.objects) removeStudioGeometry(object.id);
    sceneStore.dispatch({ type: "remove_plate", plateId: plate.id });
    this.#status = `${plate.name} wurde entfernt.`;
  }

  async #importFiles(files: FileList | readonly File[] | null): Promise<void> {
    const queue = files ? Array.from(files) : [];
    if (!queue.length) return;
    this.#error = "";
    let imported = 0;
    const state = sceneStore.getState();
    const plate = this.#activePlate(state);
    const visual = this.#currentPlateVisual(state);
    if (!plate) return;
    for (const file of queue) {
      if (!file.name.toLowerCase().endsWith(".stl")) {
        this.#error = `${file.name}: Das CAD-Studio erwartet STL-Geometrie.`;
        continue;
      }
      try {
        const geometry = parseStl(await file.arrayBuffer());
        const id = objectId();
        const transform = {
          position: positionCenteredOnPlate(
            geometry,
            { position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
            visual.widthMm,
            visual.depthMm,
          ),
          rotation: [0, 0, 0] as [number, number, number],
          scale: [1, 1, 1] as [number, number, number],
        };
        const object: SceneObject = {
          id,
          assetId: `local:${id}`,
          name: file.name.replace(/\.stl$/i, ""),
          transform,
          visible: true,
          locked: false,
          color: "#38aee8",
        };
        setStudioGeometry(id, { geometry, fileName: file.name });
        sceneStore.dispatch({ type: "add_object", plateId: plate.id, object });
        sceneStore.dispatch({ type: "select", objectIds: [id] });
        this.#transformTools?.setMode("direct");
        imported += 1;
      } catch (error) {
        this.#error = `${file.name}: ${error instanceof Error ? error.message : String(error)}`;
      }
    }
    this.#status = imported
      ? `${imported} Modell${imported === 1 ? "" : "e"} wurde${imported === 1 ? "" : "n"} in ${plate.name} importiert.`
      : "";
    if (this.#fileInput) this.#fileInput.value = "";
    this.#viewport?.frameAll();
    this.#render(sceneStore.getState());
  }

  #render(state: Readonly<SceneState>): void {
    const tree = this.#root.querySelector<HTMLElement>("#tree");
    const inspector = this.#root.querySelector<HTMLElement>("#inspector-details");
    const status = this.#root.querySelector<HTMLElement>("#status");
    const platePanel = this.#root.querySelector<HTMLElement>("#plate-panel");
    const plateBadge = this.#root.querySelector<HTMLElement>("#plate-badge");
    const coordinateGizmo = this.#root.querySelector<HTMLElement>("#coordinate-gizmo");
    if (!tree || !inspector || !status || !platePanel || !plateBadge || !coordinateGizmo || !this.#viewport) return;
    const plate = this.#activePlate(state);
    const visual = this.#currentPlateVisual(state);
    const plateKey = `${plate?.id}:${visual.id}:${visual.widthMm}:${visual.depthMm}`;
    if (plateKey !== this.#renderedPlateKey) {
      this.#renderedPlateKey = plateKey;
      this.#viewport.setPlate(visual);
    }
    this.#renderPlatePanel(platePanel, state, plate, visual);
    status.className = this.#error ? "status error" : this.#status ? "status" : "";
    status.textContent = this.#error || this.#status;
    status.hidden = !status.textContent;
    const objects = plate?.objects ?? [];
    tree.replaceChildren();
    const heading = document.createElement("h3");
    heading.textContent = `${plate?.name ?? "Druckplatte"} · ${objects.length} Objekt${objects.length === 1 ? "" : "e"}`;
    tree.append(heading);
    for (const object of objects) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "row";
      if (state.selectedObjectIds.includes(object.id)) row.setAttribute("selected", "");
      const label = document.createElement("span");
      label.textContent = object.name;
      const geometry = getStudioGeometry(object.id)?.geometry;
      const meta = document.createElement("small");
      meta.textContent = geometry ? `${geometry.triangleCount.toLocaleString("de-DE")} Dreiecke` : "Geometrie fehlt";
      row.append(label, meta);
      row.addEventListener("click", () => {
        sceneStore.dispatch({ type: "select", objectIds: [object.id] });
        this.#transformTools?.setMode("direct");
      });
      tree.append(row);
    }
    const instances: MeshInstance[] = objects.flatMap((object) => {
      const record = getStudioGeometry(object.id);
      if (!record) return [];
      return [{
        id: object.id,
        name: object.name,
        geometry: record.geometry,
        position: [...object.transform.position] as [number, number, number],
        rotation: [...object.transform.rotation] as [number, number, number],
        scale: [...object.transform.scale] as [number, number, number],
        color: object.color || "#38aee8",
        visible: object.visible,
      }];
    });
    this.#viewport.setInstances(instances);
    this.#viewport.setSelected(state.selectedObjectIds);
    const selected = objects.find((item) => state.selectedObjectIds.includes(item.id)) ?? null;
    this.#renderInspector(inspector, selected, visual);
    this.#renderPlateBadge(plateBadge, plate, visual);
    this.#renderCoordinates(coordinateGizmo, selected);
  }

  #renderPlatePanel(
    host: HTMLElement,
    state: Readonly<SceneState>,
    activePlate: PlateState | null,
    visual: StudioBuildPlateVisual,
  ): void {
    const profiles = buildPlateProfiles(this.#profileCatalog?.profiles ?? []);
    host.innerHTML = `<h3>Druckplatten</h3><div class="plate-tabs">${state.plates.map((plate, index) => `<button type="button" class="plate-tab ${plate.id === activePlate?.id ? "active" : ""}" data-plate="${plate.id}" title="${plate.name}">${index + 1}</button>`).join("")}</div><div class="plate-actions"><select id="plate-profile" ${profiles.length ? "" : "disabled"}>${profiles.length ? profiles.map((profile) => `<option value="${profile.id}" ${profile.id === visual.id ? "selected" : ""}>${profile.name}</option>`).join("") : '<option>Profile werden geladen …</option>'}</select><button type="button" id="add-plate" title="Weitere Druckplatte">＋</button><button type="button" id="remove-plate" title="Aktive Druckplatte entfernen" ${state.plates.length > 1 ? "" : "disabled"}>−</button></div><div class="plate-preview"><span class="plate-swatch" style="--plate-base:${visual.baseColor};--plate-grid:${visual.majorGridColor}"></span><span><strong>${visual.shortName}</strong><small>${visual.widthMm} × ${visual.depthMm} mm · 10-mm-Raster</small></span></div>`;
    host.querySelectorAll<HTMLButtonElement>("[data-plate]").forEach((button) => button.addEventListener("click", () => {
      sceneStore.dispatch({ type: "activate_plate", plateId: button.dataset.plate || "" });
      this.#viewport?.frameAll();
    }));
    host.querySelector<HTMLSelectElement>("#plate-profile")?.addEventListener("change", (event) => {
      void this.#setBuildPlateProfile((event.currentTarget as HTMLSelectElement).value);
    });
    host.querySelector<HTMLButtonElement>("#add-plate")?.addEventListener("click", () => this.#addPlate());
    host.querySelector<HTMLButtonElement>("#remove-plate")?.addEventListener("click", () => this.#removeActivePlate());
  }

  #renderPlateBadge(host: HTMLElement, plate: PlateState | null, visual: StudioBuildPlateVisual): void {
    host.style.setProperty("--plate-accent", visual.accentColor);
    host.innerHTML = `<strong>${plate?.name ?? "Druckplatte"} · ${visual.shortName}</strong><span>${visual.widthMm} × ${visual.depthMm} mm · Nullpunkt vorne links · ${visual.footer}</span>`;
  }

  #renderCoordinates(host: HTMLElement, object: SceneObject | null): void {
    const position = object?.transform.position ?? [0, 0, 0];
    host.innerHTML = `<div class="coordinate-title">${object ? object.name : "Koordinaten / Nullpunkt"}</div><div class="axis-row x"><span class="axis-arrow">→</span><b>X</b><code>${fixed(position[0])} mm</code></div><div class="axis-row y"><span class="axis-arrow">↑</span><b>Y</b><code>${fixed(position[1])} mm</code></div><div class="axis-row z"><span class="axis-arrow">↗</span><b>Z</b><code>${fixed(position[2])} mm</code></div>`;
  }

  #renderInspector(host: HTMLElement, object: SceneObject | null, plate: StudioBuildPlateVisual): void {
    host.replaceChildren();
    if (!object) {
      const heading = document.createElement("h2");
      heading.textContent = "Keine Auswahl";
      const text = document.createElement("p");
      text.textContent = `Aktive Platte: ${plate.name} (${plate.widthMm} × ${plate.depthMm} mm). Ein Modell importieren und links auswählen.`;
      host.append(heading, text);
      return;
    }
    const record = getStudioGeometry(object.id);
    const heading = document.createElement("h2");
    heading.textContent = object.name;
    const source = document.createElement("p");
    source.textContent = record?.fileName ?? object.assetId;
    host.append(heading, source);
    for (const [group, values] of [
      ["Position", object.transform.position],
      ["Drehung", object.transform.rotation],
      ["Skalierung", object.transform.scale],
    ] as const) {
      const title = document.createElement("h3");
      title.textContent = group;
      host.append(title);
      ["X", "Y", "Z"].forEach((axis, index) => {
        const row = document.createElement("label");
        row.className = "field";
        const text = document.createElement("span");
        text.textContent = `${axis}${group === "Position" ? " mm" : group === "Drehung" ? " °" : ""}`;
        const input = document.createElement("input");
        input.type = "number";
        input.step = group === "Skalierung" ? "0.01" : "0.1";
        input.value = Number(values[index]).toFixed(group === "Skalierung" ? 3 : 2);
        input.addEventListener("change", () => this.#setTransformValue(object, group, index, Number(input.value)));
        row.append(text, input);
        host.append(row);
      });
    }
    const colorRow = document.createElement("label");
    colorRow.className = "color-row";
    const colorText = document.createElement("span");
    colorText.textContent = "Objektfarbe";
    const color = document.createElement("input");
    color.type = "color";
    color.value = object.color || "#38aee8";
    color.addEventListener("input", () => sceneStore.dispatch({
      type: "set_color",
      plateId: sceneStore.getState().activePlateId || DEFAULT_PLATE_ID,
      objectId: object.id,
      color: color.value,
    }));
    colorRow.append(colorText, color);
    host.append(colorRow);
    if (record) {
      const stats = document.createElement("div");
      stats.className = "stats";
      const size = [0, 1, 2].map((index) => (record.geometry.boundsMax[index]! - record.geometry.boundsMin[index]!).toFixed(2));
      stats.textContent = `Dreiecke: ${record.geometry.triangleCount.toLocaleString("de-DE")} · Rohgröße: ${size.join(" × ")} mm`;
      host.append(stats);
    }
    const help = document.createElement("div");
    help.className = "help";
    help.textContent = "Strg+E: Aktive Druckplatte im Slicer öffnen · Strg+D: Duplizieren · Entf: Löschen · G/R/S: Werkzeug · Esc: Direktsteuerung";
    host.append(help);
  }

  #setTransformValue(
    object: SceneObject,
    group: "Position" | "Drehung" | "Skalierung",
    index: number,
    value: number,
  ): void {
    if (!Number.isFinite(value)) return;
    const position = [...object.transform.position] as [number, number, number];
    const rotation = [...object.transform.rotation] as [number, number, number];
    const scale = [...object.transform.scale] as [number, number, number];
    if (group === "Position") position[index] = value;
    if (group === "Drehung") rotation[index] = value;
    if (group === "Skalierung") scale[index] = Math.max(0.001, value);
    sceneStore.dispatch({
      type: "set_transform",
      plateId: sceneStore.getState().activePlateId || DEFAULT_PLATE_ID,
      objectId: object.id,
      transform: { position, rotation, scale },
    });
  }

  #selectedContext(): { plateId: string; object: SceneObject } | null {
    const state = sceneStore.getState();
    const plate = this.#activePlate(state);
    const object = plate?.objects.find((item) => state.selectedObjectIds.includes(item.id));
    return plate && object ? { plateId: plate.id, object } : null;
  }

  #deleteSelected(): void {
    const state = sceneStore.getState();
    const plateIdValue = state.activePlateId || DEFAULT_PLATE_ID;
    for (const id of state.selectedObjectIds) {
      sceneStore.dispatch({ type: "remove_object", plateId: plateIdValue, objectId: id });
      removeStudioGeometry(id);
    }
    sceneStore.dispatch({ type: "select", objectIds: [] });
    this.#transformTools?.setMode("direct");
  }

  #centerSelected(): void {
    const selected = this.#selectedContext();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const visual = this.#currentPlateVisual(sceneStore.getState());
    const position = positionCenteredOnPlate(record.geometry, selected.object.transform, visual.widthMm, visual.depthMm);
    sceneStore.dispatch({
      type: "set_transform",
      plateId: selected.plateId,
      objectId: selected.object.id,
      transform: { ...selected.object.transform, position },
    });
  }

  #placeSelectedOnBed(): void {
    const selected = this.#selectedContext();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const position = positionOnBed(record.geometry, selected.object.transform);
    sceneStore.dispatch({
      type: "set_transform",
      plateId: selected.plateId,
      objectId: selected.object.id,
      transform: { ...selected.object.transform, position },
    });
  }

  #layFlatSelected(): void {
    const selected = this.#selectedContext();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const visual = this.#currentPlateVisual(sceneStore.getState());
    const rotation = bestFlatRotation(record.geometry, selected.object.transform.scale);
    const provisional = { ...selected.object.transform, rotation };
    const position = positionCenteredOnPlate(record.geometry, provisional, visual.widthMm, visual.depthMm);
    sceneStore.dispatch({
      type: "set_transform",
      plateId: selected.plateId,
      objectId: selected.object.id,
      transform: { ...provisional, position },
    });
  }

  #duplicateSelected(): void {
    const selected = this.#selectedContext();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const id = objectId();
    const duplicate: SceneObject = {
      ...selected.object,
      id,
      name: `${selected.object.name} Kopie`,
      assetId: `local:${id}`,
      transform: {
        ...selected.object.transform,
        position: [
          selected.object.transform.position[0] + 10,
          selected.object.transform.position[1] + 10,
          selected.object.transform.position[2],
        ],
      },
    };
    setStudioGeometry(id, record);
    sceneStore.dispatch({ type: "add_object", plateId: selected.plateId, object: duplicate });
    sceneStore.dispatch({ type: "select", objectIds: [id] });
    this.#transformTools?.setMode("direct");
  }

  #exportToSlicer(): void {
    const state = sceneStore.getState();
    const plate = this.#activePlate(state);
    const meshes: ExportMesh[] = (plate?.objects ?? []).flatMap((object) => {
      const record = getStudioGeometry(object.id);
      if (!record || !object.visible) return [];
      return [{ name: object.name, geometry: record.geometry, transform: object.transform }];
    });
    try {
      const buffer = exportBinaryStl(meshes, V6_BRANDING.cadSceneLabel);
      const file = new File([buffer], safeProjectFileName(plate?.name ?? "Druckplatte"), { type: "model/stl" });
      queueWorkspaceFile("slicer", file);
      this.#status = `${meshes.length} CAD-Objekt${meshes.length === 1 ? "" : "e"} wurde${meshes.length === 1 ? "" : "n"} von ${plate?.name ?? "der Druckplatte"} an den Slicer übergeben.`;
      this.#error = "";
      this.dispatchEvent(new CustomEvent("gallery-open-slicer", {
        bubbles: true,
        composed: true,
        detail: {
          fileName: file.name,
          objectCount: meshes.length,
          plateId: plate?.id,
          buildPlateProfileId: plate?.buildPlateProfileId,
        },
      }));
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#render(state);
    }
  }
}

if (!customElements.get("ultimate-3d-studio-workspace")) {
  customElements.define("ultimate-3d-studio-workspace", Ultimate3DStudioWorkspaceV2);
}
