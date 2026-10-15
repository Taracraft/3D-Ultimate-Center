import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const path = join(root, "frontend", "studio-mega-workspace-v2.ts");
let text = readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
const oldValue = [
  "      width_mm: towerData.width || tower.width_mm,",
  "      brim_width_mm: towerData.brim || tower.brim_width_mm,",
  "      position_x: towerData.x || tower.position_x,",
  "      position_y: towerData.y || tower.position_y,",
].join("\n");
const newValue = [
  "      width_mm: towerData.width || Number(tower.width_mm ?? 35),",
  "      brim_width_mm: towerData.brim || Number(tower.brim_width_mm ?? 3),",
  "      position_x: towerData.x || Number(tower.position_x ?? plate.width - 40),",
  "      position_y: towerData.y || Number(tower.position_y ?? plate.depth - 40),",
].join("\n");
if (!text.includes(newValue)) {
  if (!text.includes(oldValue)) throw new Error("Turm-Typmarker fehlt");
  text = text.replace(oldValue, newValue);
  writeFileSync(path, `\uFEFF${text}`, "utf8");
}
console.log("Optionale Turmwerte sind auf garantierte Zahlen normalisiert.");
