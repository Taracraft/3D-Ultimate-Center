# Installation mit Docker

Diese Seite führt durch die Vorbereitung einer Docker-Installation. Sie ist keine Bestätigung, dass ein vollständiges Runtime-Paket bereits bereitsteht. Der vollständige Engine-Download ist noch offen; das vorhandene Prüfimage enthält keine Slicing-Engines und kann allein keine Modelle verarbeiten.

## Voraussetzungen

Für den beschriebenen Entwicklungsweg werden Linux/amd64, Python sowie Docker mit Compose benötigt. Hinzu kommen der vollständige Engine-Bestand, passende Profile, persistente Datenablagen, ein API-Secret und ein TLS-Zertifikat mit eingerichtetem Vertrauen. Die konkreten Dateien und Einstellungen richten sich nach der [Installation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/INSTALLATION.md) und der [Laufzeitinstallation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/RUNTIME_INSTALLATION.md).

## Vorbereitung und Ablauf

1. Wähle einen nachvollziehbaren Quellstand und halte seine Commit-ID fest. Prüfe den zugehörigen Veröffentlichungsstand sowie die tatsächlich verfügbaren Pakete.
2. Klone das Repository und erzeuge den vorgesehenen Build-Kontext nach dem [Docker-Schnellstart](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/DOCKER_QUICKSTART.md).
3. Baue das Image aus der dort festgelegten Basis. Ordne das Ergebnis dem verwendeten Quellstand zu.
4. Stelle Engine-Dateien und Profile vollständig bereit. Fehlende Engines werden nicht durch einen automatischen Download ersetzt.
5. Bereite Datenverzeichnisse, Secret und TLS-Vertrauen vor. Kontrolliere Mounts und Berechtigungen, bevor die Dienste gestartet werden.
6. Prüfe anschließend Verbindung und tatsächliche Verarbeitung getrennt. Dokumentiere Image-Identität, Engine-Bestand und das beobachtete Ergebnis.

## Erwartetes Ergebnis

Eine belastbare Installation benötigt mehr als laufende Container: Die API muss mit der vorgesehenen Authentifizierung erreichbar sein, der Worker muss die benötigten Engines und Profile lesen können, und Ergebnisse müssen in der vorgesehenen persistenten Ablage ankommen. Ein Start ohne diese Nachweise bleibt ein Teilstand.

## Wenn die Einrichtung scheitert

Ein antwortender Dienst kann einen fehlenden Engine-Bestand melden. Prüfe dann zuerst die bereitgestellten Pakete und ihre Zuordnung. Bei TLS- oder Authentifizierungsfehlern kontrolliere Adresse, Zertifikatsnamen, Vertrauen und Secret. Ändere keine Prüfsummen, um veränderte Dateien nachträglich passend zu machen. Die [Fehlerdiagnose](Fehlerdiagnose.md) beschreibt den weiteren Weg.

Bei einer vorhandenen Installation gelten vor Änderungen die [Migrationshinweise](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/MIGRATION.md). Eine Bestandsmigration ist gesondert zu planen. Den Gesamtzusammenhang beschreibt das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md).
