# Container-Pruefung mit synthetischen Prozessen

## Gepruefter Umfang

Der Source-Preflight bleibt der normale Image-Einstieg. container_runtime.py
erganzt einen Kernelvertrag und die Ueberwachung genau eines eigenen
Supervisor-Prozesses. container_probe.py verwendet diesen Vertrag mit dem
unveraenderten kanonischen job_control.py und ausschliesslich einem frisch
erzeugten temporaeren Jobbaum. Es werden keine Engine und kein API-Server
gestartet und keine bestehenden Jobs, Modelle oder Profile eingebunden.

Die Probe erzeugt einen synthetischen Eltern-/Kindprozess, die SIGTERM
ignorieren. Der Supervisor muss seine private Prozessgruppe kontrolliert
eskalieren und vollstaendig beenden. Das Ergebnis ist nur gueltig, wenn der
Container mit Exitcode 0 und dem letzten Ereignis event=passed endet.

## Erforderliche Container-Eigenschaften

- UID ungleich 0 fuer alle vier vom Kernel gemeldeten UID-Felder.
- Alle fuenf Capability-Sets leer, NoNewPrivs=1 und Seccomp-Filtermodus=2.
- Im Worker ausschliesslich die Netzwerkschnittstelle lo.
- Gemeinsamer PID-Namensraum mit einem separaten Anker; verschiedene
  Netzwerk-Namensraeume von Worker und PID 1.
- Fuer die Abnahme: readonly Root-Dateisystem, begrenzte Prozesse und Speicher,
  beschreibbares /tmp nur als eigenes tmpfs, keine Host-/Datenvolumes.

Die Kernelpruefung allein beweist weder den Inhalt des Seccomp-Filters noch
ein vertrauenswuerdiges Docker-System oder ein unveraenderliches Dateisystem.
Diese Eigenschaften werden zusaetzlich an der Docker-Konfiguration geprueft.
Ein Umgebungsflag kann den Vertrag nicht freischalten.

## Nachstellen auf einem isolierten Docker-Testhost

Zuerst den geprueften Kontext nach INSTALLATION.md erstellen und das Image
bauen. SLICER_CHECK_IMAGE muss auf dieses lokal vorhandene Testimage zeigen.
Die folgenden Namen muessen frei sein; vorhandene Container nicht ersetzen.
Keine produktiven Volumes oder Docker-Sockets in Testcontainer einbinden.

Anker starten (er simuliert ausschliesslich die Prozesssicht der spaeteren API):

```sh
docker run -d --name studio-probe-anchor --init \
  --network=none --read-only --user=65532:65532 \
  --cap-drop=ALL --security-opt=no-new-privileges:true \
  --pids-limit=32 --memory=128m --entrypoint=python3 \
  "$SLICER_CHECK_IMAGE" -c 'import time; time.sleep(120)'
```

Worker-Probe starten:

```sh
docker run -d --name studio-probe-worker \
  --pid=container:studio-probe-anchor --network=none \
  --read-only --user=65532:65532 --cap-drop=ALL \
  --security-opt=no-new-privileges:true --pids-limit=32 --memory=128m \
  --tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777 \
  --entrypoint=python3 "$SLICER_CHECK_IMAGE" \
  /opt/ultimate-slicer-server/container_probe.py
docker logs studio-probe-worker
```

Auf event=ready warten, maximal 15 Sekunden. owner.supervisor_pid und
owner.identity aus diesem Ereignis erfassen. Innerhalb von 30 Sekunden die
Identitaet aus dem Anker pruefen; PID ist ausschliesslich die gerade von der
synthetischen Probe gemeldete Zahl:

```sh
docker exec studio-probe-anchor python3 -c \
  'import sys,json; sys.path.insert(0,"/opt/ultimate-slicer-server/payload"); from job_control import process_identity; print(json.dumps(process_identity(int(sys.argv[1]))))' \
  "$PID"
```

Die Ausgabe muss exakt owner.identity entsprechen. Erst dann SIGTERM senden:

```sh
docker kill --signal=TERM studio-probe-worker
docker wait studio-probe-worker
docker logs studio-probe-worker
docker rm -f studio-probe-worker studio-probe-anchor
```

Auch bei einer fehlgeschlagenen Probe ausschliesslich diese eigenen
Testcontainer entfernen. docker wait muss 0 melden. event=passed bestaetigt
Abbruchgrund worker_shutdown, gestoppte Nachfahren, entfernte Teilartefakte
und blockierten Wiederanlauf bei einem verwaisten slicing-Marker.
event=ready bestaetigt zusaetzlich den abgewiesenen zweiten Dispatcher.
Ein Exitcode ohne das abschliessende Ereignis reicht nicht als Abnahme.

Negativtest: Derselbe geschuetzte Worker ohne --pid=container:... muss bei
require_isolation mit separate_anchor_network_required abbrechen. Die
Python-Regressionen pruefen zusaetzlich Root-UID, Capabilities, fehlende
Kernelbelege, fremde Netzwerkschnittstellen und abgeschwaechte Schutzwerte.

## Stand der Teilabnahme

Auf Linux/amd64 mit zwei tatsaechlichen Docker-Containern nachgewiesen:
gemeinsame Prozesssicht bei getrenntem Netzwerk, Besitzeridentitaet vom Anker,
SIGTERM-Weiterleitung, Eskalation fuer synthetische Nachfahren, Bereinigung,
Dispatcher-Ausschluss und Wiederanlaufsperre. Beide Testcontainer wurden entfernt.

Offen bleiben der produktive Dienstzyklus mit API und Telemetrie, Race-Tests
bei Start/Shutdown, Anchor-Ausfall, Crash/Restore, Datenvolumes, die ausdrueckliche
Einbindung des Isolationsvertrags in den nativen Engine-Dispatcher und die
Engine-/TLS-/HA-Abnahmen. supervise liefert einen Prozessstatus; sein Aufrufer
muss zusaetzlich das Jobresultat und requires_recovery auswerten. Bei Timeout
wird der Supervisor nicht blind getoetet und kein Folgejob gestartet.
Das aktuelle Image bleibt container_deploy_ready=false.

## Startfreigabe und fruehe Abbrueche

Der Supervisor verwendet fuer den produktiven Aufrufer eine explizite
Bereitschafts-/Freigabe-Handschlagfolge. Der Kindprozess meldet Bereitschaft erst,
nachdem die kanonischen Signalhandler installiert sind. Ein Stop vor diesem Punkt
wird als Ablehnungstoken uebertragen und nicht als Signal an einen unvorbereiteten
Interpreter. Timeout oder Ende vor Bereitschaft liefern Wiederherstellungsbedarf;
der wartende Job bleibt unveraendert und ein Folgejob darf nicht starten.

Auf Linux/amd64 wurden drei synthetische Fehlerwege im neu gebauten, gepinnten
Quell-Preflight-Image geprueft: Stop vor Bereitschaft, ausbleibende Bereitschaft
und Ende vor Bereitschaft. In allen drei Faellen blieb der Dispatcher ungestartet.
Der fruehe Stop schrieb ein kanonisches Abbruchresultat ohne slicing-Marker; die
beiden Startfehler erhielten den queued-Zustand. Das ist keine Abnahme einer
produktiven API, Telemetrie, Engine oder eines realen Jobs. Das Image bleibt
container_deploy_ready=false.

## Portabler Schutz der Testpaket-Referenzen

prepare_test_server_package.py und verify_test_server_package.py pruefen
HTTP(S)-Referenzen rein als Daten. Es erfolgt kein DNS- oder Netzwerkzugriff.
Zugelassen sind nur die im Quellpaket einzeln geprueften Urspruenge:

| Schema | Host |
| --- | --- |
| https | github.com |
| https | opensource.org |
| https | docs.github.com |
| https | docs.docker.com |
| http | schemas.microsoft.com |
| http | www.gnu.org |
| http | fsf.org |

Der HTTP-Schemahost ist ein XML-Namensraum, keine Abrufanweisung.
Die beiden GNU-/FSF-HTTP-Urspruenge stammen unveraendert aus dem exakt
mitgelieferten AGPL-Text. Andere Schemas/Hosts werden dadurch nicht freigegeben.
Zusaetzlich sind synthetische HTTPS-Hostnamen unter .example erlaubt.
Andere Ziele einschliesslich IP-Adressen, Zugangsdaten in der URL,
abweichende Ports, Query-Strings und ungueltige URL-Autoritaeten sperren.
Eine neue Dokumentationsquelle braucht einen expliziten Quellreview und
eine getestete Erweiterung; keine automatische DNS-/Online-Freigabe.

Eigenstaendige Hostnamenzeilen unterliegen derselben Hostauswahl.
Interne/local Hostnamen und die bisherigen Schluessel-/Tokenmuster bleiben
gesperrt. Keine private Betreiber-Domain ist als Quellkonstante erforderlich.
Dies gilt fuer Quellpaketbildung, Archivpruefung und entpackte Dateien;
passende Manifesthashes heben die Inhaltspruefung nicht auf.

Grenze: Die Pruefung erfasst HTTP(S)-Referenzen, eigenstaendige
Hostnamenzeilen und die dokumentierten Muster. Beliebige eingebettete
Hostangaben in Freitext sowie weitere Protokolle bleiben Teil des
separaten Public-Inhaltsreviews. Sie ist weder vollstaendige
Secret-/Infrastrukturpruefung noch Lizenz- oder Betriebsfreigabe.

## Offline-Quellnachweis ausgewaehlter Profile (W84)

Das vorbereitete Kontextverzeichnis enthaelt PROFILE_SOURCE_BUNDLE.json und
verify_profile_sources.py. Die Beigabe ist lesbares JSON, kein ungeprueftes
Fremdbinaerprogramm. Der Paketguard prueft den Text; die bekannten 118
Originaltexte und ihre dekodierten JSON-Zeichenketten wurden zusaetzlich
gegen dieselben Inhaltsmuster geprueft. Ein festgelegter Bundle-SHA
verlangt fuer jede Aenderung einen neuen Quellenreview.

Nur lesende Offline-Pruefung des vorbereiteten Kontextes:

    python3 context/verify_profile_sources.py --context-root context

Alternativ direkt im Quellcheckout:

    python3 Slicer-Server/verify_profile_sources.py --source-root .

Erwartet: source_files=118, verified_profiles=54, process_projections=12,
gcode_sound_roundtrips=8, engine_executed=false, worker_started=false.
Es werden keine Netzabfragen, Programme aus dem Payload oder G-Code
ausgefuehrt. Diese Befehle installieren und starten keinen Dienst.
Im kuenftigen Image wird derselbe Verifikator samt Quellen mitkopiert;
ein echter Dockerbuild bleibt bis zur manuellen Laborabnahme offen.

Fehlende oder geaenderte Quellbeigaben sperren die Paketbildung vor Ausgabe.
Der Offline-Verifikator sperrt zudem falsche Identitaeten, zyklische oder
fehlende Vererbung sowie veraenderte lokale Profilwerte/Sound-Abschnitte.
Manifest-Lizenzscope fuer die Daten: third-party-profile-source.
Keine pauschale Rechte- oder Betriebsfreigabe.


## Sicheres Entpacken des Testpakets (W85)

Der Verifikator akzeptiert weiterhin nur ein neues Zielverzeichnis.
Das aeussere Ziel wird privat mit 0700 angelegt. Eigene Unterverzeichnisse
bleiben waehrend Aufbau und Byte-/Manifestpruefung mit 0700 beschreibbar;
erst danach werden sie von innen nach aussen auf 0555 gesetzt. Dateimodi
stammen unveraendert aus dem geprueften Archiv. Windows bildet POSIX-Modi
nicht vollstaendig ab; der Modusvertrag ist dort kein Linux-Nachweis.

Bei Abbruch werden ausschliesslich die in diesem Lauf selbst angelegten
Dateien und Verzeichnisse erfasst: Schreibrechte fuer den Rueckweg
wiederherstellen, Dateien entfernen, dann leere Verzeichnisse von innen
nach aussen entfernen. Vorhandene Ziele und fremde Nachbarpfade bleiben
unangetastet; unerwartete zusaetzliche Dateien werden nicht blind geloescht.
Scheitert diese Bereinigung, meldet der Verifikator extract_cleanup_failed
statt einen vollstaendigen Rueckweg zu behaupten. Der Restbaum bleibt
dann zur kontrollierten manuellen Pruefung erhalten.

Fuenf Regressionen pruefen synthetisch die POSIX-Schreibgrenze,
Finalisierung erst nach Readback, absteigende Verzeichnistiefe, Fehler bei
Readback/Verifikation/Finalisierung und explizite Bereinigungsfehler.
Sie starten weder Engine noch Worker, Container oder Netzwerk.
Eine echte Entpackprobe als eingeschraenkter Linux-Nutzer einschliesslich
Dateimodi, Dateisystem/ACL/umask und Fehler-Rueckweg bleibt manuell offen.
Der Entpacker ist kein Schutz gegen einen konkurrierenden boesartigen
Prozess mit derselben Benutzeridentitaet.


## Portabler Pfadvertrag des Testpakets

Manifest- und Archivpfade mit Backslashes, Doppelpunkten oder NUL werden
vor dem Entpacken abgewiesen. Damit koennen POSIX-Namen nicht auf Windows
als Ruecksprung, Laufwerksangabe oder NTFS-Datenstrom umgedeutet werden.
Auch zueinander passende Manifest-/Archivhashes erteilen keine Ausnahme.
Die Ablehnung erfolgt vor dem Anlegen des aeusseren Zielverzeichnisses.
Dies ersetzt keine reale Linux-/Windows-Rechte-, ACL- oder Betriebsabnahme.
