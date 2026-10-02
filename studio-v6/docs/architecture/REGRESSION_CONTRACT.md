# V6 Regression Contract

V6 may not replace the production Beta38 build until every item below passes.

## Control Center

- Printer discovery and connection remain stable.
- Current status, temperatures, progress, layers and remaining time update live.
- Camera stream and snapshot fallback remain available.
- AMS type, slots, materials and active slot remain correct.
- Pause, resume, stop and safe printer controls retain confirmation behavior.
- Upload is available directly in Control Center.
- Gallery assets and queue entries can be opened from Control Center.

## Gallery

- Existing archive files remain visible and downloadable.
- Folder structures and existing paths migrate without loss.
- Upload supports STL, 3MF, OBJ and future configured formats.
- Upload progress, validation, duplicate detection and previews work.
- A model can open in Studio, enter Queue or start slicing.
- ZIP export of the complete gallery remains available.

## CAD Studio

- Imported models render at the correct scale and plate position.
- No object appears at an unrelated top-left origin.
- Selection is stable across rerenders.
- Left drag, right drag, orbit, pan and zoom are mutually exclusive.
- Transform controls update one canonical scene state.
- Color changes update the selected object and survive autosave.
- Import menus never remain as phantom overlays.
- No blank page occurs after import, navigation or view switching.
- Multiple objects and plates remain independent.
- Undo and redo restore deterministic scene states.
- Gallery and Queue imports use stable asset IDs.

## Slicing

- Slice jobs are persistent and survive HA reloads.
- Progress, logs, cancellation and retry are observable.
- Provider failures do not corrupt projects or assets.
- Output artifacts include normalized metadata.
- Local and external providers satisfy the same contract.

## Profiles

- Manual profile upload works.
- Bambu and Orca profile formats are normalized.
- Filament and process profiles remain editable locally.
- Cloud import never becomes a runtime dependency for local profiles.
- Every queued or sliced job stores a profile snapshot.

## Queue

- Existing Beta38 queue entries migrate without loss.
- Queue items can reference assets, projects or slice artifacts.
- Reordering, quantities and scheduling remain stable.
- Queue items can reopen in Studio and be resliced.
- Print execution records status and errors without losing the source job.

## Compatibility

- Existing HA entities remain available during migration.
- Existing services and WebSocket commands remain available through adapters.
- Existing HTTP routes remain valid until a deprecation release.
- Existing signed download links continue to work during their validity period.
- The production Beta38 dashboard remains usable until the final cutover.
