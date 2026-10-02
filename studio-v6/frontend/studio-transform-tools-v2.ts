import {
  sceneStore,
  type SceneObject,
  type SceneState,
  type SceneTransform,
} from "./scene-store.js";
import type { GizmoAxis, GizmoMode } from "./transform-gizmo.js";

export type StudioToolModeV2 = "direct" | GizmoMode;
export type StudioTransformInteractionStateV2 = Readonly<{
  mode: StudioToolModeV2;
  axis: GizmoAxis;
  snap: number;
}>;

type DragState = Readonly<{
  pointerId: number;
  startX: number;
  startY: number;
  plateId: string;
  objectId: string;
  initial: SceneTransform;
}>;

const state = {
  mode: "direct" as StudioToolModeV2,
  axis: "x" as GizmoAxis,
  translateSnap: 1,
  rotateSnap: 5,
  scaleSnap: 0.05,
};

function selected(
  scene: Readonly<SceneState>,
): { plateId: string; object: SceneObject } | null {
  const plate = scene.plates.find((item) => item.id === scene.activePlateId);
  const object = plate?.objects.find((item) =>
    scene.selectedObjectIds.includes(item.id)
  );
  return plate && object ? { plateId: plate.id, object } : null;
}

function snapped(value: number, step: number): number {
  return step > 0 ? Math.round(value / step) * step : value;
}

export class StudioTransformToolsV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #unsubscribe: (() => void) | null = null;
  #drag: DragState | null = null;

  connectedCallback(): void {
    if (this.#unsubscribe) return;
    this.#unsubscribe = sceneStore.subscribe(() => this.#render());
    this.#render();
  }

  disconnectedCallback(): void {
    this.#unsubscribe?.();
    this.#unsubscribe = null;
    this.#drag = null;
  }

  setMode(mode: StudioToolModeV2): void {
    state.mode = mode;
    this.#drag = null;
    this.#render();
  }

  setAxis(axis: GizmoAxis): void {
    state.axis = axis;
    this.#render();
  }

  step(direction: -1 | 1): void {
    const current = selected(sceneStore.getState());
    if (!current || state.mode === "direct") return;
    this.#apply(current.plateId, current.object.id, current.object.transform, direction * this.#snap());
  }

  getInteractionState(): StudioTransformInteractionStateV2 {
    return { mode: state.mode, axis: state.axis, snap: this.#snap() };
  }

  #snap(): number {
    if (state.mode === "rotate") return state.rotateSnap;
    if (state.mode === "scale") return state.scaleSnap;
    return state.translateSnap;
  }

  #setSnap(value: number): void {
    if (!Number.isFinite(value) || value < 0 || state.mode === "direct") return;
    if (state.mode === "translate") state.translateSnap = value;
    else if (state.mode === "rotate") state.rotateSnap = value;
    else state.scaleSnap = value;
  }

  #apply(
    plateId: string,
    objectId: string,
    initial: SceneTransform,
    delta: number,
  ): void {
    const position = [...initial.position] as [number, number, number];
    const rotation = [...initial.rotation] as [number, number, number];
    const scale = [...initial.scale] as [number, number, number];
    const index = state.axis === "x" ? 0 : state.axis === "y" ? 1 : 2;
    if (state.mode === "translate") {
      position[index] = snapped(position[index] + delta, state.translateSnap);
    } else if (state.mode === "rotate") {
      rotation[index] = snapped(rotation[index] + delta, state.rotateSnap);
    } else if (state.mode === "scale") {
      scale[index] = Math.max(
        0.001,
        snapped(scale[index] + delta, state.scaleSnap),
      );
    }
    sceneStore.dispatch({
      type: "set_transform",
      plateId,
      objectId,
      transform: { position, rotation, scale },
    });
  }

  #beginDrag(event: PointerEvent): void {
    const current = selected(sceneStore.getState());
    if (!current || state.mode === "direct") return;
    const button = event.currentTarget as HTMLButtonElement;
    try {
      button.setPointerCapture(event.pointerId);
    } catch (_error) {
      // Pointer capture is optional.
    }
    this.#drag = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      plateId: current.plateId,
      objectId: current.object.id,
      initial: current.object.transform,
    };
  }

  #moveDrag(event: PointerEvent): void {
    const drag = this.#drag;
    if (!drag || drag.pointerId !== event.pointerId || state.mode === "direct") {
      return;
    }
    const dx = event.clientX - drag.startX;
    const dy = drag.startY - event.clientY;
    const pixels = Math.abs(dx) >= Math.abs(dy) ? dx : dy;
    const factor = state.mode === "translate"
      ? 0.35
      : state.mode === "rotate"
        ? 0.32
        : 0.005;
    this.#apply(
      drag.plateId,
      drag.objectId,
      drag.initial,
      pixels * factor,
    );
  }

  #endDrag(event: PointerEvent): void {
    if (this.#drag?.pointerId === event.pointerId) this.#drag = null;
  }

  #reset(): void {
    const current = selected(sceneStore.getState());
    if (!current) return;
    sceneStore.dispatch({
      type: "set_transform",
      plateId: current.plateId,
      objectId: current.object.id,
      transform: {
        position: [128, 128, 0],
        rotation: [0, 0, 0],
        scale: [1, 1, 1],
      },
    });
    this.dispatchEvent(new CustomEvent("studio-place-on-bed", {
      bubbles: true,
      composed: true,
    }));
  }

  #render(): void {
    const current = selected(sceneStore.getState());
    const disabled = current ? "" : "disabled";
    const objectValues = current
      ? `<div class="values">
          <div><small>Position</small><b>${current.object.transform.position.map((value) => Number(value).toFixed(1)).join(" / ")}</b></div>
          <div><small>Drehung</small><b>${current.object.transform.rotation.map((value) => Number(value).toFixed(1)).join(" / ")}</b></div>
          <div><small>Skalierung</small><b>${current.object.transform.scale.map((value) => Number(value).toFixed(2)).join(" / ")}</b></div>
        </div>`
      : '<div class="hint">Ein Objekt auswählen.</div>';
    const editor = state.mode === "direct"
      ? `<div class="view-help">
          Linke Maustaste: Ansicht drehen<br>
          Rechte Maustaste: Ansicht verschieben<br>
          Mausrad: zoomen<br>
          Für das Objekt ein Werkzeug wählen.
        </div>`
      : `<div class="axes">
          ${this.#axisButton("x")}${this.#axisButton("y")}${this.#axisButton("z")}
        </div>
        <button id="drag" class="drag" ${disabled}>
          <strong>${this.#modeLabel()} auf ${state.axis.toUpperCase()}</strong>
          <small>Ziehen oder direkt im 3D-Fenster links ziehen</small>
        </button>
        <label class="snap"><span>Snap-Schritt</span><input id="snap" type="number" min="0" step="0.01" value="${this.#snap()}"></label>
        <div class="actions"><button id="minus" ${disabled}>− Schritt</button><button id="plus" ${disabled}>+ Schritt</button></div>`;

    this.#root.innerHTML = `<style>
      :host{display:block;margin-top:16px;padding-top:14px;border-top:1px solid #26394f;color:#edf6ff}
      *{box-sizing:border-box}h3{margin:0 0 10px;font-size:13px;color:#9fc7e8;text-transform:uppercase}
      .modes,.axes,.actions{display:grid;gap:7px;margin-bottom:10px}.modes{grid-template-columns:repeat(2,1fr)}.axes{grid-template-columns:repeat(3,1fr)}.actions{grid-template-columns:repeat(2,1fr)}
      button,input{min-width:0;border:1px solid #31506e;border-radius:8px;padding:8px;background:#112237;color:#edf6ff}button{cursor:pointer;font-weight:700}button[active]{border-color:#42c8ff;background:#173b58}button:disabled{opacity:.35}
      .axis-x[active]{border-color:#ff6262;color:#ff9292}.axis-y[active]{border-color:#66dc82;color:#8ef2a3}.axis-z[active]{border-color:#5d9dff;color:#8dbbff}
      .drag{width:100%;height:58px;border-style:dashed;touch-action:none}.drag strong,.drag small{display:block}.drag small{margin-top:4px;color:#91a5bb;font-weight:400}
      .snap{display:grid;grid-template-columns:1fr 92px;gap:8px;align-items:center;margin:8px 0;color:#9cb1c7;font-size:12px}
      .view-help{padding:10px;border:1px solid #284560;border-radius:8px;background:#0b1a29;color:#a9c5df;font-size:12px;line-height:1.6;margin-bottom:10px}
      .values{display:grid;gap:6px}.values div{padding:8px;border:1px solid #26394f;border-radius:7px;background:#09121c}.values small,.values b{display:block}.values small{color:#8298ae}.hint{color:#71869c;font-size:11px}
    </style>
    <h3>Transform-Werkzeug</h3>
    <div class="modes">
      ${this.#modeButton("direct", "Ansicht")}
      ${this.#modeButton("translate", "Verschieben")}
      ${this.#modeButton("rotate", "Drehen")}
      ${this.#modeButton("scale", "Skalieren")}
    </div>
    ${editor}
    <div class="actions"><button id="reset" ${disabled}>Zurücksetzen</button><button id="bed" ${disabled}>Auf Druckbett</button></div>
    ${objectValues}`;

    this.#root.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach(
      (button) => button.addEventListener("click", () =>
        this.setMode(button.dataset.mode as StudioToolModeV2)),
    );
    this.#root.querySelectorAll<HTMLButtonElement>("[data-axis]").forEach(
      (button) => button.addEventListener("click", () =>
        this.setAxis(button.dataset.axis as GizmoAxis)),
    );
    this.#root.querySelector<HTMLInputElement>("#snap")?.addEventListener(
      "change",
      (event) => {
        this.#setSnap(Number((event.currentTarget as HTMLInputElement).value));
        this.#render();
      },
    );
    this.#root.querySelector<HTMLButtonElement>("#minus")?.addEventListener(
      "click",
      () => this.step(-1),
    );
    this.#root.querySelector<HTMLButtonElement>("#plus")?.addEventListener(
      "click",
      () => this.step(1),
    );
    this.#root.querySelector<HTMLButtonElement>("#reset")?.addEventListener(
      "click",
      () => this.#reset(),
    );
    this.#root.querySelector<HTMLButtonElement>("#bed")?.addEventListener(
      "click",
      () => this.dispatchEvent(new CustomEvent("studio-place-on-bed", {
        bubbles: true,
        composed: true,
      })),
    );
    const drag = this.#root.querySelector<HTMLButtonElement>("#drag");
    if (drag) {
      drag.onpointerdown = (event) => this.#beginDrag(event);
      drag.onpointermove = (event) => this.#moveDrag(event);
      drag.onpointerup = (event) => this.#endDrag(event);
      drag.onpointercancel = () => { this.#drag = null; };
    }
  }

  #modeButton(mode: StudioToolModeV2, label: string): string {
    return `<button data-mode="${mode}" ${state.mode === mode ? "active" : ""}>${label}</button>`;
  }

  #axisButton(axis: GizmoAxis): string {
    return `<button class="axis-${axis}" data-axis="${axis}" ${state.axis === axis ? "active" : ""}>${axis.toUpperCase()}</button>`;
  }

  #modeLabel(): string {
    if (state.mode === "translate") return "Verschieben";
    if (state.mode === "rotate") return "Drehen";
    return "Skalieren";
  }
}

if (!customElements.get("studio-transform-tools-v2")) {
  customElements.define("studio-transform-tools-v2", StudioTransformToolsV2);
}