# Ultimate Slicer Server einrichten und prüfen

**Quellstand:** Geführte Studio-Einrichtung mit X1C,
mehreren AMS-Einheiten, externer Spule und RTSPS-Kamera. Veröffentlichte Stände
und deren Nachweise stehen in den GitHub-Releases der beiden Projekte.
Die nachfolgend genannten 6.0.5-/alpha10-
Archive und das alpha9-Runtimeimage bleiben die unveränderliche Installerbasis;
geprüfte Quelldateien werden zusätzlich über gebundene Overlays eingebunden.


[X1 Carbon: Einrichtung, AMS, externe Spule und Kamera](../docs/X1C_SETUP.md).

### Studio lässt sich nicht hinzufügen: „Invalid handler specified“

Diese Meldung fasst einen fehlgeschlagenen Import des Einrichtungsdialogs zusammen.
Die konkrete Ursache steht in **Einstellungen → System → Protokolle**. Beim
HA-Container alternativ `sudo docker logs --tail 150 ultimate-3d-studio-homeassistant`.
Eine GitHub-Anmeldung von HACS behebt keinen Python-Ladefehler.

**Behoben in Studio 6.0.8:** Der Fehler `Incomplete manufacturer profiles` mit
`local.filament.x1c_...: invalid native H2S basis` kam von einer falschen
Modellzuordnung bei der Katalogprüfung. X1C und H2S werden jetzt jeweils gegen
ihre eigene native Profilautorität und Hardwaregrenzen geprüft. Alle 183
X1C-Filamente bleiben enthalten. Kammerempfehlungen aus Herstellervorlagen
bleiben als Referenz erhalten; die erzeugten X1C-Profile fordern keinen aktiven
Kammerheizer an. Materialbereiche über 300 °C werden im abgeleiteten X1C-Profil
auf die X1C-Grenze begrenzt. Die gepinnten Herstellerdaten bleiben unverändert.
Ungültige spätere Temperatur-, Material-, AMS- oder Modelländerungen werden
weiterhin abgewiesen.

Mit dem aktuellen `3D-Ultimate-Studio.sh` im Hauptmenü **Frühere Sitzung fortsetzen**
und die passende **BESTAND**-Sitzung mit denselben Einstellungen wählen. Der
Assistent aktualisiert die bekannten eigenen Integrationsdateien und startet
sein eigenes HA nach Bedarf wieder. Persönliche Einstellungen bleiben erhalten;
Löschen oder Zurücksetzen ist für diesen Fehler nicht erforderlich. Bei der
normalen HACS-Installation Studio aktualisieren und HA vollständig neu starten.
Danach den Einrichtungsdialog erneut öffnen. Der echte Wiederholungstest bleibt
bis zur erneuten Ausführung auf dem eigenen System offen.

## Installation mit dem TaraCraft-Assistenten

**Home Assistant und Slicer laufen als getrennte Docker-Container auf deinem vorhandenen Linuxserver.**
Du administrierst Linux, Docker, Netzwerk und weitere Dienste weiterhin selbst.
Der Assistent installiert und verbindet HACS, Studio und den Slicer.

Wenn dir die aktuelle einzelne Datei `3D-Ultimate-Studio.sh` bereitgestellt wurde,
kopiere sie auf den Linux/amd64-Server und starte sie dort im Terminal:

```sh
sudo bash 3D-Ultimate-Studio.sh
```

Mit `bash 3D-Ultimate-Studio.sh --demo` lässt sich die Oberfläche vorher ansehen;
`bash 3D-Ultimate-Studio.sh --self-test` führt isolierte Prüfungen aus. Der Assistent
zeigt den aktuellen Schritt oben und das echte, scrollbar bleibende Shell-Protokoll
darunter. Bei einer vorhandenen zugehörigen Sitzung **Fortsetzen** wählen.

Die [ausführliche Anleitung für Container, HACS, MQTT, Slicer und Dashboard](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/Slicer-Server/INSTALLATION.md)
beschreibt die direkte Studio-Einrichtung ohne GitHub-Anmeldung, optionales HACS,
automatische Repository-Übernahme und das vollständige Zurücksetzen. Die
Automatisierungen gelten für den aktuellen separat bereitgestellten Assistenten
mit seinen gebundenen Setup-Ergänzungen. Sie sind keine Behauptung, dass der
unveränderte HACS-Tag 6.0.5 diese neuen Formulare bereits enthält.

Für eine Installation ohne diesen Assistenten bleibt der weiter unten beschriebene normale HACS-/Docker-Weg gültig.

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


## Manueller Docker- und Paketweg


Diese Anleitung führt vom passenden Einrichtungsweg zu den dokumentierten Vorprüfungen. Sie richtet sich an Administratoren, die einen vorhandenen Slicer mit Home Assistant verbinden oder den veröffentlichten Quellstand für eine spätere Bereitstellung prüfen möchten. Für den laufenden Betrieb ergänzen [Handbuch](HANDBUCH.md), [Laufzeitkonfiguration](RUNTIME_INSTALLATION.md) und [Betrieb, Updates und Wiederherstellung](OPERATIONS.md) diese Seite.

## 1. Lieferstatus vor Beginn verstehen

**Docker-Lieferung vom 18.10.2026:** Das vorhandene Linux/amd64-Runtime-Image mit Bambu Studio, PrusaSlicer und CuraEngine ist unter [v0.1.0-alpha10](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/tag/v0.1.0-alpha10) veröffentlicht. [Installation und genaue Versionszuordnung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/RUNTIME_RELEASE_README.md), [Prüfsummen](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/SHA256SUMS) und zugehörige Quellen/Lizenznachweise gehören zur Lieferung. Das dokumentierte Expat-Restrisiko ist für diesen Kandidaten akzeptiert, technisch aber nicht behoben; siehe [Risikodokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/v0.1.0-alpha10/EXPAT_RISK_ACCEPTANCE.json).

Studio wird unabhängig als HACS-Integration 6.0.5 ausgeliefert. Die Slicer-Quellen tragen alpha10; das unveränderte Runtime-Image enthält API-Metadaten alpha9. Image-ID: `sha256:cb37fa6b9aee8c40035a5f337a67d9fc13c4429e06098024731e556f8e8bfb49`. Es wurde dafür kein identischer Neubau vorgenommen. Externe Installations-, UI- und Pilotprüfungen bleiben `not_run` und sind keine zusätzlichen Releasegates. Eine Gesamtfertigstellung wird daraus nicht abgeleitet.

Für die ausgelieferte Docker-Runtime gilt die verlinkte Anleitung mit dem vorhandenen Image und dessen eigener Compose-Datei. Die folgenden Abschnitte dokumentieren zusätzlich den Quell-Preflight und den getrennten nativen Paketweg. Deren leere Auswahlkataloge und gesperrte Installationsaktionen gelten nicht als fehlende Engineausstattung des Runtime-Images. Für den nativen Installationsweg gilt weiterhin `native_deploy_ready=false`.


## 2. Einrichtungsweg auswählen

| Ausgangslage | Passender Weg | Aktuelle Grenze |
| --- | --- | --- |
| Eigenständiger Slicer läuft bereits auf einem anderen Host | Externe HTTPS-Verbindung | TLS, Authentifizierung und API-Kompatibilität müssen passen |
| Ein Unix-Host wurde bereits ausdrücklich für den Installer provisioniert | Geschützte Hostkopplung | Reale Hosteinrichtung und Abnahmen stehen noch aus |
| Quellcode soll ohne laufenden Dienst geprüft werden | Quell-Preflight | Kein API-Start, keine Engine und kein Slice |

Home Assistant Container und der Docker-Compose-Slicer werden getrennt verwaltet und über HTTPS verbunden. HACS verwaltet die Home-Assistant-Integration. Die zusätzlichen Entwicklerprüfungen installieren keinen Hostdienst.

## 3. Einen vorhandenen externen HTTPS-Slicer verbinden

Benötigt werden die überprüfte HTTPS-Adresse des Servers, dessen API-Secret und ein für Home Assistant vertrauenswürdiges Zertifikat. Das Zertifikat muss zum verwendeten Hostnamen passen. Der Server muss von Home Assistant aus erreichbar sein; passende Bind-Adresse und Firewallregeln gehören zur Einrichtung des Serverhosts.

Öffne in Home Assistant **Einstellungen → Geräte & Dienste → Ultimate 3D Studio → Konfigurieren**. Hinterlege die Serveradresse und das API-Secret in den vorhandenen Verbindungsoptionen. Zugangsdaten verbleiben in Home Assistant. Übernimm die Verbindung erst, wenn Zertifikatsprüfung, Authentifizierung und API-Kompatibilität erfolgreich geprüft wurden.

Der dokumentierte Verbindungstest fragt die geschützte Info-API ab. Er installiert keine Software und führt weder einen Slice noch einen Upload oder Druckstart aus. Ein Server kann erreichbar sein, obwohl ihm eine arbeitsfähige Engine fehlt: `GET /api/v1/health` ist öffentlich und kann ohne Engine `degraded` melden; `GET /api/v1/info` benötigt `Authorization: Bearer <Secret>`. Ein HTTP-Erfolg allein bestätigt keine vollständige Slicing-Funktion.

Für einen entfernten Host wird die Zertifikatsprüfung beibehalten. Beim nativen Dienst ist eine Bind-Adresse außerhalb von Loopback ohne vollständige gültige TLS-Konfiguration gesperrt. Alternativ ist laut nativer Dokumentation eine TLS-Terminierung durch einen Reverse-Proxy möglich, während der Slicer an `127.0.0.1` gebunden bleibt. Die konkrete Cross-Host-TLS-Abnahme bleibt ein offener Nachweis.

## 4. Bereits provisionierten Unix-Host koppeln

Dieser Weg setzt eine ausdrücklich vorbereitete Hostumgebung voraus. Die lokale Tokenregistrierung stellt keine automatische Host-Erkennung, HTTP-Route oder allgemeine Shell bereit. Sie gehört in eine geschützte Installer-Steuerablage außerhalb der Engine-, Profil- und Datenmounts; Worker und Browser erhalten darauf keinen Zugriff.

Die Implementierung beschreibt eine gebundene lokale Installations-ID, Principals mit festgelegten Rechten und geschützte Tokenübergabe. Eine lokale ID allein bestätigt jedoch nicht die Identität eines entfernten TLS-Hosts. Produktive Provisionierung, Rechte, gesicherter Transport und Wiederherstellung benötigen ihre eigenen Nachweise. Deshalb enthält diese Anleitung keinen vereinfachten Kopplungs- oder Installationsbefehl. Der maßgebliche Vertrag steht in [Hostkopplung](HOST_PAIRING.md) und [Installer-Transport](INSTALLER_TRANSPORT.md).

## 5. Quell-Preflight ohne Dienstinstallation

Für die Dateiprüfung werden ein vollständiger Quellbaum und Python 3.11 oder neuer benötigt. Das Ausgabeziel muss neu sein und außerhalb des Repositorys liegen. Sein Elternverzeichnis muss existieren; verlinkte Pfadketten sind unzulässig. Weder eine vorhandene Slicer-Installation noch Docker werden für diese erste Dateiprüfung benötigt.

Die folgenden Originalbefehle gelten ab der Repositorywurzel, im Studio-Gesamtrepository ab `studio/`:

```sh
python Slicer-Server/prepare_context.py --output /tmp/ultimate-slicer-context
python /tmp/ultimate-slicer-context/container_check.py check
```

Auf Windows kann stattdessen ein neuer Ordner in einem privaten temporären Verzeichnis als Ausgabeziel verwendet werden. Standortpfade werden dafür nicht in den Programmcode eingetragen. Erwartet werden folgende Ergebnisse:

| Feld | Erwarteter Wert | Bedeutung |
| --- | --- | --- |
| `source_integrity` | `verified` | Quellen passen zum Prüfvertrag |
| `container_deploy_ready` | `false` | Keine Container-Betriebsfreigabe |
| `engine_included` | `false` | Keine Engine enthalten |
| `installation_performed` | `false` | Keine Installation erfolgt |
| `worker_started` | `false` | Kein Worker gestartet |

Ein abweichendes Ergebnis wird untersucht. Prüfsummen werden nicht lediglich an veränderte Dateien angepasst. Für einen weiteren Kontext ist ein neues Ziel zu verwenden; vorhandene Ziele werden nicht automatisch geleert. Konfigurationen, Secrets und Nutzermodelle gehören außerhalb des Build-Kontexts.

## 6. Optionales Prüfimage bauen

Dieser Entwicklerweg benötigt Docker Engine und Docker Compose auf einem separaten vorgesehenen Testrechner. Ein Build kann das gewählte Basisimage herunterladen. Als `PYTHON_BASE` ist eine überprüfte offizielle Python-Linux-Referenz mit SHA-256-Digest erforderlich. Der vorhandene Quelltext nennt dafür das Format `python:<freigegebener-tag>@sha256:<64-hex-zeichen>`; dies ist ein Platzhalter und kein verwendbarer Downloadnachweis.

Mit einem tatsächlich geprüften Wert lauten die dokumentierten Originalbefehle:

```sh
docker build --build-arg PYTHON_BASE="$PYTHON_BASE" \
  --tag ultimate-slicer-server-check /tmp/ultimate-slicer-context
```

Anschließend ab der Repositorywurzel:

```sh
SLICER_CHECK_IMAGE=ultimate-slicer-server-check \
  docker compose -f Slicer-Server/compose.preview.yaml run --rm preflight
```

Die Preview-Konfiguration besitzt keine veröffentlichten Ports und keine Daten- oder Engine-Mounts. Sie arbeitet mit unprivilegiertem Benutzer, schreibgeschütztem Dateisystem und ohne zusätzliche Capabilities. `pull_policy=never` verlangt das zuvor lokal gebaute Prüfimage. Der erfolgreiche Lauf prüft dessen eingebautes Quellpaket. Fehlende Engines, Bibliotheken, Profile, Lizenznachweise und Betriebsabnahmen werden dadurch nicht ersetzt. Die Preview-Datei wird nicht durch zusätzliche Rechte zu einer freigegebenen Installation.

## 7. Älteren Containerkandidaten für die Quellentwicklung vorbereiten

Dieser Abschnitt gilt für den Kandidaten mit externen Engine-Binds. Für das veröffentlichte Image mit eingebauten Engines gilt ausschließlich die oben verlinkte Runtime-Anleitung.

Die bestehende [Laufzeitdokumentation](RUNTIME_INSTALLATION.md) beschreibt einen Kandidaten mit API, Worker und Telemetrie. Der Worker läuft im dokumentierten Containerpfad ohne Netzwerkzugriff; Programmcode und Engine werden nur lesbar eingebunden. Beide Dienste laufen ohne Root, zusätzliche Capabilities und Docker-Socket. Der gemeinsame PID-Namensraum und dieselbe UID sind dennoch keine vollständige Sicherheitsgrenze zwischen gleichberechtigten Prozessen.

Für einen späteren isolierten Lauf werden getrennte Pfade benötigt: `data/` für neue persistente Daten, `engine/` für den vollständigen Enginebestand, `tls/` für Zertifikat und Schlüssel sowie eine eigene Datei `api-token`. Die dokumentierte UID/GID lautet `65532:65532`. Der Token benötigt mindestens 32 zufällige druckbare ASCII-Zeichen und eingeschränkte Dateirechte. Der Engine-Hostpfad ist die gemeinsame Wurzel der drei Familienverzeichnisse, kein direktes Bambu-Entpackverzeichnis.

Ein leerer Enginepfad kann einen Leerlauftest ermöglichen, aber keinen Slice. Fehlende Bind-Mounts werden nicht automatisch angelegt. Eine Standardbindung an Loopback macht den Dienst ausschließlich auf dem Docker-Host erreichbar. Der konkrete Startablauf bleibt in der Laufzeitdokumentation; vor einer freigegebenen Bereitstellung fehlen insbesondere Engine-, Lizenz-, HA-Verbindungs-, Neuinstallations- und Restore-Nachweise.

## 8. Native Pakete nur innerhalb ihres Prüfvertrags

Die nativen Werkzeuge liegen in [`packages/ultimate-slicer-server/`](../packages/ultimate-slicer-server/README.md). Der Installer prüft notwendige Programme, feste Systempfade und die Voraussetzungen seiner Isolation. Er installiert keine Betriebssystempakete automatisch. Aus dem Verzeichnis mit `install_native.py` lautet die dokumentierte rein lesende Hostprüfung:

```sh
python3 install_native.py --check-host
```

Ein erfolgreicher Lauf meldet `host_dependencies: ready` und `installation_performed: false`. Das bestätigt vorhandene Hostabhängigkeiten, keine vollständige Betriebsfähigkeit. Die Installation benötigt zusätzlich einen extern bestätigten Archivhash, rechtmäßig nutzbare Engine-Dateien, deren unabhängiges Manifest sowie vollständige Maschinen-, Prozess- und Filamentprofile. `native_deploy_ready=false` sperrt die Installations- und Upgradeaktionen weiterhin. Eine bestehende Installation wird nicht als Erstinstallationsziel überschrieben.

## 9. Fehler einordnen und späteren Betrieb absichern

| Zustand | Bedeutung und nächster Schritt |
| --- | --- |
| `source_digest_mismatch` | Quellbytes und Manifest passen nicht; Ursache und maßgeblichen Quellstand prüfen |
| `output_already_exists` | Neues Ausgabeziel verwenden oder den eigenen alten Kontext bewusst entfernen |
| `unexpected_context_file` | Unerlaubte Zusatzdatei im Kontext untersuchen; Secrets gehören nicht hinein |
| Health `degraded` | Erreichbarkeit kann vorhanden sein, Enginefähigkeit fehlt oder ist eingeschränkt |
| Recovery-Marker oder `*.slicing.json` | Weitere Jobs gesperrt; Dienste stoppen, Daten sichern und alten Prozess-/Jobzustand untersuchen |

Vor einem späteren Update werden aktive und wartende Jobs erfasst und persistente Daten konsistent gesichert. Zum Rückweg gehören der passende Softwarestand und die dazugehörigen Daten. API-Token, TLS-Schlüssel und Sicherungen bleiben geschützt. Ein Fehlerbericht enthält üblicherweise Version, Architektur, Image-Digest, API-Protokoll, Fehlercode und bereinigte Logauszüge. Das Entfernen eines Containers löscht persönliche Profile, Modelle und Historie nicht automatisch.

Der erste echte Slice setzt die vollständige geprüfte Runtime voraus. Seine Abnahme umfasst Engine und Profile, Ergebnisprüfung sowie kontrollierten Abbruch und Wiederanlauf. Diese Schritte bleiben von Verbindungstest, Installation und Druckstart getrennt. Die maßgeblichen Rechte stehen in [Repository-Lizenzgrenzen](REPOSITORY_NOTICES.md), [Slicer-Lizenz](LICENSE) und [Drittanbieterhinweisen](THIRD_PARTY_NOTICES.md); das Repository besitzt keine pauschale MIT-Zuordnung.

### Technische Studio-Namen

Neue Installationen verwenden `/local/3d-studio-setup/index.html`, den
Container `ultimate-3d-studio-homeassistant`, den HA-Standardpfad
`/opt/ultimate-3d-studio/home-assistant` und die private Sitzungsablage
`/var/lib/ultimate-3d-studio-setup`. TaraCraft bleibt das Branding und Copyright.
Bereits zugeordnete alte Sitzungen, Besitznachweise, Sicherungen und Container
bleiben lesbar; ihre gespeicherten Datenpfade werden nicht stillschweigend
umbenannt. Der Assistent zeigt auch dort den neuen Setup-Link an.
