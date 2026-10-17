# Ultimate Slicer Server

![Promo-Illustration für Ultimate Slicer Server](assets/slicer-hero.png)

[Ausführliches Handbuch](HANDBUCH.md) · [PDF-Handbuch](Ultimate_Slicer_Server_Handbuch.pdf) · [API-Referenz](API.md)

Die Titelgrafik ist eine [Markenillustration](assets/ASSET_NOTICES.md), kein Produktscreenshot.

Der Server übernimmt Slicing-Aufträge für Ultimate 3D Studio. HTTP-API und Worker sind getrennt; Geometrie-, Material- und Maschinenmodule werden gemeinsam mit der Home-Assistant-Integration verwendet.

**Lieferstand:** API, Worker und Paketwerkzeuge sind als Quellen verfügbar. Das vollständige Engine-Laufzeitpaket ist noch nicht veröffentlicht; [Entwicklungsstand und Grenzen](RELEASE_STATUS.md) gelten auch für diese Dokumentation.

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

`compose.candidate.yaml` beschreibt die Dienste für Dateninitialisierung, Profilinitialisierung, API und Worker. Die API besitzt einen Netzwerkzugang; der Worker läuft ohne Netzwerk. Beide verwenden einen eingeschränkten Benutzer und binden Engine- und Profilverzeichnisse schreibgeschützt ein.

Die Engine-Paketierung verwendet einen Katalog mit festen Versionen, Dateigrößen und Prüfsummen. Ein Paket wird vollständig geprüft, bevor es in eine neue Generation übernommen wird. Der Aktivierungsmechanismus bewahrt die vorherige Generation für die Wiederherstellung auf.

## Entwicklungsstand

Die vollständige Engine- und App-Auslieferung ist noch in Arbeit. Das Prüfimage kontrolliert den Quellbestand, enthält aber keine Engine-Binaries. Die Supervisor-Einrichtung bietet daher noch kein freigegebenes installierbares App-Paket an. Weitere Angaben stehen unter [Entwicklungsstand](RELEASE_STATUS.md).

## Quellcode und Lizenz

[Quellumfang](REPOSITORY_CONTENTS.md) beschreibt den Repository-Aufbau und die Paketwerkzeuge. Für eigene und übernommene Dateien gelten die jeweils zugeordneten [Lizenzbedingungen](LICENSE) und [Drittanbieterhinweise](THIRD_PARTY_NOTICES.md).

