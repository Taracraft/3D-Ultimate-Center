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
