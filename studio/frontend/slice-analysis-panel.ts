import type {
  SliceAnalysisFeature,
  SliceAnalysisMaterial,
  SliceGcodeAnalysis,
  SliceJob,
} from "./slicing-api.js";
import type { StudioJob, StudioPrinter } from "./studio-api.js";

const FEATURE_LABELS: Readonly<Record<string, string>> = {
  inner_wall: "Innenwand",
  outer_wall: "Außenwand",
  sparse_infill: "Innenfüllung",
  internal_solid_infill: "Massive Innenfüllung",
  top_surface: "Oberseite",
  bottom_surface: "Unterseite",
  gap_infill: "Lückenfüllung",
  bridge: "Brücke",
  overhang_wall: "Überhangwand",
  floating_vertical_shell: "Freistehende Hülle",
  support: "Stützstruktur",
  support_interface: "Support-Kontaktfläche",
  brim: "Brim",
  raft: "Raft",
  skirt: "Skirt",
  prime_tower: "Reinigungsturm",
  flush_waste: "Spülabfall",
  custom: "Benutzerdefiniert",
  other: "Sonstige",
};

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function numeric(value: unknown): number | null {
  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

function formatNumber(value: unknown, digits = 2): string {
  const number = numeric(value);
  return number === null
    ? "–"
    : number.toLocaleString("de-DE", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
}

function formatDuration(value: unknown): string {
  const raw = numeric(value);
  if (raw === null) return "–";
  const total = Math.max(0, Math.round(raw));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m ${seconds}s`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  return `${minutes}m ${seconds}s`;
}

function featureLabel(feature: SliceAnalysisFeature): string {
  return FEATURE_LABELS[feature.key] || feature.label || feature.key;
}

function colorValue(value: unknown): string {
  const color = String(value || "#506070");
  return /^#[0-9a-f]{6}$/i.test(color) ? color : "#506070";
}

export class SliceAnalysisPanel extends HTMLElement {
  #job: SliceJob | null = null;
  #printJob: StudioJob | null = null;
  #printer: StudioPrinter | null = null;
  #collapsed = false;

  set job(value: SliceJob | null) {
    this.#job = value;
    this.#render();
  }

  set printJob(value: StudioJob | null) {
    this.#printJob = value;
    this.#render();
  }

  set printer(value: StudioPrinter | null) {
    this.#printer = value;
    this.#render();
  }

  connectedCallback(): void {
    this.#render();
  }

  #analysis(): SliceGcodeAnalysis | null {
    return this.#job?.slice_result?.analysis ?? null;
  }

  #progress(): number | null {
    const value = numeric(
      this.#printJob?.progress ?? this.#printer?.progress,
    );
    return value === null ? null : Math.max(0, Math.min(100, value));
  }

  #remaining(analysis: SliceGcodeAnalysis): Readonly<{
    seconds: number;
    source: "printer" | "calculated";
  }> | null {
    const printerMinutes = numeric(this.#printer?.remaining_time_minutes);
    if (printerMinutes !== null && printerMinutes >= 0) {
      return { seconds: printerMinutes * 60, source: "printer" };
    }
    const jobSeconds = numeric(
      this.#printJob?.remaining_time_seconds
      ?? this.#printJob?.remaining_seconds,
    );
    if (jobSeconds !== null && jobSeconds >= 0) {
      return { seconds: jobSeconds, source: "printer" };
    }
    const progress = this.#progress();
    const total = numeric(analysis.time?.total_seconds);
    if (progress === null || total === null || progress <= 0 || progress >= 100) {
      return null;
    }
    return {
      seconds: total * (1 - progress / 100),
      source: "calculated",
    };
  }

  #materialRow(material: SliceAnalysisMaterial): string {
    return `<tr>
      <td><span class="material"><i style="background:${esc(colorValue(material.color))}"></i><span><strong>${esc(material.material || "Material")}</strong><small>${esc(material.name || "")}</small></span></span></td>
      <td>AMS ${esc(material.material_channel_number)}</td>
      <td>${formatNumber(material.weight_g)} g</td>
      <td>${formatNumber((numeric(material.length_mm) ?? 0) / 1000)} m</td>
      <td>${formatNumber(material.volume_cm3)} cm³</td>
    </tr>`;
  }

  #featureMaterials(feature: SliceAnalysisFeature): string {
    const values = Array.isArray(feature.materials) ? feature.materials : [];
    return values
      .filter((item) => (numeric(item.weight_g) ?? 0) > 0.0001)
      .map((item) => `AMS ${item.material_channel_number}: ${formatNumber(item.weight_g)} g`)
      .join(" · ") || "–";
  }

  #featureRow(feature: SliceAnalysisFeature): string {
    return `<tr>
      <td><strong>${esc(featureLabel(feature))}</strong><small>${esc(this.#featureMaterials(feature))}</small></td>
      <td>${formatDuration(feature.time_seconds)}${feature.time_estimated ? "*" : ""}</td>
      <td>${formatNumber(feature.weight_g)} g</td>
      <td>${formatNumber((numeric(feature.length_mm) ?? 0) / 1000)} m</td>
      <td>${formatNumber(feature.volume_cm3)} cm³</td>
    </tr>`;
  }

  #liveStatus(analysis: SliceGcodeAnalysis): string {
    if (!this.#printJob) return "";
    const progress = this.#progress();
    const remaining = this.#remaining(analysis);
    const stage = String(
      this.#printer?.print_stage_label
      || this.#printJob.status
      || "Druck läuft",
    );
    return `<div class="live">
      <span class="pulse"></span>
      <strong>${esc(stage)}</strong>
      <span>${progress === null ? "Fortschritt wird ermittelt" : `${formatNumber(progress, 0)} %`}</span>
      <span>${remaining ? `${formatDuration(remaining.seconds)} verbleibend${remaining.source === "calculated" ? " · berechnet" : " · Drucker-Livewert"}` : "Restzeit wird ermittelt"}</span>
    </div>`;
  }

  #featureByKey(analysis: SliceGcodeAnalysis, key: string): SliceAnalysisFeature | null {
    const features = Array.isArray(analysis.features) ? analysis.features : [];
    return features.find((feature) => feature.key === key) ?? null;
  }

  #supportAndOverhangNotice(analysis: SliceGcodeAnalysis): string {
    const support = this.#featureByKey(analysis, "support");
    const supportInterface = this.#featureByKey(analysis, "support_interface");
    const overhang = this.#featureByKey(analysis, "overhang_wall");
    const bridge = this.#featureByKey(analysis, "bridge");
    const supportSeconds = numeric(support?.time_seconds) ?? 0;
    const supportInterfaceSeconds = numeric(supportInterface?.time_seconds) ?? 0;
    const overhangSeconds = numeric(overhang?.time_seconds) ?? 0;
    const bridgeSeconds = numeric(bridge?.time_seconds) ?? 0;
    if (!supportSeconds && !supportInterfaceSeconds && !overhangSeconds && !bridgeSeconds) return "";
    const process = this.#job?.runtime_summary?.process as Readonly<Record<string, unknown>> | undefined;
    const supportEnabled = process?.support_enabled === true || supportSeconds > 0 || supportInterfaceSeconds > 0;
    const parts: string[] = [];
    if (supportSeconds > 0) parts.push(`Support ${formatDuration(supportSeconds)}`);
    if (supportInterfaceSeconds > 0) parts.push(`Interface ${formatDuration(supportInterfaceSeconds)}`);
    if (overhangSeconds > 0) parts.push(`Überhangwand ${formatDuration(overhangSeconds)}`);
    if (bridgeSeconds > 0) parts.push(`Brücken ${formatDuration(bridgeSeconds)}`);
    const supportTarget = process?.support_build_plate_only === false
      ? "Support auf Modellflächen erlaubt"
      : process?.support_build_plate_only === true
        ? "Support nur von der Druckplatte"
        : "Support-Ziel nicht im Jobprofil gemeldet";
    const message = supportEnabled
      ? `Bambu-/G-Code-Analyse: ${parts.join(" · ")}. ${supportTarget}.`
      : `Bambu-/G-Code-Analyse: ${parts.join(" · ")} erkannt, aber kein Support im erzeugten G-Code. Support-Einstellung vor dem Druck prüfen.`;
    return `<div class="note warning">${esc(message)}</div>`;
  }

  #timeSourceNotice(analysis: SliceGcodeAnalysis): string {
    const consistency = analysis.time?.consistency;
    const source = consistency?.source ? ` · Quelle ${consistency.source}` : "";
    const confidence = consistency?.status === "ok"
      ? "Zeitprüfung ok"
      : consistency?.status === "missing"
        ? "Zeitprüfung unvollständig"
        : consistency?.status === "mismatch"
          ? "Zeitprüfung widersprüchlich"
          : "Zeitprüfung ohne separate Konsistenzmeldung";
    return `<div class="note">Zeitquelle: Gesamt-, Modell- und Vorbereitungszeit stammen aus der G-Code-/Slicer-Analyse${esc(source)}. Live-Restzeit im Druckbetrieb kommt vom Drucker und kann davon abweichen. ${esc(confidence)}.</div>`;
  }

  #tower(analysis: SliceGcodeAnalysis): string {
    const tower = analysis.tower_safety;
    if (!tower?.present) {
      return '<span class="safe">Kein Reinigungsturm erforderlich</span>';
    }
    const bounds = tower.bounds;
    const detail = bounds
      ? `X ${formatNumber(bounds.min_x)}–${formatNumber(bounds.max_x)} · Y ${formatNumber(bounds.min_y)}–${formatNumber(bounds.max_y)} mm`
      : "Grenzen nicht verfügbar";
    return `<span class="${tower.inside_plate ? "safe" : "unsafe"}">${tower.inside_plate ? "✓ Reinigungsturm innerhalb der Platte" : "✕ Reinigungsturm außerhalb der Platte"}</span><small>${esc(detail)}</small>`;
  }

  #render(): void {
    if (!this.isConnected) return;
    const analysis = this.#analysis();
    if (!analysis) {
      this.hidden = true;
      this.innerHTML = "";
      return;
    }
    this.hidden = false;
    const materials = Array.isArray(analysis.materials) ? analysis.materials : [];
    const features = Array.isArray(analysis.features) ? analysis.features : [];
    const time = analysis.time ?? {};
    const totals = analysis.totals ?? {};
    const consistency = analysis.time?.consistency;
    const timeDelta = Math.abs(numeric(consistency?.delta_seconds) ?? 0);
    const timeDeltaText = timeDelta > 0 ? ` Delta ${formatDuration(timeDelta)}.` : "";
    const timeWarning = consistency?.status === "mismatch"
      ? `<div class="note warning">Zeitprüfung: ${esc(consistency.note || "G-Code-Zeitfelder widersprechen sich.")}${timeDeltaText} Gesamtzeit bitte mit Bambu Studio gegenprüfen.</div>`
      : consistency?.status === "missing"
        ? `<div class="note warning">Zeitprüfung: ${esc(consistency.note || "Nicht alle G-Code-Zeitfelder waren verfügbar.")} Gesamtzeit bitte mit Bambu Studio gegenprüfen.</div>`
        : "";

    this.innerHTML = `<style>
      :host{display:block;margin-top:7px;color:#eaf4ff;font:12px Segoe UI,sans-serif}:host([hidden]){display:none}*{box-sizing:border-box}.panel{overflow:hidden;border:1px solid #31516d;border-radius:8px;background:#0b1722}.head{display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid #253c51}.head h3{margin:0;font-size:13px}.head p{margin:0;color:#8da3b8;font-size:10px}.head-actions{display:flex;align-items:center;gap:8px;margin-left:auto}.tower{display:flex;align-items:center;gap:8px}.analysis-collapse{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;padding:0;border:1px solid #31506e;border-radius:5px;background:linear-gradient(180deg,#19324a,#102335);color:#9edfff;font-size:16px;font-weight:900;line-height:1;cursor:pointer;box-shadow:inset 0 1px #ffffff0b,0 2px 8px #0008}.analysis-collapse:hover{border-color:#53d1ff;background:linear-gradient(180deg,#1979a5,#115575);color:#fff}.analysis-body{display:block}.panel.collapsed .analysis-body{display:none}.panel.collapsed .head{border-bottom:0}.tower small{color:#8da3b8}.safe{color:#7bea9f}.unsafe{color:#ff8995}.live{display:flex;align-items:center;gap:14px;padding:7px 10px;border-bottom:1px solid #25445b;background:#10283a}.live strong{margin-right:auto}.pulse{width:8px;height:8px;border-radius:50%;background:#5cdd7f;box-shadow:0 0 0 4px #5cdd7f22}.summary{display:grid;grid-template-columns:repeat(6,minmax(95px,1fr));gap:6px;padding:8px}.metric{padding:7px 8px;border:1px solid #263d52;border-radius:6px;background:#0e1d2a}.metric span{display:block;color:#8299ae;font-size:9px;text-transform:uppercase}.metric strong{display:block;margin-top:2px;font-size:13px}.tables{display:grid;grid-template-columns:minmax(360px,.8fr) minmax(620px,1.4fr);gap:8px;padding:0 8px 8px}.box{overflow:auto;border:1px solid #263d52;border-radius:6px}.box h4{position:sticky;left:0;margin:0;padding:7px 8px;border-bottom:1px solid #263d52;background:#102232;font-size:11px}table{width:100%;border-collapse:collapse;white-space:nowrap}th,td{padding:6px 8px;border-bottom:1px solid #1d3042;text-align:right;font-size:10px}th{color:#8ea5ba;background:#0d1b28;font-weight:600}th:first-child,td:first-child{text-align:left}tr:last-child td{border-bottom:0}td small{display:block;color:#8096aa;font-size:9px}.material{display:flex;align-items:center;gap:7px}.material i{display:block;width:12px;height:12px;border:1px solid #ffffff55;border-radius:3px}.material span{min-width:0}.note{padding:0 9px 8px;color:#7f95a8;font-size:9px}.note.warning{color:#ffd37a;font-weight:700}@media(max-width:1100px){.summary{grid-template-columns:repeat(3,1fr)}.tables{grid-template-columns:1fr}.tower{align-items:flex-end;flex-direction:column;gap:2px}}@media(max-width:650px){.head{align-items:flex-start;flex-direction:column}.tower{margin-left:0;align-items:flex-start}.summary{grid-template-columns:repeat(2,1fr)}}
    </style><section class="panel ${this.#collapsed ? "collapsed" : ""}">
      <header class="head"><div><h3>G-Code-Druckanalyse</h3><p>Material-, Zeit- und Druckschrittwerte aus dem tatsächlich erzeugten G-Code</p></div><div class="head-actions"><div class="tower">${this.#tower(analysis)}</div><button class="analysis-collapse" id="analysis-collapse" type="button" aria-expanded="${this.#collapsed ? "false" : "true"}" title="${this.#collapsed ? "Materialzusammenfassung einblenden" : "Materialzusammenfassung einklappen"}">${this.#collapsed ? "⌄" : "⌃"}</button></div></header>
      <div class="analysis-body">
      ${this.#liveStatus(analysis)}
      <div class="summary">
        <div class="metric"><span>Gesamtzeit</span><strong>${formatDuration(time.total_seconds)}</strong></div>
        <div class="metric"><span>Modellzeit</span><strong>${formatDuration(time.model_seconds)}</strong></div>
        <div class="metric"><span>Vorbereitung</span><strong>${formatDuration(time.preparation_seconds)}</strong></div>
        <div class="metric"><span>Layer</span><strong>${esc(analysis.layer_count ?? "–")}</strong></div>
        <div class="metric"><span>Materialwechsel</span><strong>${esc(analysis.filament_change_count ?? "–")}</strong></div>
        <div class="metric"><span>Gesamtmaterial</span><strong>${formatNumber(totals.weight_g)} g</strong></div>
      </div>
      <div class="tables">
        <section class="box"><h4>Materialverbrauch</h4><table><thead><tr><th>Material</th><th>Kanal</th><th>Gewicht</th><th>Länge</th><th>Volumen</th></tr></thead><tbody>${materials.map((item) => this.#materialRow(item)).join("")}</tbody></table></section>
        <section class="box"><h4>Druckschritte</h4><table><thead><tr><th>Druckschritt / Materialanteile</th><th>Zeit</th><th>Gewicht</th><th>Länge</th><th>Volumen</th></tr></thead><tbody>${features.map((item) => this.#featureRow(item)).join("")}</tbody></table></section>
      </div>
      ${this.#supportAndOverhangNotice(analysis)}${timeWarning}${this.#timeSourceNotice(analysis)}<div class="note">* Zeiten je Druckschritt werden aus den G-Code-Bewegungen berechnet und auf die Bambu-Modellzeit skaliert. Gesamt-, Modell- und Vorbereitungszeit werden aus G-Code-Analyse und nativen Slicer-Metriken übernommen; bei widersprüchlichen Quellen wird eine Warnung angezeigt.</div>
      </div>
    </section>`;
    this.querySelector<HTMLButtonElement>("#analysis-collapse")?.addEventListener("click", () => {
      this.#collapsed = !this.#collapsed;
      this.#render();
    });
  }
}

if (!customElements.get("slice-analysis-panel")) {
  customElements.define("slice-analysis-panel", SliceAnalysisPanel);
}

