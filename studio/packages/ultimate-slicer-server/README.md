# Ultimate Slicer Server – natives Linux-Paket

Dieses Verzeichnis enthält die Paketwerkzeuge für eine eigenständige native Linux-Bereitstellung des Ultimate Slicer Server. Der Dienst stellt API, Jobverarbeitung und Worker unabhängig von der Home-Assistant-Integration bereit. HACS ist für die separate HA-Integration vorgesehen und installiert dieses native Slicer-Paket nicht.

Der Quellcode ist öffentlich verfügbar. Ein freigegebener vollständiger Runtime-Download mit Slicing-Engine liegt noch nicht vor. **Der Freigabestatus bleibt `native_deploy_ready=false`; ein vollständiger Produktrelease ist offen (`FullRelease=false`).** Die abschließende Neuinstallation auf einem unabhängigen Linux-System bleibt der letzte Verifikationstest nach Fertigstellung der vorausgehenden Arbeit. Veröffentlichte Quellen, ein geprüftes Archiv oder ein grünes Quellgate bestätigen diesen Betriebsnachweis nicht.

[Handbuch](../../Slicer-Server/HANDBUCH.md) · [Linux-Testablauf](LINUX_TESTING.md) · [Installation und Einrichtung](../../Slicer-Server/INSTALLATION.md) · [Entwicklungsstand](../../Slicer-Server/RELEASE_STATUS.md)

## Lieferumfang und Voraussetzungen

`build_native_package.py` erzeugt ein deterministisches Quellarchiv. Seine Payloads und die fünf eigenständigen unprivilegierten systemd-Units werden über SHA-256 identifiziert. Die Prüfung macht den Umfang des Archivs nachvollziehbar; sie bestätigt weder eine ausführbare Engine noch die Rechte zur Weitergabe jeder enthaltenen oder zusätzlich benötigten Komponente.

`install_native.py` enthält einen eigenständigen Root-Installer für Erstinstallationen sowie getrennte Wege für Programm-Updates und Programm-Rollback. Ohne Installationsflag prüft er ein übergebenes Archiv nur lesend. Dafür verlangt er einen extern bestätigten Archiv-SHA-256. Eine Prüfsumme, die lediglich aus einer unbekannten Datei selbst berechnet wurde, ersetzt diesen Liefernachweis nicht.

Für einen späteren tatsächlichen Betrieb werden eine rechtmäßig nutzbare Linux-Slicing-Engine, eine unabhängige SHA-256-Dateiliste sowie vollständige Maschinen-, Prozess- und Filamentprofile benötigt. Die Engine gehört nicht zum öffentlichen nativen Quellarchiv. Der ausgelieferte gemeinsame [Engine-Katalog](../../Slicer-Server/engine_catalog.json) enthält derzeit `releases=[]`; Bambu Studio, PrusaSlicer und CuraEngine sind jeweils `pending`. Die verfügbaren Werkzeuge und Archivreferenzen sind daher noch kein freigegebener Runtime-Download.

Linux/amd64 ist der beschriebene Zielumfang. Eine allgemeine Zusage für ARM oder andere Architekturen setzt passende Engineprogramme, Bibliotheken und echte Tests voraus und wird aus dem Quellstand nicht abgeleitet.

## Hostabhängigkeiten lesend prüfen

Der Dienst verwendet die Python-Standardbibliothek sowie Linux-Systemwerkzeuge. Benötigt werden unter anderem `python3`, `jq`, `awk`, `grep`, `find`, `sort`, `head`, `tail`, `cut`, `tr`, `du`, `id`, `unshare`, `mkfifo`, `systemctl`, `useradd` und `userdel`. Der Installer prüft insgesamt 25 erforderliche Kommandos sowie die festen ausführbaren Programmpfade der systemd-Units.

Die notwendigen Systempakete werden vom Administrator bewusst bereitgestellt. Der Installer installiert keine Debian-Pakete automatisch und lädt keine fehlenden Abhängigkeiten herunter. Fehlt eine Voraussetzung, erfolgt ein kontrollierter Abbruch vor Änderungen an Benutzern, Programmen, Daten oder Diensten.

Die dokumentierte Hostprüfung wird aus dem Verzeichnis mit `install_native.py` ausgeführt:

```sh
python3 install_native.py --check-host
```

Bei Erfolg erscheinen `host_dependencies: ready` und `installation_performed: false`. Die Prüfung führt keine Slicer- oder Druckeraktion aus. Sie ersetzt weder eine Engine-/Lizenzprüfung noch den tatsächlichen Nachweis von systemd, Kernelisolation, TLS und Wiederherstellung. Der vollständige vorgesehene Testablauf steht in [LINUX_TESTING.md](LINUX_TESTING.md).

## Archiv bauen und prüfen

Die folgenden Originalbefehle zeigen den lokalen Paketbuild und die lesende Archivprüfung. Sie setzen ein eigenes Arbeitsverzeichnis mit den Paketwerkzeugen voraus. Der Quellpfad und der extern bestätigte SHA-256 sind Platzhalter für tatsächlich überprüfte Eingaben. Ausgabe und Arbeitsdateien gehören in einen eigenen privaten Arbeitsbereich; vorhandene Pakete oder Installationen werden dafür nicht überschrieben.

```sh
python3 build_native_package.py --source-root /pfad/zum/quellbaum --output ./ultimate-slicer-server.tar.gz
sha256sum ./ultimate-slicer-server.tar.gz
python3 install_native.py --archive ./ultimate-slicer-server.tar.gz --archive-sha256 <extern-geprüfter-sha256>
```

Der letzte Aufruf bestätigt ausschließlich den Archivvertrag. Er legt keinen Slicer-Benutzer an, installiert keine Units und startet keinen Dienst. Die Ausgabe wird zusammen mit dem geprüften Archivstand und dessen Herkunft beurteilt. Ein erfolgreicher lesender Prüflauf macht das Paket nicht automatisch installationsfähig.

Die Entwicklungspakete tragen `native_deploy_ready=false`. Damit bleiben `--install` und `--upgrade` auch dann gesperrt, wenn eine vollständige Engine angegeben wurde. Die Sperre wird weder durch einen Dokumentationstext noch durch das bloße Ergänzen eines Flags aufgehoben. Ein vorhandener Wiederherstellungspfad wird getrennt von der Erstinstallations- und Upgradefreigabe betrachtet.

## Verhalten einer später freigegebenen Erstinstallation

Der Erstinstallationsweg lehnt belegte Programmziele, vorhandene Daten und vorhandene systemd-Dienste ab. Er ist keine Migration einer laufenden Installation. Bestehende Konfigurationen, Jobs und Profile werden nicht als neue leere Installation übernommen oder überschrieben.

Die Implementierung erzeugt bei einer zulässigen Erstinstallation einen starken lokalen API-Schlüssel und speichert ihn unter `/etc/ultimate-slicer-server/config.json` mit eingeschränkten Gruppenrechten. Als Standardbindung ist `127.0.0.1` vorgesehen. Der Dienst erhält `User=ultimate-slicer`, `NoNewPrivileges=yes`, `ProtectSystem=strict` sowie getrennte Programm-, State- und Cacheverzeichnisse.

Eine Erstinstallation aktiviert und startet die Dienste nicht automatisch. Installation, Dienststart, Verbindungsprüfung, Slicing, Druckerupload und Druckstart bleiben getrennte Aktionen. Diese Beschreibung dokumentiert die vorhandene Implementierung; sie erteilt keine aktuelle Betriebsfreigabe.

## Netzwerkisolation der Engineprozesse

Der Worker verwendet für Slicing-Unterprozesse einen eigenen Netzwerk-Namespace. Im neuen nativen Paket läuft der Dienst als eingeschränkter Benutzer `ultimate-slicer` und verbindet User- und Netzwerk-Namespace, ohne dem Dienst Rootrechte auf dem Host zu geben. Der bereits vorhandene privilegierte Altbetrieb behält seinen bisherigen Aufrufvertrag; er wird durch dieses Paket nicht automatisch umgebaut.

Vor einer zulässigen Erstinstallation sieht der Root-Installer eine `runuser`-/`unshare`-Probe als eingeschränkter Dienstbenutzer vor. Diese Probe führt keinen Slice, Netzwerkzugriff oder Druckbefehl aus. Zusätzlich prüft `ultimate-slicer-dispatch.service` beim Start über `ExecStartPre` die tatsächlichen Dienstrechte.

Kann die Zielumgebung die sichere Namespace-Erzeugung nicht bereitstellen, brechen Installation beziehungsweise Dispatcher ab. Ein unisolierter Ersatzweg ist nicht vorgesehen. Isolierte Tests mit simulierten Systembefehlen belegen die portable Logik; die tatsächlichen Kernel-, AppArmor- und systemd-Bedingungen müssen auf der unabhängigen Linux-Umgebung nachgewiesen werden.

## HTTPS und Home-Assistant-Verbindung

Eine frische native Installation bindet standardmäßig nur an Loopback. Das API-Secret wird auch bei lokalen authentifizierten Anfragen benötigt. Eine andere Bind-Adresse ohne gültiges TLS-Zertifikat und zugehörigen privaten Schlüssel wird bereits beim Start verweigert. Fehlende, unvollständige oder ungültige Zertifikate sowie eine Remote-Klartextbindung sind keine unterstützten Einrichtungswege.

Die vorhandene Dokumentation zeigt folgende zusätzliche Netzwerkoptionen für die geschützte Konfigurationsdatei:

```json
{
  "host": "0.0.0.0",
  "port": 8443,
  "tls_certfile": "/etc/ultimate-slicer-server/tls/server.crt",
  "tls_keyfile": "/etc/ultimate-slicer-server/tls/server.key"
}
```

Dieses Fragment ist kein vollständiger Konfigurationsersatz. Das vom Installer erzeugte API-Secret und alle übrigen Einstellungen bleiben erhalten. Die Schlüsseldatei muss für den Dienstbenutzer lesbar und für andere Benutzer geschützt sein; dokumentiertes Beispiel sind `root:ultimate-slicer` und Modus `0640`. Der Schlüssel gehört weder in Git noch ins Frontend oder in Diagnoseexporte.

Das Zertifikat muss zum eingetragenen Hostnamen passen und von Home Assistant vertrauenswürdig geprüft werden können. Der Slicer erlaubt TLS ab Version 1.2. Alternativ kann ein TLS-Reverse-Proxy auf dem Slicer-Host terminieren, während der native Dienst strikt an `127.0.0.1` gebunden bleibt.

In Home Assistant werden unter **Einstellungen → Geräte & Dienste → Ultimate 3D Studio → Konfigurieren** die HTTPS-Adresse und das API-Secret hinterlegt. Der Verbindungstest fragt die geschützte Info-API ab. Er löst keinen Upload, Slice oder Druckstart aus. Eine reale Verbindung von einem anderen HA-Host einschließlich Zertifikatskette und Firewall bleibt ein eigener offener Nachweis.

## Verzeichnisse und Versionsmetadaten

| Aufgabe | Vorgesehener Pfad |
| --- | --- |
| Programmcode und separat beschaffte Engine | `/opt/ultimate-slicer-server` |
| Lokales Secret, Netzwerkoptionen und TLS-Dateien | `/etc/ultimate-slicer-server` |
| Jobs, Uploads, Status und Historie | `/var/lib/ultimate-slicer-server` |
| Native Dienste und Timer | `/etc/systemd/system/ultimate-slicer-*.service` beziehungsweise `.timer` |

Die zentrale Datei `release.json` enthält Softwareversion und numerische API-Protokollkompatibilität. Sie enthält keine Zugangsdaten. Der Bundler prüft ihre Syntax und nimmt ihre Dateiidentität in das Quellpaket auf. API-Server und natives Statusskript verwenden dieselben Metadaten für Info und Health.

Eine historische Hostinstallation ohne diese Datei bleibt bei ihren bisherigen Metadaten; ihr wird keine neue aktuelle Releaseversion zugeschrieben. Programm-, Dienst-, Datei-, API- und Assetnamen bleiben versionsneutral. Die tatsächliche Version wird als Datenwert transportiert und kann unabhängig von der HA-Integration aktualisiert werden.

## Programm-Update und Rückweg

Der Code-only-Upgradeweg setzt vollständig inaktive native Dienste und Timer, keine ausstehenden Jobs, eine geschützte Konfiguration, gepinnte Engine-Dateien und byteidentische systemd-Definitionen voraus. Er verändert die produktive Konfiguration, das API-Secret, vorhandene Jobs, Profileinstellungen und Units nicht. Änderungen an systemd-Definitionen werden abgewiesen und benötigen einen eigenen geprüften Migrationsvertrag.

Der neue Programm- und Enginebestand wird neben dem bisherigen Verzeichnis aufgebaut. Der bisherige Stand bleibt als rootgeschütztes, atomar umbenanntes Backup unter `/opt/.ultimate-slicer-server-backups` erhalten. Ein identisches Paket wird nach SHA-Vergleich als `unchanged=true` ohne Dateiaustausch und ohne neues Backup gemeldet.

Das folgende erhaltene Originalbeispiel beschreibt einen späteren ausdrücklich freigegebenen Testlauf. Es ist mit dem aktuellen Freigabestatus keine ausführbare Upgradefreigabe:

```sh
python3 install_native.py --archive /pfad/ultimate-slicer-server.tar.gz \
  --archive-sha256 <extern-bestätigter-SHA-256-Wert> \
  --upgrade --engine-root /pfad/zur-geprüften-engine \
  --engine-sha256-manifest /pfad/zur-geprüften-engine/SHA256SUMS \
  --accept-engine-license
```

Rollback akzeptiert ausschließlich ein nachweislich aus dem geschützten Upgrade-Backup stammendes `code`-Verzeichnis. Auch der ersetzte neuere Programmstand bleibt erhalten. Das dokumentierte Originalbeispiel lautet:

```sh
python3 install_native.py --rollback \
  --code-backup /opt/.ultimate-slicer-server-backups/<freigegebener-backupordner>/code
```

Keiner dieser Wege startet automatisch Dienste oder führt einen Slice aus. Ein Programm-Rollback ersetzt keinen vollständigen Datenrestore. Systemd- und Datenformatmigration sowie Wiederanlauf mit tatsächlichen Engine- und Jobdaten benötigen ihre eigenen Abnahmen.

## Offene Nachweise und Lizenzgrenzen

Vor der Betriebsfreigabe bleiben Engineherkunft und Lizenzpflichten, vollständige Hardware-/Materialprofile, reale Rechte und Isolation, systemd-Start, Health, HTTPS von einem zweiten Host sowie Upgrade-, Rollback- und Restoreverhalten zu prüfen. HACS-Paketierung und HA-Live-Pilot sind eigenständige Teile der Gesamtintegration. Die abschließende Linux-Neuinstallation mit echten Bedingungen bleibt der letzte Verifikationstest; aus vorherigen Quellprüfungen wird kein bestandener Installationstest abgeleitet.

Für die Rechte gelten [Repository-Lizenzgrenzen](../../Slicer-Server/REPOSITORY_NOTICES.md), die [Slicer-Lizenz](../../Slicer-Server/LICENSE), [Drittanbieterhinweise](../../Slicer-Server/THIRD_PARTY_NOTICES.md) und die ursprünglichen komponentenbezogenen Hinweise. Vorbestehende Rechte werden durch eine Quellprojektion nicht ersetzt. Das gesamte Repository besitzt keine pauschale MIT-Zuordnung. Engineprogramme, Betriebssystempakete und Bibliotheken benötigen vor ihrer Verteilung einen eigenen Herkunfts- und Lizenznachweis.
