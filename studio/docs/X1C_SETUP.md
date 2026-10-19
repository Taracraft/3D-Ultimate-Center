# X1 Carbon: Einrichtung, Materialien und Kamera

Diese Anleitung ergänzt die [geführte Installation](GUIDED_SETUP.md). Der
Installationsweg besteht aus Home Assistant Container und dem eigenständigen
Docker-Compose-Slicer auf einem selbst administrierten Linuxserver. Die Datei
heißt **3D-Ultimate-Studio.sh**; TaraCraft bleibt das Branding des Assistenten.

## 1. Installation und persönliche Anmeldung

1. Die bereitgestellte SH-Datei auf den Linux/amd64-Server kopieren und mit
   `sudo bash 3D-Ultimate-Studio.sh` ausführen. Im Dialog den gewünschten
   Installationsweg und die konkret vorgeschlagenen Pfade prüfen.
2. Der aktuelle Schritt bleibt oben sichtbar. Darunter läuft das tatsächliche
   Shell-Protokoll; Pfeiltasten, Bild auf/ab und Mausrad erlauben das Nachlesen.
   Das Runtimeimage enthält die drei Engines bereits. Ihre Dateien und
   Bibliotheken werden während der Installation geprüft. Der erste Slice
   benötigt keinen nachträglichen Engine-Download.
3. Bei einem neuen Home Assistant die angezeigte Adresse öffnen und das eigene
   HA-Benutzerkonto anlegen. Bei einem bestehenden HA nach Installation der
   Integrationsdateien Home Assistant vollständig neu starten.
4. HACS ist als Integrationsdatei installiert. Unter **Einstellungen → Geräte &
   Dienste → Integration hinzufügen → HACS** persönlich anmelden. Den angezeigten
   GitHub-Gerätecode auf GitHub bestätigen und den HACS-Dialog abschließen.
   Der Installer kann diese persönliche Autorisierung nicht erteilen.
5. Die Einrichtungsseite aus der START-Datei öffnen und Ultimate 3D Studio
   hinzufügen. Die automatische HACS-Repository-Registrierung eingeschaltet
   lassen. Sie ist an HACS 2.0.5 gebunden; bei einer abweichenden Version den
   vorbereiteten Repository-Link auf der Einrichtungsseite verwenden.

## 2. X1C einmal konfigurieren

Im geführten Studio-Dialog **Drucker verwenden** aktivieren und die Drucker-IP,
Seriennummer sowie den LAN-Zugangscode eintragen. Für die Erkennung werden Modell
und Seriennummer gemeinsam geprüft. Ein widersprüchliches Modell wird nicht
still durch ein A1-Profil ersetzt. Beim erneuten Konfigurieren behält ein leeres
Zugangscodefeld den bereits gespeicherten Wert.

**MQTT-Anmeldung vor dem Speichern prüfen** prüft nur Verbindung, Anmeldung und
Abonnement. Es startet keinen Druck. Ist der X1C beispielsweise erst im Firmennetz
erreichbar, diese Prüfung zum bewussten Offline-Speichern ausschalten. Erst ein
Netzweg von Home Assistant zum Drucker ermöglicht später Live-Daten und Kamera.
Eine erfolgreiche Slicer-Verbindung ist davon unabhängig.

Je nach Firmware schützt Bambu lokale Steuerbefehle durch Authorization Control.
Für den direkten Drittanbieterzugriff den am Drucker verfügbaren LAN-/
Entwicklermodus anhand der [offiziellen Bambu-Anleitung](https://wiki.bambulab.com/de/knowledge-sharing/enable-developer-mode)
prüfen und bewusst einstellen. Der Entwicklermodus öffnet die vorgesehenen
lokalen MQTT-, Video- und FTP-Schnittstellen. Eine erfolgreiche Statusanmeldung
beweist noch keine Berechtigung für Steuerbefehle. Der Installer verändert
weder Druckerfirmware noch diesen Modus. Ein Firmen-Drucker benötigt dafür die
vor Ort festgelegte Betriebsfreigabe.

Studio verbindet sich selbst direkt per TLS-MQTT zum Drucker auf **TCP 8883**,
mit Benutzer `bblp` und LAN-Zugangscode. Ein zusätzlicher MQTT-Broker oder die
allgemeine HA-MQTT-Integration ist dafür nicht erforderlich. Ein abgelehntes
selbstsigniertes Druckerzertifikat über die dafür vorgesehene Druckeroption
behandeln; dadurch wird die HTTPS-Prüfung des Slicers nicht deaktiviert.

Im Slicer-Schritt sind bei einem neu eingerichteten HA die HTTPS-Adresse,
API-Anmeldung und CA bereits vorbereitet. Bei einem bestehenden HA die Adresse,
das API-Secret und das erforderliche CA-Vertrauen gemäß START-Datei einrichten.
Ein vorhandenes Secret muss nicht erneut eingegeben werden. Nicht in URLs,
Screenshots oder öffentliche Fehlerberichte übernehmen.

## 3. Dashboard automatisch hinzufügen

Im letzten Dialog **Studio-Dashboard automatisch bereitstellen** eingeschaltet
lassen. Danach in der Seitenleiste **Ultimate 3D Studio** öffnen. Die Adresse ist
`/ultimate-3d-studio/studio`; die Karte ist bereits über die ganze Ansichtsbreite
eingebunden. Dafür sind weder Dashboard-YAML noch eine manuelle Modulressource
nötig. Ein fremdes Dashboard an derselben Adresse wird nicht überschrieben.

Ist Studio schon eingerichtet: **Einstellungen → Geräte & Dienste → Ultimate
3D Studio → Konfigurieren → Dashboard** verwenden. Bei einem alten manuellen
Dashboard den ausführlichen Rückfallweg in der Installationsanleitung verwenden.
Ein leeres Dashboard, ein offline gemeldeter Drucker und ein offline gemeldeter
Slicer sind drei getrennte Zustände.

## 4. Richtige X1C-Profile auswählen

Unter Profile beziehungsweise Druckvorbereitung **X1 Carbon**, die tatsächlich
montierte Düse, die eingesetzte Druckplatte und ein dazu passendes Filament
wählen. Die Quellen enthalten 0,2/0,4/0,6/0,8-mm-Düsen, jeweils eigenen
Maschinen-Startcode und ein passendes Standard-Prozessprofil. Herstellerprofile
für 0,2 mm gehen von Edelstahl aus; die übrigen X1C-Düsenprofile von gehärtetem
Stahl. Eine abweichend montierte Hardware bewusst passend konfigurieren.

183 modellgebundene Hersteller-Filamentprofile werden mit ihren vollständigen
Abhängigkeiten geliefert. Nicht jedes Material passt zu jeder Düse oder zu einem
AMS. Die Auswahl enthält unter anderem Texturierte PEI, Glatte PEI, Cool Plate,
Engineering Plate und Cool Plate SuperTack. Die tatsächlich eingesetzte Platte
wählen; deren Materialtemperaturen werden nicht aus einem A1-Profil übernommen.

Der X1C-Vertrag verwendet einen Extruder und 256 × 256 × 256 mm Bauraum. Die
konservativen gemeinsamen Grenzen sind 300 °C Düse und 110 °C Bett. Eine aktive
Kammerheizung wird nicht behauptet. Bettvermessung, LiDAR-Kalibrierung und
Hersteller-Soundabschnitte werden anhand der X1C-Quellen geprüft. Drucker-,
Düsen-, Prozess- und Filamentverträge müssen vor der Ausführung zusammenpassen.
Die im jeweiligen Auftrag gespeicherten Farben bleiben dessen Farbquelle.

## 5. AMS Gen1, AMS 2 Pro und externe Spule

Unter **Materialsysteme** die konfigurierten Angaben von tatsächlich empfangener
Telemetrie unterscheiden. Vier Fächer allein beweisen keine AMS-Generation.
Studio verwendet die gemeldeten Typdaten. Unbekannte Generationen bleiben
unbekannt; fehlende Hardwareadressen werden nicht als gültige Slots erfunden.

Bei mehreren AMS werden Einheit und lokales Fach getrennt gespeichert. Beispielsweise
sind Einheit 0/Fach 0 und Einheit 1/Fach 0 zwei unterschiedliche Materialkanäle.
Der X1C erlaubt im geprüften Vertrag bis zu 16 AMS-Kanäle. Diese Kapazität behauptet
keine tatsächlich vorhandenen oder belegten Fächer. Temperatur, Feuchte und
Trocknungsrestzeit erscheinen nur, soweit entsprechende Telemetrie vorliegt.
Feuchtestufe und Prozentwert werden getrennt behandelt. Daraus folgt keine
implementierte Fernsteuerung des Trockners.

Für ein nicht schreibgeschütztes belegtes Fach **Filament einstellen** öffnen,
modellgebundenes Material und Farbe auswählen, Vorschau prüfen und ausdrücklich
bestätigen. RFID-geschützte Angaben werden nicht überschrieben. Zwischen Vorschau
und Bestätigung geänderte Drucker-/Materialdaten machen die Vorschau ungültig.

Für die externe Spule **Externe Spule** wählen und dieselbe Material-/Farbvorschau
verwenden. Sie benötigt kein zusätzliches HA-Sensorpaket. Bei bekannter,
verbundener und untätiger Druckeridentität ist die Einrichtung auch möglich,
wenn die externe Spule noch keine Materialmetadaten meldet. Der interne
Firmwarekanal 254 ist kein reguläres AMS-Fach. Eine externe Einzelspule erzeugt
keinen Mehrfarbenkanal.

Gewöhnliches TPU/TPE und viele abrasive Materialien bleiben für den manuellen
AMS-Weg gesperrt. Speziell freigegebenes TPU for AMS und ausgewählte
Herstellermaterialien haben eigene Zuordnungen. PVA/BVOH nur trocken und gemäß
der Anleitung des tatsächlich eingesetzten AMS verwenden. Im Zweifel externe
Spule wählen und Herstellerfreigabe sowie Düse kontrollieren.

## 6. X1C-Kamera

Der X1C verwendet **RTSPS über TCP 322**, nicht den JPEG-Kameraport des A1.
Home Assistant decodiert das Video über seine Stream-/PyAV-Abhängigkeiten.
Zugangsdaten verbleiben serverseitig; Decoderfehler werden ohne vollständige
Quell-URL und ohne Zugangscode angezeigt. Kameraentität beziehungsweise deren
Live-Ansicht in HA öffnen; Studio erhält daraus auch Vorschaubilder.

Prüfen: Drucker eingeschaltet, Kamera-/LAN-Zugriff erlaubt, richtige IP und
richtiger Zugangscode, Port 322 vom HA-Container erreichbar, keine Netztrennung
oder blockierende Firewall. Ein erreichbarer MQTT-Port beweist keinen
Kamerazugriff. Die tatsächliche X1C-Kamera ist noch am Gerät zu prüfen.

## 7. Fortsetzen, Bereinigen und Diagnose

Nach einem Abbruch dieselbe SH-Datei erneut starten und die eigene Sitzung
fortsetzen. Bekannte eigene Setup-Dateien werden nur bei passenden Prüfsummen
aktualisiert. Persönlich veränderte Dateien werden nicht automatisch ersetzt.
Nur eindeutig eigene Installer-Prozesse dürfen beendet werden.

Für einen Neustart **Installationsreste entfernen und neu beginnen** wählen.
**Ohne Backup vollständig löschen** zeigt zuerst den konkreten Löschumfang und
verlangt `LOESCHEN`. Ein vom Setup neu angelegtes HA verliert dabei auch seine
Konfiguration. Der Assistent entfernt zugeordnete Studio-/Slicer-Container,
Dockerfiles, Compose-Dateien und eigene Daten gemäß Vorschau; unabhängig genutzte
Docker-Projekte und gemeinsam verwendete Images bleiben erhalten.

Wenn Slicing hängt: zuerst Wartungsstatus, Worker-Gesundheit, Recovery-Status und
das konkrete Auftragsergebnis vergleichen. Eine Ergebnisdatei mit `completed`
bedeutet nicht automatisch, dass ein abgestürzter Worker wieder arbeitet.
Die Installation kann den eng erkannten alten eigenen Recovery-Fehler korrigieren;
unbekannte Recovery-Ursachen bleiben zur Diagnose erhalten. Beim Compose-Aufruf
immer beide Dateien aus der START-Datei verwenden, einschließlich
`compose.setup.yaml`, damit die geprüften Worker-Abhängigkeiten eingebunden sind.

## 8. Logo und Nachweisgrenzen

Die Integration liefert das eigene TaraCraft-Studio-Icon in `brand/icon.png` und
`brand/icon@2x.png`. Der SVG-Master liegt unter `docs/branding/studio-mark.svg`.
Die lokale HA-Markenanzeige benötigt eine HA-Version mit Unterstützung lokaler
Integrationsmarken; der Installer bindet Home Assistant 2026.10.2.

Die HACS-Listenansicht verwendet in der geprüften HACS-Version den globalen
Home-Assistant-Markenbestand. Die lokalen Icons allein garantieren dort kein
Logo. Eine entsprechende globale Markenveröffentlichung ist separat offen;
sie wird nicht als bereits erledigt dargestellt.

Quellen- und Regressionstests ersetzen keine echte Geräteprüfung. Offen bleiben
am erreichbaren X1C: MQTT-Telemetrie, tatsächliche AMS-Generation und Fächer,
externe Spule, Kamera sowie ausdrücklich separat freizugebende Slice-/Drucktests.

Herstellerreferenzen: [Entwicklermodus](https://wiki.bambulab.com/de/knowledge-sharing/enable-developer-mode),
[Netzwerkports](https://wiki.bambulab.com/en/general/printer-network-ports),
[Integrationsmarken in HA](https://contributors.home-assistant.io/core/integrations/brands/),
[HACS und lokale Icons](https://github.com/hacs/integration/issues/5171).
