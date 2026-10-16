# Repository-Aufbau

Dieses Repository enthält den Slicer-Quellcode, seine Build-Abhängigkeiten, Tests und Dokumentation. Der Slicer wird auch im Studio-Gesamtrepository unter `studio/Slicer-Server/` geführt. Die gemeinsame Verzeichnisstruktur ermöglicht dieselben relativen Imports und Buildbefehle in beiden Repositories.

## Quellverzeichnisse

`Slicer-Server/` enthält Containerdefinitionen, Engine-Verwaltung und Installationswerkzeuge. Der Server und Dispatcher liegen unter `deploy/homeassistant/host/3d-printer-slicing-server/`. Gemeinsam verwendete Geometrie- und Materialmodule liegen unter `deploy/homeassistant/custom_components/ultimate_3d_studio/`.

Die nativen Linux-Paketwerkzeuge stehen in `packages/ultimate-slicer-server/`. Tests befinden sich unter `tests/`; die Wiki-Quellen unter `Slicer-Server/wiki/`.

## Dateimanifest

`slicer-source-manifest.json` enthält Pfad, Größe und SHA-256 der Paketdateien. Mit folgendem Befehl lässt sich der lokale Bestand prüfen:

```sh
python3 Slicer-Server/build_repository.py --verify .
```

Das Manifest beschreibt den Quellbestand. Engine-Binaries, Konfiguration, Nutzermodelle und Aufträge sind nicht Teil dieses Quellpakets. Engine-Archive werden separat über den [Katalog](ENGINE_CATALOG.md) und die [Distributionswerkzeuge](ENGINE_DISTRIBUTION.md) zugeordnet.

## Änderungen

Änderungen an gemeinsam verwendeten Modulen müssen in beiden Quellzusammenstellungen funktionieren. Der Repository-Bauer erzeugt das Komponentenpaket aus einer ausdrücklichen Dateiliste und übernimmt nur dessen benötigte Abhängigkeiten.

Die Lizenzzuordnung steht in [REPOSITORY_NOTICES.md](REPOSITORY_NOTICES.md).
