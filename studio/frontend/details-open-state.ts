export function detailsOpenAttribute(openKeys: ReadonlySet<string>, key: string): string {
  return key && openKeys.has(key) ? " open" : "";
}

export function updateDetailsOpenState(openKeys: Set<string>, key: string, open: boolean): void {
  if (!key) return;
  if (open) openKeys.add(key);
  else openKeys.delete(key);
}
