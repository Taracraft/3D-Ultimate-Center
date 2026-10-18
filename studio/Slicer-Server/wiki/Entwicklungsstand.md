# Entwicklungsstand

**Docker-Lieferung vom 18.10.2026:** Das vorhandene Linux/amd64-Runtime-Image mit Bambu Studio, PrusaSlicer und CuraEngine ist unter [v0.1.0-alpha10](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/tag/v0.1.0-alpha10) veröffentlicht. [Installation und genaue Versionszuordnung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/RUNTIME_RELEASE_README.md), [Prüfsummen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/SHA256SUMS) und zugehörige Quellen/Lizenznachweise gehören zur Lieferung. Das dokumentierte Expat-Restrisiko ist für diesen Kandidaten akzeptiert, technisch aber nicht behoben; siehe [Risikodokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/EXPAT_RISK_ACCEPTANCE.json).

Studio wird unabhängig als HACS-Integration 6.0.5 ausgeliefert. Die Slicer-Quellen tragen alpha10; das unveränderte Runtime-Image enthält API-Metadaten alpha9. Image-ID: `sha256:cb37fa6b9aee8c40035a5f337a67d9fc13c4429e06098024731e556f8e8bfb49`. Es wurde dafür kein identischer Neubau vorgenommen. Externe Installations-, UI- und Pilotprüfungen bleiben `not_run` und sind keine zusätzlichen Releasegates. Eine Gesamtfertigstellung wird daraus nicht abgeleitet.

## Vorhandenes und offene Nachweise

| Bereich | Einordnung |
| --- | --- |
| Programmquellen und Paketwerkzeuge | Veröffentlicht; konkrete Versionen und Downloads unter [Slicer-Veröffentlichungen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases) |
| Automatisierte Prüfungen | Nachweise für ihren jeweils konkreten Umfang |
| Prüfimage | Prüfung von Quellen und Systempaketen; keine Slicing-Engines enthalten |
| Vollständige Engine-Runtime | Linux/amd64-Docker-Image veröffentlicht; alle 24 Downloads vollständig hashgeprüft |
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

Den jeweils veröffentlichten Stand nennen die [Studio-Releases](https://github.com/Taracraft/3D-Ultimate-Center/releases) und [Slicer-Releases](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases). Die Docker-Runtime ist inzwischen veröffentlicht. Eine Supervisor-App-Paketreferenz bleibt getrennt und ist weiterhin nicht veröffentlicht. Linux-Testserver, Testinstallation und frische Neuinstallation sind seit der Entscheidung vom 17.10.2026 vollständig aus der Releasebewertung und dem Releaseabschluss ausgenommen. Ausstehende Tests bleiben ungeprüft beziehungsweise `not_run`.
