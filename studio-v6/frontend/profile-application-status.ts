import type { SliceProfileApplication } from "./slicing-api.js";

export const PROFILE_APPLICATION_STYLES = `
  .profile-proof{display:grid;gap:7px;margin-top:10px}
  .profile-proof-step{display:grid;grid-template-columns:24px minmax(0,1fr);gap:8px;align-items:start;padding:8px;border:1px solid #34404a;border-radius:8px;background:#171d22}
  .profile-proof-step.done{border-color:#2c7650;background:#11261a}
  .profile-proof-mark{display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#313a42;color:#9da8b1;font-weight:900}
  .profile-proof-step.done .profile-proof-mark{background:#1d5d3a;color:#a9f5c4}
  .profile-proof-copy b,.profile-proof-copy small{display:block}
  .profile-proof-copy b{color:#edf4f8;font-size:12px}
  .profile-proof-copy small{margin-top:2px;color:#8f9ca5;font-size:10px;line-height:1.4}
`;

const esc = (value: unknown): string => String(value ?? "").replace(
  /[&<>"']/g,
  (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character),
);

export function profileApplicationSummary(application?: SliceProfileApplication): string {
  if (!application) return "Profilnachweis wird geladen";
  const mark = (value: boolean): string => value ? "✓" : "…";
  return [
    `${mark(application.selected)} gewählt`,
    `${mark(application.applied)} im Slicer angewandt`,
    `${mark(application.gcode_confirmed)} im Artefakt bestätigt`,
  ].join(" · ");
}

export function profileApplicationMarkup(application?: SliceProfileApplication): string {
  if (!application) {
    return '<div class="profile-proof"><article class="profile-proof-step"><span class="profile-proof-mark">…</span><span class="profile-proof-copy"><b>Profilnachweis wird geladen</b><small>Der Slicerauftrag hat noch keinen bestätigten Profilstatus geliefert.</small></span></article></div>';
  }
  const processName = application.process?.name || application.process?.profile_id || "Prozessprofil";
  const selectedSettings = Math.max(0, Number(application.process?.selected_setting_count) || 0);
  const confirmedSettings = Math.max(0, Number(application.process?.gcode_confirmed_setting_count) || 0);
  const filamentProfiles = Math.max(0, Number(application.filament_profile_count) || 0);
  const materialChannels = Math.max(0, Number(application.material_channel_count) || 0);
  const steps = [
    {
      done: application.selected,
      label: "Gewählt",
      detail: `${processName} · ${selectedSettings} Prozesseinstellung(en) · ${filamentProfiles} Filamentprofil(e)`,
    },
    {
      done: application.applied,
      label: "Im Slicer angewandt",
      detail: `Prozessvertrag und ${materialChannels} Materialkanal/-kanäle wurden bei der nativen Materialisierung bestätigt.`,
    },
    {
      done: application.gcode_confirmed,
      label: "Im Artefakt bestätigt",
      detail: application.confirmation_source === "parsed_gcode_header_and_toolpath"
        ? `${confirmedSettings} Prozesseinstellung(en), Materialkanäle, Farben und Filamentarten stimmen mit analysiertem G-Code-Header und Toolpath überein.`
        : "Die Prüfung des erzeugten G-Code-3MF ist noch nicht vollständig bestätigt.",
    },
  ] as const;
  return `<div class="profile-proof">${steps.map((step) => `<article class="profile-proof-step ${step.done ? "done" : "pending"}"><span class="profile-proof-mark">${step.done ? "✓" : "…"}</span><span class="profile-proof-copy"><b>${esc(step.label)}</b><small>${esc(step.detail)}</small></span></article>`).join("")}</div>`;
}

export const PROCESS_VALUE_PROOF_STYLES = `
  .process-values{grid-column:1/-1;overflow:auto;max-height:220px;padding:8px}
  .process-values table{width:100%;border-collapse:collapse;font-size:10px;text-align:left}
  .process-values caption{text-align:left;font-weight:700;margin-bottom:5px}
  .process-values th,.process-values td{padding:5px;border-bottom:1px solid #34404a;vertical-align:top}
  .process-values .mismatch{color:#ffb3b3}.process-values .confirmed{color:#a9f5c4}
`;

export function processValueProofMarkup(application?: SliceProfileApplication): string {
  const rows = application?.process?.numeric_value_proof;
  if (!rows?.length) return "";
  const value = (raw: unknown): string => {
    if (raw === null || raw === undefined) return "Nicht nachgewiesen";
    return esc(Array.isArray(raw) ? raw.join(" / ") : raw);
  };
  return `<div class="process-values"><table><caption>Prozesswerte · Einzelprüfung</caption><thead><tr><th scope="col">Parameter</th><th scope="col">Profil</th><th scope="col">Angefordert</th><th scope="col">Angewandt</th><th scope="col">G-Code</th><th scope="col">Nachweis</th></tr></thead><tbody>${rows.map((row) => {
    const status = row.status === "confirmed" ? "confirmed" : row.status === "mismatch" ? "mismatch" : "unverified";
    const label = status === "confirmed" ? "Bestätigt" : status === "mismatch" ? "Abweichung" : "Nicht nachgewiesen";
    return `<tr class="${status}"><th scope="row">${esc(row.label)} (${esc(row.unit)})${row.overridden ? " · manuell" : ""}</th><td>${value(row.profile_value)}</td><td>${value(row.requested_value)}</td><td>${value(row.applied_value)}</td><td>${value(row.gcode_value)}</td><td>${label}</td></tr>`;
  }).join("")}</tbody></table></div>`;
}
