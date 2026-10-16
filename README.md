# Ultimate 3D Studio

CAD, Materialzuordnung und Druckvorbereitung in Home Assistant.

[![Tests](https://github.com/Taracraft/3D-Ultimate-Center/actions/workflows/studio-source-contract.yml/badge.svg?branch=main)](https://github.com/Taracraft/3D-Ultimate-Center/actions/workflows/studio-source-contract.yml)

[Wiki](https://github.com/Taracraft/3D-Ultimate-Center/wiki) · [Handbuch](studio/README.md) · [Funktionen](studio/handbook/FEATURES.md) · [CAD-Beispiele](studio/handbook/CAD_EXAMPLES.md) · [Slicer-Server](https://github.com/Taracraft/3D-Ultimate-Slicer-Server)

![Druckplatte mit Würfel, Zylinder, Ring und Kegel](studio/handbook/images/cad-plate.png)

## Modelle bearbeiten und Drucke vorbereiten

Ultimate 3D Studio verbindet einen 3D-Arbeitsbereich mit der Home-Assistant-Integration und einem eigenständigen Slicing-Dienst. Modelle, Materialien und Druckplatten lassen sich im Browser bearbeiten. Projekte können gespeichert, erneut geöffnet und exportiert werden.

| Bereich | Funktionen |
| --- | --- |
| CAD | STL/3MF öffnen, Grundkörper erstellen, verschieben, drehen, skalieren, spiegeln, ausrichten und anordnen; Modelle messen, teilen und reparieren |
| Projekte | Mehrere Druckplatten, Objektverwaltung, Import und Export, Speichern und Wiederöffnen |
| Materialien | Drucker, Düse, Filament, Prozess und Plattenoberfläche getrennt auswählen; AMS und externe Spule zuordnen |
| Bemalung | Pinsel, Stift, Radierer, Linie, Kreis, Rechteck und Text; separate Malbereiche mit Materialkanälen |
| Vorschau | Modell- und Schichtansicht, Filamentfarben, Toolpaths und Diagnosefilter |
| Bibliothek | Galerie, Ordner, Suche, ZIP-Import und MakerWorld-Anbindung |
| Drucker | Aufträge, Verlauf, Status und Kamera innerhalb von Home Assistant |

Der [Funktionskatalog](studio/handbook/FEATURES.md) beschreibt die Werkzeuge einzeln. Welche Drucker- und Materialkombinationen verfügbar sind, richtet sich nach der angeschlossenen Hardware und den ausgewählten Profilen.

## Einstieg

Im [Wiki](https://github.com/Taracraft/3D-Ultimate-Center/wiki) findest du die Einrichtung und typische Arbeitsabläufe. Das [Handbuch](studio/README.md) enthält die vollständige Bedienungsübersicht einschließlich Tastenkürzeln und Fehlerhilfe.

Das Projekt befindet sich in Entwicklung. Ein vollständiges Installationspaket mit allen Slicing-Engines ist noch nicht veröffentlicht. Die CAD- und Integrationsquellen stehen im Repository; Hinweise zur Einrichtung enthält die [Installationsseite](studio/handbook/wiki/Installation.md).

## Repository-Aufbau

```text
homeassistant/custom_components/ultimate_3d_studio/  Home-Assistant-Integration
studio/frontend/                                   Browseroberfläche
studio/api/ und studio/core/                       Anwendungslogik
studio/Slicer-Server/                               Slicer und Containerwerkzeuge
studio/handbook/                                    Handbuch und Bilder
studio/tests/ und studio/frontend-tests/             Tests
```

Für Entwicklungsbefehle ist `studio/` das Arbeitsverzeichnis:

```sh
git clone https://github.com/Taracraft/3D-Ultimate-Center.git
cd 3D-Ultimate-Center/studio
```

Der [Ultimate Slicer Server](https://github.com/Taracraft/3D-Ultimate-Slicer-Server) besitzt ein eigenes Repository und [Wiki](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/wiki). Er enthält die API, den Worker, die Engine-Verwaltung und die Docker-Werkzeuge.

## Entwicklung und Lizenz

[Architektur](studio/ARCHITECTURE.md) · [Entwicklung](studio/handbook/wiki/Entwicklung.md) · [Änderungen](studio/CHANGELOG-DE.md)

Es gelten die [Lizenz](LICENSE) und die Hinweise in [SOURCE_NOTICES.md](SOURCE_NOTICES.md). Einzelne Slicer- und Drittanbieterkomponenten besitzen eigene Lizenzbedingungen; die [Dateizuordnung](source-license-map.json) nennt den jeweiligen Ursprung.
