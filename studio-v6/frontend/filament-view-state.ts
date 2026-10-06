type FilamentTreeSnapshot = Readonly<{
  key: string;
  scrollTop: number;
  groups: ReadonlyMap<string, boolean>;
}>;

function treeKey(tree: HTMLElement): string {
  return tree.closest("[data-filament-profile-picker]") ? "picker" : "sidebar";
}

/** Keep independent profile views stable when their contents are refreshed. */
export function preserveFilamentView(root: ShadowRoot | HTMLElement, render: () => void): void {
  const picker = root.querySelector<HTMLDetailsElement>("[data-filament-profile-picker]");
  const pickerOpen = picker?.open;
  const snapshots: FilamentTreeSnapshot[] = [...root.querySelectorAll<HTMLElement>(".filament-tree")].map((tree) => ({
    key: treeKey(tree),
    scrollTop: tree.scrollTop,
    groups: new Map([...tree.querySelectorAll<HTMLDetailsElement>("details[data-filament-detail-key]")].map((details) => [
      details.dataset.filamentDetailKey || "", details.open,
    ])),
  }));
  render();
  const nextPicker = root.querySelector<HTMLDetailsElement>("[data-filament-profile-picker]");
  if (nextPicker && pickerOpen !== undefined) nextPicker.open = pickerOpen;
  for (const tree of root.querySelectorAll<HTMLElement>(".filament-tree")) {
    const snapshot = snapshots.find((item) => item.key === treeKey(tree));
    if (!snapshot) continue;
    for (const details of tree.querySelectorAll<HTMLDetailsElement>("details[data-filament-detail-key]")) {
      const open = snapshot.groups.get(details.dataset.filamentDetailKey || "");
      if (open !== undefined) details.open = open;
    }
    // Open groups before assigning scrollTop, otherwise the browser clamps it to a collapsed tree.
    tree.scrollTop = snapshot.scrollTop;
  }
}
