# Quellcode und Verzeichnisse

Das Slicer-Repository enthält den Dienst, gemeinsam verwendete Module, Paketwerkzeuge, Tests und Dokumentation. Seine Pfade entsprechen dem Komponentenaufbau im Studio-Gesamtrepository. Dokumente und komponentenbezogene Werkzeuge sind unter `Slicer-Server/` gebündelt; gemeinsam genutzte Module und Tests ergänzen diesen Komponentenbereich.

## Was zum Quellpaket gehört

Das Dateimanifest ermöglicht einen Vergleich von Umfang, Größe und Prüfsummen. Modelle, Aufträge, Konfiguration und Engine-Binaries sind nicht Bestandteil dieses Quellpakets. Daraus erklärt sich, warum die Größe des Repositorys nicht mit dem Speicherbedarf einer vollständigen Laufzeitinstallation übereinstimmen muss.

| Bestand | Einordnung |
| --- | --- |
| Dienst und gemeinsame Module | Programmquellen des Servers |
| Paketwerkzeuge und Tests | Aufbau und Prüfung der vorgesehenen Lieferung |
| Dokumentation | Einrichtung, Betrieb, Schnittstellen und Nachweise |
| Engine-Binaries und Ressourcen | Separat bereitzustellender Laufzeitbestand |
| Modelle, Aufträge und Konfiguration | Nutz- und Betriebsdaten außerhalb des Quellpakets |

## Einen Quellstand vergleichen

1. Halte Repository und Commit-ID des untersuchten Stands fest.
2. Lies die vorgesehenen Bestandteile in der [Repository-Beschreibung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/REPOSITORY_CONTENTS.md).
3. Vergleiche die tatsächlich vorhandenen Dateien mit dem zugehörigen Manifest und ihren vorgesehenen Pfaden.
4. Prüfe den Repository-Aufbau mit dem dokumentierten Verfahren unter [Build und Tests](Build-und-Tests.md).
5. Beurteile den separat benötigten Engine-Bestand nach dessen eigenem Katalog.

## Erwartetes Ergebnis

Ein nachvollziehbarer Vergleich zeigt, welche Quellen zu einem Stand gehören und welche Dateien bewusst separat bereitgestellt werden. Er vermeidet, fehlende Nutzdaten als Quellfehler oder ein kleines Quellarchiv als unvollständige Runtime zu interpretieren. Umgekehrt darf ein korrektes Quellmanifest nicht als Nachweis einer vollständigen Runtime-Lieferung dienen.

## Bei Abweichungen

Prüfe zunächst, ob Manifest und Dateien zum gleichen Commit gehören. Kläre danach, ob der fragliche Inhalt zum Quellpaket, zu Engines oder zu persistenten Nutzdaten zählt. Ergänze keine privaten Modelle oder lokale Konfiguration, um Größenunterschiede auszugleichen. Eine abweichende Datei braucht eine nachvollziehbare Herkunft und Versionszuordnung.

Das [Studio-Repository](https://github.com/Taracraft/3D-Ultimate-Center) zeigt den übergeordneten Projektzusammenhang. Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) beschreibt den Einsatz der Komponenten. Für die tatsächlich benötigten Engine-Dateien ist [Engine-Pakete](Engine-Bestand.md) der passende nächste Schritt; für die verfügbaren Laufzeitbestandteile der [Entwicklungsstand](Entwicklungsstand.md).
