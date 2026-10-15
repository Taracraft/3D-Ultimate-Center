# Ultimate 3D Printing Studio

## Current source baseline

The current source version is **6.0.0**. The public architecture contract is documented in [ARCHITECTURE.md](ARCHITECTURE.md). Home Assistant and the native Linux slicer have separate packages and acceptance evidence.

The current migration still requires its installation, restore, integration and release reviews. A green source quality gate does not by itself establish that a fresh installation or the loaded production runtime has passed those reviews.

## Slicer server and Docker

The dedicated [Slicer-Server](Slicer-Server/README.md) area contains Docker packaging, [installation instructions](Slicer-Server/INSTALLATION.md), operating and migration documentation, and [wiki sources](Slicer-Server/wiki/Home.md). Docker Compose is the intended installation path. The repository contains a source-integrity preflight image and an API/worker service candidate tested with synthetic boundaries. Engine releases remain pending; the candidate is not approved for production slicing or deployment.

New original material in that area uses the [private-use, no-modification license](Slicer-Server/LICENSE). Existing and third-party material keeps its applicable licensing rights; see [license boundaries](Slicer-Server/THIRD_PARTY_NOTICES.md). Public release requires a complete license review and publication of the GitHub wiki.

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
12. Slicing runs in a separate Linux service, with Docker Compose as its intended installation path, configured through the Home Assistant integration; no development PC is required.
13. Assets are content-addressed and deduplicated by SHA-256.
14. Database records use stable IDs, never UI paths as primary identity.
15. Production deployment is gated by automated unit, integration, UI and regression tests.

## Persistent data and portable installation

Home Assistant owns integration options and stored UI data through its
ConfigEntry and Storage interfaces. Installation does not require a fixed
host directory, a development PC path or a manually created runtime symlink.

The separate Compose slicer uses explicitly provisioned bind mounts for data,
profiles, engine artifacts, API credentials and TLS material. Follow the
[current runtime installation contract](Slicer-Server/RUNTIME_INSTALLATION.md)
and [clean testserver runbook](Slicer-Server/LINUX_TEST_SERVER_RUNBOOK.md).
Do not automatically adopt, delete or migrate an existing native slicer store.
The current live system retains its native slicer; Compose is tested only on
the separate clean testserver. Real persistence, upgrade and restore acceptance
remains open until that testserver supplies verified results.

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

## Container startup safety status

The source-preflight image now includes an explicit readiness/permission
handshake between its lifecycle wrapper and the canonical job controller.
A stop requested before the child has installed its signal handlers is delivered
as a deny token, not as a signal to an unprepared interpreter. Missing readiness
or an exit before readiness requires recovery and blocks follow-up work.

Three synthetic Linux/amd64 scenarios verify early stop, readiness timeout, and
premature exit without starting the dispatcher. They do not approve the
production API, telemetry, slicer engine, real jobs, or deployment. The image
therefore continues to report container_deploy_ready=false.

## Docker-Dienstbetrieb: gepruefter Kandidat

API, Worker und ein einzelner Telemetrie-Schreiber sind jetzt als
[Compose-Dienstkandidat](Slicer-Server/RUNTIME_INSTALLATION.md) umgesetzt.
Der Kandidat wurde in einem neuen synthetischen Datenverzeichnis gestartet:
TLS mit Zertifikatspruefung, 401 ohne Secret, authentifizierter Info-Abruf,
Leerlauf-Stop/Neustart, doppelter Worker und verwaister Jobmarker geprueft.
Die Engine-Ausfuehrungsgrenze verifiziert im Worker den Kernelvertrag.
Synthetischer Anchor-Ausfall und Backup/Restore (fuenf Dateien hashgleich)
sind ebenfalls bestanden. Engine, echter Slice, HA-Cross-Host und
produktiver Bestands-Restore bleiben offen.
Docker bleibt vor allen weiteren Migrationsarbeiten; keine Releasefreigabe.
