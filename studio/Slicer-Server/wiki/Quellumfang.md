# Quellumfang und Repository

Das separate Slicer-Repo ist die vollständige versionierte Komponentenauslieferung,
nicht länger nur das historische kleine Testarchiv. Es enthält alle vom nativen
und Docker-Paketbauer benötigten Quellen und die zugehörigen Komponententests.

Die ausführliche Dateigruppen-/Ausschluss-/Aktualisierungsbeschreibung steht in
[REPOSITORY_CONTENTS.md](../REPOSITORY_CONTENTS.md). Die Manifestprüfung lautet
ab Wurzel des eigenständigen Repos:

```bash
python3 Slicer-Server/build_repository.py --verify .
```

Modelle, Aufträge, aktive Secrets und Laufdaten werden privat gesichert, nicht
in Git veröffentlicht. Engine-Binärdateien sind separate lizenz- und
herkunftsgebundene Lieferartefakte. [Engine-Bestand](Engine-Bestand.md).
