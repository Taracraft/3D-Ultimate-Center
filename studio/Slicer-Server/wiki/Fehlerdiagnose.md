# Fehlerdiagnose

Beginne eine Untersuchung bei der tatsächlich fehlgeschlagenen Handlung: Verbindung aufbauen, Paket prüfen, Auftrag verarbeiten oder einen Einrichtungszustand fortsetzen. Diese Fälle benötigen unterschiedliche Nachweise. Ein erreichbarer HTTP-Endpunkt kann gleichzeitig einen eingeschränkten Zustand wegen fehlender Engine-Dateien melden.

## Voraussetzungen für eine brauchbare Diagnose

Notiere Softwareversion, betroffene Funktion und den bereinigten Fehlertext. Ergänze die verwendete Paket- oder Image-Identität, soweit sie für den Fehler relevant ist. Verwende keine vollständigen Secrets, privaten Modelle oder unbereinigten Zugangsdaten in öffentlichen Meldungen. Die [API-Dokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/API.md) hilft, Rückmeldungen der Verbindung einzuordnen.

## Schrittweise eingrenzen

| Beobachtung | Zuerst prüfen | Danach |
| --- | --- | --- |
| Verbindung scheitert | Adresse und Zertifikatsname | TLS-Vertrauen und API-Secret |
| API antwortet, Verarbeitung fehlt | Gemeldeter Dienstzustand | Engine-Bestand und passende Profile |
| Paketprüfung schlägt fehl | Eingabedateien und zugehörige Referenz | Herkunft und konkrete Dateiauswahl |
| Einrichtung wurde unterbrochen | Tatsächlich vorhandener Zustand | Dokumentierter Abgleich und Fortsetzung |
| Verarbeitung scheitert im Worker | Engine- und Profilzuordnung | Datenzugriff und vorgesehene Berechtigungen |

Gehe nach jedem Prüfschritt zurück zur ursprünglichen Handlung und dokumentiere, was sich beobachtbar verändert hat. Passe nicht mehrere unabhängige Einstellungen gleichzeitig an; sonst lässt sich die wirksame Korrektur später kaum zuordnen.

## Erwartetes Ergebnis

Eine hilfreiche Diagnose benennt den Fehlerbereich, die geprüften Voraussetzungen und das tatsächliche Ergebnis. Sie unterscheidet einen behobenen Verbindungsfehler von einer erfolgreich ausgeführten Engine. Ein einzelner erfolgreicher Versuch wird nicht zur pauschalen Freigabe aller Funktionen oder Plattformen.

## Wenn die Ursache unklar bleibt

Verändere keine Prüfsummen, um abweichende Dateien durch eine Paketprüfung zu bringen. Lösche auch kein Einrichtungsjournal, nur um einen unklaren Vorgang neu zu starten. Sichere zunächst die nötigen bereinigten Beobachtungen und gleiche den vorhandenen Zustand mit dem vorgesehenen Ablauf ab. Bei einer Änderung an Daten oder Engine-Generationen ist zusätzlich der dokumentierte Rückweg zu beachten.

Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) beschreibt die vollständigen Arbeitsabläufe. [Betrieb und Wiederherstellung](Betrieb-und-Wiederherstellung.md) hilft bei fehlgeschlagenen Änderungen; [Engine-Pakete](Engine-Bestand.md) bei Bestandsfehlern. Vorhandene Quelltests oder Dokumentation ersetzen keine Beobachtung des konkret betroffenen Laufzeitsystems.
