# CAD und Modellbearbeitung

Der CAD-Arbeitsbereich bereitet die Geometrie für eine konkrete Druckplatte vor. Die wichtigste Arbeitsregel lautet: erst die Auswahl prüfen, dann eine Transformation anwenden. Bei mehreren Objekten verhindert das, dass versehentlich eine ganze Gruppe statt eines einzelnen Teils verschoben oder skaliert wird.

## Voraussetzungen

Lade ein Modell oder füge einen Grundkörper ein. Stelle die zum Drucker passende Platte ein und sichere einen Ausgangsstand. Die Modellabmessungen sollten bekannt sein, besonders wenn die Quelldatei aus einem anderen CAD-System stammt. Materialwahl und Slicing sind nachgelagerte Schritte; eine geometrisch passende Darstellung allein bestätigt keine Druckbarkeit.

## Modelle gezielt bearbeiten

1. Wähle das gewünschte Objekt in der Objektliste. Für eine gemeinsame Bearbeitung erweitere die Auswahl mit Strg oder Umschalt.
2. Kontrolliere die Auswahl in Liste und Ansicht. Nutze Verschieben, Drehen, Skalieren oder Spiegeln für die beabsichtigte Änderung.
3. Arbeite entlang einer Achse, wenn ein Maß oder eine definierte Ausrichtung wichtig ist. Kontrolliere die Abmessungen nach dem Skalieren erneut.
4. Verwende Zentrieren, Auf Druckbett setzen oder Flach legen für eine geeignete Auflage.
5. Nutze Anordnen bei mehreren Teilen. Prüfe danach Abstände und Plattenränder; bei Platzmangel verteile die Teile auf weitere Platten.

Anordnen erhält Größe und Drehung der Modelle. Es ersetzt daher keine Prüfung, ob die gewählte Orientierung sinnvoll ist. Überlappende Teile, schwebende Flächen und aus dem Druckbereich ragende Geometrie solltest du vor dem nächsten Schritt beheben.

## Geometrie prüfen und korrigieren

Würfel, Zylinder, Kugel, Kegel, Ring und Platte dienen als direkt einfügbare Ausgangsformen. Messwerkzeuge helfen beim Vergleich von Abständen und Abmessungen. Mesh-Prüfung, Reparatur und Teilen unterstützen die Aufbereitung vorhandener Modelle. Kontrolliere das Ergebnis jeder solchen Änderung in der Ansicht und bewahre bei wichtigen Teilen eine unveränderte Projektkopie auf.

Wenn eine Bearbeitung das falsche Objekt trifft, mache den Schritt rückgängig und korrigiere die Auswahl. Verlasse den Malmodus, bevor du Modelltransformationen erwartest. Das erwartete Ergebnis ist eine bewusst angeordnete, maßhaltige Auswahl auf der richtigen Platte. Beispiele und weitere Erläuterungen findest du in [CAD-Beispiele](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/handbook/CAD_EXAMPLES.md) und im [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md).
