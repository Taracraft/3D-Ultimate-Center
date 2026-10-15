# Transaktionaler Host-Lifecycle

## Implementierter Umfang

host_lifecycle.py implementiert den dauerhaften Ablauf fuer einen Wechsel einer
bereits bestehenden, eindeutig identifizierten API-/Worker-Installation.
Es ist ein lokal provisionierter Orchestrierungskern mit vertrauenswuerdigen
Speicher- und Laufzeitadaptern. Ein konkreter Dockeradapter ist als Quelle
implementiert und synthetisch geprueft; Host-Diensteinstieg und HA-Backend
sind noch nicht implementiert.
Der restricted_installer ist optional ueber InstallerLifecycle mit dem Kern
verdrahtet; die lokale Hostprovisionierung bleibt separat erforderlich.
Diese Quelle allein aktiviert deshalb keine neue Remote-Operation und setzt
container_deploy_ready nicht auf true. Erstinstallation ohne laufenden
Vorgaenger sowie Supervisor-Verpackung bleiben eigene Implementierungsschritte.

## Verbindliche Bindung und Nachweise

Jeder Wechsel bindet eine 32-stellige Hex-Request-ID und exakt vier Identitaeten:
generation_id, unveraenderliche sha256-Image-ID, Compose-SHA256 und Volume-SHA256.
Freie Pfade, URLs, Shellbefehle und Geheimnisse sind kein Teil dieses Vertrags.

Ein Laufzeitnachweis enthaelt diese Bindung, zwei unterschiedliche vollstaendige
Container-IDs fuer api und worker, den echten booleschen Laufzustand sowie
bestaetigte Mount- und Isolationspruefung. Ein Gesundheitsnachweis ergaenzt
authentifizierte TLS/API-Pruefung, gesunden Worker und die exakte Wartungs-ID.
Ein boolesches True ist zwingend; truthy Platzhalter gelten nicht.

Der konkrete vertrauenswuerdige Adapter muss diese Aussagen selbst anhand
frischer Docker-/Kernel-/TLS-Daten pruefen. Der Kern kann eine erfundene Aussage
eines kompromittierten lokalen Adapters nicht erkennen. Request-Daten duerfen
niemals Adapter, Callback, Mountpfad oder Command ersetzen.

## Ablauf eines Wechsels

1. Privates Steuerverzeichnis und VolumeGuard pruefen, Prozesssperre erwerben.
2. Alten Laufzeitnachweis und aktuelle ACTIVE-Generation vergleichen.
3. Ausgangs- und Zielbindung samt Container-IDs dauerhaft protokollieren.
4. Wartungsabsicht speichern, Wartung als Runtime-UID setzen und bestaetigen.
5. Stop-Absicht speichern; ausschliesslich die nachgewiesenen Container stoppen.
6. Stillstand, Datentraeger und Wartung erneut pruefen.
7. Aktivierungsabsicht speichern; Generation ueber den Storeadapter wechseln
   und deren aktuellen Stand zuruecklesen.
8. Stillstand, Volume und Wartung erneut bestaetigen; Startabsicht speichern.
9. Ziel starten; Image-/Container-/Mount-/Isolations-/TLS-/Worker-Nachweise
   verifizieren und als ready_paused dauerhaft speichern.

Ein Startaufruf allein ist keine erfolgreiche Installation. Ein gesunder
Container allein ist keine gueltige TLS-Verbindung. ACTIVE allein veraendert
keinen Compose-Mount.

## Wiederaufnahme und Rueckweg

ready_paused bleibt unter Wartung. resume ist eine ausdrueckliche lokale
Betriebsentscheidung: Nochmals alle Gesundheitsnachweise und dieselben
Container-IDs pruefen, resuming dauerhaft speichern, erst dann die Barriere
entfernen und die Antwort bestaetigen. Das kann bereits freigegebene
Warteschlangeneintraege ausfuehren; es ist kein lesender Verbindungstest.

Fehler loesen niemals automatisch Resume oder Rollback aus. Das Journal bleibt
in der zuletzt bestaetigten Absichtsphase, requires_recovery wird true.
dispatch_blocked ist in Zwischenphasen null: Ein Timeout beweist weder
Vorhandensein noch Fehlen der Barriere.

Ein expliziter rollback braucht dieselbe Request-ID und eine erneut bewiesene
Wartungsbarriere. Der aktuelle Laufzeitbestand muss exakt dem alten oder dem
Zielvertrag entsprechen. Erst nach dessen bestaetigtem Stop darf der Store-
Adapter die alte Generation einschliesslich ihres Transaktionsjournals
wiederherstellen. Anschliessend wird der alte Dienstvertrag gestartet und
vollstaendig geprueft. Ergebnis ist restored_paused, niemals automatische
Wiederaufnahme. Eine teilweise entstandene/unbekannte Containergruppe bleibt
gesperrt und erfordert gesonderte lokale Bestandsklaerung.

Nach resuming ist der Ausgang bei verlorenem Rueckgabewert oder
Speicherfehler unklar. Resume/Rollback werden nicht blind wiederholt.
Auch complete ist ein historischer Transaktionsbeleg, kein aktueller
Gesundheitscheck. status zeigt den gespeicherten Stand; es startet nichts.

## Persistenz und Wiederholungen

Das eigene Steuerverzeichnis muss privat sein (POSIX 0700, eigener Besitzer).
Journal und Belege sind begrenzt, regulaer, nicht mehrfach verlinkt, POSIX0600;
Duplicate-JSON-Felder, Links und defekte Zustandskombinationen werden abgewiesen.
Atomarer Austausch, Datei-/Verzeichnis-fsync und Readback erfolgen vor jedem
nachfolgenden mutierenden Adapteraufruf. Eine separate Prozesssperre serialisiert
Wechsel, Rueckweg und Resume, ohne den lesenden Status zu blockieren.

Unvollstaendige Transaktionen blockieren andere Request-IDs. Dieselbe ID mit
anderem Ziel ist ein Konflikt. Abgeschlossene Belege werden vor einem neuen
Wechsel in receipts dauerhaft erhalten; alte Requests liefern ihren Beleg und
loesen keine erneute Aktion aus. Maximal128 archivierte Belege; bei voller
Historie kein automatisches Loeschen. Der Betreiber braucht dann einen
gesonderten gesicherten Aufbewahrungsprozess.

Das Lifecycle-Verzeichnis muss vom restricted_installer-Steuerverzeichnis
getrennt provisioniert werden, bevor beide Kerne verbunden werden: Beide
verwenden derzeit denselben relativen Namen transactions/install.lock.
Eine verschachtelte Sperre auf derselben Datei waere unzulaessig.

## Adaptervertrag und offene Verdrahtung

- verify_volume: vorhandener VolumeGuard, frisch vor jedem kritischen Schritt.
- active_generation: frisch gepruefte Storebindung und aktuelle Generation.
- activate/restore: begrenzte Generation-Operation; keine vom Request bestimmten
  Download-URLs oder Pfade. Restore muss ACTIVE und Storejournal gemeinsam
  rekonstruieren; ein reiner Compose-Rueckweg reicht nicht.
- snapshot/stop/stopped/start: eindeutig dieser Installation zugeordnete
  Container, feste Compose-/Image-/Mountvertraege, keine Shell aus Eingaben.
- pause/paused/resume/resumed: bestehende Wartungssperre unter Runtime-UID,
  dieselbe dauerhafte Request-ID, keine pauschale Markerloeschung.
- health: reale Image-/Mount-/Isolationsdaten, authentifizierte TLS/API-Antwort
  und frische Worker-Telemetrie. Ein Compose-Startresultat allein reicht nicht.

Die Docker-Dokumentation unterscheidet Start-/Health-Warten und Build/Pull-
Verhalten. Ein spaeterer Adapter muss dies fest konfigurieren; diese
Dokumentation behauptet keine bereits erfolgte Docker-Ausfuehrung.
Referenz: https://docs.docker.com/reference/cli/docker/compose/up/

Naechster zusammenhaengender Block: konkreter Dockeradapter inklusive begrenzter
Ausgaben/Fristen und Teilstart-Reconciliation, echte Store-Rollbackkopplung,
Hostentrypoint, Erstinstallation und HA-Backend. Danach folgen die vorgesehenen
realen Neuinstallations-, Upgrade-/Restore-, TLS- und Engine-Abnahmen.

## Synthetische Abnahme

32 Tests pruefen Wechsel, wiederholte und widerspruechliche IDs, mehrere
Transaktionen mit aufbewahrten Belegen, volle Historie, abgesicherte
Mutationsreihenfolge, Neustart, unklare Ausgaenge, Volumeverlust, exakte
Containeridentitaeten, TLS-/Worker-/Wartungsnachweise und expliziten Rueckweg.
Windows:30 PASS,2 POSIX-Skips,23 Untertests. Linux prueft zusaetzlich Besitz,
Modi und Links. Keine Docker-, Engine-, Drucker- oder Produktivdienstaktion.
Endgate und PC/HA-Synchronitaet werden im privaten Checkpoint nachgewiesen.

## Fester Docker-Hostadapter (synthetischer Stand 11.10.2026)

docker_host_adapter.py implementiert jetzt den lokalen Laufzeitadapter fuer den
oben beschriebenen Transaktionskern. Seine Konfiguration entsteht ausschliesslich
aus lokal provisionierten absoluten Pfaden und unveraenderlichen Identitaeten.
Weder Installationsrequest noch HA-Nachricht duerfen Dockerargumente, Composepfad,
Mountpfade, Image, Bindadresse oder Callbacks liefern.

Der Adapter fuehrt ausschliesslich argv-Vektoren ohne Shell aus. stdout/stderr
werden parallel abgeleitet, auf je 128 KiB begrenzt und bei Frist- oder
Ausgabelimit wird die eigene Prozessgruppe beendet. Compose wird vor jedem
Aufruf erneut gegen den gepinnten SHA256 geprueft. Start verwendet das lokale
Image mit --no-build und --pull never. Stop adressiert nur die zuvor frisch
bewiesenen vollstaendigen API-/Worker-Container-IDs.

Frische Docker-Inspect-Daten muessen Projekt-/Service-Labels, unveraenderliche
Image-ID, UID/GID65532, read-only root, CapDrop ALL, no-new-privileges,
PIDs-Limit, Restart=no, genaue Bind-Mountquellen und Schreibmodi belegen.
Zusaetzlich werden API-Bind/Port, Worker network=none und dessen PID-Bindung an
genau den API-Container geprueft. Fehlender oder nur teilweise vorhandener
API-/Workerbestand ist reconciliation_required und wird nicht als leerer
Erstinstallationszustand interpretiert.

Die Wartungsbefehle laufen im bereits zugeordneten API-Container explizit als
65532:65532. Der Adapter liest den dauerhaften Marker descriptorbasiert aus dem
Datenmount und bindet die exakte Request-ID. Health verlangt zusaetzlich
Worker=healthy sowie eine authentifizierte HTTPS-/api/v1/info-Antwort mit
API-Vertrag2 und Abbruchvertrag1. Tokeninhalt erscheint weder in argv noch in
der Umgebung.

Dies ist noch keine Hostinstallation: Der Adapter ist noch nicht mit dem
restricted_installer verbunden, besitzt keinen freigegebenen Systemdienst und
behandelt einen fehlenden Vorgaenger bewusst als Teilstart-Reconciliation.
Storeauswahl, Erstbootstrap, HA-Backend und echte Docker-/TLS-/Restore-Abnahme
bleiben offen. container_deploy_ready bleibt false.
## 11.10.2026 - Dockeradapter: Rueckweg und Wartungsnachweis korrigiert

Die Integrationspruefung zwischen echtem Lifecycle-Kern, Dockeradapter und
kanonischem JobControl hat zwei bisher ungedeckte Fehler nachgewiesen und
behoben. Ein vollstaendig gestopptes, weiterhin eindeutig zugeordnetes API-/
Workerpaar ist jetzt ein gueltiger Bestandsnachweis. Stop prueft seine aktuelle
Identitaet, Bindung, Mounts und Isolation erneut und wiederholt bei bereits
bestaetigtem Stillstand keine Mutation. Gemischte, fehlende, pausierte,
neustartende oder unklare Laufzustaende bleiben gesperrt.

Der Wartungsmarker wird vor dem Oeffnen auf Groesse und danach ueber denselben
Dateideskriptor auf Identitaet, Typ, Rechte und maximal4096Bytes geprueft.
Doppelte JSON-Felder und ungueltige Feldtypen werden wie im JobControl
abgewiesen. Der Rueckweg nach fehlgeschlagenem Start funktioniert auch nach
Neustart des Orchestrators und bleibt restored_paused; Resume ist ausdruecklich.

Zehn neue Integrationstests verwenden den konkreten Adapter und kanonisches
JobControl mit synthetischer Dockergrenze. Zusammen mit Adapter/Lifecycle:
Windows50PASS,4POSIXSkips,41Untertests; Linux54PASS ohneSkips.
Keine echte Docker-/Engine-/Dienst-/Jobaktion. Installer-/Storeverdrahtung,
Erstbootstrap, HA-Setup und reale Installation/Restore/TLS bleiben offen.
Finales Gesamtgate und PC/HA-Endhashes stehen im privaten Blockcheckpoint.

## 11.10.2026 - Authentifizierter Installer mit Store-/Container-Rueckweg

Der lokal provisionierte InstallerLifecycle verbindet restricted_installer,
host_lifecycle, den festen Dockeradapter und den echten Generationsspeicher.
Activate fuehrt jetzt bei konfigurierter Runtimekopplung zuerst Wartung und
bestaetigten Containerstopp aus, danach Paketaktivierung, Start und Health.
Das Ergebnis ready_paused bleibt gesperrt. Die getrennten Aktionen rollback
und resume beziehen sich auf die urspruengliche Aktivierungs-ID, brauchen
recover-Berechtigung und denselben Principal. Offene/pausierte Wechsel sperren
weitere Installationen. Wiederholung einer bestaetigten Aktion loest sie nicht
nochmals aus; unklarer Resume-Ausgang bleibt explizite Reconciliation.

Storetransaktionen sind an die Aktivierungs-ID und erwartete Generation
gebunden. restore_committed_generation prueft Generationen und Stillstand,
schreibt restoring vor dem Pointerwechsel und restored nach Readback.
Der Rueckweg funktioniert auch nach bereits abgeschlossenem Paketwechsel,
fehlgeschlagenem Containerstart, Orchestratorneustart oder verlorenem
Schreibnachweis. Die alte Generation bleibt erhalten. Ein fremder Vorgang,
abweichende Bindung oder fehlender Stillstandsnachweis blockiert den Rueckweg.

16 neue Integrationstests verbinden Authentifizierung, Store, Lifecycle,
konkreten Adapter und synthetischen Dockerdaemon. Windows zusammen64PASS,
20LinuxSkips,12Untertests; Linux84PASS ohneSkips, inklusive echtem temporaerem
Unix-Socket-Ablauf und falscherLane. Kein Docker-/Engine-/Produktivdienststart.
Installer-/Lifecycle-/Store-Sperren liegen in getrennten Steuerverzeichnissen.

Noch offen: Hostprovisionierung/Erstbootstrap ohne Vorgaenger, HA-Setup und
serverseitige Secretuebernahme, reale Installation/Upgrade/Restore/TLS sowie
freigegebene Enginepakete. Der vorhandene filesystem-only Installerpfad ist
kein Containerinstallationsnachweis. container_deploy_ready bleibt false.
Endgate, PC/HA-SHAs, Originalbackups und trockene Rueckwege im privaten Checkpoint.

### Lokale Provisionierung und Remotevertrag

Installer(..., runtime=InstallerLifecycle(...)) aktiviert die Kopplung nur aus
vertrauenswuerdiger lokaler Konfiguration. Weder Request noch HA duerfen Driver,
Callbacks, Image-/Composebindung oder Dateipfade liefern. Der bestehende
filesystem-only Aufruf ohne runtime bleibt separat verfuegbar.

rollback/resume haben genau die Felder protocol=1, operation und target mit der
urspruenglichen 32Hex-Aktivierungs-ID. Sie erzeugen keine zweite Transaktions-ID.
Der vorhandene Lifecycle-Beleg serialisiert und korreliert die Aktion. Beide
laufen ausschliesslich auf der begrenzten mutation.sock-Lane; status bleibt auf
control.sock. Verbindungsverlust liefert outcome=unknown plus urspruengliche
request_id. Es gibt keinen automatischen Retry und keinen behaupteten Abbruch.

Status ist ein gespeicherter Beleg, keine Live-Gesundheitspruefung. ready_paused,
restored_paused und complete sind getrennt. recover/adopt/abort darf eine
Runtimeaktivierung nicht als blossen Dateizeigerwechsel quittieren. Ein
pausierter Vorgang muss ueber rollback/resume fortgesetzt werden; nach unklarem
Resume bleibt ein gesonderter lokaler Abgleich erforderlich.

## Erstinstallationsbeobachtung vor dem Hostbootstrap

`DockerHostAdapter.installation_state()` liest das feste Compose-Projekt auch
ohne ACTIVE-Datei oder vorhandene Generation. Es startet keine Container und
veraendert weder Dateien noch Wartungsmarker. Ergebnisse: `empty`, `running`
oder `stopped`, jeweils mit `installation_permitted=false`. Ein vorhandenes
Paar wird gegen Image, Generation, Mounts und Isolation geprueft; dies ersetzt
keinen API-/Worker-Healthcheck.

Nur ein wirklich leeres Projekt zusammen mit fehlender ACTIVE-Datei ergibt
`empty`. Ein Paar ohne ACTIVE, ACTIVE ohne Paar, Teilbestaende, fremde
Projektservices (auch zurueckgebliebene Init-Container), doppelte IDs/Services
und fehlerhafte Daemonantworten erfordern Klaerung. Keine Fehler-zu-leer-
Umwandlung. ACTIVE wird begrenzt und descriptorbasiert gelesen; doppelte
JSON-Felder, falsche Typen, Links und Spezialdateien werden abgewiesen.
Inventar und ACTIVE werden am Ende erneut verglichen.

Diese Momentaufnahme ist KEINE dauerhafte Erstinstallationsfreigabe: Ein
geloeschter Bestand kann ebenfalls leer aussehen. Der kommende Hostbootstrap
muss unter seinem Mutationslock VolumeGuard, Installer-/Lifecycle-/Store-
Journale, Zugangsdaten, Image und Dateninitialisierung pruefen und den Bestand
unmittelbar vor der Operation erneut beobachten. Das API-/Worker-Paar kann
nach einer Beobachtung erneut wechseln. Vorhandene Initialisierungscontainer
werden weder automatisch entfernt noch als leer ignoriert.

Synthetischer Nachweis: 15 neue Faelle; zusammen mit Adapter-, Lifecycle- und
Installerkopplungstests Windows 70 bestanden/5 POSIX-Skips/55 Untertests,
Linux 75 bestanden ohne Skips. Unter Linux echte temporaere Symlinks/FIFO,
Prozessgrenzen und Unixsockets; Dockerdaemon weiterhin synthetisch.
Dauerhafte Erstinstallation, sichere lokale Provisionierung und HA-Flow
bleiben offen. Keine Deploymentfreigabe.

## Erste Dateninitialisierung mit kanonischer Wartungssperre

Der lokale Bootstrap legt zuerst sein dauerhaftes requestgebundenes Journal an.
Danach ruft er ausschliesslich den festen Compose-Einmaldienst `data-init` mit
`run --rm --no-deps -T` auf und uebergibt dessen 32-stellige Anfrage-ID ueber
die fest definierte Umgebungsvariable. Dieser isolierte Dienst initialisiert
das persistente Datenlayout und setzt anschliessend mit der bereits im
Buildkontext geprueften kanonischen `JobControl.begin_maintenance` atomar
`container-maintenance.json`. Die Queue bleibt erhalten; ein vorhandener
aktiver oder ungeklaerter Auftrag blockiert. Derselbe Request darf nach
verlorener Antwort idempotent fortgesetzt werden; ein fremder Besitzer wird
abgewiesen.

Erst nach bestaetigtem Marker-Readback darf der Bootstrap den getrennten
Compose-Aufruf zum Start von API und Worker beginnen. `data-init` ist ein
Einmalcontainer ohne Netzwerk, ohne Portfreigabe und ohne Abhaengigkeitsstart;
der Adapter erhaelt nur seinen festen Serviceaufruf und eine validierte
Anfrage-ID, keine Caller-Befehle oder -Pfade. Der Marker bleibt bis zu einer
eigenen, authentifizierten Health-/Resume-Transaktion bestehen.

Dies ist nur der Wartungsbarrieren-Schritt, kein kompletter Hostbootstrap.
Das dauerhafte Journal vor der Operation, gespeicherte Store-ID, VolumeGuard,
Kandidatgeneration/Images, Helper-Containernachweis, erste ACTIVE-Aktivierung,
Rollback ohne vorherige Generation sowie HA-Konfiguration/TLS muessen noch
gemeinsam end-to-end implementiert und abgenommen werden. Weder der Helper
noch dieses Quellgate startet einen echten Container.

## 11.10.2026 - Dauerhafte Erstinstallation und Rueckweg zu fehlendem ACTIVE

Der Hostbootstrap besitzt jetzt ein eigenes privates Journal ausserhalb des
Datenvolumens und des Engine-Stores. Die Transaktion bindet die 32-stellige
Request-ID, den SHA-256-Principal, die Store-ID sowie Generation, Image,
Compose-Datei und Volume-Beleg. Vor jeder Mutation werden Volume, Store,
leerer Dockerbestand und fehlendes ACTIVE erneut geprueft. Erst danach wird
der feste netzlose data-init-Dienst ausgefuehrt, der kanonische
Wartungsmarker gelesen, die erste Generation aktiviert und das feste
API-/Worker-Paar gestartet. Der erfolgreiche Zustand bleibt ready_paused;
ein getrenntes, principalgebundenes Resume loest die Wartung erst nach
erneutem TLS-/Worker-/Containeridentitaetsnachweis.

Der Erstinstallations-Rueckweg akzeptiert ausschliesslich die eigene
Transaktion ohne Vorgaengergeneration. Er stoppt und entfernt nur das frisch
verifizierte Containerpaar, entfernt danach atomar ausschliesslich ACTIVE,
behaelt Generationen und Nutzerdaten und loest den Wartungsmarker ueber den
festen netzlosen maintenance-clear-Dienst. Verlorene Antworten nach
Aktivierung, Containerstart, ACTIVE-Unlink oder Resume bleiben anhand der
dauerhaften Phasen wiederaufnehmbar. Ein fremder Principal, Store, Request,
Containerbestand oder Runtime-Binding wird abgewiesen.

Die zuvor doppelt definierten Hostadapter-Testmethoden und der doppelte
FakeRunner-Zweig sind konsolidiert. Gezielte Windows-Pruefung: 148 bestanden,
11 plattformbedingte Skips und 44 Untertests. Die Tests sind synthetisch und
starten keinen Dockerdaemon, keine Engine und keinen Produktivdienst.
Echte Hostinstallation, Engine-Downloads/Lizenzen, TLS, HA-Einrichtungsflow,
Upgrade/Restore und Pilot bleiben eigene Abnahmen; container_deploy_ready
bleibt false.
## W45: Gegenseitige Ausschliessung nativer und Docker-Laufzeit

Der vorhandene Paralleltest ist ein temporaerer Test-/Uebergangszustand. Auf
sauberen Zielsystemen ist Docker Compose der einzige Slicerbetrieb; der Installer
darf keinen zweiten nativen oder Dockerbetrieb starten. Vor jeder Installation
muss der Hostbestand beider Laufzeittypen geprueft werden. Der native Startpfad
muss Docker ebenfalls erkennen und ablehnen, oder im sauberen Zielsystem fehlen.

Die Gegensperre ist ein offener Implementierungs- und Abnahmepunkt, kein durch
den synthetischen Dockeradapter belegter Schutz. Der Testvertrag muss sauberen
Host, nativen Bestand, Dockerbestand sowie den temporaeren isolierten Mischtest
getrennt pruefen. Keine automatische Migration, Entfernung oder Datenbewegung
bei erkanntem Altbestand; ein solcher Befund blockiert die Neuinstallation.

## 13.10.2026 - Clean-Host-Gegensperre vor Erstinstallation

Der Erstinstallationskern akzeptiert keinen impliziten leeren Docker-
Projektbestand mehr als alleinige Freigabe. Ein vertrauenswuerdig lokal
provisionierter `verify_exclusive_host`-Adapter ist Pflicht und wird vor
Journal-/Runtimemutation sowie erneut nach der Wartungsbarriere geprueft.
Nur `True` ist zulaessig. Ein negativer oder unklarer Nachweis blockiert.

Der zugehoerige Linux-Preflight ist read-only und erkennt bekannte native
Units, Dateien, Prozesse und Slicer-Container. Er fuehrt keine Bereinigung
durch. Die Gegensperre im alten nativen Startpfad ist fuer den neuen sauberen
Testserver nicht erforderlich, weil dort kein nativer Pfad ausgeliefert wird;
eine spaetere Aenderung des vorhandenen Live-Nativdienstes ist ausdruecklich
nicht Bestandteil dieses Schritts. Echte Linux-/Race-/systemd-/Docker-Abnahme
bleibt offen.
