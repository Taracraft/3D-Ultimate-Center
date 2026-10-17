# Profile und Engines

Profile bestimmen gemeinsam mit der ausgewählten Engine die Slicing-Parameter. Drucker, Düse, Filament, Prozess und Druckplatte müssen zueinander und zur tatsächlichen Hardware passen. Die Verfügbarkeit eines Profilnamens genügt dafür nicht: Entscheidend sind die konkreten Werte und die verwendete Engine-Version.

## Voraussetzungen

Bambu Studio, PrusaSlicer und CuraEngine verwenden unterschiedliche Ressourcen und Profilformate. Engine-Dateien und Profile sind daher als zusammengehöriger Bestand zu behandeln. Der Paketkatalog bindet ein Paket an feste Versions- und Dateiwerte. Fehlende Engine-Familien oder beschädigte Archive verhindern die gemeinsame Paketbildung.

Vor einer Verarbeitung müssen die benötigte Engine und ihre Ressourcen vollständig vorhanden sein. Die schreibgeschützte Einbindung von Profilen in den Worker schützt die Laufzeit vor unbeabsichtigten Änderungen; die dauerhafte Profilablage muss trotzdem gezielt verwaltet und gesichert werden. Maßgeblich sind der [Engine-Katalog](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/ENGINE_CATALOG.md) und die [persistente Profilablage](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/PERSISTENT_PROFILES.md).

## Auswahl prüfen

1. Bestimme die Engine und den konkreten Engine-Stand für den Auftrag.
2. Gleiche das Druckerprofil mit dem verwendeten Drucker ab.
3. Prüfe Düsengröße, Material, Prozesswerte und Druckplatte als zusammenhängende Auswahl.
4. Kontrolliere, ob die benötigten Ressourcen und Profile in der vorgesehenen Laufzeitablage liegen.
5. Bewerte das tatsächliche Slicing-Ergebnis; übertrage eine erfolgreiche Verarbeitung nicht pauschal auf andere Kombinationen.

## Erwartetes Ergebnis

Eine nachvollziehbare Prüfung nennt Engine-Version und konkrete Profilkombination. Sie zeigt, dass der Auftrag mit genau diesem Bestand verarbeitet wurde. Sie bestätigt nicht automatisch sämtliche Düsen, Materialien oder Platten. Für andere Kombinationen sind passende eigene Nachweise erforderlich.

## Wenn eine Kombination nicht funktioniert

Unterscheide fehlende Dateien, ungeeignete Profilwerte und ein Problem der Engine-Ausführung. Prüfe zuerst Paketidentität und Vollständigkeit, dann die Zuordnung der Profile. Eine beschädigte oder abweichende Datei wird nicht durch nachträglich geänderte Prüfsummen zu einem freigegebenen Paket. Änderungen sollten auf einen klaren Ausgangsstand zurückführbar bleiben.

Der vollständige Runtime-Download für alle drei Engine-Familien ist noch offen. Die [Engine-Paketierung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/ENGINE_DISTRIBUTION.md) beschreibt den Bereitstellungsweg. Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) ordnet die Profilwahl in den gesamten Arbeitsablauf ein; die [Fehlerdiagnose](Fehlerdiagnose.md) hilft bei gescheiterter Verarbeitung.
