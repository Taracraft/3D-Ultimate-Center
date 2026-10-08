# Layeransicht – Implementierung und Prüfnachweis

Stand: 12.09.2026. Dieses Dokument beschreibt den geprüften und live bereitgestellten Renderpfad; visuelle Browserabnahme steht noch aus.


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


## Neuere Prioritätsentscheidung

Der oben dokumentierte Layerstand ist weiterhin live. Gemäß jüngster Benutzeranweisung wird zunächst die geprüfte Erweiterung des Prozesseditors aktiviert; danach hat Layering oberste Priorität. Siehe Abschnitte 20–21 der [vollständigen Roadmap](V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md). Die dort dokumentierte ausstehende visuelle Layerabnahme bleibt offen.


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

## 27. Preview-Markierungen fuer variable Schichthoehen - 13.09.2026

- Die Layeransicht zeigt die aktiven layer_height_ranges jetzt als Bereichsliste in der Vorschau-Seitenleiste.
- Beim Bewegen des Layerreglers wird der zum aktuellen Z-Wert passende Bereich hervorgehoben.
- Bestehende Layerdarstellung, Filter, Farben, Kamera, Einzellayer/kumulative Ansicht und Slicingpfad bleiben unveraendert.
- Vollgate gruen, Frontend live: JavaScript a4615ba32cc43543ce370dff8d715aee14b82c22137294bd751868a475fd8cab, Manifest 2da7976d988b6f5f0810689f48a531262d3d0aec6b02218b331a8ec273a1f571.
- Visuelle Browserabnahme am echten Nutzerprojekt bleibt offen.

## 28. Native variable Schichthoehen - Slicing-Server-Akzeptanz - 13.09.2026

- Der native Bambu-Pfad akzeptiert assembled_params.height_ranges jetzt mit numerischem min_z/max_z und String-range_params.layer_height.
- Job v6-vlh-accept-20260913T071923Z wurde ohne Druckstart abgeschlossen und erzeugte G-Code sowie G-Code-3MF.
- G-Code-Markeranalyse: 116 Layer, 0,12-mm-Schritte im unteren Bereich, 0,20-mm-Schritte nach dem Uebergang um 5 mm.
- Der fruehere invalid json type for layer_height-Logfehler ist im finalen Lauf nicht mehr vorhanden.
- Materializer-Hash: e7bb755a74e467f891a9dccf597f16f78b67a816f2196f83a2a17b4e751d650f.

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

## Update 2026-09-13 - Variable Bereiche und Touch-Schrittsteuerung

Die G-Code-Vorschau-Sidebar bindet die vorhandenen `layer_height_ranges` wieder direkt ein. Layerwechsel aktualisieren Z-Wert, Bahnanzahl, Extrusion und aktive Range-Markierung zusammen. Zusaetzlich gibt es Erster/Zurueck/Weiter/Letzter als Touch- und Feinsteuerung. Source-Test, volles V6-Gate und Deploy-Gate sind gruen; echte Browser-/Touch-Abnahme steht noch aus.

## Update 2026-09-13 - Schnelle Layer-Spruenge

Die Preview-Sidebar unterstuetzt jetzt -10/+10 und direkte Layernummer-Eingabe. Die UI-Eingabe ist 1-basiert, wird intern auf den 0-basierten Layerindex gemappt und begrenzt. Slider und alle Buttons nutzen denselben Preview-Zustand. Source-Test, volles V6-Gate und Deploy-Gate sind gruen.

## Update 2026-09-13 - Fokus-Highlight fuer aktuellen Layer

Die Toolpath-Vorschau erzeugt Highlight-Flächen nur noch fuer den aktuellen Layer. Historische Layer bleiben sichtbar, werden aber nicht zusaetzlich hervorgehoben. Dadurch soll die ausgewaehlte Ebene bei realen Modellen besser lesbar sein, ohne Bahnen zu reduzieren oder zu ersetzen. Source-Test, volles V6-Gate und Deploy-Gate sind gruen. Browser-Sichtpruefung war nur teilweise moeglich, da der Screenshot nicht die interaktive 3D-Layeransicht zeigte.

## Update 2026-09-13 - Layeransicht: Stage-Badge und Opera-Sichttest

Umgesetzt:
- Die 3D-Stage der Vorschau erhaelt im Preview-Modus ein eigenes Badge mit aktuellem Layer, Layeranzahl und Z-Hoehe.
- Das Badge liegt direkt im Canvas-Bereich und ist als `Aktive Layeransicht` gekennzeichnet.
- Der bestehende Sidebar-Layerzustand bleibt unveraendert; Slider, direkte Layernummer, -10/+10, variable Layerbereiche und Fokus-Highlight bleiben erhalten.
- Keine neue Persistenz, kein Slicerpfad und kein Druckerpfad.

Validierung und Live-Stand:
- Neuer Frontend-Source-Test: `layer preview stage exposes current layer badge in the canvas`.
- Vollstaendiges V6-Gate gruen am 2026-09-13 20:53 Europe/Berlin.
- Deploy-Gate gruen am 2026-09-13 20:54 Europe/Berlin.
- Live ultimate-3d-studio.js: e8d36e267b294edd44afade152be941d87c6aaed6327e991d2d04eff166d37f2.
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c.
- Live ultimate-3d-studio-build.json: b3ee5c54bc2a2defb1a27d8db0f0dda0da404bb88c302601e182dc0b5985f50d.
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-205452.
- Quellbackup: v6/backups/2026-09-13-layer-preview-stage-badge/before/.
- Opera-MCP-Sichttest: echte G-Code-Vorschau am Nutzerprojekt sichtbar; 399 Layer und 2.176.118 Bahnen im UI/Accessibility-Tree bestaetigt. Stage-Badge ist live im Bundle nachgewiesen, im Browserbild aber noch nicht separat sichtbar bestaetigt.

Weiter offen:
- Stage-Badge nach frischem Asset-Load visuell bestaetigen.
- Touch-Bedienung der Layersteuerung am echten Browser weiter abnehmen.
- Weitere Layer-UX, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.


## 43. Layeransicht - Bambu-Studio-Zielbild nach Nutzervergleich (2026-09-14)

- Nutzervergleich aufgenommen: Bambu Studio zeigt die geslicte Ansicht dicht, flächig und layergenau mit klar sichtbaren Supportstrukturen; die V6-Ansicht wirkt noch zu transparent/linienhaft.
- Ziel verschärft: V6 soll die Bambu-Studio-Sliced-Preview nicht nur grob anzeigen, sondern visuell deutlich genauer nachbilden.
- Dazu gehören solide wirkende Bahnflächen, bessere aktuelle-Layer-Dichte, sichtbare Support-/Überhangklassen und eine rechte Layerbedienung ohne Queue-Scrollsprünge.
- Offener Analysepunkt: V6 darf unsupported overhangs nicht übersehen, wenn Bambu Studio für dasselbe Modell eine Support-/Überhangproblematik zeigt.
- Diese Arbeit ist nach der Editor-Erweiterung die oberste Priorität.
