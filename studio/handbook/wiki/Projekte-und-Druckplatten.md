# Projekte und Druckplatten

Ein Projekt hält Modelle, Materialzuordnungen und Einstellungen zusammen. Druckplatten teilen diesen Arbeitsstand in getrennte Vorbereitungsbereiche. Damit kannst du beispielsweise mehrere Bauteile in einem Projekt verwalten und trotzdem nur die aktuell ausgewählte Platte für einen bestimmten Auftrag vorbereiten.

## Vorbereiten und sichern

Gib wichtigen Objekten und Projekten eindeutige Namen. Prüfe vor größeren Änderungen, ob die richtige Platte aktiv ist. Sichere einen Arbeitsstand vor einem neuen Import, einer umfangreichen Bemalung oder einer Änderung der Materialkanäle. Eine gespeicherte Projektdatei erleichtert die Weiterarbeit; eine reine Modell-STL enthält dafür nicht denselben Projektkontext.

## Ein Projekt sinnvoll aufteilen

1. Lade oder erstelle die benötigten Modelle auf der ersten Platte.
2. Kontrolliere Größe, Orientierung und Zuordnung in der Objektliste.
3. Lege zusätzliche Platten für getrennte Druckvorgänge an. Ordne die Modelle entsprechend ihrer geplanten Verarbeitung zu.
4. Wechsle zwischen den Platten und prüfe jeweils die sichtbaren Objekte sowie die zugehörigen Materialien und Einstellungen.
5. Speichere das gesamte Projekt. Kontrolliere vor Export oder Slicing nochmals die aktive Platte und die gewünschte Auswahl.

Das erwartete Ergebnis ist eine nachvollziehbare Aufteilung: Jede Platte enthält genau die Teile, die du gemeinsam vorbereiten möchtest. Ein Plattenwechsel darf nicht mit einem Wechsel des gesamten Projekts verwechselt werden.

## Dateien öffnen und Fehler einordnen

STL und 3MF sind Eingabeformate für Modelle und zugehörige unterstützte Daten. Ein Import ist noch kein geslicter Druckauftrag. Nicht jede herstellerspezifische 3MF-Erweiterung muss automatisch unterstützt sein. Vergleiche deshalb nach dem Laden Objektanzahl, Abmessungen, Platten und Materialzuordnungen mit der Quelldatei.

Der Importweg bereitet neue Inhalte vor ihrer Übernahme vor. Scheitert er, prüfe die Fehlermeldung und den bisherigen Projektzustand, bevor du einen weiteren Versuch startest. Bei unerwartetem Objektverlust arbeite mit der zuletzt gesicherten Projektkopie weiter und dokumentiere Dateiformat und auslösenden Schritt. Überschreibe diese Sicherung nicht mit dem fehlerhaften Ergebnis.

Weitere Hinweise zu Projektformaten und zum Export enthält das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md). Für Dateien aus dem Modellbestand und für Anbieterimporte lies [Galerie und MakerWorld](Galerie-und-MakerWorld.md).
