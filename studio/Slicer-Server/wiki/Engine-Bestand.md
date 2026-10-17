# Engine-Pakete

Engine-Dateien werden getrennt vom Programmquellcode verteilt. Ein vollständiges Paket umfasst den Programmeinstieg, benötigte Bibliotheken, Ressourcen, Profile und Lizenztexte. Eine einzelne ausführbare Datei oder ein großer Archivumfang belegt deshalb noch keinen nutzbaren und vollständig dokumentierten Engine-Bestand.

## Voraussetzungen

Der [Engine-Katalog](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/ENGINE_CATALOG.md) beschreibt die erwarteten Dateien. Die [Distributionswerkzeuge](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/ENGINE_DISTRIBUTION.md) stellen den Bestand aus lokalen Archiven zusammen. Herkunft und Quellversionen werden über die [Engine-Provenienz](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/ENGINE_PROVENANCE.md) zugeordnet.

Für Bambu Studio, PrusaSlicer und CuraEngine sind noch keine vollständigen Runtime-Downloads veröffentlicht. Vorhandene Inventare, Archive und Paketwerkzeuge dürfen daher nicht als fertiger öffentlicher Runtime-Download beschrieben werden.

## Einen Bestand nachvollziehbar zusammenstellen

1. Ordne jedes Ausgangsarchiv seiner Engine, Version und Herkunft zu.
2. Vergleiche den Inhalt mit der konkreten Dateiauswahl im Katalog. Berücksichtige Bibliotheken, Ressourcen und Profile ebenso wie den Programmeinstieg.
3. Prüfe die vorgesehenen Paketidentitäten und die zugehörigen Herkunftsangaben.
4. Ergänze die notwendigen Lizenz- und gegebenenfalls Quelltexte für die tatsächlichen Komponenten.
5. Halte Paketprüfung und tatsächliche Engine-Ausführung als unterschiedliche Nachweise fest.

## Erwartetes Ergebnis

Ein belastbarer Paketbestand lässt sich auf seine Eingabedateien, Versionen und zugehörigen Nachweise zurückführen. Für eine Auslieferung muss zusätzlich feststehen, welche Dateien tatsächlich verteilt werden und welche Bedingungen für sie gelten. Ein Hash bestätigt nur die Identität einer Datei gegenüber einer Referenz; er entscheidet keine Lizenzfrage und beweist keine Funktionsfähigkeit.

## Bei fehlenden oder abweichenden Dateien

Stoppe die gemeinsame Paketbildung, wenn eine erforderliche Engine-Familie fehlt oder ein Archiv beschädigt ist. Kläre die passende Referenz und das richtige Ausgangsarchiv. Eine fehlgeschlagene Prüfung darf nicht durch Anpassung der Prüfsumme an einen unklaren Bestand umgangen werden. Auch eine erfolgreiche Paketprüfung ersetzt den Funktionsnachweis mit dem vorgesehenen Laufzeitpaket nicht.

Die Auswahl für einen Auftrag erläutert [Profile und Engines](Profile-und-Engines.md). Den Zusammenhang mit Installation und Betrieb beschreibt das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md). Der [Entwicklungsstand](Entwicklungsstand.md) hilft, vorhandene Paketwerkzeuge und tatsächlich verfügbare Runtime-Downloads auseinanderzuhalten.
