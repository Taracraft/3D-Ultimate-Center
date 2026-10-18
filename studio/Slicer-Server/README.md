# Ultimate Slicer Server

![Promo-Illustration für Ultimate Slicer Server](assets/slicer-hero.png)

[Ausführliches Handbuch](HANDBUCH.md) · [PDF-Handbuch](Ultimate_Slicer_Server_Handbuch.pdf) · [API-Referenz](API.md)

Die Titelgrafik ist eine [Markenillustration](assets/ASSET_NOTICES.md), kein Produktscreenshot.

Der Server übernimmt Slicing-Aufträge für Ultimate 3D Studio. HTTP-API und Worker sind getrennt; Geometrie-, Material- und Maschinenmodule werden gemeinsam mit der Home-Assistant-Integration verwendet.

**Docker-Lieferung vom 18.10.2026:** Das vorhandene Linux/amd64-Runtime-Image mit Bambu Studio, PrusaSlicer und CuraEngine ist unter [v0.1.0-alpha10](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/tag/v0.1.0-alpha10) veröffentlicht. [Installation und genaue Versionszuordnung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/RUNTIME_RELEASE_README.md), [Prüfsummen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/SHA256SUMS) und zugehörige Quellen/Lizenznachweise gehören zur Lieferung. Das dokumentierte Expat-Restrisiko ist für diesen Kandidaten akzeptiert, technisch aber nicht behoben; siehe [Risikodokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/EXPAT_RISK_ACCEPTANCE.json).

Studio wird unabhängig als HACS-Integration 6.0.5 ausgeliefert. Die Slicer-Quellen tragen alpha10; das unveränderte Runtime-Image enthält API-Metadaten alpha9. Image-ID: `sha256:cb37fa6b9aee8c40035a5f337a67d9fc13c4429e06098024731e556f8e8bfb49`. Es wurde dafür kein identischer Neubau vorgenommen. Externe Installations-, UI- und Pilotprüfungen bleiben `not_run` und sind keine zusätzlichen Releasegates. Eine Gesamtfertigstellung wird daraus nicht abgeleitet.


## Dokumentation

| Thema | Anleitung |
| --- | --- |
| Einstieg und Voraussetzungen | [Installation](INSTALLATION.md) |
| Image aus Quellen bauen | [Docker-Schnellstart](DOCKER_QUICKSTART.md) |
| API und Worker konfigurieren | [Laufzeit](RUNTIME_INSTALLATION.md) |
| Home Assistant anbinden | [Supervisor-App und externer Server](SUPERVISOR_APP_SETUP.md) |
| Engine-Dateien bereitstellen | [Katalog](ENGINE_CATALOG.md), [Paketierung](ENGINE_DISTRIBUTION.md) |
| Daten und Profile | [Persistenz](DATA_PERSISTENCE.md), [Profile](PERSISTENT_PROFILES.md) |
| Updates und Wiederherstellung | [Wartung](MAINTENANCE.md), [Migration](MIGRATION.md) |
| Entwicklung und Tests | [Container-Tests](CONTAINER_TESTING.md), [Linux-Prüfumgebung](LINUX_SETUP.md) |

## Architektur

Die Runtime-Anleitung liefert die Compose-Datei für das veröffentlichte Image mit eingebauten Engines. `compose.candidate.yaml` beschreibt dagegen den älteren Entwicklerweg mit externen Engine-Binds und die Dienste für Dateninitialisierung, Profilinitialisierung, API und Worker. Die API besitzt einen Netzwerkzugang; der Worker läuft ohne Netzwerk. Beide verwenden einen eingeschränkten Benutzer und binden Engine- und Profilverzeichnisse schreibgeschützt ein.

Die Engine-Paketierung verwendet einen Katalog mit festen Versionen, Dateigrößen und Prüfsummen. Ein Paket wird vollständig geprüft, bevor es in eine neue Generation übernommen wird. Der Aktivierungsmechanismus bewahrt die vorherige Generation für die Wiederherstellung auf.

## Entwicklungsstand

Das veröffentlichte Runtime-Image enthält die drei Engines. Das separate Source-Preflight-Image bleibt eine reine Dateiprüfung ohne Engines. Native Paket- und Supervisor-Freigaben bleiben getrennt; offene Funktionsabnahmen stehen unter [Entwicklungsstand](RELEASE_STATUS.md).

## Quellcode und Lizenz

[Quellumfang](REPOSITORY_CONTENTS.md) beschreibt den Repository-Aufbau und die Paketwerkzeuge. Für eigene und übernommene Dateien gelten die jeweils zugeordneten [Lizenzbedingungen](LICENSE) und [Drittanbieterhinweise](THIRD_PARTY_NOTICES.md).

