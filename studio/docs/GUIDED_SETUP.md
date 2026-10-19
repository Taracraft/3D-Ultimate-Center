# Geführte Studio-Einrichtung

**Quellstand:** Geführte Studio-Einrichtung mit X1C,
mehreren AMS-Einheiten, externer Spule und RTSPS-Kamera. Veröffentlichte Stände
und deren Nachweise stehen in den GitHub-Releases der beiden Projekte.
Die nachfolgend genannten 6.0.5-/alpha10-
Archive und das alpha9-Runtimeimage bleiben die unveränderliche Installerbasis;
geprüfte Quelldateien werden zusätzlich über gebundene Overlays eingebunden.


[X1 Carbon: Einrichtung, AMS, externe Spule und Kamera](X1C_SETUP.md).

Stand: 19. Oktober 2026. Diese Anleitung beschreibt den separat bereitgestellten
TaraCraft-Assistenten mit seinen gebundenen Setup-Ergänzungen. Der unveränderte
HACS-Tag 6.0.5 enthält diese neuen Formulare noch nicht. Die neue Automatisierung
ist isoliert getestet; die vollständige UI- und Netzabnahme auf dem Zielserver
bleibt offen. Ein erfolgreicher einzelner Slice ersetzt keine Gesamtfreigabe.

## SH-Datei auf dem eigenen Server starten

Die bereitgestellte einzelne Datei `3D-Ultimate-Studio.sh` auf den eigenen
Linux/amd64-Server kopieren. In einer lokalen Konsole oder SSH-Sitzung in ihren
Ordner wechseln und starten:

```sh
sudo bash 3D-Ultimate-Studio.sh
```

Die Datei nicht mit `sh` ausführen und nicht lediglich in Home Assistant öffnen.
Für eine Vorschau ohne Installation `bash 3D-Ultimate-Studio.sh --demo`, für
isolierte Tests `bash 3D-Ultimate-Studio.sh --self-test` verwenden. Die eingebetteten
Quellen lassen sich mit `bash 3D-Ultimate-Studio.sh --extract ./TaraCraft-Setup-Quellen`
in einen noch nicht vorhandenen Ordner auspacken; die ausführliche README liegt darin.

Der aktuelle Schritt bleibt oben sichtbar. Das tatsächliche Shell-Protokoll darunter
kann mit Pfeiltasten, Bild auf/ab und Mausrad gescrollt werden. Abbruch beendet nur
eindeutig dem eigenen Installer zugeordnete Prozesse. Beim erneuten Start die passende
Sitzung und Fortsetzen wählen; vorhandene Einstellungen werden wiederverwendet.

## Geführte Einrichtung nach der Installation

**Installationsweg: Home Assistant Container und ein eigener Docker-Compose-Slicer auf deinem vorhandenen Linuxserver. Linux bleibt vollständig selbst administrierbar.**

Der Installer installiert HACS und Studio bereits als Dateien. Für die erste
Einrichtung musst du weder das Repository suchen noch Dashboard-YAML kopieren.
Beim neuen HA verbindet der Installer zusätzlich die vertrauenswürdige Slicer-CA
und hinterlegt HTTPS-Adresse und Secret in einer nur für HA/root lesbaren lokalen
Datei. Das Secret erscheint weder auf der Startseite noch im Shell-Protokoll.

1. Öffne die am Installationsende angezeigte Home-Assistant-Adresse, normalerweise
   `http://SERVER-IP:8123`. Bei einem neuen HA zuerst dein persönliches Benutzerkonto
   anlegen. Bei einem ergänzten bestehenden HA nach den neuen Integrationsdateien
   selbst einen vollständigen HA-Neustart auslösen.
2. Öffne die angezeigte **Einrichtungsseite**. Beim neuen HA ist das
   `/local/3d-studio-setup/index.html` unter derselben HA-Adresse. Dort auf
   **Geführte Einrichtung starten** klicken. Alternativ in HA:
   **Einstellungen → Geräte & Dienste → Integration hinzufügen → Ultimate 3D Studio**.
3. Einen Instanznamen vergeben und **Geführte Einrichtung** eingeschaltet lassen.
   Bereits eingerichtet? Bei **Ultimate 3D Studio → Konfigurieren** stehen getrennte
   Einträge für Drucker, Slicer, Konto und Dashboard zur Verfügung.
4. **Drucker:** einschalten und einen lokal gefundenen Drucker wählen oder IP,
   Seriennummer und LAN-Zugangscode einmal manuell eintragen. Die Seriennummer und
   den LAN-Zugangscode am Drucker unter dessen Netzwerkeinstellungen ablesen.
   **Drucker verwenden** aktivieren. Ein leer gelassener Zugangscode behält einen
   bereits gespeicherten Code bei. **MQTT-Anmeldung vor dem Speichern prüfen** ist
   im Formular standardmäßig aktiv. Absenden prüft und speichert gemeinsam.
5. **Slicer:** beim neuen HA sind Serveradresse und Secret bereits vorbereitet.
   Slicing aktiviert lassen und absenden. Adresse, TLS und Authentifizierung werden
   geprüft und in derselben Aktion gespeichert. Das Passwortfeld bleibt absichtlich
   leer: ein vorhandenes Secret muss nicht erneut eingegeben werden.
   Bei bestehendem/entferntem HA HTTPS-Adresse und Inhalt der eigenen `api-token`-
   Datei einmal eintragen; die öffentliche CA muss dort vertraut werden. Details
   stehen in der START-Datei. Den privaten Serverschlüssel nicht übertragen.
6. **Bambu-Konto:** optional anmelden, gegebenenfalls den Bestätigungscode eingeben,
   oder deaktiviert weitergehen. Das Passwort wird nicht gespeichert. Ein erlaubter
   Cloud-Profilabgleich wird später ausdrücklich unter Profile gestartet.
7. **Dashboard:** **Studio-Dashboard automatisch bereitstellen** eingeschaltet
   lassen und abschließen. Danach erscheint **Ultimate 3D Studio** in der Seitenleiste.
   Direkter Aufruf: `/ultimate-3d-studio/studio`. Die Karte ist bereits in voller
   Breite eingebunden; YAML und manuelles Registrieren einer Ressource entfallen.
   Ein eigenes Dashboard an derselben Adresse bleibt erhalten.
8. Für spätere Updates **HACS** als Integration hinzufügen und dich persönlich
   über GitHub anmelden. Nach der Anmeldung registriert der auf HACS 2.0.5 geprüfte Adapter das Studio-Repository automatisch und übernimmt die bereits geladenen lokalen Integrationsdateien für die Updateverwaltung. **Studio-Repository nach HACS-Anmeldung automatisch hinzufügen** dabei eingeschaltet lassen. Es erfolgt kein erneuter Download und keine automatische Aktualisierung der Programmdateien. Bei einer anderen HACS-Version oder fehlgeschlagener Registrierung den [vorbereiteten Repository-Link](https://my.home-assistant.io/redirect/hacs_repository/?owner=Taracraft&repository=3D-Ultimate-Center&category=integration)
   als Rückfall öffnen und die Integration übernehmen. HACS benötigt deine persönliche GitHub-Geräteanmeldung: den angezeigten Code auf GitHub bestätigen und gegebenenfalls zurück zu HACS wechseln. Diese Anmeldung kann der Installer nicht für dich erteilen. HA-Benutzerkonto und persönliche
   GitHub-Anmeldung bleiben echte Anmeldeschritte.

### MQTT: direkte Druckerverbindung

Studio hat einen eigenen Bambu-LAN-MQTT-Client. Er nutzt die eingegebenen Druckerdaten,
TLS-Port **8883**, Benutzer `bblp` und den LAN-Zugangscode. Es ist kein zusätzlicher
Mosquitto-Container und keine manuelle Einrichtung der allgemeinen HA-MQTT-Integration
nötig. Nach dem Speichern startet der vorhandene Client automatisch und verbindet
sich nach Unterbrechungen erneut.

Der Einrichtungstest meldet getrennt: Netzwerk nicht erreichbar, Zertifikat abgelehnt,
Anmeldung abgelehnt, Statusabonnement abgelehnt oder Zeitlimit. Er sendet ausschließlich
Anmelde- und Abonnementnachrichten, keinen Druckersteuerbefehl. Bestätigte Anmeldung
und SUBACK beweisen noch keine Live-Telemetrie oder korrekte Druckeridentität.
Die tatsächlich empfangenen Druckerdaten und der Verbindungsstatus sind anschließend
im Studio sichtbar.

Home Assistant selbst muss den Drucker erreichen können. Läuft dein Testserver in
einem anderen Netz, bleibt der Drucker bis zur passenden Netzverbindung offline.
Zum bewussten Speichern ohne erreichbaren Drucker **MQTT-Anmeldung vor dem Speichern
prüfen** ausschalten. Slicing und die übrige Einrichtung bleiben unabhängig nutzbar.
Das Akzeptieren eines selbstsignierten **Druckerzertifikats** ist eine eigene bewusste
Druckeroption; die HTTPS-Prüfung des Slicers bleibt davon unberührt.

### Slicing ohne nachträglichen Engine-Download

Das geprüfte Runtimeimage enthält Bambu Studio, PrusaSlicer und CuraEngine bereits
vollständig. Während der Installation prüft der Assistent alle im Image gebundenen
Dateien, Bibliotheken und Prüfsummen, ohne eine Engine auszuführen. Er lädt keine
Engine beim ersten Slice nach. Danach prüft er HTTPS, API-Authentifizierung, alle
drei Enginefamilien und den Worker. Erst bei bestandener Prüfung beendet er seine
eigene Installationswartung automatisch. Bereits ausdrücklich freigegebene Aufträge
können dann anlaufen; der Installer erzeugt keinen Testauftrag und startet keinen Druck.

Der belegte Fehler nach dem ersten Slice war ein abgewiesenes legitimes
`last_job.json`, kein fehlender Engine-Download. Der Installer liefert die eng
gebundene Quellkorrektur als schreibgeschützte zusätzliche Compose-Einbindung aus;
das veröffentlichte Image und die ursprüngliche Compose-Datei bleiben unverändert.
Zum Starten immer den vollständigen Befehl aus der aktuellen START-Datei verwenden,
also ursprüngliche Compose-Datei **und** `compose.setup.yaml`.

Beim Fortsetzen darf nur der exakt erkannte alte Fehler automatisch repariert werden:
eindeutig eigener gestoppter Worker, passender Traceback, beide exklusiven Sperren,
keine laufenden/unterbrochenen Aufträge und ein passendes finales Ergebnis. Die alte
Recovery-Meldung und Ergebnis-Prüfsumme werden dokumentiert, die Auftragsdateien
bleiben erhalten. Andere Recovery-Ursachen werden nicht automatisch gelöscht.

### Vorhandene Installation aktualisieren oder ganz neu beginnen

Die aktuelle `3D-Ultimate-Studio.sh` starten, die zugehörige frühere Sitzung auswählen
und **Fortsetzen** wählen. Identische Originaldateien können gezielt um die geführte
Einrichtung und Runtime-Korrektur ergänzt werden. Eigene Änderungen werden nicht
überschrieben. Beim eigenen neu installierten HA hält der Assistent für diese
Dateiaktualisierung nur seinen eindeutig zugeordneten HA-Container kurz an und
startet ihn im gewählten Dienststart wieder. Ein ergänztes bestehendes HA startet
der Anwender selbst neu.

Für einen frischen Anfang gibt es zwei unterschiedliche Wege im Hauptmenü:

- **Installationsreste entfernen und neu beginnen:** eigene Dienste stoppen,
  Installationsdaten sichern und die Installationspfade freigeben.
- **Ohne Backup vollständig löschen:** zuerst die konkrete Löschvorschau prüfen,
  dann `LOESCHEN` eingeben. Entfernt das vom Setup neu angelegte Home Assistant
  **einschließlich seiner Konfiguration**, Studio/Slicer, Dockerfiles, Compose-
  Dateien, eigene Container, ungeteilte zugeordnete Images/Volumes/Netzwerke,
  Downloads, Sitzungsdaten, Protokolle und erkannte alte Setup-Sicherungen.
  Bei einem nur ergänzten vorhandenen HA bleiben dessen persönliche Konfiguration
  und vorherige Originalintegrationen erhalten. Unabhängige Docker-Projekte,
  gemeinsam verwendete Images und Systempakete bleiben erhalten. Die heruntergeladene
  Installerdatei selbst wird nicht gelöscht.

## Quellen für die Einrichtung

- [Home Assistant Container auf Linux](https://www.home-assistant.io/installation/linux/#install-home-assistant-container)
- [Persönliche HACS-Geräteanmeldung](https://www.hacs.dev/docs/use/configuration/basic/)
- [Geprüfter HACS-Repository-Adapter](https://github.com/hacs/integration/blob/2.0.5/custom_components/hacs/websocket/repositories.py)

### Technische Studio-Namen

Neue Installationen verwenden `/local/3d-studio-setup/index.html`, den
Container `ultimate-3d-studio-homeassistant`, den HA-Standardpfad
`/opt/ultimate-3d-studio/home-assistant` und die private Sitzungsablage
`/var/lib/ultimate-3d-studio-setup`. TaraCraft bleibt das Branding und Copyright.
Bereits zugeordnete alte Sitzungen, Besitznachweise, Sicherungen und Container
bleiben lesbar; ihre gespeicherten Datenpfade werden nicht stillschweigend
umbenannt. Der Assistent zeigt auch dort den neuen Setup-Link an.
