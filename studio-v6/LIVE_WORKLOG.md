# LIVE_WORKLOG

## 2026-10-02 – V6 Local/Live/GitHub Konsolidierung

### Verbindlicher Scope

- Ausschließlich `v6` bearbeiten.
- V1–V5 / altes 3D-Printer-Control-Center nicht als V6-Quelle verwenden.
- Lokales V6-Repository ist die kanonische Entwicklungsbasis.
- Home Assistant ist der maßgebliche Live-Zustand.
- Öffentliches Repository `Taracraft/3D-Ultimate-Center` wird erst nach vollständigem Local↔Live-Abgleich als kanonischer Klon aktualisiert.
- Noch kein Rebuild.
- Keine Druckerbefehle / kein Druckstart in diesem Konsolidierungsschritt.

### Lokaler Repository-Stand

- Pfad: `F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Printer-Control-Center\v6`
- Branch: `feature/v6-ultimate-3d-printing-studio`
- Branch-Ref bei Prüfstart: `eed218777ac10666126df9fc8b654d5505cf6812`
- Lokale `docs/ROADMAP.md`: 88.877 Bytes und neuer als die HA-Kopie.
- Autoritative Vollroadmap vorhanden: `docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md`.

### Local ↔ Live Deploy-Vergleich

Aktiver Deploybestand, Logs/Runtime/Backups ausgeschlossen:

- 142 relevante Dateien verglichen.
- 117 SHA-256-identisch.
- 25 zunächst abweichend/gemeldet.
- 5 davon sind keine echten Abweichungen: die Systemd-Units liegen live unter `/etc/systemd/system`; alle fünf SHA-256 stimmen exakt mit lokal überein.
- `deploy-native-slicer.sh` ist ein Deployment-Helfer und muss nicht als Live-Runtimedatei vorhanden sein.
- `dispatch-job.sh` ist inhaltlich identisch; live enthält lediglich ein UTF-8-BOM vor dem Shebang.
- Live `SHA256SUMS` ist teilweise veraltet und entspricht nicht mehr allen tatsächlich installierten Dateien.

### Reale inhaltliche Backend-Divergenzen

Live-Neuerungen, die in die lokale Basis übernommen werden müssen:
- `bambu_direct_print.py`: robuste kanonische `.gcode.3mf`-Dateinamensnormalisierung.
- `profile_runtime.py`: Druckerprofil von Düse entkoppelt; düsenspezifische Druckerprofile ausgefiltert/ausgerichtet.
- `profile_runtime_v2.py`: kanonische A1-Düsenprofile, Dublettenfilter.
- Druckgeschwindigkeitspfad live enthält zusätzliche Logik; wird nicht blind übernommen, sondern gegen den lokal umfangreicheren Providerpfad gemerged.

Lokale, noch nicht vollständig live vorhandene Weiterentwicklungen:
- `materialize-bambu-multimaterial.py`: bemalte Dreiecke / Materialkanäle.
- `slicer_backend_router.py`: manueller Queue-Release-Vertrag.
- `slicer_plate_views_v2.py`: vollständiger Drucker-/Profil-/Material-/Kompatibilitätsvertrag für Batch.
- `slicer_queue_views.py`: Batch-Validierung vor Upload, max. 50 Dateien, 3MF-Vertrag, manual_release.
- `three_mf_mesh_graph.py`: Dreieck-zu-Materialkanal-Zuordnung.
- `runtime.py`: Filamentfarb-/AMS-Schreibpfad.
- `provider_bambu_lan.py` / `provider_bambu_lan_v2.py`: lokale Erweiterungen dürfen durch Live-Speed-Hotfixes nicht verloren gehen.
- `process_profile_contract.py`: lokale zusätzliche Support-Interface-Regel; Live enthält andere Regeln, daher Merge statt Überschreiben.

### Bereits sicher lokal gemerged

Vorher-Backup:
`v6/backups/2026-10-02-live-sync/before/`

Aus Live in lokal übernommen:
- `bambu_direct_print.py`
- `profile_runtime.py`
- `profile_runtime_v2.py`

### Frontend

- Lokaler Deploy-Build: gebaut 2026-10-02T06:08:04.561Z, JS 607.525 Bytes, SHA-256 `f3b756550c914805787ca710ccf3d32ba218ce3a9c60c63ab6b19aec2eb0b59b`.
- Live Buildmanifest: gebaut 2026-10-01T21:00:37.215Z.
- Live JS wurde danach separat verändert; aktuelle Datei 601.990 Bytes.
- Deshalb kein Live-Bundle blind zurück in Source kopieren. Zuerst Source-/Backend-Merge, danach lokales vollständiges Gate und neuer Build.

### Roadmap-Abgleich

Die Divergenzen passen zu den dokumentierten offenen/fortgesetzten Roadmap-Blöcken:
- Druckerprofil und Düse nicht doppelt führen.
- Filament-/AMS-/externe-Spulen-System.
- Malwerkzeuge und Material-Malen.
- Batch-Slicing/Warteschlange mit manueller Freigabe.
- Vollständiger Profil-/Kompatibilitätsvertrag.
- Roh-STL/Bambu-Slicing-Fix.
- G-Code-Bausteine / Profilverwaltung.
- MakerWorld vollständig.
- Kein Druckstart ohne Freigabevertrag.
- Vor Deploy: Backup, Gate, SHA-256, atomarer Austausch und Rollback.

### Nächste Schritte

1. Restliche inhaltliche Divergenzen Datei für Datei mergen, nicht überschreiben.
2. Lokalen Source-/Deploybaum vollständig testen.
3. Vollständiges V6-Qualitätsgate lokal grün bekommen.
4. Erst danach den geprüften lokalen Stand nach Home Assistant deployen.
5. Local↔Live erneut per SHA-256 vergleichen.
6. Erst bei Gleichstand den V6-Stand nach `Taracraft/3D-Ultimate-Center` spiegeln.
7. Rebuild erst nach erfolgreicher Dreifachsynchronität Local ↔ Live ↔ GitHub.


## 2026-10-02 Lokaler V6-Abgleich vor Homeassist-Synchronisierung

Kanonischer lokaler Projektpfad: `F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Ultimate Studio`. Lokale neuere Funktionen bleiben erhalten; GitHub ist nachrangig. Vor diesen Änderungen werden größen- und SHA-geprüfte Einzeldateibackups angelegt. Gate-Pfade folgen dem Projektordner, die verwaisten Primitive-Namen werden entfernt, Live-Dateinamensnormalisierung für `.gcode.3mf` und Speed-Dispatch im Basisprovider gezielt übernommen. AMS-Farbzuordnung, Provider V2, Profil-Enums und lokale Slicer-/Queue-Verträge bleiben erhalten. FTP-Tests bleiben vollständig gemockt; kein Druckerauftrag. Gates und Live-Abgleich stehen nach diesem Eintrag noch aus.

Gesamtgate 22:25 Europe/Berlin grün; erster HA-Abgleich 336 Dateien vollständig zurückgerollt, weil der vorhandene native Deploymenthelfer BOM-Python mit utf-8 statt utf-8-sig prüfte. Alle ursprünglichen HA-Hashes wiederhergestellt, Worker/Timer aktiv. Helfer gezielt korrigiert; erneutes Gesamtgate vor erneutem HA-Abgleich.


### Abschluss Local ↔ Homeassist, 2026-10-02

Gesamtgate 22:33:28 Europe/Berlin vollständig grün: 524 Python-Tests und 3 Subtests, 145 Frontend-Tests, Source-Policy, TypeScript, beide Builds und Compileall. Core-/API-Importpfade sind im neuen isolierten Projektroot nachgewiesen. Native Export-SHA256: 21544d85f18ee9225a5a8e6e4206d901d9d60b4903347c32d649480f39975efb.

337 Dateien mit Same-Day-Backup und atomarem Austausch konsolidiert. Backup: /var/lib/homeassistant/homeassistant/backups/20261002T203438Z-v6-local-ha-canonical. Native Deploy-/Healthprüfung und HA-Core-Konfigurationsprüfung erfolgreich. HA-Core neu gestartet und laufend. Anschließend 568 lokale Quell-/Hilfsdateien gegen HA-Quellkopie, 139 native Deploy-Ziele sowie Worker-Core/API und vier Workerabhängigkeiten per SHA geprüft: null Abweichungen. Ausgeliefertes Frontend: HTTP 200, text/javascript, 607533 Bytes, SHA256 2bc55c5ec1da45b2fd3b3b681db8c01b0094dc168aa6a49baccd71dbd4e658f9. Worker ready, alpha5, API v2; Worker und Timer aktiv.

Kein Slice, Job-Release, Druckerupload oder Druckstart. GitHub unverändert und nachrangig. Kein Fresh-Install/Rebuild der Systeme. Paketbuilds waren ausschließlich die vorgeschriebenen Gates. Visuelle Live-Abnahme offen: bestehendes Puppet liefert Connection Failed, keine PNG-Abnahme behauptet. Git-Metadaten des isolierten lokalen Ordners sind weiter nicht nachgewiesen. Dieser Abschluss betrifft die inventarisierten aktiven V6-Quellen und deploybaren Ziele, nicht historische Hilfs-/Backupdateien oder Runtime-Daten.


## 2026-10-02 Puppet auf Port 5000 wieder verbunden

Zwei Ursachen direkt im vorhandenen Add-on nachgewiesen: Die gespeicherte HA-URL mit abschließendem Slash erzeugte //api/websocket; die nur im laufenden Container gesetzte Split-DNS-Zuordnung verschwand beim Add-on-Neustart. Supervisor-Optionen auf https://homeassist.bad-timing.eu:8123 normalisiert, vorhandenen gültigen Token unverändert erhalten. Konfigurationsbackup im Add-on: /data/options.json.bak-2026-10-02T20-51-01-864Z-v6-url-normalization, Modus 0600.

Split-DNS dauerhaft über den idempotenten Hostdienst v6-puppet-hosts.service und Timer abgesichert. Gateway aus Docker-Netz hassio ermittelt; ausschließlich Puppet-Hosts-Zuordnung ergänzt. Script und Units unter deploy/homeassistant/host/puppet dokumentiert. Same-Day-Backup: /var/lib/homeassistant/homeassistant/backups/20261002T205742Z-puppet-split-dns. Bash-Syntax und systemd-Units geprüft, Timer aktiv. Erneuter Add-on-Neustart: Zuordnung automatisch wiederhergestellt, Startseite Screenshot Preview statt Connection Failed.

V6-Screenshot über http://127.0.0.1:5000/3d-studio-v6-test/0?viewport=1600x1000&wait=5000 erfolgreich: HTTP 200, image/png, gültige PNG-Signatur, 101646 Bytes, SHA256 b44fdd9384df0991efa967ce6fa441734c6e29b0b60a907a86c1daec84c42956. Visuell verbundenes V6-Dashboard bestätigt. Dies ist ein Screenshot-/Verbindungsnachweis; interaktive Malwerkzeug-, Profil- und Touch-Abnahmen bleiben offen. Kein Slice, Release, Upload oder Druckstart. GitHub-Nachzug folgt vor Fresh-Install/Rebuild.
