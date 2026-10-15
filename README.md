# Ultimate 3D Studio

Home Assistant Studio sources and a separate slicer server.

## Start here

- [Studio overview](studio/README.md)
- [Architecture](studio/ARCHITECTURE.md)
- [Slicer server](studio/Slicer-Server/README.md)
- [Installation](studio/Slicer-Server/INSTALLATION.md)
- [Operation and recovery](studio/Slicer-Server/OPERATIONS.md)
- [Wiki source pages](studio/Slicer-Server/wiki/Home.md)
- [Source notices](SOURCE_NOTICES.md)
- [File-specific notice map](source-license-map.json)

## Source delivery and installation status

The source inventory includes the native service and timer definitions needed
by the synthetic package tests. GitHub CI checks the exact delivery inventory,
the unchanged legacy component, Python contracts, TypeScript and frontend
tests. Source delivery does not approve production operation.

The slicer runs separately from Home Assistant. Compose is the intended clean
installation path. Follow the installation status and pending acceptance
steps in the slicer documentation before using a new installation.
Existing native installations require a separately reviewed migration.
Engine catalog entries remain pending. Manual Linux installation, Docker,
TLS, upgrade and restore acceptance follow the complete source delivery.

## Licensing

The inherited [MIT notice](LICENSE) remains available. New original material
in the Slicer-Server area has separate [private-use terms](studio/Slicer-Server/LICENSE).
Previously licensed and third-party material retains its own applicable terms.
Selected upstream profile originals and their derived defaults retain the
upstream AGPL terms; the custom private-use restrictions do not apply to them.

See [SOURCE_NOTICES.md](SOURCE_NOTICES.md) for the concrete file boundaries.
