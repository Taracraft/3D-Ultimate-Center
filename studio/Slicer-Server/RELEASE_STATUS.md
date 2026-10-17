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

## Versionierte Quellveroeffentlichung

Der geprüfte Quellstand wird mit den Metadaten aus [release.json](../packages/ultimate-slicer-server/release.json) als eigene Komponente veröffentlicht. Er enthält die beschriebenen Quellen, Container-/Paketierungswerkzeuge und Dokumentation. Studio besitzt eine unabhängige Integrations-/Frontendkennung. Externe Bedien-/Systemabnahmen und Testinstallationen gehören nicht zur Releasebewertung; nicht ausgeführte Prüfungen bleiben ungeprüft.

## Enginebestand in einen Image-Kontext einbinden

Die [Runtime-Kontextbrücke](RUNTIME_CONTEXT.md) verbindet einen geprüften Source-Kontext mit einer vollständigen, separat geprüften Drei-Engine-Distribution. Sie bindet die vier Eingabeprüfsummen, bewahrt Quellen- und Lizenzmetadaten und erzeugt eine Compose-Variante ohne verdeckende Engine-Binds. Die Trennung von API und Worker sowie dessen Netzwerksperre bleiben erhalten.

Das Werkzeug führt keine Engine aus und baut kein Image. Der lesende Imagechecker prüft den eingebundenen Dateibestand, keine ABI-Kompatibilität oder Betriebsfreigabe. Freigegebene Engine-Binärpakete, ein vollständiger Runtime-Download und eine installierbare Supervisor-App-Referenz werden durch diese Quellerweiterung nicht geliefert.
