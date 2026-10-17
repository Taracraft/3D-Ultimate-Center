# Betrieb und Wiederherstellung

Konfiguration, Profile, Aufträge und Ergebnisse liegen in getrennten persistenten Verzeichnissen. Sie müssen einen Containerneustart überstehen und dürfen beim Austausch des Images nicht versehentlich verloren gehen. Engine-Generationen und Anwendungsdaten haben unterschiedliche Aufgaben und sind bei Sicherung und Wiederherstellung getrennt zu betrachten.

## Voraussetzungen

Vor einer Änderung müssen der laufende Versionsstand, die verwendete Engine-Generation und die Datenablagen bekannt sein. Für einen Rückweg braucht es eine passende Sicherung und die zugehörigen Versions- und Datenformate. Ein altes Image allein ist keine vollständige Wiederherstellung, wenn Konfiguration oder Nutzdaten nicht dazu passen.

## Update vorbereiten und durchführen

1. Halte den Ausgangsstand einschließlich Anwendung, Image und Engine-Generation fest.
2. Pausiere die Verarbeitung, bevor die für das Update vorgesehenen Änderungen beginnen.
3. Sichere Konfiguration und Nutzdaten nach dem dokumentierten Verfahren. Beziehe die dauerhafte Profilablage ein.
4. Prüfe, wie die neue Engine-Generation und die Anwendung zusammenpassen und welcher Rückweg vorgesehen ist.
5. Führe die Änderung anhand der Betriebs- und Wartungsanleitung aus. Prüfe anschließend die tatsächlich erhaltenen Daten und den beobachteten Dienstzustand.

Das erwartete Ergebnis ist ein überprüfbarer neuer Stand mit erhaltenen Nutzdaten und einem weiterhin nachvollziehbaren Rückweg. Ein gestarteter Container bestätigt diese Eigenschaften noch nicht. Auch Neustart, Upgrade und Wiederherstellung sind unterschiedliche Abläufe und benötigen jeweils passende Beobachtungen.

## Wiederherstellung und Fehlerpfad

Bei einem fehlgeschlagenen Update zuerst den aktuellen Zustand feststellen und die Verarbeitung pausiert halten. Ordne Konfiguration, Daten und Engine-Generation den passenden Versionen zu. Spiele Bestandteile erst nach dieser Prüfung zurück. Ein Rückweg darf keine unklaren Datenformate verdecken oder unbemerkt eine andere Engine-Auswahl aktivieren.

Für einen Restore-Nachweis sind das wiederhergestellte Ziel und die überprüften Datei- beziehungsweise Datenidentitäten relevant. Die bloße Existenz eines Backups beweist nicht, dass sich der benötigte Zustand daraus wiederherstellen lässt.

Verbindliche Einzelheiten stehen in [Betrieb](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/OPERATIONS.md), [Wartung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/MAINTENANCE.md), [Datenhaltung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/DATA_PERSISTENCE.md) und [Generationswechsel](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/PACKAGE_ACTIVATION.md). Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) verbindet diese Verfahren. Eine bestehende produktive Installation oder ihre Migration wird durch die Vorbereitung eines Releases nicht automatisch verändert oder freigegeben.
