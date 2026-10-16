# Sauberer Linux-Testserver – Vorbereitung und Abnahme

Stand: 13.10.2026. Dieses Dokument bereitet den separaten Arbeitsplatz-Testserver
vor. Es ist keine Anweisung zur Änderung des aktuellen Live-Systems.

## Verbindliche Trennung

- Das aktuelle Live-System behält ausschließlich seinen vorhandenen nativen
  Slicer. Dort wird kein Docker-Compose-Test gestartet.
- Der neue Testserver wird als isolierte Laborumgebung mit Home Assistant
  Supervisor und dem Slicer ausschließlich in Docker Compose aufgebaut.
- Auf dem neuen Testserver darf kein nativer Slicer installiert, aktiviert oder
  aus einem Altbestand übernommen werden.
- Die langfristige HAOS-Migration ist nicht Bestandteil dieses Tests.
- Ein erkannter Altbestand wird nur gemeldet. Der Preflight stoppt, deaktiviert,
  löscht oder migriert nichts.

## Reihenfolge vor dem Testserver

Der letzte frische Testserverlauf ist Meilenstein V **nach** dem vollständigen
Release R. Zuerst alle aktiven Funktionen, unterstützte Hostintegration,
konkreten Enginepakete, Quellen-/Noticepflichten, Installationspakete,
Dokumentation und Veröffentlichungen abschließen. Nicht nur einen GitHub-
Quellkandidaten bereitstellen. Danach den unveränderten veröffentlichten Stand
mit Commit, Paket-/Image-/Dateiprüfsummen und genauer CI am Ziel prüfen.

Der [Release-Status](RELEASE_STATUS.md) und die [Abnahmematrix](wiki/Release-Abnahme.md)
beschreiben die vollständige Reihenfolge. Es werden keine unveröffentlichten
Hilfsdateien nachgeschoben. Secrets, private Backups und interne Kontinuitätsdaten
gehören nicht in die öffentliche Lieferung. Live-Migration bleibt separat.

## Erzeugtes Testserverpaket

Der kanonische PC-Quellstand erzeugt das Paket ausschließlich mit:

    python Slicer-Server/prepare_test_server_package.py --output ../ultimate-slicer-testserver-package

Den Befehl im Repositoryroot ausfuehren. Das relative Ausgabeziel liegt als
Geschwisterverzeichnis ausserhalb des Repositorys und funktioniert auf Windows
und Linux. Der Name ist ein Beispiel; kein bestehendes Ziel wiederverwenden.

Das neue Ziel muss fehlen und außerhalb des Repositorys liegen. Der Paketbauer
verwendet nur eine feste Allowlist. Engine-Binärdateien, API-Secret,
TLS-Schlüssel, Laufzeitdaten, Jobs, Profile des Benutzers und private
Standortkonfigurationen sind ausgeschlossen.

Das Ergebnis enthält genau:

- "ultimate-slicer-testserver.tar.gz"
- "verify_test_server_package.py"
- "SHA256SUMS"

Das Archiv besitzt normalisierte Tar-/Gzip-Metadaten, feste Dateimodi und
sortierte Einträge. Sein Manifest bindet Pfad, Größe, Modus und SHA-256 jeder
Datei. "container_deploy_ready", "engine_included" und
"secret_files_included" bleiben "false".

## Übertragung und Offline-Verifikation

Den gesamten Paketordner manuell auf den MCP-freien Linux-Testserver
übertragen. Dort zuerst nur im übertragenen Paketordner ausführen:

    sha256sum -c SHA256SUMS
    python3 verify_test_server_package.py --package-dir .

Beide Prüfungen müssen erfolgreich sein. Danach in ein noch nicht vorhandenes
privates Ziel extrahieren:

    python3 verify_test_server_package.py --package-dir . --extract /srv/ultimate-slicer-testpackage

Der Verifier akzeptiert ausschließlich reguläre Dateien und Verzeichnisse unter
einer festen Archivwurzel. Links, Geräte, absolute Pfade, Traversal,
Dubletten, Zusatzdateien, falsche Modi, Größen oder Hashes werden abgewiesen.
Das Extraktionsziel wird nie überschrieben.

## Read-only Clean-Host-Preflight

Erst nach vollständiger Paketprüfung:

    cd /srv/ultimate-slicer-testpackage
    python3 clean_host_preflight.py

Geprüft werden:

1. bekannte native systemd-Units,
2. feste native Installationsmarker,
3. laufende bekannte native Slicer-Prozesse,
4. vorhandene bekannte Slicer-Container, auch aus einem anderen Compose-Projekt.

Erwartet ist Exitcode 0 und "ok": true. Jede unvollständige Inventur oder
jeder gefundene Slicerbestand blockiert. Der Preflight gibt nur Status und
Anzahlen aus und verändert nichts.

## Compose vor dem ersten Start

Im extrahierten Paket liegt unter "context/" der bereits hashgebundene
Docker-Buildkontext. Vor einem Build erneut prüfen:

    python3 context/container_check.py check

Für den Build wird ein konkret freigegebener offizieller Python-Basisdigest
benötigt. Keine Tag-only- oder Latest-Referenz verwenden:

    docker build --build-arg PYTHON_BASE="$PYTHON_BASE" --tag ultimate-slicer-server-check context

Die lokale unveränderliche Image-ID erfassen. Danach neue private Testpfade für
Daten, Engine, Profile, Token und TLS anlegen; das Secret und der private
TLS-Schlüssel werden ausschließlich auf dem Testserver erzeugt und niemals in
Paket, Ausgabe oder Rückmeldung kopiert. Compose zunächst nur validieren:

    export SLICER_IMAGE='sha256:<lokal-verifizierte-image-id>'
    export SLICER_DATA='/srv/ultimate-slicer-test/data'
    export SLICER_ENGINE='/srv/ultimate-slicer-test/engine'
    export SLICER_PROFILES='/srv/ultimate-slicer-test/profiles'
    export SLICER_TOKEN='/srv/ultimate-slicer-test/api-token'
    export SLICER_TLS='/srv/ultimate-slicer-test/tls'
    export SLICER_BIND='127.0.0.1'
    export SLICER_PORT='8099'
    docker compose -f compose.candidate.yaml config --quiet

Fehlende Variablen, Bindpfade oder ein nicht lokales Image müssen die Prüfung
beenden. Es gibt keinen automatischen Pull und keinen Docker-Socket im Dienst.

## Abnahmefolge

1. Hostidentität, Betriebssystem, Architektur, Zeit und freien Speicher erfassen.
2. Home-Assistant-/Supervisor-Zustand ausschließlich lesend erfassen.
3. Paket, Sidecar und internes Manifest vollständig vergleichen.
4. Clean-Host-Preflight ausführen und bereinigtes Ergebnis sichern.
5. Compose-Konfiguration validieren, noch ohne Start.
6. Erstinstallation mit API/Worker im Wartungszustand ausführen.
7. Containeridentität, Image-ID, Mounts, Benutzer 65532, Read-only-Root,
   CapDrop, NoNewPrivileges, Prozess- und Netzwerkisolation prüfen.
8. Authentifizierten TLS-Healthcheck ohne Slice ausführen.
9. Explizites Resume prüfen.
10. Containerneustart und Hostneustart mit Persistenzprüfung.
11. Synthetischen Teilstart, Upgrade, Rollback sowie Backup/Restore getrennt
    prüfen.
12. Erst nach vollständigem Readback die Abnahme dokumentieren.

## Rückweg und Datenerhalt

Vor jeder Mutation werden Image-ID, Compose-SHA, Mountpfade, Rechte und
Datenhashes festgehalten. Vor Upgrade oder Restore stehen API und Worker
nachweislich still und der Wartungsmarker gehört zur aktuellen Anfrage.

"docker compose down" entfernt im Kandidaten keine Bind-Mount-Daten. Daten,
Profile, Token und TLS bleiben getrennt. Ein Rückweg stellt zuerst das zum
Datenstand passende alte Image und nur bei belegtem Bedarf die dazugehörige
Sicherung in einen neuen privaten Pfad wieder her. Der ursprüngliche Datenpfad
wird nicht überschrieben oder automatisch gelöscht. Resume erfolgt erst nach
erneuter Container-, TLS-, Worker-, Mount- und Persistenzprüfung.

Bei einem Teilstart, unklaren Timeout, fremden Wartungsmarker oder verlorenen
Schreibnachweis keine Mutation wiederholen und keine Marker löschen. Zustand,
Logs und Hashes bereinigt sichern; anschließend den dokumentierten
Reconciliation-/Rollbackpfad verwenden.

## Stop-Kriterien

Sofortiger Abbruch bei nativem Slicerbestand, unbekanntem Slicer-Container,
abweichenden Hashes, unklarer Engineherkunft, fehlender TLS-Authentifizierung,
unsicheren Mounts/Rechten, Teilstart, fremdem Wartungsmarker oder fehlendem
Rollbacknachweis.

Keine echten Slices, Uploads, Druckstarts, Druckerbewegungen, Heiz- oder
Materialkommandos. "container_deploy_ready" bleibt bis zum vollständigen
Linux-, Engine-, TLS-, Upgrade- und Restore-Nachweis "false".

## Secretfreier Ergebnisvertrag

Das Paket enthält `linux_test_evidence.py`. Der Verifier nimmt keine Logs,
Kommandos, Pfade, Zertifikate, Hostnamen oder Zugangsdaten an. Er akzeptiert
nur begrenzte boolesche Werte, Zähler und SHA-256-Belege für zehn geordnete
Phasen: Paket, Clean Host, Compose, Runtime, TLS, Persistenz, Upgrade,
Rollback, Backup/Restore und Supervisor-/HA-Grenze.

Nach erfolgreicher Paketverifikation zunächst eine neue, an dieses Paket
gebundene Vorlage erzeugen. Die beiden Hashes stammen aus der bereits lokal
verifizierten Paket- und Manifestausgabe:

    python3 linux_test_evidence.py \
      --write-template /srv/ultimate-slicer-test/evidence.json \
      --expected-archive-sha256 '<ARCHIV-SHA256>' \
      --expected-manifest-sha256 '<MANIFEST-SHA256>' \
      --host-fingerprint-sha256 '<HOST-FINGERPRINT-SHA256>' \
      --os-id '<OS-ID>' \
      --os-version '<OS-VERSION>' \
      --architecture '<ARCHITEKTUR>' \
      --supervisor-present 'true'

Die Vorlage wird erst auf dem tatsaechlichen Zielhost nach Erfassung der
konkreten Hostidentitaet erzeugt. Sie legt eine zufaellige, nicht geheime
`run_sha256` fuer genau diesen Testlauf an und startet vollstaendig mit
`not_run`. Jede Phase wird erst nach dem jeweiligen Readback auf `passed`
gesetzt; danach wird `evidence_sha256` aus Schema, Testsitzung, Paket- und
Manifest-SHA, Hostidentitaet sowie Phasen-ID, Status und `checks` neu
berechnet. Dadurch werden unveraenderte Phasen aus einem anderen Paket,
Hostlauf oder einer anderen Testsitzung abgewiesen. Eine Statusaenderung ohne
neuen Hash wird ebenfalls abgewiesen.

Die Evidence-Datei wird nicht direkt bearbeitet. Fuer jede Phase das bereits
vorhandene checks-Objekt dieser Phase in eine eigene kleine JSON-Datei
kopieren, ausschliesslich mit den gemessenen booleschen Werten, Zaehlern und
SHA-256-Belegen fuellen und dann genau die naechste Phase in eine neue
Evidence-Datei fortschreiben. Beispiel fuer die erste Phase:

    python3 linux_test_evidence.py \
      --advance-input /srv/ultimate-slicer-test/evidence-00.json \
      --write-output /srv/ultimate-slicer-test/evidence-01.json \
      --phase package \
      --status passed \
      --checks-json /srv/ultimate-slicer-test/package-checks.json \
      --expected-archive-sha256 '<ARCHIV-SHA256>' \
      --expected-manifest-sha256 '<MANIFEST-SHA256>'

Das Ausgabeziel darf noch nicht existieren. Die Eingabedatei bleibt
byteunveraendert. Der Fortschreibpfad akzeptiert nur die erste not_run-Phase,
wenn alle vorherigen Phasen passed sind, prueft das exakte Checkschema,
berechnet den gebundenen Phasenhash selbst und validiert das gesamte Ergebnis
vor dem Schreiben erneut. blocked ist als Stopnachweis zulaessig; danach kann
keine spaetere Phase fortgeschrieben werden. Direkte Bearbeitung, Ueberspringen,
Ueberschreiben und Fortsetzen nach einem Block werden fail closed abgewiesen.
Bestandene Phasen muessen eine lueckenlose Reihenfolge bilden. Nach `blocked`
oder `not_run` duerfen nur noch `not_run`-Phasen folgen. Bereits eine
unvollstaendige Rueckmeldung verlangt einen nichtleeren Hostfingerprint,
konkrete OS-/Versions-/Architekturwerte und eine konsistente
Supervisor-Angabe. `blocked` dokumentiert einen echten Stop-Zustand,
`not_run` eine noch nicht ausgefuehrte Phase.

Abschließend offline prüfen:

    python3 linux_test_evidence.py \
      --input /srv/ultimate-slicer-test/evidence.json \
      --expected-archive-sha256 '<ARCHIV-SHA256>' \
      --expected-manifest-sha256 '<MANIFEST-SHA256>'

Exitcode 0 bedeutet vollständige Testserverabnahme aller zehn Phasen.
Exitcode 2 bedeutet gültigen, aber unvollständigen oder blockierten Nachweis.
Exitcode 1 bedeutet ungültiges beziehungsweise unsicheres Ergebnis. Auch bei
vollständiger Testserverabnahme bleibt `container_deploy_ready=false`, weil
der Systemprüfer keine Engine-/Lizenz-, Release- oder Produktivfreigabe erteilt.
R muss bereits zuvor separat belegt sein; V bestätigt die echte Zielinstallation.
Ein produktiver Pilot oder eine Migration wird nicht automatisch gestartet.

Nur die abschließende kompakte JSON-Ausgabe und die Evidence-Datei dürfen
zurückgegeben werden. Keine Rohlogs, Token, Secrets, privaten Schlüssel,
Authorization-Header, Cookies, Hostnamen oder privaten absoluten Pfade
übermitteln. Der Verifier weist entsprechende Feldnamen, Schlüsselmaterial,
doppelte JSON-Felder, fremde Paket-Hashes und nachträglich veränderte
Phasenbelege ab.

## Phasenuebergreifende Kontinuitaet

Schema 5 bindet nicht nur jeden Einzelbeleg an Lauf, Paket und Host. Der
initiale lokale Image-SHA muss in Compose, API-/Worker-Runtime und als altes
Upgrade-Image identisch sein; der Rollback muss genau diesen SHA wiederherstellen.
Daten- und Profil-Digests bilden eine durchgehende Kette von Persistenz ueber
Upgrade und Rollback bis zur Quelle des Restore. Innerhalb jeder Phase muessen
Vorher-/Nachher- beziehungsweise Quellen-/Restore-Digests identisch und ungleich
dem Null-Digest sein. Einzeln plausible, aber untereinander widerspruechliche
Phasen werden damit abgewiesen.
Jede Phase enthaelt zusaetzlich previous_evidence_sha256. Die erste Phase
verweist auf run_sha256, jede folgende Phase exakt auf evidence_sha256 ihres
unmittelbaren Vorgaengers. Der eigene Phasenhash umfasst diesen
Vorgaengerverweis. Der atomare Fortschreibpfad berechnet deshalb beim
Fortschritt auch die noch nicht ausgefuehrte Restkette neu. Ein formal
gueltiger Phasenbeleg aus einem parallelen Zweig desselben Paket-, Host- und
Testlaufs kann nicht mehr eingesetzt werden, ohne dass die naechste Phase die
abweichende Kette fail closed meldet.
