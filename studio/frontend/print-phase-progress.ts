export type PrintPhaseDefinition = Readonly<{
  key: string;
  label: string;
  currentLabel: string;
  detail?: string;
  doneOnlyWhenJobEnds?: boolean;
}>;

export const PRINT_PHASES: readonly PrintPhaseDefinition[] = [
  { key: "bed_heating", label: "Druckbett aufheizen", currentLabel: "Druckbett wird aufgeheizt" },
  { key: "homing", label: "Druckkopf referenzieren", currentLabel: "Druckkopf wird referenziert", detail: "Der Druckkopf fährt seine Referenzposition an." },
  { key: "filament_loading", label: "Filament einziehen", currentLabel: "Filament wird eingezogen" },
  { key: "flow_calibration", label: "Fluss kalibrieren", currentLabel: "Filamentfluss wird kalibriert" },
  { key: "mechanical_check", label: "Mechanik prüfen", currentLabel: "Mechanik wird geprüft" },
  { key: "nozzle_cleaning_after", label: "Druckkopf reinigen", currentLabel: "Druckkopf wird gereinigt", detail: "Die Düse wird am Wischer gereinigt." },
  { key: "bed_leveling", label: "Druckbett nivellieren", currentLabel: "Druckbett wird nivelliert" },
  { key: "printing_model", label: "Modell drucken", currentLabel: "Modell wird gedruckt", doneOnlyWhenJobEnds: true },
  { key: "completed", label: "Abschluss", currentLabel: "Druck abgeschlossen" },
] as const;

const INDEX_BY_KEY = new Map(PRINT_PHASES.map((phase, index) => [phase.key, index]));
const CLEANING_INDEX = INDEX_BY_KEY.get("nozzle_cleaning_after") ?? 5;
const PRINTING_MODEL_INDEX = INDEX_BY_KEY.get("printing_model") ?? 7;

export type PrintPhaseProgress = Readonly<{ activeIndex:number; highestIndex:number; resolvedKey:string; currentLabel:string; detail:string; }>;
export type TrackedPrintPhaseProgress = PrintPhaseProgress & Readonly<{ seenKeys: readonly string[] }>;

export function resolvePrintPhaseProgress(rawKey:string, previousHighestIndex=-1, fallbackLabel="Druckstatus wird ermittelt", fallbackDetail="Der nächste Druckerschritt wird erwartet."): PrintPhaseProgress {
  const normalized=String(rawKey||"").trim();
  let candidate=-1;
  if (normalized === "nozzle_cleaning") candidate = CLEANING_INDEX;
  else candidate = INDEX_BY_KEY.get(normalized) ?? -1;
  if (candidate < 0) return { activeIndex:previousHighestIndex, highestIndex:previousHighestIndex, resolvedKey:"", currentLabel:fallbackLabel, detail:fallbackDetail };
  const highestIndex=Math.max(previousHighestIndex,candidate);
  const phase=PRINT_PHASES[highestIndex]!;
  return { activeIndex:highestIndex, highestIndex, resolvedKey:phase.key, currentLabel:phase.currentLabel||fallbackLabel, detail:phase.detail||fallbackDetail };
}

export function resolveSafePrintPhaseProgress(rawKey:string, previousHighestIndex:number, modelStarted:boolean, fallbackLabel="Druckstatus wird ermittelt", fallbackDetail="Der nächste Druckerschritt wird erwartet."): PrintPhaseProgress {
  const normalized=String(rawKey||"").trim();
  const safePreviousHighest=!modelStarted && previousHighestIndex >= PRINTING_MODEL_INDEX ? -1 : previousHighestIndex;
  if (!modelStarted && normalized === "printing_model") return resolvePrintPhaseProgress("",safePreviousHighest,"Druckvorbereitung läuft","Der erste Modell-Layer wurde noch nicht bestätigt.");
  return resolvePrintPhaseProgress(normalized,safePreviousHighest,fallbackLabel,fallbackDetail);
}

export function resolveTrackedPrintPhaseProgress(rawKey:string, previousSeenKeys:readonly string[]=[], modelStarted=false, fallbackLabel="Druckstatus wird ermittelt", fallbackDetail="Der nächste Druckerschritt wird erwartet."): TrackedPrintPhaseProgress {
  const seen=new Set(previousSeenKeys.filter((key)=>INDEX_BY_KEY.has(key)));
  const normalized=String(rawKey||"").trim();
  let resolvedKey=normalized;
  if (normalized === "nozzle_cleaning") resolvedKey="nozzle_cleaning_after";
  const effectiveModelStarted=modelStarted || seen.has("printing_model");
  if (resolvedKey === "printing_model" && !effectiveModelStarted) {
    const indices=[...seen].map((key)=>INDEX_BY_KEY.get(key)??-1).filter((index)=>index>=0);
    return { activeIndex:-1, highestIndex:indices.length?Math.max(...indices):-1, resolvedKey:"", currentLabel:"Druckvorbereitung läuft", detail:"Der erste Modell-Layer wurde noch nicht bestätigt.", seenKeys:[...seen] };
  }
  const candidate=INDEX_BY_KEY.get(resolvedKey)??-1;
  if (candidate < 0) {
    const indices=[...seen].map((key)=>INDEX_BY_KEY.get(key)??-1).filter((index)=>index>=0);
    return { activeIndex:-1, highestIndex:indices.length?Math.max(...indices):-1, resolvedKey:"", currentLabel:fallbackLabel, detail:fallbackDetail, seenKeys:[...seen] };
  }
  const phase=PRINT_PHASES[candidate]!;
  seen.add(phase.key);
  const indices=[...seen].map((key)=>INDEX_BY_KEY.get(key)??-1).filter((index)=>index>=0);
  return { activeIndex:candidate, highestIndex:indices.length?Math.max(...indices):candidate, resolvedKey:phase.key, currentLabel:phase.currentLabel||fallbackLabel, detail:phase.detail||fallbackDetail, seenKeys:[...seen] };
}
