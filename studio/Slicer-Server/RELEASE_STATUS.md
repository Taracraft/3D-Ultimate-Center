# Entwicklungsstand

**Docker-Lieferung vom 18.10.2026:** Das vorhandene Linux/amd64-Runtime-Image mit Bambu Studio, PrusaSlicer und CuraEngine ist unter [v0.1.0-alpha10](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/tag/v0.1.0-alpha10) veröffentlicht. [Installation und genaue Versionszuordnung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/RUNTIME_RELEASE_README.md), [Prüfsummen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/SHA256SUMS) und zugehörige Quellen/Lizenznachweise gehören zur Lieferung. Das dokumentierte Expat-Restrisiko ist für diesen Kandidaten akzeptiert, technisch aber nicht behoben; siehe [Risikodokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/EXPAT_RISK_ACCEPTANCE.json).

Studio wird unabhängig als HACS-Integration 6.0.5 ausgeliefert. Die Slicer-Quellen tragen alpha10; das unveränderte Runtime-Image enthält API-Metadaten alpha9. Image-ID: `sha256:cb37fa6b9aee8c40035a5f337a67d9fc13c4429e06098024731e556f8e8bfb49`. Es wurde dafür kein identischer Neubau vorgenommen. Externe Installations-, UI- und Pilotprüfungen bleiben `not_run` und sind keine zusätzlichen Releasegates. Eine Gesamtfertigstellung wird daraus nicht abgeleitet.

## Veröffentlichte Docker-Lieferung

Alle 24 Release-Dateien einschließlich Image, Enginearchiven, zugehörigen Quellen, Lizenzhinweisen und SHA256SUMS wurden öffentlich vollständig zurückgelesen und gegen ihre Prüfsummen geprüft. Für den manuellen Docker-Einstieg gilt die [Runtime-Anleitung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/RUNTIME_RELEASE_README.md). Die Runtime enthält alle drei Enginefamilien und ihre Laufzeitbibliotheken. Quellenversion und eingebettete API-Version werden dort ausdrücklich getrennt ausgewiesen.

## Getrennte Quell- und Paketwege

Das Source-Preflight-Image enthält weiterhin keine Engine-Binaries. Es prüft Quellen und ist vom vollständigen Runtime-Image zu unterscheiden. Der leere Quell-Auswahlkatalog bleibt dem separaten Paket-/Installerweg zugeordnet; für die Docker-Runtime gilt der imagegebundene Release-Katalog.

Eine freigegebene Supervisor-App-Paketreferenz ist noch nicht veröffentlicht. Die native Installation bleibt durch `native_deploy_ready=false` gesperrt. Historische Quellmanifestfelder wie `release_complete=false` oder `production_approved=false` beschreiben den jeweiligen Prüfvertrag und werden nicht durch eine Änderung dieser Dokumentation aufgehoben. Sie sind keine zusätzlichen Freigabeschalter für den hier belegten Docker-Download.

## Prüfgrenzen und Updates

Linux/amd64 ist der gelieferte Umfang. Weitere Architekturen sind nicht zugesagt. Externe Installation, Cross-Host-TLS, UI/iPhone, echte Slices und Pilotprüfungen werden durch die Downloadprüfung nicht bestätigt. Ausstehende Prüfungen bleiben als `not_run` dokumentiert und werden nicht zu neuen Releasegates oder fehlender Implementierung umgedeutet. Die Matrix umfasst weiterhin 118 Zeilen.

Die Expat-Entscheidung ist eine Annahme des dokumentierten Restrisikos für genau diesen Runtimekandidaten. Sie bedeutet weder Risikofreiheit noch eine Sicherheitskorrektur. Spätere belegte Korrekturen können über eine neue geprüfte Engine-/Runtime-Lieferung integriert werden; vorhandene Images, Prüfsummen und Rückwege bleiben erhalten.

[Installation](INSTALLATION.md) · [Docker-Quellweg](DOCKER_QUICKSTART.md) · [Engine-Pakete](ENGINE_DISTRIBUTION.md)
