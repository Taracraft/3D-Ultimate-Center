export type InteractionMode =
  | "idle"
  | "hovering"
  | "selecting"
  | "box_selecting"
  | "orbiting"
  | "panning"
  | "object_dragging"
  | "gizmo_translating"
  | "gizmo_rotating"
  | "gizmo_scaling"
  | "context_menu_open";

export type PointerIntent =
  | "scene"
  | "object"
  | "gizmo_translate"
  | "gizmo_rotate"
  | "gizmo_scale";

export type InteractionSnapshot = Readonly<{
  mode: InteractionMode;
  pointerId: number | null;
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
  targetId: string | null;
}>;

const INITIAL: InteractionSnapshot = Object.freeze({
  mode: "idle",
  pointerId: null,
  startX: 0,
  startY: 0,
  currentX: 0,
  currentY: 0,
  targetId: null,
});

export class PointerInteractionController {
  #state: InteractionSnapshot = INITIAL;

  get snapshot(): InteractionSnapshot {
    return this.#state;
  }

  begin(
    event: PointerEvent,
    intent: PointerIntent,
    targetId: string | null = null,
  ): InteractionSnapshot {
    if (this.#state.pointerId !== null) {
      return this.#state;
    }

    const mode = this.#resolveMode(event, intent);
    this.#state = Object.freeze({
      mode,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      currentX: event.clientX,
      currentY: event.clientY,
      targetId,
    });
    event.currentTarget instanceof Element &&
      event.currentTarget.setPointerCapture(event.pointerId);
    return this.#state;
  }

  move(event: PointerEvent): InteractionSnapshot {
    if (event.pointerId !== this.#state.pointerId) {
      return this.#state;
    }
    this.#state = Object.freeze({
      ...this.#state,
      currentX: event.clientX,
      currentY: event.clientY,
    });
    return this.#state;
  }

  end(event: PointerEvent): InteractionSnapshot {
    if (event.pointerId !== this.#state.pointerId) {
      return this.#state;
    }
    if (
      event.currentTarget instanceof Element &&
      event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    const completed = this.#state;
    this.#state = INITIAL;
    return completed;
  }

  cancel(pointerId?: number): void {
    if (pointerId === undefined || pointerId === this.#state.pointerId) {
      this.#state = INITIAL;
    }
  }

  openContextMenu(x: number, y: number, targetId: string | null): void {
    if (this.#state.pointerId !== null) {
      return;
    }
    this.#state = Object.freeze({
      mode: "context_menu_open",
      pointerId: null,
      startX: x,
      startY: y,
      currentX: x,
      currentY: y,
      targetId,
    });
  }

  #resolveMode(event: PointerEvent, intent: PointerIntent): InteractionMode {
    if (intent === "gizmo_translate") return "gizmo_translating";
    if (intent === "gizmo_rotate") return "gizmo_rotating";
    if (intent === "gizmo_scale") return "gizmo_scaling";
    if (event.button === 2) return "orbiting";
    if (event.button === 1 || event.shiftKey) return "panning";
    if (intent === "object") return "object_dragging";
    if (event.ctrlKey || event.metaKey) return "box_selecting";
    return "selecting";
  }
}
