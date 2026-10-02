# Ultimate 3D Studio V6 – Roadmap

## Verbindliches Zielbild

Ultimate 3D Studio V6 wird nach Abschluss der aktuellen Test- und Kompatibilitätsphase vollständig ohne eine installierte oder laufende Bambu-Studio-Anwendung betrieben.

Bambu Studio ist ausschließlich eine zeitlich begrenzte Referenz- und Übergangskomponente für Profilvergleich, CLI-Kompatibilität, Ergebnisvalidierung und die Absicherung bestehender Bambu-Dateiformate. Es ist kein dauerhaftes Produktivmodul und keine spätere Laufzeitabhängigkeit.

## Phase 1 – Beta- und Kompatibilitätstest

- CAD-Studio, Galerie, MakerWorld, Slicer, Profile, Auftragsverwaltung und Direktdruck als durchgängigen V6-Workflow stabilisieren.
- STL- und Mehrplatten-3MF-Import validieren.
- Druckplattenauswahl, AMS-Zuordnung und G-Code-3MF-Ausgabe gegen reale Bambu-Drucker testen.
- Vorhandene Bambu-Profile vollständig auflösen und Unterschiede dokumentieren.
- Bambu Studio nur lokal und kontrolliert als Vergleichs-Slicer beziehungsweise temporären CLI-Provider verwenden.

## Phase 2 – Nativer V6-Slicer

- Eigenen Slicing-Kern als gekapselten Provider implementieren.
- Maschinen-, Düsen-, Filament-, Prozess- und Druckplattenprofile vollständig im V6-Profilmodell abbilden.
- Vererbung, Kompatibilitätsregeln, Support-Filamente, Mehrmaterialzuordnung und Druckplattenparameter nativ auflösen.
- Mehrplatten-3MF intern analysieren, selektiv slicen und als G-Code-3MF ausgeben.
- Deterministische Geometrie-, Layer-, Support-, Infill- und Toolpath-Pipeline mit reproduzierbaren Tests bereitstellen.
- Slicer-Artefakte durch SHA-256, strukturierte Metadaten und reproduzierbare Buildinformationen absichern.

## Phase 3 – Vollständige Ablösung von Bambu Studio

- Bambu-Studio-CLI-Provider und Profiladapter entfernen.
- Keine Suche in `C:\Program Files\Bambu Studio` und keine Bambu-Studio-Prozesse mehr.
- Keine Laufzeitabhängigkeit von Bambu-Studio-Ressourcen oder Benutzerprofilverzeichnissen.
- Eigene 3MF-, G-Code- und G-Code-3MF-Erzeugung als alleiniger Produktivpfad.
- Direktdruck ausschließlich aus V6 mit validiertem Artefakt, AMS-Zuordnung und zweistufiger Freigabe.
- Migration bestehender lokaler und Cloud-Profile in das native V6-Format.

## Abnahmekriterien für „Bambu Studio vollständig abgelöst“

- V6 startet und arbeitet auf einem System ohne installierte Bambu-Studio-Anwendung.
- Alle unterstützten Drucker, Düsen, Filamente, Prozesse und Druckplatten sind im V6-Profilkatalog verfügbar.
- STL- und Mehrplatten-3MF-Dateien können ohne externe Anwendung importiert, bearbeitet, geslicet, exportiert und gedruckt werden.
- Galerie- und MakerWorld-Modelle gelangen direkt in CAD-Studio oder Slicer.
- G-Code-3MF-Ausgabe und Direktdruck funktionieren reproduzierbar ohne Bambu-Studio-Binärdateien.
- Automatische Tests prüfen Geometrie, Profile, Mehrplattenauswahl, AMS-Mapping, G-Code-Metadaten und Druckstartvertrag.


## 2026-09-15 – Wiederherstellung LAN/AMS und Layerdaten-Parität

- Bambu A1 nach Drucker-Reset wieder per LAN verbunden; HA/V6 zeigen `online`, `lan` und AMS/BMCU mit 4 Slots.
- Neuer LAN Access Code wurde in V6 und den alten `printer_control_center`-Eintrag synchronisiert; Backup: `/homeassistant/pcc-backups/20260915-0721-sync-access-code/`.
- Toolpath-Kategorien für die Bambu-Studio-nahe Layeransicht erweitert: `support_interface`, `support_transition`, `overhang_wall`, Wände, Infill, Bridge und Ober-/Unterflächen bleiben nun als eigene Kategorien erhalten.
- Verifiziert: `tests/test_v6_gcode_toolpath.py` und `tests/test_v6_gcode_analysis.py` grün; kompletter Frontend-Produktionsbuild grün.
- Build-Blocker durch kanonische TypeScript-Quellmodule behoben; keine Runtime-/DOM-Patches.
- Vorgangs-Popup behält Scrollposition bei Live-Aktualisierungen, damit lange Slicing-/Druckprotokolle scrollbar bleiben.
- G-Code-Zeitplausibilität ergänzt: extrem kurze G-Code-Zeiten werden gegen ein konservatives Extrusionsminimum geprüft, als nicht belastbar markiert und nicht mehr als `print_time_seconds` weitergereicht. Die Analyse zeigt dann eine Mindestzeit statt einer falschen Gesamtzeit.
- Supportmodus abgesichert: Normal/Baum, Grenzwinkel und `nur Druckplatte` versus `auf Modell erlaubt` werden in der Studio-Seitenleiste sichtbar und durch Regressionstest bis `support_on_build_plate_only = 0` im Bambu-Prozessprofil geprüft.
- G-Code-Supportprüfung ergänzt: Overhang-Wand/Bridge ohne erzeugte Support- oder Interface-Bahnen wird als Warnung in der Druckanalyse gemeldet und per Regressionstest abgesichert.
- Automatische Lösungsvorschläge ergänzt: Die Support-/Überhangwarnung kann direkt Normal- oder Baum-Support mit `auf Modell erlaubt` setzen; die Einstellung wird im kanonischen Prozesspanel gespeichert.
- Direktdruck-Transfertrace repariert: Event-Vertrag zwischen Direktdruck-Panel und Vorgangs-Popup nutzt nun `label`/`transferredBytes`; Job-/Druckerwechsel setzt lokale Transferwerte zurück, damit neue Uploads bei 0 starten.

## 2026-10-01 – CAD-Studio Filamentprofile vereinheitlicht

- CAD-/Studio-Seitenleiste im Farben-/Materialmodus vereinheitlicht: AMS Lite und externe Spule bleiben in einem gemeinsamen Materialquellen-Menü auswählbar, beide Pfade heißen jetzt sichtbar `Filamentprofile`.
- Externe Spule bleibt ein expliziter Einzelmaterialpfad mit genau einem gewählten Filamentprofil; AMS-Fallback und automatische Materialwechsel bleiben deaktiviert.
- AMS-Pfad behält `AMS des gewählten Druckers synchronisieren`, Projektfarben entfernen und Objektzuweisung ausschließlich über belegte AMS-Slots.
- Oberer Profilbereich benennt `Prozess` zu `Druckprofil` um.
- Geändert: `frontend/studio-mega-workspace-v2.ts`, `frontend/studio-profile-ui.ts`, `tests/test_v6_material_system_ui_contract.py`.
- Backup: `/homeassistant/3D-Studio/v6/.codex-backups/studio-mega-workspace-v2.ts.20260930-2357-filamentprofile-ui` und Live-Frontend-Backup `/homeassistant/pcc-backups/v6-frontend-20260930-2359-filamentprofile-ui/www/3d-studio-v6`.
- Verifiziert: `python3 -m pytest tests/test_v6_material_system_ui_contract.py -q` grün (`6 passed`), `npm run build` grün, Live-Hashes im HA-Container geprüft (`ultimate-3d-studio.js` SHA-256 `278284cc00b7cc49f532e0f39975a39d15d0083cb79af446a1a5d3f3a0cc96fb`).
- Puppet: Screenshot-Route auf Port 5000 erzeugt `/tmp/v6-puppet-studio.png`; Root-/Health-Pfade sind nicht als Abnahmequelle geeignet.
- Erledigter Gate-Hinweis: die zuvor offenen TypeScript-Fehler in Progress-/Direct-Print-/alten Slicer-Modulen wurden im nachfolgenden TypeScript-Gate-Fix behoben.
- Supportwarnung nachgeprüft: frühe Studio-Warnung enthält Objektname, Anzahl freischwebender Bereiche und Mindestabstand; G-Code-Analyse deckt Überhangwand/Brücken ohne Support ab und bietet Normal-/Baum-Support-Presets. Ergänzt wurde ein Regressionstest für `instanceId` und Objektname in `frontend-tests/logic.test.ts`. Verifiziert: gezielter esbuild-Testbundle-Lauf `26 passed`, `python3 -m pytest tests/test_v6_gcode_analysis.py -q` grün (`5 passed`).

## 2026-10-01 – TypeScript-Gate wieder grün

- Globales Frontend-TypeScript-Gate repariert: `npm run typecheck` läuft wieder ohne Fehler.
- Repariert wurden bestehende Typvertragsdrifts bei Direktdruck-Transferevents, Upload-Fortschritt, Studio-Operation-/Slice-Activity-Events, alten Slicer-Workspace-Provideranzeigen und dem Legacy-`createPlateSliceJob`-Aufruf.
- Keine V5-Änderung, keine Druckerbewegung, keine Druckbefehle. Änderungen bleiben im V6-Quellbaum und V6-Frontend-Deploy.
- Backups: `/homeassistant/3D-Studio/v6/.codex-backups/20261001-0009-typecheck-contract/` und Live-Frontend-Backup `/homeassistant/pcc-backups/v6-frontend-20261001-0012-typecheck-green/www/3d-studio-v6`.
- Verifiziert: `npm run typecheck` grün, `npm run build` grün, `python3 -m pytest tests/test_v6_material_system_ui_contract.py tests/test_v6_gcode_analysis.py -q` grün (`11 passed`), gezielter Frontend-Logic-Testbundle-Lauf grün (`26 passed`).
- Live-Deploy: `ultimate-3d-studio.js` SHA-256 `754179cca3a35478f59e9f9b979a707ce13387798074580ff29d854f4a975f44`; HA-Container-Hash geprüft; Puppet-Screenshot `/tmp/v6-puppet-typecheck-green.png` gültig erzeugt.

## 2026-10-01 – Slicing-/Direktdruck-Verträge ohne Druckstart geprüft

- Direktdruck-Artefaktvertrag repariert: lokale `.3mf`-Eingaben werden für den Drucker kanonisch als `.gcode.3mf` validiert/hochgeladen.
- FTPS-Upload-Timeout nach vollständigem Datentransfer wird nach Remote-Größenprüfung akzeptiert und die Verbindung wird hart geschlossen, ohne `QUIT` auf einer unsauberen Datenkanal-Verbindung.
- Live-V6-Backenddatei `custom_components/ultimate_3d_studio_v6/bambu_direct_print.py` wurde mit Backup aktualisiert; wir haben keinen Druckstart ausgelöst. Runtime-Aktivierung braucht später Integration-/HA-Core-Reload.
- Kanonischer nativer Slicer-Deploy-Snapshot wiederhergestellt: fehlende Host-/Bridge-Quellen aus vorhandenen V6-Bundles ergänzt, Dependency-SHA-Liste korrigiert und DELETE-Vertrag auf `delete_terminal_job(job_id)` mit Fehlercode `active_job_cannot_be_deleted` geschärft.
- Verifiziert ohne Druckerbewegung: `python3 -m pytest tests/test_v6_native_slicer_only.py tests/test_v6_native_slicer_canonical_sources.py tests/test_v6_direct_print_readiness.py tests/test_v6_external_spool_contract.py tests/test_v6_print_artifact.py -q` grün (`29 passed`).
- Backups: `/homeassistant/3D-Studio/v6/.codex-backups/20261001-0015-print-artifact-contract/`, `/homeassistant/pcc-backups/v6-backend-20261001-0017-print-artifact-contract/`, `/homeassistant/3D-Studio/v6/.codex-backups/20261001-0019-native-snapshot-source/`.

## 2026-10-01 – Aktiver Slicing-Server auf HA-Kontext geprüft

- Korrektur zur Umgebung: Der Slicing-Server ist unter `127.0.0.1:8099` im Home-Assistant-Serverkontext aktiv; `systemctl` im SSH-Addon-Container ist dafür keine gültige Prozess-/Service-Abnahme.
- Health geprüft: `3D-Printer Slicing Server`, Version `0.1.0-alpha5`, API-Version 2, Status `ready`, Uptime rund 455k Sekunden.
- Queue geprüft ohne neuen Druck- oder Slicing-Start: 100 Jobs, davon 90 `completed` und 10 `failed`.
- Vorhandenen erfolgreichen Probejob `codex-v6-raw-stl-positional-20260930` heruntergeladen und validiert: `plate_1.gcode.3mf`, 62.708 Bytes, SHA-256 `d049904f1d2fabcf77bdb98792e207e3f89dbf0d49aedc7fdf78e149004dfd2f`, `Metadata/plate_1.gcode`, 16.562 G-Code-Zeilen, 4.903 Extrusionsbewegungen.
- Keine Druckerbewegung, kein neuer Slicejob und kein Druckstart ausgelöst.

## 2026-10-01 – Frontend-/HTTP-Gates und Speed-Control-Vertrag grün

- Standalone-HTTP-Tests wieder lauffähig gemacht: `aiohttp.web.RequestKey` bekommt einen kompatiblen Fallback für die installierte aiohttp-Version.
- Offiziellen Frontend-Test-Runner repariert: npm wird robust über `npm_execpath` oder `npm` aus `PATH` gestartet, nicht mehr über einen nicht vorhandenen Node-Nebenpfad.
- Frontend-Policy auf den aktuellen integrierten Vorgangs-Popup-Aufbau kalibriert; der entfernte Standalone-Layer-Preview-Popup wird nicht mehr als Datei vorausgesetzt.
- Upload-Fortschritt wieder auf echten Browser-XHR-Progress gestellt; `authenticatedUpload` liefert gemessene Bytes, Rate, ETA und Status-Response weiter.
- Direktdruck-Transfer erscheint nun im globalen Vorgangs-Popup mit gemessenen Bytes, Rate, ETA und eigenem Schließen pro Transfer.
- A1/Bambu-Phasenvertrag bereinigt: nur verlässlich beobachtete Phasen bleiben sichtbar; Modell-Druck wird erst mit Job-Ende als erledigt gewertet.
- Bambu-Speed-Control durchgängig aktiviert: vier feste Level 50/100/125/166 %, `print_speed`-Befehl, Payload-Validierung und Telemetrie-Bestätigung im V2-Provider.
- Live-Deploy: Frontend `ultimate-3d-studio.js` SHA-256 `ed60c6f2fc917e56c94fcc46c5452381df1e388571aadf6ccfe1c96a58471184`, CSS unverändert `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Backend-Dateien `commands.py`, `provider_bambu_lan.py`, `provider_bambu_lan_v2.py`, `runtime.py`, `api.py` live kopiert.
- Backups: `/homeassistant/pcc-backups/v6-source-20261001-frontend-http-gates/`, `/homeassistant/pcc-backups/v6-frontend-20261001-frontend-http-speed-gates/`, `/homeassistant/pcc-backups/v6-backend-20261001-frontend-http-speed-gates/`.
- Verifiziert: `node run_frontend_tests.mjs` grün (`26 passed` plus Produktionsbuild), `npm run typecheck` grün, `python3 -m pytest tests -q --tb=short` grün (`257 passed`), Live-Backend `py_compile` grün.
- Keine Druckerbewegung, kein neuer Slicejob und kein Druckstart ausgelöst. Backend-Runtime-Aktivierung braucht später Integration-/HA-Core-Reload.

## 2026-10-01 – HA-Restart, Slicing-E2E und Direktdruck-Funktionstest bestanden

- Home Assistant Core nach Backend-Deploy neu gestartet; V6-Komponente wurde ohne Traceback geladen.
- Live-Healthchecks nach Restart: HA `running`, Slicing-Server `ready` auf `127.0.0.1:8099`, Frontend-Hash weiter `ed60c6f2fc917e56c94fcc46c5452381df1e388571aadf6ccfe1c96a58471184`.
- Slicing-E2E-Test mit kleinem Probe-STL ausgeführt: Job `codex-v6-e2e-after-ha-restart-20261001-003740`, Status `completed`, Artefakt 62.708 Bytes, 14 ZIP-Einträge, `Metadata/plate_1.gcode`, 16.562 G-Code-Zeilen, 5.401 Extrusionsbewegungen.
- Direktdruck-Prepare zunächst als echter Runtime-Fehler aufgefallen: `Ultimate3DStudioRuntime.async_upload_print_artifact()` nahm `on_progress` noch nicht an. Runtime-Vertrag repariert und live deployt; neuer Runtime-Hash `3323fc38afbe5ffb9d8820f3e9db8f6cdfe9e6185640d1c3986d4cb9a800a6f2`; HA Core danach erneut neu gestartet.
- Direktdruckfähigen Mini-Job mit autoritativem externer-Spule-Materialplan geslicet: `codex-v6-directprint-mini-20261001-004403`, Status `completed`.
- Direktdruck-Prepare erfolgreich: Remote-Datei `codex-v6-slice-probe-20260930_Druckplatte1.gcode.3mf`, 64.958 Bytes, SHA-256 `c653380d591610ed6d884a54e4e91687960f34c2b7dce0735d0f72d2ed2041f0`, G-Code validiert mit 16.562 Zeilen und 4.903 Extrusionsbewegungen; `print_started: false`.
- Echter Direktdruck-Funktionstest mit ausdrücklicher Freigabe ausgeführt: Start wurde vom Bambu A1 angenommen (`project_file`, `accepted: true`, `transport_delivered: true`, `response_received: true`, Materialquelle `external_spool`, kein AMS-Mapping). Direkt danach Stop-Befehl gesendet und bestätigt (`accepted: true`, `confirmed: true`, `attempts: 1`, finaler Druckerzustand `failed`, aber `ready: true`, kein aktueller Job).
- Puppet repariert teilweise: Split-DNS im Puppet-Container auf interne HA-IP gesetzt; Screenshots liefern wieder HTTP 200. UI-Screenshot-Abnahme bleibt eingeschränkt, weil HA/Puppet beim Testpfad sichtbar auf dem Studio-Panel bleibt und DOM-Text im manuellen Puppeteer-Dump leer war. Funktionale API-/Slicing-/Druckpfade sind davon unabhängig geprüft.
- Verifiziert: `ha core check --no-progress` grün, `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`26 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`).
- Backups: `/homeassistant/pcc-backups/v6-before-ha-restart-20261001-0031-before-ha-restart/` und `/homeassistant/pcc-backups/v6-runtime-upload-progress-20261001-0046/`.

## 2026-10-01 – Puppet-/HA-Panel-Routing für V6-Workspaces repariert

- Ursache der eingeschränkten Puppet-Abnahme behoben: HA-Testdashboard hatte nur die View `studio`, während Puppet `/3d-studio-v6-test/slicing-server` als HA-Panel-Pfad öffnet. Das Testdashboard enthält jetzt echte View-Pfade für `steuerung`, `studio`, `galerie`, `ams`, `profile`, `aufgaben`, `verlauf`, `system` und `slicing-server`.
- Frontend-Routing gehärtet: `parseRoute()` versteht jetzt auch HA-Panel-Pfade mit Prefix, und `initialRoute()` nutzt bei fehlendem Hash zuerst `location.pathname`, bevor der zuletzt gespeicherte Workspace aus `localStorage` greift.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `01a9e2d63eb630dee5a652e025c10fa7fcba49229adc03cf4c6f0fe0f4c25365`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster auf den neuen JS-Hash gesetzt.
- HA Core neu gestartet, Puppet-Container neu gestartet und Split-DNS im Puppet-Container erneut gesetzt. Frischer Puppet-Screenshot `/tmp/v6-puppet-slicing-fresh.png`, 75.621 Bytes, SHA-256 `e8a4755ca9043ddcb54253151df262b6efa5617d58cd8cc22dcb5b80f6d89235`.
- Headless-DOM-Abnahme bestätigt: `ultimate-3d-slicing-server-workspace` ist gerendert, `Slicing-Server`, `Neuer Auftrag` und `Serverdiagnose` sind sichtbar, `Steuerzentrale Liveübersicht` ist nicht aktiv; neuer Bundle wurde mit HTTP 200 geladen.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`26 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, Slicing-Server `/api/v1/health` `ready`.
- Backups: `/homeassistant/pcc-backups/v6-puppet-route-prefix-20261001-005523/`, `/homeassistant/.storage/lovelace.3d_studio_v6_test.bak-v6-workspace-views-20261001-010216`, `/homeassistant/pcc-backups/v6-initial-route-path-20261001-010658/`.

## 2026-10-01 – CAD-Grundformen Kreis/Rechteck/Linie stabil ergänzt

- Erster Zeichen-/CAD-Block umgesetzt: `Rechteck`, `Kreis` und `Linie` sind jetzt als flache, slicebare Studio-Geometrien im Menü `Einfügen` verfügbar. Damit sind die zuvor fehlenden/defekten Kreis- und Rechteck-Grundformen nicht mehr nur Dreiecks-/Import-Workarounds.
- Geometrievertrag erweitert: `PrimitiveKind` kennt nun `rectangle`, `circle` und `line`; die Formen erzeugen echte Meshes mit definierter Höhe, Bounds, Normalen und Dreiecken und können wie andere Objekte zentriert, skaliert, gefärbt, exportiert und geslicet werden.
- Legacy-/Shell-Labels mitgezogen, damit alte Studio-Shells und TypeScript-Pfade nicht am erweiterten Primitive-Typ brechen.
- Regressionstest ergänzt: `CAD flat primitives create slicable rectangle circle and line meshes` prüft Bounds und Dreieckszahlen für Rechteck, Kreis und Linie.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `295d61387b1f6d76e56194eab6114d8c1cbfbb23cd64e31fae7a03b7554cde97`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster auf den neuen JS-Hash gesetzt und HA Core neu gestartet.
- Puppet/DOM-Abnahme bestätigt: Studio lädt den neuen Bundle mit HTTP 200; Menü `Einfügen` enthält `Rechteck`, `Kreis`, `Linie` und weiterhin `First‑Layer‑Test`.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`27 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, Slicing-Server `/api/v1/health` `ready`.
- Keine Druckerbewegung, kein neuer Slicejob und kein Druckstart ausgelöst. Nächster Zeichenblock bleibt Pinsel/Radierer/Text mit Interaktion und Rahmen-Preview.
- Backup: `/homeassistant/pcc-backups/v6-cad-flat-primitives-20261001-021527/`.

## Architekturregeln

- Keine DOM-Enhancer, MutationObserver, Prototype-Manipulationen oder nachträglichen Runtime-Patches.
- Funktionen werden vollständig in den kanonischen TypeScript-/Python-Komponenten implementiert.
- V5 und bestehende Gallery-Daten bleiben unangetastet.
- Jeder Live-Deploy benötigt vollständiges Gate, Backup, SHA-256-Prüfung, atomaren Austausch und Rollbackpfad.
- Kein realer Druckstart ohne explizite zweistufige Benutzerfreigabe.

## 2026-10-01 – CAD-Textprimitive als slicebares Mesh ergänzt

- Nächster Zeichen-/CAD-Block umgesetzt: `Text` ist im Menü `Einfügen` verfügbar und erzeugt ein flaches, erhöhtes Mesh statt eines DOM-/SVG-Overlays.
- Geometrievertrag erweitert: `PrimitiveKind` kennt nun `text`; `createTextGeometry()` erzeugt deterministische Blockglyphen für Buchstaben/Ziffern mit echten Dreiecken, Bounds und Normals, sodass Text wie andere Objekte auswählbar, skalierbar, exportierbar und slicebar bleibt.
- Aktive und Legacy-Studio-Pfade mitgezogen: V2-UI, Legacy-UI, V2-Workspace, Legacy-Workspace und Shell-Labels kennen `Text`.
- Regressionstest ergänzt: `CAD text primitive creates a slicable raised letter mesh` prüft Dreieckszahl, Bounds und Höhe des Text-Meshs.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `493ca65299d50bf95d4ff302a2a4f01fcab1ca1af19128494cbbf5faa776d87a`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster auf den neuen JS-Hash gesetzt und HA Core neu gestartet.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`28 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, HA nach Restart `running`, Slicing-Server `/api/v1/health` `ready`.
- Puppet-Hinweis: Headless-Puppet konnte den HA-Panel-DOM in diesem Lauf erneut nicht als Text auslesen; Live-Datei, Resource-Hash und Server-Health sind geprüft. Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-cad-text-primitive-20261001-0228-cad-text-primitive/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0232-cad-text-primitive/`.

## 2026-10-01 – CAD-Textdialog für eigenen Text ergänzt

- Text ist nicht mehr nur ein Default-Primitive: `Einfügen → Text` öffnet im aktiven V2-Studio den vorhandenen V6-Aktionsdialog und erzeugt aus der Benutzereingabe ein flaches, slicebares 3D-Mesh.
- Der Textpfad nutzt den kanonischen Dialog (`v6-action-dialog`) und `createTextGeometry(value)`; leere oder abgebrochene Eingaben erzeugen kein Objekt.
- Eingefügte Textobjekte werden passend benannt (`Text: …`), auf der aktiven Druckplatte zentriert, selektiert und als normale Mesh-Instanz weiterverarbeitet.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `d73ca6596c0e60f79abd9287c86af6bff6b56149fd35dde6cf8823cbd8d5eacd`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert und HA Core neu gestartet.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`28 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, Live-Hash/Resource-URL geprüft, Slicing-Server `/api/v1/health` `ready`, Live-Bundle enthält Dialog-Textpfad.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-cad-text-dialog-20261001-0310-cad-text-dialog/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0314-cad-text-dialog/`.

## 2026-10-01 – CAD-Radierer als Canvas-Werkzeug ergänzt

- Nächster Interaktionsblock umgesetzt: Die Studio-Toolbar enthält jetzt `Radierer` als eigenes Zeichen-/Bearbeitungswerkzeug.
- Der Radierer ist vom Transform-Gizmo getrennt: Aktivieren setzt das Studio zurück auf Auswahlmodus, markiert den Radierer-Button aktiv und zeigt den Status `Radierer aktiv: Objekt anklicken, um es zu entfernen.`.
- Canvas-Klick mit aktivem Radierer entfernt das gepickte Objekt direkt, inklusive Materialzuweisung/Selektion, invalidiert die aktive Platte und bleibt über den bestehenden Audit-/Renderpfad nachvollziehbar.
- Der normale Löschen-Pfad nutzt dieselbe entfernungssichere Objektfunktion; Transformieren, Mehrfachauswahl und bestehende Menüaktionen bleiben unverändert.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `68ca4f0b03240eccd0520bf2582ecf5b2599ba4d0b70fc2d33e853ae2d72f666`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert und HA Core neu gestartet.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`28 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, HA nach Restart erreichbar, Slicing-Server `/api/v1/health` `ready`, Live-Bundle enthält Radierer-Label und Draw-Tool-State.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-cad-eraser-tool-20261001-0318-cad-eraser-tool/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0321-cad-eraser-tool/`.

## 2026-10-01 – CAD-Drag-Rahmen-Preview ergänzt

- Nächster Interaktionsblock umgesetzt: Im Studio erscheint beim Ziehen auf leerer Canvas-Fläche im Auswahlmodus ein sichtbarer Drag-Rahmen.
- Die Preview ist als Shadow-DOM-Overlay in der Stage umgesetzt (`selection-frame`) und verändert noch keine Modellgeometrie; sie ist damit die sichere Grundlage für spätere Rechteck-/Mehrfachauswahl und Zeichen-Drag-Werkzeuge.
- Linkes Ziehen auf leerer Fläche erzeugt den Rahmen, Loslassen oder Abbruch entfernt ihn wieder; Objektklick, Radierer, Transform-Gizmos und rechte Maustaste für Ansicht bleiben getrennt.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `6c59b4cb8d7b4048cce498b6554bf07e2974dfb7046b1dd2825c96e6cc638554`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert und HA Core neu gestartet.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`28 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, HA nach Restart erreichbar, Slicing-Server `/api/v1/health` `ready`, Live-Bundle enthält `selection-frame`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-selection-frame-preview-20261001-0328-selection-frame-preview/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0331-selection-frame-preview/`.

## 2026-10-01 – CAD-Pinselstriche als slicebare Meshes ergänzt

- Nächster Zeichenblock umgesetzt: Die Studio-Toolbar enthält jetzt `Pinsel`; Ziehen auf dem Druckbett erzeugt einen flachen, slicebaren `Pinselstrich` als echtes Mesh.
- Der Viewport kann Mauspositionen jetzt auf die Druckbett-Ebene projizieren (`platePoint()`), inklusive Ray/Plane-Schnitt aus der aktuellen Kamera. Dadurch landen Pinselstriche auf der Platte statt als ungenaue Bildschirm-Overlays.
- Neue Geometriefunktion `createStrokeGeometry(length, thickness, height)` erzeugt deterministische flache Striche mit Bounds, Normals und Dreiecken. Der Workspace setzt Länge, Mittelpunkt und Rotation aus Start-/Endpunkt des Drags.
- Der vorhandene Drag-Rahmen wird während des Pinselziehens als visuelles Feedback wiederverwendet; abgebrochene/kurze Drags erzeugen weiterhin ein kleines, slicebares Segment statt kaputter Nullgeometrie.
- Regressionstest ergänzt: `CAD brush stroke geometry creates a thin slicable mesh` prüft Dreieckszahl, Bounds und Höhe.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `a119923dda65fdc91cb13e1e0759bd56b66cb085307d94b3f219789e18a66c39`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert und HA Core neu gestartet.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`29 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, HA nach Restart erreichbar, Slicing-Server `/api/v1/health` `ready`, Live-Bundle enthält Pinsel-Label und `platePoint`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-cad-brush-stroke-20261001-0336-cad-brush-stroke/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0340-cad-brush-stroke/`.

## 2026-10-01 – CAD-Rechteckauswahl über Drag-Rahmen aktiviert

- Der zuvor eingeführte Drag-Rahmen wählt jetzt tatsächlich Objekte im Rahmen aus, statt nur als Preview zu dienen.
- Der Viewport bietet dafür `pickRect(startClientX, startClientY, endClientX, endClientY)`, projiziert sichtbare Objekt-Bounds in Canvas-Koordinaten und gibt alle geschnittenen Objekt-IDs zurück.
- Loslassen des Auswahlrahmens setzt die Auswahl auf die gefundenen Objekte; Strg/Meta/Shift ergänzt die bestehende Auswahl additiv. Objektklick, Radierer und Pinsel bleiben getrennte Pfade.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `823e7a7ea26133949d1f03f0292a515fc5a86d9b9ce7ce022a2aa94c8d763aae`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert und HA Core neu gestartet.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`29 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), `ha core check --no-progress` grün, HA nach Restart erreichbar, Slicing-Server `/api/v1/health` `ready`, Live-Bundle enthält `pickRect`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-rectangle-selection-20261001-0345-rectangle-selection/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0348-rectangle-selection/`.

## 2026-10-01 – CAD-Objektliste und Auswahl-Vertrag nachgezogen

- Objektliste im aktiven V2-Studio strukturiert: Der linke Objektbereich zeigt jetzt eine sichtbare Trennlinie `Malbereich`, damit importierte und gezeichnete Objekte unter dem Arbeitsbereich klar gruppiert sind.
- Initialer Shell-Render und nachgeladener Workspace-Render nutzen denselben `Malbereich`-Header; damit verschwindet die Überschrift nicht bei Re-Render, Plattenwechsel oder leerer Objektliste.
- Tastaturbedienung ergänzt: `Backspace` entfernt markierte Objekte jetzt wie `Delete`, während `Strg+A`, Shift-Bereichsauswahl und additive Auswahl weiter über den vorhandenen Selection-Vertrag laufen.
- Regressionstests erweitert: Frontend-Logic deckt Select-All, Shift-Range und Toggle-Auswahl ab; Python-UI-Vertrag prüft `Malbereich`, Styling-Klasse und Backspace-Löschpfad.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `3d9710ad04c674119c151117543ac6033fc1686f3bae0b3520578108ba10fad9`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API meldet `RUNNING`, Slicing-Server `/api/v1/health` `ready`, Live-Hash und Resource-URL geprüft. Der separate `ha core check` konnte in diesem SSH-Kontext wegen fehlender CLI-Token-Umgebung nicht erneut ausgeführt werden; HA lief nach dem Restart und V6-Logs waren ohne Traceback.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Puppet-Nachabnahme mit Puppet-Token ergänzt: `/data/options.json` enthält einen gültigen `access_token`; HA-API `/api/config` und Live-Asset `/local/3d-studio-v6/ultimate-3d-studio.js?...` antworten mit HTTP 200, Bundle enthält `Malbereich` und `Backspace`.
- Nach Puppet-Container-Neustart wurde Split-DNS erneut gesetzt (`homeassist.bad-timing.eu` auf Docker-Gateway `172.30.32.1`), damit Puppet HA intern erreicht statt extern auf die WAF-IP zu laufen.
- Frischer Puppet-Service-Screenshot: `/tmp/v6-puppet-selection-object-list.png`, 192.197 Bytes, SHA-256 `ed5633797f06b2e37a4d021cfa3466e3e751498f0eb4b956edeacc25d41efc87`.
- Backups: `/homeassistant/pcc-backups/v6-selection-object-list-20261001-072149-selection-object-list/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0724-selection-object-list/`.

## 2026-10-01 – CAD-Filamentprofil-Liste scrollbar gemacht

- Filamentprofil-Liste im CAD-/Studio-Seitenbereich kompakt gemacht: Der hierarchische Profilbaum liegt jetzt in `filament-tree-scroll` mit begrenzter Höhe, stabiler Scrollbar und eigenem Overscroll-Verhalten.
- AMS- und externe-Spule-Auswahl bleiben unverändert: AMS zeigt weiterhin Cloud/Lokal-Profile im Baum, externe Spule bleibt Einzelprofil-Auswahl über das kompakte Select-Feld.
- Regressionstest ergänzt: Der Materialsystem-UI-Vertrag prüft `filament-tree-scroll`, `overflow-y:auto` und `scrollbar-gutter:stable`, damit die Profil-Liste nicht wieder das Panel sprengt.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `b2f018c67174529da8c73e1695236c8d2409c35dbc39ab161d5b67385d060c93`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`.
- Puppet-Token-Abnahme: HA-API und Live-Asset mit Puppet-Token HTTP 200; Live-Bundle enthält `filament-tree-scroll` und `overflow-y:auto`. Frischer Puppet-Service-Screenshot `/tmp/v6-puppet-filament-scroll.png`, 192.588 Bytes, SHA-256 `66080b6331f31315a9e1ad41611de311b07e61757b8792fe303d6fa50dee132d`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-filament-scroll-20261001-074228-filament-scroll/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0743-filament-scroll/`.

## 2026-10-01 – Studio-Cloud-Auswahl aus Profilbar entfernt

- Studio-Profilbar weiter aufgeräumt: Die separate `BambuLab Cloud`-Auswahl oben im CAD-Studio wurde entfernt, damit Cloud-Abgleich und Cloud-Verwaltung eindeutig im `Profile`-Workspace bleiben.
- Cloud-Profile bleiben im Filamentprofil-Baum verfügbar; AMS- und externe-Spule-Auswahl sowie Materialquellen-Umschaltung bleiben unverändert funktionsfähig.
- Profilbar-Raster wurde von fünf auf vier Profilspalten reduziert, damit die rechte Menüstruktur kompakter bleibt.
- Regressionstest ergänzt: Studio-Bundle darf `data-cloud-filament-profile` und `#cloudFilamentProfileChanged` nicht mehr enthalten; `#cloud-sync` bleibt im `Profile`-Workspace nachweisbar.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `6e645bb845c7b8e30341e30144d62acb711e700619ac5c3cf6896ee53e4c637f`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`, Puppet-Token-Assetprüfung HTTP 200.
- Frischer Puppet-Service-Screenshot: `/tmp/v6-puppet-studio-cloud-cleanup.png`, 192.588 Bytes, SHA-256 `66080b6331f31315a9e1ad41611de311b07e61757b8792fe303d6fa50dee132d`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-studio-cloud-select-cleanup-20261001-074517-studio-cloud-select-cleanup/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0746-studio-cloud-select-cleanup/`.

## 2026-10-01 – Profilbezeichnungen im aktiven Profile-Workspace vereinheitlicht

- Aktiven Profile-Workspace (`profile-workspace-v3.ts`) begrifflich an die Studio-Profilbar angepasst: Prozess-Tab heißt jetzt `Druckprofil`, Druckplatten-Tab heißt `Druckplatte`.
- Legacy-V2-Workspace wurde ebenfalls auf Singular gezogen, ist aber nicht der aktive gebündelte Workspace; die eigentliche Live-Änderung sitzt in V3.
- Regressionstest ergänzt: `profile-workspace-v3.ts` muss `label: "Druckprofil"` und `label: "Druckplatte"` enthalten und darf die alten Tab-Labels `Druckprofile`/`Druckplatten` nicht mehr führen. Andere legitime Texte wie MakerWorld-`Druckprofile und Platten` bleiben unberührt.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `e8f93a39c2966f1d6f6efbb2774856169d83aa4dcd831d6a5fcdc05f9a438c10`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`, Puppet-Token-Assetprüfung HTTP 200.
- Frischer Puppet-Service-Screenshot: `/tmp/v6-puppet-profile-label-singular.png`, 188.972 Bytes, SHA-256 `058393793ad462447d80e037e643f11d9d1289010131f1350770232592e51a37`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-profile-label-singular-20261001-075027-profile-label-singular/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0751-profile-label-singular/`.


## 2026-10-01 – Externe Spule im CAD-Studio visuell hervorgehoben

- Materialquelle `Externe Spule` im aktiven V2-CAD-Studio sichtbarer gemacht: Der Einzelmaterialpfad zeigt jetzt eine eigene `external-spool-card` mit Badge `EXT`, Farbswatch, Profilname und Hinweis `Studio-Quelle` vor dem Profil-Select.
- Externe Spule bleibt fachlich unverändert ein Einzelmaterialpfad ohne AMS-Mapping und ohne automatische Materialwechsel; geändert wurde nur die Studio-Seitenleisten-Darstellung.
- Styling ergänzt: `external-spool-card`, `external-spool-badge` und `external-spool-color` geben der Quelle eine BambuLab-nahe, kompakte Kartenoptik im bestehenden Panel.
- Regressionstest ergänzt: Der Materialsystem-UI-Vertrag prüft `external-spool-card`, `external-spool-badge` und `Studio-Quelle`.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `a3a488fce14f909972bdc59e5bbb2e8e8e4b836cc5154e990f3b9e82f2453aba`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`.
- Puppet-Token-Abnahme: Live-Asset mit Puppet-Token HTTP 200; Bundle enthält `external-spool-card` und `Studio-Quelle`. Generischer Puppet-Service-Screenshot `/tmp/v6-puppet-external-spool-card.png`, 188.972 Bytes, SHA-256 `058393793ad462447d80e037e643f11d9d1289010131f1350770232592e51a37`; der Screenshot-Pfad öffnete denselben Studio-Grundzustand wie die vorherige Profilbezeichnungsabnahme, deshalb ist die codegenaue Asset-Prüfung hier der maßgebliche Nachweis.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-studio-external-spool-card-20261001-075317-studio-external-spool-card/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0754-external-spool-card/`.


## 2026-10-01 – CAD-Studio Filamentmodus und Profilbar bereinigt

- Rechte Material-/Filamentbedienung weiter vereinfacht: Das separate obere Profilbar-Dropdown `Externes Filament` wurde entfernt; die externe Spule wird nur noch im rechten Filamentpanel ausgewählt und dort als Kartenansicht angezeigt.
- Der Modus `Farben` heißt in der oberen Modusleiste jetzt `Filament`; im Menü `Ansicht` heißt der Eintrag `Filamentprofile`. Damit passt der Einstieg besser zur tatsächlichen Material-/Filamentaufgabe.
- Moduswechsel auf Filament nutzt jetzt einen zentralen `#setStudioMode()`-Pfad, setzt Preview/Viewport/Sidebar konsistent und entfernt alte globale UI-Fehlerboxen (`#global-error-box`), damit beim Öffnen des Filamentbereichs kein veralteter Fehler unten rechts hängen bleibt.
- Regressionstest ergänzt: Der UI-Vertrag prüft entfernte Profilbar-Dopplung, neuen Filament-Modus-Text und den zentralen Moduswechselpfad.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `73fbbf1343995b865f33a7d4827a09811bbc925b9f7c613ff5b161bc2b9cfc02`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`.
- Puppet-Token-Abnahme: Live-Asset HTTP 200; Bundle enthält `Filament`, `Filamentprofile`, `Filamentmodus`, `global-error-box`, `external-spool-card`; die obere Profilbar enthält keinen `<span>Externes Filament</span>` mehr. Der verbleibende Klartext `Externes Filament` gehört zum Direktdruck-Fallbacklabel und nicht zur Profilbar.
- Frischer Puppet-Service-Screenshot: `/tmp/v6-puppet-studio-filament-mode-cleanup.png`, 188.972 Bytes, SHA-256 `058393793ad462447d80e037e643f11d9d1289010131f1350770232592e51a37`; der Screenshotpfad zeigt weiterhin denselben Studio-Grundzustand, daher ist die tokenbasierte Live-Assetprüfung der maßgebliche UI-Nachweis.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-source-20261001-0940-studio-filament-mode-cleanup/` und `/homeassistant/pcc-backups/v6-frontend-20261001-0941-studio-filament-mode-cleanup/`.


## 2026-10-01 – AMS-Slotkarten im CAD-Studio ergänzt

- Rechten Filamentbereich weiter an eine BambuLab-nahe Materialansicht angenähert: Im AMS-Pfad erscheint jetzt eine eigene `AMS Lite Slots`-Sektion mit Slotkarten (`ams-slot-card`) für belegte AMS-Slots.
- Jede Slotkarte zeigt Slotnummer, Filamentfarbe, Material/Tray-ID und Status (`AMS` oder `Zugewiesen`). Bei ausgewähltem Objekt kann ein Slot direkt per Klick zugewiesen werden; das bestehende Select-Fallback bleibt erhalten.
- Der Filamentprofilbaum wurde darunter als `Filamentprofil-Katalog` beschriftet, damit klar getrennt ist: physische Zuordnung über AMS-Slots, Profilverwaltung/-sichtbarkeit über den Katalog.
- Externe Spule bleibt unverändert der Einzelmaterialpfad mit eigener `external-spool-card`; AMS und externe Spule bleiben über dasselbe Materialquellen-Menü auswählbar.
- Regressionstest ergänzt: Der Materialsystem-UI-Vertrag prüft `ams-slot-grid`, `ams-slot-card`, `AMS Lite Slots`, `Filamentprofil-Katalog` und `data-material-choice-card`.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `01992969b9493e2d28390da8d59e3e36cf73e07c6e8d4faafffadbeee2b95c76`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`.
- Puppet-Token-Abnahme: Live-Asset HTTP 200; Bundle enthält `ams-slot-grid`, `ams-slot-card`, `AMS Lite Slots`, `Filamentprofil-Katalog`, `data-material-choice-card` und `external-spool-card`.
- Frischer Puppet-Service-Screenshot: `/tmp/v6-puppet-studio-ams-slot-cards.png`, 188.972 Bytes, SHA-256 `058393793ad462447d80e037e643f11d9d1289010131f1350770232592e51a37`; der Screenshotpfad zeigt weiterhin denselben Studio-Grundzustand, daher bleibt die tokenbasierte Live-Assetprüfung der maßgebliche UI-Nachweis.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-source-20261001-1036-studio-ams-slot-cards/` und `/homeassistant/pcc-backups/v6-frontend-20261001-1038-studio-ams-slot-cards/`.


## 2026-10-01 – Mobile Studio-Scrollbarkeit und redundantes Druckerprofil entfernt

- HA-App/Mobile-Layout des CAD-Studios repariert: Objektliste und rechte Seitenleiste werden unter 850 px nicht mehr auf `max-height:300px` als innere Scrollcontainer begrenzt, sondern vollständig im Seitenfluss gestapelt (`max-height:none`, `overflow:visible`, `flex-direction:column`). Dadurch kann die Home-Assistant-App wieder bis zu den unteren rechten Studio-Optionen scrollen.
- Redundantes Feld `Druckerprofil` aus der oberen Studio-Profilbar entfernt. Die Düse bleibt das maßgebliche Auswahlfeld; der bestehende Code zieht beim Düsenwechsel weiterhin automatisch das kompatible native Maschinen-/Druckerprofil nach.
- Profilbar-Zusammenfassung nutzt jetzt die gewählte Düse statt des versteckten Druckerprofils, damit dort keine 0,2-mm-Druckerprofil-Auswahl mehr als eigener Bedienpunkt erscheint.
- Profilbar-Raster von vier auf drei nachgelagerte Profilspalten reduziert, passend zum entfernten Feld.
- Regressionstest ergänzt: Der Materialsystem-UI-Vertrag prüft, dass `<span>Druckerprofil</span>` nicht mehr in der Studio-Profilbar steht und dass die Mobile-Scrollregeln `max-height:none`/`overflow:visible` im Bundle enthalten sind.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `b47d495a74bdc9bcdcbafe653aaa890b2441f5577a913087b0a084062f47285c`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`.
- Puppet-Token-Abnahme: Live-Asset HTTP 200; Bundle enthält `selection.nozzle_profile_id`, `max-height:none`, `overflow:visible`, `flex-direction:column` und enthält kein `<span>Druckerprofil</span>` mehr.
- Frischer mobiler Puppet-Service-Screenshot: `/tmp/v6-puppet-mobile-scroll-no-printer-profile.png`, 121.308 Bytes, SHA-256 `e29dd935e84374800eb1f40e5c38cda02b9f17aa0ddd2bf50f889ff8252369ed`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-source-20261001-1059-mobile-scroll-no-printer-profile/` und `/homeassistant/pcc-backups/v6-frontend-20261001-1100-mobile-scroll-no-printer-profile/`.


## 2026-10-01 – Mobile Bottom-Safe-Area für HA-App ergänzt

- Nach dem Mobile-Scroll-Fix wurde zusätzlicher Abstand für die untere Home-Assistant-/iOS-Navigationsleiste ergänzt: Im mobilen Studio-Layout erhält die rechte Seitenleiste jetzt `padding-bottom:calc(96px + env(safe-area-inset-bottom,0px))`.
- Damit bleiben die unteren Studio-Optionen auch in der Home-Assistant-App erreichbar und werden nicht von der violetten Bottom-Bar überdeckt.
- Regressionstest ergänzt: Der Materialsystem-UI-Vertrag prüft `safe-area-inset-bottom` und das zusätzliche `padding-bottom` im mobilen Studio-CSS.
- Live-Frontend neu gebaut und deployt: `ultimate-3d-studio.js` SHA-256 `1c23afd7bac33739eebef7556993b884225be50d42b82ef9ba44357652d67a49`, CSS SHA-256 `e73c2b38d3d7875bc57b60a5c9422ef6fd2bca196a7e9296094b8ad6f64ace75`; Lovelace-Resource-Cache-Buster aktualisiert.
- Verifiziert: `npm run typecheck` grün, `node run_frontend_tests.mjs` grün (`30 passed` plus Produktionsbuild), `python3 -m pytest tests -q --tb=short` grün (`257 passed`), HA-API `RUNNING`, Slicing-Server `/api/v1/health` `ready`.
- Puppet-Token-Abnahme: Live-Asset HTTP 200; Bundle enthält `safe-area-inset-bottom`, `padding-bottom:calc(96px`, offene Mobile-Scrollregeln und weiterhin kein `<span>Druckerprofil</span>`.
- Frischer mobiler Puppet-Service-Screenshot: `/tmp/v6-puppet-mobile-bottom-safe-area.png`, 121.308 Bytes, SHA-256 `e29dd935e84374800eb1f40e5c38cda02b9f17aa0ddd2bf50f889ff8252369ed`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/pcc-backups/v6-source-20261001-1104-mobile-bottom-safe-area/` und `/homeassistant/pcc-backups/v6-frontend-20261001-1104-mobile-bottom-safe-area/`.

## 2026-10-01 – Profil-/Düsen-Konsistenz und Queue-API repariert

- Backend-Fix ergänzt: `slicer_queue_views` wird beim V6-Setup registriert. Der zuvor live mit 404 antwortende Endpunkt `/api/ultimate_3d_studio_v6/v1/slicer/queue/status` antwortet nach HA-Core-Neustart mit HTTP 200.
- Profilruntime abgesichert: Wenn ein aktives Druckerprofil einen festen `nozzle_diameter_mm` trägt und dieser nicht zur gewählten Düse passt, wird automatisch ein passendes Druckerprofil mit gleichem Hersteller/Modell und passendem Düsendurchmesser gewählt. Damit kann eine 0,4-mm-Düse nicht mehr mit dem alten A1-0,2-mm-Druckerprofil gespeichert bleiben.
- Live-Selektion korrigiert: `printer_profile_id` steht jetzt auf `local.printer.bambu_a1_0_4`; `nozzle_profile_id` bleibt `local.nozzle.a1_0_4_hardened`; Prozess, Druckplatte und SUNLU-PETG-Filament blieben unverändert.
- Regressionstest ergänzt: `test_printer_profile_is_aligned_to_selected_nozzle_diameter` deckt den 0,2/0,4-Widerspruch ab.
- Verifiziert: `python3 -m pytest -q` grün (`258 passed`), `npm test -- --runInBand` grün (`30 passed` plus Produktionsbuild), Backend-Dateien per `py_compile` geprüft, HA-API `ready`, Queue-Status HTTP 200, Profile-Selektion live konsistent.
- HA-Core wurde einmal per Docker-Container-Neustart neu geladen, damit die neue HTTP-View-Registrierung aktiv ist.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backup: `/homeassistant/3D-Studio/backups/v6-startfix-20261001-150238/`.

## 2026-10-01 – Druckerprofil nozzle-neutral, Düsen separat auswählbar

- Profilstruktur korrigiert: Sichtbare Druckerprofile enthalten keine Düsenvarianten mehr. Das Druckerprofil beschreibt nur noch den Drucker (`Bambu Lab A1`).
- Düsen bleiben ausschließlich eigene manuelle Profile. Live sichtbar sind jetzt genau vier A1-Düsenprofile: `0,2 mm`, `0,4 mm`, `0,6 mm`, `0,8 mm`.
- V2-Profilruntime filtert doppelte/generische Düsenprofile, sobald die kanonischen lokalen A1-Düsen vorhanden sind. Dadurch gibt es keine doppelte Düsenauswahl über Druckerprofil und Düsenprofil.
- Live-Selektion gesetzt: `printer_profile_id=printer.bambu_a1`, `nozzle_profile_id=local.nozzle.a1_0_4_hardened`; Prozess, Druckplatte und SUNLU-PETG-Filament blieben unverändert.
- Verifiziert: Profilruntime-Dateien per `py_compile` geprüft, gezielte Profil-/Nozzle-Tests grün (`36 passed`), kompletter Python-Gate grün (`259 passed`), HA-Core neu gestartet, V6-Health `ready`, Live-Profil-API zeigt `printer_count=1` und `nozzle_count=4`.
- Kein Druckstart, keine Druckerbewegung, kein neuer Slicejob.
- Backups: `/homeassistant/3D-Studio/backups/v6-printer-profile-neutral-20261001-153257/` und `/homeassistant/3D-Studio/backups/v6-nozzle-profile-canonical-20261001-153530/`.
