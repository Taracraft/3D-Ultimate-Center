# Ultimate 3D Studio

![Promo-Illustration - Ultimate 3D Studio](studio/handbook/assets/studio-hero.png)

**Dein Modell. Deine Materialien. Deine Druckplatte. Direkt in Home Assistant.**

Modelle sammeln, Geometrie bearbeiten, Flächen bemalen und Druckvorhaben nachvollziehbar vorbereiten: Ultimate 3D Studio verbindet die Browseroberfläche mit einer Home-Assistant-Integration und dem eigenständigen [Ultimate Slicer Server](https://github.com/Taracraft/3D-Ultimate-Slicer-Server).

[![Tests](https://github.com/Taracraft/3D-Ultimate-Center/actions/workflows/studio-source-contract.yml/badge.svg?branch=main)](https://github.com/Taracraft/3D-Ultimate-Center/actions/workflows/studio-source-contract.yml)

[PDF-Handbuch](studio/handbook/Ultimate_3D_Studio_Handbuch.pdf) · [Handbuch](studio/README.md) · [Funktionen](studio/handbook/FEATURES.md) · [CAD-Beispiele](studio/handbook/CAD_EXAMPLES.md) · [Wiki](https://github.com/Taracraft/3D-Ultimate-Center/wiki) · [Slicer-Server](https://github.com/Taracraft/3D-Ultimate-Slicer-Server)

![Originalaufnahme der Studio-Druckplatte mit synthetischen Grundkörpern](studio/handbook/images/cad-plate.png)

**Entwicklungsstand:** 77 katalogisierte Funktionen und 41 Zusatzanforderungen. Viele vollständige Funktionsabnahmen sind offen. Quellen, Tests und Dokumentation sind veröffentlicht; daraus folgt kein vollständiger Produktrelease. Die konkrete Auslieferung beschreibt [RELEASE_STATUS.md](studio/Slicer-Server/RELEASE_STATUS.md).

## Ein Arbeitsplatz für deinen Modellaufbau

| Dein Vorhaben | Das Studio bietet |
| --- | --- |
| Ein Modell vorbereiten | STL/3MF öffnen, Grundkörper erzeugen, verschieben, drehen, skalieren und auf der Platte ausrichten |
| Eine Szene aufbauen | Mehrere Druckplatten, Objektlisten, Mehrfachauswahl, Duplizieren und gespeicherte Projekte |
| Material bewusst zuordnen | Getrennte Auswahl von Drucker, Düse, Filament, Druckprofil und Oberfläche; AMS und externe Spule unterscheiden |
| Flächen gestalten | Pinsel, Stift, Radierer, Kreis, Rechteck, Linie und Text mit materialgebundenen Malbereichen |
| Ein Ergebnis beurteilen | Vorbereitungs-, Farb- und Schichtansicht, Toolpaths und Diagnosefilter für vorhandene Ergebnisse |
| Den Bestand überblicken | Galerie mit Ordnern, Suche und ZIP-Verwaltung, MakerWorld-Zugang, Aufgaben, Verlauf und Kamera |

Die [Funktionsübersicht](studio/handbook/FEATURES.md) nennt Umfang und Grenzen. Angezeigte Hardware- oder Engineauswahl ersetzt keine Abnahme der konkreten Kombination.

## Womit möchtest du beginnen?

- **Zum ersten Mal hier:** Folge dem [ersten Projekt](studio/README.md#erstes-projekt). Ein Würfel genügt, um Bearbeitung und Speichern kennenzulernen.
- **Modelle organisieren:** Öffne [Galerie und Druckerspeicher](studio/README.md#galerie) oder den [MakerWorld-Ablauf](studio/README.md#makerworld).
- **Farben und Materialien:** Lies [Bemalung](studio/README.md#bemalung), [Materialkanäle](studio/README.md#material) und [Profile](studio/README.md#profile) zusammen.
- **Eine Installation einrichten:** Beginne mit [Integration, HACS und Slicer-Verbindung](studio/README.md#einrichtung) und dem [Slicer-Schnellstart](studio/Slicer-Server/DOCKER_QUICKSTART.md).
- **Ein Problem eingrenzen:** Die [Fehlerhilfe](studio/README.md#fehlersuche) führt von der Beobachtung zum nächsten prüfbaren Schritt.

## Quellen und Entwicklung

| Pfad | Inhalt |
| --- | --- |
| `custom_components/ultimate_3d_studio/` | Root-Integrationsprojektion für HACS einschließlich Frontend-Assets |
| `homeassistant/custom_components/ultimate_3d_studio/` | Erhaltene Kompatibilitätsprojektion |
| `studio/frontend/` | Browseroberfläche |
| `studio/api/` und `studio/core/` | Anwendungslogik |
| `studio/Slicer-Server/` | Slicer-, Container- und Betriebsquellen |
| `studio/handbook/` | Funktionskatalog, Beispiele und Originalbilder |

Für Entwicklungsbefehle ist nach dem Klonen `studio/` das Arbeitsverzeichnis. [Architektur](studio/ARCHITECTURE.md), [Entwicklung](studio/handbook/wiki/Entwicklung.md) und [Änderungen](studio/CHANGELOG-DE.md) bieten den technischen Einstieg.

Es gelten die [Lizenz](LICENSE), die [bereichsspezifischen Hinweise](SOURCE_NOTICES.md) und die [Dateizuordnung](source-license-map.json). Slicer- und Drittanbietermaterial besitzen teilweise eigene Bedingungen. Herkunft und Grenzen der Originalaufnahmen sind ebenfalls in den Lizenzhinweisen dokumentiert.
