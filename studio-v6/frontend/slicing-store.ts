import { Store } from "./state-store.js";
import type { SlicePlan } from "./slicing-api.js";

export type SlicingState = Readonly<{
  activePlanId: string | null;
  plans: Readonly<Record<string, SlicePlan>>;
  selectedLayer: number;
  layerCount: number;
  loading: boolean;
  error: string | null;
}>;

export type SlicingAction =
  | { type: "loading"; planId?: string }
  | { type: "plan_updated"; plan: SlicePlan & Readonly<{ id: string }> }
  | { type: "select_layer"; layer: number }
  | { type: "layer_count"; count: number }
  | { type: "error"; message: string | null };

const INITIAL: SlicingState = {
  activePlanId: null,
  plans: {},
  selectedLayer: 0,
  layerCount: 0,
  loading: false,
  error: null,
};

function reducer(state: SlicingState, action: Readonly<SlicingAction>): SlicingState {
  if (action.type === "loading") {
    return {
      ...state,
      loading: true,
      error: null,
      activePlanId: action.planId ?? state.activePlanId,
    };
  }
  if (action.type === "plan_updated") {
    return {
      ...state,
      loading: false,
      error: null,
      activePlanId: action.plan.id,
      plans: { ...state.plans, [action.plan.id]: action.plan },
    };
  }
  if (action.type === "layer_count") {
    return {
      ...state,
      layerCount: Math.max(0, action.count),
      selectedLayer: 0,
    };
  }
  if (action.type === "select_layer") {
    return {
      ...state,
      selectedLayer: Math.max(0, Math.min(action.layer, Math.max(0, state.layerCount - 1))),
    };
  }
  return { ...state, loading: false, error: action.message };
}

export const slicingStore = new Store<SlicingState, SlicingAction>(INITIAL, reducer);