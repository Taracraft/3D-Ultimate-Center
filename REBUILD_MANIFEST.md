# Rebuild Manifest — 3D Ultimate Center V6

Stand: 2026-10-02

## Ziel

Dieses Repository soll so vollständig werden, dass das gesamte 3D Ultimate Center V6 einschließlich Home-Assistant-Integration und Slicing-Server aus dem Repository neu aufgebaut werden kann.

Der aktuelle Quellstand wurde auf der Home-Assistant-VM forensisch inventarisiert. Der Tara-PC ist aktuell nicht verfügbar; deshalb ist die Home-Assistant-VM derzeit die wichtigste Live-Quelle.

## Gefundene kanonische Quellen auf der Home-Assistant-VM

### V6 Entwicklungsbaum

```text
/var/lib/homeassistant/homeassistant/3D-Studio/v6
```

Enthält u. a.:

- `api/`
- `core/`
- `frontend/`
- `frontend-tests/`
- `tests/`
- `deploy/`
- `docs/`
- `tools/`
- `package.json`
- `package-lock.json`
- `pyproject.toml`
- `tsconfig.json`
- Build-/Test-/Deploy-Skripte
- Release-/Validierungsdokumente

Nicht als Quellbestand übernehmen:

- `node_modules/`
- `__pycache__/`
- `.pytest_cache/`
- `.test-build/`
- `.test-results/`
- alte ZIP/TAR-Artefakte
- temporäre Marker
- Backups als primären Source-Stand

### Live Home-Assistant Custom Component: Ultimate 3D Studio V6

```text
/var/lib/homeassistant/homeassistant/custom_components/ultimate_3d_studio_v6
```

Diese Live-Kopie ist wichtig, weil sie neuer sein kann als der V6-`deploy/`-Snapshot.

Enthält u. a.:

- Bambu LAN/Cloud Provider
- AMS-/Filamentlogik
- Druckprofile
- MakerWorld
- Gallery
- Slicing-Router
- Direct Print
- G-Code-Analyse
- Printer Storage
- Telemetrie
- Kamera
- Audit
- Netzwerkplugin
- 3MF-Verarbeitung

### Legacy/ergänzende Integration: Printer Control Center

```text
/var/lib/homeassistant/homeassistant/custom_components/printer_control_center
```

Enthält u. a.:

- MQTT Client
- Bambu Standalone Provider
- WebSocket/API
- Queue
- Archive Browser
- Model Export
- Studio Worker/Jobs/Profile
- Frontend

Diese Integration muss vor einer späteren Bereinigung gegen V6 geprüft werden, damit keine produktive Funktion verloren geht.

### Home-Assistant Integration für den Slicing-Server

```text
/var/lib/homeassistant/homeassistant/custom_components/printer_slicing_server
```

Enthält:

- API
- WebSocket API
- Sensor/Binary Sensor
- Config Flow
- Services
- Frontend Panel

### Nativer Slicing-Server

```text
/var/lib/homeassistant/3d-printer-slicing-server
```

Der produktive Slicing-Server ist eine eigenständige Python-/Shell-Anwendung und muss vollständig rekonstruktionsfähig ins Repository.

Wichtige Dateien:

- `server.py`
- `dispatch-job.sh`
- `refresh-state.sh`
- `append-slicing-journal.sh`
- `progress-pipe-reader.py`
- `materialize-bambu-machine.py`
- `materialize-bambu-multimaterial.py`
- `three_mf_mesh_graph.py`
- Python-Module für Upload, Gallery, Mesh, Slicing, Queue, Projekte, MakerWorld etc.
- `profiles/`
- `config/`
- `web/`
- `engines/`
- Systemd-Units
- `DEPENDENCY-SHA256SUMS`
- `SHA256SUMS`
- `native-packages.txt`
- Install-/Probe-Skripte

Nicht übernehmen:

- `data/uploads/`
- `data/output/`
- `run/`
- `__pycache__/`
- Laufzeitlogs
- alte Backups als kanonischen Stand

## Produktive Slicing-Konfiguration

Aktuelle Konfiguration:

```json
{
  "host": "127.0.0.1",
  "port": 8099,
  "token": "",
  "data_dir": "/var/lib/homeassistant/3d-printer-slicing-server/data",
  "slicer_paths": [
    "/usr/bin/PrusaSlicer",
    "/usr/bin/prusa-slicer",
    "/usr/bin/OrcaSlicer",
    "/usr/local/bin/OrcaSlicer",
    "/usr/bin/CuraEngine"
  ]
}
```

Im Repository soll daraus eine `config.example.json` entstehen. Produktive Tokens dürfen nicht committed werden.

## Systemd

### 3d-printer-slicing-server.service

```ini
[Unit]
Description=3D-Printer Slicing Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /var/lib/homeassistant/3d-printer-slicing-server/server.py /var/lib/homeassistant/3d-printer-slicing-server/config.json
WorkingDirectory=/var/lib/homeassistant/3d-printer-slicing-server
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

### Dispatcher

```ini
[Unit]
Description=3D-Printer Slicing Server Universal Dispatcher
After=network-online.target 3d-printer-slicing-server.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/sh /var/lib/homeassistant/3d-printer-slicing-server/dispatch-job.sh
```

### Refresh

```ini
[Unit]
Description=Dispatch and refresh 3D-Printer Slicing Server state
After=network-online.target 3d-printer-slicing-server.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/sh /var/lib/homeassistant/3d-printer-slicing-server/dispatch-job.sh
ExecStart=/bin/sh /var/lib/homeassistant/3d-printer-slicing-server/refresh-state.sh
ExecStart=/bin/sh /var/lib/homeassistant/3d-printer-slicing-server/append-slicing-journal.sh
```

Timer:

- Dispatcher: 10 s
- Refresh: 15 s

## Build-Abhängigkeiten V6

### Node

Auf dem aktuellen Homeassist-Host:

```text
Node.js v20.19.2
```

`package.json` fordert Node >= 20.

Frontend-Paket:

```text
ultimate-3d-printing-studio-v6-frontend
Version 6.0.0-beta3
```

Dev Dependencies:

- esbuild ^0.25.0
- typescript ^5.9.3

Scripts:

- `npm run typecheck`
- `npm run build`
- `npm test`

### Python

Aktueller Host:

```text
Python 3.13.5
```

V6 `pyproject.toml`:

- Python >= 3.12
- aiohttp >= 3.11,<4
- Test: pytest >= 8.3
- Test: pytest-asyncio >= 0.25

## Architektur laut V6-README

Produktoberflächen:

- Control Center
- Gallery
- CAD Studio
- Slicer Preview
- Profiles
- Print Queue
- Print History
- System / Provider Diagnostics

Grundprinzipien:

- kanonischer State je Domain
- immutable Frontend-State-Transitions
- Rendering aus State
- persistente Jobs
- versionierte API
- providerneutrales Slicing
- content-addressed Assets
- stabile IDs
- Deployment nur nach Tests/Gates

## Wichtige Abweichung von alter Dokumentation

Das V6-README beschreibt als persistenten Runtime-Root:

```text
/srv/3D-Studio
/mnt/homeassist-data/3D-Studio
```

Diese Pfade existieren auf dem aktuell geprüften Host **nicht**.

Der tatsächlich gefundene Entwicklungs-/Livebaum liegt unter:

```text
/var/lib/homeassistant/homeassistant/3D-Studio
```

und der produktive Slicing-Server unter:

```text
/var/lib/homeassistant/3d-printer-slicing-server
```

Das Rebuild-/Deploy-Konzept muss daher auf den realen Ist-Stand korrigiert werden.

## Bereits erkannte Slicing-Probleme

- `dispatch-job.sh: 1: #!/bin/sh: not found`
- gelegentlich fehlende `diagnostics.json.tmp`
- Cloud MQTT im Printer Control Center: `Not authorized`

Diese Punkte sind nicht Bestandteil des Rebuild-Imports, müssen aber im späteren Verifikationslauf adressiert werden.

## Was zwingend in dieses Repository übernommen werden muss

1. vollständiger V6-Source aus `3D-Studio/v6`
2. live `ultimate_3d_studio_v6`
3. `printer_control_center`, solange Abhängigkeiten nicht vollständig eliminiert sind
4. `printer_slicing_server` HA-Komponente
5. kompletter nativer Slicing-Server ohne Runtime-Daten
6. Profile und Maschinen-/Materialdefinitionen
7. Systemd-Units
8. Install-/Deploy-Skripte
9. Build-/Testskripte
10. Dashboard-/Lovelace-Definitionen in bereinigter Form
11. Rebuild-/Install-Dokumentation
12. `.env.example` / `config.example.json`
13. Dependency-Versionen und Hashes
14. Test-/Gate-Definitionen
15. `LIVE_WORKLOG.md`

## Geheimnisse und Laufzeitdaten

Dieses Repo ist öffentlich. Nicht committen:

- Home-Assistant Tokens
- Bambu Access-/Refresh-Tokens
- Drucker Access Codes
- MQTT Credentials
- Keycloak Secrets
- MCP Tokens
- Session Cookies
- private Schlüssel
- reale `.storage`-Authdaten
- Upload-/Output-Laufzeitdaten

## Status der Wiederherstellbarkeit

Aktuell:

- Projektwissen gesichert: JA
- Live-Quellorte identifiziert: JA
- V6 Build-Abhängigkeiten identifiziert: JA
- Slicing-Systemd identifiziert: JA
- Slicing-Konfiguration identifiziert: JA
- Home-Assistant Komponenten identifiziert: JA
- kompletter Source bereits im GitHub-Repo: NOCH NICHT
- vollständiges One-Command-Rebuild: NOCH NICHT

Diese Datei ist die verbindliche Checkliste, bis jeder Punkt vollständig ins Repository übernommen und auf einer frischen Maschine verifiziert wurde.
