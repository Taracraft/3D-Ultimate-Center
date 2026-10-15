$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot

function Read-Utf8([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($true))
}

function Write-Utf8([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($true))
}

function Replace-Exact([string]$Text, [string]$Old, [string]$New, [string]$Label) {
    if ($Text.Contains($New)) { return $Text }
    if (-not $Text.Contains($Old)) { throw "Quellmarker fehlt: $Label" }
    return $Text.Replace($Old, $New)
}

function Replace-Regex([string]$Text, [string]$Pattern, [string]$Replacement, [string]$Label) {
    if ([regex]::IsMatch($Text, [regex]::Escape($Replacement))) { return $Text }
    $Matches = [regex]::Matches($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if ($Matches.Count -ne 1) { throw "Quellbereich $Label: erwartet 1, gefunden $($Matches.Count)" }
    return [regex]::Replace($Text, $Pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $Replacement }, [System.Text.RegularExpressions.RegexOptions]::Singleline)
}

$WorkspacePath = Join-Path $Root 'frontend\studio-mega-workspace-v2.ts'
$Workspace = Read-Utf8 $WorkspacePath

$Workspace = Replace-Exact $Workspace @'
type MaterialChoice = Readonly<{
  key: string;
  name: string;
  material: string;
  color: string;
  source: "ams" | "profile" | "model";
}>;
'@ @'
type MaterialChoice = Readonly<{
  key: string;
  name: string;
  material: string;
  color: string;
  source: "ams" | "model";
  global_id?: string;
  unit_id?: string;
  slot_index?: number;
  display_slot?: number;
  tray_id?: string;
  filament_id?: string;
}>;
'@ 'MaterialChoice'

$Workspace = Replace-Exact $Workspace @'
function normalizeColor(value: string | null | undefined): string {
  const raw = String(value || "").trim().replace(/^#/, "");
  const rgb = raw.length >= 6 ? raw.slice(0, 6) : "6b7785";
  return /^[0-9a-f]{6}$/i.test(rgb) ? `#${rgb.toLowerCase()}` : NEUTRAL_COLOR;
}
'@ @'
function normalizeColor(value: string | null | undefined): string {
  const raw = String(value || "").trim().replace(/^#/, "");
  const rgb = raw.length >= 6 ? raw.slice(0, 6) : "6b7785";
  return /^[0-9a-f]{6}$/i.test(rgb) ? `#${rgb.toLowerCase()}` : NEUTRAL_COLOR;
}

function amsSlotOccupied(slot: DetailedAmsSlot): boolean {
  return Boolean(
    slot.present
    || String(slot.material || "").trim()
    || String(slot.sub_brand || "").trim()
    || String(slot.color || "").trim(),
  );
}

function colorLabel(value: string | null | undefined): string {
  const raw = String(value || "").trim().replace(/^#/, "").slice(0, 6);
  if (!/^[0-9a-f]{6}$/i.test(raw)) return "";
  const red = Number.parseInt(raw.slice(0, 2), 16);
  const green = Number.parseInt(raw.slice(2, 4), 16);
  const blue = Number.parseInt(raw.slice(4, 6), 16);
  const maximum = Math.max(red, green, blue);
  const minimum = Math.min(red, green, blue);
  if (maximum < 45) return "Schwarz";
  if (minimum > 215) return "Weiß";
  if (maximum - minimum < 28) return "Grau";
  if (red > green * 1.35 && red > blue * 1.35) return "Rot";
  if (green > red * 1.25 && green > blue * 1.2) return "Grün";
  if (blue > red * 1.25 && blue > green * 1.15) return "Blau";
  if (red > 180 && green > 105 && blue < 90) return "Orange";
  if (red > 160 && green > 150 && blue < 100) return "Gelb";
  return "";
}
'@ 'AMS-Helfer'

$Workspace = Replace-Exact $Workspace @'
  #amsError = "";
  #amsLoading = false;
  #viewport: StudioMegaViewport | null = null;
'@ @'
  #amsError = "";
  #amsLoading = false;
  #modalError = "";
  #viewport: StudioMegaViewport | null = null;
'@ 'Modal-Zustand'

$Workspace = Replace-Exact $Workspace @'
      this.#catalog = catalog;
      this.#printers = [...status.items];
      const initial = initialStudioSelection(catalog);
'@ @'
      this.#catalog = catalog;
      this.#printers = [...status.items];
      for (const printer of this.#printers) {
        this.#amsSlots.set(printer.printer_id, this.#occupiedAmsSlots(printer));
      }
      const initial = initialStudioSelection(catalog);
'@ 'AMS-Initialisierung'

$MaterialBlock = @'
  #amsMaterialChoices(plate = this.#plate()): MaterialChoice[] {
    const slots = this.#amsSlots.get(plate.selection.target_printer_id) ?? [];
    const seen = new Set<string>();
    const choices: MaterialChoice[] = [];
    for (const slot of slots) {
      if (!amsSlotOccupied(slot) || !slot.global_id || seen.has(slot.global_id)) continue;
      seen.add(slot.global_id);
      const materialName = String(slot.sub_brand || slot.material || "Filament").trim();
      const shade = colorLabel(slot.color);
      choices.push({
        key: `ams:${slot.global_id}`,
        name: `AMS ${slot.display_slot}: ${materialName}${shade && !materialName.toLocaleLowerCase("de-DE").includes(shade.toLocaleLowerCase("de-DE")) ? ` ${shade}` : ""}`,
        material: slot.material || "unknown",
        color: normalizeColor(slot.color),
        source: "ams",
        global_id: slot.global_id,
        unit_id: slot.unit_id,
        slot_index: slot.slot_index,
        display_slot: slot.display_slot,
        tray_id: slot.tray_id,
        filament_id: slot.tray_id,
      });
    }
    return choices.sort((left, right) => (left.display_slot ?? 0) - (right.display_slot ?? 0));
  }

  #materialChoices(plate = this.#plate()): MaterialChoice[] {
    const choices = [...this.#amsMaterialChoices(plate)];
    for (const model of this.#modelMaterials) {
      if (!choices.some((choice) => choice.key === model.key)) choices.push(model);
    }
    return choices;
  }

  #materialPlan(): SliceMaterialPlan {
    const plate = this.#plate();
    const choices = this.#amsMaterialChoices(plate);
    if (!choices.length) {
      throw new Error("Am Ziel-Drucker ist kein belegter AMS-Slot verfügbar. Bitte AMS synchronisieren.");
    }
    const originalIndexByKey = new Map(choices.map((choice, index) => [choice.key, index + 1]));
    const pending: Array<readonly [MeshInstance, number]> = [];
    const missing: string[] = [];
    for (const item of plate.instances.filter((instance) => instance.visible)) {
      const key = this.#assignments.get(item.id) || "";
      const originalIndex = originalIndexByKey.get(key);
      if (!originalIndex) missing.push(item.name);
      else pending.push([item, originalIndex]);
    }
    if (missing.length) {
      const names = [...new Set(missing)].slice(0, 4).join(", ");
      const suffix = missing.length > 4 ? ` und ${missing.length - 4} weitere` : "";
      throw new Error(`Nicht alle sichtbaren Objekte sind einem belegten AMS-Slot zugeordnet: ${names}${suffix}.`);
    }
    const usedOriginal = [...new Set(pending.map((entry) => entry[1]))].sort((left, right) => left - right);
    const compactByOriginal = new Map(usedOriginal.map((value, index) => [value, index + 1]));
    const assignments: Record<string, number> = {};
    for (const [item, originalIndex] of pending) assignments[item.id] = compactByOriginal.get(originalIndex)!;
    const usedChoices = usedOriginal.map((index) => choices[index - 1]!);
    const filaments: Array<SliceProjectFilament & {
      global_id: string;
      unit_id: string;
      slot_index: number;
      display_slot: number;
      tray_id: string;
      filament_id: string;
      source: "ams";
    }> = usedChoices.map((choice, index) => ({
      extruder: index + 1,
      name: choice.name,
      material: choice.material,
      color: choice.color,
      global_id: choice.global_id || "",
      unit_id: choice.unit_id || "",
      slot_index: choice.slot_index ?? 0,
      display_slot: choice.display_slot ?? (choice.slot_index ?? 0) + 1,
      tray_id: choice.tray_id || "",
      filament_id: choice.filament_id || choice.tray_id || "",
      source: "ams",
    }));
    const tower = loadPlatePurgeTower(plate.id);
    return {
      assignments,
      filaments,
      purge_tower: {
        ...(this.#inspection?.purge_tower ?? {}),
        ...tower,
        enabled: usedChoices.length > 1 && tower.enabled !== false,
        width_mm: this.#purgeTowerData().width,
        flush_multiplier: Math.max(.1, Number(tower.flush_multiplier ?? 1)),
      },
    };
  }

'@
$Workspace = Replace-Regex $Workspace '  #materialChoices\(plate = this\.#plate\(\)\): MaterialChoice\[\] \{.*?\n  #ui\(\): MegaUiStateV2 \{' ($MaterialBlock + '  #ui(): MegaUiStateV2 {') 'Materiallogik'

$Workspace = Replace-Exact $Workspace @'
      error: this.#error || plate.lastError,
      loading: this.#loading,
'@ @'
      error: this.#error || plate.lastError,
      modalError: this.#modalError,
      loading: this.#loading,
'@ 'Modal im UI-State'

$Workspace = Replace-Exact $Workspace @'
  #materialColor(key: string): string {
    return this.#materialChoices().find((choice) => choice.key === key)?.color ?? NEUTRAL_COLOR;
  }

  async #syncAms(): Promise<void> {
'@ @'
  #materialColor(key: string): string {
    return this.#materialChoices().find((choice) => choice.key === key)?.color ?? NEUTRAL_COLOR;
  }

  #occupiedAmsSlots(printer: DetailedDirectPrintPrinter): DetailedAmsSlot[] {
    return printer.ams.slots
      .filter((slot) => amsSlotOccupied(slot))
      .sort((left, right) => left.display_slot - right.display_slot);
  }

  #clearErrors(): void {
    this.#error = "";
    this.#modalError = "";
    this.#amsError = "";
    this.#plate().lastError = "";
    this.#root.querySelector("#error-modal")?.remove();
    this.#root.querySelector("#global-error-box")?.remove();
    this.#renderStatus();
  }

  #showError(error: unknown): void {
    const message = error instanceof Error ? error.message : String(error);
    this.#error = message;
    this.#modalError = message;
  }

  async #syncAms(): Promise<void> {
'@ 'Fehler- und AMS-Helfer'

$Workspace = Replace-Exact $Workspace @'
      const slots = printer.ams.slots.filter((slot) => slot.present).sort((left, right) => left.display_slot - right.display_slot);
'@ @'
      const slots = this.#occupiedAmsSlots(printer);
'@ 'AMS-Belegung'

$Workspace = Replace-Exact $Workspace @'
    } catch (error) {
      this.#amsError = error instanceof Error ? error.message : String(error);
    } finally {
'@ @'
    } catch (error) {
      this.#amsError = error instanceof Error ? error.message : String(error);
      this.#showError(error);
    } finally {
'@ 'AMS-Fehlerpopup'

$Workspace = Replace-Exact $Workspace @'
    this.#status = "Projektfarben entfernt. Objekte können neu AMS- oder Filamentprofilen zugewiesen werden.";
'@ @'
    this.#status = "Projektfarben entfernt. Objekte können jetzt den belegten AMS-Slots zugewiesen werden.";
'@ 'Projektfarben-Text'

$SliceMethod = @'
  async #slice(): Promise<void> {
    const plate = this.#plate();
    if (!plate.instances.length || plate.stage === "slicing") return;
    let materialPlan: SliceMaterialPlan;
    try {
      materialPlan = this.#materialPlan();
    } catch (error) {
      this.#showError(error);
      this.#renderFull();
      return;
    }
    const generation = ++this.#generation;
    plate.stage = "slicing";
    plate.lastError = "";
    this.#loading = true;
    this.#clearErrors();
    this.#status = `${plate.name} wird geslicet …`;
    this.#renderFull();
    try {
      const job = await createPlateSliceJob(
        this.#plateFile(),
        0,
        "pc",
        undefined,
        materialPlan,
        {
          studio_plate_id: plate.id,
          studio_plate_display_number: plate.id + 1,
          studio_plate_name: plate.name,
          target_printer_id: plate.selection.target_printer_id,
          printer_profile_id: plate.selection.printer_profile_id,
          nozzle_profile_id: plate.selection.nozzle_profile_id,
          process_profile_id: plate.selection.process_profile_id,
          build_plate_profile_id: plate.selection.build_plate_profile_id,
          filament_profile_ids: [...plate.selection.filament_profile_ids],
        },
      );
      plate.jobId = job.id;
      let currentJob: SliceJob = job;
      while (generation === this.#generation && ACTIVE.has(currentJob.status)) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        currentJob = await fetchSliceJob(currentJob.id);
      }
      if (currentJob.status !== "succeeded") throw new Error(currentJob.error || "Slicing fehlgeschlagen");
      const summary = await fetchToolpath(currentJob.id);
      plate.layerCount = summary.layer_count;
      plate.layers = [];
      for (let start = 0; start < summary.layer_count; start += 35) {
        const chunk = await fetchToolpath(currentJob.id, start, Math.min(summary.layer_count, start + 35));
        plate.layers.push(...(chunk.chunk?.layers ?? []));
      }
      plate.visibleLayer = Math.max(0, plate.layerCount - 1);
      plate.stage = "sliced";
      this.#mode = "preview";
      this.#status = `${plate.name}: ${plate.layerCount} Layer erfolgreich erzeugt.`;
    } catch (error) {
      plate.stage = "error";
      plate.lastError = error instanceof Error ? error.message : String(error);
      this.#showError(error);
    } finally {
      if (generation === this.#generation) {
        this.#loading = false;
        this.#renderFull();
      }
    }
  }
'@
$Workspace = Replace-Regex $Workspace '  async #slice\(\): Promise<void> \{.*?\n  #markPrinted\(\): void \{' ($SliceMethod + "`n  #markPrinted(): void {") 'Slice-Methode'

$Workspace = Replace-Exact $Workspace @'
  #bindUi(): void {
    const menus = [...this.#root.querySelectorAll<HTMLDetailsElement>("details.menu")];
'@ @'
  #bindUi(): void {
    this.#root.querySelector<HTMLButtonElement>("#error-modal-close")?.addEventListener("click", () => {
      this.#modalError = "";
      this.#root.querySelector("#error-modal")?.remove();
    });
    const menus = [...this.#root.querySelectorAll<HTMLDetailsElement>("details.menu")];
'@ 'Modal-Schließen'

$ColorsSidebar = @'
    if (this.#mode === "colors") {
      const choices = this.#amsMaterialChoices();
      const currentKey = primary ? this.#assignments.get(primary.id) || "" : "";
      host.innerHTML = `<h3>Mehrfarben & AMS</h3><div class="section"><button id="sync-ams" ${this.#amsLoading ? "disabled" : ""}>${this.#amsLoading ? "AMS wird synchronisiert …" : "AMS des gewählten Druckers synchronisieren"}</button><button id="remove-model-colors">Projektfarben entfernen</button>${this.#amsError ? `<span class="error-box">${this.#amsError}</span>` : ""}</div><div class="section"><b>Filamentprofile dieser Platte</b><small>Profile steuern Temperatur, Flow und Prozesswerte. Physische Filamente werden ausschließlich über belegte AMS-Slots zugeordnet.</small>${filamentProfilesHtml(this.#catalog, plate.selection.filament_profile_ids)}</div><div class="section"><div class="assignment"><span class="swatch" style="background:${this.#materialColor(currentKey)}"></span><b>${primary?.name || "Objekt auswählen"}</b><select id="material-choice" ${primary && choices.length ? "" : "disabled"}><option value="">Nicht zugewiesen</option>${choices.map((choice) => `<option value="${choice.key}" ${choice.key === currentKey ? "selected" : ""}>${choice.name} · ${choice.material}</option>`).join("")}</select></div><small>Zuweisung gilt für alle markierten Objekte/Teile.</small></div>`;
      host.querySelector<HTMLButtonElement>("#sync-ams")?.addEventListener("click", () => void this.#syncAms());
      host.querySelector<HTMLButtonElement>("#remove-model-colors")?.addEventListener("click", () => this.#removeModelColors());
      host.querySelectorAll<HTMLButtonElement>("[data-filament-profile]").forEach((button) => {
        button.addEventListener("click", () => this.#toggleFilamentProfile(button.dataset.filamentProfile || ""));
      });
      host.querySelector<HTMLSelectElement>("#material-choice")?.addEventListener("change", (event) => {
        const key = (event.currentTarget as HTMLSelectElement).value;
        const changes = new Map<string, MeshInstance>();
        this.#clearErrors();
        for (const item of selected) {
          if (key) this.#assignments.set(item.id, key);
          else this.#assignments.delete(item.id);
          changes.set(item.id, { ...item, color: key ? this.#materialColor(key) : NEUTRAL_COLOR });
        }
        this.#replace(changes);
      });
      return;
    }
'@
$Workspace = Replace-Regex $Workspace '    if \(this\.#mode === "colors"\) \{.*?\n    if \(this\.#mode === "preview"\) \{' ($ColorsSidebar + '    if (this.#mode === "preview") {') 'Mehrfarben-Sidebar'

Write-Utf8 $WorkspacePath $Workspace

$UiPath = Join-Path $Root 'frontend\studio-mega-ui-v2.ts'
$Ui = Read-Utf8 $UiPath
$Ui = Replace-Exact $Ui @'
  error: string;
  loading: boolean;
'@ @'
  error: string;
  modalError: string;
  loading: boolean;
'@ 'UI-Modaltyp'
$Ui = Replace-Exact $Ui @'
.direct-print-top{display:block}${STUDIO_PROFILE_CSS}
@media(max-width:1100px)
'@ @'
.direct-print-top{display:block}.error-modal{position:fixed;inset:0;z-index:10000;display:grid;place-items:center;padding:24px;background:#000b}.error-modal-panel{width:min(560px,calc(100vw - 32px));overflow:hidden;border:1px solid #d65763;border-radius:12px;background:linear-gradient(180deg,#27131a,#130b10);box-shadow:0 22px 70px #000d}.error-modal-head{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid #74313a}.error-modal-head strong{font-size:17px;color:#ffd6da}.error-modal-body{padding:18px 16px;color:#fff1f2;font-size:14px;line-height:1.5}.error-modal-actions{display:flex;justify-content:flex-end;padding:0 16px 16px}.error-modal-actions button{min-width:120px;padding:8px 13px;border:1px solid #d65763;border-radius:5px;background:#6a222c;color:#fff;font-weight:800}${STUDIO_PROFILE_CSS}
@media(max-width:1100px)
'@ 'Modal-CSS'
$Ui = Replace-Exact $Ui @'
<div id="sidebar"></div>${state.error ? `<div class="error-box">${esc(state.error)}</div>` : ""}</aside>
'@ @'
<div id="sidebar"></div>${state.error ? `<div class="error-box" id="global-error-box">${esc(state.error)}</div>` : ""}</aside>
'@ 'Inline-Fehler-ID'
$Ui = Replace-Exact $Ui @'
</section><input id="local-file" type="file" accept=".stl,.3mf" hidden></section>`;
'@ @'
</section><input id="local-file" type="file" accept=".stl,.3mf" hidden></section>${state.modalError ? `<div class="error-modal" id="error-modal" role="dialog" aria-modal="true" aria-labelledby="error-modal-title"><section class="error-modal-panel"><header class="error-modal-head"><strong id="error-modal-title">Slicing nicht möglich</strong></header><div class="error-modal-body">${esc(state.modalError)}</div><footer class="error-modal-actions"><button id="error-modal-close" type="button">Schließen</button></footer></section></div>` : ""}`;
'@ 'Modal-HTML'
Write-Utf8 $UiPath $Ui

$SlicingPath = Join-Path $Root 'frontend\slicing-api.ts'
$Slicing = Read-Utf8 $SlicingPath
$Slicing = Replace-Exact $Slicing @'
export type SliceProjectFilament = Readonly<{
  extruder: number;
  name: string;
  material: string;
  color: string | null;
}>;
'@ @'
export type SliceProjectFilament = Readonly<{
  extruder: number;
  name: string;
  material: string;
  color: string | null;
  global_id?: string;
  unit_id?: string;
  slot_index?: number;
  display_slot?: number;
  tray_id?: string;
  filament_id?: string;
  source?: "ams" | "profile" | "model";
}>;
'@ 'Filament-Metadaten'
Write-Utf8 $SlicingPath $Slicing

Write-Host 'AMS-/Modal-Quelländerung erfolgreich angewendet.' -ForegroundColor Green
