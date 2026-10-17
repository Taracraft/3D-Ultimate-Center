# Ultimate Slicer Server

![Promo-Illustration](https://raw.githubusercontent.com/Taracraft/3D-Ultimate-Slicer-Server/main/assets/slicer-hero.png)

Der Ultimate Slicer Server verarbeitet Slicing-Aufträge aus Ultimate 3D Studio. Die HTTP-API nimmt Anfragen entgegen und verwaltet Aufträge; ein getrennter Worker führt die Verarbeitung aus. Engine-Dateien, Profile und Nutzdaten sind eigenständige Bestandteile. Ein vorhandener Quellcode oder ein erfolgreich gebautes Prüfimage reicht deshalb für einen nutzbaren Slicing-Dienst noch nicht aus.

**Aktueller Lieferstand:** Programmquellen und Paketwerkzeuge sind veröffentlicht. Verfügbare Quellreleases und Downloads stehen unter [Veröffentlichungen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases). Die [Versionsmetadaten](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/packages/ultimate-slicer-server/release.json) beschreiben den Quellstand im Hauptzweig; dieser kann vom letzten Release abweichen. Der vollständige Runtime-Download mit Bambu Studio, PrusaSlicer und CuraEngine steht weiterhin aus. Die Supervisor-App bietet weiterhin kein freigegebenes Installationspaket an. Die [Entwicklungsübersicht](Entwicklungsstand.md) erläutert diese Liefergrenzen.

## Dein Einstieg

| Rolle | Empfohlener Lesepfad | Ziel |
| --- | --- | --- |
| Anwender | [Home Assistant](Home-Assistant.md) → [Profile und Engines](Profile-und-Engines.md) → [Fehlerdiagnose](Fehlerdiagnose.md) | Verbindung, Voraussetzungen und Fehler einordnen |
| Administrator | [Docker-Installation](Docker-Installation.md) → [Architektur](Architektur.md) → [Betrieb und Wiederherstellung](Betrieb-und-Wiederherstellung.md) | Eine Installation vorbereiten und ihren Betrieb planen |
| Entwickler | [Quellumfang](Quellumfang.md) → [Build und Tests](Build-und-Tests.md) → [Entwicklungsstand](Entwicklungsstand.md) | Quellen, Prüfungen und Auslieferung zusammenführen |

## Vor dem ersten Auftrag

Für den Betrieb müssen Anwendung, Engine-Paket, passende Profile und Laufzeitkonfiguration zusammenpassen. Prüfe deshalb zuerst den Veröffentlichungsstand und die konkret verfügbaren Pakete. Bereite anschließend Datenablagen, Zugangsdaten und das TLS-Vertrauen nach der Installationsanleitung vor. Erst eine eingerichtete Verbindung mit tatsächlich verfügbarer Engine ermöglicht die Prüfung eines Slicing-Auftrags.

Das erwartete Ergebnis dieser Vorbereitung ist eine nachvollziehbare Zusammenstellung aus Softwareversion, Engine-Bestand und Konfiguration. Ein erreichbarer HTTP-Endpunkt ist dabei nur ein Teilnachweis: Der Dienst kann antworten, während die für die Verarbeitung nötigen Dateien fehlen. In diesem Fall führt der nächste Schritt zur [Engine-Bestandsprüfung](Engine-Bestand.md), nicht zur Annahme einer fertigen Installation.

Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) ist der zentrale Einstieg für zusammenhängende Arbeitsabläufe. Die [API-Dokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/API.md) richtet sich an Integrationen. Prüfe vor einer Änderung einer bestehenden Installation die dokumentierten Voraussetzungen, Sicherungen und den vorgesehenen Rückweg.
