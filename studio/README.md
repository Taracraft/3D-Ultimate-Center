# Ultimate 3D Printing Studio

## Current release

**6.0.0 · 6 October 2026**

Ultimate 3D Studio is released as **6.0.0 stable**. The stable baseline incorporates the reviewed native worker/package contract, Home Assistant integration, profile and artifact validation, the current frontend, rollback-protected deployment paths and the complete automated quality gate.

Interactive UI/iPhone acceptance and live printer telemetry with the printer powered off were explicitly removed from the 6.0.0 release gates by the project owner on 6 October 2026. They are therefore not claimed as fresh acceptance evidence. MakerWorld live authentication/import remains tracked as post-release follow-up.

## Mission

Ultimate 3D Studio is a clean-room architectural rewrite of the 3D-Printer Control Center. It is designed to replace the daily Bambu Studio workflow while preserving every working production capability from v5.0.0-beta38.

The stable v5.0.0-beta38 implementation remains a historical regression oracle. Ultimate 3D Studio exited beta as 6.0.0; compatibility, performance, accessibility and additional printer-model work continue as normal post-release development.

## Product surfaces

Ultimate 3D Studio provides one unified Home Assistant dashboard shell with internal routes for:

- Control Center
- Gallery
- CAD Studio
- Slicer Preview
- Profiles
- Print Queue
- Print History
- System and Provider Diagnostics

Upload is available from Control Center, Gallery and CAD Studio. Every upload uses the same Asset Core and can be handed to Gallery, Studio, Queue or direct slicing without duplicating files.

## Non-negotiable compatibility contract

Ultimate 3D Studio must preserve or improve all currently working beta38 functions:

- printer discovery and LAN connection
- live printer telemetry
- camera and snapshot fallback
- AMS telemetry and slot mapping
- print controls
- local archive/gallery
- SD-card model browser
- upload and download
- signed external model handoff
- queue persistence and ordering
- existing Home Assistant entities, services and dashboards during migration
- current German and English release documentation

No legacy route or WebSocket command is removed before an adapter exists and regression tests prove equivalent behavior.

## Architecture principles

1. One canonical state store per domain.
2. Immutable state transitions for frontend application state.
3. Rendering is derived from state; rendering never mutates domain state.
4. No global window-owned application state.
5. No whole-card innerHTML replacement after initial mount.
6. No regex patch scripts as the normal development mechanism.
7. UI layers use explicit stacking contexts and a documented z-index scale.
8. Pointer input is handled by one interaction controller with pointer capture.
9. Scene graph, selection, camera and overlays have separate authorities.
10. Long-running work is represented as persistent jobs with progress events.
11. HTTP API is versioned under /api/ultimate_3d_studio/v1.
12. Slicing is provider-neutral. Local HA slicing is the first provider; external HTTP is a later drop-in provider.
13. Assets are content-addressed and deduplicated by SHA-256.
14. Database records use stable IDs, never UI paths as primary identity.
15. Production deployment is gated by automated unit, integration, UI and regression tests.

## Persistent runtime root

The application-facing runtime path is:

```text
/srv/3D-Studio
```

Persistent data is stored under:

```text
/mnt/homeassist-data/3D-Studio
```

`/srv/3D-Studio` must be bound or linked to the persistent storage location. `/dev/3D-Studio` is intentionally not used because `/dev` is a kernel-managed device filesystem and is not a safe persistent application root.

## Repository layout

```text
studio/
├── api/
├── core/
├── frontend/
├── tests/
├── deploy/
├── docs/
└── README.md
```

## Release history

The alpha series established the architecture, Asset Core, unified upload and gallery, scene graph, viewport, queue migration, slicer provider, profile repository, Bambu profile import, layer preview and dashboard shell.

The project entered beta with:

- `6.0.0-beta1`: first complete CAD, slicer, profile and direct-print workflow
- `6.0.0-beta2`: stable dashboard and deployment baseline
- `6.0.0-beta3`: first physically confirmed multicolor AMS print from Ultimate 3D Studio

- `6.0.0`: stable release after the reviewed native package/deployment contracts and full automated release gate.

Further work after 6.0.0 continues through normal stable maintenance; known post-release items are documented rather than represented as completed.

## Current forensic baseline

The beta38 frontend currently consists of one JavaScript file with approximately:

- 676,076 characters
- 16,509 lines
- 200 event listeners
- 139 render calls
- 48 direct innerHTML writes
- 171 window references
- 64 document references
- 23 requestAnimationFrame paths
- 62 setTimeout calls

This monolithic structure and its accumulated patch history are treated as requirements input, not as the implementation foundation for Ultimate 3D Studio.
