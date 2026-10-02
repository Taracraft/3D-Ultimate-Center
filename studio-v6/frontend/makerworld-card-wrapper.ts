import "./makerworld-info-popover.js";

export function wrapWithMakerWorldInfo(
  card: HTMLElement,
  assetId: string,
): HTMLElement {
  const wrapper = document.createElement("makerworld-info-popover");
  wrapper.setAttribute("asset-id", assetId);
  wrapper.append(card);
  return wrapper;
}