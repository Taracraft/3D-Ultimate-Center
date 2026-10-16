# Installation mit Docker

Für die Entwicklung werden Linux/amd64, Python sowie Docker mit Compose benötigt. Der vollständige Enginebestand muss separat bereitgestellt werden; das Prüfimage allein kann nicht slicen.

1. Das Repository klonen und den [Build-Kontext](../DOCKER_QUICKSTART.md) erstellen.
2. Das Image aus der festgelegten Basis bauen.
3. Daten, Profile, Engine-Dateien, API-Secret und TLS-Zertifikat vorbereiten.
4. Die [Laufzeitkonfiguration](../RUNTIME_INSTALLATION.md) prüfen, bevor Dienste gestartet werden.

Beim Wechsel einer vorhandenen Installation zuerst die [Migrationshinweise](../MIGRATION.md) beachten. Eine fehlende Engine wird nicht durch einen automatischen Download ersetzt.
