import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";


const root = dirname(fileURLToPath(import.meta.url));
const resultDirectory = join(root, ".test-results");
const resultFile = join(resultDirectory, "frontend-test-status.json");
const nodeExecutable = process.execPath;
const npmCli = join(dirname(nodeExecutable), "node_modules", "npm", "bin", "npm-cli.js");
const typescriptCli = join(root, "node_modules", "typescript", "bin", "tsc");
const logicTestScript = join(root, "run_frontend_logic_tests.mjs");
const buildScript = join(root, "build_frontend.mjs");
const buildManifest = join(root, "dist", "frontend", "frontend-build-manifest.json");
const packageFile = join(root, "package.json");
function run(script, args) {
  const result = spawnSync(nodeExecutable, [script, ...args], { cwd: root, encoding: "utf8", shell: false, env: { ...process.env, PATH: [dirname(nodeExecutable), process.env.PATH ?? ""].join(";") } });
  const stdout = result.stdout || ""; const stderr = result.stderr || "";
  if (stdout) process.stdout.write(stdout); if (stderr) process.stderr.write(stderr);
  return { code: typeof result.status === "number" ? result.status : 1, stdout, stderr, error: result.error instanceof Error ? `${result.error.name}: ${result.error.message}` : "" };
}
function version() { try { return JSON.parse(readFileSync(packageFile, "utf8")).version || null; } catch { return null; } }
function validateManifest() {
  if (!existsSync(buildManifest)) return { valid: false, error: "Build manifest missing", manifest: null };
  try {
    const manifest = JSON.parse(readFileSync(buildManifest, "utf8"));
    const artifacts = Array.isArray(manifest.artifacts) ? manifest.artifacts : [];
    const valid = manifest.schema_version === 1 && manifest.version === version() && manifest.build?.format === "esm" && manifest.build?.platform === "browser" && manifest.build?.target === "es2022" && artifacts.length === 2 && artifacts.every((item) => item.path && existsSync(join(root, item.path)));
    return { valid, error: valid ? "" : "Build manifest validation failed", manifest };
  } catch (error) { return { valid: false, error: error instanceof Error ? error.message : String(error), manifest: null }; }
}
console.log("Ultimate 3D Printing Studio V6 - Frontend Test and Build Runner");
const install = run(npmCli, ["install", "--no-audit", "--no-fund"]);
const typescript = install.code === 0 ? run(typescriptCli, ["--project", join(root, "tsconfig.json"), "--noEmit", "--pretty", "false"]) : { code: -1, stdout: "", stderr: "", error: "Skipped" };
const logic = typescript.code === 0 ? run(logicTestScript, []) : { code: -1, stdout: "", stderr: "", error: "Skipped" };
const build = logic.code === 0 ? run(buildScript, []) : { code: -1, stdout: "", stderr: "", error: "Skipped" };
const manifest = build.code === 0 ? validateManifest() : { valid: false, error: "Build was not executed successfully", manifest: null };
const success = install.code === 0 && typescript.code === 0 && logic.code === 0 && build.code === 0 && manifest.valid;
mkdirSync(resultDirectory, { recursive: true });
writeFileSync(resultFile, `${JSON.stringify({ success, expected_version: version(), node_version: process.version, node_executable: nodeExecutable, npm_cli: npmCli, typescript_cli: typescriptCli, logic_test_script: logicTestScript, build_script: buildScript, build_manifest: buildManifest, install_code: install.code, install_error: install.error, install_stdout: install.stdout, install_stderr: install.stderr, typescript_code: typescript.code, typescript_error: typescript.error, typescript_stdout: typescript.stdout, typescript_stderr: typescript.stderr, logic_test_code: logic.code, logic_test_error: logic.error, logic_test_stdout: logic.stdout, logic_test_stderr: logic.stderr, build_code: build.code, build_error: build.error, build_stdout: build.stdout, build_stderr: build.stderr, manifest_valid: manifest.valid, manifest_error: manifest.error, manifest: manifest.manifest, synthetic_dom_used: false, project_root: root }, null, 2)}\n`, "utf8");
console.log(`Result: ${success ? "OK" : "FAILED"}`);
console.log("Terminal bleibt offen.");
process.exitCode = success ? 0 : 1;
