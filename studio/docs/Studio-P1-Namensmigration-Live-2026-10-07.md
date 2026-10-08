# P1 Namensmigration – Live-/Worker-Abschlussstand 2026-10-07

## Status

P1 ist im Home-Assistant-Liveprodukt einschließlich des nativen Workers vollständig aktiviert und technisch abgenommen. Im aktiven HA-/Worker-Runtimebestand gibt es keine produktiven Studio-V6-Namensreste mehr. Der öffentliche GitHub-Abgleich bleibt der letzte P1-Abschlussschritt; historische Backups, Validierungsstände und abgeschlossene Job-Payloads werden bewusst nicht umgeschrieben.

## Bestätigter HA-Live-Stand

- Integration Domain: `ultimate_3d_studio`
- Config Entry Titel: `3D Studio Test`
- 22 Entity-Registry-Einträge auf Plattform `ultimate_3d_studio`
- Dashboard: `3d_studio_test` / `3d-studio-test` / `3D Studio Test`
- Lovelace Resource: `/local/3d-studio/ultimate-3d-studio.js?v=4cbbb1218d683a0c69874736e04f32c0c2cb9a0f1883197551c0c1ddab24925f`
- Live Frontend JS SHA256: `4cbbb1218d683a0c69874736e04f32c0c2cb9a0f1883197551c0c1ddab24925f`
- Live Komponente nur unter `custom_components/ultimate_3d_studio`
- Live Webbaum nur unter `www/3d-studio`
- aktive Studio-Storage-Dateien versionsfrei
- `configuration.yaml` und `automations.yaml` ohne aktive alte Studio-V6-Referenzen

Präziser Residualscan gegen `ultimate_3d_studio_v6`, `ultimate-3d-studio-v6`, `3d_studio_v6`, `3d-studio-v6`, `3D Studio V6` und `api_v6_commands`:
- HA-Liveprodukt: 0 Dateien
- aktiver nativer Worker: 1 Datei, `dispatch-job.sh`

## HomeKit

Die zunächst sichtbaren drei einfachen `v6`-Treffer waren keine Studio-V6-Referenzen:
- zwei zufällige ID-Teilstrings mit `KVV6`
- `external_ipv6`

Die tatsächlichen Studio-AID-Schlüssel sind bereits `ultimate_3d_studio.*`. Keine HomeKit-Datei wurde geändert.

## Worker-Historie

- 354 Jobdateien vorhanden
- 0 Jobdateinamen mit altem V6-Präfix
- 198 historische Payloads enthalten noch historische Werte wie `V6 curated local catalog`, `v6:none:...` oder `mapped_v6_process`
- diese Werte liegen in abgeschlossenen historischen Nutzdaten und werden gemäß Migrationsregel nicht blind umgeschrieben
- keine queued/slicing Jobs wurden für diese Arbeit erzeugt
- keine reale Slicing-, Upload- oder Druckaktion

## Neutraler Worker-Kandidat

Der HA-Quellkandidat `deploy/homeassistant/host/3d-printer-slicing-server/dispatch-job.sh` ersetzt ausschließlich interne Versionsnamen:
- `v6_validate_bambu_gcode` → `studio_validate_bambu_gcode`
- `V6_GCODE/V6_BYTES/V6_WAIT/V6_ORIGINAL_CODE` → `STUDIO_*`
- interne Logtexte `V6 telemetry...` → `Studio telemetry...`
- `v6:*` → `studio:*`
- `v6_adhesion_mode` / `v6_support_mode` → `studio_adhesion_mode` / `studio_support_mode`

Kandidaten-SHA256:
`3fb2598742fd5896fa2b9f97e263e20542bd7cd41828c50ebb4ff3f814d6e9f3`

Der bisherige produktive Worker bleibt bis zum Gesamtgate auf:
`731d90aa5aa4138e905b68cc9f4a217bb3bf60d21d2ae74adb0ede678b111ad1`

## Kanonischer Vertrag

PC und HA-Quellkopie wurden für folgende Kandidatendateien abgeglichen:
- `deploy/homeassistant/host/3d-printer-slicing-server/dispatch-job.sh`
- `deploy/homeassistant/host/3d-printer-slicing-server/SHA256SUMS`
- `deploy/homeassistant/host/3d-printer-slicing-server/DEPENDENCY-SHA256SUMS`
- `tests/test_studio_native_slicer_canonical_sources.py`
- `pyproject.toml`

Aktuelle Dependency-SHAs:
- `materialize-bambu-multimaterial.py`: `821ac3f47d2c589d11f3678f40435c3398059de213da0507402a7bbb2f9fd4b4`
- `slicer_execution_contract.py`: `377ed6077f594758a803459e0729588f32ba0c7f6de4c60ce93015998278a12c`

Der alte lokale PC-Test `tests/test_v6_native_slicer_canonical_sources.py` wurde inert gemacht; der aktive Testvertrag liegt unter `tests/test_studio_native_slicer_canonical_sources.py`. Eine physische Löschung des alten Dateinamens wurde nicht über einen alternativen Schreibweg erzwungen.

## Release-Metadaten

`pyproject.toml` war auf PC noch `6.0.0b3` und enthielt im Beschreibungstext `V6`. Der Kandidat ist auf:
- Version `6.0.0`
- Beschreibung `Core domain and API contracts for Ultimate 3D Printing Studio`

angeglichen. `package.json`, HA-`manifest.json` und `const.py` standen bereits korrekt auf `6.0.0`.

## Tests

Gezielter Linux-Workervertrag:
- 7/7 bestanden
- Shell-Syntax `dispatch-job.sh` bestanden
- Python-Compile des Testvertrags bestanden

Vollständiger Python-/Workerlauf in neuem isoliertem Venv:
- 1752 Tests gesammelt
- 1751 bestanden
- 15 Subtests bestanden
- 1 Fehler ausschließlich wegen fehlendem Node-Paket `typescript` in der HA-Testumgebung
- der betroffene Test ist `test_viewer_and_makerworld_modal_contracts`
- kein Produkt-/Workerfehler aus diesem Lauf
- kein Test wurde künstlich übersprungen

Ein Versuch, die gelockten Node-Dev-Abhängigkeiten in der HA-Testkopie einzurichten, wurde abgebrochen, weil der vorhandene Corepack-npm-Shim npm 12 mit Node 20 kombiniert und selbst inkompatibel ist. Keine System-Node-/npm-Installation wurde verändert.

## Connector

Ursache des Tara-PC-MCP-Ausfalls war ein Syntaxfehler in `jarvis_v6_deployment.py` Zeile 259. Nach Backup und Korrektur:
- Connector auf `192.168.100.10:8767` wieder erreichbar
- neutralisierte `jarvis_studio_*`-Module aus dem heutigen Sicherheitsstand erzeugt
- Runner auf `jarvis_studio_deployment` und `jarvis_studio_live_deploy` umgestellt
- neuere Schutzmechanismen (enger Allowlist-Scope, Backup-/Temp-Ausschlüsse, frischer Qualitätsnachweis) erhalten
- alter Toolname `v6_source_manifest` nach Neustart nicht mehr registriert

Der aktuelle Chat besitzt noch die vor dem Connector-Neustart geladene Tool-Schema-Liste und sieht die neuen `studio_*`-Tools daher nicht als aufrufbare Werkzeuge. Diese Grenze wird nicht durch einen alternativen Schreib-/RPC-Weg umgangen.

## Visuelle Live-Abnahme

Puppet Host-Port 5000:
- HTTP 200
- Content-Type `image/png`
- 1650 × 920
- 182346 Bytes
- SHA256 `5f85a4b7f3ba319aa22ec9cc40921864b6856cd3f550e52c8b9a827c21b65883`

Visuell bestätigt:
- linke Studio-Navigation vollständig vorhanden
- keine redundante schwarze HA-Tab-Leiste
- Steuerzentrale, Karten und Vorgangsfenster sauber gerendert
- keine erkennbare Layout-Zerstörung

Nachweis:
`/var/lib/homeassistant/homeassistant/backups/20261007-p1-live-layout-current.png`

## Backups

PC:
- `backups/20261007-p1-worker-contract-before`
- Connector: `C:\Users\Taracraft\AppData\Local\JARVIS\ChatGPT-PC-Connector\backups\20261007-p1-neutral-connector-before`

HA:
- `/var/lib/homeassistant/homeassistant/backups/20261007-p1-worker-contract-before`
- vorhandene P1-Backups: `20261007-p1-live-before`, `20261007-p1-worker-history-before`, `20261007-p1-active-config-cleanup-before`, `20261007-p1-retired-v6`

## Nächster verbindlicher Schritt

1. In einem Connector-Kontext mit frisch geladenem Tool-Schema das neutrale PC-`studio_quality_gate` ausführen.
2. Nur bei vollständig grünem PC-Gesamtgate Worker-Idle erneut prüfen.
3. Same-Day-Live-Backup des nativen Worker-Ziels.
4. Neutralen `dispatch-job.sh` plus aktualisierte Prüfsummen über den geprüften nativen Deploymentvertrag aktivieren.
5. Native Dienste/Health/SHA prüfen, ohne realen Slice.
6. Puppet-Screenshot erneut gegen diese Baseline prüfen.
7. PC ↔ HA ↔ GitHub synchronisieren.
8. ROADMAP, LIVE_WORKLOG und Changelogs nachziehen.
9. P1 erst danach als abgeschlossen markieren.

Keine Druckerbefehle, realen Test-Slices, Job-Releases, Uploads, Bewegungen, Heiz-/Filamentaktionen oder Druckstarts.


## Öffentlicher GitHub-Iststand

Read-only-Prüfung von `Taracraft/3D-Ultimate-Center` nach der privaten P1-Aktivierung:
- `main` führt weiterhin den öffentlichen Projektquellroot `studio-v6/`.
- Die öffentliche HA-Komponente liegt weiterhin unter `homeassistant/custom_components/ultimate_3d_studio_v6/`.
- Code Search findet dort weiterhin aktive alte API-/Storage-/User-Agent-/Testreferenzen.
- `studio-v6/pyproject.toml` steht öffentlich noch auf `6.0.0b3` und enthält die V6-Beschreibung.
- Das ist erwarteter P1-Sync-Rückstand; es wurde in diesem Arbeitsblock nichts öffentlich geschrieben.

Wichtig: Der geprüfte lokale Namespace-Helfer definiert Produkt-Renamings wie `ultimate_3d_studio_v6 -> ultimate_3d_studio` und `3d-studio-v6 -> 3d-studio`, aber keinen ausdrücklich reviewten öffentlichen Zielroot für `studio-v6/`. Eine mechanische globale Anwendung ist deshalb nicht zulässig. Der öffentliche Root-Umzug wird nach grünem Gesamtgate als eigener Pfadvertrag geplant und geprüft; kein globales String-Replacement und kein flaches Überschreiben des Repository-Roots.


## Live-/Worker-Abschlussnachtrag 07.10.2026

### Frisches autoritatives PC-Gesamtgate

Nach dem finalen Byteabgleich von `dispatch-job.sh` wurde das Gesamtgate auf dem führenden PC-Repository erneut vollständig ausgeführt. Der erste frische Lauf deckte ausschließlich einen fehlenden abschließenden LF in `dispatch-job.sh` auf und blieb deshalb korrekt rot. Nach der Ein-Byte-Korrektur war der zweite Lauf um `2026-10-07T16:31:54+02:00` vollständig grün:

- Frontend: **456/456 bestanden**
- Python/Worker: **1686 bestanden**
- explizite Plattform-Skips: **66**
- Subtests: **15 bestanden**
- Source-Policy: grün
- Produktionsbuild: grün
- HA-Core-Build: grün
- Compileall: grün
- Frontend-JS: `4cbbb1218d683a0c69874736e04f32c0c2cb9a0f1883197551c0c1ddab24925f`
- Frontend-CSS: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`

Zusätzlich bestand der aktuelle neutrale Workerquellstand unter Linux **150/150** gezielte Paket-, Profil-, Deploy- und Slicing-Vertragstests.

### Neutraler Worker live

Vor jeder produktiven Änderung wurden `queued=0`, `slicing=0` und das Fehlen von `run/dispatcher.lock` geprüft. Zwei veraltete Worker-Abhängigkeitskopien wurden vor dem Hauptdeploy einzeln fail-closed gegen das aktuelle `DEPENDENCY-SHA256SUMS` angeglichen:

- `materialize-bambu-multimaterial.py`: `821ac3f47d2c589d11f3678f40435c3398059de213da0507402a7bbb2f9fd4b4`
  - Backup: `/var/lib/homeassistant/3d-printer-slicing-server/backups/20261007-163709-p1-materializer-dependency`
- `slicer_execution_contract.py`: `377ed6077f594758a803459e0729588f32ba0c7f6de4c60ce93015998278a12c`
  - Backup: `/var/lib/homeassistant/3d-printer-slicing-server/backups/20261007-163821-p1-slicer-execution-contract`

Anschließend lief der kanonische `deploy-native-slicer.sh` erfolgreich durch alle acht Stufen. Er erkannte nur `runtime/dispatch-job.sh` als eigentliche Paketänderung, prüfte den Idle-Zustand zweimal, erstellte ein Same-Day-Backup, installierte atomar und bestätigte API v2 sowie Telemetrie/Capabilities.

- Live `dispatch-job.sh`: `3fb2598742fd5896fa2b9f97e263e20542bd7cd41828c50ebb4ff3f814d6e9f3`
- Hauptbackup: `/var/lib/homeassistant/3d-printer-slicing-server/backups/20261007-163830-studio-native-deploy`
- Deploy-Nachweis ZIP: `/var/lib/homeassistant/3d-printer-slicing-server/deploy-logs/20261007-163830-studio-native-deploy.zip`
- ZIP SHA256: `595c5e3527d66c5096d9953da5260ef78e2a386ad842948fb452bb5a8729c87a`
- Worker-`SHA256SUMS` anschließend auf den geprüften Paketstand synchronisiert; Backup: `/var/lib/homeassistant/3d-printer-slicing-server/backups/20261007-163930-p1-sha256-manifest`

Abschließende Live-Prüfung:
- Slicing-Server: `active`
- Dispatch-Timer: `active`
- Refresh-Timer: `active`
- Worker API: `status=ready`, API v2
- Live-Progress/History/ETA/Job-Detail/Engine-Result/Runtime-Summary: bestätigt
- alle **11/11** Worker-Abhängigkeiten per SHA geprüft
- aktive Worker-Namensresiduals: **0**
- keine queued/slicing Jobs, kein Dispatcher-Lock

### Connector final neutral

Für das frische PC-Gate wurde wegen des im laufenden Chat gecachten alten Toolschemas kurzzeitig eine eng begrenzte Kompatibilitätsbrücke für den bereits bekannten Toolnamen verwendet. Sie rief intern ausschließlich das neutrale `run_studio_quality_gate()` auf. Unmittelbar nach dem grünen Gate wurde die Brücke aus dem vorherigen Backup zurückgenommen und der Connector-Worker neu gestartet.

Final:
- Connector erreichbar auf `192.168.100.10:8767`
- Runner verwendet `jarvis_studio_*`
- temporäre Brücke entfernt
- alter Toolname `v6_prepare_bundle`: **nicht registriert / Unknown tool**

### Finale visuelle Layout-Gegenprobe

Nach dem Worker-Abschluss wurde das versionsfreie Dashboard über Puppet Host-Port 5000 erneut aufgenommen.

Großer Nachweis:
- HTTP 200
- Content-Type `image/png`
- gültige PNG-Signatur
- 1000 × 600
- 137455 Bytes
- SHA256 `5c675529a830374b889d788687b95213b16194aa6346faed3a948424d1e3a260`
- Datei: `/var/lib/homeassistant/homeassistant/backups/20261007-p1-worker-final-layout-small.png`

Visuell bestätigt:
- reguläre linke Studio-Navigation vollständig vorhanden
- Steuerzentrale, Galerie, 3D-Studio, Materialsysteme, Profile, Aufgaben, Verlauf, System und Slicing-Server sichtbar
- keine redundante schwarze Lovelace-Tab-Leiste
- Steuerzentrale und Karten sauber angeordnet
- Vorgangsfenster, Fortschritt und Kamera-/Größer-/Minimieren-Steuerung sauber dargestellt
- keine erkennbare Layout-Zerstörung

Das Frontend wurde im Worker-Abschlussblock nicht geändert.

### Sicherheitsgrenzen

Kein realer Test-Slice, kein Job-Release, kein Druckerupload, kein Druckstart, keine Bewegung, keine Heiz- oder Filamentaktion. Historische Job-Payloads und Backup-/Validierungsstände mit alten Versionsbezeichnern bleiben als Rückweg/Nachweis erhalten.

### Verbleibender P1-Abschlusspunkt

Der private PC-/HA-Live-/Worker-Stand ist vollständig neutralisiert und abgenommen. P1 wird erst nach dem explizit geplanten, geprüften öffentlichen GitHub-Pfadabgleich endgültig geschlossen. Insbesondere wird der öffentliche Root `studio-v6/` nicht mechanisch oder global umbenannt.
