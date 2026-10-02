# AGENTS.md - 3D-Printer Control Center V6

## Verbindliche Regeln

### Sprache
Alle Antworten an den Nutzer sind ausschliesslich auf Deutsch zu verfassen.
- Keine chinesischen Schriftzeichen in Antworten
- Code/Kommentare duermen Englisch sein
- Commit-Nachrichten koennen Englisch sein

### Arbeitsweise
- Vor jeder Aenderung zuerst Ist-Zustand pruefen
- Backups vor Aenderungen erstellen
- Keine Druckerbefehle ohne explizite Freigabe
- Kein Druckstart ohne zweistufige Freigabe

### Projektidentifikation
- V6 = Ultimate 3D Printing Studio (neue Integration ultimate_3d_studio_v6)
- Nicht verwechseln mit dem alten printer_control_center (v5/beta38)

### Bemalung und Mehrfarben-Druck
- Sichtbare Bemalung ist nur dann druckbar, wenn jede Fläche einem tatsächlich belegten AMS-Materialkanal eindeutig zugeordnet ist.
- Die Malwerkzeuge dürfen keine freien RGB-Farben anbieten. Farben folgen ausschließlich dem geladenen Material; eine externe Einzelspule erlaubt keinen Mehrfarben-Druck.
- 3MF-Dreiecksreferenzen müssen vor dem Slicer gegen die aktive Materialliste validiert werden. Unbekannte, fehlende oder mehrdeutige Kanäle sowie Farbverläufe innerhalb eines Dreiecks werden fail-closed abgewiesen.
- Der native Worker muss bemalte Dreiecke vor dem Bambu-Slicer in getrennte Materialteile je Kanal aufteilen. Eine Studio-Farbe darf nie ohne nachgewiesene Worker-Umsetzung als druckbar gelten.
- Die Objektliste behält importierte Modelle unverändert und führt Bemalungen getrennt unter „Malbereich“.

### Qualitäts- und Bereitstellungsvertrag
- Vor jeder Bereitstellung müssen Source-Policy, TypeScript, Frontend-Tests, Produktionsbuild, Python-/Worker-Tests und Compile-Prüfung grün sein.
- Frontend/Home-Assistant-Komponente und nativer Slicer-Worker sind getrennte Deploy-Ziele. Änderungen am Worker erfordern dessen eigenen geprüften Deploymentpfad, Same-Day-Backup, atomaren Austausch, aktuelle Abhängigkeits-Prüfsummen und Live-SHA-Verifikation.
- Ein Connector-Zeitlimit ist kein Prüfergebnis. Maßgeblich sind die erzeugten Statusdateien und die verifizierten Live-SHAs.
- Kein Test-Slice, Job-Release, Upload zum Drucker oder Druckstart ohne ausdrückliche Freigabe. Druckstart bleibt immer vom Slice getrennt.
- Der erste reale Mehrfarben-Nachweis ist ein kleiner, manuell freigegebener Test-Slice: Materialvorschau und Kanäle müssen Studio und AMS exakt entsprechen, bevor ein Druck freigegeben werden kann.

- Photoshop-artiges Malen darf nicht als reine Bildschirm- oder Dreiecksfarbe implementiert werden: Berührte Modellflächen müssen vor dem Auftrag adaptiv in exportierbare Feintriangulationen unterteilt werden. Bestehende Materialzuweisungen sind dabei verlustfrei auf die Unterdreiecke zu übertragen; erst danach wird die Werkzeugform bewertet.
- Kreis und Rechteck brauchen beim Ziehen einen glatten Aufziehrahmen über der Arbeitsfläche. Der Rahmen ist nur Interaktion; die resultierenden Materialflächen müssen aus der verfeinerten Modellgeometrie stammen.

## 2026-09-30 Supportwarnung Filamentprofile Puppet

- Im V6 Studio bleibt die Materialquelle explizit auswählbar: AMS/AMS Lite und Externe Spule dürfen nicht zu einem versteckten Automatismus verschmelzen.
- Die UI zeigt nur noch ein fachliches Menü "Filamentprofile". Dieses Menü umfasst lokale, Standard- und bereits synchronisierte Cloud-Profile; Cloud-Synchronisation bleibt ein manueller Vorgang im Bereich Profile.
- Die Profilwahl muss je Materialquelle dispatchen: AMS nutzt Slot-/AMS-Profilzuordnung, Externe Spule nutzt genau ein externes Filamentprofil.
- Supportwarnungen müssen als native Modal-Dialoge im Top-Layer laufen, alle betroffenen Objektnamen zeigen, XSS-sicher escapen und dürfen keinen Slice/Upload/Printjob starten, bevor der Benutzer entschieden hat.
- Lokaler UI-Test für dieses Projekt: Puppet läuft auf dem Home-Assistant-Host über Port 5000 (Container intern 10000). Nicht Opera und nicht Puppeteer installieren/verwenden.
- Puppet braucht Split-DNS: homeassist.bad-timing.eu muss im Container auf das IPv4-Gateway des Docker-Netzes hassio zeigen (aktuell 172.30.32.1). home_assistant_url=https://homeassist.bad-timing.eu:8123 muss ohne abschließenden Slash gespeichert sein; sonst entsteht //api/websocket. Die Zuordnung wird seit 2026-10-02 durch v6-puppet-hosts.timer nach Container-Neuanlage automatisch wiederhergestellt; Details unter deploy/homeassistant/host/puppet/README.md.
- Ein erfolgreicher Puppet-Test ist erst gültig, wenn Status 200, Content-Type image/png und PNG-Signatur geprüft sind; HTTP 200 auf einer HTML-/Fehlerseite reicht nicht.

## 2026-09-30 Malwerkzeug Live-Regeln

- Pinsel und Stift muessen kontinuierlich entlang der Zeigerbewegung stempeln; schnelle Mausbewegungen duerfen keine gestrichelten Einzelpunkte erzeugen.
- Die adaptive Malauflösung im Studio ist aktuell feiner als der alte 0,7-mm-Vertrag und wird mit 0,35 mm Zielkante fuer beruehrte Dreiecke abgesichert.
- Malbereiche sind eigene Listeneintraege unter "Malbereich". Sie muessen per Klick, Strg/Klick, Shift/Klick, Strg+A und Entf verwaltbar bleiben, ohne importierte Modellobjekte umzubenennen oder zu vermischen.
- Live-Abnahme per Puppet ist nur gueltig, wenn das Add-on wirklich mit Home Assistant verbunden ist. Eine HTML-Seite "Connection Failed" wegen Access-Token/HA-URL ist ein Blocker und kein visueller UI-Test.


## Laufende Synchronisierung (Benutzerregel 2026-10-02)

- Jede Projektänderung muss in F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Ultimate Studio, der HA-Quellkopie und Taracraft/3D-Ultimate-Center im öffentlichen GitHub nachgezogen und per Hash geprüft werden.
- Produktive HA-Ziele werden erst nach grünem Gesamtgate mit Backup und Live-SHA-Prüfung aktualisiert. Kein abgeschlossener Schritt ohne bestätigten lokalen und öffentlichen Stand.
