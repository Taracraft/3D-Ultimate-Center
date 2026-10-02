export function normalizeMakerWorldTerms(values: readonly string[]): string[] {
  const result: string[] = [];
  for (const raw of values) {
    const value = String(raw || "").trim();
    if (!value || result.some((item) => item.localeCompare(value, "de", { sensitivity: "base" }) === 0)) continue;
    result.push(value);
    if (result.length >= 12) break;
  }
  return result;
}

export function addMakerWorldTerms(current: readonly string[], value: string): string[] {
  const additions = String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return normalizeMakerWorldTerms([...current, ...additions]);
}

export function removeMakerWorldTerm(current: readonly string[], value: string): string[] {
  return current.filter((item) => item.localeCompare(value, "de", { sensitivity: "base" }) !== 0);
}