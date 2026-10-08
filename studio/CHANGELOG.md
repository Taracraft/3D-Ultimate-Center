# Changelog

## Post-release — 2026-10-07

### Version-neutral Studio namespace – private live completion

- Migrated Home Assistant, dashboard, browser/storage namespace and the native worker to version-neutral Studio identifiers while retaining release version **6.0.0**.
- Fresh authoritative gate passed: 456 frontend tests, 1,686 Python/worker tests and 15 subtests; source policy, production/HA-core builds and compileall are green.
- Neutral native worker is live: `dispatch-job.sh` `3fb2598742fd5896fa2b9f97e263e20542bd7cd41828c50ebb4ff3f814d6e9f3`; all 11 worker dependencies match the current SHA contract; API v2 and telemetry/capabilities report ready.
- Migrated the Tara-PC connector to `jarvis_studio_*`; the temporary compatibility bridge used only for the cached old client schema was removed immediately after the gate.
- Puppet visual verification confirms the unchanged layout: complete left Studio navigation, no redundant black HA tab bar, and clean control-center/cards/process-window rendering.
- Public GitHub path synchronization remains the last separately reviewed P1 closure item; no global or mechanical rename of `studio-v6/` is allowed.
- No printer command, real test slice, job release, upload, movement, heating, filament action or print start was performed.

## 6.0.0 — 2026-10-06

### Stable release

- Exited the beta series and set the authoritative frontend/package and Home Assistant integration version to **6.0.0**.
- Retained the closed native PROFILE_FILES contract for the curated A1/H2S package, fail-closed manifests, same-day backup/rollback and live SHA verification.
- Included the mobile navigation layout correction that keeps the horizontal tab strip as the single scroll owner and prevents active tabs from stretching vertically.
- Stable release is gated by the complete automated source policy, TypeScript, frontend logic, production build, Python/worker and Home Assistant compile checks. Final 6.0.0 gate evidence is recorded in the release evidence document.
- Interactive UI/iPhone acceptance and printer telemetry while the printer is powered off were explicitly removed from the 6.0.0 release gates by the project owner. This is a scope decision, not fabricated test evidence.
- MakerWorld live authentication/import remains a documented post-release follow-up. No printer command, real test slice, upload, movement, heating, filament action or print start is part of this release transition.


## Unreleased - 2026-09-30

### Paint tools and paint areas

- Paint areas in the object list are now selectable independently: click, Ctrl-click, Shift-click, Ctrl+A and Delete include the separated entries under "Malbereich".
- Brush and pen now stamp continuously along pointer movement and refine touched model surfaces to a 0.35 mm target edge before applying material paint. Circle, rectangle and text use the same exportable refined geometry.
- Rectangle/circle keep the smooth drag preview above the workspace; the print path remains material-bound and uses only loaded AMS filaments for painted multicolor regions.
- Frontend logic tests passed: 145/145. Production build passed; live on Home Assistant: JS SHA-256 2aa4b352fc6b9ef2a50bf03f6eec10b564bb98b461eaa27f8f6d4e4cf5039c91, CSS SHA-256 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c.
- Puppet port 5000 responds locally, but currently shows "Connection Failed" for the HA URL/access token. No valid visual Puppet acceptance in this step. No slice, upload or print start.


## Layer paths – end faces and lighting, 2026-09-12

- Open spatial extrusion chains now have end faces only at their outer endpoints; closed contours and straight internal joins receive no extra partition faces.
- Corrected side-triangle winding so lighting normals point outward.
- Direction reversals split chains; flat support view, filters, colors and the 25-field editor remain available.
- Three regression tests failed against the old geometry and passed after the fix. Full gate passed: 94 frontend tests and 361 Python tests.
- Frontend deployed with backup and independently verified SHA-256 hashes; no restart, slicing or print command. Visual browser acceptance remains open.
- Details: [Roadmap, section 24](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md).

## Activated – process editor and connected layer paths, 2026-09-12

- Activated the 25-field local process editor on HA with native mappings and extended artifact evidence.
- Performed exactly one authorized HA Core restart and verified HA/V6 profile API readiness. Recorded ongoing authorization for necessary HA Core restarts within the roadmap.
- Layer preview now joins turns and closing seams of continuous extrusion contours using bounded bevel faces.
- Travel, hidden segments, material/tool changes and feature boundaries remain separate. Existing colors, filters, layer controls and camera integration are retained.
- Passed 91 frontend tests, 361 Python tests and the complete quality gate; frontend deployed with backup and independently verified live SHA-256 hashes.
- Visual browser acceptance remains open. No real slicing, print command or worker/printer restart.
- [Complete progress and evidence, sections 22–23](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md).

## Process editor – 25 fields, 2026-09-12 (verified, activation pending)

- Added 16 validated local fields for line widths, print speeds, support clearances and interface layers, with matching native process mappings.
- Extended materialization feedback and individual artifact evidence to every requested editor field; missing and conflicting evidence remains explicit.
- Verified all additional keys in the actual Linux profile resources. Passed 88 frontend tests, 361 Python tests and the complete build/compile gate.
- Verified package staged on HA and previous files backed up. Activation is pending explicit authorization for one HA Core restart; no worker restart, slicing or print command occurred.
- Recorded the user's sequence: activate/verify this editor stage, then prioritize layering; investigate obstacles and maintain the complete documentation.
- Remaining scope and activation procedure: [Roadmap, sections 20–21](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md) and [Editor validation](docs/PROCESS_EDITOR_VALIDATION_2026-09-12.md).

## Unreleased — 2026-09-12

### Continuous layer preview

- Added a TypeScript geometry builder that retains every valid extrusion path accepted by the existing visibility rules, without stride sampling.
- Restored full layer height and estimated bead width without the previous percentage reduction; surface lighting keeps individual layers distinguishable.
- Geometry buffers use bounded pages; total memory still grows with visible path count.
- Preserved existing feature filters, material/feature colors, support view, layer controls and camera integration.
- Full gate passed with 87 frontend tests and 343 Python tests; frontend deployed with rollback backup and independently verified live SHA-256 hashes.
- Visual browser acceptance remains open because access was blocked. No real slicing, print command or service restart was performed.
- Preserved the pre-existing transfer-attempt and confirmation-dialog fixes. Further process-editor work follows layer acceptance; release remains 6.0.0-beta3.
- Full history and open release criteria: [Maintained roadmap](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md), sections 18–19.

## Unreleased — 2026-09-10

### 3D Ultimate Studio and profile truth

- Centralized the visible product name as **3D Ultimate Studio** and the slicer name as **3D Ultimate Slicer**.
- Preserved the internal V6 domain, API routes, custom-element names, entity IDs and storage keys unchanged for compatibility.
- Slicer jobs now distinguish **selected**, **applied in the slicer** and **confirmed in the artifact**.
- Artifact confirmation is derived exclusively from analysis of the generated G-code 3MF, including process settings, material channels, colors and filament types.
- Added secure linked-component production-3MF resolution, group-preserving plate placement and successful reference slices for 0.2 / 0.4 / 0.6 / 0.8 mm nozzles.
- Passed the complete V6 quality gate and controlled Home Assistant frontend deployment with SHA-256 and rollback backup.
- No print job was started and V5 remains untouched.

## 6.0.0-beta3 — 2026-07-12

### Official transition from alpha to beta

- Ultimate 3D Studio V6 has officially left the alpha phase.
- The current functional and physically verified baseline is released as **6.0.0-beta3**.
- First successful multicolor print prepared, sliced and started directly from Ultimate 3D Studio V6 on a Bambu Lab A1 with AMS Lite.

### Multicolor, AMS and direct printing

- Added authoritative object, extruder and AMS-slot mapping without silent fallback to the external spool.
- Physically verified multicolor slicing, purge tower, filament changes and direct printing.
- Added native Bambu build-plate selection with profile-dependent bed-temperature validation.
- Added final G-code validation for build-plate type, M140/M190, purge-tower placement and printable-area bounds.
- Preserved two-step direct-print authorization with SHA-256 verification and server-enforced AMS mapping.

### Studio and slicer

- Added persistent Studio workspaces with IndexedDB storage for models, plates, transforms, colors and AMS assignments.
- Removed the delayed destructive Studio refresh caused by asynchronous printer and profile initialization.
- Added bounded purge-tower placement from the active build plate and validation against the generated G-code.
- Added G-code analysis for material, time, layers, print features and filament changes.

### Printer status and profiles

- Added persistent printer dialogs and camera panels that are not destroyed by telemetry refreshes.
- Added monotonic A1 print-stage tracking with separate nozzle-cleaning phases before and after flow calibration.
- Improved support analysis for stacked, side-connected and cross-object supported geometry.
- Enabled local removal of printer, nozzle, filament, process and build-plate profiles.

### Verification

- Real multicolor output on Bambu Lab A1 with AMS Lite successfully confirmed.
- Frontend source-policy validation passed without violations.
- Frontend logic tests, strict TypeScript and production build passed.
- Python tests and Home Assistant compile validation passed.
- No MutationObserver, prototype, DOM-injection or runtime-layout patches.

## 6.0.0-beta2 — 2026-07-06

### Stable dashboard baseline

- Locked the current desktop and mobile dashboard layout as the beta-v2 visual baseline.
- Corrected the desktop Slicer width by separating the App Shell workspace host from the Slicer grid namespace.
- Preserved the responsive mobile layout and the existing Gallery, CAD Studio, profiles, jobs and system workspaces.
- Kept the source policy free of MutationObserver, prototype patching, DOM injection and runtime layout patches.

### Direct printing

- Kept the visible one-click direct-print workflow unchanged.
- Restored compatibility with the currently registered Home Assistant endpoints by executing `prepare` and immediately `start` from the same confirmed user action.
- Removed the frontend dependency on the unavailable `/print/execute` route that caused HTTP 404.
- Retained FTPS artifact validation, SHA-256 comparison, AMS mapping and print calibration options.

### Verification

- Frontend source-policy check passed without violations.
- Frontend logic tests, strict TypeScript build and production build passed.
- Python tests and Home Assistant compile validation passed.

## 6.0.0-beta1 — 2026-07-05

### Studio and slicing

- Added real multi-plate CAD workspace with selectable Bambu build-plate profiles, accurate dimensions, coordinate axes, grid and Studio-to-Slicer handoff.
- Added real Bambu Studio CLI slicing with original, cloud-synchronized and local user profiles.
- Added G-code 3MF artifact generation, validation, download and cancellation.
- Added complete editable printer, nozzle, filament, process and build-plate profiles, including structured values and custom G-code.

### Direct printing

- Added authenticated Bambu LAN direct printing for completed G-code 3MF jobs.
- Added bounded archive validation, SHA-256 verification and implicit FTPS upload to the selected printer.
- Added a two-step safety workflow: upload preparation first, then an explicit final `DRUCKEN` confirmation before the MQTT `project_file` command is sent.
- Added printer readiness checks, AMS availability and occupied-slot validation, bed leveling, flow calibration, vibration calibration and timelapse options.
- Added discard support for prepared uploads and short-lived single-use print authorizations.

### MakerWorld and profiles

- Added MakerWorld model details, signed 3MF download, STL conversion and multi-term intersection filters.
- Added Bambu Cloud profile synchronization with persistent offline availability.
- Added local editable derivatives of cloud and built-in profiles without modifying the originals.

### Interface and stability

- Added native progress bars to the control center, system telemetry and slicer components.
- Removed the global progress-enhancer and periodic DOM-scanning architecture that could duplicate workspace layers after reload.
- Strengthened the frontend source policy against MutationObserver, prototype modification and runtime enhancer patterns.
- Preserved the existing Gallery and the stable V5 beta38 codebase unchanged.

### Verification

- 10 DOM-free frontend logic tests passed.
- Strict TypeScript and production builds passed.
- 119 Python tests passed, including direct-print artifact and AMS payload tests.
- Home Assistant compile validation passed.

## 2026-09-13 - Layering: native variable layer-height handoff

- Added validated `layer_height_ranges` handoff from Studio upload through HA API into Bambu Studio `assembled_params.height_ranges`.
- Enforced A1/nozzle-specific limits in both HA validation and the worker materializer.
- Activated live after the full V6 gate and verified the real worker path with a materializer-only probe; no print job was started.

## 2026-09-13 - Layering: variable layer-height UI

- Added a visible range-list UI for variable layer heights in the slicer options panel.
- Add/edit/remove actions persist `layer_height_ranges` and use the native manifest handoff activated earlier.
- Full V6 gate passed and the frontend was deployed live.

## 2026-09-13 - Layering: preview range markers and native Bambu acceptance

- Added layer-view sidebar markers for active variable layer-height ranges; the current preview Z highlights the matching range while preserving the existing preview, filters, colors and camera path.
- Fixed Bambu Studio CLI compatibility for assembled_params.height_ranges: min_z and max_z are emitted as JSON numbers, while range_params.layer_height remains a string as required by Bambu's process schema.
- Ran a synthetic native Slicing Server acceptance job without any printer command. Bambu Studio completed, produced G-code and G-code 3MF, accepted the height ranges and no longer logged the previous invalid json type for layer_height error.
- Targeted G-code analysis of job v6-vlh-accept-20260913T071923Z found 116 layer markers with 0.12 mm steps in the lower range and 0.20 mm steps after the transition around 5 mm.
- Version remains 6.0.0-beta3; full browser visual acceptance, graphical height-curve editing, broader process editor work, paint tools and release criteria remain open.

## 2026-09-13 - Layering: variable layer-height curve preview

- Added a compact source-owned curve preview above the variable layer-height range list in the process options panel.
- The curve scales Z range width and layer-height bar height from the active layer_height_ranges while preserving the native range handoff.
- Added a frontend source regression test so the curve UI markers remain covered by the V6 gate.
- Full V6 gate passed and the frontend was deployed live with rollback backup. JavaScript SHA-256 a9754054ff6dbd0c67cd36ee1a0684a267fa3b1edfeca996435b898dc67e08b9; build manifest 013f5580619eb4e8cd09f0ba7c1b08aa2c2a0a4e540b647cb930e8b994906915.
- No HA Core restart, worker restart, printer command or print start.

## 2026-09-13 - Layering: pointer editing for variable layer-height curve

- Made the variable layer-height curve directly editable in the process options panel: X selects an existing Z range and Y sets its layer_height_mm.
- The editor writes back into the existing layer_height_ranges storage and native Bambu handoff path; no second data model or printer command was added.
- Added a frontend source regression test for the pointer-editing contract.
- Full V6 gate passed and the frontend was deployed live. JavaScript SHA-256 4f677c0e13dc3d1c995fb0274d3a307e0f6c5195bb37680339b75ef116dd63b4; build manifest 90dfeb9dbdfa986dde0aaf8492f400db49022252bac67b3c09e8d165e31e83ba.
- No HA Core restart, worker restart, printer command or print start.

## 2026-09-13 - Layering: drag editing for variable layer-height curve

- Extended the variable layer-height curve from click editing to pointer drag editing.
- Pointer capture, pointermove and pointerup/cancel cleanup keep the edit path contained in the source-owned process options panel.
- The editor still writes only layer_height_ranges and keeps the native Bambu handoff unchanged.
- Full V6 gate passed and the frontend was deployed live. JavaScript SHA-256 6c916f93ecfeea0bb7b57541d2bde78c3d33e2642d8d2cdd7b4be4a52a5acf4d; build manifest 93c3fa1ae38a2b54beff4c9ed64b11ae86841dc107efe1c9c09e6e7035337152.
- No HA Core restart, worker restart, printer command or print start.

## 2026-09-13 - Layering: nozzle presets and curve snapping

- Passed the active nozzle diameter from the Studio workspace into the process options panel.
- Added nozzle-contract layer-height presets for variable layer-height ranges and snapped pointer/drag curve edits to those presets.
- Preset buttons update the active range only and keep the existing layer_height_ranges persistence and native Bambu handoff.
- Reconstructed a truncated workspace source from the last full backup during implementation and revalidated it with the complete V6 gate.
- Full V6 gate passed and the frontend was deployed live. JavaScript SHA-256 e5aac4dcad1bb02557754379702cadf175f4a2aa62ac59a41bbb56ebd3d6b9cb; build manifest 6f19c4d605e5b16da727fd09b182c589b6f99fd4df1736e83f55f87938394b1f.
- No HA Core restart, worker restart, printer command or print start.

## 2026-09-13 - Layering: preview Z coupling for the height curve

- Passed the currently visible preview Z from the layer view into the process options panel.
- The variable layer-height curve now highlights the range that contains the currently visible preview height.
- This is a visual coupling only; layer_height_ranges persistence, nozzle presets, pointer/drag editing and native Bambu handoff are unchanged.
- Full V6 gate passed and the frontend was deployed live. JavaScript SHA-256 049f6bab056fdd30392f71e911d9ee6b7583e4e4c26a465a3983679afa6a0bba; build manifest 194b2e70dfa26307db0bfa58fe2e37e8a125fe2281daf12919ba408399ea0bfc.
- No HA Core restart, worker restart, printer command or print start.

## 2026-09-13 - Layering: inline nozzle validation for variable layer ranges

- Added inline min/max validation for variable layer-height range inputs using the active nozzle process contract.
- Manual range layer-height values outside the active nozzle limits now fail directly in the process options panel.
- Presets, curve snapping, preview-Z highlighting and native Bambu handoff continue to use the same layer_height_ranges path.
- Full V6 gate passed and the frontend was deployed live. JavaScript SHA-256 d594c76e0b5f935f20f1c7e9e60d9e85d1b5dcd1686491388b9b3ccded2c356e; build manifest 2052c33c11647b44979ee96e499a5a71633ab54f7bbaabd398bc336d0c5b17fb.
- No HA Core restart, worker restart, printer command or print start.

## 2026-09-13 - Process editor 31 fields

- Extended the V6 process settings editor from 25 to 31 materialized numeric fields.
- Added gap infill, solid infill, ironing, support and support-interface speeds plus bridge flow ratio.
- Aligned frontend field model, Home Assistant process-profile contract and Python tests.
- Activated backend contract live with backup and HA Core restart; no printer command or print start.

## 2026-09-13 - Layer preview touch stepper

- Restored variable layer-height range rendering in the active G-code preview sidebar.
- Added first/previous/next/last layer controls next to the layer slider for touch and fine inspection.
- Kept slider and step controls on the stable preview refresh path; full V6 gate and deploy gate passed.
- No backend change, no HA Core restart, no worker restart and no printer command.

## 2026-09-13 - Layer preview fast jumps

- Added -10/+10 layer jumps and a direct layer-number input to the G-code preview sidebar.
- Kept slider, step buttons and direct entry synchronized with track count, extrusion, Z height and active variable layer range.
- Full V6 gate and deploy gate passed; no backend change and no printer command.

## 2026-09-13 - Current layer focus highlight

- Focused toolpath highlights on the selected/current layer while keeping previous layers dimmed as context.
- Preserved real G-code toolpaths, material colors and feature colors; no sampling, fabricated geometry or runtime patch.
- Browser screenshot of the live HA tab confirmed the page was open and the right popup stack did not overlap the visible content, but the interactive 3D layer view was not visible in that screenshot.
- Full V6 gate and deploy gate passed; no backend change and no printer command.

## 2026-09-13 - Layeransicht: Stage-Badge und Opera-Sichttest

- Added a visible preview-stage badge for the active G-code layer view with layer index, layer count and Z height.
- Added a frontend source test for the preview-stage badge.
- Full V6 gate and deploy gate passed; live JS `e8d36e267b294edd44afade152be941d87c6aaed6327e991d2d04eff166d37f2`.
- Opera MCP visual check confirmed the real project layer preview with 399 layers and 2,176,118 toolpath segments. Badge browser visibility still needs a fresh-cache visual confirmation.


## 2026-09-14 - Slicing popup scroll, Bambu support styles and time consistency

- Preserved the global Vorgänge/Slicing popup scroll positions across telemetry rerenders so scrolling the queue no longer jumps back to the top.
- Extended the process editor support controls with Bambu-like support style choices: Standard, tree slim, tree strong, tree hybrid and tree organic.
- Added the model-contact support path: when "Nur vom Druckbett" is disabled, the request carries support_build_plate_only=false through the frontend, plate-slice route, backend validation and native materialization.
- Native process materialization now records support_mode, support_style, support_on_build_plate_only and support_threshold_angle in the generated process settings evidence.
- G-code analysis now flags missing or contradictory time fields and warns in the analysis panel instead of presenting implausible duration values as silently authoritative.
- Full V6 gate passed twice; backend files deployed with backup /homeassistant/pcc-backups/v6-backend/20260914-070545 and frontend deployed with backup /homeassistant/pcc-backups/v6-frontend/20260914-070608.
- No HA Core restart, no worker restart, no slicing job, no printer command and no material write were triggered.
- Next priority: make the layer preview match the Bambu Studio sliced view much more closely, including dense/solid layer rendering and overhang/support visibility.

## 2026-09-30 Supportwarnung Filamentprofile Puppet

- Fixed V6 Studio filament profile selection: one unified "Filamentprofile" picker while keeping AMS/external spool as explicit material source.
- Fixed support-warning lifecycle by moving it to a native modal dialog and preventing duplicate slice/upload flow before user decision.
- Fixed floating-support analysis for normalized downward normals and mirrored geometry.
- Verified frontend/TypeScript/build gate, 145 frontend logic tests, and Python gate with 519 tests plus 3 subtests.
- Deployed and verified live HA assets: JS cfb87956f95d4384752ad201bc05015bd462e93005a2b7018fd6de8efd973677, CSS 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c, build JSON 99dbdb2cef3721b20599cfd7cde0a34132d4d3465bd99fe350c6b3c27e5f1f20.
- Restored local Puppet screenshot verification on HA port 5000; documented required split-DNS route.

## 2026-09-30 Roh-STL-Bambu-Slicing-Fix

- Fixed native Bambu Studio raw-file slicing: non-multimaterial jobs now pass the uploaded input file as a positional Bambu Studio argument.
- Verified raw STL slicing with `codex-v6-raw-stl-positional-20260930`: completed, Bambu Studio return_code 0, output artifact produced.
- Confirmed printer stayed IDLE and no print job was started.
