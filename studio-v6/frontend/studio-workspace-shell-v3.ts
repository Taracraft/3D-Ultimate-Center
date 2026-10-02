import "./studio-workspace-shell-v2.js";
import { transformedBounds } from "./mesh-export.js";
import { sceneStore, type PlateState, type SceneObject, type SceneTransform } from "./scene-store.js";
import { getStudioGeometry } from "./studio-session.js";

type InnerStudioShell = HTMLElement & { files: readonly File[] };

function activePlate(): PlateState | null {
  const state = sceneStore.getState();
  return state.plates.find((plate) => plate.id === state.activePlateId) ?? state.plates[0] ?? null;
}

function arrangeObjects(plate: PlateState): number {
  const objects = plate.objects.filter((object) => object.visible && getStudioGeometry(object.id));
  if (!objects.length) return 0;

  const width = Math.max(40, plate.widthMm || 256);
  const depth = Math.max(40, plate.depthMm || 256);
  const margin = Math.min(12, Math.max(5, Math.min(width, depth) * 0.035));
  const gap = Math.min(10, Math.max(4, Math.min(width, depth) * 0.025));
  const aspect = width / depth;
  const columns = Math.max(1, Math.ceil(Math.sqrt(objects.length * aspect)));
  const rows = Math.max(1, Math.ceil(objects.length / columns));
  const cellWidth = Math.max(10, (width - margin * 2 - gap * (columns - 1)) / columns);
  const cellDepth = Math.max(10, (depth - margin * 2 - gap * (rows - 1)) / rows);
  const usableWidth = Math.max(5, cellWidth - gap);
  const usableDepth = Math.max(5, cellDepth - gap);

  objects.forEach((object, index) => {
    const record = getStudioGeometry(object.id);
    if (!record) return;
    const column = index % columns;
    const row = Math.floor(index / columns);
    const targetX = margin + column * (cellWidth + gap) + cellWidth / 2;
    const targetY = margin + row * (cellDepth + gap) + cellDepth / 2;

    const zeroPosition: SceneTransform = {
      position: [0, 0, 0],
      rotation: object.transform.rotation,
      scale: object.transform.scale,
    };
    const currentBounds = transformedBounds(record.geometry, zeroPosition);
    const sizeX = Math.max(0.001, currentBounds.max[0] - currentBounds.min[0]);
    const sizeY = Math.max(0.001, currentBounds.max[1] - currentBounds.min[1]);
    const fitFactor = Math.min(1, usableWidth / sizeX, usableDepth / sizeY);
    const scale: [number, number, number] = [
      object.transform.scale[0] * fitFactor,
      object.transform.scale[1] * fitFactor,
      object.transform.scale[2] * fitFactor,
    ];
    const fittedBounds = transformedBounds(record.geometry, {
      position: [0, 0, 0],
      rotation: object.transform.rotation,
      scale,
    });
    const centerX = (fittedBounds.min[0] + fittedBounds.max[0]) / 2;
    const centerY = (fittedBounds.min[1] + fittedBounds.max[1]) / 2;
    const transform: SceneTransform = {
      position: [targetX - centerX, targetY - centerY, -fittedBounds.min[2]],
      rotation: object.transform.rotation,
      scale,
    };
    sceneStore.dispatch({ type: "set_transform", plateId: plate.id, objectId: object.id, transform });
  });
  return objects.length;
}

export class Ultimate3DArrangedStudioShell extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #inner: InnerStudioShell | null = null;
  #unsubscribe: (() => void) | null = null;
  #pendingArrange = false;
  #timer = 0;
  #lastCount = 0;

  set files(value: readonly File[]) {
    if (!value.length) return;
    this.#pendingArrange = true;
    this.#inner!.files = value;
    this.#scheduleArrange();
  }

  connectedCallback(): void {
    if (!this.#root.childElementCount) this.#mount();
    if (!this.#unsubscribe) {
      this.#unsubscribe = sceneStore.subscribe(() => {
        const count = activePlate()?.objects.length ?? 0;
        if (this.#pendingArrange && count !== this.#lastCount) {
          this.#lastCount = count;
          this.#scheduleArrange();
        }
        this.#renderStatus();
      });
    }
    this.#lastCount = activePlate()?.objects.length ?? 0;
    this.#renderStatus();
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
    window.clearTimeout(this.#timer);
  }

  #mount(): void {
    const style = document.createElement("style");
    style.textContent = `:host{display:block;width:100%;height:100%;min-width:0;min-height:0}.wrap{display:grid;grid-template-rows:auto minmax(0,1fr);height:100%;min-height:680px}.arrange{display:flex;gap:8px;align-items:center;padding:7px 10px;border-bottom:1px solid #26384f;background:#0b1621}.arrange button{min-height:34px;padding:7px 11px;border:1px solid #3488b5;border-radius:8px;background:#123b55;color:#eef8ff;font-weight:700;cursor:pointer}.arrange button:hover{border-color:#55d2ff}.arrange span{color:#8298ad;font-size:10px}.host{min-width:0;min-height:0;overflow:auto}.host>ultimate-3d-studio-shell{display:block;width:100%;min-height:680px}`;
    const wrapper = document.createElement("section");
    wrapper.className = "wrap";
    wrapper.innerHTML = `<header class="arrange"><button id="arrange" type="button">Automatisch anordnen</button><span id="status">Objekte werden innerhalb der aktiven Druckplatte verteilt und zentriert.</span></header><main class="host" id="host"></main>`;
    const inner = document.createElement("ultimate-3d-studio-shell") as InnerStudioShell;
    this.#inner = inner;
    wrapper.querySelector("#host")?.append(inner);
    this.#root.replaceChildren(style, wrapper);
    this.#root.querySelector<HTMLButtonElement>("#arrange")?.addEventListener("click", () => this.#arrangeNow());
  }

  #scheduleArrange(): void {
    window.clearTimeout(this.#timer);
    this.#timer = window.setTimeout(() => {
      this.#pendingArrange = false;
      this.#arrangeNow();
    }, 180);
  }

  #arrangeNow(): void {
    const plate = activePlate();
    if (!plate) return;
    const count = arrangeObjects(plate);
    const status = this.#root.querySelector<HTMLElement>("#status");
    if (status) status.textContent = count
      ? `${count} Objekt(e) auf ${plate.name} verteilt, eingepasst und auf Z = 0 gesetzt.`
      : "Keine sichtbaren Objekte zum Anordnen vorhanden.";
  }

  #renderStatus(): void {
    const plate = activePlate();
    const status = this.#root.querySelector<HTMLElement>("#status");
    if (!status || this.#pendingArrange) return;
    status.textContent = plate
      ? `${plate.name} · ${plate.objects.length} Objekt(e) · ${plate.widthMm || 256} × ${plate.depthMm || 256} mm`
      : "Keine aktive Druckplatte vorhanden.";
  }
}

if (!customElements.get("ultimate-3d-arranged-studio")) {
  customElements.define("ultimate-3d-arranged-studio", Ultimate3DArrangedStudioShell);
}