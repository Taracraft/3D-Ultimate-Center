# Updates und Migration

Vor einem Wechsel des Slicing-Dienstes muss klar sein, welche Anwendungsversion, Enginegeneration und Datenformate zusammengehören. Eine vorhandene Installation sollte nicht während laufender Aufträge ersetzt werden.

## Vorbereitung

Konfiguration, Profile, Jobdaten und Ergebnisse sichern. Die aktuell verwendete Image-ID und Enginegeneration notieren. Den neuen Stand zunächst mit eigenen Datenverzeichnissen prüfen; produktive Volumes nicht gleichzeitig an zwei aktive Worker anschließen.

## Umstellung

1. Neue Aufträge anhalten und den Worker kontrolliert stoppen.
2. Den gesicherten Bestand und die vorgesehenen Zielpfade prüfen.
3. Anwendung, Engine-Dateien und Profile in ihrer passenden Version bereitstellen.
4. TLS, Authentifizierung, Dateirechte und API-Kompatibilität kontrollieren.
5. Die Verbindung in Home Assistant aktualisieren und den Status prüfen.
6. Verarbeitung erst wieder freigeben, wenn Konfiguration und Datenbestand zusammenpassen.

## Rückweg

Die vorherige Image-ID und Enginegeneration bis zum Abschluss der Umstellung erhalten. Bei einem Fehler zuerst den neuen Dienst stoppen. Ein Datenrestore ist getrennt von einem Image-Rollback zu behandeln, insbesondere nach Änderungen am Datenformat. Eine ältere Anwendung darf nicht ungeprüft auf einen neueren Datenbestand zugreifen.

## Native Dienste und Compose

Die Verzeichnisse und Benutzerrechte eines nativen Dienstes unterscheiden sich von den Container-Mounts. Compose darf einen vorhandenen nativen Worker nicht versehentlich parallel starten. Der Clean-Host-Preflight meldet einen solchen Bestand, entfernt ihn aber nicht selbst.

Die vollständige Engine-/App-Veröffentlichung befindet sich noch in Entwicklung. Die verfügbaren Paketwerkzeuge und ihre Einschränkungen sind unter [Entwicklungsstand](RELEASE_STATUS.md) beschrieben.

[Betrieb](OPERATIONS.md) · [Datenhaltung](DATA_PERSISTENCE.md) · [Wartung](MAINTENANCE.md)
