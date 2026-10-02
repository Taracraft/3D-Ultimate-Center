export type PrintPhaseDefinition = Readonly<{
  key: string;
  label: string;
  currentLabel: string;
  detail?: string;
  doneOnlyWhenJobEnds?: boolean;
}>;

export const PRINT_PHASES: readonly PrintPhaseDefinition[] = [
  { key: "bed_heating", label: "Bett heizt", currentLabel: "Druckbett heizt" },
  { key: "homing", label: "Homing", currentLabel: "Drucker referenziert die Achsen" },
  { key: "filament_loading", label: "Filament laden", currentLabel: "Filament wird geladen" },
  { key: "flow_calibration", label: "Flow-Kalibrierung", currentLabel: "Filamentfluss wird kalibriert" },
  { key: "mechanical_check", label: "Mechanikprüfung", currentLabel: "Mechanik wird geprüft" },
  {
    key: "nozzle_cleaning_after",
    label: "Düse reinigen",
    currentLabel: "Druckkopf wird gereinigt",
    detail: "Der A1 meldet die verlässlich beobachtbare Reinigung nach der Kalibrierung.",
  },
  { key: "bed_leveling", label: "Druckbett nivellieren", currentLabel: "Druckbett wird nivelliert" },
  {
    key: "printing_model",
    label: "Modell drucken",
    currentLabel: "Modell wird gedruckt",
    doneOnlyWhenJobEnds: true,
  },
  { key: "completed", label: "Abschluss", currentLabel: "Druck abgeschlossen" },
] as const;

const INDEX_BY_KEY = new Map(PRINT_PHASES.map((phase, index) => [phase.key, index]));

export type PrintPhaseProgress = Readonly<{
  activeIndex: number;
  highestIndex: number;
  resolvedKey: string;
  currentLabel: string;
  detail: string;
  seenKeys: readonly string[];
}>;

function normalizePhaseKey(rawKey: string): string {
  const normalized = String(rawKey || "").trim();
  return normalized === "nozzle_cleaning" ? "nozzle_cleaning_after" : normalized;
}

export function resolvePrintPhaseProgress(
  rawKey: string,
  previousHighestIndex = -1,
  fallbackLabel = "Druckstatus wird ermittelt",
  fallbackDetail = "Der nächste Druckerschritt wird erwartet.",
): PrintPhaseProgress {
  const normalized = normalizePhaseKey(rawKey);
  const candidate = INDEX_BY_KEY.get(normalized) ?? -1;

  if (candidate < 0) {
    return {
      activeIndex: previousHighestIndex,
      highestIndex: previousHighestIndex,
      resolvedKey: "",
      currentLabel: fallbackLabel,
      detail: fallbackDetail,
      seenKeys: PRINT_PHASES.slice(0, Math.max(0, previousHighestIndex + 1)).map((phase) => phase.key),
    };
  }

  const highestIndex = Math.max(previousHighestIndex, candidate);
  const activeIndex = highestIndex;
  const phase = PRINT_PHASES[activeIndex]!;
  return {
    activeIndex,
    highestIndex,
    resolvedKey: phase.key,
    currentLabel: phase.currentLabel || fallbackLabel,
    detail: phase.detail || fallbackDetail,
    seenKeys: PRINT_PHASES.slice(0, activeIndex + 1).map((item) => item.key),
  };
}

export function resolveTrackedPrintPhaseProgress(
  rawKey: string,
  seenKeys: ReadonlySet<string> = new Set(),
  fallbackLabel = "Druckstatus wird ermittelt",
  fallbackDetail = "Der nächste Druckerschritt wird erwartet.",
): PrintPhaseProgress {
  const previousHighestIndex = Math.max(
    -1,
    ...[...seenKeys].map((key) => INDEX_BY_KEY.get(key) ?? -1),
  );
  const progress = resolvePrintPhaseProgress(rawKey, previousHighestIndex, fallbackLabel, fallbackDetail);
  return {
    ...progress,
    seenKeys: [...new Set([...seenKeys, ...progress.seenKeys])],
  };
}