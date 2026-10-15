# Wartungssperre fuer Containerwechsel

## Zweck und aktueller Stand

Der kanonische JobControl-Dispatcher besitzt einen dauerhaften Wartungszustand.
Der Installer kann damit neue Jobstarts verhindern, bevor er einen Container
stoppt oder dessen Engine-Mount wechselt. Diese Quellimplementierung ist noch
kein vollstaendiger Docker-Lifecycle-Adapter und keine Betriebsfreigabe.

Die Barriere beendet keinen aktiven Auftrag. Sie ist eine kooperative
Betriebssperre zwischen vertrauenswuerdigen Komponenten, keine Sicherheitsgrenze
gegen einen kompromittierten Prozess mit Schreibrechten auf das Datenverzeichnis.

## Atomarer Beginn

Der vertrauenswuerdige lokale Aufrufer verwendet die Runtime-UID (im Kandidaten
65532) und eine vor dem Aufruf dauerhaft gespeicherte zufaellige 32-stellige
Hex-Korrelations-ID. `begin_maintenance(request_id)` nimmt dieselbe
`dispatcher.guard`-Sperre wie der Dispatcher, nicht blockierend.

Ist ein Dispatcher aktiv, wird Busy gemeldet; kein Signal wird gesendet.
Ein verbliebener slicing-Marker oder eine Worker-Recovery-Sperre verhindert den
Beginn ebenfalls. Unter der Sperre wird `run/container-maintenance.json`
atomar geschrieben, die Datei und das Verzeichnis werden synchronisiert und der
Inhalt zurueckgelesen. Erst dann wird `dispatch_blocked=true` bestaetigt.
`services_stopped=false` bleibt ausdruecklich erhalten.

Der Dispatcher prueft die Existenz des Markers innerhalb seiner Sperre und vor
jedem Claim. Auch ein beschaedigter Marker oder ein haengender symbolischer Link
blockiert den Start. Bestehende Warteschlangen und Ergebnisse bleiben erhalten.
Neue API-Uploads und Queue-Eintraege bleiben moeglich; die Barriere verhindert
deren Ausfuehrung. Es gibt in diesem Block keinen neuen oeffentlichen
administrativen HTTP-Endpunkt.

## Neustart, Status und explizite Fortsetzung

Der Marker liegt im persistenten Datenmount und ueberlebt Prozess- und
Container-Neustarts. Der Worker behandelt den Dispatcherzustand `maintenance`
als kontrollierten Leerlauf, nicht als fehlerhaften Job. Seine Telemetrie enthaelt
zusaetzlich das Feld `maintenance`; ein gesunder pausierter Worker ist damit
nicht mit einem betriebsbereiten Installer gleichzusetzen.

Drei lokale Kommandos im vorhandenen container_service-Einstieg:
- `maintenance-begin --request-id ID`
- `maintenance-status`
- `maintenance-end --request-id ID`

Sie validieren den bereits initialisierten Datenbaum und laufen als dessen
Runtime-UID. Sie erzeugen keinen neuen Datenbestand, starten keinen Worker und
brauchen keine Profile, Tokens oder Engine-Ausfuehrung. Sie sind fuer einen
spaeteren festen Hostadapter vorgesehen; keine allgemeine Shell in HA Core.

Nur dieselbe ID kann die Barriere bestaetigen oder entfernen. Ein anderer
Auftrag darf sie nicht uebernehmen. Zum Entfernen werden Dispatcher-Sperre,
Markeridentitaet und fehlende Recovery-/slicing-Marker erneut geprueft.
Es gibt keine automatische Freigabe durch Timeout, Neustart, Healthcheck oder
Fehlerbehandlung. Explizites Ende erlaubt dem normalen Worker wieder, bereits
freigegebene Queue-Eintraege zu verarbeiten; es ist deshalb ein bewusster
Betriebswechsel und kein lesender Verbindungstest.

## Unklarer Ausgang und Wiederherstellung

Ein Timeout oder fsync-Fehler kann nach einer bereits erfolgten Dateiaenderung
auftreten. Das ist kein Erfolg und kein Beweis, dass nichts passiert ist.
Nach Beginn kann derselbe Auftrag den vorhandenen gueltigen Marker erneut
bestaetigen. Fehlt der Marker bei einem Ende-Aufruf, wird
`maintenance_not_present` gemeldet, kein erfundener idempotenter Erfolg.
Der uebergeordnete Hostadapter muss unklare Ausgaenge mit seinem Journal und
aktuellen Container-/Mountnachweisen abgleichen.

Defekte, verlinkte, mehrfach verknuepfte, uebergrosse oder auf POSIX falsch
berechtigte Marker werden nicht adoptiert oder automatisch geloescht.
Gespeicherte Korrelations-IDs sind keine Authentifizierungstokens. Der Zugriff
auf diese Kommandos muss durch den vertrauenswuerdigen Hostinstaller erfolgen.

## Noch erforderlicher Lifecycle-Vertrag

1. Installerauftrag und bisherigen Compose-/Image-/Mountstand dauerhaft binden.
2. Wartungsbarriere setzen und zuruecklesen; bei Busy ohne Jobabbruch abbrechen.
3. Genau die zugehoerigen Container stoppen und deren Stillstand nachweisen.
4. VolumeGuard, ausgewaehlte vollstaendige Engine-Generation, Daten und Profile
   pruefen; konkrete Compose-Mounts binden. ACTIVE allein aendert keinen Mount.
5. Neue Container unter bestehender Barriere starten; Identitaeten, Mounts,
   TLS/API und Worker-Health pruefen.
6. Bei Fehlschlag Barriere erhalten, fehlgeschlagenen Kandidaten nachweislich
   stoppen und den vorherigen Dienststand kontrolliert wiederherstellen.
7. Erst nach erfolgreicher Abnahme bewusst fortsetzen; HA zeigt Fortschritt,
   Fehler und Wiederherstellungsbedarf, Geheimnisse bleiben im Backend.

Dieser Hostadapter, seine Kopplung an den eingeschraenkten Installer sowie der
HA-Einrichtungsflow sind weiterhin offen. Ebenso offen bleiben echte
Docker-Neuinstallation, Enginefreigaben, Cross-Host-TLS und Live-Migration.

## Nachweise

20 synthetische Linux-Tests pruefen Sperrkonkurrenz, aktiven Auftrag,
Queue-/Artefakterhalt, Neustart, Besitzer-ID, fehlerhafte Marker, Busy und
fsync-Fehler. Ein eigener Prozess wechselt wirklich auf UID/GID65532 und prueft
Initialisierung, Wartungsbeginn, unterbundenen Dispatch und explizites Ende.
Es werden keine Engines, Docker-Container oder produktiven Jobs ausgefuehrt.
Windows prueft die portablen Teile; POSIX-/UID-Nachweise werden dort uebersprungen.
Das abschliessende Gesamtgate und der PC/HA-Abgleich werden im privaten
Blockcheckpoint dokumentiert.
