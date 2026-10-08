import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (path) => readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
const write = (path, text) => writeFileSync(path, `\uFEFF${text}`, "utf8");

function exact(text, oldValue, newValue, label) {
  if (text.includes(newValue)) return text;
  if (!text.includes(oldValue)) throw new Error(`Quellmarker fehlt: ${label}`);
  return text.replace(oldValue, newValue);
}

const workspacePath = join(root, "frontend", "studio-mega-workspace-v2.ts");
let text = read(workspacePath);

text = exact(
  text,
  "  #selected = new Set<string>();\n  #assignments = new Map<string, string>();\n",
  "  #selected = new Set<string>();\n  #selectionAnchor: string | null = null;\n  #assignments = new Map<string, string>();\n",
  "Auswahlanker",
);

text = text.replaceAll(
  "(event.ctrlKey || event.metaKey || event.shiftKey)",
  "(event.ctrlKey || event.metaKey)",
);

const oldSelect = [
  "  #select(id: string | null, additive: boolean): void {",
  "    if (!id) {",
  "      if (!additive) this.#selected.clear();",
  "    } else if (additive) {",
  "      if (this.#selected.has(id)) this.#selected.delete(id);",
  "      else this.#selected.add(id);",
  "    } else {",
  "      this.#selected.clear();",
  "      this.#selected.add(id);",
  "    }",
  "    this.#refreshSelectionUi();",
  "  }",
].join("\n");
const newSelect = [
  "  #select(id: string | null, toggle: boolean, range = false): void {",
  "    const orderedIds = this.#plate().instances.map((item) => item.id);",
  "    if (!id) {",
  "      if (!toggle && !range) {",
  "        this.#selected.clear();",
  "        this.#selectionAnchor = null;",
  "      }",
  "    } else if (range) {",
  "      const anchorIndex = this.#selectionAnchor ? orderedIds.indexOf(this.#selectionAnchor) : -1;",
  "      const targetIndex = orderedIds.indexOf(id);",
  "      if (anchorIndex >= 0 && targetIndex >= 0) {",
  "        const start = Math.min(anchorIndex, targetIndex);",
  "        const end = Math.max(anchorIndex, targetIndex);",
  "        this.#selected = new Set(orderedIds.slice(start, end + 1));",
  "      } else {",
  "        this.#selected = new Set([id]);",
  "        this.#selectionAnchor = id;",
  "      }",
  "    } else if (toggle) {",
  "      if (this.#selected.has(id)) this.#selected.delete(id);",
  "      else this.#selected.add(id);",
  "      this.#selectionAnchor = id;",
  "    } else {",
  "      this.#selected = new Set([id]);",
  "      this.#selectionAnchor = id;",
  "    }",
  "    this.#refreshSelectionUi();",
  "  }",
].join("\n");
text = exact(text, oldSelect, newSelect, "Shift-Bereichsauswahl");

text = text.replaceAll(
  "this.#select(button.dataset.object || null, event.ctrlKey || event.metaKey || event.shiftKey)",
  "this.#select(button.dataset.object || null, event.ctrlKey || event.metaKey, event.shiftKey)",
);
text = text.replaceAll(
  "this.#select(this.#viewport?.pick(event.clientX, event.clientY) ?? null, event.ctrlKey || event.metaKey || event.shiftKey)",
  "this.#select(this.#viewport?.pick(event.clientX, event.clientY) ?? null, event.ctrlKey || event.metaKey, event.shiftKey)",
);

text = exact(
  text,
  "      this.#selected = new Set(this.#plate().instances.map((item) => item.id));\n      this.#refreshSelectionUi();\n",
  "      this.#selected = new Set(this.#plate().instances.map((item) => item.id));\n      this.#selectionAnchor = this.#plate().instances[0]?.id ?? null;\n      this.#refreshSelectionUi();\n",
  "Strg-A-Anker",
);
text = exact(
  text,
  "      this.#selected.clear();\n      this.#refreshSelectionUi();\n    });\n    on(\"frame-all\"",
  "      this.#selected.clear();\n      this.#selectionAnchor = null;\n      this.#refreshSelectionUi();\n    });\n    on(\"frame-all\"",
  "Auswahl-leeren-Anker",
);

text = exact(
  text,
  "  #purgeTowerData(plate = this.#plate()): { instances: MeshInstance[]; width: number; height: number; flushVolume: number; colorCount: number } {",
  "  #purgeTowerData(plate = this.#plate()): { instances: MeshInstance[]; width: number; height: number; flushVolume: number; colorCount: number; x: number; y: number; brim: number } {",
  "Turm-Rueckgabe",
);
text = exact(
  text,
  "    if (keys.length <= 1 || stored.enabled === false) return { instances: [], width: 0, height: 0, flushVolume: 0, colorCount: keys.length };",
  "    if (keys.length <= 1 || stored.enabled === false) return { instances: [], width: 0, height: 0, flushVolume: 0, colorCount: keys.length, x: 0, y: 0, brim: 0 };",
  "Turm-Leerwert",
);
text = exact(
  text,
  [
    "    const width = Math.max(25, Math.min(60, Math.ceil(Math.sqrt(requiredArea) / 2) * 2));",
    "    const x = Math.max(width / 2, Math.min(plate.width - width / 2, Number(stored.position_x ?? plate.width - width / 2 - 8)));",
    "    const y = Math.max(width / 2, Math.min(plate.depth - width / 2, Number(stored.position_y ?? plate.depth - width / 2 - 8)));",
  ].join("\n"),
  [
    "    const width = Math.max(25, Math.min(60, Math.ceil(Math.sqrt(requiredArea) / 2) * 2));",
    "    const brim = Math.max(0, Math.min(20, Number(stored.brim_width_mm ?? 3)));",
    "    const visibleInset = 18;",
    "    const minimumCenter = width / 2 + brim + visibleInset;",
    "    const maximumX = Math.max(minimumCenter, plate.width - width / 2 - brim - visibleInset);",
    "    const maximumY = Math.max(minimumCenter, plate.depth - width / 2 - brim - visibleInset);",
    "    const x = Math.max(minimumCenter, Math.min(maximumX, Number(stored.position_x ?? maximumX)));",
    "    const y = Math.max(minimumCenter, Math.min(maximumY, Number(stored.position_y ?? maximumY)));",
  ].join("\n"),
  "Turm-Sicherheitsbereich",
);
text = exact(
  text,
  "    return { instances, width, height, flushVolume, colorCount: keys.length };",
  "    return { instances, width, height, flushVolume, colorCount: keys.length, x, y, brim };",
  "Turm-Rueckgabewerte",
);
text = exact(
  text,
  "    const tower = loadPlatePurgeTower(plate.id);\n    return {",
  [
    "    const tower = loadPlatePurgeTower(plate.id);",
    "    const towerData = this.#purgeTowerData(plate);",
    "    savePlatePurgeTower(plate.id, {",
    "      ...tower,",
    "      width_mm: towerData.width || tower.width_mm,",
    "      brim_width_mm: towerData.brim || tower.brim_width_mm,",
    "      position_x: towerData.x || tower.position_x,",
    "      position_y: towerData.y || tower.position_y,",
    "    });",
    "    return {",
  ].join("\n"),
  "Turm-Plan-Daten",
);
text = exact(
  text,
  [
    "        enabled: usedChoices.length > 1 && tower.enabled !== false,",
    "        width_mm: this.#purgeTowerData().width,",
    "        flush_multiplier: Math.max(.1, Number(tower.flush_multiplier ?? 1)),",
  ].join("\n"),
  [
    "        enabled: usedChoices.length > 1 && tower.enabled !== false,",
    "        width_mm: towerData.width,",
    "        brim_width_mm: towerData.brim,",
    "        position_x: towerData.x,",
    "        position_y: towerData.y,",
    "        flush_multiplier: Math.max(.1, Number(tower.flush_multiplier ?? 1)),",
  ].join("\n"),
  "Turm-Plan-Position",
);

text = exact(
  text,
  [
    "          initialX: Number(purge.position_x ?? this.#plate().width - 30),",
    "          initialY: Number(purge.position_y ?? this.#plate().depth - 30),",
  ].join("\n"),
  [
    "          initialX: this.#purgeTowerData().x || Number(purge.position_x ?? this.#plate().width - 30),",
    "          initialY: this.#purgeTowerData().y || Number(purge.position_y ?? this.#plate().depth - 30),",
  ].join("\n"),
  "Turm-Drag-Start",
);
text = exact(
  text,
  [
    "        const x = Math.max(data.width / 2, Math.min(this.#plate().width - data.width / 2, purgeDrag.initialX + (event.clientX - purgeDrag.startX) * .28));",
    "        const y = Math.max(data.width / 2, Math.min(this.#plate().depth - data.width / 2, purgeDrag.initialY - (event.clientY - purgeDrag.startY) * .28));",
    "        savePlatePurgeTower(this.#plate().id, { ...state, position_x: Math.round(x), position_y: Math.round(y) });",
  ].join("\n"),
  [
    "        const visibleInset = 18;",
    "        const minimumCenter = data.width / 2 + data.brim + visibleInset;",
    "        const maximumX = Math.max(minimumCenter, this.#plate().width - data.width / 2 - data.brim - visibleInset);",
    "        const maximumY = Math.max(minimumCenter, this.#plate().depth - data.width / 2 - data.brim - visibleInset);",
    "        const x = Math.max(minimumCenter, Math.min(maximumX, purgeDrag.initialX + (event.clientX - purgeDrag.startX) * .28));",
    "        const y = Math.max(minimumCenter, Math.min(maximumY, purgeDrag.initialY - (event.clientY - purgeDrag.startY) * .28));",
    "        savePlatePurgeTower(this.#plate().id, { ...state, width_mm: data.width, brim_width_mm: data.brim, position_x: Math.round(x), position_y: Math.round(y) });",
  ].join("\n"),
  "Turm-Drag-Grenzen",
);

text = exact(
  text,
  "    this.#viewport?.setInstances(this.#displayInstances());\n    this.#refreshSelectionUi();",
  "    this.#viewport?.setInstances(this.#displayInstances());\n    this.#viewport?.resize();\n    this.#refreshSelectionUi();",
  "Farbwechsel-Viewport",
);
text = exact(
  text,
  "        this.#viewport?.setInstances(this.#displayInstances());\n        this.#renderSidebar();",
  "        this.#viewport?.setInstances(this.#displayInstances());\n        this.#viewport?.resize();\n        this.#renderSidebar();",
  "Moduswechsel-Viewport",
);
text = exact(
  text,
  "    this.#viewport.frameAll();\n    let down:",
  [
    "    this.#viewport.frameAll();",
    "    const mountedViewport = this.#viewport;",
    "    requestAnimationFrame(() => {",
    "      if (this.#viewport !== mountedViewport) return;",
    "      mountedViewport.resize();",
    "      mountedViewport.frameAll();",
    "      requestAnimationFrame(() => {",
    "        if (this.#viewport !== mountedViewport) return;",
    "        mountedViewport.resize();",
    "        mountedViewport.requestRender();",
    "      });",
    "    });",
    "    let down:",
  ].join("\n"),
  "Viewport-Nachlayout",
);

write(workspacePath, text);

const viewportPath = join(root, "frontend", "studio-mega-viewport.ts");
let viewport = read(viewportPath);
viewport = exact(
  viewport,
  "    this.#instances = instances;\n    for (const instance of instances) this.#ensureGpu(instance);\n    this.#rebuildOverlays();\n    this.requestRender();",
  "    this.#instances = instances;\n    for (const instance of instances) this.#ensureGpu(instance);\n    this.#rebuildOverlays();\n    this.resize();\n    this.requestRender();",
  "Viewport-Instanzen-Resize",
);
viewport = exact(
  viewport,
  "  frameAll(): void {\n    this.#target = [this.#plate.widthMm / 2, this.#plate.depthMm / 2, 0];",
  "  frameAll(): void {\n    this.resize();\n    this.#target = [this.#plate.widthMm / 2, this.#plate.depthMm / 2, 0];",
  "Viewport-Frame-Resize",
);
write(viewportPath, viewport);

console.log("Shift-Bereichsauswahl, Turmgrenzen und stabiler Viewport wurden übernommen.");
