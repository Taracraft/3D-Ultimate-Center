import { V6_BRANDING } from "./branding.js";
import "./slicer-accordion.css";
import "./direct-print-panel.js";
import type { Ultimate3DDirectPrintPanel } from "./direct-print-panel.js";
import { createPlateSliceJob } from "./plate-slice-api.js";
import { ProfileApi, type V6ProfileCatalog, type V6ProfileSelection } from "./profile-api.js";
import { PROGRESS_STYLES, progressMarkup, type ProgressTone } from "./progress-ui.js";
import { PROFILE_APPLICATION_STYLES, profileApplicationMarkup } from "./profile-application-status.js";
import {
  analyzeGeometry,
  layerCount,
  layerZ,
  getCachedSliceSegmentsAtZ as sliceSegmentsAtZ,
  type GeometryAnalysis,
  type Segment2,
} from "./stl-layer-preview.js";
import {
  createSlicePlan,
  downloadSliceArtifact,
  fetchSliceJob,
  fetchSlicerProvider,
  inspectSliceModel,
  uploadSliceGeometry,
  type SliceJob,
  type SliceModelInspection,
  type SliceModelPlate,
  type SlicerProvider,
} from "./slicing-api.js";
import { slicingStore } from "./slicing-store.js";
import { parseStl, type MeshGeometry } from "./webgl-studio-viewport.js";

const ACTIVE = new Set(["queued", "running", "cancelling"]);

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function jobTone(status: string): ProgressTone {
  if (["failed", "interrupted"].includes(status)) return "red";
  if (["cancelled", "cancelling"].includes(status)) return "amber";
  if (status === "succeeded") return "green";
  return "blue";
}

export class Ultimate3DSlicerWorkspaceV3 extends HTMLElement {
  readonly #profiles = new ProfileApi();
  readonly #open = new Set<string>(["provider", "model", "plates", "layer", "status"]);
  #provider: SlicerProvider | null = null;
  #catalog: V6ProfileCatalog | null = null;
  #model: File | null = null;
  #inspection: SliceModelInspection | null = null;
  #plateIndex = 0;
  #geometry: MeshGeometry | null = null;
  #analysis: GeometryAnalysis | null = null;
  #height = 0.2;
  #layer = 0;
  #status = "Noch kein Modell geladen";
  #error = "";
  #job: SliceJob | null = null;
  #generation = 0;

  set file(value: File | null) {
    if (!value) return;
    this.#model = value;
    this.#inspection = null;
    this.#plateIndex = 0;
    this.#geometry = null;
    this.#analysis = null;
    this.#layer = 0;
    this.#job = null;
    this.#error = "";
    this.#status = `${value.name} wurde an den Slicer übergeben.`;
    this.#open.add("model");
    this.#open.add("plates");
    if (this.isConnected) void this.#prepare();
  }

  get file(): File | null { return this.#model; }

  connectedCallback(): void {
    this.#render();
    void this.#load();
    if (this.#model) void this.#prepare();
  }

  disconnectedCallback(): void {
    this.#generation += 1;
  }

  #selectedPlate(): SliceModelPlate | null {
    return this.#inspection?.plates.find((plate) => plate.plate_index === this.#plateIndex)
      ?? this.#inspection?.plates[0]
      ?? null;
  }

  async #load(): Promise<void> {
    try {
      [this.#provider, this.#catalog] = await Promise.all([
        fetchSlicerProvider(),
        this.#profiles.getCatalog(),
      ]);
      this.#error = "";
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    }
    this.#render();
  }

  async #prepare(): Promise<void> {
    const file = this.#model;
    if (!file) return;
    const generation = ++this.#generation;
    this.#status = "Modell und Druckplatten werden analysiert …";
    this.#error = "";
    this.#open.add("status");
    this.#render();
    try {
      const inspection = await inspectSliceModel(file);
      if (generation !== this.#generation) return;
      this.#inspection = inspection;
      if (!inspection.plates.some((plate) => plate.plate_index === this.#plateIndex)) {
        this.#plateIndex = inspection.plates[0]?.plate_index ?? 0;
      }
      if (inspection.format === "3mf") {
        this.#geometry = null;
        this.#analysis = null;
        this.#status = `${file.name}: ${inspection.plate_count} Druckplatte${inspection.plate_count === 1 ? "" : "n"} erkannt. Druckplatte ${this.#plateIndex + 1} ist ausgewählt.`;
      } else {
        this.#geometry = parseStl(await file.arrayBuffer());
        this.#analysis = analyzeGeometry(this.#geometry);
        this.#layer = 0;
        slicingStore.dispatch({ type: "layer_count", count: layerCount(this.#analysis, this.#height) });
        this.#status = `${this.#analysis.triangleCount.toLocaleString("de-DE")} Dreiecke analysiert`;
      }
    } catch (error) {
      if (generation !== this.#generation) return;
      this.#inspection = null;
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = "Vorbereitung fehlgeschlagen";
    }
    this.#render();
  }

  async #savePlan(): Promise<void> {
    if (!this.#model || !this.#analysis || !this.#catalog) return;
    this.#status = "Slice-Plan wird gespeichert …";
    this.#error = "";
    this.#render();
    try {
      const stored = await uploadSliceGeometry(this.#model);
      const plan = await createSlicePlan({
        name: `${this.#model.name} – Slice-Plan`,
        project_id: null,
        plate_id: String(this.#plateIndex),
        geometry_id: stored.geometry_id,
        profile_selection: this.#catalog.selection,
        layer_height_mm: this.#height,
        analysis: this.#analysis,
        preview: {
          mode: "geometry_cross_section",
          layer_count: layerCount(this.#analysis, this.#height),
        },
      });
      slicingStore.dispatch({ type: "plan_updated", plan });
      this.#status = "Slice-Plan dauerhaft gespeichert";
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = "Speichern fehlgeschlagen";
    }
    this.#render();
  }

  async #slice(): Promise<void> {
    if (!this.#model || !this.#inspection || !this.#provider?.capabilities.gcode_generation) return;
    const selectedPlate = this.#selectedPlate();
    if (!selectedPlate) return;
    const generation = ++this.#generation;
    this.#status = `Druckplatte ${selectedPlate.display_number} wird an den nativen Linux-Slicing-Server übertragen …`;
    this.#error = "";
    this.#open.add("status");
    this.#open.add("gcode");
    this.#render();
    try {
      this.#job = await createPlateSliceJob(this.#model, selectedPlate.plate_index);
      while (generation === this.#generation && this.#job && ACTIVE.has(this.#job.status)) {
        this.#status = this.#jobLabel(this.#job);
        this.#render();
        await new Promise((resolve) => window.setTimeout(resolve, 700));
        if (generation !== this.#generation || !this.#job) return;
        this.#job = await fetchSliceJob(this.#job.id);
      }
      if (generation !== this.#generation || !this.#job) return;
      this.#status = this.#jobLabel(this.#job);
      if (["failed", "interrupted"].includes(this.#job.status)) {
        throw new Error(this.#job.error || "Der Slicing-Server hat den Auftrag nicht abgeschlossen.");
      }
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
      this.#status = "G-Code-Erzeugung fehlgeschlagen";
    }
    this.#render();
  }


  async #download(): Promise<void> {
    if (this.#job?.status !== "succeeded") return;
    try {
      const artifact = await downloadSliceArtifact(this.#job.id);
      const url = URL.createObjectURL(artifact.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = artifact.filename;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      this.#status = artifact.sha256
        ? `G-Code-3MF geladen · SHA-256 ${artifact.sha256.slice(0, 12)}…`
        : "G-Code-3MF geladen";
    } catch (error) {
      this.#error = error instanceof Error ? error.message : String(error);
    }
    this.#render();
  }

  #downloadSource3mf(): void {
    if (!this.#model?.name.toLowerCase().endsWith(".3mf")) return;
    const url = URL.createObjectURL(this.#model);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = this.#model.name;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  #selectPlate(index: number): void {
    if (!this.#inspection?.plates.some((plate) => plate.plate_index === index)) return;
    this.#plateIndex = index;
    this.#job = null;
    this.#error = "";
    const plate = this.#selectedPlate();
    this.#status = `${plate?.name || `Druckplatte ${index + 1}`} ist für das Slicing ausgewählt.`;
    this.#render();
  }

  #jobLabel(job: SliceJob): string {
    if (job.status === "queued") return "Slicing-Server wartet auf die Ausführung …";
    if (job.status === "running") return `Bambu-Slicing für Druckplatte ${this.#plateIndex + 1} läuft …`;
    if (job.status === "cancelling") return "Slicing wird abgebrochen …";
    if (job.status === "succeeded") return `G-Code-3MF für Druckplatte ${this.#plateIndex + 1} ist fertig`;
    if (job.status === "cancelled") return "Slicing wurde abgebrochen";
    return job.error || "Slicing fehlgeschlagen";
  }

  #progress(): string {
    if (this.#job) {
      return progressMarkup({
        label: this.#jobLabel(this.#job),
        detail: this.#job.id,
        value: this.#job.status === "succeeded" ? 100 : 0,
        indeterminate: ACTIVE.has(this.#job.status),
        tone: jobTone(this.#job.status),
      });
    }
    return progressMarkup({
      label: this.#status,
      value: this.#model && this.#inspection ? 100 : 0,
      indeterminate: Boolean(this.#model && !this.#inspection && !this.#error),
      tone: this.#error ? "red" : "blue",
    });
  }

  #name(id: string | null | undefined): string {
    return id ? this.#catalog?.profiles.find((profile) => profile.id === id)?.name || id : "Nicht ausgewählt";
  }

  #profileRows(selection: V6ProfileSelection | null): string {
    if (!selection) return "Profile werden geladen …";
    const rows: Array<[string, string]> = [
      ["Drucker", this.#name(selection.printer_profile_id)],
      ["Düse", this.#name(selection.nozzle_profile_id)],
      ["Druckprofil", this.#name(selection.process_profile_id)],
      ["Druckplatte", this.#name(selection.build_plate_profile_id)],
    ];
    selection.filament_profile_ids.forEach((id, index) => rows.push([`Filament ${index + 1}`, this.#name(id)]));
    return `<div class="profile-rows">${rows.map(([label, value]) => `<div><span>${esc(label)}</span><b>${esc(value)}</b></div>`).join("")}</div>`;
  }

  #plateRows(): string {
    const inspection = this.#inspection;
    if (!inspection) return '<div class="card"><span class="muted">Datei wird analysiert …</span></div>';
    return `<div class="plate-list">${inspection.plates.map((plate) => `<label class="plate-option ${plate.plate_index === this.#plateIndex ? "selected" : ""}"><input type="radio" name="slice-plate" value="${plate.plate_index}" ${plate.plate_index === this.#plateIndex ? "checked" : ""}><span class="plate-number">${plate.display_number}</span><span><b>${esc(plate.name)}</b><small>${plate.object_count === null ? "Objektanzahl nicht angegeben" : `${plate.object_count} Objekt${plate.object_count === 1 ? "" : "e"}`}</small></span></label>`).join("")}</div>`;
  }

  #duration(seconds: number | null | undefined): string {
    if (!Number.isFinite(seconds)) return "–";
    const total = Math.max(0, Math.round(seconds ?? 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const rest = total % 60;
    return hours ? `${hours} h ${minutes} min` : minutes ? `${minutes} min ${rest} s` : `${rest} s`;
  }

  #preview(): string {
    if (this.#inspection?.format === "3mf") {
      const plate = this.#selectedPlate();
      return `<div class="empty"><strong>${esc(plate?.name || `Druckplatte ${this.#plateIndex + 1}`)} ausgewählt</strong><span>${this.#inspection.plate_count} Druckplatte${this.#inspection.plate_count === 1 ? "" : "n"} erkannt. Nur die ausgewählte Platte wird geslicet.</span></div>`;
    }
    if (!this.#geometry || !this.#analysis) return '<div class="empty"><strong>Noch keine Layer-Vorschau</strong><span>STL oder 3MF aus MakerWorld, Galerie oder CAD-Studio laden.</span></div>';
    const count = layerCount(this.#analysis, this.#height);
    const selected = Math.max(0, Math.min(this.#layer, count - 1));
    return this.#svg(sliceSegmentsAtZ(this.#geometry, layerZ(this.#analysis, this.#height, selected)), this.#analysis);
  }

  #svg(segments: readonly Segment2[], analysis: GeometryAnalysis): string {
    if (!segments.length) return '<div class="empty"><strong>Diese Schicht ist leer.</strong></div>';
    const width = Math.max(1, analysis.boundsMax[0] - analysis.boundsMin[0]);
    const depth = Math.max(1, analysis.boundsMax[1] - analysis.boundsMin[1]);
    const scale = Math.min(500 / width, 500 / depth);
    const ox = (540 - width * scale) / 2;
    const oy = (540 - depth * scale) / 2;
    const lines = segments.slice(0, 40000).map((segment) => {
      const x1 = ox + (segment.a[0] - analysis.boundsMin[0]) * scale;
      const y1 = 540 - (oy + (segment.a[1] - analysis.boundsMin[1]) * scale);
      const x2 = ox + (segment.b[0] - analysis.boundsMin[0]) * scale;
      const y2 = 540 - (oy + (segment.b[1] - analysis.boundsMin[1]) * scale);
      return `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}"/>`;
    }).join("");
    return `<svg class="layer" viewBox="0 0 540 540"><g>${lines}</g></svg>`;
  }

  #details(id: string, title: string, body: string, meta = ""): string {
    return `<details class="accordion" data-section="${esc(id)}" ${this.#open.has(id) ? "open" : ""}><summary><span>${esc(title)}</span>${meta ? `<small>${esc(meta)}</small>` : ""}</summary><div class="accordion-body">${body}</div></details>`;
  }

  #jobCard(): string {
    if (!this.#job) return "";
    const result = this.#job.slice_result;
    const active = ACTIVE.has(this.#job.status);
    const body = `<div class="metrics"><div><small>Druckplatte</small><b>${this.#plateIndex + 1}</b></div><div><small>Ausgabe</small><b>${esc(this.#job.output_file || "wird vorbereitet")}</b></div><div><small>Druckzeit</small><b>${this.#duration(result?.print_time_seconds)}</b></div><div><small>Filament</small><b>${Number.isFinite(result?.filament_used_g) ? `${Number(result?.filament_used_g).toFixed(2)} g` : "–"}</b></div><div><small>Artefakt</small><b>${this.#job.output_size_bytes ? `${(this.#job.output_size_bytes / 1024).toFixed(1)} KB` : "–"}</b></div></div>${profileApplicationMarkup(this.#job.profile_application)}${this.#job.error ? `<div class="error">${esc(this.#job.error)}</div>` : ""}<div class="job-actions">${this.#job.status === "succeeded" ? '<button class="primary" data-action="download">G-Code-3MF herunterladen</button>' : ""}</div>`;
    return `<section class="job" data-status="${esc(this.#job.status)}">${this.#details("gcode", "G-Code-Ausgabe", body, this.#jobLabel(this.#job))}</section>`;
  }

  #render(): void {
    const ready = Boolean(this.#provider?.capabilities.gcode_generation);
    const count = this.#analysis ? layerCount(this.#analysis, this.#height) : 0;
    const active = Boolean(this.#job && ACTIVE.has(this.#job.status));
    const canSlice = ready && this.#model && this.#inspection && !active;
    const left = [
      this.#details("provider", "Slicer-Provider", `<div class="card ${ready ? "ready" : "offline"}"><strong>${esc(this.#provider?.name || "Wird geladen …")}</strong><span class="muted">${esc(ready ? "Originalprofile lokal aufgelöst" : this.#provider?.server?.message || "Slicing-Server nicht bereit")}</span></div>`, ready ? "bereit" : "nicht bereit"),
      this.#details("model", "Geladenes Modell", `<div class="card"><strong>${esc(this.#model?.name || "Kein Modell")}</strong><span class="muted">${this.#model ? `${(this.#model.size / 1024 / 1024).toFixed(2)} MB` : "STL oder 3MF auswählen"}</span></div>`, this.#model?.name || "leer"),
      this.#details("plates", "Druckplattenauswahl", this.#plateRows(), this.#inspection ? `${this.#inspection.plate_count} Platte(n)` : "–"),
      this.#details("profiles", "Aktive Profile", this.#profileRows(this.#catalog?.selection || null), `${this.#catalog?.selection.filament_profile_ids.length || 0} Filament(e)`),
      this.#details("height", "Layerhöhe", `<label><span>${this.#height.toFixed(2)} mm</span><input data-control="height" type="range" min="0.08" max="0.40" step="0.02" value="${this.#height}"></label>`, `${this.#height.toFixed(2)} mm`),
    ].join("");
    const right = [
      this.#details("layer", "Schicht", `<label><span>${count ? `${this.#layer + 1} / ${count}` : "–"}</span><input data-control="layer" type="range" min="0" max="${Math.max(0, count - 1)}" value="${Math.min(this.#layer, Math.max(0, count - 1))}" ${count ? "" : "disabled"}></label>`, count ? `${this.#layer + 1}/${count}` : "–"),
      this.#details("status", "Status", `${this.#progress()}<div class="status">${esc(this.#status)}</div>${this.#error ? `<div class="error">${esc(this.#error)}</div>` : ""}`, this.#error ? "Fehler" : "bereit"),
      this.#details("output", "Ausgabe und Direktdruck", '<p class="hint">Nur die ausgewählte Druckplatte wird in ein validiertes G-Code-3MF geslicet. Danach sind Download und zweistufiger Direktdruck verfügbar.</p>', this.#job?.status || "geschlossen"),
    ].join("");

    this.innerHTML = `<style>${PROGRESS_STYLES}${PROFILE_APPLICATION_STYLES}:host{display:block;min-height:720px;color:#eef3f8;font:13px/1.45 Inter,Segoe UI,sans-serif;background:#15191d}*{box-sizing:border-box}.shell{min-height:720px;display:grid;grid-template-rows:auto 1fr}.top{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 18px;border-bottom:1px solid #32383e;background:#1d2227}.title{display:flex;gap:11px;align-items:center}.mark{width:34px;height:34px;border-radius:8px;background:#64d86b;color:#102313;display:grid;place-items:center;font-weight:900}h2{font-size:15px;margin:0}.muted{display:block;color:#9aa5ae;font-size:12px}.actions{display:flex;gap:7px;flex-wrap:wrap}button{border:1px solid #48515a;background:#293037;color:#edf3f7;border-radius:7px;padding:8px 11px;cursor:pointer}button:disabled{opacity:.4}.primary{background:#64d86b!important;color:#0d2111!important;border-color:#64d86b!important;font-weight:800}.danger{border-color:#d26767!important;color:#ffc2c2!important;background:#3a2527!important}.content{display:grid;grid-template-columns:320px minmax(420px,1fr) 310px;min-height:0}.panel{padding:12px;border-right:1px solid #30363c;overflow:auto}.panel:last-child{border-right:0;border-left:1px solid #30363c}.card,.status{border:1px solid #353c43;background:#20262b;border-radius:8px;padding:10px}.accordion-body>.card{border:0;background:transparent;padding:0}.ready{color:#bdf0c4}.offline{color:#e5b9b5}.preview{display:grid;place-items:center;min-height:0;padding:20px;background:radial-gradient(circle at 50% 30%,#293036,#171b1f 68%)}.layer{width:min(70vh,680px);height:min(70vh,680px);max-width:100%;background:#0f1316;border:1px solid #394047;border-radius:10px}.layer line{stroke:#68dc72;stroke-width:1.15;vector-effect:non-scaling-stroke}.empty{min-height:340px;display:grid;place-content:center;text-align:center;color:#96a1a9;gap:6px}.empty strong{color:#dce4e9;font-size:16px}label{display:grid;gap:6px;color:#aab3ba}input[type=range]{width:100%;accent-color:#64d86b}.profile-rows{display:grid;gap:6px}.profile-rows div{display:grid;grid-template-columns:90px 1fr;gap:8px;padding:6px 0;border-bottom:1px solid #30373d}.profile-rows span{color:#84909a}.plate-list{display:grid;gap:7px}.plate-option{display:grid;grid-template-columns:auto 34px 1fr;gap:8px;align-items:center;padding:8px;border:1px solid #343e47;border-radius:8px;background:#181e23;cursor:pointer}.plate-option.selected{border-color:#64d86b;background:#1c2b20}.plate-option input{accent-color:#64d86b}.plate-number{width:30px;height:30px;display:grid;place-items:center;border-radius:7px;background:#30383f;font-weight:900}.plate-option b,.plate-option small{display:block}.plate-option small{color:#89959d;margin-top:2px}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:7px}.metrics div{background:#191e22;border:1px solid #30373d;border-radius:7px;padding:8px;min-width:0}.metrics small{display:block;color:#84909a}.metrics b{display:block;overflow:hidden;text-overflow:ellipsis}.error{margin-top:8px;color:#ffb4b4;background:#362426;border:1px solid #704449;border-radius:7px;padding:9px}.hint{margin:0;color:#8d98a0;font-size:12px;line-height:1.55}.job,.direct-print{grid-column:1/-1;margin:0 16px 16px}.job-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:10px}.v6-progress{margin-bottom:9px}@media(max-width:1050px){.content{grid-template-columns:280px 1fr}.content>.panel:last-child{grid-column:1/-1;border-left:0;border-top:1px solid #30363c}}@media(max-width:760px){.top{align-items:flex-start;flex-direction:column}.content{display:block}.preview{min-height:460px}}</style><div class="shell"><header class="top"><div class="title"><div class="mark">S</div><div><h2>${V6_BRANDING.slicerName}</h2><div class="muted">Mehrplatten-3MF, echte Layer-Geometrie, G-Code-3MF und Direktdruck</div></div></div><div class="actions"><button data-action="choose">STL / 3MF öffnen</button>${this.#model?.name.toLowerCase().endsWith(".3mf") ? '<button data-action="export-model">Original-3MF exportieren</button>' : ""}<button data-action="prepare" ${this.#model ? "" : "disabled"}>Neu analysieren</button><button data-action="save" ${this.#analysis ? "" : "disabled"}>Slice-Plan speichern</button><button class="primary" data-action="slice" ${canSlice ? "" : "disabled"}>Platte ${this.#plateIndex + 1} slicen</button><input id="model-input" type="file" accept=".stl,.3mf,model/stl,model/3mf" hidden></div></header><div class="content"><aside class="panel">${left}</aside><main class="preview">${this.#preview()}</main><aside class="panel">${right}</aside>${this.#jobCard()}${this.#job?.status === "succeeded" ? '<section class="direct-print"><ultimate-3d-direct-print-panel id="direct-print-panel"></ultimate-3d-direct-print-panel></section>' : ""}</div></div>`;

    this.querySelectorAll<HTMLDetailsElement>("details[data-section]").forEach((details) => details.addEventListener("toggle", () => {
      const id = details.dataset.section || "";
      if (details.open) this.#open.add(id); else this.#open.delete(id);
    }));
    this.querySelector<HTMLButtonElement>('[data-action="choose"]')?.addEventListener("click", () => this.querySelector<HTMLInputElement>("#model-input")?.click());
    this.querySelector<HTMLInputElement>("#model-input")?.addEventListener("change", (event) => {
      const file = (event.currentTarget as HTMLInputElement).files?.[0];
      if (file) this.file = file;
    });
    this.querySelector<HTMLButtonElement>('[data-action="export-model"]')?.addEventListener("click", () => this.#downloadSource3mf());
    this.querySelector<HTMLButtonElement>('[data-action="prepare"]')?.addEventListener("click", () => void this.#prepare());
    this.querySelector<HTMLButtonElement>('[data-action="save"]')?.addEventListener("click", () => void this.#savePlan());
    this.querySelector<HTMLButtonElement>('[data-action="slice"]')?.addEventListener("click", () => void this.#slice());
    this.querySelector<HTMLButtonElement>('[data-action="download"]')?.addEventListener("click", () => void this.#download());
    this.querySelectorAll<HTMLInputElement>('input[name="slice-plate"]').forEach((input) => input.addEventListener("change", () => this.#selectPlate(Number(input.value))));
    this.querySelector<HTMLInputElement>('[data-control="height"]')?.addEventListener("input", (event) => {
      this.#height = Number((event.currentTarget as HTMLInputElement).value);
      this.#layer = 0;
      this.#render();
    });
    this.querySelector<HTMLInputElement>('[data-control="layer"]')?.addEventListener("input", (event) => {
      this.#layer = Number((event.currentTarget as HTMLInputElement).value);
      this.#render();
    });
    const direct = this.querySelector<Ultimate3DDirectPrintPanel>("#direct-print-panel");
    if (direct) {
      direct.enabled = Boolean(this.#provider?.capabilities.direct_print);
      direct.job = this.#job;
    }
  }
}

if (!customElements.get("ultimate-3d-slicer-workspace")) {
  customElements.define("ultimate-3d-slicer-workspace", Ultimate3DSlicerWorkspaceV3);
}

