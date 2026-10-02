import {
  StudioTransformToolsV2,
  type StudioTransformInteractionStateV2,
} from "./studio-transform-tools-v2.js";

export type StudioTransformInteractionState = StudioTransformInteractionStateV2;

export class StudioTransformTools extends StudioTransformToolsV2 {}

if (!customElements.get("studio-transform-tools")) {
  customElements.define("studio-transform-tools", StudioTransformTools);
}
