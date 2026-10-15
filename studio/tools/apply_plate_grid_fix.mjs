import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const path = join(root, "frontend", "studio-mega-ui-v2.ts");
let text = readFileSync(path, "utf8").replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");

const oldGrid = ".app{display:grid;grid-template-rows:auto auto auto auto auto minmax(0,1fr);height:100%;min-height:720px}";
const newGrid = ".app{display:grid;grid-template-rows:auto auto auto auto auto auto minmax(0,1fr);height:100%;min-height:720px}.titlebar{grid-row:1}.toolstrip{grid-row:2}.modebar{grid-row:3}.profilebar{grid-row:4}.direct-print-top{grid-row:5;min-height:0}.plate-strip{grid-row:6;min-height:62px}.body{grid-row:7}";

if (!text.includes(newGrid)) {
  if (!text.includes(oldGrid)) throw new Error("Grid-Quellmarker wurde nicht gefunden.");
  text = text.replace(oldGrid, newGrid);
}

if (!text.includes(".plate-strip{grid-row:6;min-height:62px}")) {
  throw new Error("Plattenleisten-Fix ist unvollständig.");
}

writeFileSync(path, `\uFEFF${text}`, "utf8");
console.log("Persistente Plattenleisten-Gridzeilen wurden angewendet.");
