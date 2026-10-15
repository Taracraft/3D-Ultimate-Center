# Docker-Dienstkandidat: Installation und Betrieb

Dieser Stand startet API, Worker und Telemetrie als Docker-Compose-Dienste.
Die Linux/amd64-Abnahme umfasst TLS/Authentifizierung, Leerlauf, kontrollierten
Stop/Neustart, doppelte Worker, Anchor-Ausfall und erhaltene verwaiste Jobmarker.
Ein Backup/Restore des synthetischen Testbestands wurde hashgenau geprueft.
Er ist noch keine freigegebene Slicer-Installation: eine Engine ist nicht
enthalten. Reale Slices, HA-Verbindung und die Migration
bestehender Daten sind noch abzunehmen. `container_deploy_ready=false` bleibt.

## Was zusammen startet

- `api` stellt die bestehende API ueber TLS bereit und ist PID-Anchor.
- `worker` teilt dessen PID-Namensraum fuer die bestehende Besitzerpruefung,
  hat jedoch `network_mode: none`.
- Genau ein Worker besitzt den Dienst-Lock; genau ein Thread aktualisiert
  die Telemetrie. Fehler sperren weitere Auftraege ueber eine erhaltene
  Wiederherstellungsmarkierung.
- Der Dispatcher verwendet im Container die Kernelpruefung vor jedem
  Engine-Aufruf. Der native Installationsweg behaelt seine unshare-Isolation.

Beide Dienste laufen ohne Root, zusaetzliche Capabilities oder Docker-Socket.
Root-Dateisystem und Engine sind nur lesbar. Gemeinsamer PID-Namensraum und
gemeinsame UID sind kein Schutz vor einem boesartigen gleichberechtigten
Prozess; insbesondere sind separate Secret-Mounts keine vollstaendige
Prozess-Sicherheitsgrenze. Dieser Punkt gehoert in die Release-Pruefung.

## Neues, isoliertes Testsystem vorbereiten

Nur einen neuen Linux-Docker-Testpfad verwenden. Bestehende native Laufzeitdaten
werden hier nicht automatisch uebernommen. Docker Compose muss vorhanden sein.
Der Quellbaum muss vollstaendig sein.

1. Den Kontext mit `prepare_context.py` wie in [INSTALLATION.md](INSTALLATION.md)
   erzeugen und das Image mit einem geprueften Python-Basisdigest bauen.
2. Eine lokale, unveraenderliche Image-ID mit
   `docker image inspect --format '{{.Id}}' <lokaler-image-name>` feststellen.
3. Folgende Verzeichnisse ausserhalb des Repositorys bereitstellen:

   - `data/`: neues persistentes Datenverzeichnis, UID/GID 65532:65532.
   - `engine/`: schreibgeschuetzte Engine samt Bibliotheken und Profilen.
     Fuer reine Leerlaufpruefungen darf dieses Verzeichnis leer sein.
   - `tls/`: `server.crt` und `server.key`; Schluessel lesbar fuer UID 65532,
     Modus 0600; Elternverzeichnis zugreifbar fuer diese UID.
   - `api-token`: lokal erzeugtes zufaelliges API-Secret mit mindestens
     32 druckbaren ASCII-Zeichen, UID 65532, Modus 0600.

Das Zertifikat muss zum spaeter verwendeten Hostnamen passen und Home Assistant
muss seiner CA vertrauen. Kein Abschalten der Zertifikatspruefung als
Installationsschritt. Die Tests verwenden ausschliesslich eigene temporaere
Zertifikate mit explizit vertrautem Testzertifikat.

## Compose konfigurieren

Die folgenden Werte sind Beispiele fuer neue Testpfade und muessen lokal
angepasst werden. Secrets selbst kommen nicht in die Umgebung oder ins Repo.

```sh
export SLICER_IMAGE='sha256:<lokal-gepruefte-image-id>'
export SLICER_DATA='/srv/ultimate-slicer-test/data'
export SLICER_ENGINE='/srv/ultimate-slicer-test/engine'
export SLICER_TOKEN='/srv/ultimate-slicer-test/api-token'
export SLICER_TLS='/srv/ultimate-slicer-test/tls'
export SLICER_BIND='127.0.0.1'
export SLICER_PORT='8099'
docker compose -f Slicer-Server/compose.candidate.yaml config --quiet
docker compose -f Slicer-Server/compose.candidate.yaml up -d
docker compose -f Slicer-Server/compose.candidate.yaml ps
```

Platzhalter sind keine veroeffentlichten Images. `pull_policy: never` verlangt
ein bereits lokal vorhandenes Image. Fehlende Bind-Mounts werden nicht
automatisch angelegt. Der Standard-Bind bleibt auf dem Docker-Host lokal;
ein Zugriff von HA auf einem anderen Host benoetigt eine ausdruecklich passende
Bind-Adresse, Firewall-Freigabe und vertrauenswuerdiges TLS-Zertifikat.

Die Quelle fuer die Compose-Eigenschaften ist die
[offizielle Docker-Referenz](https://docs.docker.com/reference/compose-file/services/).

## Zustand pruefen

`GET /api/v1/health` ist oeffentlich und gibt ohne Engine `degraded` zurueck.
`GET /api/v1/info` erfordert `Authorization: Bearer <Secret>`.
Ein `200` auf Health beweist Erreichbarkeit, keine funktionierende Engine.
Der Worker-Healthcheck prueft Herzschlag, Prozessidentitaet und Recovery-Sperre.

```sh
docker compose -f Slicer-Server/compose.candidate.yaml logs --tail 100 api worker
docker compose -f Slicer-Server/compose.candidate.yaml exec worker \
  python3 /opt/ultimate-slicer-server/container_service.py worker-check
```

Logausgaben und generierte Daten koennen private Informationen enthalten.
Die API-Konfiguration mit Secret liegt ausschliesslich im privaten
Container-tmpfs; das Image enthaelt weder Standortkonfiguration noch Token.

## Stop, Neustart und Fehler

```sh
docker compose -f Slicer-Server/compose.candidate.yaml stop
docker compose -f Slicer-Server/compose.candidate.yaml down
docker compose -f Slicer-Server/compose.candidate.yaml up -d
```

Compose stoppt abhaengige Worker vor dem API-Anchor. Fuer einen Imagewechsel
oder Anchor-Neustart beide Dienste gemeinsam neu erzeugen; den Worker nicht
an einem alten PID-Namensraum weiterbetreiben. Automatische Restart-Schleifen
sind im Kandidaten ausgeschaltet. Ein ungesunder Dienst wird nicht automatisch
repariert.

`run/container-recovery.json` oder vorhandene `*.slicing.json` blockieren den
Worker. Nicht automatisch loeschen und Jobs nicht einfach erneut freigeben:
zuerst beide Dienste stoppen, Daten sichern, alle zum alten Container gehoerigen
Prozesse als beendet nachweisen und den kanonischen Jobzustand untersuchen.
Ein Rueckwechsel des Images entfernt diese Datenmarkierungen nicht.

## Daten und Rueckweg

Vor Backup oder Restore beide Dienste stoppen und ihren Stillstand pruefen.
Daten, eigene Profile, Auftraege und Resultate gemeinsam sichern; API-Token,
TLS-Dateien, Compose-Konfiguration und exakte Image-ID separat geschuetzt
aufbewahren. Restore zuerst in einen neuen privaten Testpfad vornehmen, UID/GID
und Rechte erhalten und Dateihashes vergleichen. Produktive Volumes niemals
mit einem leeren Testverzeichnis ersetzen.

Diese Schritte definieren den Betriebsweg. Eine vollstaendige Datenmigration
und ein Restore bestehender produktiver Auftraege sind damit noch nicht
abgenommen.

## Noch offene Freigabekriterien

- Engine-/Profil-/Bibliotheksumfang, nachvollziehbare Herkunft und Lizenzen.
- Reale Engine-Abnahme auf der Zielarchitektur; keine ARM-Zusage ohne Test.
- Zusaetzliche Crash-Faelle mit realer Engine; der synthetische Anchor-Ausfall ist geprueft.
- Verifizierte HA-Verbindung und frische Installation auf einem weiteren Host.
- Geprueftes Backup/Restore sowie Bestandsmigration ohne Datenverlust.
- Datenschutz-/Lizenz-/Releasepruefung und nachvollziehbarer veroeffentlichter
  Image-Digest; README/Wiki gegen genau dieses Image nachstellen.


## W21: Prusa-/Cura-Bibliotheken im Docker-Kandidaten (10.10.2026)

22 weitere Laufzeitpakete ergaenzt. Neues Linux/amd64-Kandidatenimage gebaut;
356 installierte Debian-Pakete im Versionsinventar. Statische Pruefung ohne
Engineausfuehrung: Bambu 172 ELF/731 Abhaengigkeiten/1356 Versionspruefungen,
Prusa 222/965/1929, Cura 11/32/139. Bei allen drei Engines fehlen weder
Bibliotheken noch angeforderte GNU-Versionen. Dies ist keine Pruefung von
Symbolbindung, dynamisch geladenen Plugins, Profilen oder realem Slicing.

Isolierter Compose-Leerlauf: Worker gesund, TLS mit explizitem Testvertrauen,
Info mit Token=200, ohne Token=401; eigene Testcontainer wieder entfernt.
58 gezielte Docker-Kontexttests bestanden, ein Windows-Symlink-Skip.
PC zuerst, danach HA-Quellspiegel mit Originalbackups und SHA-Vergleich.
Abschliessendes Gesamtgate und generierte Build-Metadaten werden separat im
privaten W21-Checkpoint nachgewiesen; dieser Eintrag behauptet keinen Live-Deploy.

Weiter offen: kuratierter versionierter Engine-/Profilkatalog, automatische
Bereitstellung und passende Containerpfade fuer Prusa/Cura, persistenter
Speichervertrag und Installationsdienst, gefuehrter HA-Assistent, reale
Engine-/Neuinstallations-/Upgrade-/Restore-Abnahme. Es sind noch keine Engines
im Image installiert. container_deploy_ready=false bleibt. Docker zuerst,
danach weitere Migration und GitHub-Veroeffentlichung mit Wiki/main-Abschluss.

Die geplante einfache Einrichtung erfolgt aus Home Assistant, siehe
[HA-Einrichtungsassistent](HA_INSTALLATION_PLAN.md). Automatischer Dauerspeicher
ist der Standard; ein eigener Pfad bleibt unter Erweitert moeglich.


## W22: Gemeinsame Container-Enginepfade (10.10.2026)

Dispatcher und Telemetrie verwenden jetzt denselben lesenden Pfadvertrag:
`/engine/<engine-id>/bin/<binary>`. Bambu-API und Worker teilen die neue
Ressourcenwurzel. Native Hostdefaults bleiben erhalten. Fehlende/nicht
ausfuehrbare Programme und verlinkte Einstiegspfade werden abgewiesen;
kein Container-Fallback auf PATH oder Hostprogramme. Version bleibt ohne
Nachweis unknown. Details: Slicer-Server/ENGINE_LAYOUT.md.

PC zuerst, dann HA-Quellen mit Originalbackups und SHA-Abgleich. Docker-
Dateifreigabe fuer das neue Modul beim realen Build ergaenzt; danach Image
erfolgreich gebaut. 75 gezielte PC-Tests bestanden, 6 Windows-Plattformskips.
Linux-Container: 11 Pfadpruefungen, zwei rein synthetische Prusa-/Cura-
Dispatcherlaeufe erfolgreich, fehlende Bambu-Engine abgewiesen, Telemetrie
identisch zur Erkennung. Die Linux-Pruefung deckt die Symlink-/Ausfuehrbarkeits-
Faelle ab; auf dem HA-Host ist pytest nicht installiert.
Compose mit leerem Engine-Speicher: Worker gesund, Health degraded,
Engine-Liste leer, TLS/Auth bestanden. Eigene Testcontainer entfernt.

Gesamtgate und finale Build-Synchronisation werden im privaten W22-Checkpoint
nachgewiesen. Keine echte Engine, kein echter Slice und kein Produktivdeploy.
Automatischer Download/Installationskatalog, Ressourcen/Profile, transaktionaler
Installer und HA-Assistent bleiben offen; container_deploy_ready=false.

Der Hostpfad SLICER_ENGINE ist jetzt die Wurzel mit den drei Engine-Unterordnern,
kein direktes Bambu-squashfs-root. Siehe [Engine-Speicher](ENGINE_LAYOUT.md).
