# Ultimate 3D Printing Studio V6 - System Architecture

## Application shell

V6 uses one unified Home Assistant dashboard shell with internal routes:

- `/control`
- `/gallery`
- `/studio/:project_id?`
- `/slicer/:job_id?`
- `/profiles`
- `/queue`
- `/history`
- `/system`

The shell mounts once. Switching workspaces does not recreate the complete application or discard active state.

## Core domains

- Asset Core: uploads, validation, SHA-256 deduplication, previews and immutable source files.
- Gallery Core: folders, tags, favorites, search, versions and model handoff.
- Project Core: projects, plates, scene objects, transformations, revisions and autosave.
- Slicing Core: provider capabilities, persistent jobs, progress, logs and artifacts.
- Profile Core: printer, nozzle, filament, process and build-plate profiles.
- Queue Core: ordering, quantity, scheduling, profile snapshots and execution state.
- Printer Core: Bambu LAN connection, telemetry, camera, AMS, transfer and print commands.

## API

All new HTTP routes are versioned below:

```text
/api/printer_control_center/v1
```

Primary resources:

```text
/assets
/gallery
/projects
/slicing
/profiles
/queue
/printers
/providers
/system
```

Legacy V5 routes remain active through compatibility adapters until regression tests prove functional equivalence.

## Frontend state rules

- One canonical state store per domain.
- Rendering is derived from state and never mutates domain state.
- Scene graph, selection, viewport, camera and overlays have separate authorities.
- Pointer handlers dispatch commands; they do not directly rewrite scene DOM.
- Global `window` application state is forbidden.
- Whole-card `innerHTML` replacement after initial mount is forbidden.
- Event listeners are registered once and removed during unmount.

## Layer contract

```text
0   workspace background
10  build plate and model rendering
20  selection outline
30  transform gizmos and measurements
40  contextual overlays
50  fixed toolbars
60  inspectors and drawers
70  menus and popovers
80  modal backdrop
90  modal dialogs
100 notifications and command palette
```

Arbitrary z-index values are forbidden. Every component may create only documented stacking contexts.

## Persistent runtime paths

```text
/srv/3D-Studio
/mnt/homeassist-data/3D-Studio
```

The application path `/srv/3D-Studio` points to persistent storage under `/mnt/homeassist-data/3D-Studio`. `/dev` is not used for persistent application data.

## Slicing execution

Production slicing uses exactly one fixed execution path:

- the native Linux slicing server at `127.0.0.1:8099` on the HA Linux host;
- authenticated Home Assistant routes proxy jobs and verified artifacts;
- no selectable local-computer, remote-computer or external HTTP slicer exists;
- Bambu LAN printer transfer remains a separate print path after slicing succeeds.

Changing the slicing host requires a reviewed source and deployment change. It is not a runtime provider setting.
