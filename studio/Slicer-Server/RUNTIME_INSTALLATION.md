# Docker-Dienstkandidat: Laufzeit einrichten und betreiben

Ultimate Slicer Server trennt HTTP-API und Auftragsverarbeitung in eigene Compose-Dienste. Der veröffentlichte Quellstand enthält diesen Laufzeitvertrag, die Initialisierung und Diagnosewerkzeuge. **Eine vollständige freigegebene Slicer-Runtime mit Engine-Downloads ist noch nicht veröffentlicht.** Das Prüfimage allein kann keine Modelle slicen.

Diese Anleitung beschreibt den isolierten Linux/amd64-Kandidatenweg. Sie ersetzt keine Enginefreigabe und keine Betriebsabnahme. Die eigenständige Linux-Neuinstallation bleibt der letzte Verifikationsschritt. Die Grundlagen und Einrichtungswege erklärt das [Handbuch](HANDBUCH.md); die Quellprüfung und den Imagebau beschreibt der [Docker-Schnellstart](DOCKER_QUICKSTART.md).

## 1. Dienste und Verantwortlichkeiten

| Bestandteil | Aufgabe | Grenze |
| --- | --- | --- |
| `api` | HTTP-API über TLS; PID-Anchor für den zugehörigen Worker | Ein erreichbarer Dienst bestätigt keine vollständige Engine |
| `worker` | Aufträge verarbeiten und Telemetrie aktualisieren | Eigener netzloser Betrieb, genau ein Dienst-Lock |
| Dateninitialisierung | Den vorgesehenen neuen Datenbestand vorbereiten | Keine automatische Übernahme fremder Laufzeitdaten |
| Profilinitialisierung | Geprüfte Drucker-Seeddateien einmalig bereitstellen | Ersetzt keine vollständige Engine-/Profilfreigabe |
| Wartungsende | Den eigenen bestätigten Wartungszustand ausdrücklich beenden | Kein allgemeiner Reset fremder Recovery-Zustände |

Der Worker teilt für die bestehende Besitzerprüfung den PID-Namensraum der API, besitzt aber `network_mode: none`. API und Worker laufen ohne Root, zusätzliche Capabilities und Docker-Socket. Root-Dateisystem und Enginebestand sind nur lesbar.

Ein gemeinsamer PID-Namensraum und dieselbe UID sind keine Schutzgrenze gegen einen bösartigen gleichberechtigten Prozess. Separate Secret-Mounts ändern diese Eigenschaft nicht grundsätzlich. Die tatsächliche Isolation, Mountzuordnung und Hostkonfiguration gehören deshalb zur Prüfung des konkreten Betriebsstands.

## 2. Voraussetzungen

Verwende einen neuen isolierten Linux-Docker-Testpfad. Docker und Compose müssen vorhanden sein; der Quellbaum muss vollständig sein. Erzeuge den begrenzten Kontext mit `prepare_context.py` und baue das Image nach [INSTALLATION.md](INSTALLATION.md) beziehungsweise [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md).

Ein tatsächlich geprüftes Python-Basisimage mit vollständigem Digest ist erforderlich. Ein Platzhalter oder ein bewegliches Tag ist kein reproduzierbarer Nachweis. Der Bau eines Images bestätigt außerdem noch nicht die vollständige Eignung der Systempakete, Bibliotheken, Plugins und Ressourcen.

Die vorhandene native Installation wird nicht automatisch in diesen Compose-Bestand übernommen. Ein nativer Worker und ein Compose-Worker dürfen denselben Bestand nicht gleichzeitig verarbeiten. Die spätere Migration braucht einen eigenen abgestimmten Ablauf mit Sicherung und Rückweg.

Die lokale Image-ID lässt sich nach dem dokumentierten Verfahren feststellen:

~~~sh
docker image inspect --format '{{.Id}}' <lokaler-image-name>
~~~

`<lokaler-image-name>` ist durch den tatsächlich gebauten Namen zu ersetzen. Notiere die bestätigte ID zusammen mit dem Quellstand und dem verwendeten Buildnachweis.

## 3. Speicherbereiche vorbereiten

Alle Laufzeitbereiche liegen außerhalb des Repositorys. Stelle sie unter den vorgesehenen Eigentümer-, Gruppen- und Dateirechten bereit. Fehlende Bind-Mounts werden nicht automatisch als leere Verzeichnisse angelegt.

| Bereich | Inhalt und Voraussetzung |
| --- | --- |
| `data/` | Neuer persistenter Datenbereich mit den für UID/GID 65532 vorgesehenen Rechten |
| `engine/` | Vollständiger ausgewählter Engine-Stamm samt Bibliotheken und Ressourcen; nur lesbar eingebunden |
| `profiles/` | Bereits vorbereiteter dauerhafter Profilstamm; der Stamm ist nicht mit seinem Unterordner `printers/` gleichzusetzen |
| `tls/` | `server.crt` und `server.key`; der Schlüssel ist für die Laufzeitidentität lesbar, aber privat |
| `api-token` | Lokal erzeugtes zufälliges Secret mit mindestens 32 druckbaren ASCII-Zeichen |

Für die Token-Datei nennt der Kandidatenvertrag UID 65532 und Modus 0600. Auch der TLS-Schlüssel benötigt geschützte Rechte und einen für die Laufzeitidentität zugänglichen Elternpfad. Ein pauschales rekursives `chmod` oder `chown` ist kein Ersatz für den konkreten Speichervertrag.

Die Hostinitialisierung kann Daten- und Profilstämme gezielt für die Runtime-Gruppe freigeben. Details stehen in [RUNTIME_PERMISSIONS.md](RUNTIME_PERMISSIONS.md). Rootless Docker und User-Namespace-Remapping besitzen andere UID/GID-Beziehungen und benötigen eine eigene Prüfung.

Die Profilinitialisierung läuft netzlos und erhält nur ihren eigenen Profilmount schreibbar. API und Worker verwenden den Profilstamm anschließend nur lesend. Der dokumentierte Seed umfasst A1 und H2S mit 0,4-mm-Düse. Gültige Benutzerprofile bleiben bei Wiederverwendung erhalten; ein Imagewechsel überschreibt sie nicht automatisch. Siehe [PERSISTENT_PROFILES.md](PERSISTENT_PROFILES.md).

Für reine Leerlaufprüfungen darf der Engine-Stamm leer sein. Daraus entsteht ein ausdrücklich eingeschränkter Zustand. Ein solcher Lauf belegt keine Slicing-Fähigkeit.

## 4. TLS und Erreichbarkeit festlegen

Das Zertifikat muss zum später verwendeten Hostnamen passen. Home Assistant muss der ausstellenden CA vertrauen. Das Abschalten der Zertifikatsprüfung ist kein Installationsschritt.

Eine Bind-Adresse von `127.0.0.1` beschränkt die API auf den Docker-Host. Für Home Assistant auf einem anderen Host sind eine bewusst gewählte passende Bind-Adresse, eine passende Firewallregel und vertrauenswürdiges TLS erforderlich. Eine erreichbare IP allein bestätigt weder die Zertifikatsidentität noch die Authentifizierung.

Das API-Secret selbst gehört nicht in öffentliche Compose-Dateien, das Image, einen Diagnoseexport oder einen Screenshot. Die private Datei wird als Datei eingebunden; der Pfad darf in der Laufzeitkonfiguration stehen, der Secret-Inhalt nicht.

## 5. Compose konfigurieren

Die folgenden Variablen gehören zum dokumentierten Kandidatenvertrag:

| Variable | Inhalt |
| --- | --- |
| `SLICER_IMAGE` | Tatsächlich vorhandene lokale Image-ID |
| `SLICER_DATA` | Neuer dauerhafter Datenstamm |
| `SLICER_ENGINE` | Gesamter ausgewählter Engine-Stamm |
| `SLICER_PROFILES` | Vorbereiteter dauerhafter Profilstamm |
| `SLICER_TOKEN` | Pfad zur privaten Secret-Datei |
| `SLICER_TLS` | Pfad zum Zertifikatsverzeichnis |
| `SLICER_BIND` | Bewusst gewählte Bind-Adresse |
| `SLICER_PORT` | Lokaler API-Port, dokumentierter Standard 8099 |
| `SLICER_BOOTSTRAP_REQUEST_ID` | Eigene Initialisierungs-/Wartungskennung |

Die bisherige Laufzeitanleitung enthält diesen Beispielausschnitt für neue Testpfade:

~~~sh
export SLICER_IMAGE='sha256:<lokal-gepruefte-image-id>'
export SLICER_DATA='/srv/ultimate-slicer-test/data'
export SLICER_ENGINE='/srv/ultimate-slicer-test/engine'
export SLICER_TOKEN='/srv/ultimate-slicer-test/api-token'
export SLICER_TLS='/srv/ultimate-slicer-test/tls'
export SLICER_BIND='127.0.0.1'
export SLICER_PORT='8099'
~~~

Der Ausschnitt ist **keine vollständige fertige Konfiguration**: Auch Profilstamm und die eigene Bootstrap-/Wartungskennung sind anhand der tatsächlichen Compose-Datei bereitzustellen. Der Platzhalter für die Image-ID muss durch den bestätigten lokalen Wert ersetzt werden. Diese Anleitung erfindet dafür weder einen veröffentlichten Image-Digest noch einen universellen Initialisierungsschlüssel.

Nachdem sämtliche Werte und Hostpfade vorbereitet sind, dokumentiert die Quelle:

~~~sh
docker compose -f Slicer-Server/compose.candidate.yaml config --quiet
docker compose -f Slicer-Server/compose.candidate.yaml up -d
docker compose -f Slicer-Server/compose.candidate.yaml ps
~~~

Der normale Start aktiviert nur `data-init`, `profile-init`, `api` und `worker`.
Wenn `SLICER_BOOTSTRAP_REQUEST_ID` gesetzt ist, legt die Dateninitialisierung die
zugehörige Wartungssperre an und lässt sie bestehen. Bereits freigegebene
Queue-Einträge bleiben dadurch unverändert; der Worker darf sie während der
Wartung nicht übernehmen. Ein gewöhnliches `up -d` beendet diese Sperre nicht.

`pull_policy: never` verlangt ein bereits lokal vorhandenes Image. Compose lädt kein erfundenes Runtime-Paket nach. Die Quelle für die Compose-Eigenschaften ist die [offizielle Docker-Referenz](https://docs.docker.com/reference/compose-file/services/).

Das ausdrücklich eigene Wartungsende ist ein Betriebswechsel: Danach kann der normale Worker bereits freigegebene Queue-Einträge verarbeiten. Es darf deshalb nicht als harmloser lesender Verbindungstest behandelt werden.

Erst nach der bewussten Entscheidung, den vorbereiteten Bestand für die
Verarbeitung freizugeben, wird das Wartungsende als einzelner Hilfsdienst
aufgerufen. Verwende dafür die unveränderte Kennung deiner eigenen Sperre:

~~~sh
docker compose -f Slicer-Server/compose.candidate.yaml run --rm --no-deps maintenance-clear
~~~

`maintenance-clear` gehört zum Profil `maintenance` und läuft beim normalen
Start nicht mit. Der gezielte `run`-Aufruf aktiviert ausschließlich diesen
Hilfsdienst. Verwende dafür kein pauschales `up` mit aktiviertem Wartungsprofil.
Eine fehlende, ungültige oder fremde Kennung wird vom bestehenden
Wartungsvertrag vor einer Änderung abgewiesen; sie ist keine Erlaubnis zum
Löschen anderer Wartungs- oder Recovery-Markierungen. Der leere Standardwert in
der Compose-Datei hält den Hilfsdienst bei der Konfigurationsauswertung optional
und hebt diese Prüfung nicht auf.

## 6. Enginepfade und Ressourcen

`SLICER_ENGINE` wird im Container als `/engine` eingebunden. Es bezeichnet nicht direkt eine historische Bambu-Extraktionswurzel.

| Engine-ID | Programmeinstieg |
| --- | --- |
| `bambu_studio` | `/engine/bambu_studio/bin/bambu-studio` |
| `prusaslicer` | `/engine/prusaslicer/bin/prusa-slicer` |
| `curaengine` | `/engine/curaengine/bin/CuraEngine` |

Dispatcher und Telemetrie verwenden denselben lesenden Pfadvertrag. Fehlende oder nicht ausführbare Programme und verlinkte Einstiegspfade werden abgewiesen. Im Container gibt es keinen Ersatz über beliebige Programme im Host-PATH oder eine andere Enginefamilie.

Der Imagebau berücksichtigt außerdem die festen Ressourcenpfade für Prusa und Cura. Das ersetzt keine tatsächlich geladene Plugin-, ABI- oder Slicing-Prüfung. `available=true` bedeutet bei der Dateierkennung nur, dass der akzeptierte Programmeinstieg vorhanden und ausführbar ist.

Der ausgelieferte Katalog enthält weiterhin keine freigegebenen Engine-Releases. Informationen zu den vorhandenen Offlinewerkzeugen stehen in [ENGINE_DISTRIBUTION.md](ENGINE_DISTRIBUTION.md); die Pfade und Ressourcen beschreibt [ENGINE_LAYOUT.md](ENGINE_LAYOUT.md). Lizenz- und Herkunftsgrenzen bleiben eigenständig bestehen.

## 7. Zustand prüfen

`GET /api/v1/health` ist öffentlich. Ohne Engine kann es `degraded` melden. `GET /api/v1/info` verlangt `Authorization: Bearer <Secret>`. Eine Health-Antwort beweist Erreichbarkeit, keine korrekte Authentifizierung und keine vollständige Engine.

Der dokumentierte Worker-Healthcheck berücksichtigt Herzschlag, Prozessidentität und Recovery-Sperre:

~~~sh
docker compose -f Slicer-Server/compose.candidate.yaml logs --tail 100 api worker
docker compose -f Slicer-Server/compose.candidate.yaml exec worker \
  python3 /opt/ultimate-slicer-server/container_service.py worker-check
~~~

Logausgaben und generierte Daten können private Informationen enthalten. Die API-Konfiguration mit Secret liegt im privaten Container-tmpfs; das Image enthält keine Standortkonfiguration und keinen Token.

Die vorhandene Testdokumentation beschreibt Linux/amd64-Prüfungen für TLS/Auth, Leerlauf, kontrollierte Stopps, doppelte Worker, Anchor-Ausfall und erhaltene verwaiste Jobmarker. Diese dokumentierten Prüfungen ersetzen keine reale Engine-, HA-Verbindungs- oder Bestandsmigrationsabnahme. Details stehen in [CONTAINER_TESTING.md](CONTAINER_TESTING.md).

## 8. Stoppen, Neustarten und Wiederherstellen

~~~sh
docker compose -f Slicer-Server/compose.candidate.yaml stop
docker compose -f Slicer-Server/compose.candidate.yaml down
docker compose -f Slicer-Server/compose.candidate.yaml up -d
~~~

Compose stoppt den abhängigen Worker vor dem API-Anchor. Bei einem Imagewechsel oder Anchor-Neustart beide Dienste gemeinsam zum passenden Stand neu erzeugen. Der Worker darf nicht am alten PID-Namensraum weiterbetrieben werden.

Automatische Restart-Schleifen sind im Kandidaten ausgeschaltet. Ein ungesunder Dienst wird nicht automatisch repariert. Vor einem bewussten Neustart werden deshalb Ursache, Datenbestand und erhaltene Zustandsmarkierungen geprüft.

`run/container-recovery.json` oder vorhandene `*.slicing.json` blockieren den Worker. Diese Dateien nicht automatisch löschen und Aufträge nicht einfach erneut freigeben. Zuerst beide Dienste stoppen, Daten sichern und nachweisen, dass die zum alten Container gehörigen Prozesse beendet sind. Danach den kanonischen Auftragszustand untersuchen. Ein Image-Rollback entfernt die Markierungen nicht.

Vor Backup oder Restore beide Dienste stoppen und den Stillstand prüfen. Daten, eigene Profile, Aufträge und Ergebnisse zusammen sichern; API-Token, TLS-Dateien, Compose-Konfiguration und Image-ID separat geschützt aufbewahren. Ein Restore wird zuerst in einen neuen privaten Testpfad vorgenommen. Rechte und Dateihashes müssen zum gesicherten Stand passen.

Ein Datenrestore ist vom Image-Rollback zu unterscheiden. Ein älterer Worker darf keine unbekannten neueren Jobdaten blind verarbeiten. Die Umstellung einer vorhandenen Installation behandelt [MIGRATION.md](MIGRATION.md).

## 9. Home Assistant anbinden

Der externe Verbindungsweg benötigt die tatsächliche HTTPS-Serveradresse, das passende Secret und gültiges Zertifikatsvertrauen. Die Zugangsdaten verbleiben in Home Assistant. Ein Verbindungstest ist getrennt vom Slicing-Auftrag und Druckstart.

Die Supervisor-Verwaltung ist ein eigener Weg über den bereitgestellten HA-Client. Im geprüften Stand fehlt die freigegebene App-Paketreferenz, weshalb deren Installation gesperrt bleibt. Ein Fehler dort löst keinen automatischen Wechsel zum Unix-Hostinstaller aus.

Der aktuelle Ablauf und die Behandlung unterbrochener Vorgänge stehen in [SUPERVISOR_APP_SETUP.md](SUPERVISOR_APP_SETUP.md). Die allgemeinen Verbindungsgrenzen beschreibt [HA_INSTALLATION_PLAN.md](HA_INSTALLATION_PLAN.md).

## 10. Status und verbleibende Abnahmen

Der Quellstand stellt Laufzeit- und Paketierungsbausteine bereit. Nicht bestätigt sind damit:

- eine vollständige veröffentlichte Runtime mit freigegebenen Engines und App-Referenz;
- eine reale Slicing-Abnahme jeder vorgesehenen Engine-/Profilkombination;
- die unabhängige HA-Verbindung und Bestandsmigration ohne Datenverlust;
- sämtliche produktiven Crash-, Update- und Restorefälle;
- eine Unterstützung weiterer Architekturen ohne deren eigene Nachweise.

Die Eigen- und Drittanbieterrechte stehen unter [REPOSITORY_NOTICES.md](REPOSITORY_NOTICES.md), [LICENSE](LICENSE) und [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Die Lizenztexte werden durch diese Anleitung nicht verändert und nicht pauschal durch MIT ersetzt.

**Gesamtproduktrelease und Betriebsfreigabe bleiben offen. Die eigenständige Linux-Neuinstallation ist der letzte Verifikationsschritt.**
