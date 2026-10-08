# 2026-09-30 Malwerkzeug

- Repariert: Malbereich-Auswahl in der Objektliste, Mehrfachauswahl und Entfernen ueber Entf.
- Repariert: Pinsel/Stift stempeln entlang schneller Bewegungen; adaptive Oberflaechenverfeinerung auf 0,35 mm Zielkante vor Materialauftrag.
- Validiert: Frontend-Logiktests 145/145, Produktionsbuild OK, HA-Live-Hashes JS 2aa4b352fc6b9ef2a50bf03f6eec10b564bb98b461eaa27f8f6d4e4cf5039c91 und CSS 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c.
- Blockiert: Puppet Port 5000 antwortet, aber Add-on zeigt "Connection Failed" zur Home-Assistant-URL bzw. zum Access-Token; daher kein gueltiger visueller Puppet-Test.
- Nicht gemacht: Kein Slice, kein Upload, kein Druckstart.

## 2026-10-01 - Profile, G-Code-Bausteine, MakerWorld und Connector-Pruefung

- Tara MCP geprueft: JARVISPCConnector laeuft als Windows-Dienst, TCP 192.168.100.10:8767 ist erreichbar. Langlaeufer koennen das MCP-Gateway mit HTTP 504 abbrechen, der PC selbst war dabei nicht ueberlastet.
- HA MCP geprueft: Home Assistant 2026.9.3 laeuft. Puppet wird nicht ueber Opera geprueft; relevant ist HA lokal Port 5000.
- Puppet-Stand: Port 5000 lauscht lokal auf HA und liefert HTML, meldet aber intern "Puppet - Connection Failed". Das ist ein Puppet-Zielverbindungsproblem, kein toter Port.
- Profilregel: Startsound, Endsound, G-Code 1 und G-Code 2 sind druckprofilgekoppelte Bausteine. Im Studio muessen sie als vier eigene Auswahlfelder sichtbar sein; in Profile muessen sie separat pflegbar sein, ohne als normales aktiv waehlbares Druckprofil zu wirken.
- Umgesetzt im Arbeitsstand: Das alte einzelne Benutzer-G-Code-Auswahlfeld wurde durch vier Auswahlfelder ersetzt. Die Profile-Seite trennt Druckprofile und G-Code-Bausteine ueber eigene Gruppen; Bausteine sind nicht mehr als aktives Druckprofil waehlbar.
- MakerWorld-Aufnahme: "Ideen fuer Sie" darf nicht leer bleiben, Empfehlungen/Vorschlaege muessen geladen werden, Druckdateien brauchen Alternativ-/kompatible Profile anderer Drucker, und Beschreibungsbilder/HTML duerfen nicht ausgeblendet oder verschluckt werden.
- Gate-Nachweis nach der Profil-/G-Code-Aenderung: Frontend-Status success=true, Python-Status success=true, connector-v6-quality-gate success=true mit vier erfolgreichen Stufen.
- Sicherheit: Kein Druckstart erfolgt. Live-Deploy erst nach gruener Buildausgabe und anschliessender HA-Dateipruefung.
- Live-Nachtrag 23:24: Frontend-JS gezielt ueber HA-SSH aus kanonischer Quelle aktualisiert, da der lange MCP-Deploy mit 504 abbrach. Live-SHA: 045f7c684c3fcb0228801f18d9765488cff6fb75d7ce954055db625000218336. Marker geprueft: Logo 3D, kein sichtbares Logo-V6, vier G-Code-Preset-Felder aktiv, altes data-gcode-quick-select entfernt, System-Fallback neutral.


## 2026-10-02 - MakerWorld Detail/Clone und kleine Deploy-Schritte

- Diagnose Tara-PC: PC, Dienst und lokaler Connector-Port sind gesund. JARVISPCConnector laeuft, TCP 192.168.100.10:8767 antwortet lokal unter 1 ms, CPU/RAM sind unkritisch. Das wiederkehrende Problem ist der MCP-Gateway-Timeout bei langen Requests, nicht Router/Firewall/PC-Last.
- Arbeitsregel bestaetigt: Lange V6-Aktionen in kleine Schritte teilen. Quality-Gate darf fertiglaufen, danach Statusdateien lesen und Artefakte gezielt deployen statt den grossen Deploy-Langlaeufer zu verwenden.
- Gate-Nachweis fuer MakerWorld-Aenderung: connector-v6-quality-gate success=true. Frontend-Tests/Build OK, Core-Build OK, Python-Syntax/Imports/Pytest OK.
- MakerWorld Backend: Detail-Normalisierung sammelt jetzt Beschreibungsbilder aus HTML, Markdown und Bild-URLs, laedt mehr Druckprofil-Kandidaten statt beim ersten Profilblock abzubrechen, nutzt mehrere Empfehlungsendpunkte und faellt bei leeren Empfehlungen auf Tag-/Titel-/Trending-Suche zurueck.
- MakerWorld Frontend: Beschreibungs-HTML wird safegelisted statt komplett weg-escaped, Bilder aus der Beschreibung werden angezeigt, die Vorschau-Galerie nimmt diese Bilder auf, und der Druckdateien-Filter ist deutsch als "Alle" sichtbar.
- Live-Deploy klein: Frontend-JS SHA 087f8b713d953407d683c24ed26f6aa1fff04b17deffe6a7d41a1178ef77c3b4 und MakerWorld-Backend SHA cb92f70ed2deccbf31eda6b93e905f47beae9d8c9f3571cc2aa2a4c38b8d4364 nach HA kopiert, mit Backup und SHA-Pruefung.
- Neustart-Hinweis: Python-Custom-Component-Aenderungen werden erst nach Home-Assistant-Neustart aktiv; Frontend-JS ist sofort live, sobald der Browser die neue Ressource laedt.

## 2026-10-02 - MakerWorld Kommentarfix und Puppet

- MakerWorld-Kommentare nachgebessert: Kommentar-Normalisierung sammelt alle Kandidatenlisten statt beim ersten generischen Listenfeld abzubrechen, erkennt weitere Content-Felder und versucht zusaetzliche Kommentar-/Rating-Routen.
- Live-Backend-SHA nach Kommentarfix: 3bc35caa311499cfed926e7460a675652c9cefe72b59e0b57bc376a0f283783e. HA wurde neu gestartet; Detailtests liefern bei drei aktuellen Modellen je 50 Kommentare, 12 Empfehlungen und mehrere Druckprofile.
- Puppet-Test: HA-Screenshot-Tool-Bruecke gibt INVALID_ARGUMENT fuer Dashboardpfade zurueck, aber Puppet selbst funktioniert direkt ueber HA-Port 5000. Direkter Test auf /3d-studio-v6-test/studio lieferte HTTP 200 image/png, 189305 Bytes, PNG 1400x900.

## 2026-10-02 - A1-Duesenprofile und Druckpfad-Status

- Live-Fix: `profile_runtime_v2.py` blendet die kuratierten A1-Duesenvarianten nicht mehr auf nur vier kanonische Eintraege herunter. Sichtbar sind jetzt 7 Profile: 0,2 mm Edelstahl, 0,4/0,6/0,8 mm Edelstahl und 0,4/0,6/0,8 mm gehaerteter Stahl.
- Quelle geprueft: Der Windows-Repo-Stand besitzt diesen restriktiven Filter nicht; ein regulaerer Deploy aus dem Repo wuerde die vollstaendige Auswahl nicht wieder entfernen.
- Nachweis live nach HA-Neustart: Profil-API liefert 7 Nozzle-Eintraege, Auswahl bleibt sicher auf `local.nozzle.a1_0_4_hardened`.
- Slicer-Status read-only: Native Linux-Slicing-Server ist `ready`, keine aktiven oder wartenden Jobs, 100 alte Jobs in der Liste, davon 90 completed und 10 failed.
- Druckerstatus read-only: Bambu A1 ist verbunden; einfacher Printer-Endpunkt meldet `printer_state=failed`, aber der detaillierte Direct-Print-Status meldet `ready=true`. AMS und externe Spule werden erkannt. Kein Druckstart, keine Jobfreigabe und kein Materialbefehl wurden ausgefuehrt.
- Regel: Ein `failed`-Reststatus darf nicht als aktiver Druck interpretiert werden, muss aber vor einem echten Druckstart in UI/Diagnose sichtbar bleiben. Start bleibt weiterhin zweistufig und explizit freigabepflichtig.

## 2026-10-02 - MakerWorld/Puppet Live-Verifikation

- HA-Screenshot-Bruecke liefert weiterhin `INVALID_ARGUMENT` fuer Dashboardpfade. Direkter Puppet-Port-5000-Test auf `/3d-studio-v6-test/studio?viewport=1400x900&wait=7000&dark` ist gruen: HTTP 200 `image/png`, 189305 Bytes, PNG 1400x900, nicht leer.
- MakerWorld Browse ist live erreichbar ueber `/ultimate_3d_studio_v6/v1/makerworld/browse?nav_key=Trending&offset=0&limit=3` und liefert aktuelle Modelle: 3283972 `Spinning Magic Skeleton Wand`, 3260310 `Modular Quick-Release Tripod`, 3347382 `Winter Rentier`.
- Korrekte Detailroute ist `/ultimate_3d_studio_v6/v1/makerworld/design/{design_id}`. Die alte Versuchroute `/makerworld/detail/{id}` ist falsch und liefert leere Detaildaten.
- Live-Detailpruefung: 3283972 liefert 5 Druckdatei-/Profilinstanzen, 50 geladene Kommentare, 12 Empfehlungen, 2 Galerie-Bilder und 1 Beschreibungsbild. 3260310 liefert 7 Profilinstanzen, 50 Kommentare, 12 Empfehlungen, 1 Bild. 3347382 liefert 7 Profilinstanzen, 7 Kommentare und 12 Empfehlungen.
- Kein Druckstart, keine Jobfreigabe und kein Materialbefehl wurden ausgefuehrt.

## 2026-10-02 - Tara-PC-MCP-Stabilisierung

- Ursache der wiederholten Werkzeugabbrueche gefunden: Der MCP-LAN-Server wurde doppelt gestartet. Der geplante Task `JARVIS ChatGPT PC MCP LAN Server` und der Dienst `JARVISPCConnector` starteten denselben MCP `run_jarvis_pc_mcp_lan_v13.py` parallel.
- Beleg: Port `192.168.100.10:8767` war bereits belegt, waehrend weitere Startversuche mit `WinError 10048` scheiterten. Gleichzeitig war `mcp-lan-v13.log` auf ca. 1,1 GB angewachsen.
- Reparatur: Der doppelte Scheduled Task wurde nach XML-Backup deaktiviert. `JARVISPCConnector` bleibt die einzige MCP-Startquelle.
- Logpflege: `mcp-lan-v13.log` und `jarvis-pc-connector-service.log` wurden rotiert. Nach Dienstneustart laeuft nur noch `192.168.100.10:8767` ueber das Service-Child, neues `mcp-lan-v13.log` startete bei 0 Byte.
- Arbeitsregel: Bei zukuenftigen MCP-Abbruechen zuerst pruefen, ob der Scheduled Task deaktiviert ist, ob nur ein Portbesitzer auf `8767` existiert und ob das MCP-Log nicht erneut unkontrolliert waechst. Grosse V6-Tools erst nach kleinem Connector-Healthcheck verwenden.

