export type StudioSelectionResult = Readonly<{
  selected: Set<string>;
  anchor: string | null;
}>;

export function nextStudioSelection(
  orderedIds: readonly string[],
  currentSelection: ReadonlySet<string>,
  id: string | null,
  toggle: boolean,
  range: boolean,
  anchor: string | null,
): StudioSelectionResult {
  if (!id) {
    return toggle || range
      ? { selected: new Set(currentSelection), anchor }
      : { selected: new Set(), anchor: null };
  }

  if (range) {
    const anchorIndex = anchor ? orderedIds.indexOf(anchor) : -1;
    const targetIndex = orderedIds.indexOf(id);
    if (anchorIndex >= 0 && targetIndex >= 0) {
      const selected = new Set(currentSelection);
      const start = Math.min(anchorIndex, targetIndex);
      const end = Math.max(anchorIndex, targetIndex);
      for (const item of orderedIds.slice(start, end + 1)) selected.add(item);
      return { selected, anchor };
    }
    const selected = new Set(currentSelection);
    selected.add(id);
    return { selected, anchor: anchor ?? id };
  }

  if (toggle) {
    const selected = new Set(currentSelection);
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    return { selected, anchor: id };
  }

  return { selected: new Set([id]), anchor: id };
}

export function selectAllStudioObjects(orderedIds: readonly string[]): StudioSelectionResult {
  return {
    selected: new Set(orderedIds),
    anchor: orderedIds[0] ?? null,
  };
}
