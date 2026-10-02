# Changelog

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