import type { PrinterCommand } from "./printer-command-policy.js";
import type { V6Printer } from "./v6-api.js";

export type PrinterIssue = Readonly<Record<string, unknown>>;

const OFFICIAL_WIKI = "https://wiki.bambulab.com/en/home";
const RETRY_CODE = /^(?:07|12)[0-9A-F]{2}-80(?:01|02|03|04|05|06|07|10|11|12|13|14|15|16)$/i;

function record(value: unknown): PrinterIssue {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as PrinterIssue
    : {};
}

export function escapeIssueHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

export function printerIssues(printer: V6Printer | null | undefined): PrinterIssue[] {
  const explicit = Array.isArray(printer?.issues)
    ? printer.issues.map(record).filter((item) => Object.keys(item).length > 0)
    : [];
  if (explicit.length) return explicit;

  const hms = Array.isArray(printer?.hms)
    ? printer.hms.map(record).filter((item) => Object.keys(item).length > 0)
    : [];
  if (hms.length) return hms;

  const code = String(printer?.error_code ?? "").trim();
  const message = String(printer?.error_message ?? "").trim();
  if (!code && !message) return [];
  return [{
    code: code || "UNBEKANNT",
    title: "Druckerfehler",
    message: message || "Der Drucker hat eine Störung gemeldet.",
    severity: "error",
    blocking: true,
    active: true,
    help_url: `${OFFICIAL_WIKI}?search=${encodeURIComponent(code || message)}`,
  }];
}

export function primaryPrinterIssue(printer: V6Printer | null | undefined): PrinterIssue | null {
  return printerIssues(printer)[0] ?? null;
}

export function issueCode(issue: PrinterIssue | null | undefined): string {
  return String(issue?.code || issue?.code_compact || "UNBEKANNT");
}

export function issueTitle(issue: PrinterIssue | null | undefined): string {
  return String(issue?.title || "Druckerstörung");
}

export function issueMessage(issue: PrinterIssue | null | undefined): string {
  return String(issue?.message || "Der Drucker hat eine Störung gemeldet.");
}

export function issueSeverity(issue: PrinterIssue | null | undefined): "error" | "warning" | "info" {
  const value = String(issue?.severity || issue?.level || "warning").toLowerCase();
  if (value.includes("error") || value.includes("fatal") || value.includes("serious")) return "error";
  if (value.includes("info")) return "info";
  return "warning";
}

export function issueRecommendedCommand(issue: PrinterIssue | null | undefined): PrinterCommand {
  const explicit = String(issue?.recommended_action || issue?.action || "").toLowerCase();
  if (explicit === "retry" || explicit === "ams_retry" || explicit === "retry_ams") return "retry";
  if (explicit === "resume") return "resume";
  return RETRY_CODE.test(issueCode(issue)) ? "retry" : "resume";
}

export function issueActionLabel(issue: PrinterIssue | null | undefined): string {
  return issueRecommendedCommand(issue) === "retry"
    ? "Problem behoben – erneut versuchen"
    : "Problem behoben – fortsetzen";
}

export function issueHelpUrl(issue: PrinterIssue | null | undefined): string {
  const configured = String(issue?.help_url || issue?.qr_url || "").trim();
  if (/^https:\/\/([a-z0-9-]+\.)*bambulab\.com(?:\/|$)/i.test(configured)) return configured;
  const code = issueCode(issue);
  return `${OFFICIAL_WIKI}?search=${encodeURIComponent(code)}`;
}

export function issueQrImageUrl(issue: PrinterIssue | null | undefined): string {
  const target = issueHelpUrl(issue);
  return `https://quickchart.io/qr?size=220&margin=1&ecLevel=M&text=${encodeURIComponent(target)}`;
}

export function issueSignature(printer: V6Printer | null | undefined): string {
  return printerIssues(printer)
    .map((issue) => `${issueCode(issue)}:${issueMessage(issue)}:${issueSeverity(issue)}`)
    .sort()
    .join("|");
}

export function issueMarkup(issue: PrinterIssue, compact = false): string {
  const code = issueCode(issue);
  const title = issueTitle(issue);
  const message = issueMessage(issue);
  const severity = issueSeverity(issue);
  const help = issueHelpUrl(issue);
  const qr = issueQrImageUrl(issue);
  const action = issueRecommendedCommand(issue) === "retry" ? "AMS-/Filamentvorgang erneut versuchen" : "Druck fortsetzen";
  return `<article class="printer-issue-card ${severity} ${compact ? "compact" : ""}">
    <div class="printer-issue-copy">
      <span class="printer-issue-level">${escapeIssueHtml(severity === "error" ? "FEHLER" : severity === "warning" ? "WARNUNG" : "HINWEIS")}</span>
      <strong>${escapeIssueHtml(title)}</strong>
      <code>${escapeIssueHtml(code)}</code>
      <p>${escapeIssueHtml(message)}</p>
      <small class="printer-issue-action">Nächste Aktion: ${escapeIssueHtml(action)}</small>
      <a href="${escapeIssueHtml(help)}" target="_blank" rel="noopener noreferrer">Offizielle Bambu-Hilfe öffnen ↗</a>
    </div>
    <a class="printer-issue-qr" href="${escapeIssueHtml(help)}" target="_blank" rel="noopener noreferrer" title="Hilfe mit dem Smartphone öffnen">
      <img src="${escapeIssueHtml(qr)}" alt="QR-Code zur offiziellen Bambu-Hilfe für ${escapeIssueHtml(code)}" loading="lazy" referrerpolicy="no-referrer">
      <small>QR-Code scannen</small>
    </a>
  </article>`;
}

export const PRINTER_ISSUE_STYLES = `
  .printer-issue-card{display:grid;grid-template-columns:minmax(0,1fr) 126px;gap:14px;padding:13px;border:1px solid #9c7330;border-radius:11px;background:#30230f;color:#fff1cc}
  .printer-issue-card.error{border-color:#b64d5a;background:#35171d;color:#ffe3e7}
  .printer-issue-card.info{border-color:#377ca5;background:#10283a;color:#ddf3ff}
  .printer-issue-copy{min-width:0}.printer-issue-copy strong,.printer-issue-copy code,.printer-issue-copy p,.printer-issue-copy a,.printer-issue-action{display:block}
  .printer-issue-copy strong{margin-top:5px;font-size:16px}.printer-issue-copy code{width:max-content;max-width:100%;margin-top:6px;padding:4px 7px;border:1px solid currentColor;border-radius:6px;font:700 12px Consolas,monospace;overflow-wrap:anywhere}
  .printer-issue-copy p{margin:8px 0;color:inherit;line-height:1.45}.printer-issue-copy a{width:max-content;max-width:100%;margin-top:7px;color:#8edcff;font-weight:700;text-decoration:none;overflow-wrap:anywhere}.printer-issue-action{color:#ffd289;font-weight:800}
  .printer-issue-level{display:inline-block;padding:3px 6px;border:1px solid currentColor;border-radius:999px;font-size:9px;font-weight:800;letter-spacing:.08em}
  .printer-issue-qr{display:grid;place-items:center;align-content:center;gap:5px;padding:7px;border-radius:9px;background:#fff;color:#16212b;text-decoration:none}.printer-issue-qr img{display:block;width:108px;height:108px;image-rendering:pixelated}.printer-issue-qr small{font-size:9px;font-weight:800}
  .printer-issue-card.compact{grid-template-columns:minmax(0,1fr) 100px;padding:10px}.printer-issue-card.compact .printer-issue-qr img{width:84px;height:84px}
  @media(max-width:560px){.printer-issue-card,.printer-issue-card.compact{grid-template-columns:1fr}.printer-issue-qr{grid-template-columns:auto 1fr;justify-content:start}.printer-issue-qr img{width:88px;height:88px}}
`;