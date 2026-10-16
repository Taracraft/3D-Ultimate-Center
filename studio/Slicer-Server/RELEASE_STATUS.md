# Entwicklungsstand

Ultimate Slicer Server befindet sich in Entwicklung. Der Quellcode für API, Worker, Containerbau, Engine-Verwaltung und Home-Assistant-Anbindung ist verfügbar. Ein vollständiges installierbares Laufzeitpaket mit den vorgesehenen Slicing-Engines ist noch nicht veröffentlicht.

## Verfügbare Komponenten

- HTTP-API, Jobverwaltung und getrennte Worker-Prozesse.
- Dockerfile, Compose-Konfiguration und Werkzeuge für einen definierten Build-Kontext.
- Engine-Katalog, Archivprüfung, Paketierung und Generationsverwaltung.
- Home-Assistant-Einrichtung mit externem Serverpfad und Supervisor-Verwaltung.
- Automatisierte Tests für Geometrie, Jobabläufe, Speicher und Schnittstellen.

## Einschränkungen

Das Source-Preflight-Image enthält keine Engine-Binaries. Es prüft Dateien und Abhängigkeiten, ist aber kein vollständiges Runtime-Image. Für Slicing werden zusätzlich passende Engine-Dateien, Profile, Ressourcen und Bibliotheken benötigt.

Der ausgelieferte Engine-Katalog enthält noch keine freigegebenen Pakete. Auch für die Supervisor-App ist noch keine freigegebene Paketreferenz hinterlegt. Bis zur vollständigen Paketbereitstellung bleiben die entsprechenden Installationsaktionen gesperrt.

Die aktuellen Quellen zielen auf Linux/amd64. Unterstützung weiterer Architekturen hängt von den verfügbaren Engine- und Bibliothekspaketen ab.

## Builds und Veröffentlichungen

Ein erfolgreicher Quelltest oder Imagebau ersetzt kein installierbares Paket. Verfügbare Downloads werden auf der [Release-Seite](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases) mit Version, Inhalt und Prüfsummen beschrieben.

Technische Metadaten wie `release_complete=false` oder `production_approved=false` geben den Umfang der jeweiligen Paketprüfung an. Sie werden nicht durch eine Änderung dieser Dokumentation aufgehoben.

[Installation](INSTALLATION.md) · [Docker](DOCKER_QUICKSTART.md) · [Engine-Pakete](ENGINE_DISTRIBUTION.md)
