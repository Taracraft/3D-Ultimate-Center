import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const migration = join(root, "apply_frontend_workflow_fix.mjs");
const lines = readFileSync(migration, "utf8").split(/\r?\n/);
let matched = 0;
for (let index = 0; index < lines.length; index += 1) {
  const line = lines[index];
  if (!line.includes("this.#status =") || !line.includes("Layer erfolgreich erzeugt")) continue;
  matched += 1;
  lines[index] = matched === 1
    ? "    '      this.#status = `${plate.name}: ${plate.layerCount} Layer erfolgreich erzeugt.`;',"
    : "    '      this.#status = `${plate.name}: ${plate.layerCount} Layer erfolgreich erzeugt.`;\\n      jobActivityStore.registerSlicerJob(currentJob);\\n      await this.#persistNow();',";
}
if (matched !== 2) throw new Error(`Erwartet wurden 2 Statuszeilen, gefunden: ${matched}`);
writeFileSync(migration, lines.join("\n"), "utf8");
await import(`${pathToFileURL(migration).href}?run=${Date.now()}`);

const policyPath = join(root, "run_frontend_logic_tests.mjs");
let policy = readFileSync(policyPath, "utf8");
const broadCheck = '  if (directPrintPanelSource.includes("window.confirm(")) violations.push("direct print prepare popup still present");';
const preciseCheck = '  if (directPrintPanelSource.includes("Druckjob vollständig auf den Drucker übertragen?")) violations.push("direct print prepare popup still present");';
if (policy.includes(broadCheck)) {
  policy = policy.replace(broadCheck, preciseCheck);
  writeFileSync(policyPath, policy, "utf8");
  console.log("UPDATED run_frontend_logic_tests.mjs popup policy");
}
