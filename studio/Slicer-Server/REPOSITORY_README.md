# Ultimate Slicer Server

![Promo-Illustration - Ultimate Slicer Server](https://raw.githubusercontent.com/Taracraft/3D-Ultimate-Slicer-Server/main/assets/slicer-hero.png)

![Animierte, zugeschnittene Originalaufnahme des Slicing- und Vorschau-Workflows](https://raw.githubusercontent.com/Taracraft/3D-Ultimate-Slicer-Server/main/assets/ultimate-slicer-server-demo.gif)

Die Animation nutzt tatsächlich aufgenommene, zugeschnittene Studio-Frames; Browserleiste, Adressfeld und Taskleiste sind nicht enthalten. Sie zeigt den sichtbaren Slicing-/Vorschau-Workflow, nicht die Lieferung eines eigenständigen Runtime-Images, einer Engine oder eine vollständige Produktabnahme.

**Slicing als eigenständiger Dienst für [Ultimate 3D Studio](https://github.com/Taracraft/3D-Ultimate-Center).** Modelle, Aufträge und Ergebnisse erhalten einen gemeinsamen technischen Ablauf: Eine HTTP-API nimmt Anfragen entgegen, ein getrennter Worker verarbeitet die Jobs, und fest zugeordnete Engines liefern die Grundlage für die spätere G-Code-Erzeugung.

[PDF-Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/Ultimate_Slicer_Server_Handbuch.pdf) · [API-Referenz](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/API.md) · [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) · [Installation und Einrichtung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/INSTALLATION.md) · [Betrieb](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/OPERATIONS.md) · [Entwicklungsstand](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/RELEASE_STATUS.md) · [Lizenzhinweise](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/SOURCE_NOTICES.md)

## Was der Dienst übernimmt

Ultimate Slicer Server trennt die rechenintensive Auftragsverarbeitung von der Studio-Oberfläche und ihrer Home-Assistant-Anbindung. Die API, Jobverwaltung, Worker-Steuerung, Telemetrie, Containerkonfiguration und nativen Linux-Paketwerkzeuge sind als Quellen verfügbar. Bambu Studio, PrusaSlicer und CuraEngine sind die drei vorgesehenen Enginefamilien. Versionen, Dateien, Profile und Ressourcen werden über überprüfbare Katalog- und Paketverträge zugeordnet.

Programmcode und Enginebestand werden schreibgeschützt eingebunden. Eigene Konfiguration, Profile, Modelle, Auftragszustände und Ergebnisse erhalten getrennte Speicherbereiche. Dadurch lassen sich Softwarestand und persönliche Daten bei einem Update getrennt betrachten. Die Betriebsdokumentation beschreibt, welche Daten zusammen gesichert werden und wie ein Fehlerzustand vor einem Wiederanlauf erhalten bleibt.

Bedienung und Verbindungsverwaltung erfolgen in Ultimate 3D Studio. Der Server stellt die dafür benötigte Schnittstelle und Verarbeitung bereit. Ein Verbindungstest, ein Slicing-Auftrag, ein Druckerupload und ein Druckstart bleiben jeweils eigenständige Aktionen.

## Aktueller Lieferumfang

**Der Quellstand ist veröffentlicht; ein vollständiger Produktrelease ist noch offen (`FullRelease=false`).** Es gibt derzeit keinen freigegebenen Runtime-Download, keinen freigegebenen Image-Digest und keine freigegebene Supervisor-Paketreferenz. Das vorhandene Prüfimage enthält keine Slicing-Engines und kann allein keine Modelle slicen.

| Bereich | Was aktuell vorliegt | Was noch fehlt |
| --- | --- | --- |
| API und Worker | Quellen, Jobverwaltung und Prüfwerkzeuge | Vollständige reale Funktionsabnahme |
| Docker | Build-Kontext und Compose-Dienstkandidat | Freigegebenes Image mit vollständigem Enginebestand |
| Engines | Katalog-, Archiv- und Distributionswerkzeuge | Freigegebene Einträge für alle drei Familien |
| Home Assistant | Externe Verbindung und Supervisor-Verwaltung im Quellcode | Freigegebene App-Paketreferenz und reale Abnahmen |
| Natives Linux-Paket | Paketierung, lesende Vorprüfung und Installationslogik | Betriebsfreigabe; `native_deploy_ready=false` |

Der ausgelieferte [Engine-Katalog](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/engine_catalog.json) enthält `releases=[]`; `bambu_studio`, `prusaslicer` und `curaengine` stehen unter `pending`. Vorhandene Archivnachweise und erfolgreiche Quellprüfungen ersetzen weder diese Freigabe noch einen echten Slice. Linux/amd64 ist der beschriebene Zielumfang. Eine allgemeine ARM-Unterstützung ist nicht zugesagt.

## Der passende Einstieg

Die [Installationsanleitung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/INSTALLATION.md) führt durch drei getrennte Wege. Für einen bereits betriebenen eigenständigen Slicer wird in Home Assistant dessen HTTPS-Adresse mit API-Secret eingerichtet. Die Supervisor-App ist der vorgesehene verwaltete Weg für eine geeignete Home-Assistant-Installation; ihre Installation bleibt bis zur freigegebenen Paketreferenz gesperrt. Die Kopplung eines bereits provisionierten Unix-Hosts benötigt eine eigenständige geschützte Hosteinrichtung und ist kein automatischer Ersatz für einen fehlgeschlagenen App-Vorgang.

Wer an den Quellen arbeitet, beginnt mit einer isolierten Dateiprüfung. Wer eine laufende Installation betreut, liest zuerst [Betrieb, Updates und Wiederherstellung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/OPERATIONS.md). Linux-Testserver, Testinstallationen und frische Neuinstallationen gehören seit der Entscheidung vom 17.10.2026 nicht zur Releasebewertung oder zum Releaseabschluss. Nicht ausgeführte Prüfungen bleiben separat als ungeprüft beziehungsweise `not_run` dokumentiert. Ein grünes Gesamtgate oder ein veröffentlichtes Wiki bestätigt keine vollständige Produktabnahme.

## Quellen nachvollziehbar prüfen

Die folgenden Befehle gelten ab der Wurzel dieses eigenständigen Slicer-Repositories. Sie prüfen Quellen beziehungsweise erzeugen einen neuen Build-Kontext außerhalb des Klons. Im Studio-Gesamtrepository ist `studio/` die Komponentenwurzel; dort gelten Profilprüfung und Kontextbildung ebenfalls. Die Liefermanifestprüfung mit `build_repository.py --verify .` gehört dagegen ausschließlich zur erzeugten Slicer-Repositoryprojektion.

```sh
python3 Slicer-Server/build_repository.py --verify .
python3 Slicer-Server/verify_profile_sources.py --source-root .
BUILD_ROOT="$(mktemp -d /tmp/ultimate-slicer-build-XXXXXX)"
python3 Slicer-Server/prepare_context.py --source-root "$PWD" --output "$BUILD_ROOT/context"
```

Diese Schritte stellen keinen laufenden Slicer bereit. Zugangsdaten, Nutzermodelle und Standortkonfiguration gehören außerhalb des Image-Kontexts. Details zu erwarteten Ergebnissen und Fehlercodes stehen in der [Installation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/INSTALLATION.md).

## Orientierung im Repository

| Verzeichnis | Inhalt |
| --- | --- |
| `Slicer-Server/` | Container, Engineverwaltung, Einrichtung und Betriebsdokumentation |
| `deploy/homeassistant/host/3d-printer-slicing-server/` | Server, Dispatcher und Jobverwaltung |
| `deploy/homeassistant/custom_components/ultimate_3d_studio/` | Gemeinsame Geometrie- und Materialmodule |
| `packages/ultimate-slicer-server/` | Native Linux-Paketwerkzeuge |
| `tests/` | Automatisierte Quell- und Vertragsprüfungen |

Die technischen Verzeichnisnamen bleiben als bestehende Quellpfade erhalten. Für den vollständigen Enginebestand siehe [Engine-Distribution](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/ENGINE_DISTRIBUTION.md), für persistente Daten [Datenhaltung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/DATA_PERSISTENCE.md). Das [GitHub-Wiki](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/wiki) bietet einen zusätzlichen Dokumentationseinstieg.

Die Titelgrafik ist eine [Promo-Illustration](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/assets/ASSET_NOTICES.md), kein Produktscreenshot und kein Funktionsnachweis.

## Lizenz und Herkunft

Die Rechte unterscheiden sich nach Komponente. Das gesamte Repository wird weder pauschal als MIT-lizenziert noch pauschal als Open Source eingeordnet. Maßgeblich sind [SOURCE_NOTICES.md](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/SOURCE_NOTICES.md), die [Slicer-Lizenz](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/LICENSE), [Drittanbieterhinweise](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/THIRD_PARTY_NOTICES.md) und die jeweiligen Herkunftsnachweise. Engineprogramme, Betriebssystempakete, Basisimages und Bibliotheken benötigen vor ihrer Auslieferung eine eigene Prüfung. Eine Dateiprüfsumme belegt Dateiidentität, keine Lizenz- oder Betriebsfreigabe.
