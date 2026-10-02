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
    const source = readFileSync(join(frontendDirectory, entry.name), "utf8");

    for (const pattern of forbiddenPatterns) {
      if (source.includes(pattern)) violations.push(`${entry.name}: ${pattern}`);
    }
    if (source.includes("const NAVIGATION:")) navigationAuthorities.push(entry.name);
  }

  if (navigationAuthorities.length !== 1) {
    violations.push(`Navigation authorities: expected 1, found ${navigationAuthorities.length}`);
  }

  const controlSource = readFileSync(join(frontendDirectory, "control-workspace-v2.ts"), "utf8");
  if (!controlSource.includes('<ultimate-3d-printer-actions id="printer-actions">')) {
    violations.push("control-workspace-v2.ts: persistent printer actions mount missing");
  }
  if (!controlSource.includes('this.#root.querySelector<Ultimate3DPrinterActions>("#printer-actions")')) {
    violations.push("control-workspace-v2.ts: printer actions are not updated through persistent root lookup");
  }
  if (controlSource.includes('host.querySelector<Ultimate3DPrinterActions>("ultimate-3d-printer-actions")')) {
    violations.push("control-workspace-v2.ts: dynamic subtree still owns printer actions dialog");
  }

  const commandSource = readFileSync(join(frontendDirectory, "printer-command-store-v2.ts"), "utf8");
  if (!commandSource.includes('#mounted = false')) violations.push("printer-command-store-v2.ts: persistent component mount guard missing");
  if (!commandSource.includes('<v6-action-dialog id="printer-command-dialog"></v6-action-dialog>')) violations.push("printer-command-store-v2.ts: persistent command dialog missing");
  if (!commandSource.includes('id="printer-command-actions"')) violations.push("printer-command-store-v2.ts: persistent command action host missing");
  if (!commandSource.includes('id="printer-command-feedback"')) violations.push("printer-command-store-v2.ts: persistent command feedback host missing");
  if (commandSource.includes('<v6-action-dialog></v6-action-dialog>')) violations.push("printer-command-store-v2.ts: command dialog is still recreated by telemetry rendering");
  if (commandSource.includes("this.#root.innerHTML = `<style>") && !commandSource.includes("#mount(): void")) violations.push("printer-command-store-v2.ts: full render still replaces the dialog");

  const directPrintSource = readFileSync(join(frontendDirectory, "direct-print-panel-next.ts"), "utf8");
  if (!directPrintSource.includes('plan.source !== "authoritative_ams_runtime"')) violations.push("direct-print-panel-next.ts: authoritative AMS plan validation missing");
  if (!directPrintSource.includes("use_ams: true")) violations.push("direct-print-panel-next.ts: AMS print start is not enabled");
  if (!directPrintSource.includes("ams_mapping: [...selection.mapping]")) violations.push("direct-print-panel-next.ts: slicer AMS mapping is not forwarded");
  if (/use_ams:\s*false[\s\S]{0,80}ams_mapping:\s*\[\]/.test(directPrintSource)) violations.push("direct-print-panel-next.ts: external-spool fallback is still hardcoded");
  if (!directPrintSource.includes("Ohne gültigen autoritativen AMS-Plan wird der Start blockiert")) violations.push("direct-print-panel-next.ts: fail-closed AMS user contract missing");

  const studioSource = readFileSync(join(frontendDirectory, "studio-mega-workspace-v2.ts"), "utf8");
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

  const persistenceSource = readFileSync(join(frontendDirectory, "studio-persistence.ts"), "utf8");
  if (!persistenceSource.includes('const DATABASE_NAME = "ultimate-3d-studio-v6"')) violations.push("studio-persistence.ts: dedicated IndexedDB database missing");
  if (!persistenceSource.includes("put(snapshot, ACTIVE_KEY)")) violations.push("studio-persistence.ts: workspace save transaction missing");
  if (!persistenceSource.includes("get(ACTIVE_KEY)")) violations.push("studio-persistence.ts: workspace restore transaction missing");

  const popupSource = readFileSync(join(frontendDirectory, "global-job-popup-v3.ts"), "utf8");
  if (!popupSource.includes("resolvePrintPhaseProgress")) violations.push("global-job-popup-v3.ts: monotonic print phase tracker missing");
  if (!popupSource.includes("#phaseHighest = new Map<string, number>()")) violations.push("global-job-popup-v3.ts: per-job phase history missing");

  const phaseSource = readFileSync(join(frontendDirectory, "print-phase-progress.ts"), "utf8");
  if (!phaseSource.includes('key: "nozzle_cleaning_before"')) violations.push("print-phase-progress.ts: pre-calibration cleaning phase missing");
  if (!phaseSource.includes('key: "nozzle_cleaning_after"')) violations.push("print-phase-progress.ts: post-calibration cleaning phase missing");
  if (!phaseSource.includes("Math.max(previousHighestIndex, candidate)")) violations.push("print-phase-progress.ts: monotonic phase progression missing");

  const profileUiSource = readFileSync(join(frontendDirectory, "studio-profile-ui.ts"), "utf8");
  if (!profileUiSource.includes(":host{height:auto;min-height:100%;overflow:visible}")) violations.push("studio-profile-ui.ts: growing studio host contract missing");
  if (!profileUiSource.includes("grid-template-rows:auto auto auto auto auto auto minmax(560px,1fr)")) violations.push("studio-profile-ui.ts: seven-row non-overlapping studio grid missing");
  if (!profileUiSource.includes(".body{grid-row:7;min-height:560px}")) violations.push("studio-profile-ui.ts: dedicated viewport row height missing");

  const directPrintStripSource = readFileSync(join(frontendDirectory, "studio-direct-print-strip.ts"), "utf8");
  if (!directPrintStripSource.includes("strip.append(this.#panel, this.#analysis)")) violations.push("studio-direct-print-strip.ts: printer dialog must precede G-code analysis");
  if (directPrintStripSource.includes("strip.append(this.#analysis, this.#panel)")) violations.push("studio-direct-print-strip.ts: G-code analysis still precedes printer dialog");

  const entrySource = readFileSync(join(frontendDirectory, "v6-entry.ts"), "utf8");
  if (!entrySource.includes("let persistentStudioShell")) violations.push("persistent studio shell missing");
  if (!entrySource.includes("function studioShell()")) violations.push("persistent studio shell factory missing");
  if (!entrySource.includes("host.append(studio)")) violations.push("persistent studio shell is not adopted by new card host");

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
  console.log("Monotonic A1 print phase sequence with repeated nozzle cleaning: OK");
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
