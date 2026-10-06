import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { build } from "esbuild";

const root = dirname(fileURLToPath(import.meta.url));
const frontendDirectory = join(root, "frontend");
const testEntry = join(root, "frontend-tests", "logic.test.ts");
const outputDirectory = join(root, ".test-build", "frontend-logic");
const outputFile = join(outputDirectory, "logic.test.mjs");

function readSource(path) {
  return readFileSync(path, "utf8").replace(/\r\n?/g, "\n");
}

const forbiddenPatterns = [
  "prototype.connectedCallback =",
  "prototype.disconnectedCallback =",
  "prototype._render =",
  "__transformToolsPatched",
  "__transformMountPatched",
  "new MutationObserver",
  "ultimate-3d-studio-status-patch",
  "ultimate-3d-controls-confirmation-patch",
  "installElementEnhancer(",
  "observeProgressRoot(",
  "setProgressSlot(",
  "./progress-enhancer-",
  "workspace-progress-enhancer.js",
  "setInterval(check, 900)",
];

function runSourcePolicyGate() {
  const violations = [];
  const navigationAuthorities = [];

  for (const entry of readdirSync(frontendDirectory, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".ts")) continue;
    const source = readSource(join(frontendDirectory, entry.name));

    for (const pattern of forbiddenPatterns) {
      if (source.includes(pattern)) violations.push(`${entry.name}: ${pattern}`);
    }
    if (source.includes("const NAVIGATION:")) navigationAuthorities.push(entry.name);
  }

  if (navigationAuthorities.length !== 1) {
    violations.push(`Navigation authorities: expected 1, found ${navigationAuthorities.length}`);
  }

  const controlSource = readSource(join(frontendDirectory, "control-workspace-v2.ts"));
  if (!controlSource.includes('<ultimate-3d-printer-actions id="printer-actions">')) violations.push("control-workspace-v2.ts: persistent printer actions mount missing");
  if (!controlSource.includes('this.#root.querySelector<Ultimate3DPrinterActions>("#printer-actions")')) violations.push("control-workspace-v2.ts: printer actions are not updated through persistent root lookup");
  if (controlSource.includes('host.querySelector<Ultimate3DPrinterActions>("ultimate-3d-printer-actions")')) violations.push("control-workspace-v2.ts: dynamic subtree still owns printer actions dialog");

  const commandSource = readSource(join(frontendDirectory, "printer-command-store-v2.ts"));
  if (!commandSource.includes('#mounted = false')) violations.push("printer-command-store-v2.ts: persistent component mount guard missing");
  if (!commandSource.includes('<v6-action-dialog id="printer-command-dialog"></v6-action-dialog>')) violations.push("printer-command-store-v2.ts: persistent command dialog missing");
  if (!commandSource.includes('id="printer-command-actions"')) violations.push("printer-command-store-v2.ts: persistent command action host missing");
  if (!commandSource.includes('id="printer-command-feedback"')) violations.push("printer-command-store-v2.ts: persistent command feedback host missing");
  if (commandSource.includes('<v6-action-dialog></v6-action-dialog>')) violations.push("printer-command-store-v2.ts: command dialog is still recreated by telemetry rendering");
  if (commandSource.includes("this.#root.innerHTML = `<style>") && !commandSource.includes("#mount(): void")) violations.push("printer-command-store-v2.ts: full render still replaces the dialog");

  const directPrintSource = readSource(join(frontendDirectory, "direct-print-panel-next.ts"));
  if (!directPrintSource.includes('"authoritative_external_spool_runtime"')) violations.push("direct-print-panel-next.ts: authoritative external-spool plan validation missing");
  if (!directPrintSource.includes('"authoritative_ams_runtime"')) violations.push("direct-print-panel-next.ts: authoritative AMS plan validation missing");
  if (!directPrintSource.includes("use_ams: selection.useAms")) violations.push("direct-print-panel-next.ts: material source is not forwarded explicitly");
  if (!directPrintSource.includes("ams_mapping: [...selection.mapping]")) violations.push("direct-print-panel-next.ts: slicer AMS mapping is not forwarded");
  if (!directPrintSource.includes("useAms: false, mapping: []")) violations.push("direct-print-panel-next.ts: explicit external-spool source is missing");
  if (!directPrintSource.includes("keinen automatischen Fallback")) violations.push("direct-print-panel-next.ts: fail-closed source contract missing");
  const prepareStart = directPrintSource.indexOf("  async #prepare(): Promise<void> {");
  const startStart = directPrintSource.indexOf("  async #start(): Promise<void> {", prepareStart);
  const discardStart = directPrintSource.indexOf("  async #discard(): Promise<void> {", startStart);
  if (prepareStart < 0 || startStart < 0 || discardStart < 0) violations.push("direct-print-panel-next.ts: prepare/start blocks could not be verified");
  else {
    const prepareBlock = directPrintSource.slice(prepareStart, startStart);
    const startBlock = directPrintSource.slice(startStart, discardStart);
    if (!prepareBlock.includes("prepareDirectPrint(")) violations.push("direct-print-panel-next.ts: Druck vorbereiten does not call prepareDirectPrint");
    if (prepareBlock.includes("startDirectPrint(")) violations.push("direct-print-panel-next.ts: SECURITY REGRESSION - Druck vorbereiten calls startDirectPrint");
    if (!startBlock.includes("startDirectPrint(")) violations.push("direct-print-panel-next.ts: Drucken does not call startDirectPrint");
    if (startBlock.includes("prepareDirectPrint(")) violations.push("direct-print-panel-next.ts: print start unexpectedly prepares a second job");
  }
  if (!directPrintSource.includes("LAN-Direktdruck nicht erreichbar")) violations.push("direct-print-panel-next.ts: LAN/direct-print separation label missing");
  if (!directPrintSource.includes("Cloud/App-Verbindung kann trotzdem online sein")) violations.push("direct-print-panel-next.ts: cloud-vs-LAN status explanation missing");

  const studioSource = readSource(join(frontendDirectory, "studio-mega-workspace-v2.ts"));
  if (!studioSource.includes("#initialized = false")) violations.push("studio reconnect initialization guard missing");
  if (!studioSource.includes("if (!this.#initialized)")) violations.push("studio reconnect guard missing");
  if (!studioSource.includes("this.#cleanupTimer = globalThis.setTimeout")) violations.push("studio delayed cleanup missing");
  if (studioSource.includes("this.#renderFull();\n    void this.#loadEnvironment();\n  }\n\n  disconnectedCallback")) violations.push("studio still reloads on every reconnect");
  if (!studioSource.includes("void this.#bootstrap();")) violations.push("studio initial bootstrap does not restore the workspace first");
  if (!studioSource.includes("await this.#restoreWorkspace();")) violations.push("studio workspace restore is missing");
  if (!studioSource.includes("positions: new Float32Array(item.geometry.positions)")) violations.push("studio mesh geometry is not persisted");
  if (!studioSource.includes("this.#schedulePersist();")) violations.push("studio workspace persistence scheduling is missing");
  const environmentStart = studioSource.indexOf("  async #loadEnvironment(): Promise<void> {");
  const environmentEnd = studioSource.indexOf("\n  #plate(): Plate", environmentStart);
  if (environmentStart < 0 || environmentEnd < 0) violations.push("studio environment loader block could not be verified");
  else {
    const environmentBlock = studioSource.slice(environmentStart, environmentEnd);
    if (environmentBlock.includes("this.#renderFull()")) violations.push("studio environment loader still performs a destructive full render");
    if ((environmentBlock.match(/this\.#refreshEnvironmentUi\(\)/g) ?? []).length < 2) violations.push("studio environment success and failure paths are not incremental");
  }

  const persistenceSource = readSource(join(frontendDirectory, "studio-persistence.ts"));
  if (!persistenceSource.includes('const DATABASE_NAME = "ultimate-3d-studio-v6"')) violations.push("studio-persistence.ts: dedicated IndexedDB database missing");
  if (!persistenceSource.includes("put(snapshot, ACTIVE_KEY)")) violations.push("studio-persistence.ts: workspace save transaction missing");
  if (!persistenceSource.includes("get(ACTIVE_KEY)")) violations.push("studio-persistence.ts: workspace restore transaction missing");

  const cameraSource = readSource(join(frontendDirectory, "printer-camera-panel.ts"));
  if (!cameraSource.includes("const FRAME_INTERVAL_MS = 2_000")) violations.push("printer-camera-panel.ts: automatic two-second frame interval missing");
  if (!cameraSource.includes("#frameTimer: number | null = null")) violations.push("printer-camera-panel.ts: managed frame timer missing");
  if (!cameraSource.includes("#viewportVisible = true")) violations.push("printer-camera-panel.ts: viewport visibility state missing");
  if (!cameraSource.includes("this.#stopFrameTimer()")) violations.push("printer-camera-panel.ts: frame timer cleanup missing");
  const noReloadSources = [
    "printer-camera-panel.ts",
    "control-workspace-v2.ts",
    "system-workspace-v5.ts",
    "global-job-popup-v3.ts",
    "studio-mega-workspace-v2.ts",
  ];
  for (const file of noReloadSources) {
    const source = readSource(join(frontendDirectory, file));
    if (/location\.reload\s*\(|history\.go\s*\(\s*0\s*\)|location\.(?:assign|replace)\s*\(/.test(source)) violations.push(file + ": forbidden page reload/navigation replacement found");
  }
  if (studioSource.includes("while (generation === this.#generation && ACTIVE.has(currentJob.status))")) violations.push("studio slice completion still depends on DOM generation");
  if (!studioSource.includes("handedToReconcile = true;\n      await this.#activatePlateJob(plate);")) violations.push("studio slice job is not delegated to the plate-bound reconciler");
  if (!studioSource.includes("#reconcilingJobs = new Set<string>()")) violations.push("studio per-job reconciliation guard missing");
  if (!studioSource.includes("#deferredFullRender = false")) violations.push("studio deferred reconnect render state missing");
  if (!studioSource.includes('from "./browser-yield.js"')) violations.push("studio large-model preparation does not yield to the browser");
  if (!studioSource.includes('from "./mesh-geometry-async.js"')) violations.push("studio large-model import still builds geometry synchronously");
  if (!studioSource.includes('from "./studio-plate-preflight.js"')) violations.push("studio plate-bound preflight import missing");
  if (!studioSource.includes('from "./three-mf-export-stream.js"')) violations.push("studio streamed compressed 3MF exporter missing");
  if (!studioSource.includes("await buildMeshGeometryAsync(part.positions)")) violations.push("studio 3MF scene geometry is not built cooperatively");
  if (!studioSource.includes("await analyzePlateBounds(")) violations.push("studio does not block out-of-volume models before upload");
  if (!studioSource.includes("await export3mfStreamed(")) violations.push("studio slice export is not streamed and compressed");
  if (!studioSource.includes("await waitForBrowserPaint()")) violations.push("studio preparation popup is not painted before heavy work");
  if (!studioSource.includes('#materialSourceChanged(value: string)')) violations.push("studio material-source selector handler missing");
  if (!studioSource.includes('source: "external_spool"')) violations.push("studio external-spool slice plan missing");
  if (!studioSource.includes('purge_tower: { enabled: false }')) violations.push("studio external-spool purge tower is not disabled");
  if (!studioSource.includes('plate.externalFilamentProfileId')) violations.push("studio external-spool filament profile is not plate-bound");
  if (!studioSource.includes("ultimate-3d-slice-preparation")) violations.push("studio preparation lifecycle event missing");
  if (studioSource.includes("export3mf(")) violations.push("studio still uses the synchronous uncompressed 3MF exporter");
  if (studioSource.includes("this.#schedulePersist(0)")) violations.push("studio still schedules immediate full geometry persistence after every render");

  if (!studioSource.includes('#previewColorMode: PreviewColorMode = "material"')) violations.push("studio preview must default to real job filament colors");
  if ((studioSource.match(/this\.#previewColorMode = "feature"/g) ?? []).length !== 1) violations.push("Drucktyp may only be selected by its explicit diagnostic control");
  if (studioSource.includes("toolColors[tool %") || studioSource.includes("plate.toolColors.length ? plate.toolColors :")) violations.push("preview must not invent or remap job colors from live material choices");
  if (!studioSource.includes('return buildContinuousToolpathMeshes(')) violations.push("studio continuous toolpath renderer missing");
  if (studioSource.includes('toolpathPreviewSampling(')) violations.push("studio preview still samples away extrusion paths");
  const ribbonSource = readSource(join(frontendDirectory, "toolpath-ribbon-geometry.ts"));
  if (!ribbonSource.includes('for (const segment of layer.segments)')) violations.push("continuous preview must visit all extrusion paths");
  if (!studioSource.includes('data-preview-feature="${key}"')) violations.push("studio preview per-category visibility controls missing");
  if (!studioSource.includes('id="preview-feature-all"') || !studioSource.includes('id="preview-feature-none"')) violations.push("studio preview All/None feature controls missing");
  if (!studioSource.includes('id="preview-material-summary"')) violations.push("studio preview material summary is not collapsible");
  const previewRefreshStart = studioSource.indexOf("  #refreshPreviewViewport(): void {");
  const displayInstancesStart = studioSource.indexOf("\n  #displayInstances(): MeshInstance[]", previewRefreshStart);
  if (previewRefreshStart < 0 || displayInstancesStart < 0) violations.push("studio preview refresh block could not be verified");
  else {
    const previewRefreshBlock = studioSource.slice(previewRefreshStart, displayInstancesStart);
    if ((previewRefreshBlock.match(/requestAnimationFrame/g) ?? []).length < 2) violations.push("studio layer refresh lacks the double animation-frame redraw guard");
    if (previewRefreshBlock.includes("frameAll(")) violations.push("studio layer refresh resets the camera framing");
  }
  const layerInputStart = studioSource.indexOf('layerSlider?.addEventListener("input"');
  const layerChangeStart = studioSource.indexOf('layerSlider?.addEventListener("change"', layerInputStart);
  if (layerInputStart < 0 || layerChangeStart < 0) violations.push("studio layer slider input block could not be verified");
  else {
    const layerInputBlock = studioSource.slice(layerInputStart, layerChangeStart);
    if (!layerInputBlock.includes("this.#refreshPreviewViewport();")) violations.push("studio layer change does not use the stable preview refresh path");
    if (layerInputBlock.includes("frameAll(")) violations.push("studio layer change unexpectedly reframes the camera");
  }

  const popupSource = readSource(join(frontendDirectory, "global-job-popup-v3.ts"));
  if (!popupSource.includes("resolveLivePrintPhase")) violations.push("global-job-popup-v3.ts: server-backed observed-stage print phase tracker missing");
  if (!popupSource.includes("#phaseSeen = new Map<string, Set<string>>()")) violations.push("global-job-popup-v3.ts: per-job observed phase history missing");
  if (!popupSource.includes("phase.doneOnlyWhenJobEnds")) violations.push("global-job-popup-v3.ts: interruptible model-print phase guard missing");
  if (!popupSource.includes("ultimate-3d-slice-preparation")) violations.push("global-job-popup-v3.ts: slicer preparation listener missing");
  if (!popupSource.includes("SLICER · VORBEREITUNG")) violations.push("global-job-popup-v3.ts: visible preparation card missing");
  if (!popupSource.includes("preparationCard + slicerCard + previewCard + transferCard + printCards + traceCard + studioCard")) violations.push("global-job-popup-v3.ts: preparation, slicer and layer-preview cards are not composed before real jobs");
  if (!popupSource.includes("estimatedOverallEta")) violations.push("global-job-popup-v3.ts: overall ETA estimator missing");
  if (!popupSource.includes("slicerProgressPercent")) violations.push("global-job-popup-v3.ts: native slicer progress is not wired");
  if (!popupSource.includes("slicerEtaSeconds")) violations.push("global-job-popup-v3.ts: native slicer ETA is not wired");
  if (popupSource.includes('if (job.status === "running") return 62;')) violations.push("global-job-popup-v3.ts: synthetic native slicer progress remains in popup");
  if (!popupSource.includes("Gesamt-ETA ~")) violations.push("global-job-popup-v3.ts: overall ETA is not visibly marked as estimated");
  if (!popupSource.includes("formatBytes(entry.metrics?.inputSizeBytes)")) violations.push("global-job-popup-v3.ts: studio input size is not unit-aware");
  if (!popupSource.includes("formatBytes(entry.metrics?.outputSizeBytes)")) violations.push("global-job-popup-v3.ts: studio output size is not unit-aware");

  const phaseSource = readSource(join(frontendDirectory, "print-phase-progress.ts"));
  const reliableA1PhaseOrder = [
    "bed_heating",
    "homing",
    "filament_loading",
    "flow_calibration",
    "mechanical_check",
    "nozzle_cleaning_after",
    "bed_leveling",
    "printing_model",
    "completed",
  ];
  let previousA1PhasePosition = -1;
  for (const key of reliableA1PhaseOrder) {
    const position = phaseSource.indexOf(`key: "${key}"`);
    if (position < 0) violations.push(`print-phase-progress.ts: reliable A1 phase ${key} missing`);
    else if (position <= previousA1PhasePosition) violations.push(`print-phase-progress.ts: reliable A1 phase ${key} is out of order`);
    previousA1PhasePosition = position;
  }
  if (phaseSource.includes('key: "nozzle_cleaning_before"')) violations.push("print-phase-progress.ts: unverifiable pre-calibration cleaning phase remains visible");
  if (phaseSource.includes('key: "filament_change"')) violations.push("print-phase-progress.ts: removed filament-change phase is visible");
  if (phaseSource.includes('key: "test_strip"')) violations.push("print-phase-progress.ts: removed test-strip phase is visible");
  if (!phaseSource.includes("resolveTrackedPrintPhaseProgress")) violations.push("print-phase-progress.ts: observed-stage resolver missing");
  if (!phaseSource.includes("doneOnlyWhenJobEnds")) violations.push("print-phase-progress.ts: model-print completion semantics missing");

  const selectionSource = readSource(join(frontendDirectory, "studio-selection.ts"));
  if (!selectionSource.includes("const selected = new Set(currentSelection)")) violations.push("studio-selection.ts: additive selection state missing");
  if (!studioSource.includes('document.addEventListener("keydown", this.#keyDown, true)')) violations.push("studio keyboard shortcuts are not document-routed");
  if (!studioSource.includes("async #persistNow(): Promise<void>")) violations.push("studio immediate persistence contract missing");
  if (!studioSource.includes("jobActivityStore.registerSlicerJob(job)")) violations.push("studio plate-bound slicer job activation missing");
  if (!studioSource.includes("stage: plate.stage")) violations.push("studio plate stage is not persisted");
  if (!studioSource.includes("jobId: plate.jobId")) violations.push("studio plate job is not persisted");

  const directPrintPanelSource = readSource(join(frontendDirectory, "direct-print-panel-next.ts"));
  if (directPrintPanelSource.includes("Druckjob vollständig auf den Drucker übertragen?")) violations.push("direct print prepare popup still present");
  if (directPrintPanelSource.includes("window.prompt(")) violations.push("direct print start popup still present");
  if (!directPrintPanelSource.includes(">Drucken</button>")) violations.push("direct print button was not renamed to Drucken");
  if (!directPrintPanelSource.includes("fetchDirectPrintTransferStatus")) violations.push("direct print panel does not poll measured printer-transfer status");
  if (!directPrintPanelSource.includes("status.rate_bytes_per_second")) violations.push("direct print panel does not expose measured transfer rate");
  if (!directPrintPanelSource.includes("status.eta_seconds")) violations.push("direct print panel does not expose measured transfer ETA");
  const directPrintTransferEventsSource = readSource(join(frontendDirectory, "direct-print-transfer-events.ts"));
  if (!directPrintTransferEventsSource.includes('DIRECT_PRINT_TRANSFER_EVENT = "ultimate-3d-direct-print-transfer"')) violations.push("direct print transfer event contract missing");
  if (!popupSource.includes("globalThis.addEventListener(DIRECT_PRINT_TRANSFER_EVENT")) violations.push("global popup is not subscribed to direct print transfers");
  if (!popupSource.includes("const transferCard = visibleTransfer")) violations.push("direct print transfer list entry missing");
  if (!popupSource.includes("this.#dismissButton(transferWorkflowKey, transferTitle)")) violations.push("direct print transfer per-item close button missing");
  if (!popupSource.includes("formatBytes(visibleTransfer.loadedBytes)") || !popupSource.includes("formatRate(visibleTransfer.rateBytesPerSecond)") || !popupSource.includes("formatDuration(visibleTransfer.etaSeconds)")) violations.push("direct print transfer popup metrics are incomplete");
  if (popupSource.includes('class="progress moving"><u style="width:${transferProgress}%')) violations.push("direct print transfer progress is not strictly measured left-to-right");

  const makerWorldSource = readSource(join(frontendDirectory, "makerworld-workspace-core-v2.ts"));
  if (!makerWorldSource.includes("data-remove-filter")) violations.push("MakerWorld removable filter chips missing");
  if (!makerWorldSource.includes("this.#hasMore = Boolean(result.has_more)")) violations.push("MakerWorld real pagination result is not honored");
  if (!makerWorldSource.includes("#addTerms(value: string)")) violations.push("MakerWorld additive search filters missing");

  const profileUiSource = readSource(join(frontendDirectory, "studio-profile-ui.ts"));
  if (!profileUiSource.includes(":host{height:auto;min-height:100%;overflow:visible}")) violations.push("studio-profile-ui.ts: growing studio host contract missing");
  if (!profileUiSource.includes("grid-template-rows:auto auto auto auto auto auto minmax(560px,1fr)")) violations.push("studio-profile-ui.ts: seven-row non-overlapping studio grid missing");
  if (!profileUiSource.includes(".body{grid-row:7;min-height:560px}")) violations.push("studio-profile-ui.ts: dedicated viewport row height missing");

  const directPrintStripSource = readSource(join(frontendDirectory, "studio-direct-print-strip.ts"));
  if (!directPrintStripSource.includes("strip.append(this.#panel, this.#analysis)")) violations.push("studio-direct-print-strip.ts: printer dialog must precede G-code analysis");
  if (directPrintStripSource.includes("strip.append(this.#analysis, this.#panel)")) violations.push("studio-direct-print-strip.ts: G-code analysis still precedes printer dialog");

  const entrySource = readSource(join(frontendDirectory, "v6-entry.ts"));
  if (!entrySource.includes('const REGISTRY_KEY = "__ultimate3dStudioV6PersistentRegistry"')) violations.push("global persistent studio registry missing");
  if (!entrySource.includes("globalRecord[REGISTRY_KEY]")) violations.push("persistent studio registry is not stored on globalThis");
  if (!entrySource.includes("studio-claim-denied")) violations.push("connected card ownership protection missing");
  if (!entrySource.includes("claimNextConnectedCard")) violations.push("persistent studio handover after card disconnect missing");
  if (!entrySource.includes("host.append(studio)")) violations.push("persistent studio shell is not adopted by the active card host");
  const previewProgressSource = readSource(join(frontendDirectory, "studio-preview-progress-popup.ts"));
  const globalJobPopupSource = readSource(join(frontendDirectory, "global-job-popup-v3.ts"));
  if (entrySource.includes('import "./studio-preview-progress-popup.js"') || entrySource.includes("<studio-preview-progress-popup")) violations.push("layer-preview must be a list entry, not a second standalone popup");
  if (!entrySource.includes("<ultimate-3d-global-job-popup></ultimate-3d-global-job-popup>")) violations.push("single right-side popup list mount missing");
  if (!globalJobPopupSource.includes("#previewWorkflowKey(): string")) violations.push("independent layer-preview workflow identity missing");
  if (!globalJobPopupSource.includes('`preview:${this.#sliceTrace.traceId}`')) violations.push("layer-preview dismissal key missing");
  if (!globalJobPopupSource.includes("const previewCard = visiblePreview")) violations.push("layer-preview list entry missing");
  if (!globalJobPopupSource.includes("this.#dismissButton(previewWorkflowKey, previewTitle)")) violations.push("layer-preview per-item close button missing");
  if (!globalJobPopupSource.includes("preparationCard + slicerCard + previewCard + transferCard + printCards + traceCard + studioCard")) violations.push("right-side popup list ordering is incomplete");
  if (!globalJobPopupSource.includes("(loadedLayers / layerCount) * 100")) violations.push("layer-preview list entry does not use measured layer progress");
  if (!globalJobPopupSource.includes("metrics?.etaSeconds")) violations.push("layer-preview list entry does not use measured preview ETA");
  if (!globalJobPopupSource.includes("ETA wird nach dem ersten Datenblock berechnet")) violations.push("layer-preview pending-ETA explanation missing");
  if (!globalJobPopupSource.includes("@keyframes calculate{from{transform:scaleX(0)}to{transform:scaleX(1)}}")) violations.push("one-way 0-to-100 calculation animation missing");
  if (globalJobPopupSource.includes("alternate") || previewProgressSource.includes("alternate")) violations.push("calculation progress must never reverse direction");
  if (globalJobPopupSource.includes("active ? 50 : 100")) violations.push("fixed placeholder calculation progress remains");
  if (!globalJobPopupSource.includes("linear-gradient(155deg,rgba(7,28,43,.98),rgba(5,17,29,.98))")) violations.push("right-side popup list does not retain the layer-preview surface design");
  if (!globalJobPopupSource.includes('<div class="eyebrow">Vorgänge</div>')) violations.push("right-side popup list shared header design missing");
  for (const control of ['id="collapse"', 'id="camera-toggle"', 'id="expand"', 'id="close"', "this.#cameraVisible = !this.#cameraVisible", "this.#expanded = !this.#expanded", "this.#collapsed = !this.#collapsed", "this.#dismissedSignature = this.#lastSignature", "[data-dismiss-item]", "[data-target]", "overflow-y:auto", "overflow:auto"]) {
    if (!globalJobPopupSource.includes(control)) violations.push(`global job popup functionality marker missing: ${control}`);
  }

  const navigationSource = readSource(join(frontendDirectory, "app-shell-view.ts"));
  if (!navigationSource.includes('["slicing-server", "Slicing-Server", "≋"]')) violations.push("Slicing-Server navigation entry missing");
  if (navigationSource.indexOf('["slicing-server", "Slicing-Server", "≋"]') < navigationSource.indexOf('["system", "System", "⌁"]')) violations.push("Slicing-Server must be placed below System");
  const routerSource = readSource(join(frontendDirectory, "router.ts"));
  if (!routerSource.includes('| { name: "slicing-server" }')) violations.push("Slicing-Server route type missing");
  const shellSource = readSource(join(frontendDirectory, "app-shell-v4.ts"));
  if (!shellSource.includes('"slicing-server": "ultimate-3d-slicing-server-workspace"')) violations.push("Slicing-Server route is not mounted as its own workspace");

  if (!navigationSource.includes(".nav-buttons{display:flex;width:100%;min-width:0")) violations.push("mobile navigation does not own a stable horizontal scroller");
  for (const marker of ["touch-action:pan-x", "overscroll-behavior-x:contain", "-webkit-overflow-scrolling:touch", "scrollbar-width:none"]) {
    if (!navigationSource.includes(marker)) violations.push("mobile navigation iOS scrolling marker missing: " + marker);
  }
  if (!navigationSource.includes("nav{display:grid;grid-template-columns:minmax(0,1fr);padding:0;overflow:hidden")) violations.push("mobile nav container still competes with the horizontal tab scroller");

  for (const marker of ['"pageshow"', '"focus"', '"online"', "IntersectionObserver", "FRAME_REQUEST_TIMEOUT_MS", "controller.abort()", "signal: controller.signal"]) {
    if (!cameraSource.includes(marker)) violations.push("camera mobile lifecycle marker missing: " + marker);
  }
  if (cameraSource.includes("this.getClientRects().length > 0")) violations.push("camera refresh still depends on unreliable iOS getClientRects visibility");

  const systemSource = readSource(join(frontendDirectory, "system-workspace-v5.ts"));
  if (systemSource.includes('data-tab="slicing"')) violations.push("Slicing-Server is still embedded as a System tab");
  const slicingServerSource = readSource(join(frontendDirectory, "slicing-server-workspace.ts"));
  if (!slicingServerSource.includes("#newJobOpen = false")) violations.push("Slicing-Server new-job accordion state missing");
  if (!slicingServerSource.includes("#diagnosticsOpen = false")) violations.push("Slicing-Server diagnostics accordion state missing");
  if (!slicingServerSource.includes('#newJobOpen ? "open" : ""')) violations.push("New-job accordion open state is not restored after refresh");
  if (!slicingServerSource.includes('#diagnosticsOpen ? "open" : ""')) violations.push("Diagnostics accordion open state is not restored after refresh");
  if (!slicingServerSource.includes("10_000")) violations.push("Slicing-Server refresh interval contract missing");
  if (!slicingServerSource.includes("printer_slicing_server/job")) violations.push("Slicing-Server job-detail API is not wired");
  if (!slicingServerSource.includes("Vollständige Server-Daten")) violations.push("Slicing-Server raw server detail is missing");
  if (!slicingServerSource.includes("Bambu-Zeitanteile")) violations.push("Slicing-Server Bambu feature timing view is missing");

  const transportSource = readSource(join(frontendDirectory, "ha-api-transport.ts"));
  if (!transportSource.includes("export async function authenticatedUpload(")) violations.push("ha-api-transport.ts: authenticated upload-progress transport missing");
  if (!transportSource.includes('xhr.upload.addEventListener("progress"')) violations.push("ha-api-transport.ts: real browser upload progress listener missing");
  if (!transportSource.includes("uploadProgressSnapshot(event.loaded")) violations.push("ha-api-transport.ts: upload progress does not use measured bytes");
  if ((transportSource.match(/headers\.set\("Authorization"/g) ?? []).length < 2) violations.push("ha-api-transport.ts: upload transport does not share the canonical HA bearer-token path");
  const plateSliceSource = readSource(join(frontendDirectory, "plate-slice-api.ts"));
  if (!plateSliceSource.includes("authenticatedUpload(")) violations.push("plate-slice-api.ts: jobs-plate upload does not use progress-capable transport");
  if (!plateSliceSource.includes("onUploadProgress?: (progress: AuthenticatedUploadProgress)")) violations.push("plate-slice-api.ts: upload progress callback contract missing");
  if (!plateSliceSource.includes("project_name?: string;")) violations.push("plate-slice-api.ts: gallery project-name contract missing");
  if (!studioSource.includes('project_name: this.#inspection?.filename || this.#file?.name || ""')) violations.push("studio project-name forwarding from gallery/source file missing");
  if (!studioSource.includes("processedBytes: upload.loadedBytes")) violations.push("studio upload checkpoint does not report real transferred bytes");
  if (!studioSource.includes("totalBytes: upload.totalBytes")) violations.push("studio upload checkpoint does not report total transfer bytes");
  if (!studioSource.includes("rateBytesPerSecond: upload.rateBytesPerSecond")) violations.push("studio upload checkpoint does not report measured transfer rate");
  if (!studioSource.includes("etaSeconds: upload.etaSeconds")) violations.push("studio upload checkpoint does not report measured transfer ETA");

  const slicingApiSource = readSource(join(frontendDirectory, "slicing-api.ts"));
  if (!slicingApiSource.includes("callHomeAssistantApi")) violations.push("Slicer JSON polling does not use Home Assistant callApi transport");
  if (!slicingApiSource.includes("SliceSlicerProgress")) violations.push("Slicer API live progress contract missing");
  if (!slicingApiSource.includes("engine_result?: SliceEngineResult")) violations.push("Slicer API engine result contract missing");
  const jsonRequestStart = slicingApiSource.indexOf("async function jsonRequest<T>");
  const jsonRequestEnd = slicingApiSource.indexOf("\nexport async function fetchSlicerProvider", jsonRequestStart);
  if (jsonRequestStart < 0 || jsonRequestEnd < 0) violations.push("Slicer JSON request block could not be verified");
  else if (slicingApiSource.slice(jsonRequestStart, jsonRequestEnd).includes("authenticatedFetch")) violations.push("Slicer JSON polling still uses direct bearer-token fetch");

  if (violations.length > 0) throw new Error(`Frontend source policy failed:\n${violations.join("\n")}`);
  return { forbiddenPatternCount: forbiddenPatterns.length, navigationAuthorities };
}

console.log("");
console.log("========================================================================");
console.log("Ultimate 3D Printing Studio V6 - Frontend Logic Tests");
console.log("========================================================================");
console.log("");

let policyResult = null;
try {
  policyResult = runSourcePolicyGate();
  console.log(`Source policy: OK (${policyResult.forbiddenPatternCount} Patchmuster geprüft)`);
  console.log(`Navigation authority: ${policyResult.navigationAuthorities[0]}`);
  console.log("Persistent printer action dialog: OK");
  console.log("Authoritative AMS direct-print mapping: OK");
  console.log("Persistent studio reconnect lifecycle: OK");
  console.log("Persistent Studio workspace and non-destructive environment refresh: OK");
  console.log("Observed A1/Bambu print phases with false-stage-zero guard: OK");
  console.log("Non-overlapping printer dialog and studio viewport layout: OK");
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}

if (process.exitCode !== 1 && !existsSync(testEntry)) {
  console.error(`Test entry was not found: ${testEntry}`);
  process.exitCode = 1;
}

if (process.exitCode !== 1) {
  rmSync(outputDirectory, { recursive: true, force: true });
  mkdirSync(outputDirectory, { recursive: true });
  await build({ absWorkingDir: root, entryPoints: [testEntry], outfile: outputFile, bundle: true, format: "esm", platform: "node", target: ["node20"], packages: "external", sourcemap: false, minify: false, legalComments: "none", logLevel: "info" });
  const result = spawnSync(process.execPath, ["--test", outputFile], { cwd: root, stdio: "inherit", shell: false, env: { ...process.env, NODE_NO_WARNINGS: "1" } });
  process.exitCode = typeof result.status === "number" ? result.status : 1;
}

console.log("");
console.log("No synthetic DOM library was used.");
console.log("Terminal bleibt offen.");
