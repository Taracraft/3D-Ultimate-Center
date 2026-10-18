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

**Docker-Lieferung vom 18.10.2026:** Das vorhandene Linux/amd64-Runtime-Image mit Bambu Studio, PrusaSlicer und CuraEngine ist unter [v0.1.0-alpha10](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/tag/v0.1.0-alpha10) veröffentlicht. [Installation und genaue Versionszuordnung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/RUNTIME_RELEASE_README.md), [Prüfsummen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/SHA256SUMS) und zugehörige Quellen/Lizenznachweise gehören zur Lieferung. Das dokumentierte Expat-Restrisiko ist für diesen Kandidaten akzeptiert, technisch aber nicht behoben; siehe [Risikodokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/EXPAT_RISK_ACCEPTANCE.json).

Studio wird unabhängig als HACS-Integration 6.0.5 ausgeliefert. Die Slicer-Quellen tragen alpha10; das unveränderte Runtime-Image enthält API-Metadaten alpha9. Image-ID: `sha256:cb37fa6b9aee8c40035a5f337a67d9fc13c4429e06098024731e556f8e8bfb49`. Es wurde dafür kein identischer Neubau vorgenommen. Externe Installations-, UI- und Pilotprüfungen bleiben `not_run` und sind keine zusätzlichen Releasegates. Eine Gesamtfertigstellung wird daraus nicht abgeleitet.

Der Release enthält 24 einzeln geprüfte Downloads mit insgesamt 4.754.562.403 Bytes. Jeder Download wurde nach dem Upload ohne Anmeldung vollständig gegen Größe und SHA-256 geprüft. Das Runtime-Image ist vom weiterhin verfügbaren Source-Preflight-Image zu unterscheiden: Nur die Runtime enthält die drei Engines und ihre Laufzeitbibliotheken.

Der Quellkatalog `Slicer-Server/engine_catalog.json` bleibt der noch leere Auswahlkatalog für den getrennten Paket-/Installerweg. Für diese Docker-Lieferung gilt der imagegebundene Release-Download `CATALOG.json`; ein leerer Quellkatalog bedeutet nicht, dass dem veröffentlichten Image Engines fehlen. Eine allgemeine ARM-Unterstützung ist nicht zugesagt.


## Installation mit dem TaraCraft-Assistenten

**Home Assistant und Slicer laufen als getrennte Docker-Container auf deinem vorhandenen Linuxserver.**
Du administrierst Linux, Docker, Netzwerk und weitere Dienste weiterhin selbst.
Der Assistent installiert und verbindet HACS, Studio und den Slicer.

Wenn dir die aktuelle einzelne Datei `TaraCraft-Install.sh` bereitgestellt wurde,
kopiere sie auf den Linux/amd64-Server und starte sie dort im Terminal:

```sh
sudo bash TaraCraft-Install.sh
```

Mit `bash TaraCraft-Install.sh --demo` lässt sich die Oberfläche vorher ansehen;
`bash TaraCraft-Install.sh --self-test` führt isolierte Prüfungen aus. Der Assistent
zeigt den aktuellen Schritt oben und das echte, scrollbar bleibende Shell-Protokoll
darunter. Bei einer vorhandenen zugehörigen Sitzung **Fortsetzen** wählen.

Die [ausführliche Anleitung für Container, HACS, MQTT, Slicer und Dashboard](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/Slicer-Server/INSTALLATION.md)
beschreibt die geführte Einrichtung, persönliche GitHub-Geräteanmeldung,
automatische Repository-Übernahme und das vollständige Zurücksetzen. Die
Automatisierungen gelten für den aktuellen separat bereitgestellten Assistenten
mit seinen gebundenen Setup-Ergänzungen. Sie sind keine Behauptung, dass der
unveränderte HACS-Tag 6.0.5 diese neuen Formulare bereits enthält.

Für eine Installation ohne diesen Assistenten bleibt der unten verlinkte normale
HACS-/Docker-Weg gültig. Anmeldedaten, Docker-Host und Netzverbindungen werden immer
für die eigene Umgebung eingerichtet.

## Der passende Einstieg

Die eigenständig installierbare Docker-Lieferung beginnt mit der [Runtime-Installationsanleitung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/RUNTIME_RELEASE_README.md). Sie beschreibt Download, vollständige Hashprüfung, Laden der exakten Image-ID und die mitgelieferte Compose-Konfiguration. Eigene Daten, TLS-Dateien und API-Secret werden auf dem Zielhost eingerichtet. Ultimate 3D Studio verbindet sich anschließend über HTTPS mit dem Dienst.

Die folgenden Quellprüfungen dokumentieren zusätzliche Entwicklerwege. Für die Installation auf deinem Linuxserver gilt die Runtime-Anleitung mit Docker Compose. Die normale Docker-Installation benötigt keine Hostkopplung und keinen zusätzlichen Installer-Dienst.


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
