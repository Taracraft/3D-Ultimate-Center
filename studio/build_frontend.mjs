import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { build, version as esbuildVersion } from "esbuild";


const root = dirname(fileURLToPath(import.meta.url));
const packageFile = join(root, "package.json");
const sourceDirectory = join(root, "frontend");
const outputDirectory = join(root, "dist", "frontend");
const entryFile = join(sourceDirectory, "studio-entry.ts");
const sourceCssFile = join(sourceDirectory, "layers.css");
const outputJavaScriptFile = join(outputDirectory, "ultimate-3d-studio.js");
const outputCssFile = join(outputDirectory, "ultimate-3d-studio.css");
const manifestFile = join(outputDirectory, "frontend-build-manifest.json");

const forbiddenPatterns = [
  "prototype.connectedCallback =",
  "prototype.disconnectedCallback =",
  "prototype._render =",
  "__transformToolsPatched",
  "__transformMountPatched",
  "new MutationObserver",
  "ultimate-3d-studio-status-patch",
  "ultimate-3d-controls-confirmation-patch",
];
function sha256(path) { return createHash("sha256").update(readFileSync(path)).digest("hex"); }
function artifact(path) { const stats = statSync(path); return { path: relative(root, path).replaceAll("\\", "/"), size_bytes: stats.size, sha256: sha256(path) }; }
function assertRequiredFile(path, label) { if (!existsSync(path)) throw new Error(`${label} was not found: ${path}`); }
function assertBundlePolicy(source) {
  const violations = forbiddenPatterns.filter((pattern) => source.includes(pattern));
  if (violations.length > 0) throw new Error(`Generated frontend bundle contains forbidden runtime patch patterns:\n${violations.join("\n")}`);
  const requiredMarkers = ["ultimate-3d-studio-card","ultimate-3d-studio","ultimate-3d-unified-studio","ultimate-3d-steuerung-workspace","ultimate-3d-system-workspace","ultimate-3d-studio:gallery-library-cache-v1","openGalleryProject","gallery_asset_id"];
  const missing = requiredMarkers.filter((marker) => !source.includes(marker));
  if (missing.length > 0) throw new Error(`Generated frontend bundle is incomplete:\n${missing.join("\n")}`);
  const registrations = source.match(/customElements\.define\(["']ultimate-3d-studio-card["']/g) ?? [];
  if (registrations.length !== 1) throw new Error(`Expected one ultimate-3d-studio-card registration, found ${registrations.length}`);
  return { card_registration_count: registrations.length, required_markers: requiredMarkers, forbidden_patterns_checked: forbiddenPatterns };
}
console.log("");
console.log("========================================================================");
console.log("Ultimate 3D Printing Studio - Frontend Production Build");
console.log("========================================================================");
console.log("");
assertRequiredFile(packageFile, "package.json");
assertRequiredFile(entryFile, "Frontend entry point");
assertRequiredFile(sourceCssFile, "Frontend layer stylesheet");
const packageMetadata = JSON.parse(readFileSync(packageFile, "utf8"));
rmSync(outputDirectory, { recursive: true, force: true });
mkdirSync(outputDirectory, { recursive: true });
console.log(`Entry point: ${entryFile}`);
console.log(`Output:      ${outputDirectory}`);
console.log(`esbuild:     ${esbuildVersion}`);
console.log("");
const buildResult = await build({ absWorkingDir: root, entryPoints: [entryFile], outfile: outputJavaScriptFile, bundle: true, format: "esm", platform: "browser", target: ["es2022"], charset: "utf8", treeShaking: true, legalComments: "none", minify: false, sourcemap: false, metafile: true, logLevel: "info", tsconfig: join(root, "tsconfig.json") });
copyFileSync(sourceCssFile, outputCssFile);
assertRequiredFile(outputJavaScriptFile, "JavaScript bundle");
assertRequiredFile(outputCssFile, "CSS artifact");
const javaScriptSource = readFileSync(outputJavaScriptFile, "utf8");
const policy = assertBundlePolicy(javaScriptSource);
const inputCount = Object.keys(buildResult.metafile.inputs).length;
const manifest = { schema_version: 1, product: "Ultimate 3D Printing Studio", version: String(packageMetadata.version ?? "unknown"), build: { bundler: "esbuild", bundler_version: esbuildVersion, format: "esm", platform: "browser", target: "es2022", minified: false, sourcemap: false, entry_point: relative(root, entryFile).replaceAll("\\", "/"), bundled_input_count: inputCount }, architecture: { active_workspace: "ultimate-3d-unified-studio", runtime_monkey_patches_allowed: false, nested_workspace_shells_allowed: false, webgl_canvas_authorities: 1 }, policy: { runtime_monkey_patches_allowed: false, navigation_authorities: 1, ...policy }, artifacts: [artifact(outputJavaScriptFile), artifact(outputCssFile)], manifest_path: relative(root, manifestFile).replaceAll("\\", "/") };
writeFileSync(manifestFile, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
console.log("");
console.log("Build artifacts:");
for (const builtArtifact of manifest.artifacts) console.log(`  ${builtArtifact.path} (${builtArtifact.size_bytes} bytes, sha256 ${builtArtifact.sha256})`);
console.log(`  ${manifest.manifest_path} (${statSync(manifestFile).size} bytes)`);
console.log("");
console.log(`Bundled TypeScript modules: ${inputCount}`);
console.log(`Policy patterns checked: ${forbiddenPatterns.length}`);
console.log("Frontend production build: OK");
console.log("Terminal bleibt offen.");
