import { sceneStore, type SceneTransform } from "./scene-store.js";

export type GizmoMode = "translate" | "rotate" | "scale";
export type GizmoAxis = "x" | "y" | "z" | "xy" | "xz" | "yz";

export type GizmoDrag = Readonly<{
  mode: GizmoMode;
  axis: GizmoAxis;
  plateId: string;
  objectId: string;
  startX: number;
  startY: number;
  initial: SceneTransform;
}>;

export class TransformGizmoController {
  #drag: GizmoDrag | null = null;

  begin(drag: GizmoDrag): void {
    if (this.#drag) throw new Error("gizmo drag already active");
    this.#drag = drag;
  }

  update(currentX: number, currentY: number): SceneTransform | null {
    const drag = this.#drag;
    if (!drag) return null;
    const dx = currentX - drag.startX;
    const dy = currentY - drag.startY;
    const next = this.#applyDelta(drag, dx, dy);
    sceneStore.dispatch({
      type: "set_transform",
      plateId: drag.plateId,
      objectId: drag.objectId,
      transform: next,
    });
    return next;
  }

  end(): GizmoDrag | null {
    const completed = this.#drag;
    this.#drag = null;
    return completed;
  }

  cancel(): void {
    const drag = this.#drag;
    if (!drag) return;
    sceneStore.dispatch({
      type: "set_transform",
      plateId: drag.plateId,
      objectId: drag.objectId,
      transform: drag.initial,
    });
    this.#drag = null;
  }

  #applyDelta(drag: GizmoDrag, dx: number, dy: number): SceneTransform {
    const amount = (dx - dy) * 0.1;
    if (drag.mode === "translate") {
      const position = [...drag.initial.position] as [number, number, number];
      this.#applyAxis(position, drag.axis, amount);
      return { ...drag.initial, position };
    }
    if (drag.mode === "rotate") {
      const rotation = [...drag.initial.rotation] as [number, number, number];
      this.#applyAxis(rotation, drag.axis, amount);
      return { ...drag.initial, rotation };
    }
    const scale = [...drag.initial.scale] as [number, number, number];
    this.#applyAxis(scale, drag.axis, amount * 0.01);
    return {
      ...drag.initial,
      scale: scale.map((value) => Math.max(0.001, value)) as [number, number, number],
    };
  }

  #applyAxis(
    values: [number, number, number],
    axis: GizmoAxis,
    amount: number,
  ): void {
    const indexes: readonly (0 | 1 | 2)[] =
      axis === "x" ? [0] :
      axis === "y" ? [1] :
      axis === "z" ? [2] :
      axis === "xy" ? [0, 1] :
      axis === "xz" ? [0, 2] :
      [1, 2];

    for (const index of indexes) {
      values[index] = values[index] + amount;
    }
  }
}
