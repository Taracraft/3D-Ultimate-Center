# Source Import Status

Stand: 2026-10-02

## Ziel

Main soll ein vollständiger, reproduzierbarer Stand des 3D Ultimate Center V6 inklusive Slicing-Server und Home-Assistant-Integration werden.

## Bereits im Repository

- DRUCKSTUDIO_CONTINUITY.md
- REBUILD_MANIFEST.md
- .gitignore für Secrets/Runtime
- studio-v6/package.json
- studio-v6/pyproject.toml
- erste V6-Core-Dateien
- slicing-server/config.example.json
- slicing-server/native-packages.txt
- slicing-server/install-engine.sh
- deployment/systemd/*
  - 3d-printer-slicing-server.service
  - 3d-printer-slicing-dispatch.service
  - 3d-printer-slicing-dispatch.timer
  - 3d-printer-slicing-refresh.service
  - 3d-printer-slicing-refresh.timer

## Forensisch identifizierte Quellbereiche — noch vollständig zu spiegeln

### V6 Development Source
Quelle:
`/var/lib/homeassistant/homeassistant/3D-Studio/v6`

- [ ] api/ vollständig
- [ ] core/ vollständig
- [ ] frontend/ vollständig
- [ ] frontend-tests/ vollständig
- [ ] tests/ vollständig
- [ ] docs/ vollständig
- [ ] tools/ vollständig
- [ ] deploy/ vollständig
- [ ] Build-/Test-/Deploy-Skripte im Root vollständig
- [ ] package-lock.json
- [ ] tsconfig.json
- [ ] README / Changelogs / Validation Manifests

### Live Home Assistant Component
Quelle:
`/var/lib/homeassistant/homeassistant/custom_components/ultimate_3d_studio_v6`

- [ ] vollständiger aktueller Live-Stand
- [ ] network_plugin/
- [ ] manifest.json
- [ ] strings.json
- [ ] keine __pycache__ / Backups / Binärreste

### Printer Control Center
Quelle:
`/var/lib/homeassistant/homeassistant/custom_components/printer_control_center`

- [ ] vollständiger Source
- [ ] frontend/
- [ ] assets/
- [ ] translations/
- [ ] services.yaml
- [ ] Abhängigkeiten zu V6 dokumentieren

### Slicing Server HA Integration
Quelle:
`/var/lib/homeassistant/homeassistant/custom_components/printer_slicing_server`

- [ ] vollständiger Source
- [ ] frontend/
- [ ] translations/
- [ ] services.yaml

### Nativer Slicing Server
Quelle:
`/var/lib/homeassistant/3d-printer-slicing-server`

- [ ] alle aktuellen Python-Module
- [ ] server.py
- [ ] dispatch-job.sh
- [ ] refresh-state.sh
- [ ] append-slicing-journal.sh
- [ ] progress-pipe-reader.py
- [ ] Materializer
- [ ] profiles/
- [ ] config/
- [ ] web/
- [ ] Engine-/Install-/Probe-Skripte
- [ ] SHA256-/Dependency-Manifeste
- [ ] alle relevanten systemd Units
- [ ] Runtime-Daten explizit ausgeschlossen

### Home Assistant UI / Dashboard
- [ ] V6 Lovelace Dashboards exportieren
- [ ] Resources exportieren
- [ ] keine Auth-/Storage-Secrets übernehmen
- [ ] reproduzierbare Dashboard-Installationsanleitung

### Runtime / Deployment
- [ ] reale Verzeichnisstruktur dokumentieren
- [ ] Installationsskript für frische Debian-/HA-VM
- [ ] Service Enable/Start Schritte
- [ ] Healthchecks
- [ ] Rebuild-/Smoke-Test
- [ ] vollständiger E2E-Test

## Wichtige Feststellung

Die im alten V6-README beschriebenen Pfade

`/srv/3D-Studio`
und
`/mnt/homeassist-data/3D-Studio`

existieren auf dem aktuell geprüften Host nicht.

Der aktuelle reale Stand liegt unter:

- `/var/lib/homeassistant/homeassistant/3D-Studio/v6`
- `/var/lib/homeassistant/3d-printer-slicing-server`
- `/var/lib/homeassistant/homeassistant/custom_components/...`

Die spätere Rebuild-Dokumentation muss den realen Ist-Stand abbilden.

## Definition für „fertig“

Dieses Dokument ist erst abgeschlossen, wenn jeder Haken gesetzt ist und ein frischer Neuaufbau ausschließlich aus dem GitHub-Repository erfolgreich getestet wurde.
