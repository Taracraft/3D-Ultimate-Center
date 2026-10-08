import "./studio-workspace-v3.js";
import "./studio-context-menu.js";
import { bestFlatRotation, positionCenteredOnPlate, positionOnBed } from "./mesh-export.js";
import { createPrimitiveGeometry, type PrimitiveKind } from "./primitive-geometry.js";
import { ProfileApi, type StudioProfileCatalog } from "./profile-api.js";
import { sceneStore, type PlateState, type SceneObject, type SceneTransform } from "./scene-store.js";
import { getStudioGeometry, removeStudioGeometry, setStudioGeometry } from "./studio-session.js";
import type { StudioContextMenu, StudioContextMenuItem } from "./studio-context-menu.js";
import { parseStl } from "./webgl-studio-viewport.js";

const LABELS: Record<PrimitiveKind, string> = {
  cube: "Würfel",
  cylinder: "Zylinder",
  sphere: "Kugel",
  cone: "Kegel",
  torus: "Ring",
  plate: "Platte",
  "first-layer": "First-Layer-Test",
};

function newId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

function profileName(catalog: StudioProfileCatalog | null, id: string | null | undefined): string {
  if (!catalog || !id) return "nicht ausgewählt";
  return catalog.profiles.find((item) => item.id === id)?.name || id;
}

export class Ultimate3DStudioWorkspaceShellV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  readonly #profiles = new ProfileApi();
  #core: HTMLElement | null = null;
  #catalog: StudioProfileCatalog | null = null;
  #clipboard: { object: SceneObject; record: ReturnType<typeof getStudioGeometry> } | null = null;
  #unsubscribe: (() => void) | null = null;

  set files(value: readonly File[]) {
    void this.#importFiles(value);
  }

  connectedCallback(): void {
    if (!this.#core) this.#mount();
    if (!this.#unsubscribe) {
      this.#unsubscribe = sceneStore.subscribe(() => this.#renderTransferControls());
    }
    void this.#loadProfiles();
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
  }

  async #loadProfiles(): Promise<void> {
    try {
      this.#catalog = await this.#profiles.getCatalog();
      this.#renderTransferControls();
    } catch {
      this.#catalog = null;
      this.#renderTransferControls();
    }
  }

  #mount(): void {
    const style = document.createElement("style");
    style.textContent = `
      :host{display:block;min-width:0;min-height:0;background:#08101a;color:#eef5ff}*{box-sizing:border-box}.shell{display:grid;grid-template-rows:auto minmax(0,1fr);min-height:720px}.bar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:9px 12px;border-bottom:1px solid #26384f;background:#0d1723}.bar strong{margin-right:auto;color:#9eb3c8}.bar button,.bar select{min-height:36px;padding:7px 10px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;font-weight:700}.bar button{cursor:pointer}.bar button:hover{border-color:#42c8ff}.bar button:disabled,.bar select:disabled{opacity:.4;cursor:not-allowed}.bar .first{border-color:#dfaa43;background:#4b3611;color:#fff1c2}.bar .transfer{border-color:#4b7aa0;background:#17324b}.bar .copy{border-color:#3d8058;background:#153421}.host{min-width:0;min-height:0;overflow:auto}.host>ultimate-3d-studio-workspace{display:block;width:100%;min-width:0}.hint{width:100%;color:#7890a8;font-size:11px}.profile{width:100%;padding:7px 10px;border:1px solid #2e5d7c;border-radius:8px;background:#10263a;color:#9ee7ff;font-size:11px}@media(max-width:700px){.bar strong{width:100%}.bar{max-height:250px;overflow:auto}.bar select{max-width:100%}}
    `;
    const shell = document.createElement("section");
    shell.className = "shell";
    const bar = document.createElement("header");
    bar.className = "bar";
    bar.id = "toolbar";
    const title = document.createElement("strong");
    title.textContent = "Geometrien, Druckplatten und CAD-Werkzeuge";
    bar.append(title);
    for (const kind of ["cube", "cylinder", "sphere", "cone", "torus", "plate"] as PrimitiveKind[]) {
      bar.append(this.#button(LABELS[kind], () => this.#addPrimitive(kind)));
    }
    const firstLayer = this.#button("First-Layer-Test für aktiven Drucker", () => this.#addFirstLayer(), "first");
    firstLayer.id = "first-layer";
    bar.append(firstLayer);

    const copy = this.#button("Kopieren", () => this.#copySelected(), "copy");
    copy.id = "copy";
    const paste = this.#button("Einfügen", () => this.#pasteToActivePlate(), "copy");
    paste.id = "paste";
    const target = document.createElement("select");
    target.id = "target-plate";
    const move = this.#button("Auf Druckplatte verschieben", () => this.#moveToSelectedPlate(), "transfer");
    move.id = "move";
    const moveNew = this.#button("Auf neue Druckplatte verschieben", () => this.#moveToNewPlate(), "transfer");
    moveNew.id = "move-new";
    bar.append(copy, paste, target, move, moveNew);

    const profile = document.createElement("div");
    profile.className = "profile";
    profile.id = "profile-binding";
    bar.append(profile);
    const hint = document.createElement("span");
    hint.className = "hint";
    hint.textContent = "Strg+C/Strg+V kopiert Objekte. Zielplatten übernehmen Druckplattenprofil und Abmessungen der aktuellen Platte. Rechtsklick öffnet dieselben Aktionen.";
    bar.append(hint);

    const host = document.createElement("main");
    host.className = "host";
    const core = document.createElement("ultimate-3d-studio-workspace");
    core.addEventListener("contextmenu", (event) => this.#openContext(event));
    this.#core = core;
    host.append(core);
    shell.append(bar, host);
    this.#root.replaceChildren(style, shell, document.createElement("studio-context-menu"));
    this.addEventListener("keydown", this.#onKeyDown);
    this.#renderTransferControls();
  }

  readonly #onKeyDown = (event: KeyboardEvent): void => {
    if (!(event.ctrlKey || event.metaKey)) return;
    const key = event.key.toLowerCase();
    if (key === "c") {
      event.preventDefault();
      this.#copySelected();
    }
    if (key === "v") {
      event.preventDefault();
      this.#pasteToActivePlate();
    }
  };

  #button(label: string, action: () => void, className = ""): HTMLButtonElement {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.className = className;
    button.addEventListener("click", action);
    return button;
  }

  #activePlate(): PlateState | null {
    const state = sceneStore.getState();
    return state.plates.find((plate) => plate.id === state.activePlateId) ?? state.plates[0] ?? null;
  }

  #selected(): { plate: PlateState; object: SceneObject } | null {
    const state = sceneStore.getState();
    const plate = this.#activePlate();
    const object = plate?.objects.find((item) => state.selectedObjectIds.includes(item.id));
    return plate && object ? { plate, object } : null;
  }

  #renderTransferControls(): void {
    const state = sceneStore.getState();
    const active = this.#activePlate();
    const selected = this.#selected();
    const target = this.#root.querySelector<HTMLSelectElement>("#target-plate");
    if (target) {
      const previous = target.value;
      target.replaceChildren();
      for (const plate of state.plates.filter((item) => item.id !== active?.id)) {
        const option = document.createElement("option");
        option.value = plate.id;
        option.textContent = plate.name;
        target.append(option);
      }
      if ([...target.options].some((option) => option.value === previous)) target.value = previous;
      target.disabled = !selected || target.options.length === 0;
    }
    const copy = this.#root.querySelector<HTMLButtonElement>("#copy");
    const paste = this.#root.querySelector<HTMLButtonElement>("#paste");
    const move = this.#root.querySelector<HTMLButtonElement>("#move");
    const moveNew = this.#root.querySelector<HTMLButtonElement>("#move-new");
    if (copy) copy.disabled = !selected;
    if (paste) paste.disabled = !this.#clipboard || !active;
    if (move) move.disabled = !selected || !target?.value;
    if (moveNew) moveNew.disabled = !selected;

    const printer = profileName(this.#catalog, this.#catalog?.selection.printer_profile_id);
    const nozzle = profileName(this.#catalog, this.#catalog?.selection.nozzle_profile_id);
    const buildPlate = profileName(this.#catalog, active?.buildPlateProfileId || this.#catalog?.selection.build_plate_profile_id);
    const binding = this.#root.querySelector<HTMLElement>("#profile-binding");
    if (binding) binding.textContent = `Aktive Bindung: Drucker ${printer} · Düse ${nozzle} · Druckplatte ${buildPlate}`;
    const first = this.#root.querySelector<HTMLButtonElement>("#first-layer");
    if (first) first.disabled = !this.#catalog?.selection.printer_profile_id || !this.#catalog?.selection.nozzle_profile_id || !active?.buildPlateProfileId;
  }

  #copySelected(): void {
    const selected = this.#selected();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    this.#clipboard = { object: selected.object, record };
    this.#renderTransferControls();
  }

  #pasteToActivePlate(): void {
    const plate = this.#activePlate();
    const clipboard = this.#clipboard;
    if (!plate || !clipboard?.record) return;
    const id = newId("paste");
    const object: SceneObject = {
      ...clipboard.object,
      id,
      assetId: `copy:${clipboard.object.id}`,
      name: `${clipboard.object.name} Kopie`,
      transform: {
        ...clipboard.object.transform,
        position: [clipboard.object.transform.position[0] + 10, clipboard.object.transform.position[1] + 10, clipboard.object.transform.position[2]],
      },
    };
    setStudioGeometry(id, clipboard.record);
    sceneStore.dispatch({ type: "add_object", plateId: plate.id, object });
    sceneStore.dispatch({ type: "select", objectIds: [id] });
  }

  #createInheritedPlate(source: PlateState): PlateState {
    const state = sceneStore.getState();
    return {
      id: newId("plate"),
      name: `Druckplatte ${state.plates.length + 1}`,
      orderIndex: state.plates.length,
      objects: [],
      buildPlateProfileId: source.buildPlateProfileId,
      widthMm: source.widthMm,
      depthMm: source.depthMm,
    };
  }

  #moveToSelectedPlate(): void {
    const selected = this.#selected();
    const target = this.#root.querySelector<HTMLSelectElement>("#target-plate")?.value;
    if (!selected || !target) return;
    sceneStore.dispatch({
      type: "move_object",
      sourcePlateId: selected.plate.id,
      targetPlateId: target,
      objectId: selected.object.id,
    });
  }

  #moveToNewPlate(): void {
    const selected = this.#selected();
    if (!selected) return;
    const plate = this.#createInheritedPlate(selected.plate);
    sceneStore.dispatch({ type: "add_plate", plate });
    sceneStore.dispatch({
      type: "move_object",
      sourcePlateId: selected.plate.id,
      targetPlateId: plate.id,
      objectId: selected.object.id,
    });
  }

  async #importFiles(files: readonly File[]): Promise<void> {
    const plate = this.#activePlate();
    if (!plate) return;
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith(".stl")) continue;
      const geometry = parseStl(await file.arrayBuffer());
      const id = newId("import");
      const transform: SceneTransform = {
        position: positionCenteredOnPlate(
          geometry,
          { position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
          plate.widthMm || 256,
          plate.depthMm || 256,
        ),
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
    }
  }

  #addPrimitive(kind: PrimitiveKind): void {
    const plate = this.#activePlate();
    if (!plate) return;
    const width = plate.widthMm || 256;
    const depth = plate.depthMm || 256;
    const geometry = createPrimitiveGeometry(kind, width, depth);
    const id = newId("primitive");
    const object: SceneObject = {
      id,
      assetId: `primitive:${kind}`,
      name: LABELS[kind],
      transform: { position: [width / 2, depth / 2, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
      visible: true,
      locked: false,
      color: "#38aee8",
    };
    setStudioGeometry(id, { geometry, fileName: `${LABELS[kind]}.stl` });
    sceneStore.dispatch({ type: "add_object", plateId: plate.id, object });
    sceneStore.dispatch({ type: "select", objectIds: [id] });
  }

  #addFirstLayer(): void {
    const plate = this.#activePlate();
    const selection = this.#catalog?.selection;
    if (!plate || !selection?.printer_profile_id || !selection.nozzle_profile_id || !plate.buildPlateProfileId) return;
    const width = plate.widthMm || 256;
    const depth = plate.depthMm || 256;
    const geometry = createPrimitiveGeometry("first-layer", width, depth);
    const id = newId("first-layer");
    const printer = profileName(this.#catalog, selection.printer_profile_id);
    const nozzle = profileName(this.#catalog, selection.nozzle_profile_id);
    const buildPlate = profileName(this.#catalog, plate.buildPlateProfileId);
    const object: SceneObject = {
      id,
      assetId: `first-layer:${selection.printer_profile_id}:${selection.nozzle_profile_id}:${plate.buildPlateProfileId}`,
      name: `First-Layer · ${printer} · ${nozzle} · ${buildPlate}`,
      transform: { position: [width / 2, depth / 2, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
      visible: true,
      locked: false,
      color: "#f3bf49",
    };
    setStudioGeometry(id, { geometry, fileName: `${object.name}.stl` });
    sceneStore.dispatch({ type: "add_object", plateId: plate.id, object });
    sceneStore.dispatch({ type: "select", objectIds: [id] });
  }

  #setTransform(transform: SceneTransform): void {
    const selected = this.#selected();
    if (!selected) return;
    sceneStore.dispatch({ type: "set_transform", plateId: selected.plate.id, objectId: selected.object.id, transform });
  }

  #center(): void {
    const selected = this.#selected();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    this.#setTransform({ ...selected.object.transform, position: positionCenteredOnPlate(record.geometry, selected.object.transform, selected.plate.widthMm || 256, selected.plate.depthMm || 256) });
  }

  #onBed(): void {
    const selected = this.#selected();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    this.#setTransform({ ...selected.object.transform, position: positionOnBed(record.geometry, selected.object.transform) });
  }

  #flat(): void {
    const selected = this.#selected();
    const record = selected ? getStudioGeometry(selected.object.id) : null;
    if (!selected || !record) return;
    const rotation = bestFlatRotation(record.geometry, selected.object.transform.scale);
    const provisional = { ...selected.object.transform, rotation };
    this.#setTransform({ ...provisional, position: positionCenteredOnPlate(record.geometry, provisional, selected.plate.widthMm || 256, selected.plate.depthMm || 256) });
  }

  #remove(): void {
    const selected = this.#selected();
    if (!selected) return;
    sceneStore.dispatch({ type: "remove_object", plateId: selected.plate.id, objectId: selected.object.id });
    removeStudioGeometry(selected.object.id);
    sceneStore.dispatch({ type: "select", objectIds: [] });
  }

  #openContext(event: Event): void {
    event.preventDefault();
    const mouse = event as MouseEvent;
    const selected = this.#selected();
    const plates = sceneStore.getState().plates.filter((plate) => plate.id !== selected?.plate.id);
    const items: StudioContextMenuItem[] = selected ? [
      { label: "Kopieren", action: () => this.#copySelected(), detail: "Strg+C" },
      { label: "Einfügen auf aktueller Platte", action: () => this.#pasteToActivePlate(), disabled: !this.#clipboard, detail: "Strg+V" },
      ...plates.map((plate): StudioContextMenuItem => ({
        label: `Auf ${plate.name} verschieben`,
        action: () => {
          sceneStore.dispatch({ type: "move_object", sourcePlateId: selected.plate.id, targetPlateId: plate.id, objectId: selected.object.id });
        },
      })),
      { label: "Auf neue Druckplatte verschieben", action: () => this.#moveToNewPlate() },
      { label: "Zentrieren", action: () => this.#center() },
      { label: "Flach legen", action: () => this.#flat() },
      { label: "Auf Druckbett", action: () => this.#onBed() },
      { label: "Löschen", action: () => this.#remove(), danger: true },
    ] : [
      { label: "Würfel hinzufügen", action: () => this.#addPrimitive("cube") },
      { label: "Zylinder hinzufügen", action: () => this.#addPrimitive("cylinder") },
      { label: "Kugel hinzufügen", action: () => this.#addPrimitive("sphere") },
      { label: "First-Layer-Test für aktiven Drucker", action: () => this.#addFirstLayer(), disabled: !this.#catalog?.selection.printer_profile_id || !this.#catalog?.selection.nozzle_profile_id || !this.#activePlate()?.buildPlateProfileId },
    ];
    this.#root.querySelector<StudioContextMenu>("studio-context-menu")?.openAt(mouse.clientX, mouse.clientY, items);
  }
}

if (!customElements.get("ultimate-3d-studio-shell")) {
  customElements.define("ultimate-3d-studio-shell", Ultimate3DStudioWorkspaceShellV2);
}
