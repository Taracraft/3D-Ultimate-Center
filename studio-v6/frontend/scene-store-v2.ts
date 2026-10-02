import { Store } from "./state-store.js";

export type Vector3 = readonly [number, number, number];
export type SceneTransform = Readonly<{ position: Vector3; rotation: Vector3; scale: Vector3 }>;
export type SceneObject = Readonly<{
  id: string;
  assetId: string;
  name: string;
  transform: SceneTransform;
  visible: boolean;
  locked: boolean;
  color: string | null;
}>;
export type PlateState = Readonly<{
  id: string;
  name: string;
  orderIndex: number;
  objects: readonly SceneObject[];
  buildPlateProfileId?: string;
  widthMm?: number;
  depthMm?: number;
}>;
export type SceneState = Readonly<{
  projectId: string | null;
  revision: number;
  activePlateId: string | null;
  plates: readonly PlateState[];
  selectedObjectIds: readonly string[];
}>;
export type SceneAction =
  | { type: "load"; state: SceneState }
  | { type: "activate_plate"; plateId: string }
  | { type: "add_plate"; plate: PlateState }
  | { type: "remove_plate"; plateId: string }
  | { type: "rename_plate"; plateId: string; name: string }
  | { type: "set_plate_profile"; plateId: string; profileId: string; widthMm: number; depthMm: number }
  | { type: "select"; objectIds: readonly string[] }
  | { type: "add_object"; plateId: string; object: SceneObject }
  | { type: "remove_object"; plateId: string; objectId: string }
  | { type: "move_object"; sourcePlateId: string; targetPlateId: string; objectId: string; object?: SceneObject }
  | { type: "set_transform"; plateId: string; objectId: string; transform: SceneTransform }
  | { type: "set_color"; plateId: string; objectId: string; color: string | null };

const INITIAL_STATE: SceneState = Object.freeze({
  projectId: null,
  revision: 0,
  activePlateId: null,
  plates: Object.freeze([]),
  selectedObjectIds: Object.freeze([]),
});

function updatePlate(state: SceneState, plateId: string, updater: (plate: PlateState) => PlateState): SceneState {
  let found = false;
  const plates = state.plates.map((plate) => {
    if (plate.id !== plateId) return plate;
    found = true;
    return updater(plate);
  });
  if (!found) throw new Error(`Unknown plate: ${plateId}`);
  return { ...state, revision: state.revision + 1, plates };
}

function reducer(state: SceneState, action: Readonly<SceneAction>): SceneState {
  switch (action.type) {
    case "load": return action.state;
    case "activate_plate":
      if (!state.plates.some((plate) => plate.id === action.plateId)) throw new Error(`Unknown plate: ${action.plateId}`);
      return { ...state, activePlateId: action.plateId, selectedObjectIds: [] };
    case "add_plate":
      if (state.plates.some((plate) => plate.id === action.plate.id)) throw new Error(`Duplicate plate: ${action.plate.id}`);
      return { ...state, revision: state.revision + 1, activePlateId: action.plate.id, selectedObjectIds: [], plates: [...state.plates, action.plate] };
    case "remove_plate": {
      if (state.plates.length <= 1) throw new Error("At least one plate is required");
      if (!state.plates.some((plate) => plate.id === action.plateId)) throw new Error(`Unknown plate: ${action.plateId}`);
      const plates = state.plates.filter((plate) => plate.id !== action.plateId).map((plate, index) => ({ ...plate, orderIndex: index }));
      return { ...state, revision: state.revision + 1, plates, activePlateId: state.activePlateId === action.plateId ? plates[0]?.id ?? null : state.activePlateId, selectedObjectIds: [] };
    }
    case "rename_plate":
      return updatePlate(state, action.plateId, (plate) => ({ ...plate, name: action.name.trim().slice(0, 120) || plate.name }));
    case "set_plate_profile":
      return updatePlate(state, action.plateId, (plate) => ({ ...plate, buildPlateProfileId: action.profileId, widthMm: action.widthMm, depthMm: action.depthMm }));
    case "select":
      return { ...state, selectedObjectIds: [...new Set(action.objectIds)] };
    case "add_object":
      return updatePlate(state, action.plateId, (plate) => {
        if (plate.objects.some((item) => item.id === action.object.id)) throw new Error(`Duplicate object: ${action.object.id}`);
        return { ...plate, objects: [...plate.objects, action.object] };
      });
    case "remove_object":
      return updatePlate(state, action.plateId, (plate) => ({ ...plate, objects: plate.objects.filter((item) => item.id !== action.objectId) }));
    case "move_object": {
      if (action.sourcePlateId === action.targetPlateId) return state;
      const source = state.plates.find((plate) => plate.id === action.sourcePlateId);
      const target = state.plates.find((plate) => plate.id === action.targetPlateId);
      if (!source) throw new Error(`Unknown plate: ${action.sourcePlateId}`);
      if (!target) throw new Error(`Unknown plate: ${action.targetPlateId}`);
      const object = action.object || source.objects.find((item) => item.id === action.objectId);
      if (!object) throw new Error(`Unknown object: ${action.objectId}`);
      if (target.objects.some((item) => item.id === object.id)) throw new Error(`Duplicate object: ${object.id}`);
      return {
        ...state,
        revision: state.revision + 1,
        activePlateId: action.targetPlateId,
        selectedObjectIds: [object.id],
        plates: state.plates.map((plate) => {
          if (plate.id === action.sourcePlateId) return { ...plate, objects: plate.objects.filter((item) => item.id !== action.objectId) };
          if (plate.id === action.targetPlateId) return { ...plate, objects: [...plate.objects, object] };
          return plate;
        }),
      };
    }
    case "set_transform":
      return updatePlate(state, action.plateId, (plate) => ({
        ...plate,
        objects: plate.objects.map((item) => {
          if (item.id !== action.objectId) return item;
          if (item.locked) throw new Error(`Object is locked: ${item.id}`);
          return { ...item, transform: action.transform };
        }),
      }));
    case "set_color":
      return updatePlate(state, action.plateId, (plate) => ({
        ...plate,
        objects: plate.objects.map((item) => item.id === action.objectId ? { ...item, color: action.color } : item),
      }));
  }
}

export const sceneStore = new Store<SceneState, SceneAction>(INITIAL_STATE, reducer);