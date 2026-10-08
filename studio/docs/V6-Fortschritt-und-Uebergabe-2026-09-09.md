# V6 – Fortschritt, Umsetzung und Übergabe

Stand: 9. September 2026, 01:25 Uhr (Europe/Berlin)

## Verbindliche Projektregeln

- Ausschließlich der kanonische V6-Quellstand wird verändert.
- Keine DOM-/Runtime-Patches, kein `MutationObserver`, keine Prototyp-Hooks.
- Vor Änderungen werden Quell- und Live-Backups erstellt.
- Änderungen werden erst nach TypeScript-, Frontend-, Python-, Build-, Compile- und Schutztests ausgerollt.
- Deployment erfolgt kontrolliert mit SHA-256-Prüfung und Rückrollmöglichkeit.
- Keine Druck-, Lade-, Entlade-, RFID- oder sonstigen unbestätigten Druckerbefehle.
- Kein PC-Slicing; der native Slicer-Worker und Port 5000 bleiben unverändert.
- Während eines laufenden Drucks werden Materialart und Farbe nicht verändert.

## Umgesetzte Punkte

### Galerie-Upload

- Der Fehler `Maximum request body size ... / Unexpected token M` wurde behoben.
- Große Dateien werden über den vorhandenen Upload-Controller in 4-MiB-Blöcken übertragen.
- Der Browser versucht Klartext- oder 413-Fehlerantworten nicht mehr fälschlich als JSON zu lesen.
- Fortschritt, Bytes und ETA bleiben erhalten.
- Ein Upload oberhalb der 16-MiB-HA-Grenze wurde ohne Druckauftrag getestet.

### Materialsysteme und Darstellung

- Navigation und Seite heißen nun „Materialsysteme“ beziehungsweise „Materialsysteme & Filamente“.
- Unterstützte AMS-, AMS-Lite-, AMS-2-Pro-, AMS-HT-, BMCU-/BCMU- und externe Systeme werden getrennt dargestellt.
- Konfiguriertes System und echte Live-Erkennung bleiben getrennt.
- Der graue Strich wurde entfernt.
- Systeme, Spulen und AMS-Fächer sind aufklappbar und zeigen weitere Telemetrieinformationen.
- Belegte Fächer und die externe Spule werden als farbige Spulensymbole dargestellt.
- Nur ein laut `slot.active` tatsächlich zur Düse geladener AMS-Weg wird grün markiert.
- Die externe Spule wird aus echter HA-Telemetrie dargestellt und als „am Drucker geladen“ gekennzeichnet.
- RFID-Daten und Restmengen werden nicht erfunden. RFID-Fächer sind für manuelle Änderungen gesperrt.

### Rot-statt-schwarz-Problem

- Die Darstellung verwendet jetzt die tatsächliche Drucker-/Spulentelemetrie statt einer roten Ersatzfarbe.
- Live bestätigt: externe Spule, PETG, Filament-ID `GFG99`, Farbe `#161616`, geladen.
- Das Modell beziehungsweise die Materialdarstellung erscheint damit schwarz/dunkel statt rot.

### Filamentprofil-Auswahl

- Filamentwechsel im rechten Studio-Menü werden serialisiert.
- Während des Speicherns werden weitere Klicks ignoriert.
- Die Backend-Auswahl wird abgewartet; bei Fehlern wird die vorige Auswahl wiederhergestellt.
- Erfolgs- und Fehlermeldungen sind eindeutig; die Auswahl wird auditiert.
- Das aktuelle Cloud-Profil `PTEG TEST Langsamer` wird korrekt als PETG verarbeitet.
- Die lange Cloud-Profilliste öffnet nicht mehr ungefragt vollständig und besitzt einen eigenen Scrollbereich.

### Materialart und Farbe am Drucker setzen

- In den aufgeklappten Spulen-/Slotdetails können Materialart und Farbe gewählt werden.
- Externe Spule am A1: PLA, PETG, TPU und PVA.
- AMS Lite: PLA, PETG und PVA; TPU wird sicher abgelehnt und bleibt auf die externe Spule beschränkt.
- Nicht freigegebene A1-Materialarten wie ABS werden serverseitig abgelehnt.
- Materialart, Farbe, generische Bambu-Filament-ID und sichere Temperaturspanne werden als ein zusammengehöriger Datensatz vorbereitet.
- Externe Spule wird für den Druckerbefehl korrekt als AMS-ID 255 / Tray 0 adressiert; die angezeigte Telemetrie-Tray-ID 254 bleibt davon getrennt.
- Schreiben ist nur für Administratoren, nur bei bereitstehendem Drucker, ohne aktiven Druck, ohne RFID und nach Vorschau plus ausdrücklicher Bestätigung möglich.
- Vor dem Schreiben wird die Live-Telemetrie erneut verglichen. Hat sie sich geändert, wird abgebrochen.
- Nach Annahme durch den Drucker wird die Rückmeldung erneut per Telemetrie geprüft und auditiert.

## Sicherheits- und Live-Nachweise

- Der Drucker befand sich beim Abschluss weiterhin im Zustand `running`; deshalb wurde absichtlich kein Material-/Farbschreibbefehl gesendet.
- Der sichere Vorschautest liefert im laufenden Druck HTTP 409 mit: „Druckerzustand 'running' erlaubt derzeit keine Materialänderung.“
- Ein ABS-Test liefert HTTP 400 und wird vor jedem Druckerzugriff verworfen.
- Live-Telemetrie der externen Spule: verfügbar, geladen, PETG, `#161616`, `GFG99`, 220–270 °C, kein RFID.
- Home Assistant Core 2026.9.1 läuft.
- Der HA-Konfigurationscheck war erfolgreich.
- Port 5000 hört unverändert auf IPv4 und IPv6.
- Im abschließenden V6-Logauszug gab es keinen neuen Traceback der V6-Komponente.

## Qualitätsgate und Prüfsummen

- Source-Policy: erfolgreich, keine verbotenen Runtime-Muster.
- Frontend-Test und Build: erfolgreich.
- Home-Assistant-Core-Build: erfolgreich.
- Python-Tests: erfolgreich.
- Python-`compileall`: erfolgreich.
- Finales Bundle: 134 Dateien, SHA-256 `d4867e5edda4bf164dcf39ed717d625f23951047e2a1fd8bbe9f2418de47f147`.
- Frontend JavaScript: `6bb024e04ca81bb644d4265cb5ff5ae4e0de7da4752799e6df3771f87e61648f`.
- Frontend CSS: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.
- Finale Live-Datei `filament_color_views.py`: `82d278b2c719dfeb1644dd08c0bcf331474044163d9e599df5365dac83ec92f0`.

## Backups

- Kanonischer Quellstand vor Material-/Farbänderungen: `v6/backups/v6-filament-color-before-20260908-2210`.
- HA-Backend vor dem Funktionsdeploy: `/config/pcc-backups/v6-filament-setting-before-20260909-0105`.
- HA-Frontend vor dem Deploy: `/homeassistant/pcc-backups/v6-frontend/20260909-010511`.
- Zusätzliche Rückrollkopie vor dem finalen Wortlaut-Fix: `/config/pcc-backups/v6-filament-setting-final-20260909-012010`.

## Bedienung

1. Nach Ende des laufenden Drucks die Seite „Materialsysteme & Filamente“ öffnen.
2. Externe Spule oder ein belegtes, nicht per RFID geschütztes AMS-Fach aufklappen.
3. Filamentart und Farbe wählen.
4. „Am Drucker setzen“ drücken und die Vorschau bestätigen.
5. Die Seite zeigt anschließend, ob die neue Einstellung per Telemetrie bestätigt wurde.

Die Funktion führt keine automatische Änderung nach Druckende aus. Eine Änderung wird nur durch den bewussten Klick und die Bestätigung des Benutzers ausgelöst.



---

Der obige Grundstand ist historische Dokumentation. Aktueller Stand: 12.09.2026, 19:31 Europe/Berlin. Die vollständige fortlaufende Projekthistorie steht in [V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md](V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md).


## 18. Fortschrittsnachtrag 2026-09-12 – vorhandener Transfer-/Dialogstand nachgeprüft

- Zu Beginn der Fortsetzung war gegenüber Abschnitt 17 bereits ein neuerer Quell- und Live-Stand vorhanden. Diese Änderungen wurden nicht in diesem Arbeitsschritt neu implementiert.
- `frontend/transfer-attempt.ts` und der Direktdruckpfad unterscheiden den vorherigen serverseitigen Startzeitpunkt von einem neuen Transferversuch. Antworten werden zusätzlich an die aktive clientseitige Trace-ID gebunden.
- `global-job-popup-v3.ts` behält die Druckeraktionskomponente beim Aktualisieren der Störungsliste bei. `printer-command-store-v2.ts` bindet die Bestätigung an den weiterhin aktuellen Drucker und Auftrag.
- Gespeichertes Vollgate dieses vorgefundenen Standes: 343 Python-Tests sowie Frontendtests, TypeScript und Builds erfolgreich. Vor Beginn der Layeränderung unabhängig auf HA bestätigter JavaScript-Hash: `4c61b47b8cfb23e9fb57f59d0e7747ff93559ef3199d43737ad2e295194df9ed`.
- Vorhandenes Live-Backup dieses früheren Deployments: `/homeassistant/pcc-backups/v6-frontend/20260912-122336`.
- Die physische Wiederholung eines abgebrochenen Drucks wurde hier nicht getestet. Kein automatischer Druckstart oder Druckabbruch zur Reproduktion.
- Der Benutzer hat die weitere Untersuchung des Drucker-/Z-Homing-Fehlers ausdrücklich zurückgestellt („vergiss den fehler“). Vorhandene Fehlercodefunktionen bleiben erhalten; es gibt hier keine neue Ursachenbehauptung oder Herstellerdiagnose.

## 19. Fortschrittsnachtrag 2026-09-12 – durchgängige Layerdarstellung

### Benutzerziel und Arbeitsreihenfolge

- Aktueller Schwerpunkt bleibt ausdrücklich die Layeransicht. Reale zusammenhängende G-Code-Bahnen sollen sichtbar sein, ohne den akzeptierten Bedienumfang zu verlieren.
- Der Druckeinstellungseditor gehört weiterhin zur Roadmap und folgt nach diesem Schritt. Die neun vorhandenen lokalen Prozesswerte gelten nicht als vollständiger Prozesseditor.
- Roadmap, Übergabe, technische Dokumentation und deutsche/englische Änderungsnotizen werden mit dem tatsächlichen Umsetzungsstand fortgeschrieben. Ältere Abschnitte bleiben als Historie vollständig erhalten; neuere Nachträge berichtigen ältere Haltepunkte.

### Befund im kanonischen Quellcode

- Der alte aktive Vorschaupfad übersprang bei großen kumulativen Ansichten einzelne frühere Modell-/Supportsegmente über Schrittweiten.
- Modellbahnen wurden auf 80 % bzw. 76 % ihrer geschätzten Breite reduziert.
- Frühere Seitenflächen bildeten nur 72 % der Schichthöhe ab. Diese Kombination begünstigte die ausgedünnte Darstellung.
- Die bestehende Auswahl der historischen Außen-/Oberflächenansicht wurde beibehalten. Der neue Schritt bedeutet nicht, dass bisher ausgeblendete innere Historienbahnen plötzlich vollständig eingeblendet werden.

### Implementiert und live bereitgestellt

- Neuer reiner TypeScript-Geometriebaustein: `v6/frontend/toolpath-ribbon-geometry.ts`.
- `studio-mega-workspace-v2.ts` verwendet diesen Baustein im bisherigen Vorschaupfad.
- Alle nach den bestehenden Sichtbarkeitsregeln angenommenen, gültigen Extrusionssegmente werden gezeichnet. Es gibt in diesem aktiven Pfad keine schrittweise Segmentausdünnung mehr.
- Modellbahnen erhalten Seitenflächen bis zur vollen Schichthöhe. Die obere Bahnfläche liegt an der gelieferten Z-Höhe.
- Die Breite wird aus Extrusion, Bahnlänge und Schichthöhe unter der bestehenden 1,75-mm-Filamentannahme geschätzt. Sie wird nicht mehr auf 80/76 % verkleinert. Darstellungsgrenzen: 0,08 bis 1,6 mm; dies ist kein neuer Düsen- oder Slicingparameter und keine Behauptung einer exakt gemessenen Strangform.
- Die Beleuchtungsnormalen der Seitenflächen machen einzelne Bahnen kenntlich, ohne künstliche Lücken zwischen den Schichten einzufügen. Diese Beleuchtung ist eine Darstellungsnäherung, keine Änderung am G-Code.
- Float32-Seiten mit maximal `54 * 4096` Zahlen pro Geometrieseite vermeiden große temporäre JavaScript-Zahlenlisten. Die Gesamtgeometrie bleibt proportional zur Zahl der sichtbaren Bahnen; die Seiten begrenzen nicht den gesamten Speicherverbrauch.
- Support-Einzelansicht bleibt flach und behält alle geladenen, gültigen Supportbahnen. Modell-/Materialfarben, Strukturfarben und die bisherigen Filterentscheidungen bleiben im bestehenden Workspace.
- Einzellayer/kumulative Ansicht, Kategorienfilter, Alle/Keine, Materialzusammenfassung, Zoom-/Kameraautorität, Layerregler, Vorschaufortschritt und Slicingpfad wurden nicht durch neue Bedienwege ersetzt.
- Ungültige Koordinaten, nichtpositive Extrusion und praktisch längenlose Segmente erzeugen keine ungültigen WebGL-Puffer.
- Keine DOM-/Prototype-/Runtime-Injection, kein Frontend-Reload. Keine Änderungen an technischen Domain-/API-/Storage-IDs, V5, Worker oder Port 5000.

### Tests und konkrete Grenzen der Verifikation

- Vier neue ausführbare Geometrietests:
  1. 180.001 Bahnen oberhalb des alten Vorschau-Budgets: jede Bahn bleibt erhalten, eindeutige Mesh-IDs, begrenzte Geometrieseiten.
  2. Durchgängige aufeinanderfolgende Schichthöhen und 0,2-mm-Bahnbreite.
  3. Einzellayer, Support-Isolation, Farbzuordnung und ausgeblendete Kategorien.
  4. Ungültige Koordinaten/Travel sowie unveränderte Eingangsdaten.
- Erstes Vollgate stoppte vor Build/Deploy, weil eine alte Quellprüfung ausdrücklich die bisherige Sampling-Ausnahme für Brim/Raft/Skirt/Tower verlangte. Die Prüfung wurde auf den neuen vollständigen Renderpfad umgestellt; alle übrigen Gates bleiben erhalten.
- Finales vollständiges Gate: **87 Frontendtests und 343 Python-Tests bestanden**, TypeScript, Frontend-Build, HA-Frontend-Build und Python-Compileall grün, Quellrichtlinie ohne Verstöße.
- Das Deployment-Werkzeug führte das vollständige Gate erneut erfolgreich aus. Abschlusszeit: **12.09.2026, 19:31:44 Europe/Berlin**.
- Zusätzlicher synthetischer Lastlauf vor der abschließenden Beleuchtungskorrektur: 500.000 Bahnen / 3.000.000 Dreiecke, rund 206 MiB reine Positions-/Normaldaten, rund 403 MiB Prozess-RSS in der Testumgebung, Geometrieerzeugung rund 1,37 s. Dies ist kein Browser-/GPU- oder Tablet-Benchmark und kein garantierter Produktwert.
- Nach der Beleuchtungskorrektur blieben die vier Geometrietests grün; Seiten-/Oberflächennormalen und unveränderte Höhen/Breiten wurden zusätzlich numerisch geprüft.
- Visuelle Browserabnahme wurde versucht, aber nicht durchgeführt: zuerst Nutzungslimit bei der automatischen Freigabeprüfung, danach Browser-URL-Sperre für die isolierte Testansicht. Keine Umgehung dieser Sperre.
- Ein tatsächliches großes Nutzerprojekt im Browser, sichtbare Kantendarstellung, Endgeräte-Speicherverbrauch und subjektive Bildqualität bleiben noch zu prüfen. Kein neuer realer Slice und kein Drucktest durchgeführt.
- Die Slicing-/Geometriequelle, Objekttransformationen und Kameraimplementierung wurden nicht verändert. Die Anzeigequalität ist damit quellseitig verbessert, aber noch nicht vom Benutzer visuell abgenommen.

### Deployment, Prüfsummen und Rollback

- Kanonisches Quellbackup: `v6/backups/2026-09-12-continuous-layer-preview` mit vorherigem Workspace, Frontend-Testdatei und Testläufer.
- Live-Rollbackbackup: `/homeassistant/pcc-backups/v6-frontend/20260912-193144`.
- Live-Ziel: `/homeassistant/www/3d-studio-v6/`.
- **JavaScript:** `cb80e49ca21bd748228b99e1346c945e6f1983a15ef5155af822c5e083d78aaa`.
- **CSS:** `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.
- **Live-Buildmanifest:** `8a4f3eb10fcedb2c0f70ffdbce76f5e435c60de78e9117ad48c0654716c0f488`.
- Der vorherige vorbereitete Manifest-Hash war anders, weil das Deployment neu gebaut wurde. Maßgeblich ist der oben unabhängig auf HA bestätigte Live-Hash.
- Alle drei Artefakte nach Deployment unabhängig über HA-SSH bestätigt. Zusätzlich wurden Marker für vollständige Supportbahnen, Kategorienfilter, Materialzusammenfassung und Alle/Keine im ausgelieferten Bundle nachgewiesen.
- Kein HA-Core-, Worker- oder Druckerneustart; kein Druckstart/-abbruch, keine Materialänderung und kein Slicingauftrag.
- Kein Commit, Tag oder Push behauptet. Die bereits dokumentierte Freigabe für Datei-/SHA-256-Vergleich statt nicht verfügbarem Git-Working-Tree-Aufruf wurde beibehalten.

### Dokumentationsstand und nächste Schritte

1. Layerdarstellung am tatsächlichen Nutzerprojekt visuell abnehmen; bei Auffälligkeiten zuerst diesen Renderpfad korrigieren, ohne Filter/Farben/Zoom zu entfernen.
2. Danach Druckeinstellungseditor über die neun vorhandenen Werte hinaus erweitern, ausschließlich anhand tatsächlich materialisierter und validierter Prozessparameter.
3. Bestehende neun Werte: Schichthöhe, erste Schicht, Wandlinien, Deckschichten, Bodenschichten, Füllgrad, Außenwandgeschwindigkeit, Innenwandgeschwindigkeit, Verfahrgeschwindigkeit.
4. Grafische variable Layerhöhe einschließlich nativer Übergabe und Vorschau bleibt offen.
5. Robuste Schnittflächen-Kappen, Support-/Naht-/Material-Malwerkzeuge und Sammel-Slicing/Warteschlange bleiben offen.
6. Beta-Ausstieg nicht allein durch Entfernen des Labels erklären: verbleibende Browser-/E2E-/visuelle Prüfungen, dokumentierte Kompatibilität, Restore-/Rollback-Nachweise und Releasekriterien weiter verfolgen.
7. Langfristige Roadmap einschließlich nativer Slicer-Unabhängigkeit erhalten; keine vorschnelle Entfernung des funktionierenden Linux-Slicers.


## 20. Verbindliche Priorität nach Benutzerkorrektur – 12.09.2026

- Zuerst die bisher zurückgestellte Erweiterung des Druckeinstellungseditors bearbeiten. Danach hat Layering oberste Priorität; dies ersetzt die Reihenfolge der älteren Abschnitte 19 und der damaligen Übergabe.
- Die Roadmap fortlaufend umsetzen und dokumentieren. Schwierigkeiten sind Anlass zur Fehlersuche und zur Prüfung zulässiger Alternativen, kein Grund für einen stillen Abbruch oder das Vergessen weiterer Aufgaben.
- Technische Blockaden, fehlende Abnahmen und notwendige Freigaben konkret dokumentieren; keine bestandenen Prüfungen oder vollständigen Chat-Erinnerungen behaupten, die nicht vorliegen.
- Bestehende Freigaberegeln für Neustarts und Druckerbefehle sowie Schutzregeln bleiben bestehen. Dokumentation einschließlich deutscher/englischer Änderungsnotizen bei jedem abgeschlossenen Arbeitsschritt fortschreiben.


## 21. Prozesseditor-Erweiterung auf 25 Werte – geprüft und zur Aktivierung vorbereitet, 12.09.2026

### Umsetzung und Funktionsumfang

- Die bestehende Eingabe für neun lokale Prozesswerte wurde um 16 Werte erweitert. Die Feldanzahl wird aus dem tatsächlichen Feldkatalog ermittelt.
- Bestehende Suche, Änderungsvergleich und ausdrückliche Speicherbestätigung bleiben erhalten. Leere Eingaben bleiben ungesetzt; geerbte Werte werden nicht erfunden.
- Zusätzliche Zahlen werden im Frontend und im lokalen Python-Prozessvertrag auf Endlichkeit, Mindestwert und gegebenenfalls Ganzzahligkeit geprüft. Boolesche Werte, leere Strings und ungültige Zahlen werden als Zahlen abgewiesen.
- Die zusätzlichen Schlüssel wurden sowohl im installierten Bambu-Profilbestand auf dem PC als auch im tatsächlichen nativen Linux-Profilbestand nachgewiesen. Es wurden keine Profilvorgaben verändert und keine neuen Hardwaregrenzen behauptet.
- Die vorhandene native Materialisierung übernimmt die Werte über den SHA-256-gebundenen Prozessvertrag. Ihre Rückmeldung enthält jetzt alle angeforderten Prozessschlüssel sowie die bisherigen drei Auftragswerte.
- Der Analysebericht zeigt zusätzlich zu den bisherigen drei Zeilen die weiteren Editorwerte, sobald sie tatsächlich angefordert wurden. Profil, Anforderung, native Rückmeldung und G-Code-Nachweis bleiben getrennt; fehlende Belege bleiben „Nicht nachgewiesen“, Abweichungen „Abweichung“.
- Arraywerte aus nativen Profilen bleiben in der Rückmeldung erhalten und werden vom bestehenden Tabellenrenderer unterstützt.
- Keine Slicer-Engine-, Dispatcher- oder Serveränderung. Der Worker benötigt für diesen Schritt keinen Neustart: geändert wird sein bei Bedarf gestarteter Materialisierungshelfer. Seine kanonische Abhängigkeitsprüfsumme wurde entsprechend aktualisiert.
- Die bisherigen neun Felder und alle Layeränderungen bleiben erhalten. Cloudprofile, Druckerbefehle und Materialschreibpfade wurden in diesem Schritt nicht erweitert.

### Neue lokale Werte und native Zuordnung

| Eingabe | Lokaler Schlüssel | Nativer Schlüssel |
|---|---|---|
| Linienbreite (mm) | `line_width_mm` | `line_width` |
| Außenwand-Linienbreite (mm) | `outer_wall_line_width_mm` | `outer_wall_line_width` |
| Innenwand-Linienbreite (mm) | `inner_wall_line_width_mm` | `inner_wall_line_width` |
| Deckflächen-Linienbreite (mm) | `top_surface_line_width_mm` | `top_surface_line_width` |
| Support-Linienbreite (mm) | `support_line_width_mm` | `support_line_width` |
| Infillgeschwindigkeit (mm/s) | `sparse_infill_speed_mm_s` | `sparse_infill_speed` |
| Massivfüllung-Geschwindigkeit (mm/s) | `internal_solid_infill_speed_mm_s` | `internal_solid_infill_speed` |
| Deckflächengeschwindigkeit (mm/s) | `top_surface_speed_mm_s` | `top_surface_speed` |
| Geschwindigkeit erste Schicht (mm/s) | `initial_layer_speed_mm_s` | `initial_layer_speed` |
| Brückengeschwindigkeit (mm/s) | `bridge_speed_mm_s` | `bridge_speed` |
| Supportabstand oben (mm) | `support_top_z_distance_mm` | `support_top_z_distance` |
| Supportabstand unten (mm) | `support_bottom_z_distance_mm` | `support_bottom_z_distance` |
| Supportabstand seitlich (mm) | `support_object_xy_distance_mm` | `support_object_xy_distance` |
| Support-Interface-Abstand (mm) | `support_interface_spacing_mm` | `support_interface_spacing` |
| Support-Interfaceschichten oben (Schichten) | `support_interface_top_layers` | `support_interface_top_layers` |
| Support-Interfaceschichten unten (Schichten) | `support_interface_bottom_layers` | `support_interface_bottom_layers` |

### Prüfung

- Vollständiges Gate vom **12.09.2026, 19:49:26 Europe/Berlin**: **88 Frontendtests und 361 Python-Tests bestanden**; TypeScript, beide Frontendbuilds, Quellrichtlinie und HA-Compileall erfolgreich.
- Neue Tests prüfen alle 16 zusätzlichen Schlüssel, fehlerhafte Eingaben, Null-/Leerwertbehandlung, native Zuordnung, Materialisierungsrückmeldung sowie bestätigte/fehlende/abweichende Artefaktnachweise.
- Der vorhandene ausführbare Zwei-AMS-Materialisierungstest wurde um die 16 Werte ergänzt. Er erstellt die nativen Prozessdateien und prüft jeden Rückgabewert; er startet weder Slicer noch Drucker.
- Der erste Gate-Lauf zeigte 88 erfolgreiche Frontendtests und 360 erfolgreiche Python-Tests. Ein alter Mengenvergleich erwartete vier Einstellungen bei nun 20 Einstellungen im erweiterten Testprofil. Der Vergleich wurde auf den tatsächlichen Testvertrag umgestellt; alle einzelnen Werte werden weiterhin geprüft. Der folgende Vollgate-Lauf war vollständig grün.
- Im Scratch-Python war pytest nicht installiert; maßgeblich ist das ausgeführte vollständige Gate im kanonischen PC-Projekt mit dessen vorhandener Testumgebung.
- Reales Slicing mit den neuen Werten und visuelle Browserabnahme bleiben offen. Keine Aussage, dass alle 25 Werte bereits an einem echten Druck überprüft wurden.
- Read-only-Abgleich am nativen Worker: alle 16 Schlüssel vorhanden, Helfer noch mit altem Hash, zum Prüfzeitpunkt keine eingereihten oder laufenden Slicingjobs. Dieser Zeitpunkt ersetzt keine erneute Aktivierungsprüfung.

### Bereitstellung, Backups und Status

**Status: geprüft und auf HA im Staging bereitgelegt, noch nicht live aktiviert.** Die laufende Oberfläche ist weiterhin der erfolgreich bereitgestellte Layerstand aus Abschnitt 19.

- Kanonisches Quellbackup: `v6/backups/2026-09-12-process-editor-25/before/`.
- HA-Staging: `/homeassistant/pcc-staging/20260912-editor25/`.
- Geprüftes Paket: `editor-bundle.zip`, 470.920 Byte, SHA-256 `35314679a9d78a097c11e74567848ecb3b3d54e12636f8cf7b344c4c44e62836`.
- Ausgewählte Backend-/Frontenddateien und Abhängigkeitsmanifest aus diesem Paket extrahiert; Pythonquellen auf HA zusätzlich kompiliert.
- Vorabbackup der sechs vorhandenen HA-Dateien: `/homeassistant/pcc-backups/v6-editor25/20260912-pre-activation/`.
- Exakte Alt-/Neuhashes und Stagingstatus: `/homeassistant/pcc-staging/20260912-editor25/activation-manifest.json`.
- Die separate native Workerdatei wurde nur gelesen. Vor ihrer späteren Änderung zusätzlich direkt am Worker sichern und den weiterhin erwarteten Althash prüfen.
- Vorheriger und weiterhin laufender nativer Helfer: `5037431dc78cfddb17722b843621b54dd1687ac054e46ef0680e2b4fed84e681`.
- Keine Live-Datei durch den neuen Editorstand ersetzt, kein HA-/Worker-/Druckerneustart, kein Reload, kein Slice, kein Druckauftrag.

| Datei relativ zum HA-Staging | Geprüfter neuer SHA-256 |
|---|---|
| `custom_components/ultimate_3d_studio_v6/process_profile_contract.py` | `81fb9ce4581ada5ab83a0b4acf85512f23a99c4667afe8353c0fe5548117c67d` |
| `custom_components/ultimate_3d_studio_v6/slicer_backend_router.py` | `d38281a8500e03fac528f12343f6d2068eb5fd3241cfde0e6e47bba6842c08aa` |
| `custom_components/ultimate_3d_studio_v6/materialize-bambu-multimaterial.py` | `2bdc065f62cbf81e71732c6bf9b78836f93cf8d5cbcceb826d8dc9db7c82259d` |
| `www/3d-studio-v6/ultimate-3d-studio.js` | `8f92f68a1388305948d1d7cc3789bb566ac067acd7c7fdb3ee761e2906aa6f0f` |
| `www/3d-studio-v6/ultimate-3d-studio.css` | `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c` |
| `www/3d-studio-v6/ultimate-3d-studio-build.json` | `f3f00da11316c8d3d5806a71eb8358e721334cd4e31f5455d2cc0c79a5f2d253` |
| `host/3d-printer-slicing-server/DEPENDENCY-SHA256SUMS` | `35124b8497491e0135c9f0743a2267a54abe9760a0103b2b911a7a6fc83b37d0` |

### Konkrete Aktivierung nach erforderlicher Freigabe

1. Zunächst exakte Freigabe für **einen HA-Core-Neustart** einholen. Die bestehende Roadmap verlangt für diesen Eingriff ausdrücklich eine Freigabe; die neue Beharrlichkeitsregel hebt sie nicht auf.
2. Gate-/Quellstand, Staginghashes und weiterhin passende Live-Althashes erneut vergleichen. Bei zwischenzeitlichen Änderungen stoppen und abgleichen, nichts überschreiben.
3. Native Warteschlange und laufende Jobs erneut prüfen. Für den atomaren Austausch des Materialisierungshelfers dieselbe exklusive `run/dispatcher.lock`-Verzeichnissperre wie der Dispatcher erwerben; eine fremde Sperre niemals entfernen. Helfer und dessen Abhängigkeitsmanifest separat sichern.
4. Ausschließlich `process_profile_contract.py`, `slicer_backend_router.py` und `materialize-bambu-multimaterial.py` aus dem geprüften Staging in die V6-Komponente übernehmen. Den gleichen Helfer in `/var/lib/homeassistant/3d-printer-slicing-server/` mit passendem Abhängigkeitsmanifest bereitstellen; keinen Worker-Neustart ausführen.
5. Python-/HA-Konfigurationsprüfung; bei Fehlern die gesicherten Dateien zurücklegen. Nach erfolgreicher Prüfung den ausdrücklich freigegebenen einzelnen HA-Core-Neustart ausführen und Zustand/Logs prüfen.
6. Erst nach bestätigtem Backendstart die drei geprüften Frontendartefakte bereitstellen und unabhängig per SHA-256 verifizieren. Keine automatische Seitenneuladung.
7. Beim Rückrollen die zu diesem Schritt gesicherten Backend-/Workerdateien und den zuvor live bestätigten Layer-Frontendstand zusammengehörig wiederherstellen. Ein erneuter HA-Neustart zum Laden zurückgerollter Pythonmodule benötigt wiederum die dafür erforderliche Freigabe.

### Fortsetzung und weiterhin offene Roadmap

- Nach Aktivierung und Prüfung dieser Editorstufe hat **Layering oberste Priorität**, entsprechend der jüngsten Benutzeranweisung in Abschnitt 20.
- Der vollständige Prozesseditor ist damit noch nicht abgeschlossen: unter anderem Infillmuster, Wandreihenfolge, Naht, Bügeln, weitere Beschleunigungs-/Brücken-/Überhangparameter und die passende Trennung von Maschinen-/Filamentparametern bleiben offen. 25 Werte sind keine Behauptung vollständiger Herstellerprofilabdeckung.
- Variable Layerhöhe einschließlich nativer Übergabe und Vorschau, Malwerkzeuge, Schnittflächen-Kappen, Warteschlange und Beta-Releasekriterien weiter verfolgen. Bestehende Funktionen erhalten.
- Roadmap und Projektkontext enthalten die verbindliche Regel: bei Schwierigkeiten weiter untersuchen und zulässige Alternativen nutzen; Hindernisse und notwendige Freigaben offen festhalten. Kein stiller Abbruch und keine erfundenen Erfolgsmeldungen.


## 22. Fortgeltende Freigabe und Aktivierung des 25-Werte-Editors – 12.09.2026

### Verbindliche Benutzerfreigabe

- Der Benutzer hat ausdrücklich zugestimmt: „ja darfst und auch zukünftig, fahre nach plan fort“.
- Diese Freigabe gilt für die jetzt notwendige und für künftig notwendige HA-Core-Neustarts innerhalb der Roadmap. Für denselben bereits freigegebenen Eingriff nicht erneut um Zustimmung bitten.
- Frühere Aussagen, jeder einzelne HA-Core-Neustart benötige eine neue Rückfrage, sind insoweit durch diese neuere Benutzeranweisung ersetzt.
- Zustand, Backup, Qualitätsgate, Datei-/SHA-Abgleich und Rückweg weiterhin prüfen. Keine Freigabe für automatische Druckstarts, Druckerbefehle oder Worker-/Druckerneustarts daraus ableiten.
- Dauerhafter Projektkontext unter `C:\Users\Taracraft\.codex\context\PROJECT_3D_PRINTER_CONTROL_CENTER.md` entsprechend ergänzt. Arbeitsreihenfolge bleibt Editorstufe abschließen, dann Layering vorrangig weiterführen.

### Aktivierung durchgeführt

- Das kanonische Paket wurde erneut gegen alle sieben Staging-Prüfsummen abgeglichen; alle Werte passten. Sämtliche vorhandenen Live-Althashes passten ebenfalls.
- HA-Konfigurationsprüfung vor und nach dem Dateiaustausch erfolgreich. Der erste Aufruf unter sudo hatte keinen Supervisor-Token; der reguläre authentifizierte HA-CLI-Aufruf war erfolgreich. Keine Zugangsdaten ausgegeben.
- Exklusive native `run/dispatcher.lock`-Sperre erworben und anschließend freigegeben. Keine eingereihten oder laufenden Slicingjobs beim Austausch.
- Drei HA-Komponentendateien, der native Materialisierungshelfer und dessen Abhängigkeitsmanifest atomar und mit Prüfsummenprüfung übernommen; Eigentümer und Dateimodi erhalten.
- Aktivierungsbackup: `/homeassistant/pcc-backups/v6-editor25/20260912-200542-activation/` (im Hilfscontainer als `/config/pcc-backups/...` sichtbar). Enthält vorherige HA-Dateien und zuvor vorhandene Workerdateien.
- Ein anfänglicher Installationsaufruf stoppte vor jeglicher Dateiveränderung wegen eines JSON-/Python-Literalfehlers; korrigierter Aufruf war erfolgreich.
- **Genau ein HA-Core-Neustart** ausgelöst. Der aufrufende Connector lieferte nach Wartezeit keinen Erfolgsstatus; der Neustart wurde nicht wiederholt. Unabhängige Prüfung bestätigte HA `running`, Startzeit **2026-09-12T20:06:18.113744912Z** beziehungsweise 22:06:18 Europe/Berlin.
- HA-Konfigurations-API bestätigt geladene Integration `ultimate_3d_studio_v6`. Im gefilterten aktuellen Logausschnitt keine passende V6-Fehler-/Setup-/Tracebackmeldung.
- Profil-API des laufenden HA antwortet erfolgreich: 186 Profile, benutzerdefinierte Profile unterstützt. Dieser Read-only-Test hat kein Benutzerprofil angelegt oder verändert.
- Danach die drei geprüften Editor-Frontendartefakte übernommen und alle sechs HA-Dateihashes unabhängig bestätigt. Die Editorstufe mit 25 Werten ist **aktiv**, nicht mehr nur vorbereitet.
- Kein Worker- oder Druckerneustart, kein Seitenreload, kein realer Slice und kein Drucker-/Materialbefehl.
- Der Editor-JavaScript-Hash `8f92f68a1388305948d1d7cc3789bb566ac067acd7c7fdb3ee761e2906aa6f0f` wurde anschließend durch den nachfolgenden Layerbuild aus Abschnitt 23 abgelöst. Die Editorfunktionen sind darin weiterhin enthalten.

## 23. Layering – verbundene Bahnecken und Konturschluss, 12.09.2026

### Befund und Umsetzung

- Nach der Editoraktivierung wurde entsprechend der Priorität am Layering weitergearbeitet.
- Der zuvor ausgerollte Renderpfad erhielt alle angenommenen Segmente und volle Schichthöhen, erzeugte aber jedes Segment als eigenen rechteckigen Streifen. An Richtungswechseln konnte dadurch eine unbedeckte äußere Ecke zwischen den Streifen bleiben.
- `frontend/toolpath-ribbon-geometry.ts` ergänzt jetzt abgeschrägte Eckverbindungen einschließlich Seitenfläche. Diese füllen die äußere Ecke, ohne unbeschränkt lange Gehrungsspitzen zu erzeugen.
- Ein zusammenhängender Konturzug wird auch an seiner Schlussnaht verbunden, wenn das letzte Ende wieder den tatsächlichen Anfang erreicht.
- Verbindungen nur zwischen direkt aufeinanderfolgenden, akzeptierten Extrusionssegmenten mit übereinstimmendem End-/Startpunkt, Z, Werkzeug, Feature, Kategorie und Darstellungsstil. Toleranzen: XY 0,00001 mm, Z 0,000001 mm.
- Travel, ungültige Geometrie und ausgeblendete Segmente unterbrechen die Verbindungskette. Zwischen versetzten Endpunkten, Werkzeug-/Material- oder Featurewechseln wird keine künstliche Verbindung eingefügt.
- Support-Einzelansicht bleibt flach. Bestehende Glanzmarkierung wird über die Eckverbindung fortgeführt. Farben, Kategorienfilter, Einzellayer/kumulative Darstellung, Zoom, Popup und Slicingpfad bleiben erhalten.
- Keine Segmentausdünnung eingeführt und keine G-Code-Koordinaten verändert. Die Eckgeometrie ist eine Darstellungsnäherung und keine Simulation der exakt gedruckten Strangform.
- Pro nicht geradliniger Verbindung kommen bei räumlicher Darstellung drei Dreiecke hinzu; bei flacher Darstellung eines, optional eines für die Glanzmarkierung. Gesamtgeometrie und Speicher bleiben linear in der sichtbaren Bahnzahl. Kein neuer Gesamt-Speicherdeckel und kein Browser-/GPU-Leistungsnachweis.

### Tests und Deployment

- Drei neue kanonische Frontendtests prüfen:
  1. Numerische Flächenabdeckung der vorher offenen Außenecke bei Links- und Rechtskurven, endliche Normalen und unveränderte Eingangsdaten.
  2. Trennung bei Travel, ausgeblendeten Segmenten, versetzten Endpunkten sowie Werkzeug- und Featurewechseln.
  3. Geschlossene Konturen einschließlich Schlussnaht, flache Darstellung und Glanzmarkierungen.
- Die vier bestehenden Geometrietests einschließlich 180.001 vollständig erhaltener Bahnen bleiben grün. Separater lokaler Lauf: sieben Geometrietests bestanden.
- Vollständiges kanonisches Gate beim Deployment: **91 Frontendtests und 361 Python-Tests bestanden**, Quellrichtlinie, TypeScript, beide Frontendbuilds und HA-Compileall erfolgreich.
- Gate-/Deploymentabschluss: **12.09.2026, 22:11:34 Europe/Berlin**.
- Quellbackup: `v6/backups/2026-09-12-layer-corners/before/`.
- Live-Frontendbackup: `/homeassistant/pcc-backups/v6-frontend/20260912-221134`.
- Alle drei Live-Prüfsummen nach Deployment erneut unabhängig über HA-SSH bestätigt:

| Live-Artefakt | SHA-256 |
|---|---|
| JavaScript | `a16ac1748e6280ba428707f9331d1f1e95a316893ea2c331d38412f5e58e561b` |
| CSS | `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c` |
| Buildmanifest | `1cbe14c292705385a30cb1cd110e89ffba6bf0e87d80e3e34816cc8df135c597` |

- Dieser Layerdeploy erforderte keinen weiteren HA-Neustart. Insgesamt in dieser Fortsetzung genau ein HA-Core-Neustart für den Editor, kein Worker-/Druckerneustart.
- Visuelle Browserabnahme weiterhin offen. Die zuvor gesperrte Browser-Testfläche wurde nicht über andere Wege umgangen. Die Geometrietests ersetzen keine visuelle Bestätigung am tatsächlichen Nutzerprojekt.
- Beta-Version bleibt 6.0.0-beta3. Weder vollständiger Beta-Ausstieg noch vollständiger Hersteller-Prozesseditor behauptet.

### Dokumentation und nächster Roadmapstand

- Vollständige alte Roadmap erhalten und um Abschnitte 22–23 ergänzt; Projektkontext, langfristige Roadmap, Übergabe, Editor-/Layer-Prüfnachweise und deutsche/englische Changelogs fortgeschrieben.
- Layering bleibt oberste aktuelle Priorität: tatsächliche Projektansicht und große reale Modelle visuell prüfen, sobald der zulässige Zugriff verfügbar ist. Variable Layerhöhe einschließlich nativer Übergabe bleibt als eigener noch nicht implementierter Schritt offen.
- Weitere Editorparameter, Schnittflächen-Kappen, Malwerkzeuge, Sammel-Slicing/Warteschlange und Releasekriterien aus der bisherigen Roadmap bleiben offen. Keine Aufgaben stillschweigend entfernt.


## 24. Layering – offene Bahnenden und äußere Flächennormalen, 12.09.2026

### Befund und umgesetzte Korrektur

- Die nach Abschnitt 23 zusammenhängend gezeichneten Bahnen hatten an offenen Anfangs-/Endpunkten noch keine Stirnflächen.
- Die Dreiecksreihenfolge beider seitlichen Bahnflächen erzeugte nach innen gerichtete Normalen. Das war ein Fehler der Beleuchtungsgeometrie; eine visuelle Browserbeobachtung wird damit nicht behauptet.
- Beide Seitenflächen in `frontend/toolpath-ribbon-geometry.ts` sind jetzt nach außen orientiert. Die vorhandene Schichtbeleuchtung bleibt erhalten.
- Offene räumliche Bahnketten erhalten genau eine Stirnfläche mit zwei Dreiecken am Anfang und am Ende. Zusammenhängende gerade Segmente bekommen keine innere Trennfläche.
- Geschlossene Konturen bleiben ohne zusätzliche Stirnflächen an der Schlussnaht; die Eckverbindungen aus Abschnitt 23 bleiben erhalten.
- Travel, ungültige oder ausgeblendete Segmente und unvereinbare Endpunkte/Styles beenden die aktuelle Kette mit Stirnflächen. Neue Ketten beginnen unabhängig.
- Richtungsumkehrungen werden als getrennte offene Läufe behandelt. Die Richtungsprüfung trennt bei einem normierten Skalarprodukt von höchstens -0,999999; damit wird eine direkt zurücklaufende Bahn nicht fälschlich als geschlossene Kontur behandelt.
- Die flache Supportansicht erhält keine senkrechten Stirnflächen. Filter, Farben, Materialzuordnung, Layersteuerung, Zoom, Popup und Slicing bleiben in ihren bisherigen Pfaden.
- Es werden weiterhin alle akzeptierten Segmente gezeichnet, und die Eingangsdaten werden nicht verändert. Je offener räumlicher Kette entstehen vier zusätzliche Dreiecke, unabhängig von deren Segmentzahl.
- Diese Darstellung ist weiterhin eine Vorschaugeometrie aus geschätzten Bahnbreiten. Keine Behauptung einer vollständig geschlossenen Volumengeometrie oder exakt simulierter Extrusionsform.

### Nachweise

- Drei neue Regressionstests zuerst gegen den bisherigen Stand ausgeführt: alle drei schlugen wie erwartet fehl (innere Normalen, fehlende Stirnflächen, ungeschlossene Umkehrläufe).
- Nach der Korrektur sind diese Tests erfolgreich. Geprüft werden positive/negative sowie diagonale Bahnausrichtungen, ausschließlich äußere Flächennormalen, Stirnflächen nur an Kettenenden, fehlende innere Trennflächen und die weiterhin flache Supportdarstellung.
- Die bestehenden Tests für 180.001 vollständig erhaltene Bahnen, Seitenpuffergrenzen, volle Schichthöhen, Filter/Materialwechsel, Eckabdeckung, Konturschluss und Glanzmarkierungen bleiben erfolgreich.
- Bestehende Dreieckszahl-Erwartungen wurden gezielt um die nun zusätzlich notwendigen Stirnflächen erweitert; die unabhängigen Flächen- und Grenzprüfungen bleiben erhalten.
- Separater Geometrielauf: **10 Tests bestanden**.
- Vollständiges kanonisches Deployment-Gate: **94 Frontendtests und 361 Python-Tests bestanden**; Quellrichtlinie, TypeScript, beide Frontendbuilds und HA-Compileall erfolgreich.
- Deploymentabschluss: **12.09.2026, 22:20:52 Europe/Berlin**.

### Live-Stand und Rückweg

- Kanonisches Quellbackup: `v6/backups/2026-09-12-layer-ends/before/`.
- Live-Frontendbackup: `/homeassistant/pcc-backups/v6-frontend/20260912-222052`.
- Alle drei Live-Dateihashes nach Deployment unabhängig über HA-SSH bestätigt:

| Artefakt | Live-SHA-256 |
|---|---|
| JavaScript | `5b0d64c0e6c79022d5cf495ab5f59723edb0ef543248633411eeea69c1bd6a73` |
| CSS | `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c` |
| Buildmanifest | `1025d70bd4fdc5102fd905c0bb624041bb77d2341997d8d3f6099bf912eb7896` |

- In dieser Fortsetzung kein HA-/Worker-/Druckerneustart, kein Seitenreload, kein realer Slice und kein Drucker-/Materialbefehl.
- Der aktive 25-Werte-Editor und die zugehörigen Backend-/Workeränderungen aus Abschnitt 22 bleiben aktiv.
- Die Benutzerfreigabe für künftig notwendige HA-Core-Neustarts im Rahmen der Roadmap gilt weiterhin; keine erneute Rückfrage für denselben Freigabeumfang.

### Offene Abnahme und weitere Roadmap

- Die visuelle Browserabnahme und die Prüfung großer tatsächlicher Nutzerprojekte bleiben offen; der bisherige Browserzugriff war gesperrt und wurde nicht umgangen.
- Grafische variable Layerhöhe mit nativer Übergabe ist weiterhin ein separater offener Schritt. Die hier ergänzten Stirnflächen implementieren diese Funktion nicht.
- Layering bleibt die höchste aktuelle Priorität. Weitere Prozessparameter, Malwerkzeuge, Schnittflächen-Kappen, Sammel-Slicing/Warteschlange und Beta-Abnahmekriterien bleiben unverändert in der fortlaufenden Roadmap.
- Vollständige ursprüngliche Roadmap und alle bisherigen Nachträge erhalten. Deutsche/englische Änderungsnotizen, Übergabe, Layer-/Editor-Prüfnachweise und dauerhafter Projektkontext wurden auf diesen Stand fortgeschrieben.

## 25. Layering - Variable Schichthoehen: native Uebergabe aktiviert (2026-09-13)

Status: aktiviert in Quelle, Home Assistant und echtem Worker-Pfad; grafischer Kurveneditor folgt als naechster Layering-Block.

Umgesetzt:
- Die Studio-Slice-API kann `layer_height_ranges` als JSON-Parameter uebergeben.
- `slicer_plate_views_v2.py` akzeptiert die Bereiche nur als Array und reicht sie durch die bestehende Nozzle-Validierung.
- `slicer_nozzle_profiles.py` validiert maximal 32 geordnete Z-Bereiche ohne Ueberlappung, Z 0..256 mm und Schichthoehen innerhalb des aktiven A1-Duesenvertrags.
- `materialize-bambu-multimaterial.py` schreibt die Bereiche in Bambu Studios nativen `assembled_params[].height_ranges[].range_params.layer_height`-Pfad fuer die zusammengesetzte Modellgruppe 1.
- Der Worker prueft dieselben Bereiche nochmals gegen die aus `target_printer` uebergebenen Min/Max-Layerhoehen.
- Frontend-Typ, Speicherung und Upload-Serialisierung behalten `layer_height_ranges`; bestehende globale/per-Plate Optionen bleiben kompatibel.

Validierung:
- Kanonisches V6-Gate: gruen am 2026-09-13 08:31 Europe/Berlin.
- Gate-Stufen: Frontend-Test/Build gruen, HA-Core-Build gruen, Python 366 Tests gruen, HA compileall gruen.
- Live HA-Core nach Restart verifiziert: Container gestartet 2026-09-13T06:28:12Z, `ultimate_3d_studio_v6` geladen, 186 Profile erreichbar.
- Live Worker materializer-only Probe ohne Druckauftrag: `assembled_params` enthaelt `height_ranges` mit `layer_height: "0.12"`, Summary meldet `variable_layer_heights.applied: true`.
- Kein echter Druck und kein echter Slicer-CLI-Lauf mit Druckjob wurde gestartet.

Hashes / Backups:
- `materialize-bambu-multimaterial.py`: `696f4e68552bfdcfcb7bc29e198d1412dabb273ed2597db44d456950a32a1916`
- `slicer_nozzle_profiles.py`: `e02b7e511524f447ec8183914e74b11f6e80f966408e64e5965afee393327b4f`
- `slicer_plate_views_v2.py`: `ca81d4de0cc1cfa793c66b4010c6f53dc9542ed12bfcec3be2135694cd949e33`
- Worker `DEPENDENCY-SHA256SUMS`: `8af27bee45994bea083a0fc772c8b4d372557feb78c0557342befae1ae0796ad`
- Live Frontend JS: `46853f80e4b815347d2e5e557c681caa821d578e1c836e18e5e8c5fbd929fc54`
- Live Frontend Buildmanifest: `30fdfc58d7452bdc5951c85a05ad32572e4cbf56f5331460a2721e5d9a8ad901`
- Repo-Backup: `backups/2026-09-13-variable-layer-heights/before/`
- HA/Worker-Backup: `/homeassistant/pcc-backups/v6-variable-layer-heights/20260913-062744` und Host-Worker-Backup `/config/pcc-backups/v6-variable-layer-heights/20260913-063413`
- Frontend-Backup: `/homeassistant/pcc-backups/v6-frontend/20260913-083139`

Wichtig fuer den naechsten Schritt:
- Die native Grundlage ist aktiv, aber der sichtbare grafische Editor fuer eine Hoehenkurve ist noch offen.
- Naechster Layering-Block: UI fuer variable Schichthoehen in der aktiven Studio-Oberflaeche, inklusive einfacher Bereichsliste/Preview-Markierung und danach echter nativer Slicer-CLI-Akzeptanztest ohne Druck.

## 26. Layering - Variable Schichthoehen: sichtbare Bereichs-UI aktiviert (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; baut auf der nativen Uebergabe aus Abschnitt 25 auf.

Umgesetzt:
- Das sichtbare `studio-process-options-panel` enthaelt jetzt eine kompakte Liste fuer variable Schichthoehenbereiche.
- Nutzer koennen Bereiche hinzufuegen, Z-Start/Z-Ende/Layerhoehe bearbeiten und Bereiche entfernen.
- Die UI speichert dieselbe Struktur `layer_height_ranges[{min_z_mm,max_z_mm,layer_height_mm}]`, die HA-API und Worker bereits validieren.
- Bestehende Druckeinstellungen bleiben kompatibel; ohne Bereiche wird weiterhin die Standard-Layerhoehe verwendet.
- Die Upload-Serialisierung schreibt aktive Bereiche in den Query-Parameter `layer_height_ranges`, der native Worker schreibt daraus `assembled_params.height_ranges`.

Validierung:
- Kanonisches V6-Gate nach UI-Aenderung: gruen am 2026-09-13 08:39 Europe/Berlin.
- Gate-Stufen: Frontend-Test/Build gruen, HA-Core-Build gruen, Python 366 Tests gruen, HA compileall gruen.
- Frontend live deployed mit unabhängiger Hashpruefung.

Live Frontend:
- `ultimate-3d-studio.js`: `de2d6b5946bb5a47f3b33f8c43146b5616e4bb8958872ecfc119fbae3d5c1607`
- `ultimate-3d-studio.css`: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`
- `ultimate-3d-studio-build.json`: `fcd3b9525ca1ee60c71d2eef7b4f58c52b4b61fbc9d77f42e8b1bbb92fb98da8`
- Frontend-Backup: `/homeassistant/pcc-backups/v6-frontend/20260913-083919`

Offen als naechster Layering-Punkt:
- Preview-Markierungen in der Layeransicht fuer die aktiven Hoehenbereiche.
- Nativer Slicer-CLI-Akzeptanztest mit variablen Hoehen ohne echten Druck.
- Danach feinere Hoehenkurve statt nur Bereichsliste.

## 27/28. Fortsetzung 13.09.2026 - Layering, variable Schichthoehen und native Akzeptanz

- Layeransicht erweitert: aktive variable Schichthoehenbereiche erscheinen in der Vorschau-Seitenleiste und werden anhand des aktuellen Layer-Z-Werts markiert.
- Frontend live nach Gate; aktueller JS-Hash a4615ba32cc43543ce370dff8d715aee14b82c22137294bd751868a475fd8cab, CSS 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c, Manifest 2da7976d988b6f5f0810689f48a531262d3d0aec6b02218b331a8ec273a1f571.
- Bambu-Manifest-Schema korrigiert: min_z/max_z als Zahlen, layer_height im Prozessprofil und in range_params als String.
- Finaler Materializer-Hash e7bb755a74e467f891a9dccf597f16f78b67a816f2196f83a2a17b4e751d650f; Worker-Dependency-Hash 33229942abb41de4bfd16be840226b866ba0ab6b18039994d5bc50802d6007f3.
- Native Akzeptanzjob v6-vlh-accept-20260913T071923Z abgeschlossen: G-Code und G-Code-3MF erzeugt, variable Layerhoehen angewandt, 116 Layer-Marker mit 0,12-mm- und 0,20-mm-Schritten analysiert.
- Kein Druckauftrag, kein Druckstart, kein Materialschreiben und kein Druckerneustart. Naechster Schritt bleibt visuelle Browserabnahme/grafischer Hoehenkurveneditor und danach weitere Roadmap.

Suchmarker: Native Bambu-Akzeptanz fuer variable Schichthoehen ist mit Job v6-vlh-accept-20260913T071923Z dokumentiert; kein Druckauftrag wurde gestartet.

## 29. Layering - Hoehenkurven-Vorschau im Prozessoptions-Editor (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; kleiner Editor-/Layering-Schritt nach der nativen Bambu-Akzeptanz.

Umgesetzt:
- Das Panel fuer variable Schichthoehen zeigt oberhalb der Bereichsliste jetzt eine kompakte Kurven-/Balkenvorschau.
- Die horizontale Balkenbreite folgt der Z-Ausdehnung des Bereichs, die Balkenhoehe folgt der jeweiligen Schichthoehe.
- Die Vorschau wird direkt aus den gespeicherten layer_height_ranges erzeugt; sie fuehrt keine zweite Datenstruktur und keine neue Slicer-Logik ein.
- Ohne aktive Bereiche bleibt der bestehende Leerzustand erhalten.
- Native Uebergabe, HA-/Worker-Validierung, Bambu-Manifestpfad und G-Code-Erzeugung aus Abschnitt 28 bleiben unveraendert.
- Quellbackup: v6/backups/2026-09-13-variable-layer-curve-preview/before/.

Validierung und Live-Stand:
- Neuer Frontend-Quelltest: process options panel exposes a source-owned variable layer-height curve preview.
- Vollstaendiges V6-Gate gruen am 2026-09-13 09:31 Europe/Berlin.
- Deploy-Gate ebenfalls gruen am 2026-09-13 09:31 Europe/Berlin.
- Live ultimate-3d-studio.js: a9754054ff6dbd0c67cd36ee1a0684a267fa3b1edfeca996435b898dc67e08b9
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 013f5580619eb4e8cd09f0ba7c1b08aa2c2a0a4e540b647cb930e8b994906915
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-093136
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browserabnahme der Layeransicht und des Kurveneditors am echten Nutzerprojekt.
- Echte grafische Hoehenkurvenbearbeitung mit Zieh-/Pinselinteraktion statt nur Balkenvorschau und Zahlenliste.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 30. Layering - Direkte Pointer-Bearbeitung der Hoehenkurve (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 29 von reiner Vorschau zu direkter Bedienung.

Umgesetzt:
- Die Hoehenkurve im Prozessoptions-Editor reagiert jetzt auf Pointer/Klick innerhalb vorhandener variabler Schichthoehenbereiche.
- Die X-Position waehlt den betroffenen Z-Bereich, die Y-Position setzt dessen layer_height_mm zwischen 0,04 und 0,56 mm.
- Nach der Aenderung wird derselbe layer_height_ranges-Speicherpfad genutzt wie bei der Zahlenliste; HA-/Worker-Validierung und nativer Bambu-Manifestpfad bleiben unveraendert.
- Der bearbeitete Zahlenwert bekommt Fokus, damit die Aenderung sofort sichtbar und bei Bedarf exakt korrigierbar ist.
- CSS nutzt touch-action:none und Crosshair-Cursor fuer diese Kurvenflaeche. Keine DOM-/Runtime-Injection, kein Reload, keine zweite Datenquelle.
- Quellbackup: v6/backups/2026-09-13-variable-layer-curve-edit/before/.

Validierung und Live-Stand:
- Neuer Frontend-Quelltest: process options panel supports pointer editing for the variable layer-height curve.
- Vollstaendiges V6-Gate gruen am 2026-09-13 14:31 Europe/Berlin.
- Deploy-Gate ebenfalls gruen am 2026-09-13 14:31 Europe/Berlin.
- Live ultimate-3d-studio.js: 4f677c0e13dc3d1c995fb0274d3a307e0f6c5195bb37680339b75ef116dd63b4
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 90dfeb9dbdfa986dde0aaf8492f400db49022252bac67b3c09e8d165e31e83ba
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-143143
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browserabnahme am echten Nutzerprojekt und Bedienpruefung der Kurve mit Maus/Touch.
- Komfortfunktionen fuer echte Hoehenkurvenbearbeitung: Ziehen statt Einzelklick, Bereich teilen/zusammenfuehren, Snap/Presets je Duesenvertrag und Darstellung direkt in der 3D-Layeransicht.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 31. Layering - Drag-Bearbeitung der Hoehenkurve (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 30 von Einzelklick auf Ziehen.

Umgesetzt:
- Die Hoehenkurve fuer variable Schichthoehen unterstuetzt jetzt Pointer-Drag.
- Beim Pointerdown wird die betroffene Kurve verarbeitet, der Pointer wird fuer die Kurvenflaeche gefangen, Pointermove setzt fortlaufend die Schichthoehe, Pointerup oder Pointercancel raeumt die Listener wieder auf.
- Die Berechnung bleibt gleich: X waehlt einen vorhandenen Z-Bereich, Y setzt layer_height_mm im validierten Bereich 0,04..0,56 mm.
- Der Editor schreibt weiterhin ausschliesslich in layer_height_ranges; kein neuer Slicerpfad, kein neues Persistenzmodell und kein Druckerbefehl.
- Quellbackup: v6/backups/2026-09-13-variable-layer-curve-drag/before/.

Validierung und Live-Stand:
- Neuer Frontend-Quelltest: process options panel cleans up drag listeners for variable layer-height curve editing.
- Vollstaendiges V6-Gate gruen am 2026-09-13 14:35 Europe/Berlin.
- Deploy-Gate ebenfalls gruen am 2026-09-13 14:36 Europe/Berlin.
- Live ultimate-3d-studio.js: 6c916f93ecfeea0bb7b57541d2bde78c3d33e2642d8d2cdd7b4be4a52a5acf4d
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 93c3fa1ae38a2b54beff4c9ed64b11ae86841dc107efe1c9c09e6e7035337152
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-143625
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Bereich teilen/zusammenfuehren und Snap/Presets je Duesenvertrag.
- Darstellung der editierbaren Hoehenkurve direkt gekoppelt an die 3D-Layeransicht.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 33. Layering - Duesenvertrag-Presets und Kurven-Snap (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 32 um duesenspezifische Presets fuer variable Schichthoehen.

Umgesetzt:
- Der Workspace reicht den aktiven Nozzle-Durchmesser als nozzle-diameter in das Prozessoptions-Panel.
- Das Panel nutzt den bestehenden nozzle-process-contract und erzeugt daraus Presets zwischen minimaler und maximaler Layerhoehe der aktiven A1-Duese.
- Kurvenbearbeitung per Pointer/Drag snapt jetzt auf diese Presetwerte; die Zahlenfelder bleiben weiterhin direkt editierbar.
- Preset-Buttons setzen die Layerhoehe des aktiven Bereichs und fokussieren danach das zugehoerige Zahlenfeld.
- Ohne erkannte Duese bleibt ein allgemeiner 0,04-0,56-mm-Fallback sichtbar; HA/Worker validieren weiterhin fail-closed gegen den echten Duesenvertrag.
- Keine neue Persistenz und kein zweites Datenmodell: gespeichert wird weiter layer_height_ranges.
- Bei der Umsetzung wurde eine durch den begrenzten Text-Reader abgeschnittene Workspace-Datei aus dem letzten vollstaendigen Source-Backup rekonstruiert und danach mit dem vollen Gate validiert.
- Quellbackup: v6/backups/2026-09-13-variable-layer-nozzle-presets/before/.

Validierung und Live-Stand:
- Frontend-Source-Vertrag in test_v6_nozzle_process_controls.py erweitert.
- Vollstaendiges V6-Gate gruen am 2026-09-13 15:04 Europe/Berlin.
- Deploy-Gate gruen am 2026-09-13 15:04 Europe/Berlin.
- Live ultimate-3d-studio.js: e5aac4dcad1bb02557754379702cadf175f4a2aa62ac59a41bbb56ebd3d6b9cb
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 6f19c4d605e5b16da727fd09b182c589b6f99fd4df1736e83f55f87938394b1f
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-150432
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Darstellung der editierbaren Hoehenkurve direkt gekoppelt an die 3D-Layeransicht.
- Staerkere Inline-Validierung der Zahlenfelder gegen die aktive Duese, ohne Backend-Sicherheitsnetz zu ersetzen.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 34. Layering - Preview-Z-Kopplung der Hoehenkurve (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; koppelt die editierbare Hoehenkurve direkt an die aktuelle Layeransicht.

Umgesetzt:
- Der Workspace berechnet aus der aktuellen Layeransicht die sichtbare Z-Hoehe als visibleLayerZ.
- Der UI-Renderer reicht diesen Wert als preview-z-mm in das Prozessoptions-Panel.
- Das Panel beobachtet preview-z-mm und markiert in der Hoehenkurve den Bereich, dessen Z-Spanne zur aktuellen Preview-Hoehe passt.
- Die Markierung ist rein visuell; layer_height_ranges, Presets, Pointer-/Drag-Bearbeitung und native Bambu-Uebergabe bleiben unveraendert.
- Der bestehende Kurvenvorschau-Test wurde auf die gekoppelte Signatur aktualisiert; der Source-Contract prueft preview-z-mm und visibleLayerZ.
- Quellbackup: v6/backups/2026-09-13-variable-layer-preview-coupling/before/.

Validierung und Live-Stand:
- Vollstaendiges V6-Gate gruen am 2026-09-13 15:09 Europe/Berlin.
- Deploy-Gate gruen am 2026-09-13 15:10 Europe/Berlin.
- Live ultimate-3d-studio.js: 049f6bab056fdd30392f71e911d9ee6b7583e4e4c26a465a3983679afa6a0bba
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 194b2e70dfa26307db0bfa58fe2e37e8a125fe2281daf12919ba408399ea0bfc
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-151021
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Inline-Zahlenvalidierung gegen aktive Duese im Bereichseditor.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 35. Layering - Inline-Duesenvalidierung im Bereichseditor (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 33/34 um direkte Zahlenfeld-Validierung gegen die aktive Duese.

Umgesetzt:
- Die Layerhoehen-Eingaben der variablen Bereiche erhalten min/max direkt aus dem aktiven nozzle-process-contract.
- Manuelle Zahlenwerte ausserhalb des aktiven Duesenbereichs werden direkt am Feld mit einer klaren Meldung blockiert.
- Presetleiste, Pointer-/Drag-Snap und Preview-Z-Markierung nutzen weiter denselben Nozzle-Vertrag.
- Das Backend-/Worker-Sicherheitsnetz bleibt unveraendert fail-closed; die UI-Validierung ersetzt keine native Pruefung.
- Keine neue Persistenz und kein Druckerpfad: gespeichert wird weiter layer_height_ranges.
- Quellbackup: v6/backups/2026-09-13-variable-layer-inline-nozzle-validation/before/.

Validierung und Live-Stand:
- Frontend-Logic-Test und Python-Source-Contract um die Inline-Duesenvalidierung erweitert.
- Vollstaendiges V6-Gate gruen am 2026-09-13 15:14 Europe/Berlin.
- Deploy-Gate gruen am 2026-09-13 15:14 Europe/Berlin.
- Live ultimate-3d-studio.js: d594c76e0b5f935f20f1c7e9e60d9e85d1b5dcd1686491388b9b3ccded2c356e
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 2052c33c11647b44979ee96e499a5a71633ab54f7bbaabd398bc336d0c5b17fb
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-151433
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Weitere Prozesseditorparameter ueber die 25-Werte-Stufe hinaus.
- Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## Update 2026-09-13 - Prozesseditor nach Layering-Schritten

- Stand nach Abschnitt 36: Druckeinstellungseditor erweitert von 25 auf 31 Werte.
- Neue Felder: gap/solid infill speed, ironing speed, support speed, support interface speed, bridge flow ratio.
- Live: Frontend-Hash `3b18cca8602584dc88ca173451e95949787e24f0922e0cf50a6651c90650c782`; Backend-Vertrag `b9486077bd70987ad0c0e1635eba84b5262a3b44064bf4560ab97597c3b40c64`.
- Weiter nach Plan: Layeransicht hat oberste Prioritaet; Browser-/Touch-Abnahme bleibt offen.

## Update 2026-09-13 - Layeransicht nach Editorstufe

- Stand nach Abschnitt 37: variable Layerbereiche wieder in der aktiven Preview-Sidebar sichtbar.
- Layerbedienung erweitert um Erster/Zurueck/Weiter/Letzter neben dem Slider.
- Live: Frontend-Hash `c47833e514564292115a1cfd49671fad9bf2e383b1465305e22217601d25ca6c`; Build-Manifest `050b497712ca2dd1b1e6a261bcee46ddfbb47a9fd39749033b33f61b0e14f75e`.
- Browser-/Touch-Abnahme am echten Nutzerprojekt bleibt offen und ist naechster Layering-Schwerpunkt.

## Update 2026-09-13 - Layeransicht schnelle Spruenge

- Stand nach Abschnitt 38: -10/+10 und direkte Layernummer-Eingabe live.
- Live: Frontend-Hash `c745c34dde507e3df1d65ca337b16e11b2e6e3632d6e3699a764eff8117fa5f1`; Build-Manifest `97086334041f7f960dcb967ff040994dd279553161d7251b2d245f9968b835e2`.
- Weiter offen: echte Browser-/Touch-Abnahme am Nutzerprojekt.

## Update 2026-09-13 - Layeransicht Fokus-Highlight

- Stand nach Abschnitt 39: aktueller Layer hat fokussierte Highlight-Flächen, Historien-Layer bleiben gedimmt.
- Live: Frontend-Hash `a30051474d1262498339497742e5bc66d3d2ed3d5bcc07b5c47228dde7bbedc6`; Build-Manifest `c5447e80c780c0b5a016d4852684bc1ebeddbbd8b33e1ff39e765198f1bb4a60`.
- Browser-Sichtpruefung: HA-Tab sichtbar, rechte Vorgangsliste/Layeransicht-Karte ohne sichtbare Ueberlappung; echte 3D-Layerinteraktion noch nicht abgenommen.

## 2026-09-13 - Layeransicht: Stage-Badge und Opera-Sichttest

- Aktueller Stand: Layering bleibt oberste Prioritaet nach abgeschlossenem 31-Werte-Druckeinstellungseditor.
- Neu live: Preview-Stage-Badge in `frontend/studio-mega-ui-v2.ts` fuer aktive Layeransicht (`Aktive Layeransicht`, Layer X/Y, Z-Hoehe).
- Test: `layer preview stage exposes current layer badge in the canvas`.
- Gate: vollstaendig gruen 2026-09-13 20:53 Europe/Berlin; Deploy gruen 20:54.
- Live-Hashes: JS e8d36e267b294edd44afade152be941d87c6aaed6327e991d2d04eff166d37f2; CSS 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c; Build JSON b3ee5c54bc2a2defb1a27d8db0f0dda0da404bb88c302601e182dc0b5985f50d.
- HA-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-205452; Source-Backup: v6/backups/2026-09-13-layer-preview-stage-badge/before/.
- Opera-MCP: erster V6-Tab war HA-Websocket-disconnected, frischer Tab zeigte echte G-Code-Vorschau mit 399 Layern und 2.176.118 Bahnen. Neues Stage-Badge ist im Live-Bundle vorhanden, aber im Browserbild noch nicht separat bestaetigt.
- Keine Druckerbefehle, kein Materialschreiben, kein Druckstart, kein HA-Core- oder Worker-Neustart.


## 41. Vorgänge-Scroll, Bambu-Supportstile und Zeitprüfung (2026-09-14)

Status: Quellstand geprüft, vollständiges V6-Gate grün, Backend- und Frontend-Dateien kontrolliert auf HA abgelegt. Version bleibt 6.0.0-beta3.

Umgesetzt:
- Das globale Vorgänge-/Slicing-Popup merkt sich Scrollpositionen über Telemetrie-Rerender hinweg. Die Slicing-Warteschlange darf beim Nachladen nicht mehr auf Anfang springen.
- Der Druckeinstellungseditor bietet Bambu-nahe Supportauswahl: Typ Aus/Normal(auto)/Baum(auto) und Stil Standard, Baum schlank, Baum stark, Baum-Hybrid, Baum Organisch.
- "Nur vom Druckbett" ist jetzt ein echter Pipeline-Wert. Deaktiviert bedeutet: Support darf direkt auf Modellflächen starten; support_build_plate_only=false wird nicht mehr versehentlich normalisiert.
- support_style wird vom Frontend an die Plate-Slice-Route gesendet, dort validiert, in der A1-Nozzle-/Prozessvalidierung abgesichert und im nativen Multimaterial-Materializer in die Prozesssettings geschrieben.
- Der native Materializer legt Support-Nachweise für support_mode, support_style, support_on_build_plate_only und support_threshold_angle ab.
- Die G-Code-Zeitanalyse erzeugt einen consistency-Status für fehlende, widersprüchliche oder unplausible Zeitfelder. Das Analysepanel zeigt dann eine Warnung statt einer stillen Scheingenauigkeit.
- Die Zeitkorrektur ist absichtlich eine Plausibilitätswarnung, keine Behauptung, dass ältere bereits erzeugte Slices nachträglich korrekte Zeiten erhalten.
- Quelltests ergänzt für Popup-Scrollstabilität, Bambu-Supportstile, support_style-Routing und support_build_plate_only=false mit Modellkontakt.

Validierung und Live-Stand:
- Vollständiges V6-Gate grün am 2026-09-14 07:05 Europe/Berlin: Frontend-Test/Build, HA-Core-Build, Python-Tests und homeassistant_compileall erfolgreich.
- Bundle SHA-256: b54f7d72b76b560b29fee67fa473fe2d39bf287cb9b6c5aac4f20ca86e15decb.
- Backend-Dateien auf HA installiert und kompiliert: gcode_analysis.py bf68c42cbd2eb09533d06b1fd2548b37099fd3f1688114c16408db8ab34f1f85, slicer_nozzle_profiles.py 1eb163fcef3ff94112d78c9096a313d869f2cd3806a59dbcf550741b1e38c9fc, materialize-bambu-multimaterial.py 17be3820f6983b53e27fe939fc9e1bc54729f70e82400a90371e2b21dd9d18e4, slicer_plate_views_v2.py 5126d5a84a6993699e0e18a7593ef4296b56795184a50755e3e4b423d9a68659.
- Backend-Backup: /homeassistant/pcc-backups/v6-backend/20260914-070545.
- Frontend-Deploy-Gate grün am 2026-09-14 07:06 Europe/Berlin.
- Live ultimate-3d-studio.js: da4ef294589cdf948bf77d421fcde55f1605887f28347e826307dfb6451203a7.
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c.
- Live ultimate-3d-studio-build.json: d8fde1d978a9a9e31f4a1d0e250e25e183f8a3c6b2cf871dfc7a072cc361ce05.
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260914-070608.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Slicingjob, kein Druckerbefehl, kein Materialschreiben und kein Druckstart. Die auf HA abgelegten Python-Routen sind nach HA-Core-Reload/Neustart sicher im laufenden Prozess aktiv.

Weiter offen, höchste Priorität:
- Die geslicte Layeransicht muss der Bambu-Studio-Vorschau deutlich genauer entsprechen: dichtere/flächigere Layerdarstellung statt dünner transparenter Linien, Support und Überhänge sichtbar und farblich nachvollziehbar.
- Support-/Überhang-Analyse muss Fälle melden, die Bambu Studio als problematisch erkennt, insbesondere bei deaktiviertem "Nur vom Druckbett" und Baum-Support am Modell.
- Browser-/Touch-Abnahme am echten Nutzerprojekt mit frischem Cache bleibt erforderlich; keine visuelle Akzeptanz behaupten, bis sie wirklich geprüft wurde.


## 42. Supportstil-Erweiterung und Modellkontakt-Support (2026-09-14)

- Zurückgestellte Erweiterung des Druckeinstellungseditors fortgesetzt: Support-Typ und Support-Stil sind nun getrennte, Bambu-nahe Controls.
- Unterstützte Stile: Standard, Baum schlank, Baum stark, Baum-Hybrid, Baum Organisch.
- "Nur vom Druckbett" ist kein kosmetischer Schalter mehr: deaktiviert erlaubt Modellkontakt-Support und wird als support_build_plate_only=false bis in die native Materialisierung übertragen.
- Validierung schützt Support-Modus, Support-Stil, Modellkontakt-Boolean und Schwellenwinkel im Frontend-, Route- und Nozzle-Vertragspfad.
- Native Prozesssettings enthalten die Supportwerte als Nachweis. Bestehende 25 Editorwerte und variable Schichthöhen bleiben unverändert.
- Gate und Deploy siehe Roadmap Abschnitt 41.


## 43. Layeransicht - Bambu-Studio-Zielbild nach Nutzervergleich (2026-09-14)

- Nutzervergleich aufgenommen: Bambu Studio zeigt die geslicte Ansicht dicht, flächig und layergenau mit klar sichtbaren Supportstrukturen; die V6-Ansicht wirkt noch zu transparent/linienhaft.
- Ziel verschärft: V6 soll die Bambu-Studio-Sliced-Preview nicht nur grob anzeigen, sondern visuell deutlich genauer nachbilden.
- Dazu gehören solide wirkende Bahnflächen, bessere aktuelle-Layer-Dichte, sichtbare Support-/Überhangklassen und eine rechte Layerbedienung ohne Queue-Scrollsprünge.
- Offener Analysepunkt: V6 darf unsupported overhangs nicht übersehen, wenn Bambu Studio für dasselbe Modell eine Support-/Überhangproblematik zeigt.
- Diese Arbeit ist nach der Editor-Erweiterung die oberste Priorität.
