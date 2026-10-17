# Erste Schritte

Mit einem kleinen Projekt lernst du den Weg durch Ultimate 3D Studio kennen: Modell laden, auf der Platte ausrichten, Material und Prozess wählen und den Arbeitsstand sichern. Verwende für den Einstieg eine einfache STL-Datei, deren erwartete Abmessungen du kennst. Alternativ kannst du einen Grundkörper einfügen.

## Vor dem Start

Die Studio-Oberfläche muss in Home Assistant eingerichtet sein. Halte Angaben zu Drucker, Düse, verwendeter Platte und Filament bereit. Für die reine Modellvorbereitung ist ein fertiges Slicing-Ergebnis noch keine Voraussetzung. Zum späteren Slicen werden zusätzlich der Ultimate Slicer Server sowie passende freigegebene Engine- und Profildateien benötigt.

## Dein erstes vorbereitetes Modell

1. Öffne das Studio und beginne mit einem neuen Projekt. Sichere zuvor einen vorhandenen Arbeitsstand.
2. Lade eine STL- oder 3MF-Datei beziehungsweise füge einen Grundkörper ein. Warte auf den Abschluss des Imports.
3. Wähle das Objekt in der Liste aus. Vergleiche Abmessungen und Orientierung mit deiner Erwartung.
4. Setze das Modell auf das Druckbett. Nutze Zentrieren oder Flach legen, wenn die ursprüngliche Ausrichtung ungeeignet ist.
5. Wähle Drucker, Düse, Filament, Prozess und Plattenoberfläche getrennt aus. Kontrolliere die tatsächliche Materialzuführung.
6. Speichere das Projekt unter einem nachvollziehbaren Namen. Überprüfe bei mehreren Platten die aktive Platte.

Du solltest anschließend ein passend dimensioniertes Modell auf der vorgesehenen Druckplatte und eine nachvollziehbare Profilkombination sehen. Die [CAD-Beispiele](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/handbook/CAD_EXAMPLES.md) helfen beim Einstieg mit mehreren Formen.

## Wenn etwas unerwartet aussieht

Ein sehr kleines oder großes Modell verlangt zuerst eine Größenkontrolle. Ändere nicht gleichzeitig Skalierung, Material und Prozess, sonst lässt sich die Ursache schwer nachvollziehen. Bei einem Importfehler lies die Meldung und kontrolliere den bisherigen Arbeitsstand. Wiederholte Importklicks sind keine zuverlässige Fehlerbehebung.

Ist der Slicer offline, bewahre das vorbereitete Projekt auf und prüfe die Verbindung separat. Nach einem späteren Slicing kontrollierst du erste Schicht, Stützen, Materialwechsel und Warnungen in der Vorschau. Modellvorbereitung und Slicing starten keinen Druck. Für den vollständigen Ablauf lies das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md) und anschließend [Vorschau und Analyse](Vorschau.md).
