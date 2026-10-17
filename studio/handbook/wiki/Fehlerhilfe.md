# Fehlerhilfe

Grenze einen Fehler zuerst auf den betroffenen Bereich ein: Modellbearbeitung, Anbieterimport, Slicing-Verbindung, Auftragsergebnis oder Kamera. So vermeidest du, dass eine fehlende Engine mit einem Importproblem verwechselt wird. Sichere einen noch nutzbaren Projektstand vor weiteren Versuchen.

## Mit der richtigen Frage beginnen

| Beobachtung | Zuerst prüfen |
| --- | --- |
| Slicing nicht verfügbar | Aktive Platte, Modelle, Profile und Serververbindung |
| Keine Schichtvorschau | Vorhandenes Ergebnis für den ausgewählten Auftrag |
| Unerwartete Materialfarbe | Auftragspalette, Materialkanal und Ansichtsmodus |
| Kamera bleibt stehen | Home-Assistant-Verbindung und Kameraquelle |
| MakerWorld liefert keine Daten | Anmeldung, Region und genaue Anbietermeldung |
| Prozesswerte wirken falsch | Profilstandard und eigene Überschreibungen |

## Eine Ursache schrittweise eingrenzen

1. Notiere die genaue Fehlermeldung sowie den letzten erfolgreichen Schritt.
2. Prüfe, ob der Fehler mit einem kleinen bekannten Modell ebenfalls auftritt.
3. Vergleiche Platte, Auftrag, Profilkombination und Serverzustand mit deiner Erwartung.
4. Ändere jeweils nur die vermutete Ursache und wiederhole den betroffenen Schritt gezielt.
5. Kontrolliere danach, ob Projekt und Materialzuordnungen vollständig erhalten sind.

Ein antwortender Server muss noch keine nutzbare Engine besitzen. Ebenso kann die CAD-Oberfläche funktionieren, während Slicing oder ein externer Anbieter nicht erreichbar ist. Trenne diese Beobachtungen im Fehlerbericht.

## Kamera prüfen

Die Kameravorschau verwendet den Home-Assistant-Kameraproxy der ausgewählten Kamera. Externe Adressen und Proxyadressen anderer Kameraentitäten werden nicht übernommen. JPEG, PNG, WebP, GIF und AVIF sind vorgesehen; SVG und übergroße Einzelbilder werden zurückgewiesen.

Bei einem stehen gebliebenen Bild prüfe zunächst die Kamera in Home Assistant und die Netzwerkverbindung. Verwende danach Aktualisieren. Bei Rückkehr zum Fenster wird die Bildabfrage erneut angestoßen. Ein weiterhin altes Bild braucht eine Prüfung des tatsächlichen Abrufs; ein sichtbares Kamerafenster allein bestätigt keine Aktualisierung.

## Einen hilfreichen Fehlerbericht erstellen

Erfasse Version beziehungsweise Build, Arbeitsbereich, auslösende Schritte, erwartetes und beobachtetes Ergebnis. Füge einen bereinigten Screenshot hinzu, wenn er das Problem erklärt. Entferne private Dateinamen, Kontodaten und Tokens aus Kameraadressen. Das erwartete Ergebnis der Diagnose ist eine reproduzierbare Eingrenzung oder eine konkrete korrigierte Einstellung. Weitere Hilfen stehen im [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md) und in der [Slicer-Fehlerdiagnose](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/wiki/Fehlerdiagnose).
