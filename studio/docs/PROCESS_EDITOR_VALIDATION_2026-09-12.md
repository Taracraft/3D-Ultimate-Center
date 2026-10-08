# Prozesseditor – 25 Werte, Implementierung und Prüfnachweis



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


## Nachfolgender Layerstand, 12.09.2026, 22:20 Europe/Berlin

Die Editorstufe bleibt unverändert aktiv. Der danach bereitgestellte Layerbuild ergänzt Stirnflächen und korrigiert Flächennormalen; vollständiges Gate mit 94 Frontendtests und 361 Python-Tests bestanden. Aktuelle Prüfsummen, Backups und offene visuelle Abnahme stehen in Abschnitt 24 der [fortgeschriebenen Roadmap](V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md).

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

## Nachtrag 13.09.2026 - Editorstatus und Layering-Fortsetzung

- Die zuvor zur Aktivierung vorbereitete 25-Werte-Stufe des Prozesseditors ist inzwischen live aktiviert und bleibt Bestandteil des aktuellen Frontend-/Backendstands.
- Weitere Herstellerparameter jenseits der 25 Werte bleiben offen; insbesondere Infillmuster, Wandreihenfolge, Naht, Buegeln, Beschleunigung/Travel/Retraction/Kuehlung und per Objekt abweichende Einstellungen sind nicht erledigt.
- Nach Abschluss der Editorstufe wurde gemaess Prioritaet am Layering weitergearbeitet: variable Schichthoehen besitzen native Uebergabe, sichtbare Bereichs-UI, Preview-Markierungen und eine erfolgreiche native Bambu-Akzeptanz ueber den Slicing-Server.
- Kein realer Druck und kein Druckerbefehl wurden fuer diese Akzeptanz ausgefuehrt. Version bleibt 6.0.0-beta3.

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

## Update 2026-09-13 - 31-Feld-Erweiterung

Der Editorvertrag wurde von 25 auf 31 Felder erweitert. Die neuen Speed-/Flow-Werte sind in `PROCESS_EDITOR_FIELDS`, `_LOCAL_SETTING_MAP`, `_ADVANCED_NUMERIC_RULES` und den Materialisierungs-Tests abgedeckt. Gate und Live-Aktivierung sind gruen; HA Core wurde nach Backend-Austausch neu gestartet.


## 42. Supportstil-Erweiterung und Modellkontakt-Support (2026-09-14)

- Zurückgestellte Erweiterung des Druckeinstellungseditors fortgesetzt: Support-Typ und Support-Stil sind nun getrennte, Bambu-nahe Controls.
- Unterstützte Stile: Standard, Baum schlank, Baum stark, Baum-Hybrid, Baum Organisch.
- "Nur vom Druckbett" ist kein kosmetischer Schalter mehr: deaktiviert erlaubt Modellkontakt-Support und wird als support_build_plate_only=false bis in die native Materialisierung übertragen.
- Validierung schützt Support-Modus, Support-Stil, Modellkontakt-Boolean und Schwellenwinkel im Frontend-, Route- und Nozzle-Vertragspfad.
- Native Prozesssettings enthalten die Supportwerte als Nachweis. Bestehende 25 Editorwerte und variable Schichthöhen bleiben unverändert.
- Gate und Deploy siehe Roadmap Abschnitt 41.
