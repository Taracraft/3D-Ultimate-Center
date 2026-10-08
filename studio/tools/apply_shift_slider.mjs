import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (path) => readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
const write = (path, text) => writeFileSync(path, `\uFEFF${text}`, "utf8");
const block = (...lines) => `${lines.join("\n")}\n`;
function exact(text, oldValue, newValue, label) {
  if (text.includes(newValue)) return text;
  if (!text.includes(oldValue)) throw new Error(`Quellmarker fehlt: ${label}`);
  return text.replace(oldValue, newValue);
}

const workspacePath = join(root, "frontend", "studio-mega-workspace-v2.ts");
let text = read(workspacePath);
text = text.replaceAll("event.ctrlKey || event.metaKey", "event.ctrlKey || event.metaKey || event.shiftKey");
text = text.replaceAll("Strg+Klick", "Strg/Shift+Klick");
const oldSummary = '<div class="preview-summary"><span>${(currentLayer?.segments.length ?? 0).toLocaleString("de-DE")} Bahnen</span><span>${(currentLayer?.extrusion_mm ?? 0).toFixed(2)} mm Extrusion</span></div>';
const newSummary = '<div class="preview-summary"><span id="preview-track-count">${(currentLayer?.segments.length ?? 0).toLocaleString("de-DE")} Bahnen</span><span id="preview-extrusion">${(currentLayer?.extrusion_mm ?? 0).toFixed(2)} mm Extrusion</span></div>';
text = exact(text, oldSummary, newSummary, "Layer-Summary");
text = exact(text,
  block('      host.querySelector<HTMLInputElement>("#layer")?.addEventListener("input", (event) => {','        plate.visibleLayer = Number((event.currentTarget as HTMLInputElement).value);','        this.#viewport?.setInstances(this.#displayInstances());','        this.#renderSidebar();','      });'),
  block('      const layerSlider = host.querySelector<HTMLInputElement>("#layer");','      layerSlider?.addEventListener("input", (event) => {','        const value = Number((event.currentTarget as HTMLInputElement).value);','        plate.visibleLayer = value;','        const layer = plate.layers.find((item) => item.index === value);','        const label = this.#root.querySelector<HTMLElement>("#layer-label");','        if (label) label.textContent = "Layer " + (value + 1) + " / " + plate.layerCount + " · Z " + (layer?.z ?? 0).toFixed(2) + " mm";','        const tracks = this.#root.querySelector<HTMLElement>("#preview-track-count");','        if (tracks) tracks.textContent = (layer?.segments.length ?? 0).toLocaleString("de-DE") + " Bahnen";','        const extrusion = this.#root.querySelector<HTMLElement>("#preview-extrusion");','        if (extrusion) extrusion.textContent = (layer?.extrusion_mm ?? 0).toFixed(2) + " mm Extrusion";','        this.#viewport?.setInstances(this.#displayInstances());','      });','      layerSlider?.addEventListener("change", () => this.#renderSidebar());'),
  "Layer-Slider",
);
write(workspacePath, text);

const uiPath = join(root, "frontend", "studio-mega-ui-v2.ts");
let ui = read(uiPath).replaceAll("Strg+Klick", "Strg/Shift+Klick");
write(uiPath, ui);
console.log("Shift-Auswahl und flüssiger Layer-Schieber wurden in die TypeScript-Quellen übernommen.");
