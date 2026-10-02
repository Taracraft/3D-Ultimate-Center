# V6 Studio Arbeitsnotiz 2026-09-14 Layer Preview

Stand:
- Tara-PC Connector war zunaechst mit internen MCP-Fehlern blockiert.
- Gezielt nur der Tara-PC Connector-Worker wurde neu gestartet; danach waren connector_info, pc_health, read/write und HA-SSH wieder erreichbar.
- Kein Drucker-, HA-, V6-Worker- oder Slicer-Neustart wurde gemacht.
- Bambu A1 lief waehrend der Pruefung laut HA: RUNNING, ca. 39 %, Layer 302/1179, Restzeit ca. 876 min.
- HA/V6 Live-Build blieb unveraendert: beta3, JS 33c6353d1e2e2fc479ac30e5808d27651e2582be63488a7260b4c1e72d17eef9, runtime_patching false.
- Raspberry jarvis-pc-tunnel.service laeuft, health 200/live, ready weiter 503.
- HA Advanced SSH & Web Terminal ist installiert/gestartet und ein harmloser SSH-Check war erfolgreich.
- Opera Browser Connector ist wieder verbunden.

Source-Aenderung, noch NICHT gebaut/deployt:
- Datei: frontend/toolpath-ribbon-geometry.ts
- Ziel: Layer-/Toolpath-Vorschau optisch flacher und Bambu-Studio-naeher machen, ohne Slicer/G-Code/Druckablauf zu aendern.
- Aenderungen:
  - extrusionRibbonWidth begrenzt Breiten konservativer: max 1.25 statt 1.6, fallback .38 statt .42.
  - visualRibbonHeight(style,current,height) ergaenzt.
  - Seiten-/Cap-/Corner-Flaechen nutzen reduzierte visuelle Hoehe:
    - aktueller Layer: 72 % der realen Layerhoehe
    - History: 36 % der realen Layerhoehe
  - Layer-Top bleibt exakt auf z, damit die Hoehenposition nicht verschoben wird.

Blocker:
- v6_prepare_bundle liefert aktuell INVALID_ARGUMENT, bevor Tests/Build starten.
- v6_deploy_frontend liefert ebenfalls INVALID_ARGUMENT.
- raspberry_pi control_service restart fuer jarvis-pc-tunnel wurde vom Tool ebenfalls mit INVALID_ARGUMENT abgelehnt.
- Deshalb wurde die Source-Aenderung NICHT deployed.

Naechster sauberer Schritt:
1. V6-Spezialtools wieder gangbar machen oder manuell den offiziellen V6-Gate/Build-Pfad auf Tara-PC ausfuehren.
2. Erst wenn Gate/Build gruen ist: v6_deploy_frontend.
3. Danach HA-Builddatei pruefen und Browser-Abnahme der Layeransicht mit echtem geslictem Projekt.
4. Falls Gate nicht zeitnah laeuft, Source-Aenderung entweder zuruecknehmen oder per sauberem lokalem Build validieren.


## Nachtrag 18:25

Benutzer meldete: HA wurde neu gestartet, sollte gleich wieder gehen.

Erneut geprueft:
- HA ist wieder erreichbar; HA-SSH antwortet.
- Tara-PC Connector ist erreichbar.
- Raspberry pc-tunnel bleibt health 200/live, ready aber 503.
- v6_prepare_bundle und v6_deploy_frontend liefern weiter INVALID_ARGUMENT, bevor Node/Gate startet.
- Es laeuft kein node.exe waehrend der fehlgeschlagenen Aufrufe; das Gate startet also nicht.
- Windows-Events zeigen keinen passenden V6-/Python-Gatefehler.
- Kurzzeitig wurde ein Connector-no-arg-Wrapper getestet, weil die Argumentuebergabe der Spezialtools defekt wirkt.
- Der Wrapper wurde nicht nutzbar in der aktuellen App-Toolliste sichtbar.
- Ein temporaerer Umbau von v6_source_manifest wurde abgebrochen, weil danach ebenfalls INVALID_ARGUMENT kam.
- Connector-Dateien wurden aus Backups wiederhergestellt:
  - run_jarvis_pc_mcp_lan_v13.py wieder ohne Wrapper-Import.
  - jarvis_v6_live_deploy.py wieder mit confirmed-Parameter.
  - jarvis_v6_deployment.py wieder mit originaler v6_prepare_bundle(ttl_seconds).
- Connector-Worker wurde danach neu gestartet und connector_info ist wieder OK.

Wichtig:
- Die V6-Source-Aenderung an frontend/toolpath-ribbon-geometry.ts ist weiterhin nur lokal im Quellbaum.
- Sie ist NICHT gebaut, NICHT deployed und NICHT per Gate validiert.
- Live in HA bleibt unveraendert beim vorherigen beta3 Build.
- Naechster sinnvoller Schritt: V6-Spezialtool-/MCP-Argumentrouter reparieren oder auf Tara-PC manuell das offizielle Gate ausfuehren.

## Nachtrag 18:40

Manueller sauberer Gate/Build/Deploy-Weg wurde vorbereitet, weil die V6-MCP-Spezialtools weiterhin INVALID_ARGUMENT liefern.

Neue Datei:
- F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Printer-Control-Center\v6\Run-V6-LayerPreview-Gate-And-Deploy-20260914.ps1

Dieses PowerShell-ISE-Skript macht:
- arbeitet nur im erlaubten V6-Pfad.
- prueft auf verbotene Runtime-Patch-Pattern im frontend-Source.
- fuehrt run_frontend_tests.mjs aus.
- fuehrt build_v6_core.mjs aus.
- fuehrt run_python_tests.py aus.
- kompiliert deploy\homeassistant\custom_components\ultimate_3d_studio_v6 per compileall.
- prueft die drei Deploy-Artefakte und berechnet lokale SHA-256-Hashes.
- uebertraegt ultimate-3d-studio.js, ultimate-3d-studio.css und ultimate-3d-studio-build.json per bestehender ha-jarvis-admin SSH-Konfiguration.
- legt Remote-Stage und Backup an:
  - Stage: /home/hassio/v6-frontend-<timestamp>
  - Backup: /homeassistant/pcc-backups/v6-frontend/<timestamp>
  - Live: /homeassistant/www/3d-studio-v6
- prueft Remote-Hashes mit sha256sum.
- kopiert atomar nach live.
- schreibt Log und summary.json unter .test-results\manual-layer-preview-deploy-<timestamp>.
- laesst das Terminal offen.

Wichtig:
- Das Skript startet keinen Druck.
- Das Skript schreibt kein Material.
- Das Skript startet weder HA, noch V6-Worker, noch Drucker, noch Slicer neu.
- Live in HA wurde beim Erstellen des Skripts erneut gelesen und ist weiterhin der alte Build: JS 33c6353d1e2e2fc479ac30e5808d27651e2582be63488a7260b4c1e72d17eef9, CSS 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c, built_at 2026-09-14T05:37:44.987Z.

Nachtrag nach erneutem Versuch:
- v6_prepare_bundle wurde noch einmal mit ttl_seconds=600 getestet.
- Ergebnis erneut: INVALID_ARGUMENT.
- Es gibt im freigegebenen Tara-PC-Connector weiterhin keinen allgemeinen PowerShell-/Command-Runner.
- Damit wurde nichts gebaut und nichts deployed.

Naechster Schritt:
- Skript in PowerShell ISE auf Tara-PC ausfuehren oder, falls wieder ein sicherer Remote-Command-Runner verfuegbar ist, kontrolliert ausfuehren.
- Danach summary.json und HA-Live-Builddatei pruefen.
- Anschliessend Browser-Abnahme der Layer-/Toolpath-Ansicht gegen Bambu Studio Vergleich.


## Nachtrag 18:55

Neuer gemeldeter UI-Fehler:
- Filamentprofile unten rechts in der Studio-Seitenleiste sind nicht scrollbar bzw. die Profilliste kann unten abgeschnitten werden.

Source-Fix vorbereitet:
- Datei: frontend/studio-profile-ui.ts
- Bereich: STUDIO_PROFILE_CSS / filamentProfilesHtml-Darstellung.
- Aenderung:
  - .filament-tree bekommt einen eigenen Scroll-Kontext mit overflow:auto und overscroll-behavior:contain.
  - sichtbare Scrollbar fuer Chromium/WebKit ergaenzt.
  - in der rechten .side/#sidebar wird die Filamentliste auf max-height:min(38vh,360px) begrenzt, damit der Bereich unten rechts scrollbar bleibt und nicht aus der sichtbaren Seitenleiste herauslaeuft.

Status:
- Diese Aenderung ist Source-only.
- Noch NICHT gebaut, NICHT deployed, NICHT visuell abgenommen.
- Der bereits erstellte manuelle PowerShell-ISE Gate/Build/Deploy-Pfad baut diese Aenderung mit.

## 2026-09-14 23:33 CEST - Gate green and frontend deployed

Status: completed and live in Home Assistant.

Changed source only in V6:
- `frontend/studio-profile-ui.ts`: filament profile tree keeps the legacy `max-height:460px` contract and adds viewport-bound scrolling with contained overscroll for the lower-right filament profile list.
- `frontend/toolpath-ribbon-geometry.ts`: narrower Bambu-like extrusion ribbon width is kept, but non-flat ribbons preserve full consecutive layer heights so Z layers stay gap-free; flat/support paths remain flat.

Quality gate after fixes:
- Source policy: OK, no runtime patch / MutationObserver / prototype patch violations.
- Frontend tests and build: OK, 104/104 logic tests passing.
- Home Assistant core frontend build: OK.
- Python tests: OK, 375/375 passing.
- compileall: OK.

Deployed frontend artifacts only, no HA restart, no worker restart, no printer/material action:
- Backup: `/homeassistant/pcc-backups/v6-frontend/20260914-233334`
- Live JS SHA-256: `3e16620b5581dd6e71297bf59c8a9d6c9ca4afc68da4fcc675fa312b774325f0`
- Live CSS SHA-256: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`
- Live build JSON SHA-256 from deploy: `cb7dfb4e52ecf130ac5b057b034713b73291d99eb3755e1989086bded0c1d8b5`
- HA readback build time: `2026-09-14T21:33:17.654Z`

Next recommended work:
1. Browser/manual verify the lower-right filament profile list scrolls without jumping in the live Studio.
2. Compare live layer/toolpath preview against Bambu Studio screenshots; if it still looks too tall, improve shader/lighting/width/opacity rather than reducing real Z height.
3. Continue with earlier reported queue scroll-jump and incorrect print-duration estimation.
4. Then continue support-mode parity: build-plate-only vs model-contact supports and unsupported-overhang warnings.

## 2026-09-15 00:37 CEST - Slicing functionality restored first

User priority recorded: restore slicing functionality before any further visual work. Do not let preview/Bambu-parity work block actual slicing.

Bug:
- Live slicing failed with: "Das Bambu-Prozessprofil enthält keine eigenen Einstellungen."
- Cause: `process_profile_contract.py` rejected Bambu Cloud process profiles when they had only a validated `inherits` base profile and no own overlay settings.
- Correct behavior: empty Bambu Cloud process settings are valid if `inherits` exactly matches the validated nozzle base profile. Empty settings means "use the native base profile as-is".

Changed source:
- `deploy/homeassistant/custom_components/ultimate_3d_studio_v6/process_profile_contract.py`
- `tests/test_v6_process_profile_contract.py`

Verification:
- Full V6 gate green after change.
- Frontend logic tests: 104/104.
- Python tests: 376/376.
- Home Assistant compileall: OK.
- Regression test added: `test_cloud_profile_can_use_validated_base_without_own_overlay`.

Deploy:
- Backend file deployed to HA: `/homeassistant/custom_components/ultimate_3d_studio_v6/process_profile_contract.py`
- HA LF SHA-256: `a49172e572c43fe884d862c79de63237b9a081c17843062395a460aab9348a35`
- V6 source/bundle SHA-256 for same file: `55c751186a376a7b1c4d9abf240e6f8303e097fb640a22a56de325c800631fd0` (CRLF source differs from HA LF line endings)
- Backup: `/homeassistant/pcc-backups/v6-backend/20260915-003724`
- HA Core container restarted because the patched Python module is imported by the running HA process.
- HA reachable again via connector after restart.

Next:
1. User should retry slicing the same model/profile first.
2. If it still fails, capture the next exact error message and fix that before visual improvements.
3. Only after successful slicing continue queue scroll-jump, wrong print duration, support modes and Bambu-like preview parity.

## 2026-09-15 00:49 CEST - ABS/PLA stale filament guard

User reported slicing still blocked although no ABS was selected in the visible Studio UI:
- Error: "Filamentprofil eSUN ABS passt zu keinem Material der aktiven AMS-Slots."
- Screenshot showed active material/profile context as eSUN PLA+/PLA, not ABS.

Fix:
- Source-only backend change in `filament_profile_mapping.py`.
- Added a narrow fallback for the single-material case: if exactly one stale selected filament profile is incompatible with the active physical AMS filament, and the catalog contains one clear matching profile for the active material, attach the matching active-material profile instead of blocking on the stale ABS id.
- Multi-profile / multi-channel positional conflicts remain strict and still fail closed.

Regression tests added in `tests/test_v6_filament_profile_mapping.py`:
- `test_single_stale_abs_selection_falls_back_to_matching_active_pla_profile`
- `test_single_stale_abs_selection_still_fails_when_no_matching_active_profile_exists`

Verification:
- Full V6 gate green after change.
- Frontend logic tests: 104/104.
- Python tests: all green.
- Home Assistant compileall: OK.
- Source policy: no JS runtime patch, no DOM injection, no MutationObserver/prototype patch.

Deploy:
- Backend file deployed to HA: `/homeassistant/custom_components/ultimate_3d_studio_v6/filament_profile_mapping.py`
- HA SHA-256: `21a40b6a9ac9e53053304a39401e59501d1aa05ca11926474fd109ee692f5850`
- Backup: `/homeassistant/pcc-backups/v6-backend/20260915-004847-filament-map`
- HA Core container restarted; Puppet/Worker/printer untouched.


## 2026-09-15 01:54 CEST - Active material channels override unused profile selections

User priority remains binding: restore and protect slicing functionality before further visual work.

Confirmed root cause from live HA profile storage:
- Global selection still contained both `local.filament.esun_abs` and `cloud.filament.pfus907bcf946d6bd6`.
- The active slice material plan used only one PLA channel.
- The earlier single-profile fallback did not cover two globally selected profiles with only one used channel. PLA was resolved correctly, but the unused ABS profile was still treated as a blocking unresolved profile.

Source fix:
- `deploy/homeassistant/custom_components/ultimate_3d_studio_v6/filament_profile_mapping.py`
- Used material channels are authoritative. Once every channel in the plate material plan has one clear compatible profile, extra global profile selections for unused AMS slots are ignored.
- Equal-count positional conflicts and ambiguous multiple compatible profiles remain fail-closed.

Regression protection:
- Exact live-ID regression for ABS + PLA selection with only PLA used.
- Multi-material regression with one unused extra profile.
- 100-case parameterized matrix across PLA, PETG, ABS, ASA, TPU, PA and PC, varying profile order, stale-profile count, AMS slot and color.
- Negative ambiguity test ensures two compatible active profiles are not guessed.
- Complete gate: source policy OK; frontend 104/104; Python 481/481; HA compileall OK.
- Forbidden DOM/runtime patch patterns: 0 violations.

Deployment:
- Live backend file: `/homeassistant/custom_components/ultimate_3d_studio_v6/filament_profile_mapping.py`
- Live/source SHA-256: `70496ad4fca9fcf4294a36ec33d1cfe4672a55c50713e5696f7f5583bca16772`
- Backup: `/homeassistant/pcc-backups/v6-backend/20260915-0152-unused-profile/filament_profile_mapping.py`
- Only HA Core was restarted to load the Python module. Frontend, V6 worker, Puppet, Raspberry and printer were untouched.
- Live-module smoke test with the real stored selection chose `cloud.filament.pfus907bcf946d6bd6` for the used PLA channel.

Current external blocker after HA restart:
- V6 integration is loaded, but Bambu A1 currently reports offline/disconnected and 0 AMS slots.
- From Tara-PC, Raspberry Pi and the HA container, printer `192.168.178.21` answers ping and TCP 6000, while TCP 8883 is actively refused.
- This is outside the profile-mapping code and prevents authoritative live AMS resolution until printer LAN/MQTT access is available again.
- Do not use stale AMS data or bypass the safety check.

Next:
1. Recheck TCP 8883 and V6 printer state; no printer restart without explicit user instruction.
2. Once LAN/MQTT is available, repeat the exact same model/profile slice and inspect the resulting native job.
3. Fix any next exact functional error before returning to Bambu-like preview parity, support/overhang analysis, queue behavior or duration estimation.
