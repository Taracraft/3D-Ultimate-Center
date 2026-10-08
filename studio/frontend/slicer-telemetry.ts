import type { SliceJob, SliceSlicerProgress } from "./slicing-api.js";

const ACTIVE = new Set(["queued", "running", "cancelling"]);
const clampPercent = (value: unknown): number => Math.max(0, Math.min(100, Number(value) || 0));
const finite = (value: unknown): number | null => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};
const timeMs = (value: unknown): number | null => {
  const parsed = new Date(String(value || "")).getTime();
  return Number.isFinite(parsed) ? parsed : null;
};

const MESSAGE_TRANSLATIONS: readonly [string, string][] = [
  ["start to load files", "Dateien werden geladen"],
  ["loading files finished", "Dateien wurden geladen"],
  ["slicing begins", "Slicing wird gestartet"],
  ["starting the slicing process", "Slicing wird gestartet"],
  ["slicing model", "Modell wird geslicet"],
  ["slicing supports", "Stützstrukturen werden berechnet"],
  ["slicing volumes", "Volumen werden geslicet"],
  ["slicing mesh", "Mesh wird verarbeitet"],
  ["post process mesh", "Mesh wird nachbearbeitet"],
  ["fixing slicing errors", "Geometrie wird geprüft und korrigiert"],
  ["mmu segmentation", "Materialsegmente werden berechnet"],
  ["fuzzy skin segmentation", "Fuzzy-Skin-Segmente werden berechnet"],
  ["removing top empty layers", "Leere obere Layer werden entfernt"],
  ["generate thumbnails", "Vorschaubilder werden erzeugt"],
  ["exporting 3mf", "3MF wird exportiert"],
  ["slicing finished", "Slicing ist abgeschlossen"],
  ["all done, success", "Slicing ist abgeschlossen"],
];

export function translateSlicerMessage(value: unknown): string {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const lower = raw.toLocaleLowerCase("en-US");
  for (const [needle, label] of MESSAGE_TRANSLATIONS) {
    if (lower.includes(needle)) return label;
  }
  return raw;
}

export function nativeSlicerProgress(job: SliceJob | null | undefined): SliceSlicerProgress | null {
  const progress = job?.slicer_progress;
  return progress && progress.source === "bambu_cli_pipe" ? progress : null;
}

export function slicerProgressPercent(job: SliceJob): number {
  const native = nativeSlicerProgress(job);
  if (native) return clampPercent(native.total_percent);
  if (job.status === "queued") return 12;
  if (job.status === "running") return 62;
  if (job.status === "cancelling") return 88;
  return 100;
}

export function slicerActivityLabel(job: SliceJob): string {
  const native = nativeSlicerProgress(job);
  if (native?.warning) return `Warnung: ${translateSlicerMessage(native.warning)}`;
  if (native?.message) return translateSlicerMessage(native.message);
  if (job.status === "queued") return "Auftrag wartet auf den Slicing-Server";
  if (job.status === "running") return "Modell wird geslicet";
  if (job.status === "cancelling") return "Abbruch wird angefordert";
  if (job.status === "succeeded") return "G-Code wurde erfolgreich erzeugt";
  if (job.status === "cancelled") return "Auftrag wurde abgebrochen";
  if (job.status === "interrupted") return "Auftrag wurde unterbrochen";
  return job.error || "Slicing fehlgeschlagen";
}

export function slicerEtaSeconds(job: SliceJob, nowMs = Date.now()): number | null {
  if (!ACTIVE.has(job.status)) return job.status === "succeeded" ? 0 : null;
  const progress = nativeSlicerProgress(job);
  if (!progress) return null;
  const currentPercent = clampPercent(progress.total_percent);
  if (currentPercent >= 100) return 0;
  if (currentPercent < 3) return null;

  const startedAt = timeMs(progress.started_at) ?? timeMs(progress.history?.[0]?.at);
  if (startedAt === null || nowMs <= startedAt) return finite(progress.eta_seconds);
  const elapsedSeconds = Math.max(0.001, (nowMs - startedAt) / 1000);
  const overallRate = currentPercent / elapsedSeconds;
  if (!(overallRate > 0)) return finite(progress.eta_seconds);

  const history = (progress.history || [])
    .map((entry) => ({ at: timeMs(entry.at), percent: clampPercent(entry.total_percent) }))
    .filter((entry): entry is { at: number; percent: number } => entry.at !== null && entry.percent <= currentPercent)
    .filter((entry, index, all) => index === 0 || entry.percent > all[index - 1]!.percent);
  const currentEvent = history[history.length - 1];
  let rate = overallRate;
  if (currentEvent) {
    let anchor: { at: number; percent: number } | undefined;
    for (let index = history.length - 2; index >= 0; index -= 1) {
      const candidate = history[index]!;
      if (currentPercent - candidate.percent >= 5 || currentEvent.at - candidate.at >= 45_000) {
        anchor = candidate;
        break;
      }
    }
    if (anchor) {
      const progressed = currentPercent - anchor.percent;
      const recentSeconds = Math.max(0.001, (nowMs - anchor.at) / 1000);
      const recentRate = progressed / recentSeconds;
      if (recentRate > 0) {
        const bounded = Math.max(overallRate * 0.25, Math.min(overallRate * 4, recentRate));
        rate = overallRate * 0.35 + bounded * 0.65;
      } else if (nowMs - currentEvent.at > 20_000) {
        rate = overallRate * 0.5;
      }
    } else if (nowMs - currentEvent.at > 20_000) {
      rate = overallRate * 0.65;
    }
  }

  const calculated = (100 - currentPercent) / rate;
  const server = finite(progress.eta_seconds);
  const combined = server !== null && server >= 0 ? calculated * 0.35 + server * 0.65 : calculated;
  return Number.isFinite(combined) && combined >= 0 && combined <= 24 * 60 * 60 ? combined : null;
}
