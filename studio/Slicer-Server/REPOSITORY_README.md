# Ultimate Slicer Server

Der Slicing-Dienst für [Ultimate 3D Studio](https://github.com/Taracraft/3D-Ultimate-Center): HTTP-API, Jobverwaltung, isolierter Worker und Engine-Paketierung für Linux.

[Wiki](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/wiki) · [Installation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/INSTALLATION.md) · [Docker](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/DOCKER_QUICKSTART.md) · [Betrieb](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/OPERATIONS.md) · [Entwicklungsstand](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/RELEASE_STATUS.md)

## Aufbau

Die API nimmt Modelle und Slicing-Aufträge entgegen. Der Worker verarbeitet die Aufträge getrennt von der API. Engine-Dateien und Profile werden schreibgeschützt eingebunden; Konfiguration, Aufträge und Ergebnisse liegen in eigenen persistenten Verzeichnissen.

| Bestandteil | Verzeichnis |
| --- | --- |
| Container, Engine-Verwaltung und Installation | `Slicer-Server/` |
| Server, Dispatcher und Jobverwaltung | `deploy/homeassistant/host/3d-printer-slicing-server/` |
| Gemeinsame Geometrie- und Materialmodule | `deploy/homeassistant/custom_components/ultimate_3d_studio/` |
| Native Linux-Paketwerkzeuge | `packages/ultimate-slicer-server/` |
| Automatisierte Tests | `tests/` |

Bambu Studio, PrusaSlicer und CuraEngine sind als Enginefamilien vorgesehen. Ihre Versionen, Archive und Ressourcen werden über einen festen Katalog zugeordnet.

## Aktueller Stand

API, Worker, Paketwerkzeuge und Docker-Konfiguration sind als Quellcode verfügbar. Ein vollständiges Laufzeitpaket mit freigegebenen Engine-Binaries ist noch nicht veröffentlicht. Das vorhandene Prüfimage enthält keine Slicing-Engines und kann deshalb allein keine Modelle slicen.

Die [Installationsanleitung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/INSTALLATION.md) unterscheidet Quellprüfung, Containerbau und Laufzeitkonfiguration. Die [Engine-Dokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/ENGINE_DISTRIBUTION.md) beschreibt die Zusammenstellung des vollständigen Enginebestands.

## Aus Quellen arbeiten

Alle Befehle gelten ab der Wurzel dieses Repositories. Im Studio-Gesamtrepository gelten sie ab `studio/`.

```sh
python3 Slicer-Server/build_repository.py --verify .
python3 Slicer-Server/verify_profile_sources.py --source-root .
BUILD_ROOT="$(mktemp -d /tmp/ultimate-slicer-build-XXXXXX)"
python3 Slicer-Server/prepare_context.py --source-root "$PWD" --output "$BUILD_ROOT/context"
```

Build-Ausgaben müssen außerhalb des Klons liegen. Der Kontextgenerator übernimmt nur die benötigten Quellen und Metadaten. Zugangsdaten, Konfiguration und Nutzermodelle gehören nicht in den Image-Kontext.

## Dokumentation

[Docker-Schnellstart](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/DOCKER_QUICKSTART.md) erklärt den Imagebau. [Laufzeitkonfiguration](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/RUNTIME_INSTALLATION.md) beschreibt Verzeichnisse, Zertifikate und Compose-Dienste. [Betrieb](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/OPERATIONS.md), [Wartung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/MAINTENANCE.md) und [Datenhaltung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/DATA_PERSISTENCE.md) behandeln den laufenden Dienst.

Für die Home-Assistant-Anbindung siehe [Einrichtung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/SUPERVISOR_APP_SETUP.md) und [Wiki](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/wiki/Home-Assistant).

## Lizenz

Die Lizenzbedingungen unterscheiden sich nach Komponente. Maßgeblich sind [SOURCE_NOTICES.md](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/SOURCE_NOTICES.md), die [Slicer-Lizenz](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/LICENSE) und die [Drittanbieterhinweise](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/THIRD_PARTY_NOTICES.md). Bereits bestehende Lizenzen werden durch die Veröffentlichung nicht ersetzt.
