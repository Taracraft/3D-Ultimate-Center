# Änderungsprotokoll

## 6.0.0 — 06.10.2026

### Stabiles Release

- Beta-Serie beendet und die autoritative Frontend-/Paket- sowie Home-Assistant-Integrationsversion auf **6.0.0** gesetzt.
- Geschlossenen nativen PROFILE_FILES-Vertrag für das kuratierte A1/H2S-Paket, fail-closed Manifeste, Same-Day-Backup/Rollback und Live-SHA-Prüfung beibehalten.
- Mobile Navigationskorrektur aufgenommen: Die horizontale Tableiste bleibt alleiniger Scroll-Owner; aktive Tabs dürfen mobil nicht mehr vertikal aufgezogen werden.
- Stable wird durch Source-Policy, TypeScript, Frontendlogik, Produktionsbuild, Python-/Worker-Tests und Home-Assistant-Compileprüfung abgesichert. Der finale 6.0.0-Gatenachweis steht im Release-Nachweis.
- Interaktive UI-/iPhone-Abnahme und Druckertelemetrie bei ausgeschaltetem Drucker wurden vom Projekteigner ausdrücklich aus den 6.0.0-Release-Gates entfernt. Das ist eine Scope-Entscheidung und kein erfundener Testabschluss.
- MakerWorld-Liveanmeldung/-Import bleibt als dokumentiertes Post-Release-Thema erhalten. Beim Versionswechsel werden keine Druckerbefehle, realen Test-Slices, Uploads, Bewegungen, Heiz-/Filamentaktionen oder Druckstarts ausgeführt.


## Unveroeffentlicht - 30.09.2026

### Malwerkzeug und Malbereiche

- Malbereiche in der Objektliste sind jetzt eigenstaendig auswaehlbar: Klick, Strg/Klick, Shift/Klick, Strg+A und Entf beruecksichtigen die getrennten Eintraege unter "Malbereich".
- Pinsel und Stift stempeln entlang der echten Zeigerbewegung und verfeinern beruehrte Modellflaechen vor dem Farbauftrag auf 0,35 mm Zielkante. Kreis, Rechteck und Text verwenden dieselbe exportierbare Feintriangulation.
- Rechteck/Kreis behalten die glatte Aufziehvorschau ueber der Arbeitsflaeche; der Druckpfad bleibt materialgebunden und nutzt nur geladene AMS-Filamente fuer bemalte Mehrfarbenbereiche.
- Frontend-Logiktests bestanden: 145/145. Produktionsbuild erfolgreich; live auf Home Assistant: JS SHA-256 2aa4b352fc6b9ef2a50bf03f6eec10b564bb98b461eaa27f8f6d4e4cf5039c91, CSS SHA-256 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c.
- Puppet-Port 5000 antwortet lokal, zeigt aber aktuell "Connection Failed" zur HA-URL bzw. zum Access-Token. Deshalb keine gueltige visuelle Puppet-Abnahme in diesem Schritt. Kein Slice, Upload oder Druckstart.


## Layerbahnen – Endflächen und Beleuchtung, 12.09.2026

- Offene räumliche Bahnketten erhalten Stirnflächen ausschließlich an ihren äußeren Enden; geschlossene Konturen und gerade Innenübergänge bleiben ohne zusätzliche Trennflächen.
- Dreiecksorientierung der Seitenflächen korrigiert: Beleuchtungsnormalen zeigen nach außen.
- Richtungsumkehrungen werden getrennt behandelt; flache Supportansicht, Filter, Farben und der 25-Werte-Editor bleiben erhalten.
- Drei neue Regressionstests am Altstand fehlgeschlagen und nach Korrektur bestanden. Vollgate: 94 Frontendtests und 361 Python-Tests erfolgreich.
- Frontend live mit Backup und unabhängig bestätigten SHA-256-Werten; kein Neustart oder Druck-/Slicingauftrag. Visuelle Browserabnahme bleibt offen.
- Details: [Roadmap, Abschnitt 24](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md).

## Aktiviert – Editor und verbundene Layerbahnen, 12.09.2026

- Editor mit 25 validierten lokalen Prozesswerten samt nativer Zuordnung und erweitertem Artefaktnachweis auf HA aktiviert.
- Genau ein freigegebener HA-Core-Neustart; HA und V6-Profil-API anschließend erfolgreich geprüft. Fortgeltende Freigabe für künftig notwendige HA-Core-Neustarts im Roadmaprahmen dokumentiert.
- Layerdarstellung verbindet Richtungswechsel und Schlussnähte zusammenhängender Extrusionskonturen durch begrenzte Eckflächen.
- Travel, versteckte Segmente, Material-/Werkzeug- und Featurewechsel bleiben getrennt. Bestehende Farben, Filter, Layersteuerung und Kamera bleiben erhalten.
- 91 Frontendtests und 361 Python-Tests sowie vollständiges Qualitätsgate erfolgreich. Frontend live mit Backup und unabhängig bestätigten SHA-256-Werten.
- Visuelle Browserabnahme weiterhin offen. Kein realer Slice, Druckbefehl oder Worker-/Druckerneustart.
- [Vollständiger Fortschritt und Nachweise, Abschnitte 22–23](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md).

## Prozesseditor – 25 Werte, 12.09.2026 (geprüft, Aktivierung ausstehend)

- 16 zusätzliche Eingaben für Linienbreiten, Geschwindigkeiten, Supportabstände und Interfaceschichten mit Frontend-/Backendvalidierung und nativer Zuordnung.
- Materialisierungsrückmeldung und Einzelprüfung auf alle angeforderten Editorwerte erweitert; fehlende und abweichende Artefaktnachweise bleiben ausdrücklich erkennbar.
- Alle zusätzlichen Schlüssel im tatsächlichen Linux-Profilbestand bestätigt. 88 Frontendtests und 361 Python-Tests sowie vollständiges Build-/Compilegate erfolgreich.
- Geprüftes Paket auf HA im Staging, Altstand gesichert. Noch nicht live: Aktivierung benötigt einen ausdrücklich freigegebenen HA-Core-Neustart. Kein Worker-Neustart, Slice oder Druck erfolgt.
- Benutzerpriorität fortgeschrieben: Editorstufe aktivieren/prüfen, danach Layering vorrangig weiterführen; Hindernisse bearbeiten und alle Dokumente fortschreiben.
- Details und weitere offene Parameter: [Roadmap, Abschnitte 20–21](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md) und [Editor-Prüfnachweis](docs/PROCESS_EDITOR_VALIDATION_2026-09-12.md).

## Unveröffentlicht — 12.09.2026

### Durchgängige Layeransicht

- Neuer TypeScript-Geometriebaustein erhält alle nach den bestehenden Sichtbarkeitsregeln angenommenen Extrusionsbahnen; keine schrittweise Ausdünnung mehr.
- Volle Schichthöhe und geschätzte Bahnbreite ohne bisherige prozentuale Verkleinerung. Beleuchtung erhält die Erkennbarkeit einzelner Schichten.
- Geometriepuffer werden seitenweise erstellt. Gesamtspeicher wächst weiterhin mit der sichtbaren Bahnzahl.
- Bestehende Filter, Material-/Strukturfarben, Supportansicht, Layersteuerung und Kamera bleiben im bisherigen Vorschaupfad.
- Vollgate einschließlich 87 Frontendtests und 343 Python-Tests bestanden; Frontend live mit Backup und unabhängig bestätigten SHA-256-Werten.
- Browserabnahme durch Zugriffssperre noch offen; kein realer Slice, Druckauftrag oder Neustart.
- Vorgefundene Transfer-/Bestätigungsdialog-Korrekturen bleiben erhalten. Druckeinstellungseditor folgt nach Layerabnahme; Version bleibt 6.0.0-beta3.
- Vollständige Historie und offene Releasekriterien: [Fortgeschriebene Roadmap](docs/V6-Studio-Vollanalyse-und-Roadmap-2026-09-09.md), Abschnitte 18–19.

## Unveröffentlicht — 10.09.2026

### 3D Ultimate Studio und Profilwahrheit

- Der sichtbare Produktname wurde zentral auf **3D Ultimate Studio** und der Slicer auf **3D Ultimate Slicer** umgestellt.
- Interne V6-Domain, API-Routen, Custom-Element-Namen, Entity-IDs und Speicherkeys bleiben kompatibel und unverändert.
- Sliceraufträge zeigen jetzt getrennt **gewählt**, **im Slicer angewandt** und **im Artefakt bestätigt**.
- Die Artefaktbestätigung stammt ausschließlich aus der Analyse des erzeugten G-Code-3MF mit Prozesseinstellungen, Materialkanälen, Farben und Filamentarten.
- Produktions-3MF mit verknüpften Komponenten werden sicher aufgelöst, als Gruppe innerhalb der Druckplatte platziert und für 0,2 / 0,4 / 0,6 / 0,8 mm erfolgreich geslicet.
- Vollständiges V6-Qualitätsgate und kontrollierter Home-Assistant-Frontend-Deploy mit SHA-256 und Rollback-Backup bestanden.
- Kein Druckauftrag und keine Änderung an V5.

## 6.0.0-beta3 — 12.07.2026

### Offizieller Wechsel von Alpha zu Beta

- Ultimate 3D Studio V6 verlässt offiziell die Alpha-Phase.
- Der aktuelle funktionsfähige und real getestete Stand wird als **6.0.0-beta3** festgeschrieben.
- Erster physisch bestätigter Multicolor-Druck über Bambu Lab A1 und AMS Lite direkt aus Ultimate 3D Studio V6.

### Multicolor, AMS und Direktdruck

- Autoritative Objekt-, Extruder- und AMS-Slot-Zuordnung ohne stillen Rückfall auf die externe Spule.
- Mehrfarbenslicing, Reinigungsturm, Filamentwechsel und Direktdruck erfolgreich im realen Druck bestätigt.
- Native Bambu-Druckplattenauswahl einschließlich profilabhängiger Druckbetttemperatur.
- G-Code-Endkontrolle für Druckplattentyp, M140/M190, Reinigungsturm und Druckflächenbegrenzung.
- Zweistufige Druckfreigabe mit SHA-256-Prüfung und serverseitig erzwungenem AMS-Mapping.

### Studio und Slicer

- CAD-Studio mit mehreren Druckplatten, Objekttransformationen, Farben, AMS-Zuweisungen und realer G-Code-Vorschau.
- Studio-Sitzung wird in IndexedDB gespeichert und bis zur ausdrücklichen Löschung wiederhergestellt.
- Verspätete Profil- und Druckerinitialisierung erzeugt keinen destruktiven einmaligen Studio-Refresh mehr.
- Reinigungsturmposition wird aus der aktiven Druckplatte übernommen und gegen die reale Druckfläche validiert.
- Material-, Zeit-, Layer-, Druckschritt- und Materialwechselanalyse aus dem erzeugten G-Code.

### Druckerstatus und Bedienung

- Persistente Kamera- und Druckdialoge ohne Telemetrie-bedingtes Schließen.
- Monotone A1-Druckphasenanzeige mit getrennten Reinigungsphasen vor und nach der Flow-Kalibrierung.
- Supportanalyse berücksichtigt aufeinanderliegende, seitlich verbundene und objektübergreifend gestützte Modellteile.
- Drucker-, Düsen-, Filament-, Prozess- und Druckplattenprofile können aus dem lokalen Katalog entfernt werden.

### Prüfung

- Reale Multicolor-Ausgabe auf Bambu Lab A1 mit AMS Lite erfolgreich bestätigt.
- Frontend-Quellrichtlinie ohne Verstöße bestanden.
- Frontend-Logiktests, Strict-TypeScript- und Produktionsbuild bestanden.
- Python-Tests und Home-Assistant-Compile-Prüfung bestanden.
- Keine MutationObserver-, Prototype-, DOM-Injection- oder Runtime-Layout-Patches.

## 6.0.0-beta2 — 06.07.2026

### Stabiler Dashboard-Stand

- Das aktuelle Desktop- und Mobil-Layout wurde als verbindlicher visueller Stand **beta-v2** festgelegt.
- Die Desktop-Breite des Slicers wurde durch getrennte Layout-Namensräume für App-Shell und Slicer korrigiert.
- Das funktionierende mobile Layout sowie Galerie, CAD-Studio, Profile, Aufgaben und System bleiben unverändert.
- Keine MutationObserver-, Prototype-, DOM-Injection- oder Runtime-Layout-Patches.

### Direktdruck

- Der sichtbare Ein-Klick-Direktdruck bleibt unverändert.
- Das Frontend verwendet wieder die im laufenden Home Assistant registrierten Endpunkte: zuerst `prepare`, danach unmittelbar `start` innerhalb derselben bestätigten Benutzeraktion.
- Die nicht registrierte Route `/print/execute`, die HTTP 404 verursachte, wird nicht mehr aufgerufen.
- FTPS-Artefaktprüfung, SHA-256-Vergleich, AMS-Zuordnung und Kalibrierungsoptionen bleiben erhalten.

### Prüfung

- Frontend-Quellrichtlinie ohne Verstöße bestanden.
- Frontend-Logiktests, Strict-TypeScript- und Produktionsbuild bestanden.
- Python-Tests und Home-Assistant-Compile-Prüfung bestanden.

## 6.0.0-beta1 — 05.07.2026

- Echtes CAD-Studio mit mehreren Druckplatten, realen Abmessungen, Koordinatenachsen und direkter Übergabe an den Slicer.
- Echtes Bambu-Studio-CLI-Slicing mit Original-, Cloud- und lokalen Benutzerprofilen.
- Vollständig editierbare Drucker-, Düsen-, Filament-, Prozess- und Druckplattenprofile.
- Authentifizierter Bambu-LAN-Direktdruck mit GCode-3MF-Prüfung, SHA-256, FTPS-Upload und MQTT-Start.
- Zweistufige Freigabe: zuerst nur Upload, danach exakte Eingabe von `DRUCKEN` vor dem realen Startbefehl.
- AMS-Slot-Prüfung sowie Optionen für Druckbettnivellierung, Flow-, Vibrationskalibrierung und Timelapse.
- MakerWorld-Details, 3MF-Download, STL-Konvertierung und Mehrfachfilter.
- Native Fortschrittsbalken in Steuerzentrale, System und Slicer.
- Globale Progress-Enhancer und periodische DOM-Scanner vollständig entfernt.
- Frontend-Quellrichtlinie gegen MutationObserver, Prototype-Manipulation und Runtime-Enhancer verschärft.
- Galerie und V5 beta38 unverändert gelassen.

### Prüfung

- 10 DOM-freie Frontend-Logiktests bestanden.
- Strict TypeScript und Produktionsbuild bestanden.
- 119 Python-Tests bestanden.
- Home-Assistant-Compile-Prüfung bestanden.

## 2026-09-13 - Layering: variable Schichthoehen nativ vorbereitet

- `layer_height_ranges` wird vom Studio-Upload bis zum nativen Bambu-`assembled_params.height_ranges`-Manifest durchgereicht.
- HA-API, Nozzle-Vertrag und Worker validieren die Bereiche streng gegen A1-Bauhoehe und Duesen-Layerhoehen.
- Live aktiviert mit HA-Core-Restart, Worker-Hostpfad korrigiert und materializer-only Liveprobe ohne Druckauftrag bestanden.

## 2026-09-13 - Layering: UI fuer variable Schichthoehen

- Das sichtbare Slicer-Optionspanel hat jetzt eine Bereichsliste fuer variable Schichthoehen.
- Hinzufuegen, Bearbeiten und Entfernen von Z-Bereichen speichert `layer_height_ranges` und nutzt den aktivierten nativen Manifestpfad.
- Vollstaendiges V6-Gate gruen, Frontend live deployed.

## 2026-09-13 - Layering: Preview-Markierungen und native Bambu-Abnahme

- Die Layeransicht zeigt aktive Bereiche variabler Schichthoehen jetzt in der Vorschau-Seitenleiste; die aktuelle Vorschau-Z-Hoehe markiert den passenden Bereich. Bestehende Vorschau, Filter, Farben und Kamera bleiben erhalten.
- Bambu-Studio-CLI-Kompatibilitaet fuer assembled_params.height_ranges korrigiert: min_z und max_z werden als JSON-Zahlen geschrieben, range_params.layer_height bleibt wie vom Bambu-Prozessschema verlangt ein String.
- Synthetischer nativer Slicing-Server-Akzeptanzjob ohne Druckerbefehl ausgefuehrt. Bambu Studio lief durch, erzeugte G-Code und G-Code-3MF, akzeptierte die Hoehenbereiche und meldete den vorherigen invalid json type for layer_height-Fehler nicht mehr.
- Gezielte G-Code-Analyse des Jobs v6-vlh-accept-20260913T071923Z: 116 Layer-Marker, 0,12-mm-Schritte im unteren Bereich und 0,20-mm-Schritte nach dem Uebergang um 5 mm.
- Version bleibt 6.0.0-beta3; visuelle Browserabnahme, grafischer Hoehenkurveneditor, weitere Prozesseditorwerte, Malwerkzeuge und Releasekriterien bleiben offen.

## 2026-09-13 - Layering: Hoehenkurven-Vorschau fuer variable Schichthoehen

- Ueber der Bereichsliste fuer variable Schichthoehen zeigt der Prozessoptions-Editor jetzt eine kompakte quellseitige Hoehenkurven-Vorschau.
- Die Vorschau skaliert Bereichsbreite nach Z-Ausdehnung und Balkenhoehe nach Layerhoehe aus den aktiven layer_height_ranges; die native Uebergabe bleibt unveraendert.
- Ein Frontend-Quelltest sichert die UI-Marker der Kurvenvorschau im V6-Gate ab.
- Vollstaendiges V6-Gate gruen und Frontend live deployed mit Rollback-Backup. JavaScript-SHA-256 a9754054ff6dbd0c67cd36ee1a0684a267fa3b1edfeca996435b898dc67e08b9; Buildmanifest 013f5580619eb4e8cd09f0ba7c1b08aa2c2a0a4e540b647cb930e8b994906915.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl und kein Druckstart.

## 2026-09-13 - Layering: Pointer-Bearbeitung der variablen Hoehenkurve

- Die variable Schichthoehenkurve im Prozessoptions-Editor ist direkt bedienbar: X waehlt einen bestehenden Z-Bereich, Y setzt dessen layer_height_mm.
- Der Editor schreibt weiter in den vorhandenen layer_height_ranges-Speicher und nativen Bambu-Uebergabepfad; kein zweites Datenmodell und kein Druckerbefehl.
- Frontend-Quelltest fuer den Pointer-Editing-Vertrag ergaenzt.
- Vollstaendiges V6-Gate gruen und Frontend live deployed. JavaScript-SHA-256 4f677c0e13dc3d1c995fb0274d3a307e0f6c5195bb37680339b75ef116dd63b4; Buildmanifest 90dfeb9dbdfa986dde0aaf8492f400db49022252bac67b3c09e8d165e31e83ba.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl und kein Druckstart.

## 2026-09-13 - Layering: Drag-Bearbeitung der variablen Hoehenkurve

- Die variable Schichthoehenkurve wurde von Einzelklick auf Pointer-Drag erweitert.
- Pointer-Capture, Pointermove und Pointerup/Cancel-Aufraeumen halten den Bearbeitungspfad im quellseitigen Prozessoptions-Panel.
- Der Editor schreibt weiterhin nur layer_height_ranges und laesst die native Bambu-Uebergabe unveraendert.
- Vollstaendiges V6-Gate gruen und Frontend live deployed. JavaScript-SHA-256 6c916f93ecfeea0bb7b57541d2bde78c3d33e2642d8d2cdd7b4be4a52a5acf4d; Buildmanifest 93c3fa1ae38a2b54beff4c9ed64b11ae86841dc107efe1c9c09e6e7035337152.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl und kein Druckstart.

## 2026-09-13 - Layering: Duesen-Presets und Kurven-Snap

- Der aktive Duesendurchmesser wird vom Studio-Workspace in das Prozessoptions-Panel gereicht.
- Variable Schichthoehen erhalten Presets aus dem Duesenvertrag; Pointer-/Drag-Bearbeitung der Kurve snapt auf diese Werte.
- Preset-Schaltflaechen aktualisieren nur den aktiven Bereich und behalten die vorhandene layer_height_ranges-Persistenz sowie native Bambu-Uebergabe bei.
- Eine waehrend der Umsetzung durch den begrenzten Text-Reader abgeschnittene Workspace-Datei wurde aus dem letzten vollstaendigen Backup rekonstruiert und mit dem vollstaendigen V6-Gate validiert.
- Vollstaendiges V6-Gate gruen und Frontend live deployed. JavaScript-SHA-256 e5aac4dcad1bb02557754379702cadf175f4a2aa62ac59a41bbb56ebd3d6b9cb; Buildmanifest 6f19c4d605e5b16da727fd09b182c589b6f99fd4df1736e83f55f87938394b1f.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl und kein Druckstart.

## 2026-09-13 - Layering: Preview-Z-Kopplung der Hoehenkurve

- Die aktuell sichtbare Preview-Z-Hoehe wird aus der Layeransicht in das Prozessoptions-Panel gereicht.
- Die variable Hoehenkurve markiert jetzt den Bereich, der die aktuelle Preview-Hoehe enthaelt.
- Die Kopplung ist rein visuell; layer_height_ranges-Persistenz, Duesen-Presets, Pointer-/Drag-Bearbeitung und native Bambu-Uebergabe bleiben unveraendert.
- Vollstaendiges V6-Gate gruen und Frontend live deployed. JavaScript-SHA-256 049f6bab056fdd30392f71e911d9ee6b7583e4e4c26a465a3983679afa6a0bba; Buildmanifest 194b2e70dfa26307db0bfa58fe2e37e8a125fe2281daf12919ba408399ea0bfc.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl und kein Druckstart.

## 2026-09-13 - Layering: Inline-Duesenvalidierung fuer variable Bereiche

- Die Layerhoehen-Eingaben variabler Bereiche nutzen jetzt min/max aus dem aktiven Duesen-Prozessvertrag.
- Manuelle Layerhoehen ausserhalb der aktiven Duesengrenzen werden direkt im Prozessoptions-Panel blockiert.
- Presets, Kurven-Snap, Preview-Z-Markierung und native Bambu-Uebergabe verwenden weiterhin denselben layer_height_ranges-Pfad.
- Vollstaendiges V6-Gate gruen und Frontend live deployed. JavaScript-SHA-256 d594c76e0b5f935f20f1c7e9e60d9e85d1b5dcd1686491388b9b3ccded2c356e; Buildmanifest 2052c33c11647b44979ee96e499a5a71633ab54f7bbaabd398bc336d0c5b17fb.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl und kein Druckstart.

## 2026-09-13 - Druckeinstellungseditor 31 Werte

- V6-Druckeinstellungseditor von 25 auf 31 materialisierte numerische Felder erweitert.
- Lueckenfuellung, solide Fuellung, Buegeln, Support, Support-Interface und Brueckenfluss ergaenzt.
- Frontend-Feldmodell, Home-Assistant-Prozessvertrag und Python-Tests angeglichen.
- Backend-Vertrag mit Backup und HA-Core-Neustart live aktiviert; kein Druckerbefehl und kein Druckstart.

## 2026-09-13 - Layeransicht Touch-Schrittsteuerung

- Variable Schichthoehenbereiche werden wieder direkt in der aktiven G-Code-Vorschau-Sidebar gerendert.
- Layer-Slider um Erster/Zurueck/Weiter/Letzter fuer Touch- und Feinpruefung erweitert.
- Slider und Stepper bleiben auf dem stabilen Preview-Refresh-Pfad; vollstaendiges V6-Gate und Deploy-Gate gruen.
- Keine Backend-Aenderung, kein HA-Core-Neustart, kein Worker-Neustart und kein Druckerbefehl.

## 2026-09-13 - Layeransicht schnelle Spruenge

- G-Code-Vorschau um -10/+10-Layerspruenge und direkte Layernummer-Eingabe erweitert.
- Slider, Schrittbuttons und Direkteingabe bleiben mit Bahnanzahl, Extrusion, Z-Hoehe und aktiver variabler Layer-Range synchron.
- Vollstaendiges V6-Gate und Deploy-Gate gruen; keine Backend-Aenderung und kein Druckerbefehl.

## 2026-09-13 - Aktueller Layer Fokus-Highlight

- Toolpath-Highlights auf den ausgewaehlten/aktuellen Layer fokussiert; vorherige Layer bleiben nur gedimmter Kontext.
- Echte G-Code-Bahnen, Materialfarben und Drucktypfarben bleiben erhalten; kein Sampling, keine erfundene Geometrie und kein Runtime-Patch.
- Browser-Screenshot des Live-HA-Tabs bestaetigt offene Seite und nicht ueberlappende rechte Vorgangsliste; die interaktive 3D-Layeransicht war im Screenshot noch nicht sichtbar.
- Vollstaendiges V6-Gate und Deploy-Gate gruen; keine Backend-Aenderung und kein Druckerbefehl.

## 2026-09-13 - Layeransicht: Stage-Badge und Opera-Sichttest

- Sichtbares Stage-Badge fuer die aktive G-Code-Layeransicht ergaenzt: Layernummer, Layeranzahl und Z-Hoehe stehen direkt in der 3D-Flaeche.
- Frontend-Source-Test fuer das Stage-Badge ergaenzt.
- Vollstaendiges V6-Gate und Deploy-Gate bestanden; Live-JS `e8d36e267b294edd44afade152be941d87c6aaed6327e991d2d04eff166d37f2`.
- Opera-MCP-Sichttest bestaetigt echte Projekt-Layeransicht mit 399 Layern und 2.176.118 Bahnen. Separate Browser-Sichtbarkeit des neuen Badges bleibt nach frischem Cache noch nachzupruefen.


## 2026-09-14 - Vorgänge-Scroll, Bambu-Supportstile und Zeitprüfung

- Die Scrollpositionen im globalen Vorgänge-/Slicing-Popup bleiben jetzt bei Telemetrie-Rerendern erhalten; die Warteschlange springt beim Scrollen nicht mehr automatisch nach oben.
- Der Prozesseditor enthält Bambu-nahe Supportstile: Standard, Baum schlank, Baum stark, Baum-Hybrid und Baum Organisch.
- Modellkontakt-Support ist durchgereicht: wenn "Nur vom Druckbett" deaktiviert ist, läuft support_build_plate_only=false durch Frontend, Plate-Slice-Route, Backend-Validierung und native Materialisierung.
- Die native Prozessmaterialisierung protokolliert support_mode, support_style, support_on_build_plate_only und support_threshold_angle in den Prozess-Evidenzen.
- Die G-Code-Analyse markiert fehlende oder widersprüchliche Zeitfelder und zeigt im Analysepanel eine Warnung, statt unplausible Druckdauerwerte still als verbindlich zu behandeln.
- Vollständiges V6-Gate zweimal grün; Backend-Dateien live mit Backup /homeassistant/pcc-backups/v6-backend/20260914-070545 und Frontend live mit Backup /homeassistant/pcc-backups/v6-frontend/20260914-070608.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Slicingjob, kein Druckerbefehl und kein Materialschreiben.
- Nächste Priorität: Layeransicht deutlich näher an die geslicte Bambu-Studio-Ansicht bringen, inklusive dichter/flächiger Layerdarstellung und sichtbarer Überhang-/Supportauswertung.

## 2026-09-30 Supportwarnung Filamentprofile Puppet

- Repariert: V6 Studio zeigt die Filamentprofile wieder als ein gemeinsames Menü "Filamentprofile"; AMS und Externe Spule bleiben als Materialquelle auswählbar.
- Repariert: Druckprofil-/Prozesslogik bleibt rechts bei Düse/Druckprofil; das überflüssige linke Druckerprofil-Menü wurde aus der Studio-Profilbar entfernt.
- Repariert: Supportwarnung nutzt ein natives Modal, bleibt auch bei Re-Render stabil, zeigt alle betroffenen Objekte und blockiert Slice/Upload bis zur Benutzerentscheidung.
- Repariert: Floating-Support-Heuristik erkennt kleine/gespiegelte Abwärtsflächen zuverlässiger.
- Tests: TypeScript/Frontend/Build grün, 145 Frontend-Logic-Tests grün, Python-Gate 519 Tests + 3 Subtests grün.
- Live: HA-Frontend-Artefakte mit SHA-256 verifiziert; Puppet Port 5000 wieder funktionsfähig und als PNG getestet.

## 2026-09-30 Slicing-Druckpfad-Prüfung

- Geprüft: Bambu A1 ist online/idle; V6 und nativer Slicing Server sind ready.
- Geprüft: Bekannter V6-3MF-A1-Job wurde erneut erfolgreich mit Bambu Studio gesliced, ohne Druckauftrag zu starten.
- Repariert: Slicing-Diagnose zeigt nach erfolgreichem letzten Job nicht mehr fälschlich eine alte Log-Fehlerzeile als aktuellen Fehler.
- Hinweis: Minimal-STL mit Defaultprofil schlägt noch beim Bambu-Studio-3MF-Export fehl; das ist als separater Defaultprofil-/Importfall offen.

## 2026-09-30 Roh-STL-Bambu-Slicing-Fix

- Repariert: Roh-STL-Dateien werden im nativen Bambu-Studio-Slicingpfad jetzt korrekt als Eingabedatei an Bambu Studio übergeben.
- Verifiziert: Minimaler STL-Testjob wurde erfolgreich gesliced, ohne einen Druckauftrag zu starten.
- Verifiziert: Bambu A1 blieb `IDLE`, letzter Slicingfehler `none`.
