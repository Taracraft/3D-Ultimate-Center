import type { FloatingSupportIssue } from "./floating-support-analysis.js";

export type SupportDecision = "cancel" | "enable" | "continue";
export type SupportWarning = Readonly<{ result: Promise<SupportDecision>; cancel: () => void }>;

function esc(value: string): string {
  return value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}

export function supportWarningHtml(issues: readonly FloatingSupportIssue[]): string {
  const details = issues.map((issue) => {
    const facts: string[] = [];
    if (issue.floatingShellCount > 0) facts.push(`${issue.floatingShellCount} freischwebende(r) Bereich(e) · Höhe über Druckbett mindestens ${issue.minimumGapMm.toFixed(2)} mm`);
    if (issue.overhangTriangleCount > 0) {
      facts.push(`Abwärts gerichtete Flächen · Dreiecksspanne bis ${issue.maxOverhangMm.toFixed(2)} mm`);
      facts.push(`Flächenwinkel zur Horizontalen bis ${issue.maxOverhangAngleDeg.toFixed(1)}°`);
    }
    if (issue.bridgeOverhangMm > 0) facts.push("Mögliche Brücke / horizontale Unterseite");
    return `<li><b>${esc(issue.name)}</b> · ${facts.map(esc).join(" · ")}</li>`;
  }).join("");
  return `<section class="error-modal-panel"><header class="error-modal-head"><strong id="support-warning-title">Support empfohlen</strong></header><div class="error-modal-body">Diese Objekte enthalten freischwebende Bereiche oder mögliche kritische Überhänge. Ohne Support können Bereiche absacken oder in der Luft gedruckt werden.<ul class="support-warning-list">${details}</ul><p>Geometrische Vorprüfung, keine Druckgarantie. Die Dreiecksspanne ist nicht die tatsächliche ungestützte Brückenlänge. Support und Layeransicht vor dem Druck prüfen.</p></div><footer class="support-warning-actions"><button data-support-decision="cancel" type="button" autofocus>Abbrechen</button><button class="primary" data-support-decision="enable" type="button">Support auswählen</button><button class="danger" data-support-decision="continue" type="button">Auf eigene Gefahr ohne Support</button></footer></section>`;
}

// Native modal top layer: no competition with progress-popup z-index values.
export function openSupportWarning(root: ShadowRoot, issues: readonly FloatingSupportIssue[]): SupportWarning {
  const dialog = root.ownerDocument.createElement("dialog");
  dialog.id = "support-warning-modal";
  dialog.className = "error-modal support-warning-modal support-warning-dialog";
  dialog.setAttribute("aria-labelledby", "support-warning-title");
  dialog.innerHTML = supportWarningHtml(issues);
  let settled = false;
  let resolveResult!: (decision: SupportDecision) => void;
  const result = new Promise<SupportDecision>((resolve) => { resolveResult = resolve; });
  const finish = (decision: SupportDecision): void => {
    if (settled) return;
    settled = true;
    if (dialog.open) dialog.close();
    dialog.remove();
    resolveResult(decision);
  };
  for (const decision of ["cancel", "enable", "continue"] as const) {
    dialog.querySelector<HTMLButtonElement>(`[data-support-decision="${decision}"]`)?.addEventListener("click", () => finish(decision));
  }
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); finish("cancel"); });
  dialog.addEventListener("close", () => finish("cancel"));
  root.append(dialog);
  try { dialog.showModal(); }
  catch (error) { finish("cancel"); throw error; }
  return { result, cancel: () => finish("cancel") };
}
