# Ultimate Slicer Server einrichten und prüfen

Diese Anleitung führt vom passenden Einrichtungsweg zu den dokumentierten Vorprüfungen. Sie richtet sich an Administratoren, die einen vorhandenen Slicer mit Home Assistant verbinden oder den veröffentlichten Quellstand für eine spätere Bereitstellung prüfen möchten. Für den laufenden Betrieb ergänzen [Handbuch](HANDBUCH.md), [Laufzeitkonfiguration](RUNTIME_INSTALLATION.md) und [Betrieb, Updates und Wiederherstellung](OPERATIONS.md) diese Seite.

## 1. Lieferstatus vor Beginn verstehen

**Ein vollständiger Produktrelease ist noch offen (`FullRelease=false`).** API, Worker, Containerwerkzeuge und native Paketwerkzeuge sind als Quellcode veröffentlicht. Der aktuelle Stand liefert jedoch keinen freigegebenen Runtime-Download, keinen freigegebenen Image-Digest und keine freigegebene Supervisor-Paketreferenz. Das Prüfimage enthält keine Engines; damit ist allein kein echtes Slicing möglich.

Der [Engine-Katalog](engine_catalog.json) enthält `releases=[]`. Bambu Studio, PrusaSlicer und CuraEngine stehen jeweils unter `pending`. Für den nativen Installationsweg gilt `native_deploy_ready=false`; der Containerkandidat bleibt ebenfalls ohne Betriebsfreigabe. Die Installationssperren werden durch die folgenden Prüfungen oder diese Dokumentation nicht aufgehoben.

Linux/amd64 ist der beschriebene Zielumfang. Andere Architekturen benötigen passende Engines, Bibliotheken und eigene reale Nachweise. Insbesondere ist keine allgemeine ARM-Unterstützung zugesagt. Die Linux-Neuinstallation bleibt der letzte Verifikationstest, nachdem die vorausgehende Produktarbeit abgeschlossen ist. Ein grünes Quellgate, ein gebautes Image oder veröffentlichte Wikiseiten bestätigen keinen vollständigen Produktrelease.

## 2. Einrichtungsweg auswählen

| Ausgangslage | Passender Weg | Aktuelle Grenze |
| --- | --- | --- |
| Eigenständiger Slicer läuft bereits auf einem anderen Host | Externe HTTPS-Verbindung | TLS, Authentifizierung und API-Kompatibilität müssen passen |
| Home Assistant besitzt Supervisor und soll eine verwaltete App nutzen | Supervisor-App | Installation mangels freigegebener Paketreferenz gesperrt |
| Ein Unix-Host wurde bereits ausdrücklich für den Installer provisioniert | Geschützte Hostkopplung | Reale Hosteinrichtung und Abnahmen stehen noch aus |
| Quellcode soll ohne laufenden Dienst geprüft werden | Quell-Preflight | Kein API-Start, keine Engine und kein Slice |

Diese Wege sind getrennt. Ein Fehler im Supervisor-Pfad startet keinen Host-Installer. Ohne Supervisor bleiben Studio und externe Slicer-Verbindung grundsätzlich eigenständige Funktionen. HACS ist für die Home-Assistant-Integration vorgesehen und installiert das native Linux-Slicer-Paket nicht.

## 3. Einen vorhandenen externen HTTPS-Slicer verbinden

Benötigt werden die überprüfte HTTPS-Adresse des Servers, dessen API-Secret und ein für Home Assistant vertrauenswürdiges Zertifikat. Das Zertifikat muss zum verwendeten Hostnamen passen. Der Server muss von Home Assistant aus erreichbar sein; passende Bind-Adresse und Firewallregeln gehören zur Einrichtung des Serverhosts.

Öffne in Home Assistant **Einstellungen → Geräte & Dienste → Ultimate 3D Studio → Konfigurieren**. Hinterlege die Serveradresse und das API-Secret in den vorhandenen Verbindungsoptionen. Zugangsdaten verbleiben in Home Assistant. Übernimm die Verbindung erst, wenn Zertifikatsprüfung, Authentifizierung und API-Kompatibilität erfolgreich geprüft wurden.

Der dokumentierte Verbindungstest fragt die geschützte Info-API ab. Er installiert keine Software und führt weder einen Slice noch einen Upload oder Druckstart aus. Ein Server kann erreichbar sein, obwohl ihm eine arbeitsfähige Engine fehlt: `GET /api/v1/health` ist öffentlich und kann ohne Engine `degraded` melden; `GET /api/v1/info` benötigt `Authorization: Bearer <Secret>`. Ein HTTP-Erfolg allein bestätigt keine vollständige Slicing-Funktion.

Für einen entfernten Host wird die Zertifikatsprüfung beibehalten. Beim nativen Dienst ist eine Bind-Adresse außerhalb von Loopback ohne vollständige gültige TLS-Konfiguration gesperrt. Alternativ ist laut nativer Dokumentation eine TLS-Terminierung durch einen Reverse-Proxy möglich, während der Slicer an `127.0.0.1` gebunden bleibt. Die konkrete Cross-Host-TLS-Abnahme bleibt ein offener Nachweis.

## 4. Supervisor-App: Voraussetzungen und Vorgangsstatus

Der App-Pfad verwendet den von Home Assistant bereitgestellten Supervisor-Client. Zusätzliche Core-Mounts, Shellzugang oder ein eingebundener Docker-Socket sind dafür nicht vorgesehen. Vorgänge benötigen einen aktiven Administrator; Repository, App-Slug und Version müssen mit der serverseitig freigegebenen Paketreferenz übereinstimmen.

Aktuell fehlt diese Referenz. Daher darf weder das Prüfimage ohne Engines noch ein selbst gewählter Paketname als Ersatz dienen. Der Dialog kann eine bestätigte Installation erst anbieten, wenn die passende freigegebene Referenz vorliegt. Eine Installation und der Start einer App sind getrennte Vorgänge; der beschriebene Adapter startet, aktualisiert oder entfernt keine App.

Bei einem unterbrochenen Vorgang bleibt eine lokale `pending`-Absicht erhalten. Ein Timeout oder geschlossener Dialog ist kein Anlass, die Installation erneut zu senden. Ist die erwartete App später vollständig installiert und gestoppt vorhanden, kann ein Administrator den dokumentierten Bestandsabgleich bestätigen. Dessen Ergebnis `reconciled_stopped` bestätigt den abgeglichenen gestoppten Bestand; der Ausgang der ursprünglichen Anfrage bleibt unbekannt. Ein bereits laufender Container erscheint als `running_unverified`. Aus diesem Zustand werden keine Zugangsdaten und keine funktionierende Verbindung abgeleitet.

Details zur Prüfung der App, Version, Schutzbedingungen und Supervisor-Jobs stehen in [Home-Assistant-Einrichtung](SUPERVISOR_APP_SETUP.md).

## 5. Bereits provisionierten Unix-Host koppeln

Dieser Weg setzt eine ausdrücklich vorbereitete Hostumgebung voraus. Die lokale Tokenregistrierung stellt keine automatische Host-Erkennung, HTTP-Route oder allgemeine Shell bereit. Sie gehört in eine geschützte Installer-Steuerablage außerhalb der Engine-, Profil- und Datenmounts; Worker und Browser erhalten darauf keinen Zugriff.

Die Implementierung beschreibt eine gebundene lokale Installations-ID, Principals mit festgelegten Rechten und geschützte Tokenübergabe. Eine lokale ID allein bestätigt jedoch nicht die Identität eines entfernten TLS-Hosts. Produktive Provisionierung, Rechte, gesicherter Transport und Wiederherstellung benötigen ihre eigenen Nachweise. Deshalb enthält diese Anleitung keinen vereinfachten Kopplungs- oder Installationsbefehl. Der maßgebliche Vertrag steht in [Hostkopplung](HOST_PAIRING.md) und [Installer-Transport](INSTALLER_TRANSPORT.md).

## 6. Quell-Preflight ohne Dienstinstallation

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

## 7. Optionales Prüfimage bauen

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

## 8. Containerkandidat und Daten vorbereiten

Die bestehende [Laufzeitdokumentation](RUNTIME_INSTALLATION.md) beschreibt einen Kandidaten mit API, Worker und Telemetrie. Der Worker läuft im dokumentierten Containerpfad ohne Netzwerkzugriff; Programmcode und Engine werden nur lesbar eingebunden. Beide Dienste laufen ohne Root, zusätzliche Capabilities und Docker-Socket. Der gemeinsame PID-Namensraum und dieselbe UID sind dennoch keine vollständige Sicherheitsgrenze zwischen gleichberechtigten Prozessen.

Für einen späteren isolierten Lauf werden getrennte Pfade benötigt: `data/` für neue persistente Daten, `engine/` für den vollständigen Enginebestand, `tls/` für Zertifikat und Schlüssel sowie eine eigene Datei `api-token`. Die dokumentierte UID/GID lautet `65532:65532`. Der Token benötigt mindestens 32 zufällige druckbare ASCII-Zeichen und eingeschränkte Dateirechte. Der Engine-Hostpfad ist die gemeinsame Wurzel der drei Familienverzeichnisse, kein direktes Bambu-Entpackverzeichnis.

Ein leerer Enginepfad kann einen Leerlauftest ermöglichen, aber keinen Slice. Fehlende Bind-Mounts werden nicht automatisch angelegt. Eine Standardbindung an Loopback macht den Dienst ausschließlich auf dem Docker-Host erreichbar. Der konkrete Startablauf bleibt in der Laufzeitdokumentation; vor einer freigegebenen Bereitstellung fehlen insbesondere Engine-, Lizenz-, HA-Verbindungs-, Neuinstallations- und Restore-Nachweise.

## 9. Native Pakete nur innerhalb ihres Prüfvertrags

Die nativen Werkzeuge liegen in [`packages/ultimate-slicer-server/`](../packages/ultimate-slicer-server/README.md). Der Installer prüft notwendige Programme, feste Systempfade und die Voraussetzungen seiner Isolation. Er installiert keine Betriebssystempakete automatisch. Aus dem Verzeichnis mit `install_native.py` lautet die dokumentierte rein lesende Hostprüfung:

```sh
python3 install_native.py --check-host
```

Ein erfolgreicher Lauf meldet `host_dependencies: ready` und `installation_performed: false`. Das bestätigt vorhandene Hostabhängigkeiten, keine vollständige Betriebsfähigkeit. Die Installation benötigt zusätzlich einen extern bestätigten Archivhash, rechtmäßig nutzbare Engine-Dateien, deren unabhängiges Manifest sowie vollständige Maschinen-, Prozess- und Filamentprofile. `native_deploy_ready=false` sperrt die Installations- und Upgradeaktionen weiterhin. Eine bestehende Installation wird nicht als Erstinstallationsziel überschrieben.

## 10. Fehler einordnen und späteren Betrieb absichern

| Zustand | Bedeutung und nächster Schritt |
| --- | --- |
| `source_digest_mismatch` | Quellbytes und Manifest passen nicht; Ursache und maßgeblichen Quellstand prüfen |
| `output_already_exists` | Neues Ausgabeziel verwenden oder den eigenen alten Kontext bewusst entfernen |
| `unexpected_context_file` | Unerlaubte Zusatzdatei im Kontext untersuchen; Secrets gehören nicht hinein |
| Health `degraded` | Erreichbarkeit kann vorhanden sein, Enginefähigkeit fehlt oder ist eingeschränkt |
| Recovery-Marker oder `*.slicing.json` | Weitere Jobs gesperrt; Dienste stoppen, Daten sichern und alten Prozess-/Jobzustand untersuchen |

Vor einem späteren Update werden aktive und wartende Jobs erfasst und persistente Daten konsistent gesichert. Zum Rückweg gehören der passende Softwarestand und die dazugehörigen Daten. API-Token, TLS-Schlüssel und Sicherungen bleiben geschützt. Ein Fehlerbericht enthält üblicherweise Version, Architektur, Image-Digest, API-Protokoll, Fehlercode und bereinigte Logauszüge. Das Entfernen eines Containers löscht persönliche Profile, Modelle und Historie nicht automatisch.

Der erste echte Slice setzt die vollständige geprüfte Runtime voraus. Seine Abnahme umfasst Engine und Profile, Ergebnisprüfung sowie kontrollierten Abbruch und Wiederanlauf. Diese Schritte bleiben von Verbindungstest, Installation und Druckstart getrennt. Die maßgeblichen Rechte stehen in [Repository-Lizenzgrenzen](REPOSITORY_NOTICES.md), [Slicer-Lizenz](LICENSE) und [Drittanbieterhinweisen](THIRD_PARTY_NOTICES.md); das Repository besitzt keine pauschale MIT-Zuordnung.
