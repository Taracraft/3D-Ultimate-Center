import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";

const root = path.dirname(fileURLToPath(import.meta.url));
const entry = path.join(root, "frontend", "studio-entry.ts");
const baseCssPath = path.join(root, "frontend", "layers.css");
const out = path.join(root, "deploy", "homeassistant", "www", "3d-studio");
const jsPath = path.join(out, "ultimate-3d-studio.js");
const cssPath = path.join(out, "ultimate-3d-studio.css");
const manifestPath = path.join(out, "ultimate-3d-studio-build.json");
const version = JSON.parse(await readFile(path.join(root, "package.json"), "utf8")).version;
const hash = (data) => createHash("sha256").update(data).digest("hex");
const relative = (file) => path.relative(root, file).replaceAll("\\", "/");

await mkdir(out, { recursive: true });
await rm(jsPath, { force: true });
await rm(cssPath, { force: true });
await rm(manifestPath, { force: true });

const result = await esbuild.build({
  entryPoints: [entry],
  outfile: jsPath,
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2022"],
  charset: "utf8",
  legalComments: "none",
  minify: true,
  sourcemap: false,
  metafile: true,
  logLevel: "info",
  tsconfig: path.join(root, "tsconfig.json"),
});

const componentCss = await readFile(cssPath).catch(() => Buffer.alloc(0));
const baseCss = await readFile(baseCssPath);
const css = Buffer.from(`${baseCss.toString("utf8").trim()}\n${componentCss.toString("utf8").trim()}\n`);
await writeFile(cssPath, css);

const bundle = await readFile(jsPath);
const text = bundle.toString("utf8");
const forbidden = [
  "prototype.connectedCallback =",
  "prototype.disconnectedCallback =",
  "prototype._render =",
  "new MutationObserver",
  "__transformToolsPatched",
  "__transformMountPatched",
];
const violations = forbidden.filter((pattern) => text.includes(pattern));
if (violations.length) throw new Error(`Forbidden runtime patch pattern:\n${violations.join("\n")}`);

for (const marker of [
  "ultimate-3d-studio-card",
  "ultimate-3d-studio",
  "ultimate-3d-unified-studio",
]) {
  if (!text.includes(marker)) throw new Error(`Required bundle marker missing: ${marker}`);
}
const registrations = text.match(/customElements\.define\(["']ultimate-3d-studio-card["']/g) ?? [];
if (registrations.length !== 1) throw new Error(`Expected one Studio card registration, found ${registrations.length}`);

for (const item of await readdir(out, { withFileTypes: true })) {
  if (item.isFile() && /^ultimate-3d-studio\.[0-9a-f]+\.js$/i.test(item.name)) {
    await rm(path.join(out, item.name), { force: true });
  }
}

const modules = Object.keys(result.metafile?.inputs || {}).sort();
const manifest = {
  schema_version: 3,
  product: "Ultimate 3D Printing Studio",
  version,
  entry: relative(entry),
  output: relative(jsPath),
  size_bytes: bundle.length,
  sha256: hash(bundle),
  css: {
    output: relative(cssPath),
    size_bytes: css.length,
    sha256: hash(css),
    sources: [relative(baseCssPath), "component CSS"],
  },
  architecture: {
    workspace: "ultimate-3d-unified-studio",
    workspace_shell_count: 1,
    webgl_canvas_authorities: 1,
    runtime_patching: false,
    build_patch_imports: false,
  },
  bundle: {
    format: "esm",
    platform: "browser",
    target: "es2022",
    minified: true,
    sourcemap: false,
    bundled_input_count: modules.length,
    inputs: modules,
  },
  policy: {
    runtime_monkey_patches_allowed: false,
    card_registration_count: registrations.length,
    forbidden_patterns_checked: forbidden,
  },
  built_at: new Date().toISOString(),
};

await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log(`Version: ${version}`);
console.log(`JS: ${bundle.length} Bytes, SHA256 ${manifest.sha256}`);
console.log(`CSS: ${css.length} Bytes, SHA256 ${manifest.css.sha256}`);
console.log(`Module: ${modules.length}`);
console.log("Core-Build: OK");
console.log("Terminal bleibt offen.");
