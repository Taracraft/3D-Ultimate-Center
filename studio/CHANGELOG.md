# Historical changes

This summary covers the historical baseline through 7 October 2026. It is not acceptance evidence for the current delivery candidate. Current Linux, TLS, installation, upgrade, restore, fresh HACS and release checks require their own evidence.

## Studio and profiles
- Multiple build plates, persistent workspaces, transformations, material assignments and editable printer, nozzle, filament and process profiles.
- Separate reporting of selected settings, slicer-applied settings and artifact-confirmed settings.
- Explicit AMS and external-spool selection, artifact validation and two-step print authorization.

## Layers and process settings
- Continuous extrusion-path geometry, joined contours, end faces, lighting and layer focus.
- Variable layer-height ranges with nozzle limits, presets, curve editing and preview synchronization.
- Layer navigation, direct layer jumps, support styles and warnings for inconsistent time estimates.

## Painting and interface
- Independent paint-area selection and continuous brush/pen strokes.
- Circle, rectangle and text tools using exportable refined geometry.
- Persistent camera and progress dialogs, stable scrolling and mobile navigation.
- MakerWorld model details and profile workflows.

## Historical versions
The baseline records beta milestones during July 2026 and version 6.0.0 on 6 October 2026. Those historical labels do not grant current deployment permission or replace current test and license review. Private operational paths, local access diagnostics and standing restart permissions are deliberately excluded from this summary.

## 7 October 2026
- Migrated the active Studio integration, frontend and worker identifiers to a version-neutral namespace while retaining the release version in central metadata.
- Historical deployment and visual checks do not prove acceptance of the current source candidate.

## 18 October 2026 - 6.0.5 / Slicer 0.1.0-alpha10
- The catalog serializer now emits the required Linux system field and omits an unset archive_path instead of serializing null. Internal delivery receipts retain their existing format.
- Regression coverage verifies catalog validation and the separate receipt contract. Integration, frontend and Slicer source metadata use consistent new versions without moving existing tags.
- This is a source correction. The existing private runtime archive retains its own identity and historical metadata. A complete public Docker runtime download and the outstanding Expat decision are not supplied by this source release.
