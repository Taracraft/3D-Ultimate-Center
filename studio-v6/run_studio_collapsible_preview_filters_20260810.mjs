import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const migrationPath = join(root, "apply_studio_collapsible_preview_filters_20260810.mjs");
const buildPath = join(root, "build_frontend.mjs");
let migration = readFileSync(migrationPath, "utf8");

function replaceMigrationCallByLabel(source, label, oldValue, newValue) {
  const endMarker = `, 1, "${label}");`;
  const end = source.indexOf(endMarker);
  if (end < 0) throw new Error(`Migration label not found: ${label}`);
  const start = source.lastIndexOf("ws = replaceExact(ws,", end);
  if (start < 0) throw new Error(`Migration call start not found: ${label}`);
  const replacement = [
    "ws = replaceExact(ws,",
    JSON.stringify(oldValue) + ",",
    JSON.stringify(newValue) + `, 1, "${label}");`,
  ].join("\n");
  return source.slice(0, start) + replacement + source.slice(end + endMarker.length);
}

const previewDataOld = [
  '      const features = [...new Set((currentLayer?.segments ?? []).map((segment) => String(segment[7] || "Modell")))];',
  '      const categories = new Map<string, string>();',
  '      for (const segment of currentLayer?.segments ?? []) categories.set(String(segment[7] || "Modell"), String(segment[8] || "model"));',
].join("\n");
const previewDataNew = [
  previewDataOld,
  '      const featureFilter = PREVIEW_FEATURE_KEYS.map((key) => `<label class="preview-filter-item"><input type="checkbox" data-preview-feature="${key}" ${this.#previewVisibleFeatures.has(key) ? "checked" : ""}><i style="--feature-color:${previewFeatureColor(key)}"></i><span>${escapeHtml(previewFeatureLabel(key))}</span></label>`).join("");',
  '      const materials = (plate.toolColors.length ? plate.toolColors : this.#materialChoices(plate).map((item) => item.color)).map(normalizeColor);',
  '      const materialRows = materials.map((color, index) => `<div class="preview-material-row"><i style="--material-color:${color}"></i><span>Filament ${index + 1}</span><small>${color.toUpperCase()}</small></div>`).join("");',
].join("\n");
migration = replaceMigrationCallByLabel(migration, "preview sidebar data", previewDataOld, previewDataNew);

const legendOld = [
  '      const legend = features.slice(0, 12).map((feature) => {',
  '        const color = featurePreviewColor(feature, categories.get(feature) || "model");',
  '        return `<span class="feature-chip"><i style="background:${color}"></i>${escapeHtml(feature)}</span>`;',
  '      }).join("");',
].join("\n");
const legendNew = [
  legendOld,
  '      const filterSection = `<div class="section preview-filter"><div class="preview-filter-head"><b>Sichtbare Druckbahnen</b><span class="preview-filter-actions"><button id="preview-feature-all" type="button">Alle</button><button id="preview-feature-none" type="button">Keine</button></span></div><small>Druckbahntypen können wie in Bambu Studio vollständig aus der 3D-Vorschau ausgeblendet werden.</small><div class="preview-filter-grid">${featureFilter}</div></div>`;',
  '      const materialSection = materialRows ? `<details class="preview-material-details" id="preview-material-summary" ${this.#previewMaterialOpen ? "open" : ""}><summary>Materialzusammenfassung · ${materials.length} Filament(e)</summary><div class="preview-material-body">${materialRows}</div></details>` : "";',
].join("\n");
migration = replaceMigrationCallByLabel(migration, "preview filter/material sections", legendOld, legendNew);

const previewTailOld = Buffer.from("JHt0aGlzLiNwcmV2aWV3Q29sb3JNb2RlID09PSAiZmVhdHVyZSIgJiYgbGVnZW5kID8gYDxkaXYgY2xhc3M9ImZlYXR1cmUtbGVnZW5kIj4ke2xlZ2VuZH08L2Rpdj5gIDogIiJ9JHtwbGF0ZS5zdGFnZSA9PT0gInNsaWNlZCIgPyAnPGJ1dHRvbiBpZD0ibWFyay1wcmludGVkIj5BbHMgZ2VkcnVja3QgbWFya2llcmVuPC9idXR0b24+JyA6ICIifTwvZGl2PmA7", "base64").toString("utf8");
const previewTailNew = Buffer.from("JHt0aGlzLiNwcmV2aWV3Q29sb3JNb2RlID09PSAiZmVhdHVyZSIgJiYgbGVnZW5kID8gYDxkaXYgY2xhc3M9ImZlYXR1cmUtbGVnZW5kIj4ke2xlZ2VuZH08L2Rpdj5gIDogIiJ9JHtmaWx0ZXJTZWN0aW9ufSR7bWF0ZXJpYWxTZWN0aW9ufSR7cGxhdGUuc3RhZ2UgPT09ICJzbGljZWQiID8gJzxidXR0b24gaWQ9Im1hcmstcHJpbnRlZCI+QWxzIGdlZHJ1Y2t0IG1hcmtpZXJlbjwvYnV0dG9uPicgOiAiIn08L2Rpdj5gOw==", "base64").toString("utf8");
migration = replaceMigrationCallByLabel(migration, "preview sidebar insert sections", previewTailOld, previewTailNew);

const bindingsOld = [
  '      host.querySelector<HTMLButtonElement>("#preview-material")?.addEventListener("click", () => {',
  '        this.#previewColorMode = "material";',
  '        this.#viewport?.setInstances(this.#displayInstances());',
  '        this.#renderSidebar();',
  '      });',
  '      host.querySelector<HTMLButtonElement>("#preview-feature")?.addEventListener("click", () => {',
  '        this.#previewColorMode = "material";',
  '        this.#viewport?.setInstances(this.#displayInstances());',
  '        this.#renderSidebar();',
  '      });',
].join("\n");
const bindingsNew = [
  '      host.querySelector<HTMLButtonElement>("#preview-material")?.addEventListener("click", () => {',
  '        this.#previewColorMode = "material";',
  '        this.#viewport?.setInstances(this.#displayInstances());',
  '        this.#renderSidebar();',
  '      });',
  '      host.querySelector<HTMLButtonElement>("#preview-feature")?.addEventListener("click", () => {',
  '        this.#previewColorMode = "feature";',
  '        this.#viewport?.setInstances(this.#displayInstances());',
  '        this.#renderSidebar();',
  '      });',
  '      host.querySelectorAll<HTMLInputElement>("[data-preview-feature]").forEach((input) => input.addEventListener("change", () => {',
  '        const key = input.dataset.previewFeature as PreviewFeatureKey;',
  '        if (input.checked) this.#previewVisibleFeatures.add(key); else this.#previewVisibleFeatures.delete(key);',
  '        this.#viewport?.setInstances(this.#displayInstances());',
  '      }));',
  '      host.querySelector<HTMLButtonElement>("#preview-feature-all")?.addEventListener("click", () => {',
  '        this.#previewVisibleFeatures = new Set(PREVIEW_FEATURE_KEYS);',
  '        this.#viewport?.setInstances(this.#displayInstances());',
  '        this.#renderSidebar();',
  '      });',
  '      host.querySelector<HTMLButtonElement>("#preview-feature-none")?.addEventListener("click", () => {',
  '        this.#previewVisibleFeatures.clear();',
  '        this.#viewport?.setInstances(this.#displayInstances());',
  '        this.#renderSidebar();',
  '      });',
  '      host.querySelector<HTMLDetailsElement>("#preview-material-summary")?.addEventListener("toggle", (event) => {',
  '        this.#previewMaterialOpen = (event.currentTarget as HTMLDetailsElement).open;',
  '      });',
].join("\n");
migration = replaceMigrationCallByLabel(migration, "preview bindings and feature bug fix", bindingsOld, bindingsNew);

migration = migration.replace('  if (value.includes("solid infill")) return "solid_infill";\n  if (value.includes("infill")) return "infill";\n  if (value.includes("bridge")) return "bridge";', '  if (value.includes("bridge")) return "bridge";\n  if (value.includes("solid infill")) return "solid_infill";\n  if (value.includes("infill")) return "infill";');
writeFileSync(migrationPath, migration, "utf8");

execFileSync(process.execPath, [migrationPath], { stdio: "inherit" });

let buildSource = readFileSync(buildPath, "utf8");
const runnerCall = 'execFileSync(process.execPath, [join(root, "run_studio_collapsible_preview_filters_20260810.mjs")], { stdio: "inherit" });\n';
const runnerImport = 'import { execFileSync } from "node:child_process";\n';
buildSource = buildSource.replace(runnerCall, "").replace(runnerImport, "");
writeFileSync(buildPath, buildSource, "utf8");
console.log("ONE_TIME_RUNNER_HOOK_REMOVED=1");
