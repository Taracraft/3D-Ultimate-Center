# Entwicklungsstand

Programmquellen, Paketwerkzeuge und automatisierte Tests sind veröffentlicht. Die verfügbaren Quellreleases und Downloads stehen unter [Slicer-Veröffentlichungen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases). Die [Versionsmetadaten](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/packages/ultimate-slicer-server/release.json) beschreiben den Quellstand im Hauptzweig; dieser kann vom letzten Release abweichen. Der vollständige Runtime-Download mit Bambu Studio, PrusaSlicer und CuraEngine steht weiterhin aus. Die Supervisor-App bietet weiterhin kein freigegebenes Installationspaket an.

## Vorhandenes und offene Nachweise

| Bereich | Einordnung |
| --- | --- |
| Programmquellen und Paketwerkzeuge | Veröffentlicht; konkrete Versionen und Downloads unter [Slicer-Veröffentlichungen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases) |
| Automatisierte Prüfungen | Nachweise für ihren jeweils konkreten Umfang |
| Prüfimage | Prüfung von Quellen und Systempaketen; keine Slicing-Engines enthalten |
| Vollständige Engine-Runtime | Veröffentlichung und Freigaben weiterhin offen |
| Supervisor-App | Kein freigegebenes Installationspaket hinterlegt |
| HACS | Studio-Integration im normalen Repositorymodus; [veröffentlichte Versionen](https://github.com/Taracraft/3D-Ultimate-Center/releases) und [Quellmetadaten](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/custom_components/ultimate_3d_studio/manifest.json) getrennt prüfen; Testinstallationen separat dokumentiert |
| Vollständige Funktionsabnahmen | Noch nicht für alle beauftragten Abläufe abgeschlossen |

Die dokumentierten Werkzeuge und vorhandenen Teilprüfungen beschreiben den Entwicklungsumfang. Vollständige Funktionsabnahmen sind davon getrennt zu betrachten. Ein grüner automatisierter Prüflauf und veröffentlichte Dokumentation bestätigen für sich allein weder ein vollständiges Runtime-Paket noch eine erfolgreiche Installation.

## Den Stand für einen Einsatz prüfen

1. Lies den [Release-Status](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/RELEASE_STATUS.md) des verwendeten Quellstands.
2. Prüfe in den [Veröffentlichungen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases), welche konkreten Downloads tatsächlich vorhanden sind.
3. Ordne Anwendung, Engine-Pakete, Container und Integrations-Assets ihren Versionen zu.
4. Prüfe die benötigten Nachweise für deinen vorgesehenen Ablauf, statt einen einzelnen grünen Teiltest auf den gesamten Einsatz zu übertragen.

## Erwartetes Ergebnis und Fehlerpfad

Das Ergebnis ist eine klare Liste verfügbarer Bestandteile und noch offener Voraussetzungen. Fehlt ein erforderlicher Download, ist der dokumentierte Installationsweg an dieser Stelle noch nicht vollständig. Ein Prüfimage oder Quellarchiv ersetzt die fehlende Runtime nicht. Widersprechen sich eine ältere Anleitung und der aktuelle belegte Paketstand, muss die Abweichung vor dem nächsten Einrichtungsschritt geklärt werden.

Die [Installation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/INSTALLATION.md) benennt die benötigten Dateien und Einstellungen. Das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) verbindet die Arbeitsabläufe. Beurteile die Eignung anhand der tatsächlich verfügbaren Pakete und der dokumentierten Systemvoraussetzungen. Sichere bestehende Konfiguration und Nutzdaten, bevor du eine Änderung planst.


## Releasebewertung

**Historischer Stand vom 17.10.2026 vor den Folgepatches:** Die Veröffentlichung der Quellreleases Studio 6.0.0 und Slicer Server 0.1.0-alpha5 war abgeschlossen.

Den jeweils veröffentlichten Stand nennen die [Studio-Releases](https://github.com/Taracraft/3D-Ultimate-Center/releases) und [Slicer-Releases](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases). Die oben benannten Engine- und Supervisor-App-Pakete bleiben eigenständige offene Liefergrenzen. Linux-Testserver, Testinstallation und frische Neuinstallation sind seit der Entscheidung vom 17.10.2026 vollständig aus der Releasebewertung und dem Releaseabschluss ausgenommen. Ausstehende Tests bleiben ungeprüft beziehungsweise `not_run`.
