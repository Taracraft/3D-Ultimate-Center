# V6 Frontend Build Contract

## Canonical build root

The canonical frontend toolchain is executed from the V6 root directory:

```text
v6/
```

The root `package.json`, `tsconfig.json`, `run_frontend_tests.mjs` and
`build_frontend.mjs` define the supported build path. The files under
`frontend/` are source files, not an independently deployed application.

## Browser entry point

The production entry point is:

```text
frontend/app-shell.ts
```

It registers the `ultimate-3d-studio` custom element and imports the Gallery,
Studio and Slicer workspace implementations.

## Production artifacts

A successful build creates:

```text
dist/frontend/ultimate-3d-studio.js
dist/frontend/ultimate-3d-studio.css
dist/frontend/frontend-build-manifest.json
```

The JavaScript artifact is one bundled ES module for browser execution with an
ES2022 target. The stylesheet remains a separate artifact so the future Home
Assistant adapter can register or inject it explicitly without coupling style
loading to the domain modules.

The manifest records:

- product and V6 version
- bundler and bundler version
- browser platform and ES module format
- ES2022 target
- canonical entry point
- bundled input count
- artifact sizes
- SHA-256 digests

Generated files under `dist/` are local build output and are intentionally not
tracked in Git.

## Gate order

The frontend runner performs the following steps in this order:

1. Install locked Node dependencies.
2. Run the strict TypeScript check with no emit.
3. Run the production bundle build.
4. Validate the build manifest and generated artifacts.
5. Write `.test-results/frontend-test-status.json`.

A successful TypeScript check without a successful bundle and manifest is not a
passing frontend gate.

## Commands

Full frontend gate:

```powershell
.\run_frontend_tests.ps1
```

Combined Python, HTTP and frontend build gate:

```powershell
.\run_api_runtime_gate.ps1
```

Direct Node build after dependencies are installed:

```powershell
& "C:\Program Files\nodejs\node.exe" .\build_frontend.mjs
```

## Deployment boundary

The build does not deploy files to Home Assistant, does not modify storage
views and does not alter the productive V5 beta38 integration. The later Home
Assistant adapter consumes validated V6 build artifacts as a separate layer.
