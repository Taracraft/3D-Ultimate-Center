import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const frontend = join(root, "frontend");

function read(path) {
  return readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
}
function write(path, text) {
  writeFileSync(path, `\uFEFF${text}`, "utf8");
}
function exact(text, oldValue, newValue, label) {
  if (text.includes(newValue)) return text;
  if (!text.includes(oldValue)) throw new Error(`Quellmarker fehlt: ${label}`);
  return text.replace(oldValue, newValue);
}

// ---------------------------------------------------------------------------
// Support dropdown: no rerender on every click, public support-mode request.
// ---------------------------------------------------------------------------
{
  const path = join(frontend, "studio-process-options-panel.ts");
  let text = read(path);
  text = exact(
    text,
    `    this.#studioRoot?.addEventListener("change", this.#studioChanged);\n    this.#studioRoot?.addEventListener("click", this.#studioChanged);\n`,
    `    this.#studioRoot?.addEventListener("change", this.#studioChanged);\n`,
    "Supportpanel-Klicklistener entfernen",
  );
  text = exact(
    text,
    `    this.#studioRoot?.removeEventListener("change", this.#studioChanged);\n    this.#studioRoot?.removeEventListener("click", this.#studioChanged);\n`,
    `    this.#studioRoot?.removeEventListener("change", this.#studioChanged);\n`,
    "Supportpanel-Klicklistener Cleanup",
  );
  text = exact(
    text,
    `  readonly #studioChanged = (): void => this.#render();\n\n  get #plateId(): string { return this.getAttribute("plate-id") || "0"; }\n`,
    `  readonly #studioChanged = (event: Event): void => {\n    if (event.composedPath().includes(this)) return;\n    this.#render();\n  };\n\n  setSupportMode(mode: SupportMode): void {\n    this.#saveProcess({ ...this.#value, support_mode: mode });\n    requestAnimationFrame(() => this.#root.querySelector<HTMLSelectElement>("#support-mode")?.focus());\n  }\n\n  get #plateId(): string { return this.getAttribute("plate-id") || "0"; }\n`,
    "Supportpanel-API",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Colors label, warning styling.
// ---------------------------------------------------------------------------
{
  const path = join(frontend, "studio-mega-ui-v2.ts");
  let text = read(path);
  text = text.replace('<button id="view-colors">Mehrfarben</button>', '<button id="view-colors">Farben</button>');
  text = text.replace('<button data-mode="colors">Mehrfarben</button>', '<button data-mode="colors">Farben</button>');
  text = exact(
    text,
    `.error-modal-actions button{min-width:120px;padding:8px 13px;border:1px solid #d65763;border-radius:5px;background:#6a222c;color:#fff;font-weight:800}\${STUDIO_PROFILE_CSS}\n`,
    `.error-modal-actions button{min-width:120px;padding:8px 13px;border:1px solid #d65763;border-radius:5px;background:#6a222c;color:#fff;font-weight:800}.support-warning-modal .error-modal-panel{border-color:#d79b36;background:linear-gradient(180deg,#2d2311,#171108)}.support-warning-modal .error-modal-head{border-bottom-color:#76531d}.support-warning-modal .error-modal-head strong{color:#ffe4ad}.support-warning-list{margin:10px 0 0;padding-left:19px;color:#ffe9bf}.support-warning-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px;padding:0 16px 16px}.support-warning-actions button{min-width:130px;padding:8px 12px;border:1px solid #8c6a32;border-radius:5px;background:#2a2113;color:#fff;font-weight:800}.support-warning-actions .primary{border-color:#d79b36;background:#6a4916}.support-warning-actions .danger{border-color:#d65763;background:#6a222c}\${STUDIO_PROFILE_CSS}\n`,
    "Supportwarnung-CSS",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Analyze floating shells before slicing and offer an explicit override.
// ---------------------------------------------------------------------------
{
  const path = join(frontend, "studio-mega-workspace-v2.ts");
  let text = read(path);
  text = exact(
    text,
    `import { createPlateSliceJob, type SliceMaterialPlan } from "./plate-slice-api.js";\n`,
    `import { createPlateSliceJob, loadSliceProcessOverrides, type SliceMaterialPlan } from "./plate-slice-api.js";\nimport { analyzeFloatingSupportNeeds, type FloatingSupportIssue } from "./floating-support-analysis.js";\n`,
    "Supportanalyse-Import",
  );

  const method = [
    "  async #supportDecision(issues: readonly FloatingSupportIssue[]): Promise<\"cancel\" | \"enable\" | \"continue\"> {",
    "    this.#root.querySelector(\"#support-warning-modal\")?.remove();",
    "    return await new Promise((resolve) => {",
    "      const modal = document.createElement(\"div\");",
    "      modal.id = \"support-warning-modal\";",
    "      modal.className = \"error-modal support-warning-modal\";",
    "      const details = issues.slice(0, 8).map((issue) => {",
    "        const shells = issue.floatingShellCount === 1 ? \"1 freischwebender Bereich\" : `${issue.floatingShellCount} freischwebende Bereiche`;",
    "        return `<li><b>${escapeHtml(issue.name)}</b> · ${shells} · Abstand mindestens ${issue.minimumGapMm.toFixed(2)} mm</li>`;",
    "      }).join(\"\");",
    "      const more = issues.length > 8 ? `<li>… und ${issues.length - 8} weitere Objekte</li>` : \"\";",
    "      modal.innerHTML = `<section class=\"error-modal-panel\" role=\"dialog\" aria-modal=\"true\" aria-labelledby=\"support-warning-title\"><header class=\"error-modal-head\"><strong id=\"support-warning-title\">Support empfohlen</strong></header><div class=\"error-modal-body\">Mindestens ein Teil beginnt ohne Verbindung zur Druckplatte oder zu einem darunterliegenden Teil. Ohne Support kann der Druck in der Luft beginnen und fehlschlagen.<ul class=\"support-warning-list\">${details}${more}</ul></div><footer class=\"support-warning-actions\"><button id=\"support-warning-cancel\" type=\"button\">Abbrechen</button><button class=\"primary\" id=\"support-warning-enable\" type=\"button\">Support auswählen</button><button class=\"danger\" id=\"support-warning-continue\" type=\"button\">Auf eigene Gefahr ohne Support</button></footer></section>`;",
    "      const finish = (value: \"cancel\" | \"enable\" | \"continue\"): void => {",
    "        modal.remove();",
    "        resolve(value);",
    "      };",
    "      modal.querySelector<HTMLButtonElement>(\"#support-warning-cancel\")?.addEventListener(\"click\", () => finish(\"cancel\"));",
    "      modal.querySelector<HTMLButtonElement>(\"#support-warning-enable\")?.addEventListener(\"click\", () => finish(\"enable\"));",
    "      modal.querySelector<HTMLButtonElement>(\"#support-warning-continue\")?.addEventListener(\"click\", () => finish(\"continue\"));",
    "      this.#root.append(modal);",
    "    });",
    "  }",
    "",
  ].join("\n");
  text = exact(
    text,
    `  async #slice(): Promise<void> {\n`,
    `${method}  async #slice(): Promise<void> {\n`,
    "Supportwarnung-Methode",
  );

  text = exact(
    text,
    `    if (!plate.instances.length || plate.stage === "slicing") return;\n    let materialPlan: SliceMaterialPlan;\n`,
    `    if (!plate.instances.length || plate.stage === "slicing") return;\n    const processOptions = loadSliceProcessOverrides();\n    if (processOptions.support_mode === "off") {\n      const supportIssues = analyzeFloatingSupportNeeds(plate.instances);\n      if (supportIssues.length) {\n        const decision = await this.#supportDecision(supportIssues);\n        if (decision === "cancel") return;\n        if (decision === "enable") {\n          const panel = this.#root.querySelector("studio-process-options-panel") as (HTMLElement & { setSupportMode?: (mode: "normal" | "tree" | "off") => void }) | null;\n          panel?.setSupportMode?.("normal");\n          this.#status = "Normal-Support wurde aktiviert. Supporttyp und Grenzwinkel können rechts angepasst werden.";\n          this.#renderStatus();\n          return;\n        }\n      }\n    }\n    let materialPlan: SliceMaterialPlan;\n`,
    "Supportwarnung-vor-Slice",
  );
  write(path, text);
}

// ---------------------------------------------------------------------------
// Logic tests for on-bed, floating object and detached floating shell.
// ---------------------------------------------------------------------------
{
  const path = join(root, "frontend-tests", "logic.test.ts");
  let text = read(path);
  text = exact(
    text,
    `import { analyzeGeometry, layerCount, layerZ, sliceSegmentsAtZ } from "../frontend/stl-layer-preview.js";\n`,
    `import { analyzeFloatingSupportNeeds } from "../frontend/floating-support-analysis.js";\nimport { analyzeGeometry, layerCount, layerZ, sliceSegmentsAtZ } from "../frontend/stl-layer-preview.js";\n`,
    "Supportanalyse-Testimport",
  );
  const tests = `\n\ntest("support analysis ignores geometry resting on the bed", () => {\n  const geometry: MeshGeometry = {\n    positions: new Float32Array([0,0,0, 10,0,0, 0,10,0]),\n    normals: new Float32Array(9),\n    triangleCount: 1,\n    boundsMin: [0,0,0],\n    boundsMax: [10,10,0],\n  };\n  const issues = analyzeFloatingSupportNeeds([{ id: "bed", name: "Bed", geometry, position: [0,0,0], rotation: [0,0,0], scale: [1,1,1], color: "#fff", visible: true }]);\n  assert.equal(issues.length, 0);\n});\n\ntest("support analysis detects a complete floating object", () => {\n  const geometry: MeshGeometry = {\n    positions: new Float32Array([0,0,0, 10,0,0, 0,10,0]),\n    normals: new Float32Array(9),\n    triangleCount: 1,\n    boundsMin: [0,0,0],\n    boundsMax: [10,10,0],\n  };\n  const issues = analyzeFloatingSupportNeeds([{ id: "floating", name: "Floating", geometry, position: [0,0,4], rotation: [0,0,0], scale: [1,1,1], color: "#fff", visible: true }]);\n  assert.equal(issues.length, 1);\n  assert.equal(issues[0]?.floatingShellCount, 1);\n  assert.equal(issues[0]?.minimumGapMm, 4);\n});\n\ntest("support analysis detects a detached floating shell inside one mesh", () => {\n  const geometry: MeshGeometry = {\n    positions: new Float32Array([\n      0,0,0, 10,0,0, 0,10,0,\n      20,20,5, 30,20,5, 20,30,5,\n    ]),\n    normals: new Float32Array(18),\n    triangleCount: 2,\n    boundsMin: [0,0,0],\n    boundsMax: [30,30,5],\n  };\n  const issues = analyzeFloatingSupportNeeds([{ id: "mixed", name: "Mixed", geometry, position: [0,0,0], rotation: [0,0,0], scale: [1,1,1], color: "#fff", visible: true }]);\n  assert.equal(issues.length, 1);\n  assert.equal(issues[0]?.floatingShellCount, 1);\n  assert.equal(issues[0]?.minimumGapMm, 5);\n});\n`;
  if (!text.includes('test("support analysis ignores geometry resting on the bed"')) text += tests;
  write(path, text);
}

console.log("Supportwarnung, stabile Supportauswahl und Farben-Beschriftung wurden übernommen.");
