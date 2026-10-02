export type ProgressTone = "blue" | "green" | "amber" | "red";

export type ProgressView = Readonly<{
  label: string;
  detail?: string;
  value?: number | null;
  indeterminate?: boolean;
  compact?: boolean;
  tone?: ProgressTone;
}>;

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

export function clampProgress(value: unknown): number {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, numeric));
}

export function progressMarkup(view: ProgressView): string {
  const value = clampProgress(view.value ?? 0);
  const indeterminate = view.indeterminate === true;
  const percentage = indeterminate ? "" : `${Math.round(value)} %`;
  const classes = [
    "v6-progress",
    view.compact ? "compact" : "",
    indeterminate ? "indeterminate" : "",
    `tone-${view.tone ?? "blue"}`,
  ].filter(Boolean).join(" ");
  const aria = indeterminate
    ? 'role="progressbar" aria-busy="true"'
    : `role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(value)}"`;
  return `<section class="${classes}" ${aria}>
    <div class="v6-progress-head">
      <strong>${escapeHtml(view.label)}</strong>
      <span>${escapeHtml(percentage)}</span>
    </div>
    ${view.detail ? `<div class="v6-progress-detail">${escapeHtml(view.detail)}</div>` : ""}
    <div class="v6-progress-track"><span class="v6-progress-fill" style="--v6-progress:${value}%"></span></div>
  </section>`;
}

export const PROGRESS_STYLES = `
  .v6-progress{--progress-a:#00beff;--progress-b:#00ffb1;display:grid;gap:6px;padding:10px 11px;border:1px solid #2d526f;border-radius:10px;background:linear-gradient(180deg,#102033,#0d1927);box-shadow:inset 0 1px #ffffff0a}
  .v6-progress.compact{gap:4px;padding:7px 9px;border-radius:8px}
  .v6-progress-head{display:flex;align-items:center;justify-content:space-between;gap:12px;min-width:0}
  .v6-progress-head strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#eaf7ff;font-size:12px}
  .v6-progress-head span{flex:none;color:#b8d9ed;font:700 11px ui-monospace,SFMono-Regular,Consolas,monospace}
  .v6-progress-detail{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#829bb0;font-size:10px}
  .v6-progress-track{position:relative;height:8px;overflow:hidden;border-radius:999px;background:rgba(128,128,128,.18)}
  .v6-progress.compact .v6-progress-track{height:7px}
  .v6-progress-fill{position:absolute;inset:0 auto 0 0;width:var(--v6-progress);max-width:100%;border-radius:inherit;background:linear-gradient(90deg,var(--progress-a),var(--progress-b));box-shadow:0 0 12px var(--progress-a);transition:width .18s ease}
  .v6-progress-fill::after{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent 0 34%,#ffffff59 47%,transparent 60%);transform:translateX(-130%);animation:v6-progress-shine 1.8s ease-in-out infinite}
  .v6-progress.indeterminate .v6-progress-fill{width:38%;animation:v6-progress-slide 1.15s ease-in-out infinite}
  .v6-progress.tone-green{--progress-a:#00d77b;--progress-b:#9dff7a;border-color:#2b6848}
  .v6-progress.tone-amber{--progress-a:#ff9100;--progress-b:#ffe066;border-color:#775b2c}
  .v6-progress.tone-red{--progress-a:#ef596d;--progress-b:#ff9b91;border-color:#75404a}
  @keyframes v6-progress-slide{0%{left:-42%}50%{left:32%}100%{left:104%}}
  @keyframes v6-progress-shine{0%,38%{transform:translateX(-130%)}75%,100%{transform:translateX(180%)}}
  @media(prefers-reduced-motion:reduce){.v6-progress-fill,.v6-progress-fill::after{animation:none!important;transition:none!important}.v6-progress.indeterminate .v6-progress-fill{left:31%;width:38%}}
`;