import { STUDIO_BRANDING } from "./branding.js";
import {
  bestFlatRotation,
  exportBinaryStl,
  positionCenteredOnPlate,
  positionOnBed,
  type ExportMesh,
} from "./mesh-export.js";
import { ProfileApi, type StudioProfileCatalog } from "./profile-api.js";
import { sceneStore, type PlateState, type SceneObject, type SceneState, type SceneTransform } from "./scene-store.js";
import { buildPlateProfiles, studioBuildPlateVisual, type StudioBuildPlateVisual } from "./studio-build-plates.js";
import { StudioPlateViewport } from "./studio-plate-viewport.js";
import { getStudioGeometry, removeStudioGeometry, setStudioGeometry } from "./studio-session.js";
import { StudioTransformTools, type StudioTransformInteractionState } from "./studio-transform-tools.js";
import { parseStl, type MeshInstance } from "./webgl-studio-viewport.js";
import { consumeWorkspaceFiles, queueWorkspaceFile } from "./workspace-file-handoff.js";

const DEFAULT_PLATE_ID = "plate-1";
const DEFAULT_PLATE_PROFILE_ID = "build-plate-smooth-pei";
const DEFAULT_PLATE_SIZE = 256;

type ObjectDrag = Readonly<{
  pointerId: number;
  startX: number;
  startY: number;
  plateId: string;
  objectId: string;
  initial: SceneTransform;
  interaction: StudioTransformInteractionState;
}>;

function objectId(): string { return `object-${crypto.randomUUID()}`; }
function plateId(): string { return `plate-${crypto.randomUUID()}`; }
function fixed(value: number): string { return Number.isFinite(value) ? value.toFixed(2) : "0.00"; }
function snap(value: number, step: number): number { return step > 0 ? Math.round(value / step) * step : value; }

function safeProjectFileName(value: string): string {
  const cleaned = value.replace(/[\\/:*?"<>|]+/g, "_").trim();
  return `${cleaned || "3D-Studio-Projekt"}.stl`;
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

export class Ultimate3DStudioWorkspaceV3 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #profileApi = new ProfileApi();
  #profileCatalog: StudioProfileCatalog | null = null;
  #unsubscribe: (() => void) | null = null;
  #viewport: StudioPlateViewport | null = null;
  #fileInput: HTMLInputElement | null = null;
  #transformTools: StudioTransformTools | null = null;
  #objectDrag: ObjectDrag | null = null;
  #renderedPlateKey = "";
  #status = "";
  #error = "";

  connectedCallback(): void {
    if (this.#unsubscribe) return;
    if (!sceneStore.getState().plates.length) sceneStore.dispatch({ type: "load", state: defaultScene() });
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
    this.#objectDrag = null;
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
      this.#render(sceneStore.getState());
      return;
    }
    if (key === "g" || key === "r" || key === "s") {
      event.preventDefault();
      this.#transformTools?.setMode(key === "g" ? "translate" : key === "r" ? "rotate" : "scale");
      this.#render(sceneStore.getState());
      return;
    }
    if (key === "x" || key === "y" || key === "z") {
      event.preventDefault();
      this.#transformTools?.setAxis(key);
      this.#render(sceneStore.getState());
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
      const profiles = buildPlateProfiles(this.#profileCatalog.profiles);
      const selectedId = plate?.buildPlateProfileId
        || this.#profileCatalog.selection.build_plate_profile_id
        || DEFAULT_PLATE_PROFILE_ID;
      const profile = profiles.find((item) => item.id === selectedId) || profiles[0];
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
      :host{display:block;min-height:720px;color:#edf6ff;outline:none}*{box-sizing:border-box}.layout{display:grid;grid-template-columns:300px minmax(0,1fr) 330px;min-height:720px;background:#08101a}.panel{border-color:#24364b;background:#0c1622}.left{border-right:1px solid #24364b;overflow:auto}.right{border-left:1px solid #24364b;padding:14px;overflow:auto}.toolbar{display:grid;gap:8px;padding:10px;border-bottom:1px solid #24364b;background:#0f1b29}.toolbar-row{display:flex;flex-wrap:wrap;gap:7px}.toolbar-row+.toolbar-row{padding-top:7px;border-top:1px solid #26394f}button{border:1px solid #31506e;border-radius:8px;padding:8px 10px;background:#14263a;color:#edf6ff;cursor:pointer;font-weight:650}button:hover{border-color:#36bfff}button.active{border-color:#42c8ff;background:#173b58;box-shadow:inset 0 0 0 1px #42c8ff55}.primary{border-color:#35a9e8;background:#176187}.danger{border-color:#7c3441;background:#321820}button:disabled{opacity:.4;cursor:not-allowed}.plate-panel{padding:10px;border-bottom:1px solid #24364b;background:#0a141f}.plate-panel h3{margin:0 0 8px;font-size:12px;color:#94abc2;text-transform:uppercase;letter-spacing:.08em}.plate-tabs{display:flex;gap:5px;overflow:auto;padding-bottom:7px}.plate-tab{min-width:42px;padding:7px 9px}.plate-tab.active{border-color:#49c8ff;background:#163d58}.plate-actions{display:grid;grid-template-columns:1fr auto auto;gap:6px}.plate-actions select{min-width:0;width:100%;padding:8px;border:1px solid #31506e;border-radius:8px;background:#09131f;color:#fff}.plate-preview{display:grid;grid-template-columns:50px 1fr;gap:9px;align-items:center;margin-top:8px;padding:8px;border:1px solid #2d455d;border-radius:8px;background:#101b28}.plate-swatch{width:50px;height:43px;border:1px solid #ffffff42;border-radius:5px;background-color:var(--plate-base);background-image:linear-gradient(var(--plate-grid) 1px,transparent 1px),linear-gradient(90deg,var(--plate-grid) 1px,transparent 1px);background-size:8px 8px}.plate-preview strong,.plate-preview small{display:block}.plate-preview small{color:#8ca1b8;margin-top:2px}.tree{padding:10px;display:grid;gap:6px;overflow:auto;max-height:460px}.tree h3{margin:4px 0 8px;font-size:13px;color:#94abc2;text-transform:uppercase}.row{width:100%;display:grid;grid-template-columns:1fr auto;text-align:left;gap:8px;align-items:center}.row[selected]{border-color:#ffad42;background:#2b251a}.row small{color:#8ca1b8}.status{margin:10px;padding:9px;border:1px solid #2c684b;border-radius:8px;background:#10261b;color:#92e7b4;font-size:12px}.status.error{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}.viewport{position:relative;min-width:0;overflow:hidden;background:#050a10}canvas{display:block;width:100%;height:100%;min-height:720px;touch-action:none;cursor:grab;user-select:none}canvas[object-tool]{cursor:crosshair}canvas[dragging]{cursor:grabbing}.help-overlay{position:absolute;right:14px;bottom:14px;max-width:340px;padding:8px 10px;border:1px solid #2b4967;border-radius:8px;background:#09121dcc;color:#8fb0ce;font-size:12px;pointer-events:none}.plate-badge{position:absolute;left:14px;top:14px;min-width:230px;padding:9px 11px;border:1px solid var(--plate-accent,#45bdf5);border-radius:9px;background:#09121de8;pointer-events:none}.plate-badge strong,.plate-badge span{display:block}.plate-badge span{margin-top:3px;color:#9db2c7;font-size:11px}.coordinate-gizmo{position:absolute;left:14px;bottom:14px;width:205px;padding:9px;border:1px solid #314a62;border-radius:9px;background:#09121de8;pointer-events:none}.coordinate-title{margin-bottom:6px;color:#9db2c7;font-size:10px;text-transform:uppercase}.axis-row{display:grid;grid-template-columns:32px 24px 1fr;gap:7px;align-items:center;margin:3px 0}.axis-row.x{color:#ef5350}.axis-row.y{color:#66bb6a}.axis-row.z{color:#42a5f5}.axis-row code{color:#edf6ff}.drop{position:absolute;inset:18px;display:none;place-items:center;border:2px dashed #40c7ff;border-radius:16px;background:#0c1d2ed9;font-size:22px;font-weight:700;z-index:5}.viewport[file-drag] .drop{display:grid}.right h2{margin:0 0 6px}.right p{color:#91a5bb}.field{display:grid;grid-template-columns:80px 1fr;gap:8px;align-items:center;margin:8px 0}.field input{width:100%;padding:7px;border:1px solid #2d4662;border-radius:7px;background:#09121c;color:#fff}.color-row{display:grid;grid-template-columns:1fr 54px;gap:8px;align-items:center;margin:12px 0}.color-row input{width:54px;height:36px}.stats{margin-top:16px;padding-top:12px;border-top:1px solid #26394f;color:#9cb1c7;font-size:12px}.help{margin-top:10px;color:#71869c;font-size:11px}@media(max-width:1100px){.layout{grid-template-columns:250px minmax(0,1fr)}.right{display:none}}@media(max-width:760px){.layout{grid-template-columns:1fr}.left{display:none}canvas{min-height:620px}}
    `;
    const layout = document.createElement("section");
    layout.className = "layout";

    const left = document.createElement("aside");
    left.className = "panel left";
    const toolbar = document.createElement("div");
    toolbar.className = "toolbar";
    const fileRow = document.createElement("div");
    fileRow.className = "toolbar-row";
    fileRow.append(
      this.#button("STL importieren", () => this.#fileInput?.click()),
      this.#button("Im Slicer öffnen", () => this.#exportToSlicer(), "primary"),
      this.#button("Alles einpassen", () => this.#viewport?.frameAll()),
    );
    const modeRow = document.createElement("div");
    modeRow.className = "toolbar-row";
    modeRow.id = "mode-row";
    modeRow.append(
      this.#modeButton("Ansicht", "direct"),
      this.#modeButton("Verschieben", "translate"),
      this.#modeButton("Drehen", "rotate"),
      this.#modeButton("Skalieren", "scale"),
    );
    const objectRow = document.createElement("div");
    objectRow.className = "toolbar-row";
    objectRow.append(
      this.#button("Duplizieren", () => this.#duplicateSelected()),
      this.#button("Zentrieren", () => this.#centerSelected()),
      this.#button("Flach legen", () => this.#layFlatSelected()),
      this.#button("Auf Druckbett", () => this.#placeSelectedOnBed()),
      this.#button("Löschen", () => this.#deleteSelected(), "danger"),
    );
    toolbar.append(fileRow, modeRow, objectRow);
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
    const canvas = document.createElement("canvas");
    this.#bindObjectTools(canvas);
    const drop = document.createElement("div");
    drop.className = "drop";
    drop.textContent = "STL hier ablegen";
    const plateBadge = document.createElement("div");
    plateBadge.className = "plate-badge";
    plateBadge.id = "plate-badge";
    const coordinates = document.createElement("div");
    coordinates.className = "coordinate-gizmo";
    coordinates.id = "coordinate-gizmo";
    const help = document.createElement("div");
    help.className = "help-overlay";
    help.id = "mouse-help";
    viewportHost.append(canvas, drop, plateBadge, coordinates, help);

    const right = document.createElement("aside");
    right.className = "panel right";
    const inspector = document.createElement("div");
    inspector.id = "inspector-details";
    const transformTools = document.createElement("studio-transform-tools") as StudioTransformTools;
    transformTools.addEventListener("studio-place-on-bed", () => this.#placeSelectedOnBed());
    this.#transformTools = transformTools;
    right.append(inspector, transformTools);

    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".stl,model/stl,application/sla";
    input.multiple = true;
    input.hidden = true;
    input.addEventListener("change", () => void this.#importFiles(input.files));
    this.#fileInput = input;

    viewportHost.addEventListener("dragenter", (event) => { event.preventDefault(); viewportHost.setAttribute("file-drag", ""); });
    viewportHost.addEventListener("dragover", (event) => event.preventDefault());
    viewportHost.addEventListener("dragleave", (event) => { if (event.target === viewportHost) viewportHost.removeAttribute("file-drag"); });
    viewportHost.addEventListener("drop", (event) => {
      event.preventDefault();
      viewportHost.removeAttribute("file-drag");
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

  #modeButton(label: string, mode: StudioTransformInteractionState["mode"]): HTMLButtonElement {
    const button = this.#button(label, () => {
      this.#transformTools?.setMode(mode);
      this.#render(sceneStore.getState());
    });
    button.dataset.mode = mode;
    return button;
  }

  #bindObjectTools(canvas: HTMLCanvasElement): void {
    canvas.addEventListener("pointerdown", (event) => {
      const interaction = this.#transformTools?.getInteractionState();
      const selected = this.#selectedContext();
      if (event.button !== 0 || !interaction || interaction.mode === "direct" || !selected) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      this.#objectDrag = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        plateId: selected.plateId,
        objectId: selected.object.id,
        initial: selected.object.transform,
        interaction,
      };
      canvas.setAttribute("dragging", "");
      try { canvas.setPointerCapture(event.pointerId); } catch (_error) {}
    }, { capture: true });
    canvas.addEventListener("pointermove", (event) => {
      const drag = this.#objectDrag;
      if (!drag || drag.pointerId !== event.pointerId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      this.#applyObjectDrag(drag, event.clientX - drag.startX, event.clientY - drag.startY, event.shiftKey);
    }, { capture: true });
    const finish = (event: PointerEvent): void => {
      if (this.#objectDrag?.pointerId !== event.pointerId) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      this.#objectDrag = null;
      canvas.removeAttribute("dragging");
      try { canvas.releasePointerCapture(event.pointerId); } catch (_error) {}
    };
    canvas.addEventListener("pointerup", finish, { capture: true });
    canvas.addEventListener("pointercancel", finish, { capture: true });
  }

  #applyObjectDrag(drag: ObjectDrag, dx: number, dy: number, uniformScale: boolean): void {
    const position = [...drag.initial.position] as [number, number, number];
    const rotation = [...drag.initial.rotation] as [number, number, number];
    const scale = [...drag.initial.scale] as [number, number, number];
    const axisIndex = drag.interaction.axis === "x" ? 0 : drag.interaction.axis === "y" ? 1 : 2;
    const primary = drag.interaction.axis === "y" || drag.interaction.axis === "z" ? -dy : dx;
    if (drag.interaction.mode === "translate") {
      position[axisIndex] = snap(position[axisIndex] + primary * 0.35, drag.interaction.snap);
    } else if (drag.interaction.mode === "rotate") {
      rotation[axisIndex] = snap(rotation[axisIndex] + primary * 0.32, drag.interaction.snap);
    } else if (drag.interaction.mode === "scale") {
      const next = Math.max(0.001, snap(scale[axisIndex] + primary * 0.005, drag.interaction.snap));
      if (uniformScale) scale[0] = scale[1] = scale[2] = next;
      else scale[axisIndex] = next;
    }
    sceneStore.dispatch({
      type: "set_transform",
      plateId: drag.plateId,
      objectId: drag.objectId,
      transform: { position, rotation, scale },
    });
  }

  #activePlate(state: Readonly<SceneState>): PlateState | null {
    return state.plates.find((plate) => plate.id === state.activePlateId) ?? state.plates[0] ?? null;
  }

  #currentPlateVisual(state: Readonly<SceneState>): StudioBuildPlateVisual {
    const plate = this.#activePlate(state);
    const profiles = buildPlateProfiles(this.#profileCatalog?.profiles ?? []);
    const profileId = plate?.buildPlateProfileId
      || this.#profileCatalog?.selection.build_plate_profile_id
      || DEFAULT_PLATE_PROFILE_ID;
    const profile = profiles.find((item) => item.id === profileId) || profiles[0];
    const visual = studioBuildPlateVisual(profile);
    return {
      ...visual,
      widthMm: plate?.widthMm || visual.widthMm,
      depthMm: plate?.depthMm || visual.depthMm,
    };
  }

  async #setBuildPlateProfile(profileIdValue: string): Promise<void> {
    const state = sceneStore.getState();
    const plate = this.#activePlate(state);
    const profiles = buildPlateProfiles(this.#profileCatalog?.profiles ?? []);
    const profile = profiles.find((item) => item.id === profileIdValue);
    if (!plate || !profile) return;
    const visual = studioBuildPlateVisual(profile);
    sceneStore.dispatch({ type: "set_plate_profile", plateId: plate.id, profileId: profile.id, widthMm: visual.widthMm, depthMm: visual.depthMm });
    if (this.#profileCatalog && this.#profileCatalog.profiles.some((item) => item.id === profile.id)) {
      try {
        const selection = await this.#profileApi.saveSelection({
          ...this.#profileCatalog.selection,
          build_plate_profile_id: profile.id,
        });
        this.#profileCatalog = { ...this.#profileCatalog, selection };
      } catch (error) {
        this.#error = `Druckplattenauswahl konnte nicht gespeichert werden: ${error instanceof Error ? error.message : String(error)}`;
      }
    }
    this.#status = `Druckplatte gewählt: ${profile.name}`;
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
        buildPlateProfileId: current?.buildPlateProfileId || DEFAULT_PLATE_PROFILE_ID,
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
        const transform: SceneTransform = {
          position: positionCenteredOnPlate(geometry, { position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] }, visual.widthMm, visual.depthMm),
          rotation: [0, 0, 0],
          scale: [1, 1, 1],
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
        imported += 1;
      } catch (error) {
        this.#error = `${file.name}: ${error instanceof Error ? error.message : String(error)}`;
      }
    }
    this.#status = imported ? `${imported} Modell${imported === 1 ? "" : "e"} in ${plate.name} importiert.` : "";
    if (this.#fileInput) this.#fileInput.value = "";
    this.#viewport?.frameAll();
    this.#render(sceneStore.getState());
  }

  #render(state: Readonly<SceneState>): void {
    const tree = this.#root.querySelector<HTMLElement>("#tree");
    const inspector = this.#root.querySelector<HTMLElement>("#inspector-details");
    const status = this.#root.querySelector<HTMLElement>("#status");
    const platePanel = this.#root.querySelector<HTMLElement>("#plate-panel");
    const badge = this.#root.querySelector<HTMLElement>("#plate-badge");
    const coordinates = this.#root.querySelector<HTMLElement>("#coordinate-gizmo");
    const mouseHelp = this.#root.querySelector<HTMLElement>("#mouse-help");
    const canvas = this.#root.querySelector<HTMLCanvasElement>("canvas");
    if (!tree || !inspector || !status || !platePanel || !badge || !coordinates || !mouseHelp || !canvas || !this.#viewport) return;
    const plate = this.#activePlate(state);
    const visual = this.#currentPlateVisual(state);
    const interaction = this.#transformTools?.getInteractionState() ?? { mode: "direct", axis: "x", snap: 1 };
    const plateKey = `${plate?.id}:${visual.id}:${visual.widthMm}:${visual.depthMm}`;
    if (plateKey !== this.#renderedPlateKey) {
      this.#renderedPlateKey = plateKey;
      this.#viewport.setPlate(visual);
    }
    canvas.toggleAttribute("object-tool", interaction.mode !== "direct");
    mouseHelp.textContent = interaction.mode === "direct"
      ? "Ansicht: links drehen · rechts verschieben · Mausrad zoomen"
      : `${interaction.mode === "translate" ? "Verschieben" : interaction.mode === "rotate" ? "Drehen" : "Skalieren"} auf ${interaction.axis.toUpperCase()}: links ziehen${interaction.mode === "scale" ? " · Umschalt = gleichmäßig" : ""} · rechts bleibt Ansicht`;
    this.#root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((button) => button.classList.toggle("active", button.dataset.mode === interaction.mode));
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
      const meta = document.createElement("small");
      const geometry = getStudioGeometry(object.id)?.geometry;
      meta.textContent = geometry ? `${geometry.triangleCount.toLocaleString("de-DE")} Dreiecke` : "Geometrie fehlt";
      row.append(label, meta);
      row.addEventListener("click", () => sceneStore.dispatch({ type: "select", objectIds: [object.id] }));
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
    badge.style.setProperty("--plate-accent", visual.accentColor);
    badge.innerHTML = `<strong>${plate?.name ?? "Druckplatte"} · ${visual.shortName}</strong><span>${visual.widthMm} × ${visual.depthMm} mm · ${visual.footer}</span>`;
    this.#renderCoordinates(coordinates, selected);
  }

  #renderPlatePanel(host: HTMLElement, state: Readonly<SceneState>, activePlate: PlateState | null, visual: StudioBuildPlateVisual): void {
    const profiles = buildPlateProfiles(this.#profileCatalog?.profiles ?? []);
    host.innerHTML = `<h3>Druckplatten</h3><div class="plate-tabs">${state.plates.map((plate, index) => `<button type="button" class="plate-tab ${plate.id === activePlate?.id ? "active" : ""}" data-plate="${plate.id}" title="${plate.name}">${index + 1}</button>`).join("")}</div><div class="plate-actions"><select id="plate-profile">${profiles.map((profile) => `<option value="${profile.id}" ${profile.id === visual.id ? "selected" : ""}>${profile.name}</option>`).join("")}</select><button type="button" id="add-plate">＋</button><button type="button" id="remove-plate" ${state.plates.length > 1 ? "" : "disabled"}>−</button></div><div class="plate-preview"><span class="plate-swatch" style="--plate-base:${visual.baseColor};--plate-grid:${visual.majorGridColor}"></span><span><strong>${visual.shortName}</strong><small>${visual.widthMm} × ${visual.depthMm} mm · ${visual.footer}</small></span></div>`;
    host.querySelectorAll<HTMLButtonElement>("[data-plate]").forEach((button) => button.addEventListener("click", () => {
      sceneStore.dispatch({ type: "activate_plate", plateId: button.dataset.plate || "" });
      this.#viewport?.frameAll();
    }));
    host.querySelector<HTMLSelectElement>("#plate-profile")?.addEventListener("change", (event) => void this.#setBuildPlateProfile((event.currentTarget as HTMLSelectElement).value));
    host.querySelector<HTMLButtonElement>("#add-plate")?.addEventListener("click", () => this.#addPlate());
    host.querySelector<HTMLButtonElement>("#remove-plate")?.addEventListener("click", () => this.#removeActivePlate());
  }

  #renderCoordinates(host: HTMLElement, object: SceneObject | null): void {
    const position = object?.transform.position ?? [0, 0, 0];
    host.innerHTML = `<div class="coordinate-title">${object ? object.name : "Koordinaten / Nullpunkt"}</div><div class="axis-row x"><b>X</b><span>→</span><code>${fixed(position[0])} mm</code></div><div class="axis-row y"><b>Y</b><span>↑</span><code>${fixed(position[1])} mm</code></div><div class="axis-row z"><b>Z</b><span>↗</span><code>${fixed(position[2])} mm</code></div>`;
  }

  #renderInspector(host: HTMLElement, object: SceneObject | null, plate: StudioBuildPlateVisual): void {
    host.replaceChildren();
    if (!object) {
      const heading = document.createElement("h2");
      heading.textContent = "Keine Auswahl";
      const text = document.createElement("p");
      text.textContent = `Aktive Platte: ${plate.name}. Modell links auswählen, danach Werkzeug und Achse wählen.`;
      host.append(heading, text);
      return;
    }
    const record = getStudioGeometry(object.id);
    const heading = document.createElement("h2");
    heading.textContent = object.name;
    const source = document.createElement("p");
    source.textContent = record?.fileName ?? object.assetId;
    host.append(heading, source);
    for (const [group, values] of [["Position", object.transform.position], ["Drehung", object.transform.rotation], ["Skalierung", object.transform.scale]] as const) {
      const title = document.createElement("h3");
      title.textContent = group;
      host.append(title);
      ["X", "Y", "Z"].forEach((axis, index) => {
        const row = document.createElement("label");
        row.className = "field";
        const label = document.createElement("span");
        label.textContent = `${axis}${group === "Position" ? " mm" : group === "Drehung" ? " °" : ""}`;
        const input = document.createElement("input");
        input.type = "number";
        input.step = group === "Skalierung" ? "0.01" : "0.1";
        input.value = Number(values[index]).toFixed(group === "Skalierung" ? 3 : 2);
        input.addEventListener("change", () => this.#setTransformValue(object, group, index, Number(input.value)));
        row.append(label, input);
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
    color.addEventListener("input", () => sceneStore.dispatch({ type: "set_color", plateId: sceneStore.getState().activePlateId || DEFAULT_PLATE_ID, objectId: object.id, color: color.value }));
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
    help.textContent = "G/R/S wählen Werkzeug · X/Y/Z wählen Achse · Umschalt beim Skalieren = gleichmäßig · Esc = Ansicht";
    host.append(help);
  }

  #setTransformValue(object: SceneObject, group: "Position" | "Drehung" | "Skalierung", index: number, value: number): void {
    if (!Number.isFinite(value)) return;
    const position = [...object.transform.position] as [number, number, number];
    const rotation = [...object.transform.rotation] as [number, number, number];
    const scale = [...object.transform.scale] as [number, number, number];
    if (group === "Position") position[index] = value;
    if (group === "Drehung") rotation[index] = value;
    if (group === "Skalierung") scale[index] = Math.max(0.001, value);
    sceneStore.dispatch({ type: "set_transform", plateId: sceneStore.getState().activePlateId || DEFAULT_PLATE_ID, objectId: object.id, transform: { position, rotation, scale } });
  }

  #selectedContext(): { plateId: string; object: SceneObject } | null {
    const state = sceneStore.getState();
    const plate = this.#activePlate(state);
    const object = plate?.objects.find((item) => state.selectedObjectIds.includes(item.id));
    return plate && object ? { plateId: plate.id, object } : null;
  }

  #deleteSelected(): void {
    const state = sceneStore.getState();
    const activePlateId = state.activePlateId || DEFAULT_PLATE_ID;
    for (const id of state.selectedObjectIds) {
      sceneStore.dispatch({ type: "remove_object", plateId: activePlateId, objectId: id });
      removeStudioGeometry(id);
    }
    sceneStore.dispatch({ type: "select", objectIds: [] });
  }

  #centerSelected(): void {
    const selected = this.#selectedContext();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const visual = this.#currentPlateVisual(sceneStore.getState());
    const position = positionCenteredOnPlate(record.geometry, selected.object.transform, visual.widthMm, visual.depthMm);
    sceneStore.dispatch({ type: "set_transform", plateId: selected.plateId, objectId: selected.object.id, transform: { ...selected.object.transform, position } });
  }

  #placeSelectedOnBed(): void {
    const selected = this.#selectedContext();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const position = positionOnBed(record.geometry, selected.object.transform);
    sceneStore.dispatch({ type: "set_transform", plateId: selected.plateId, objectId: selected.object.id, transform: { ...selected.object.transform, position } });
  }

  #layFlatSelected(): void {
    const selected = this.#selectedContext();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const visual = this.#currentPlateVisual(sceneStore.getState());
    const rotation = bestFlatRotation(record.geometry, selected.object.transform.scale);
    const provisional = { ...selected.object.transform, rotation };
    const position = positionCenteredOnPlate(record.geometry, provisional, visual.widthMm, visual.depthMm);
    sceneStore.dispatch({ type: "set_transform", plateId: selected.plateId, objectId: selected.object.id, transform: { ...provisional, position } });
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
        position: [selected.object.transform.position[0] + 10, selected.object.transform.position[1] + 10, selected.object.transform.position[2]],
      },
    };
    setStudioGeometry(id, record);
    sceneStore.dispatch({ type: "add_object", plateId: selected.plateId, object: duplicate });
    sceneStore.dispatch({ type: "select", objectIds: [id] });
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
      const buffer = exportBinaryStl(meshes, STUDIO_BRANDING.cadSceneLabel);
      const file = new File([buffer], safeProjectFileName(plate?.name ?? "Druckplatte"), { type: "model/stl" });
      queueWorkspaceFile("slicer", file);
      this.#status = `${meshes.length} CAD-Objekt${meshes.length === 1 ? "" : "e"} von ${plate?.name ?? "der Druckplatte"} an den Slicer übergeben.`;
      this.#error = "";
      this.dispatchEvent(new CustomEvent("gallery-open-slicer", {
        bubbles: true,
        composed: true,
        detail: { fileName: file.name, objectCount: meshes.length, plateId: plate?.id, buildPlateProfileId: plate?.buildPlateProfileId },
      }));
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#render(state);
    }
  }
}

if (!customElements.get("ultimate-3d-studio-workspace")) {
  customElements.define("ultimate-3d-studio-workspace", Ultimate3DStudioWorkspaceV3);
}
