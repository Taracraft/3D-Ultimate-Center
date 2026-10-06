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


### GitHub-Nachzug nach Local ↔ Homeassist, 2026-10-02

572 kanonische Quell-/Hilfsdateien direkt aus dem neuen lokalen Repo erneut gegen HA-Quellkopie und erwartete SHA256 geprüft: null Abweichungen. GitHub-Zielpfade separat abgeglichen: 576 Dateien einschließlich vier zusätzlicher kanonischer Worker-Abhängigkeitskopien, null Git-Blob-Abweichungen. Ältere parallele Workerquellen bleiben ausschließlich unter studio-v6/deploy/homeassistant/3d-printer-slicing-server erhalten; aktiver slicing-server folgt dem geprüften host/Worker. Historische Komponenten und übrige öffentliche Dateien unverändert.

Veröffentlichter Synchronisierungscommit: 430fdda6285c5df57a0c89aa94b21c6167a4fdfe. Git-Baum: 6a44718b936147299ab2ba92e732910be176a674. Vorheriger main-Stand als backup/v6-before-local-ha-sync-20261002 gesichert. main ohne Force aktualisiert und nach Veröffentlichung verifiziert. CI ausdrücklich übersprungen, damit kein Rebuild vor diesem Dreifachabgleich startet. Dieser Eintrag wird anschließend ebenfalls bytegenau lokal, auf HA und öffentlich nachgezogen.

Puppet über Host-Port 5000 verbunden und Neustartfestigkeit nachgewiesen. Nächste Roadmap-Abnahmen bleiben interaktive Malwerkzeuge/Materialprofile/Touch, Queue-End-to-End und 50-Dateien-Batchleistung; echte Slice-/Release-/Upload-/Druckaktionen erfordern weiterhin ausdrückliche Freigabe. Ein Fresh-Install ist noch nicht durchgeführt. Der ältere öffentliche rebuild-homeassist.sh wurde nicht ausgeführt; er berücksichtigt unter anderem alte V5-Komponenten und muss vor einer etwaigen Verwendung am aktuellen V6-Vertrag geprüft werden.


## 2026-10-02 MakerWorld-Empfehlungen und laufende Synchronisierung

Neue Benutzerregel: Jede Projektänderung wird in den kanonischen lokalen Ordner, die HA-Quellkopie und das öffentliche GitHub übernommen; produktive HA-Ziele erst nach grünem Gesamtgate. Lokaler Pfad bleibt F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Ultimate Studio. GitHub ist Taracraft/3D-Ultimate-Center.

Roadmap-Arbeitspunkt MakerWorld / Ideen für Sie: eingebettete Empfehlungen erhalten; normalisierte Suchergebnisse behalten Vorschaubilder und Zähler. Öffentliche numerische Design-ID wird von opaken Download-IDs getrennt; verschachtelte Ersteller-/Profilmetadaten werden nicht als Empfehlungen angeboten. Selbstempfehlungen und Dubletten entfernt. Optionale Anreicherung läuft parallel mit Budgets: Kommentare 8 Sekunden, direkte Empfehlungen 3 Sekunden plus Suchfallback 5 Sekunden. Teilergebnisse bleiben erhalten; optionale Ausfälle führen nicht zum erneuten Laden gültiger Modelldetails. Eingebettete Kommentare werden mit weiteren Kommentaren zusammengeführt.

Sieben gezielte Regressionstests ergänzen die vorhandenen Detailtests: Suchmedien/Zähler, öffentliche ID/Metadaten, eingebettete Empfehlungen, Zusammenführung, langsame Endpunkte/Teilergebnisse, vollständige Einbettung und Abbruchweitergabe. Gesamtgate und Live-API-Nachweis stehen nach diesem Eintrag aus. Kein Slice, Release, Druckerupload oder Druckstart.


### MakerWorld-Empfehlungen: geprüfter Abschluss 2026-10-02

Gesamtgate abgeschlossen um 23:25:01 Europe/Berlin: Source-Policy, TypeScript, 145 Frontendtests, beide Builds, 531 Python-Tests und 3 Subtests sowie Compileall grün. Sieben neue Regressionstests erfolgreich. Natives Exportbundle SHA256 9e2248d86ba4da47400f22906d6c339a035ca8c24372b60850905e7ac06b1a39. MakerWorld-Komponente SHA256 ff974c6e8971737537b79ba910cdeddfcaed77916cf4e4461246a6d0a8d88c93.

Live-Komponente und neues Buildmanifest nach Same-Day-Backup atomar aus dem geprüften PC-Export übernommen; HA-Core-Konfigurationsprüfung grün, HA-Core neu gestartet. Backup /var/lib/homeassistant/homeassistant/backups/20261002T212742Z-makerworld-runtime. 572 kanonische Quellen erneut direkt vom PC gelesen; HA-Quellkopie und 129 Komponent-/Frontend-Ziele nach Deployment ohne Abweichungen. Native Workerdateien blieben unverändert, Worker und Timer aktiv.

Authentifizierter Live-GET für Modell 2887138: HTTP 200, 3,9 Sekunden; zwölf Empfehlungen, alle mit Bild-URLs und erhaltenen Downloadzählern, zwei Druckprofile, ein Beschreibungsbild und 50 Kommentare. Keine Selbstempfehlung/ungültige Design-ID in der Antwort. Puppet-Startseite auf Host-Port 5000 weiterhin Screenshot Preview. Dies ist eine API-Abnahme des Empfehlungspfads, keine interaktive Gesamt-Abnahme von MakerWorld.

Neue Synchronisierungsregel dauerhaft in AGENTS.md festgehalten. Diese Änderung einschließlich Tests, Regel, Roadmap, Worklog und gebautem Manifest wird vollständig nach Taracraft/3D-Ultimate-Center übertragen und per Git-Blobhash geprüft. Der vorherige öffentliche Stand ist unter backup/v6-before-makerworld-20261002 gesichert. Weiter offen bleiben vollständiger alternativer/kompatibler Druckprofilvertrag, originalgetreue Beschreibungsformatierung, interaktive MakerWorld-Abnahme sowie die zuvor dokumentierten Mal-/Touch-/Queue-Abnahmen. Kein Slice, Job-Release, Druckerupload, Druckstart oder Fresh-Install.


## 2026-10-02 MakerWorld-Druckervarianten und Rich-HTML

Die tatsächliche MakerWorld-Struktur `extention.modelInfo` und `otherCompatibilityModelInfo` wird ausgelesen: eigene Profil-IDs, Druckermodelle, Düsen und Plattendaten je Variante. Profile aus Empfehlungen oder fremden Modellen werden ausgeschlossen. Beschreibungen erhalten ein passives HTML-Feld mit Überschriften, Listen, Tabellen und Bildern; Klartext bleibt kompatibel. Zusatzbilder werden nur unterdrückt, wenn sie tatsächlich inline gerendert sind. Regressionstests ergänzen diese Verträge. Abnahme am 02.10.2026, 23:48 Uhr: Source-Policy, TypeScript, 148 Frontendtests, beide Produktionsbuilds, 537 Python-Tests plus 3 Subtests und Compile-Prüfung grün. Native Bundle-SHA: ab86d429aba75ddf538ab933c047ea3c35e8dc7f3f877843f51fd4cb4fbd3329. Live-API HTTP 200 in 3,65 s: 28 eindeutige Druckprofilvarianten für 14 Druckermodelle, alle mit Platten; HTML-Beschreibung 6778 Zeichen, 50 Kommentare und 12 Empfehlungen. Ausgelieferte Frontend-SHA c1916d3c1dfb28c3b4af587bac12eaa4c197da50e1674b7dc23353e15617bbf6 bestätigt. Puppet Port 5000: HTTP 200, image/png, gültige Signatur und visuell verbundenes Studio. Dies ist eine API-/Screenshotprüfung; interaktive MakerWorld-Abnahme und vollständige Profilübernahme ins Studio bleiben offen. Keine Slice-, Upload- oder Druckaktion. Worker und Timer unverändert aktiv. Änderungen im lokalen Repo und HA bytegleich; öffentliche Veröffentlichung dieses geprüften Standes gehört zum Abschluss dieses Schritts.


## 2026-10-03 A1-Hardwaregrenzen am Druckerprofil

Priorisierte Benutzerreparatur: Das sichtbare düsenunabhängige A1-Druckerprofil besitzt nun maximale Hardwaretemperaturen als Attribute (Hotend 300 °C, Bett 100 °C; Herstellerreferenz https://bambulab.com/en/a1/tech-specs). Die Grenzen sind keine Filament-Solltemperaturen. Der bisherige Resolver suchte ausschließlich ausgeblendete düsenspezifische Druckerprofile und blockierte deshalb selbst A1/0,4 mm/0,20 mm/PLA. Cloud-A1-Profile können die eindeutig markierte integrierte A1-Hardwareautorität beziehen; A1 mini erhält diese Grenzen nicht. Filament-, AMS- und Düsenprüfungen bleiben aktiv. Abnahme 03.10.2026: Gesamtgate grün (540 Python-Tests plus 3 Subtests, 148 Frontendtests, Source-Policy, TypeScript, beide Builds, Compileall). HA-Konfiguration geprüft und Backend neu geladen. Live-Profilkatalog bestätigt die Temperaturattribute und das Entfernen der Standarddüsen-ID. Rein lesender Live-Vertragstest besteht für A1/0,4 mm/0,20 mm/SUNLU PLA+/AMS-Slot 4. Keine Slice-, Upload- oder Druckaktion. Native Bundle-SHA c3487a688ec6d19b51c23f04012fff29ae1b7dc1c4f2769b23157ec62bf8cd18. Lokales Repo und HA werden per Hash synchronisiert; GitHub-Veröffentlichung gehört zum Abschluss dieses Schritts.

Ergänzung auf Benutzerwunsch: Die redundante Standarddüsen-ID entfällt aus den integrierten Druckerprofilen. Der vorhandene Parametereditor übernimmt die neuen Temperaturattribute automatisch. Vier leere Legacy-Sound-/G-Code-Felder im lokalen Druckprofil dürfen den Prozessvertrag nicht blockieren; nichtleere unbekannte Inhalte bleiben gesperrt.


## 2026-10-03 A1: sechs G-Code-Abschnitte

Maschinen-Start und Maschinen-Ende (G-Code 1/2) sowie Startsound und Endsound besitzen vier eigene klonbare Standardprofile aus den gelieferten Bambu-Studio-A1-Originalen vom 20260513. Die Soundblöcke bleiben an ihrer ursprünglichen Stelle; vollständige Rekonstruktion wird geprüft, einschließlich aller 30 Timelapse-Aufnahmen und Motor-Abschaltung. Die beiden Filamentabschnitte bleiben Parameter des Filamentprofils, einschließlich des leeren/comment-only Filament-Endes; Benutzerwerte werden nicht überschrieben.

Die vier Menüauswahlen werden pro Platte/Projekt erhalten, invalidieren bestehende Slice-Ergebnisse und gelangen über einen validierten, gehashten Vertrag in die native Maschinenkonfiguration. Filament-/falsche Slotprofile werden abgelehnt, A1-Vorlagen nicht auf andere Druckermodelle übertragen. Die getrennte Düsenauswahl bleibt maßgeblich. Gesamtgate, SHA-Abgleich und gesicherte Laufzeitübernahme folgen; Prüfung ohne echten Slice, Upload oder Druck.


Abnahme 03.10.2026: Gesamtgate grün (549 Python-Tests plus 3 Subtests, 149 Frontendtests, Source-Policy, TypeScript, beide Builds und Compileall). Bundle-SHA 63b0881e7b85aed3669345a4af0c0e1dc1fba47ca3ccae4c845873f2331dfeec. Gesicherte Laufzeitübernahme und HA-Konfigurationsprüfung bestanden; Live-Profilkatalog HTTP 200 bestätigt vier getrennte A1-Maschinen-/Soundprofile und beide Filamentfelder. Rein lesender Vertragstest A1/0,4 mm/0,20 mm/SUNLU PLA+/AMS-Slot 4 grün. Alle 576 Quelldateien im lokalen Repo/HA und 580 öffentliche Dateizuordnungen werden per SHA abgeglichen. Worker und Timer aktiv. Kein echter Slice, Upload oder Druck. GitHub-Veröffentlichung dieses geprüften Standes ist Teil des Abschlusses.


## 2026-10-03 Native A1-Slice-Abnahme

Der ausdrücklich autorisierte echte Slice (geschlossener Würfel 10×10×2 mm; A1, 0,4-mm-Düse, 0,20-mm-Schichten, SUNLU PLA+, AMS-Slot 4, Texturplatte) deckte zwei Fehler auf: Die CLI lud unveränderte native Filamentbasen und ersetzte damit die ausgewählten Filament-Gcodes; vier numerische Prozesswerte wurden wegen falscher JSON-Typen ignoriert. Die Materialisierung schreibt nun je Job und Materialkanal ein aufgelöstes Filamentprofil für --load-filaments und serialisiert native Zahlen/Boolwerte als Strings. Native Basisdateien bleiben unverändert. Regression prüft eigene Filamentcodes, Temperaturüberschreibung, getrennte Kanäle und Skalartypen. Der isolierte native Kandidat erzeugt erfolgreich Gcode-3MF (Exit 0), enthält alle sechs Abschnitte und verursacht keine invalid-json-type-Meldung. Wiederholung auf der übernommenen Laufzeit und weitere Varianten gehören zur Abnahme. Kein Druckerupload oder Druckstart.


Finale Abnahme: Das vollständige native Projektgate besteht (Frontendtests/TypeScript, beide Builds, Python-Tests und Compileall). Bundle-SHA 741596648161b0e2ee9b14d90b3124607ed66c33cffa3a8894779be558dc64ec. Nach gesicherter Laufzeitübernahme und HA-Konfigurationsprüfung bestehen drei echte native Slice-Varianten auf dem installierten Worker: unveränderte A1/SUNLU/AMS4-Auswahl, modifizierte Filament-Gcodes mit 225/230 °C und ausgeschaltete Soundbefehle. Alle erzeugen Gcode-3MF mit Exit 0, zehn 0,20-mm-Schichten und ohne invalid-json-type-Meldungen. Der Default enthält alle sechs Abschnitte; Filamentmakros werden ausgeführt und eigene Filamentcodes übernommen, M1006 fehlt bei stummen Sounds. Verifiziert sind 576 Quelldateien lokal/HA sowie 580 GitHub-Zuordnungen. Kein Druckerupload oder Druckstart.


## 2026-10-03 Profil-Audit: Reparaturauftrag und größere Drucker

Alle nachgewiesenen Auditfehler sind als offene Reparaturen an docs/ROADMAP.md angehängt. Ergänzung des Benutzers: Größere Platten und bestimmte Profilkombinationen sind auf entsprechend größeren Druckern gültig; Katalogprofile erhalten und Zulässigkeit je ausgewähltem Drucker bestimmen. Der aktuelle native A1-Pfad darf keine Unterstützung anderer Drucker vortäuschen. Audit: 13.888 Vorprüfungen, 363 native Versuche, 335 Archive, 28 CLI-Ablehnungen und 17 Temperatur-Abschlussfehler; 180 falsche Profilbestätigungen. Sicherheits-, Parameter-, Platten-, Größen-, Cloud- und Vertragsreparaturen sind offen. Kein Druckerupload oder Druckstart.


## 2026-10-03 Reparaturkandidat: vollständiger Parameter- und Artefaktvertrag

Implementiert und isoliert geprüft: gemeinsame native Filamentmaterialisierung mit expliziten Benutzerwerten, Temperaturranges getrennt von Solltemperaturen, native Plattentypen einschließlich Supertack, vollständige Profilpayload-Bindung, unabhängige Hardwaregrenzen, druckerspezifische Größenprüfung und lineare/Kreisbogen-Druckgeometrie. Gültige Cloud-Prozessprofile mit leerem Overlay werden nativ akzeptiert. Ergebnisbestätigung benötigt tatsächliche native Parameter und ausgeführte Düsenheizbefehle; native Materialfamilien werden ausdrücklich nachgewiesen, statt kuratierte Produktnamen als Materialtyp zu vergleichen.

Nachweis: 13.888 Vorprüfungen (6.527 zulässig, 7.361 begründet abgewiesen), 147 Prozess-/Düsenprüfungen (73 zulässig), 322 native Slice-Artefakte. Alle 322 bestehen die Abschlussprüfung, Parameterbeweis und Profilbestätigung; kein Parameterverlust. Die zunächst vier abgelehnten 0,08-mm-Fälle enthalten gültige Kreisbögen und bestehen nach Prüfung des gesamten Bogenverlaufs. Zusätzlicher echter Cloud-Basis-Slice bestanden. Zwei-PLA-Mehrmaterialtest mit 13 Start-/End-Filamentblöcken und 14 Materialwechseln bestanden. PLA/PETG mit unterschiedlichen Betttemperaturen wird künftig vorab abgewiesen: ein gemeinsames Bett kann keine getrennten Sollwerte ausführen; kompatible Benutzerprofile müssen einen gemeinsamen Bettvertrag haben.

Negativnachweis: veränderte Maschine/Prozess/Filamentpayloads abgewiesen; 350 °C auch bei neu berechneten Hashes durch Hardwareprüfung abgewiesen; zuvor fälschlich akzeptiertes natives 350-°C-Archiv nun vom Direktdruck-Artefaktvalidator abgewiesen. Große Platten werden nicht aus dem Katalog entfernt. Ein 300-mm-Profil darf auf geeigneter größerer Hardware bestehen; native Ausführung anderer Druckermodelle benötigt noch eigene geprüfte Verträge. Kleine physische A1-Platten benötigen ebenfalls einen eigenen Start-/Wisch-/Ursprungsvertrag und werden bis dahin ausdrücklich abgewiesen.

Gesamtgate/gesichertes Deployment und SHA-Synchronisierung laufen noch. Erst danach gilt dieser Kandidat als bereitgestellt. Kein Druckerupload oder Druckstart.


## 2026-10-03 Bereitstellung und nächste Vertragsprüfung

A1-Reparaturstand bereitgestellt: GitHub-Commit 2154435151f524cf18e393dd5578eb3072d30923, Bundle e65fb4f9640b64e6ef76fb3d331bf47c9f7861d7e8066d000b1b144cee4904e9. Vollständiges Windows-Gate grün, gesichertes HA-/Worker-Deployment mit 55 geänderten Zielen, HA core check und Neustart bestanden. 580 Quelldateien lokal/HA und 588 öffentliche GitHub-Zuordnungen geprüft. Profil-API nach Neustart: HTTP 200, 165 Profile. Danach 21 weitere echte Slices mit den installierten Workerdateien: PLA, PETG und TPU über alle sieben A1-Düsenprofile; 21 bestanden, keine Parameterabweichung oder native Optionswarnung.

Abgeschlossen für den geprüften A1-Pfad: Parameterübernahme, native Plattentypen/Materialvorprüfung, Payload-/V2-Vertragsbindung, Hardware-Temperaturgrenzen, Cloud-Basis ohne Overlay und nachweisbare Ergebnisbestätigung. Große Druckerprofile sind erhalten; deren eigene native Maschinenverträge und praktische Abnahme bleiben offen. Kleinere physische A1-Platten benötigen weiterhin eigene Start-/Wisch-/Ursprungsverträge.

Nächster Schritt in Arbeit: Erstschichthöhe unabhängig von normaler Schichthöhe gegen die gewählte Düse prüfen, Temperaturfelder in Prozessprofilen früh statt erst im Worker ablehnen, finale Parameterbestätigung zusätzlich an ausgeführte Heizbefehle binden, kompakte/nummerierte Bewegungen denselben Geometriegrenzen unterwerfen. Kein Druckerupload oder Druckstart.


### 2026-10-03 Finale Abnahme des A1-Vertrags

Auch der zweite Vertragsblock ist bereitgestellt (Codecommit 7c968d7acf697ad285495ff0bc24a58f9466dff4, Bundle 7a5296fa97000d60f123cc20d87c3b2c8c3d95a86f658aa01eda510edbccac97). Gesamtgate: 614 Python-Tests und 3 Untertests bestanden; Frontendtests, TypeScript, beide Builds, Source-Policy und Compile-Prüfung grün. Alle 322 nativen Archive sowie beide passenden Mehrmaterialfälle bestehen die verschärfte Heizbefehls-/Geometrieprüfung. Nach gesichertem zweiten Deployment, HA core check und Neustart nochmals 21/21 Slices auf den installierten Workerdateien bestanden. Puppet-Port 5000: HTTP 200, image/png, geprüfte PNG-Signatur, verbundenes Studio ohne aktiven Druckauftrag. Abschlussbericht: docs/profile-gcode-contract-validation-2026-10-03.md.

Die angehakten Punkte gelten für den nachgewiesenen A1-Pfad und die aktuell vorgeprüften Profile. Andere Drucker bleiben erhalten, erhalten aber keine fiktive A1-Hardwarefreigabe. Nächste offene strukturelle Arbeit: eigene native Verträge und Abnahme für weitere/größere Druckermodelle; eigene Maschinen-/Ursprungsverträge für kleinere physische Platten. Reale Druckqualität sowie interaktive Touch-/Maus-Abnahme bleiben separate Prüfungen. Kein Upload zum Drucker und kein Druckstart ausgeführt.


### 2026-10-03 – H2S-Artefaktvertrag und große Testgeometrie

16 native H2S-Slices mit 300 × 8 × 2,4 mm Streifen erzeugt: 0,2/0,4/0,6/0,8-mm-Düsen, Generic PLA/PETG, Textured/Smooth PEI. Bisherige falsche A1-Markerpflicht durch explizite H2S-Befehlsprüfung ergänzt. Zusätzliche Reinigungs-/Spül-/Kammertemperaturen kontrolliert, physische Hardwareobergrenzen gegen gefälschte Autorität abgesichert. Alle 16 H2S-Artefakte bestanden, 16 Größenfälle auf A1 abgewiesen, sieben reale Manipulationen abgewiesen, 322 A1-Regressionsartefakte sowie 20 gezielte Tests bestanden. Vollständige H2S-Profilauswahl und Mehrmaterial bleiben offen; kein produktiver H2S-Auftrag, Druckerupload oder Druckstart. Bericht: docs/h2s-native-contract-validation-2026-10-03.md.


Abnahme des H2S-Artefaktbausteins: Vollständiges Windows-Gate: 632 Python-Tests plus drei Untertests, Source-Policy, TypeScript, Frontend-Tests, Produktions-/HA-Build und Compile-Prüfung bestanden. Gesichertes Deployment: /var/lib/homeassistant/homeassistant/backups/20261003T082551Z-v6-h2s-artifact-contract. HA-Konfigurationsprüfung und Neustart erfolgreich, Profil-API HTTP 200, acht Worker-Abhängigkeiten per SHA bestätigt. Installierter Stand: 16 H2S-Artefakte und sieben Negativmutationen bestanden sowie 21 neue A1-Slices ohne Parameterverlust oder native Optionenwarnungen. Bundle-SHA256: 80f2440e60fcdb7a0bdfc209487b1b12710768ba02a75f4eb9b60924316b6831.


## 2026-10-03 — H2S-Anbindung, geprüfter Kandidat

Eigenständige H2S-Profile und Maschinen-/Filament-/Kammerverträge implementiert. 592 Kombinationen vorgeprüft; 190 native Einzelmaterial- und zwei Mehrmaterial-Slices bestanden. Alle 192 Archive mit tatsächlichem Parameter-/Heizbefehlsnachweis bestätigt. Gefundene Fehler bei zusätzlichem Extrudereintrag, nativem Kammerparameternamen, Materialwechsel-Temperaturzuordnung und A1-Reinigungsturmgrenzen korrigiert. Modellgebundene G-Code-Vorlagen in der UI; Standardbausteine folgen beim Modellwechsel, individuelle Bausteine werden nicht umgeschrieben. Das erste Gesamtgate deckte eine veraltete Frontend-Testvorlage ohne Modellbindung auf; Vorlage und H2S-Abgrenzung geprüft. Finales Gesamtgate und korrigierte Bereitstellung bestanden. Keine Druckeraktion.

Live-Abnahme: erste H2S-Aktivierung wegen A1-spezifischem statischem Katalogvalidator zurückgerollt; bisheriger V6-Stand danach wieder HTTP 200. Modellabhängige native H2S-Katalogprüfung und Importregression ergänzt. Gesamte Integration zusätzlich im realen HA-Python importiert (230 statische Profile). Erneutes vollständiges Gate vor korrigierter Aktivierung.

### Abgeschlossene H2S-Softwareabnahme

Abnahme abgeschlossen: Vollständiges Windows-Gate am 03.10.2026 um 12:44 Uhr (CEST): 1239 Python-Tests plus drei Untertests, 149 Frontend-Tests, Source-Policy, TypeScript, Produktions-/HA-Build und Compile-Prüfung bestanden. Korrigierter Stand nach HA-Konfigurationsprüfung und Neustart aktiv; Profil-API HTTP 200 mit 221 Profilen, darunter 52 H2S-Profile (37 Filamente, vier Düsen, ein Drucker, zwei Platten und acht Prozess-/G-Code-Profile). Zehn Worker-Abhängigkeiten und 26 Bereitstellungsziele per SHA bestätigt. Installierter Worker: 190 H2S- und 21 A1-Slices ohne Parameterverlust oder native Optionswarnungen. Mit dem tatsächlich installierten Prüfcode: 192/192 H2S-Archive (einschließlich zweier Mehrmaterialarchive) und 21/21 frische A1-Archive gültig und durch G-Code bestätigt; zusätzlich 322 frühere A1-Archive geprüft. Fünf manipulierte H2S-Archive werden abgewiesen. Puppet auf Port 5000 liefert die verbundene V6-Oberfläche; dies ersetzt keine interaktive oder physische Druckabnahme.

Same-Day-Backup der korrigierten Bereitstellung: `/var/lib/homeassistant/homeassistant/backups/20261003T104732Z-v6-h2s-studio-worker-contract`. Gate-Bundle-SHA256: `f7bfd148790143c0e9fc735339ebcefe3c05855038fc218de1370418fa8cf1b5`. Die erste Aktivierung wurde wegen der älteren A1-Katalogprüfung zurückgerollt; modellabhängige Prüfung und echter HA-Import sind korrigiert und erneut vollständig geprüft. Lokales Repo und HA-Quellen werden vollständig mit 588 Quelldateien und 598 öffentlichen GitHub-Zielen abgeglichen. Kein Druckerupload, Job-Release oder Druckstart.


## 2026-10-03 — Notfallreparatur Druckvorschau, geprüfte Ursache

Benutzer meldet fehlende Druckvorschau und Ladebalken und verlangt unveränderte Darstellung. Drei reale Benutzeraufträge sind einlagige First-Layer-Tests. Der finale Validator fordert trotzdem die Bettheizung für nicht existierende Folgeschichten und verwirft gültige G-Code-Artefakte. Dadurch startet der bestehende Vorschau-/Ladebalkenablauf nicht.

Die erste Vermutung einer fehlenden Popup-Einbindung wurde durch das Gesamtgate widerlegt: Der originale Ladebalken ist absichtlich als Vorschau-Eintrag im gemeinsamen Vorgangsfenster integriert; das separate Legacy-Popup darf nicht zusätzlich eingebunden werden. Die versuchte Einbindung wurde vor jeder Bereitstellung zurückgenommen. Sämtliche Frontend- und Buildquellen bleiben bytegleich; kein zweites Fenster, keine neue Darstellung.

Korrektur ausschließlich im Bett-Phasenvertrag: Wegfall des Folgephasen-Heiznachweises nur bei übereinstimmender Layerzahl 1, genau einem nativen Layerwechsel und konstanter tatsächlicher XY-Extrusionsebene. Erstschichtheizung, vollständige Parameterübernahme, Hardwaregrenzen und Mehrschichtprüfungen bleiben verbindlich. Alle drei ursprünglichen Archive bestehen mit dem Kandidaten. Zehn zusätzliche Regressionfälle sichern Einzelschicht, gefälschte Layerangaben, Heizfehler, Temperaturgrenzen und unveränderte UI-Verdrahtung. Gesamtgate, Deployment, frischer Slice-/Puppet-Nachweis und Dreifachsynchronisierung noch offen. Keine Druckeraktion.


### Live-Abnahme der Vorschau-Reparatur

Gesamtgate auf dem kanonischen PC erfolgreich (Source-Policy, TypeScript, Frontendtests, beide Builds, Python-/Worker-Tests, Compileall). 38 gezielte Artefakt-/Kanonizitätstests grün. Alle 213 bestehenden A1-/H2S-Archive bestehen den neuen vollständigen Parameter-/G-Code-Validator. Frischer isolierter nativer Slice des ursprünglichen First-Layer-Modells erfolgreich.

Backup und atomare Bereitstellung: `/config/backups/20261003T120959Z-v6-preview-first-layer-restore`; acht Dateien inklusive HA-Quellen, Live-Komponente, nativer Worker-Abhängigkeit und Prüfsummen. HA-Konfigurationsprüfung, nativer Dienstneustart und HA-Core-Neustart erfolgreich. Live-Testjob `server__v6-preview-restore-20261003T121119Z` ist `succeeded`; vollständige Toolpath-API mit den produktiven Parametern `start=0&end=1` liefert HTTP 200, genau einen Layer und 690 Segmente. Keine Druckerübertragung, kein Druckstart, keine Änderung alter fehlgeschlagener Aufträge.

Alle 207 Frontend-Dateien unverändert. Neu erzeugtes produktives JavaScript und CSS sind byteidentisch zu den ausgelieferten Originalen; JavaScript SHA256 `0bcc578072e2fd23ff5bd81cedf8a2bfa919cb5795cbc66fe82f6ad5d4d0ed9e`, CSS SHA256 `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`. Nur das Build-Nachweisdokument wird mit dem aktuellen bestandenen Gate synchronisiert.

Offen bleiben die visuelle Browser-Endabnahme des konkreten neuen Jobs und der Commit/Hash-Abgleich mit dem öffentlichen GitHub. Der ursprüngliche Popup-Verdacht war falsch und wurde vor Bereitstellung vollständig zurückgenommen. Keine Behauptung einer bestandenen Pixel-Abnahme. Bestehender Puppet ist erreichbar und liefert ein gültiges PNG; ein automatisierter isolierter Browser-Abnahmepfad wurde nicht eingerichtet, ein weiterer HA-Connector-Versuch scheiterte mit HTTP 502. Reparatur ist live und API-verifiziert, aber der Gesamtpunkt bleibt bis Browser-/GitHub-Abnahme offen. Die Profil-Detailansicht meldet ohne angeforderte Vollanalyse weiterhin `pending_gcode_analysis`; dieser Wert wurde nicht künstlich auf bestätigt gesetzt.


## 2026-10-03 — P0 Druckvorschau: Backend repariert, Sichtabnahme offen

Die fehlende Vorschau der drei einlagigen First-Layer-Tests wurde durch die fälschlich verlangte Folgeschicht-Bettheizung verursacht. Korrektur ist auf HA und Worker aktiv; Erstschicht-, Hardware-, Parameter- und Mehrschichtprüfungen bleiben verbindlich. Der vorhandene Live-Testjob liefert HTTP 200, succeeded, eine Schicht und 690 Segmente. 38 gezielte Prüfungen erneut bestanden; das bestandene Gesamtgate und der 213-Artefakte-Nachweis bleiben dokumentiert.

Alle 207 Frontend-Dateien und die ausgelieferten JS-/CSS-Artefakte sind unverändert. Puppet auf Host-Port 5000 wurde tatsächlich gesichtet: Das gültige PNG zeigt nur die Steuerzentrale, nicht die Druckvorschau. Die Navigation wurde lesend geprüft; der anschließende Navigationsklick scheiterte am Werkzeug-Sicherheitscheck. Keine Umgehung, kein Ersatzbrowser und keine DOM-Injektion.

- [x] Einlagigen Backend-/Toolpath-Pfad und Regressionen erneut prüfen.
- [x] Unveränderte Frontendquellen und Live-JavaScript per SHA bestätigen.
- [ ] Druckbahnen und originalen Vorschau-Ladebalken tatsächlich sichtbar abnehmen, einschließlich Mehrschichtfall und Zustandswechseln.
- [ ] pending_gcode_analysis nach angeforderter Vollanalyse prüfen.
- [ ] Öffentliche Veröffentlichung einschließlich Datei-/Blobhash-Abgleich bestätigen; der frühere MCP-Erinnerungscommit ersetzt den Reparatur-Codeabgleich nicht.

Details: [Druckvorschau-Abnahme](docs/V6-Druckvorschau-Abnahme-2026-10-03.md). Diese P0-Abnahme hat Vorrang vor weiteren Drucker- und Funktionsausbauten. Beta bleibt bestehen. Kein neuer Slice, Druckstart, Druckerupload oder Dienstneustart in dieser Fortsetzung.


## 2026-10-03 — Benutzerbilder: First-Layer-Vorschau sichtbar, Uploadmodell fehlt

Die drei Benutzerbilder zeigen den Vorschau-Ladebalken bei 100 Prozent und rote First-Layer-Bahnen. Abgleich mit primitive-geometry.ts: umlaufender Rahmen, parallele Querstege und mittlerer Längssteg entsprechen dem eingebauten Testmodell; das graue Raster ist die Druckplatte. Die erste Interpretation einer vollständig leeren Vorschau war zu pauschal. Kein Renderer-/Farb-/Layout-Umbau erforderlich. Vollständige Mehrschicht-/Interaktions-/Pixelabnahme bleibt separat.

Der read-only Transferstatus des konkreten Benutzerjobs nennt den exakten Abbruch vor dem Upload: Für das gewählte Druckermodell fehlen geprüfte Hardwaregrenzen. Die verbundene Drucker-API meldet model=null; der Provider verwendete ausschließlich dieses optionale Telemetriefeld. Neue Identitätsauflösung bindet das Modell an die konfigurierte, verbundene Seriennummer und den gepinnten Herstellerkatalog: 039/N2S=A1, 093/O1S=H2S. Keine Ableitung aus Anzeigenamen oder vom Druckauftrag behaupteten Hardwaregrenzen. Unbekannte Familien, ungültige Seriennummern und widersprechende Telemetrie bleiben blockiert. Snapshot und Upload verwenden dieselbe Auflösung; die Hardware-/G-Code-Prüfung bleibt unverändert. Quelle: BambuStudio Commit da8b44ee34dd349f2ae0df3f1cbae366df482354, resources/printers/N2S.json und O1S.json.

Zusätzlich schluckte der Frontendfehler-Resolver den strukturierten HA-Fehlerbody zugunsten von Response error: 502. Enger Fix stellt body.error.message wieder her, ohne den POST erneut auszuführen. Regression vor Korrektur: drei von vier Fällen fehlgeschlagen; nach Korrektur vier bestanden. 22 Identitäts-/Providerprüfungen ohne Netzwerk bestanden. Der originale Benutzerjob besteht die vollständige Artefaktprüfung mit der unabhängig aufgelösten A1-Hardware. Kein Druckerzugriff/Upload in diesem Test.

Quellbackup/Kandidat: /config/backups/20261003-transfer-error-detail. Gesamtgate und Bereitstellung dieses neuen Fixes stehen bei diesem Eintrag noch aus. Ein späteres Deployment ist keine Behauptung eines erfolgreichen echten Uploads; automatische Wiederholung und Druckstart bleiben aus. Weiterer bestätigter UI-Befund: Profilkopf zeigt generische Düsenwerte 200/300 statt ausgewählter Prozesswerte 70/150 mm/s. Die tatsächlichen G-Code-Werte sind im Benutzerbild korrekt bestätigt; dieser Anzeige-Fehler bleibt ein eigener offener Punkt.


### 03.10.2026, 15:50 CEST — Modell-/Übertragungsfix geprüft und bereitgestellt, Aktivierung offen

Gesamtgate am kanonischen PC bestanden: Source-Policy, TypeScript, 153 Frontendtests, beide Builds, Python-Gesamttests und Compile-Prüfung. Zusätzlich 22 isolierte Identitäts-/Providerregressionen sowie vier Fehlerbody-/Nichtwiederholungsprüfungen bestanden. Letztere zeigen den Fehler vorher mit drei roten Tests. Der originale Benutzer-G-Code besteht mit der aus der Hersteller-Serienfamilie unabhängig ermittelten A1-Identität die vollständige Artefaktprüfung ohne FTPS-/Druckerzugriff.

Sechs Ziele mit Same-Day-Backup `/config/backups/20261003T134818Z-v6-connected-model-transfer` bereitgestellt und per SHA bestätigt: zwei HA-Python-Dateien und JavaScript/Buildmanifest im Live-Ziel sowie in der HA-Quellkopie. Native Workerdateien und CSS unverändert. Von 207 Frontendquellen änderte sich ausschließlich `ha-api-transport.ts` zur Fehlerdetailanzeige; Renderer, Geometrie, Farben und Popup-Layout unverändert. Neues Live-JavaScript: `652d71e328b0bd352875800fe576c9911f4aeade9d5773984d46d9fb207e9305`.

HA-Konfigurationsprüfung erfolgreich. Der anschließend notwendige `ha core restart` wurde vom Werkzeug-Sicherheitscheck blockiert und nicht ausgeführt. Die Backend-Aktivierung bleibt daher offen; kein Ersatzpfad und keine Umgehung. Der Nutzer muss Home Assistant neu starten, anschließend ist die laufende Drucker-API erneut auf model=A1 zu prüfen. Kein tatsächlicher Upload erneut ausgeführt und kein Druck gestartet. Ein erfolgreicher echter Transfer wird ausdrücklich noch nicht behauptet.

Noch offen: Aktivierung/Live-Modellprüfung, tatsächliche manuell freigegebene Übertragung, falsche generische Platzhalter 200/300 statt ausgewählter 70/150 mm/s, vollständiger GitHub-Codeabgleich und weitergehende Vorschau-/Interaktionsabnahme. Quellen und Dokumentation lokal/HA synchron; öffentliches main in diesem Schritt nicht geändert.


## 2026-10-03 — Mehrfarben-Uploadfehler korrigiert und aktiviert

Der interne Mehrteile-Name enthielt `+4 Teile`; der native Worker wies ihn mit HTTP 400 `invalid_filename` ab. Router erzeugt jetzt einen begrenzten ASCII-Transportnamen und erhält Projektname, Modelldaten und Materialplan. Fünf gezielte Regressionen grün (Originalcode: vier Fehler); isoliertes Gesamtgate mit 1.277 Python-Tests plus drei Untertests, 161 Frontendtests, TypeScript, beiden Builds, Source-Policy und Compile-Prüfung grün. Isolierung wegen separater unvollständiger First-Layer-Änderungen auf dem PC; diese unverändert. Backup und atomare Bereitstellung, HA core check und Neustart erfolgreich. Echter Upload der Original-AMS-Testdatei: alter Name HTTP 400, korrigierter Name HTTP 201, Daten bytegleich. Kein Slicerjob, Druckerupload oder Druckstart. Vollständige Vierfarben-Slice-/Slotabnahme bleibt offen. Details: [Mehrfarben-Upload-Reparatur](docs/V6-Mehrfarben-Upload-Reparatur-2026-10-03.md).


### 03.10.2026 – TaraCraft First-Layer live, GitHub-Schreiben blockiert

First-Layer-Test auf PC und HA umgesetzt: Bettfläche mit 5 mm Rand, mittiges großes T mit drei Konturbändern, diagonale Füllung 135°, bei 0,4-mm-Düse 0,28 mm Höhe und 0,60 mm Linienbreite. 167 Frontendtests, 1285 Python-/Worker-Tests plus 3 Subtests und vollständiges Gate grün. Isolierter nativer Slice bestätigt genau eine Schicht und diagonale Bodenbahnen. Kein Druckerupload oder Druckstart.

HA-/Worker-Deployment mit Backup, atomarem Austausch und SHA-Prüfung; HA-Konfigurationsprüfung und Core-Neustart erfolgreich. Puppet Port 5000 als echtes PNG gesichtet: verbundenes Studio; interaktive T-Abnahme bleibt gesondert. Details und korrigierte PC-/MCP-Zugriffserinnerung: docs/FIRST_LAYER_TARACRAFT_2026-10-03.md.

GitHub-Veröffentlichung noch offen: create_blob wurde mit „user rejected MCP tool call“ abgewiesen. Kein Commit und kein Ref-Update; kein alternativer Schreibweg. Aktuelle öffentliche Basis d490faad38a18b64e9c6f6a4548a23a4662b55b3. Vollständiger Gesamt-Repository-Gleichstand wird nicht behauptet; vorbestehende, nicht zum First-Layer-Delta gehörende PC/HA-Abweichungen bleiben erhalten.

## 03.10.2026 21:55 CEST · Privater Prüfstand, Kamera und Namensmigration

- Privaten Prüfstand weitergeführt; keine öffentliche Freigabe.
- Live-Kameraartefakt und HA-Ressourcenhash abgeglichen: 57acf6c99c7010688f75b5f15ae83e0ea6cf053ee93d506d828b928eed6ba437; API und persistenter Ressourcenstand bestätigt, HTTPS-Auslieferung nach SHA geprüft.
- Namensmigration aus 734 frischen PC-Textdateien vorbereitet: 373 angepasste Dateien, aktueller Kandidat 1.0.0-beta.4. Source-Policy, TypeScript, 182 Frontendtests, beide Builds und 1290 Python-Tests plus drei Untertests bestanden.
- Elf Speicher-/Konfigurationsregressionen bestanden; elf HA-Speichersnapshots und zwei Konfigurationssnapshots vorbereitet. Drei Druck-Automationen behalten IDs, Trigger und Aktionen. Vier Nutzdatenbereiche unverändert. Browsercode mit Sicherung, Rücklesen und Rückweg am PC und HA gesichert.
- Native Worker: 353 terminale Zustandsdateien; keine wartenden/aktiven Dateien. 98 von 100 API-Verlaufskennungen haben noch den bisherigen Prefix. 2471 Laufzeitdateien inventarisiert; binäre Artefakte und Jobverlauf unverändert.
- Kandidat noch nicht aktiviert. Worker-/Connectorverträge, PC-Anwendung, atomare Aktivierung, reale Browser-/iPhone-Abnahme und nicht editierbare Site-Beschreibung bleiben offen. Browsersitzung blockiert; keine UI-Abnahme als bestanden behauptet. Kein Slice/Release/Upload/Druckstart.
- Privater Prüfstand: https://taracraft-pruefstand.fassinator1982dn.chatgpt.site


## 03.10.2026 23:34 CEST · Fehlerpass aus dem privaten Dashboard

- Verbindliche Arbeitsliste: 53 Dashboard-Einträge in fünf Bereichen. SY-01 Audit-Restlücken und GA-06 MakerWorld-Kennzeichnung korrigiert; PR-08 bestehende Profilkorrektur anhand von Tests und bytegleichem Live-Ausgangsbuild bestätigt.
- Audit: fünf neue Fehlerfälle am alten Code, sieben Regressionen nach Korrektur grün; sechs AMS-Kategorisierungsfälle bestanden. Aktive API HTTP 200, 5.000 Einträge und Zusammenfassung ohne weiteren Bedarf nach den geprüften Maskierungsregeln; keine Audit-Ereignisse gelöscht.
- 176 Frontendtests, 1.297 Backendtests plus drei Untertests, Source-Policy, TypeScript, beide Builds, Syntax/Imports/Compile bestanden. Kanonischer PC-Status erfolgreich; PC-/isolierte Artefakte bytegleich. Ein Connector-Zeitlimit wurde über tatsächliche Statusdateien aufgelöst.
- Sieben Quelländerungen am PC und auf HA gesichert, übernommen und rückgelesen. Acht Artefaktziele mit Same-Day-Backup aktualisiert. HA-Konfigurationsprüfung und Neustart erfolgreich, Integration loaded. Live-JS SHA256: 486590a08b9aecbb54ef73168900c78fe2a0cae4f693a2f9d2bbf47fb4f9a1a3; HTTPS und dauerhafte Ressourcenverknüpfung stimmen überein.
- Namensmigrationskandidat aktualisiert: 737 Textquellen, 375 Anpassungen; 186 Frontendtests und 1.297 Backendtests plus drei Untertests grün. Elf Speicher-/zwei Konfigurationssnapshots erneuert; vier Nutzdatenbereiche erhalten. Aktivierung und die im Dashboard genannten Voraussetzungen bleiben offen.
- Privates Dashboard um Arbeitsboard, Voraussetzungen, Sortierung, Direktlinks und persönliche Prüfschritte/Notizen erweitert. Neun Modell-/Interaktionslogiktests grün; echte Browser-/iPhone-Abnahme und WebMCP-Prüfung weiterhin offen. 22/53 dokumentierte Abschlüsse, 31 ausstehend; fünf teilweise abgenommene Bugs.
- Bericht: docs/Studio-Dashboard-Fehlerpass-2026-10-03.md. Backup: backups/20261003-dashboard-defect-pass (HA), .codex-backups/20261003-dashboard-defect-pass (PC). Kein öffentlicher Schreibvorgang, kein Slice, Release, Druckerupload oder Druckstart. Beta bleibt.


## 2026-10-04 06:10 CEST · Dashboard SY-11: Worker, Connector und Einbindungen

Privater Prüfstand: https://taracraft-pruefstand.fassinator1982dn.chatgpt.site

- Tatsächliche YAML-Einbindungen rekursiv erfasst: 27 Dateien, zwei Konfigurationskandidaten und elf frische HA-Speicherkandidaten. Vier Nutzdatenbereiche unverändert. Drei Druck-Automationen behalten ID/Trigger/Aktionen; eine weitere Modulstatus-Automation hat drei gegen das Register geprüfte neue Entitätsverweise, neuen Anzeigetext und eine nicht referenzierte versionsfreie Auslösekennung. Fremde Anwendungen bleiben erhalten.
- Worker-Probekopie: 4.980 Dateien / 9.017.698.873 Byte; 354 Auftragskennungen, davon 324 umbenannt. 4.708 Pfade und 1.021 JSON-Metadatendateien angepasst, 3.959 übrige Dateiinhalte bytegleich. 353 Zustandsdateien sind abgeschlossen oder fehlgeschlagen, keine aktiv/wartend.
- Tatsächliche Worker-Lesefunktionen gegen Quelle und Kandidat: 354 Details, 100 Verlaufseinträge in gleicher Reihenfolge, 327 Downloads und 1.871 Dateiverweise bestanden. Kein neu fehlender Verweis und keine alte Versionskennung in vorbereiteten Job-IDs.
- PC-Connector: 13 Module frisch textuell abgeglichen, zehn Kandidatendateien angepasst; sechs aktive Produktwerkzeuge erhalten Namen ohne Versionsbezug bei gleichen Argumenten und Schutzprüfungen. Acht Vertragsprüfungen bestanden. Aktiver Dienst nicht ersetzt oder neu gestartet.
- Browser-Migration ergänzt: nur Druckplatten-Auftragskennungen werden umgebunden; Geometrie, Profilwahl und rohe Rückwegsicherungen bleiben erhalten. Vier zusätzliche Frontendtests; kompilierter Helfer stimmt bei allen 354 Worker-Kennungen überein. Keine tatsächliche IndexedDB-Abnahme behauptet.
- Gesamtgate im isolierten Produktkandidaten: 190 Frontendtests, 1297 Backendtests plus drei Untertests, Typen, Source-Policy, beide Builds, Syntax, Imports und Compile grün. Weitere 45 Migrationsprüfungen bestanden (22 Speicher/Konfiguration, 15 Worker, acht Connector).
- Kandidaten-JavaScript: eb03e6232db722263d1b23b85caff9e06c395f85eb78e332e229a91b5375948c. Produktbetrieb bleibt auf dem bisherigen Live-Build 486590a08b9aecbb54ef73168900c78fe2a0cae4f693a2f9d2bbf47fb4f9a1a3.
- Vorbereitung und Nachweise: HA backups/20261004-studio-migration; reproduzierbarer Code, Connector-Kandidaten und Berichte zusätzlich PC .codex-backups/20261004-studio-migration. Große Worker-Kopie verbleibt auf HA.
- SY-11 bleibt partial: frischer vollständiger PC-Abgleich und Übernahme, koordinierte Aktivierung mit Rückweg, Cache-Neuerzeugung und echte Browser-/iPhone-Abnahme offen. Nicht editierbare Site-Beschreibung bleibt Plattformrestpunkt. Keine öffentliche Freigabe oder öffentliche GitHub-Schreiboperation. Kein Slice, Release, Druckerupload oder Druckstart.
- Dashboard um neun nachvollziehbare Teilnachweise der Umbenennung erweitert; fünf Vorbereitungsnachweise geprüft. Zehn automatisierte Dashboardprüfungen bestanden. Gesamtzählung bleibt 22 von 53 abgeschlossen. Die private Auslieferung dieses Updates wird zusätzlich durch den Sites-Deploymentnachweis bestätigt.

Vollständiger Bericht: docs/Studio-Namensmigration-Pruefpass-2026-10-04.md.

## 2026-10-04 · Paralleler Fehlerpass mit sechs Agents

53 Roadmap-Einträge auf sechs Prüfbereiche verteilt; 27 Dateien (14 Produkt, 13 Tests) zentral übernommen. Navigation/Reconnect, Kamera-Fortsetzung, Filamentgruppen/Scrollposition, CAD-Treffpunkt/Materialfarbe/sichere Namensanzeige, Slicerwarnung und Analysestatus, Galerie-Anfragerennen/Uploadziele/Dateischutz sowie Laufzeit-/Auditaktualisierung korrigiert.

Gesamtgate und kanonisches PC-Gate grün: 231 Frontendtests, 1.334 Python-/Worker-Tests und neun Untertests; Source-Policy, Typprüfung, beide Builds, Syntax, Imports und Compile bestanden. PC-/isoliertes JavaScript und CSS bytegleich. HA-Konfigurationsprüfung und Neustart erfolgreich, Integration loaded, Health HTTP200. Ressourcen-API und dauerhafter Speicher abgeglichen. HTTPS-SHA: 29fc7bc256736fc7652555668b3a36ba3e9f9a7ac0bd22b7a96a7e346fb54eec.

CAD-Gegenprüfung: Aktive Feintriangulierung nicht verdrahtet; globales Paint-Clear und Platten-ID/Layer-Zuordnung sind offene Datenhaltungsfehler. Größerer Kompositions-/Refinement-Prototyp wegen mehrdeutiger Altprojekte nicht übernommen. Ursprüngliche Dreiecksreferenzen müssen vor künftigem Refinement validiert werden. Jobabbruch weiterhin fehlende Capability. Echte Browser-/iPhone-/Touch- und Hardwareabnahmen bleiben offen; Beta bleibt.

Namenskandidat nachgeführt: 245 Frontendtests, 1.334 Backendtests und neun Untertests sowie alle Gates grün. Kandidaten-SHA 3e869c5b9625e634d89ee1af55d45501276d3a9bfe17b7d8b1dd55583cb50020. Elf Speicherdateien, zwei geänderte Konfigurationen aus 27 erreichbaren Dateien; 15 Helpertests. Keine Namensaktivierung.

Bericht: docs/Studio-Parallel-Fehlerpass-2026-10-04.md. Nachweise und Sicherungen: HA backups/20261004-parallel-defect-pass; PC .codex-backups/20261004-parallel-defect-pass. Keine öffentlichen Writes, kein neuer Slice, kein Release, kein Druckerupload und kein Druckstart.


## 2026-10-05 · Hauptvorschau mit echten auftragsgebundenen Filamentfarben

Sieben kanonische PC-Dateien nach frischer Quellprüfung und vollständiger Sicherung übernommen und rückgelesen. Hauptvorschau startet mit Materialfarben, automatische Drucktyp-Resets entfallen, ungültige Paletteinträge behalten ihren Kanalplatz, unbekannte Kanäle werden nicht per Modulo auf vorhandene Farben abgebildet. Historische Aufträge greifen nicht auf die aktuelle AMS-Bestückung zurück. Der Parser erfindet keine Filamentfarbe aus ungültigen Metadaten oder einer bloßen Extruder-Anzeigefarbe.

Gegenprobe Hauptstudio: sieben Fehler unter 33 Tests am alten Code, alle 33 am Kandidaten bestanden. 13 neue plus drei vorhandene Parserprüfungen unter Linux bestanden. PC-Gesamtgate abgeschlossen 00:35:28 CEST: 403 Frontendtests, 1.575 Python-/Worker-Tests, 15 Untertests bestanden; neun native Linux-Prüfungen auf Windows ausgelassen; beide Builds, Source-Policy, Typprüfung, Syntax/Imports/Compile erfolgreich. Connector-Zeitlimit anhand der realen vollständigen Statusdatei aufgelöst.

HA-Quellsynchronisierung, Änderungen am alternativen Viewer sowie das 95-Prozent-MakerWorld-Popup wurden blockiert und nicht angewendet. Keine Live-Bereitstellung, kein neuer Realjob-/Pixelnachweis und keine Behauptung, der echte MakerWorld-Import funktioniere bereits. Dashboard/GitHub/Namensmigrationskandidat offen.

Bericht: [Materialvorschau-Prüfpass](docs/Studio-Materialvorschau-Pruefpass-2026-10-05.md). PC-Sicherung: backups/20261005-material-preview-colors. Isolierter Prüfstand und Logs auf HA: /config/backups/20261005-preview-popup-local. Kein Slice, Release, Druckerupload, Druckstart oder Dienstneustart.


## 2026-10-05 · PC-/HA-Quellabgleich tatsächlich ausgeführt

Das zuvor gesperrte MakerWorld-Transfermodul ist in diesem Abschnitt über denselben kanonischen Dateitransfer erfolgreich im HA-Staging angekommen. 662 ausgewählte Projekt-/Deploydateien wurden vom PC aufgenommen und vollständig ein zweites Mal rückgelesen. Aufnahme: 07:52:40 CEST. Die HA-Entwicklungsquelle wurde nach Originalsicherung in 52 Dateien nachgezogen; um 07:55:16 CEST stimmen alle 662 Dateien dieses Umfangs per SHA-256 mit dem PC-Kandidaten überein. Keine Löschung außerhalb des Umfangs.

PC-Gate vom 07:35:48 CEST: 440 Frontendtests, 1576 Python-/Worker-Tests und 15 Untertests bestanden; neun Linux-Prozessgruppentests auf Windows ausgelassen. Alle Gatephasen erfolgreich. Zusätzlich 314 Pythonquellen auf HA syntaktisch kompiliert, kein neuer kompletter Linux-Testlauf.

Produktive Komponenten, www und nativer Worker wurden NICHT aktualisiert. Weitergehende Vorabprüfung/Supervisor-/Puppet-Aufruf vom Werkzeug-Sicherheitscheck blockiert; nativer HA-Connector bei zwei Leseoperationen mit HTTP 502. Keine Umgehung gesperrter Options-/Zugangsdatenlesezugriffe. Kein Neustart, Slice, Druckerupload oder Druckstart.

Öffentliches main lesend auf 770725483bf51233d6d00408a5aabdf36b1fe893 bestätigt; separater öffentlicher Checkout angelegt, noch kein Push. Öffentliche Pfade studio-v6/, homeassistant/, slicing-server/, deployment/ bei der Fortsetzung erhalten, nicht die PC-Wurzel darüberkopieren.

Details: [Quellabgleich und verbleibende Aktivierung](docs/Studio-PC-HA-Quellabgleich-2026-10-05.md). Originalsicherung und maschinenlesbare Nachweise: backups/20261005-studio-release-sync auf HA. Roadmapstatus bleibt teilweise umgesetzt, nicht live abgenommen.


## 2026-10-05 · Native Workerbereitstellung: Supervisor-Paketierung in Arbeit

Beim lesenden Vorabcheck fehlt produktiv job_control.py. Der geprüfte neue Worker benötigt diese Datei; das bisherige Deployskript verlangt sie jedoch nur als vorhandene Zielabhängigkeit und installiert sie nicht. Quellseitige Korrektur: Supervisor in Installations-/Backup-/Rollbackumfang aufnehmen, Python-Syntax prüfen, dessen Paketchecksumme vorab sowie alle installierten Dateien vor Neustart und nach Health prüfen; Änderung nur am Supervisor erfordert ebenfalls Worker-Neustart. Andere native Abhängigkeiten werden weiterhin gegen ihren vorhandenen Zielstand geprüft und nicht still ersetzt.

Gezielte isolierte Linux-Prüfung des tatsächlichen Deployskripts an synthetischen Zielwurzeln und System-/Netzwerk-Doubles: 26 Tests, am alten Skript 17 fehlgeschlagen/9 bestanden, am Kandidaten alle 26 bestanden. Kein echter Dienst oder Druckauftrag war Testziel. Deployskript ist nach frischem PC-/HA-Abgleich mit Originalsicherung geändert; SHA-256 5fcb1f8eba35faf5897e21630aa23f42c9fe09ab1dcaa55ffe4905c7835e1697. Neue Testdatei identisch auf PC und HA; SHA-256 3c743c46d9e8d795912eca8f0a4d9ebd9f3ba7abb3124c3a3af1ba5642b9cbad.

Arbeitsabschnitt noch OFFEN: vollständiges erneutes PC-Gate, öffentlicher Codeabgleich und echte Bereitstellung. Backups/Nachweise: backups/20261005-native-deploy-supervisor auf PC und HA. Keine produktiven Dateien ausgetauscht und kein Dienst neu gestartet. Firmen-VM bleibt bis zur morgigen WAF-/Zertifikat-/Keycloak-Fortsetzung unberührt. Ziel bleibt die durch tatsächliche Abnahme belegte Beta-Freigabe, nicht bloße Umbenennung.


### 05.10.2026 23:10 CEST · Paketierungskorrektur geprüft und veröffentlicht

PC-Gesamtgate 22:59:29 erfolgreich: 440 Frontend, 1591 Python und 15 Untertests; 31 Windows-Auslassungen (22 neue Linux/root-Deployfälle, neun Linux-Prozessgruppenfälle). Alle 26 neuen Fälle separat unter Linux bestanden, am Original 17 Fehler. Skript/Test exakt auf PC und HA sowie im öffentlichen Commit 36b234f3c34f7bf9964b2484f9eeeb8a53dd7c10, Entwurfs-PR #1; neuer CI-Lauf 37373691825 zuletzt queued, nicht als bestanden ausgegeben.

681 Textquell-/kanonische Deploydateien auf PC/HA abgeglichen; sieben zusätzliche Abweichungen übernommen. Alte frontend/dist-Dateien und zwei nicht mehr benötigte generierte Binärfixtures explizit ausgeschlossen, nicht gelöscht. Native Abhängigkeitsvorprüfung 11/11 passend. Kein Live-Deploy. Öffentlicher Restabgleich, echte Aktivierung und reale Abnahmen weiterhin offen.

Neuer P0-Neuaufbaubefund: öffentliches scripts/rebuild-homeassist.sh ist wegen pauschaler Slicerwurzel-Löschung, V5-Kopie und nicht passendem nativen Installationsvertrag nicht für die Firmeninstallation freigegeben; nicht ausgeführt. Vollständiger Bericht: docs/Studio-Native-Deployment-Paketierung-2026-10-05.md. Nächsten automatischen Lauf auf die gespeicherten Nachweise aufsetzen, keine erneute Entwicklung dieses Fixes.


### Abschlussnachtrag: GitHub-Lifecycle-Prüfung bestanden

Der öffentliche Job isolated-deployment-lifecycle im Lauf 37373691825 ist erfolgreich abgeschlossen. Das heruntergeladene Artefakt 11370564597 wurde unabhängig per SHA-256 9c366ead5c61b7ab9525ded21ed312ead5276e0f576288e33db537d10df24835 geprüft. JUnit bestätigt 26 Tests, null Fehler, null Auslassungen; commit.txt bindet das Ergebnis an 36b234f3c34f7bf9964b2484f9eeeb8a53dd7c10, source.sha256 bestätigt die beiden PC-/HA-Quellhashes. Dies sind dieselben 26 gezielten Fälle, kein zusätzlicher unabhängiger Gesamtbestand. Die vorherige Warteschlangenmeldung ist damit aufgelöst.

Produktive Aktivierung und vollständiger öffentlicher Abgleich bleiben offen. Beim sauberen Linux-Neuaufbau außerdem die öffentliche Aufteilung slicing-server/ und deployment/systemd/ in einen tatsächlich vollständigen nativen Installationskandidaten überführen; die synthetischen Lifecycle-Tests ersetzen diese Paketvollständigkeitsprüfung nicht.
