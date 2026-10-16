# Ultimate Slicer Server – natives Linux-Paket

Dieses Verzeichnis enthält die **versionsneutrale, unabhängige** Linux-Distribution des Slicers. Sie wird nicht durch HACS installiert; HACS installiert später nur die Home-Assistant-Integration.

## Was bereits existiert

- `build_native_package.py` erzeugt ein deterministisches, quellenbasiertes Archiv. Jeder Payload und jede der fünf eigenständigen, unprivilegierten systemd-Units ist SHA-256-geprüft.
- `install_native.py` ist ein eigenständiger **Root-Installer für eine Erstinstallation**. Standardmäßig prüft er ein Archiv **nur lesend**. Er verlangt immer einen extern bestätigten Archiv-SHA-256.
- Für eine tatsächliche Erstinstallation muss eine **separate, rechtmäßig nutzbare Linux-Slicing-Engine** mit unabhängiger SHA-256-Dateiliste und vollständigen Maschinen-, Prozess- und Filamentprofilen angegeben werden. Die Engine gehört bewusst **nicht** zum öffentlichen Quellarchiv.
- Vor der Installation werden vorhandene Installationen, Daten und systemd-Dienste ausdrücklich abgelehnt. Keine bestehenden Konfigurationen oder Jobs überschreiben.
- Der Installer erzeugt einen starken lokalen API-Schlüssel, speichert ihn unter `/etc/ultimate-slicer-server/config.json` mit gruppenbeschränkten Rechten und setzt `127.0.0.1` als Standardbindung.
- Der Dienst erhält `User=ultimate-slicer`, `NoNewPrivileges=yes`, `ProtectSystem=strict`, separate Programm-/Datenverzeichnisse sowie systemd-verwaltete State-/Cache-Verzeichnisse. Ein erster Installationslauf **aktiviert oder startet die Dienste nicht automatisch**.

## Laufzeitabhängigkeiten und Freigabesperre

Der native Linux-Dienst verwendet die Python-Standardbibliothek und externe Linux-Systemwerkzeuge. Für eine frische Installation sind insbesondere python3, jq, awk, grep, find, sort, head, tail, cut, tr, du, id, unshare, mkfifo, systemctl, useradd und userdel erforderlich. Auch die fest in den systemd-Units referenzierten Linux-Binärdateien müssen ausführbar sein.

**Der Installer prüft diese Voraussetzungen vor Änderungen an Programmen, Benutzern, Daten und Diensten.** Fehlt eine notwendige Abhängigkeit, bricht er kontrolliert ab. Es erfolgen weder automatische Paketinstallationen noch Downloads.

Ein lesend verifiziertes Paket ist **nicht automatisch installationsfreigegeben**. Die Entwicklungspakete tragen in den Paketmetadaten native_deploy_ready=false. Damit sind --install und --upgrade auch bei vollständiger Engine-Angabe gesperrt. Erst nach den offenen unabhängigen Linux-, Lizenz-, TLS-, HACS- und Restore-Abnahmen darf ein kontrollierter Releaseprozess einen freigegebenen Quellstand erzeugen. Ein vorhandener Wiederherstellungspfad bleibt davon getrennt.

## Versionsmetadaten ohne versionierte Pfade

Die native Slicer-Version wird ausschließlich in der mitgelieferten Datei `release.json` gepflegt. Diese enthält den Software-Versionswert und die numerische API-Protokollkompatibilität, aber keine Zugangsdaten. Der Paket-Bundler prüft ihre Syntax und nimmt die SHA-256-identifizierte Datei in das unabhängige Quellpaket auf.

Der API-Server liest diese Metadaten aus seinem konfigurierten Programmverzeichnis. Das native Statusskript verwendet **dieselbe Datei** für die Info- und Health-API. Eine bestehende historische Hostinstallation ohne `release.json` bleibt über ihre bisherigen Konfigurations- bzw. Statusmetadaten kompatibel und erhält keine erfundene aktuelle Releaseversion.

Neue Programm-, Datei-, Dienst-, Klassen-, Variablen-, API- und Assetnamen bleiben versionsneutral. Die tatsächliche Version wird nur als Datenwert transportiert und in der Studio-Oberfläche beziehungsweise im Verbindungsstatus angezeigt. Das Slicer-Paket kann unabhängig von der Home-Assistant-Integration aktualisiert werden.

## Rootless-Netzwerkisolation (Pflicht)

Der Worker nutzt für seine Slicing-Unterprozesse weiterhin einen eigenen Netzwerk-Namespace. Der bereits installierte privilegierte Altbetrieb behält den bisherigen Aufruf. Im neuen Linux-Paket läuft der Dienst aber mit `User=ultimate-slicer` und verwendet **User- und Netzwerk-Namespace gemeinsam**, ohne dem Dienst Rootrechte auf dem Host zu erteilen.

- Vor der Erstinstallation führt der Root-Installer eine reine `runuser`-/`unshare`-Probe als eingeschränkter Dienstbenutzer aus; kein Slicing, kein Netzwerkzugriff und kein Druckbefehl.
- Zusätzlich prüft `ultimate-slicer-dispatch.service` per `ExecStartPre` die tatsächlichen Dienstrechte bei jedem Start.
- Unterstützt die Zielumgebung diese sichere Namespace-Erzeugung nicht, bricht die Installation beziehungsweise der Dispatcher **ohne unsicheren Netzwerk-Fallback** ab.
- Die Windows-Tests verwenden nur isolierte Dateibäume und simulierte Systembefehle. Die reale Kernel-/AppArmor-/systemd-Prüfung muss auf der unabhängigen Linux-Testumgebung nachgewiesen werden.

## HTTPS für externe Slicer-Verbindungen

Ein frisch installierter Slicer bindet ausschließlich auf Loopback. Authentifizierung mit dem API-Secret gilt auch lokal. Eine andere Bind-Adresse ohne gültiges TLS-Zertifikat und zugehörigen privaten Schlüssel wird **bereits beim Start verweigert**.

Für Remote-Verbindungen können folgende zusätzliche Einstellungen in der geschützten Datei /etc/ultimate-slicer-server/config.json festgelegt werden:

    {
      "host": "0.0.0.0",
      "port": 8443,
      "tls_certfile": "/etc/ultimate-slicer-server/tls/server.crt",
      "tls_keyfile": "/etc/ultimate-slicer-server/tls/server.key"
    }

**Wichtig:** Dies ist kein vollständiger Konfigurationsersatz! Insbesondere das vom Installer erzeugte API-Secret sowie alle bestehenden Konfigurationseinstellungen bleiben erhalten. Der Schlüssel wird nicht in Git, in das Frontend oder in Diagnoseexporte übernommen. Die TLS-Schlüsseldatei muss für den eingeschränkten Dienstbenutzer lesbar, aber nicht für andere Benutzer zugänglich sein; beispielsweise root:ultimate-slicer und Modus 0640.

Das Zertifikat muss zum vom Nutzer angegebenen Hostnamen passen und von Home Assistant vertrauenswürdig geprüft werden können. Der Slicer erlaubt TLS erst ab Version 1.2. Unter Einstellungen → Geräte & Dienste → Ultimate 3D Studio → Konfigurieren wird die HTTPS-Serveradresse samt API-Secret hinterlegt. Der Verbindungstest fragt nur die geschützte Info-API ab, ohne Drucker-, Upload- oder Slicing-Aktionen.

Alternativ kann ein TLS-Reverse-Proxy auf dem Slicer-Host terminieren, während der native Slicer strikt an 127.0.0.1 gebunden bleibt.

Remote-Betrieb bleibt ein Freigabeblocker bis zur tatsächlichen TLS-Handshakeprüfung, korrekten Firewallregeln und isolierten systemd-Abnahme. Fehlende, unvollständige und ungültige Zertifikate sowie Remote-Klartextbindungen führen zum Startabbruch.

## Verzeichnisgrenzen

| Aufgabe | Verzeichnis |
|---|---|
| Geprüfter Programmcode + gesondert beschaffte Engine | `/opt/ultimate-slicer-server` |
| Lokales Secret und Netzwerkoptionen | `/etc/ultimate-slicer-server` |
| Jobs, Uploads, Status, Historie | `/var/lib/ultimate-slicer-server` |
| Native Dienste und Timer | `/etc/systemd/system/ultimate-slicer-*.service` bzw. `.timer` |

## Native Linux-Abhängigkeiten

Auf einer frischen Debian-Installation werden Python, JSON-/Shell-Werkzeuge und Linux-Namespace-Funktionen benötigt. Die folgenden Systempakete muss der Administrator bewusst vorinstallieren:

Der native Installer installiert keine Debian-Systempakete automatisch. Er prüft vor dem Anlegen von Benutzern, Dateien oder systemd-Diensten alle **25 erforderlichen Kommandos** und die für die Units verwendeten festen Pfade.

Eine vollständig lesende Vorprüfung auf dem vorgesehenen Linux-Host ohne Slicer- oder Druckeraktionen:

    python3 install_native.py --check-host

Bei Erfolg werden die Statusfelder `host_dependencies: ready` und `installation_performed: false` ausgegeben. Fehlende Programme führen zu einem sicheren Abbruch. Die Prüfung ersetzt weder die vollständige Engine-/Lizenzprüfung noch die systemd-/TLS-Abnahme.

## Rein lesende Vorprüfung

Nach lokalem Paketbuild kann die Vorprüfung ohne Root und ohne Dienstveränderung erfolgen:

```bash
python3 build_native_package.py --source-root /pfad/zum/quellbaum --output ./ultimate-slicer-server.tar.gz
sha256sum ./ultimate-slicer-server.tar.gz
python3 install_native.py --archive ./ultimate-slicer-server.tar.gz --archive-sha256 <extern-geprüfter-sha256>
```

Der letzte Aufruf bestätigt lediglich den Archivvertrag. Das Flag `--install` wird **nicht** ohne validierte Engine-Prüfsummen, Lizenzfreigabe und gesonderten Linux-Installations-/Restore-Test verwendet.

## Code-only-Upgrade und Wiederherstellung

Der Installer unterstützt jetzt zusätzlich explizite, getrennte Betriebsarten für **Programm-Updates** und **Programm-Rollback**. Die produktive Konfiguration, das Secret, vorhandene Jobs, Profileinstellungen und die systemd-Units werden dabei nicht verändert.

- **Code-only-Upgrade:** Nur bei nachgewiesen vollständig inaktiven nativen Diensten und Timern, ohne ausstehende Jobs, mit bereits geschützter Konfigurationsdatei, gepinnten Engine-Dateien und byteidentischen systemd-Definitionen. Die neue Code-/Engine-Struktur wird vollständig neben dem alten Programmverzeichnis aufgebaut; das bisherige Verzeichnis bleibt als rootgeschütztes, atomar umbenanntes Backup unter \`/opt/.ultimate-slicer-server-backups\` erhalten.
- **Identisches Paket:** Wird nach SHA-Vergleich ohne Dateienwechsel und ohne neues Backup als \`unchanged=true\` zurückgemeldet.
- **Rollback:** Ausschließlich ein nachweislich aus diesem geschützten Upgrade-Backup stammendes \`code\`-Verzeichnis darf wiederhergestellt werden. Auch der ersetzte neuere Programmstand wird behalten. Secret und Benutzerdaten bleiben unverändert.
- **systemd-Änderungen:** Werden von diesem Code-only-Upgrade absichtlich verweigert und benötigen einen später separat geprüften Service-Migrationsvertrag.
- **In allen Betriebsarten:** Kein automatischer Dienststart, kein Druckerzugriff und kein Test-Slice.

Beispiel einer später auf einer gesondert freigegebenen Linux-Testumgebung durchzuführenden Aktualisierung:

\`\`\`bash
python3 install_native.py --archive /pfad/ultimate-slicer-server.tar.gz \
  --archive-sha256 <extern-bestätigter-SHA-256-Wert> \
  --upgrade --engine-root /pfad/zur-geprüften-engine \
  --engine-sha256-manifest /pfad/zur-geprüften-engine/SHA256SUMS \
  --accept-engine-license
\`\`\`

Die Ausgabe enthält den privaten Backuppfad für einen ausdrücklich freigegebenen Wiederherstellungslauf:

\`\`\`bash
python3 install_native.py --rollback \
  --code-backup /opt/.ultimate-slicer-server-backups/<freigegebener-backupordner>/code
\`\`\`

Diese Beispiele sind **keine Freigabe für die produktive HA-VM**. Der vollständige, unabhängige Debian-Lauf mit echten Rechten, Lizenzen, Engine-Daten, Arbeitsprofilen sowie Neustart und Restoration bleibt ein Release-Gate.

## Noch ausstehende Freigabeschritte

1. Reale isolierte Debian-Erstinstallation unter Linux/root, inkl. Rechte-, systemd-, Health- und Wiederanlauftests.
2. Engine-Lizenz, Dateiprovenienz und vollständige Hardware-/Materialprofile überprüfen; keine automatischen Downloads oder Engine-Binärdateien im öffentlichen Quellpaket.
3. Code-only-Upgrade und -Rollback sind mit synthetischen Jobdaten getestet. Systemd-/Datenformatmigration und vollständige Linux-Wiederanlaufabnahme bleiben offen; der Erstinstallationsmodus verweigert weiterhin belegte Installationsziele.
4. Authentifizierter HTTPS-Zugang von einer anderen Home-Assistant-Installation mit einem verifizierten Zertifikat; kein öffentlicher Klartextserver.
5. HACS-Komplettpaket, frontendseitige dynamische Buildanzeige, HA-Live-Pilot und anschließender kontrollierter GitHub-main-Release.

**Freigabestatus: `native_deploy_ready=false`.** Alle Änderungen in diesem Schritt betreffen ausschließlich PC-Quellen und private Offline-Tests; die laufende HA-Instanz und GitHub bleiben unverändert.
