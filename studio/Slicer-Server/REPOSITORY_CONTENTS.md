# Vollständiger Slicer-Quellumfang

## Zuständigkeit und Repositories

`Taracraft/3D-Ultimate-Center` enthält das Studio-Gesamtprodukt mit HA-Integration
und Frontend. `Taracraft/3D-Ultimate-Slicer-Server` ist das eigenständige private
Auslieferungsrepo des Slicer-Dienstes. Es ersetzt dort den früheren Status als
kleine reine Testpaket-Übergabe. Die Sichtbarkeit bleibt unverändert.

Die kanonischen Entwicklungsquellen werden weiterhin zusammen gepflegt.
`build_repository.py` definiert die exakte Komponentenprojektion. Änderungen
werden an der kanonischen Quelle umgesetzt, geprüft und anschließend erneut
projiziert. Keine manuell auseinanderlaufenden zweiten Worker-Dateien pflegen.

## Enthaltene Abhängigkeiten

| Baum | Grund für die Aufnahme |
| --- | --- |
| `Slicer-Server/` | Vollständige Slicer-Komponente: Laufzeit, Docker, Installationsverträge, Engine-Verwaltung, Dokumentation, Wiki, Provenienz und Offline-Profilquellen |
| `packages/ultimate-slicer-server/` | Native Paketbauer, Root-Installer, Testkit, manuelle Linux-Prüfung und fünf eigene Units |
| `deploy/homeassistant/host/3d-printer-slicing-server/` | Originale API-/Worker-Quellen, Maschinenprofile, Hashlisten und historische Host-Servicequellen |
| Zehn Dateien unter `deploy/homeassistant/custom_components/ultimate_3d_studio/` | Tatsächlich benötigte Worker-Helfer laut Kontext-/Paketbauer, keine vollständige zweite HA-Integration |
| `tests/` | Alle ausgewählten Komponententests samt untereinander verwendeten Testhelfern und manuellen Linux-/TLS-Prüfwerkzeugen |
| Root-Dateien und Workflow | Lesbarer Einstieg, Lizenzabgrenzung, gepinnte Test-Abhängigkeiten, CI und Byte-erhaltende Git-Attribute |

Die historischen Host-Units bleiben Quellen für die Herkunftsprüfung. Der native
Paketbauer liefert stattdessen seine eigenen fünf `ultimate-slicer-*`-Units aus;
er installiert keine historischen standortspezifischen HA-Dienste.

## Nicht enthalten – und weshalb

- Keine Modelle, Uploads, privaten Projekte, Jobs, Ergebnisse oder Logs.
- Keine aktiven `config.json`, API-Secrets, TLS-Schlüssel oder HA-Zugangsdaten.
- Keine privaten Daten-/Lauf-/Validierungsverzeichnisse und keine Hostbackups.
- Keine unkontrollierte Kopie der installierten AppImages, ELF-Bibliotheken
  oder Debian-Paketdatenbanken in den Git-Verlauf.
- Kein zweites Frontend und keine unabhängige Kopie der gesamten HA-Integration.
  Die Studio-Oberfläche bleibt im Produktrepo.

Diese Grenzen vermeiden nicht nur unnötige Größe, sondern trennen auslieferbare
Programmquellen von installationsspezifischem Zustand. Für einen vollständigen
Betriebs-Restore wird zusätzlich eine private, getestete Datensicherung gebraucht.

## Prüfen und erneut erzeugen

Ab Wurzel des Slicer-Repos:

```bash
python3 Slicer-Server/build_repository.py --verify .
```

Für die Auslieferung aus dem kanonischen Studio-Quellbaum:

```bash
SLICER_SOURCE_PARENT="$(mktemp -d /tmp/ultimate-slicer-source-XXXXXX)"
python3 Slicer-Server/build_repository.py --source-root "$PWD" \
  --output "$SLICER_SOURCE_PARENT/repository"
```

Der Generator lehnt existierende Ziele, relative Ausgabeziele, Ziele innerhalb
des Quellbaums sowie verlinkte, fehlende oder zu große Quellen ab. Das Manifest
enthält alle aktuellen Lieferdateien mit ursprünglichem Quellpfad, Bytezahl,
Modus und SHA-256. Es wird selbst über den Git-Commit identifiziert. Ein Hash
beweist Integrität relativ zu diesem Stand, nicht allein dessen Vertrauenswürdigkeit.

Die frühere Testpaket-Historie wird nicht gelöscht. Ihr Archiv ist kein Ersatz
für die aktuelle Zusammenstellung. Im Konflikt gelten aktuelle Quellen,
Manifest und zugehörige CI des jeweiligen Commits.
