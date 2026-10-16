# Dauerhafte Druckerprofile im Container-Kandidaten

Status: implementierter und isoliert gepruefter Quellvertrag. Noch keine
freigegebene Docker-Installation und kein produktiver Containerstart.

## Ablauf

Der Hostinstaller provisioniert zuerst den dauerhaft verfuegbaren Speicher und
dessen Rechte gemaess HOST_STORAGE.md und RUNTIME_PERMISSIONS.md. Er muss den
gebundenen Datentraeger pruefen und API/Worker vor einer Initialisierung stoppen.
SLICER_PROFILES bezeichnet exakt den bereits angelegten profiles-Stammordner;
Compose legt fehlende Hostpfade nicht selbst an.

Der einmalige Dienst profile-init laeuft ohne Netzwerk als UID/GID 65532. Nur
sein Profilmount ist schreibbar; Daten, Engines, Token und TLS sind dort nicht
eingebunden. Die Startbedingung der API verlangt seinen erfolgreichen Abschluss;
der Worker folgt der API. Das Image muss zuvor aus den aktuellen Quellen neu
gebaut sein. pull_policy=never bleibt bestehen.

container_service.py init-profiles kopiert die kuratierten Drucker-JSON-Dateien
aus dem integritaetsgeprueften Image nach profiles/printers. Aktuell sind dies
Bambu Lab A1 und H2S mit 0,4-mm-Duese. Dies installiert keine Engines, keine
Desktop-Anwendungen und keine neuen Herstellerbibliotheken. Deren Bereitstellung
bleibt Aufgabe des separaten Paket-/Ressourcenkatalogs.

API und Worker binden denselben Profilstamm unter
/var/lib/ultimate-slicer-profiles ausschliesslich lesend ein. --profiles benennt
den Stamm, nicht den printers-Unterordner. Auch der Dispatch-Unterprozess erhaelt
den Pfad. Der bisher separate H2S-Pfad wird im Container ausdruecklich auf diese
Ablage gelenkt. Die native Server-/Dispatcher-Voreinstellung bleibt kompatibel.

## Wiederholung und Abbruch

Eine exklusive Prozesssperre verhindert gleichzeitige Initialisierungen.
PROFILE_STATE.json wird vor dem ersten Kopieren mit state=preparing dauerhaft
geschrieben. Erst nach geschriebenen Dateien und Verzeichnissynchronisation
wechselt der Beleg atomar auf ready. Linux-Verzeichnisse werden mit fsync
gesichert; Windows dient nur den isolierten Entwicklungstests.

Ein fertiger Bestand wird validiert und unveraendert wiederverwendet. Die im
Beleg gespeicherten SHA-256-Werte dokumentieren den urspruenglichen Seed.
Benutzeraenderungen an gueltigen Profilen bleiben erhalten; ein neuer Image-Seed
ersetzt vorhandene Profile nicht automatisch. Zusaetzliche gueltige
Druckerprofile sind moeglich. Entfernte erforderliche Seedprofile blockieren.

Fremde Stammdateien, unvollstaendige Belege und unbekannte Zustaende blockieren.
Keine automatische Adoption, Loeschung oder Recovery. Ein abgebrochener Vorgang
muss mit gesicherten Originalen und gestoppten Verbrauchern bewusst rekonstruiert
werden; ein automatisierter Recovery-Assistent ist noch offen.

## Validierung und Vertrauensgrenze

Nur regulaere, nicht hartverlinkte JSON-Dateien mit sicheren Dateinamen und
passender id werden akzeptiert. Symlinks, erkannte Junctions, doppelte JSON-Keys,
nicht endliche JSON-Konstanten sowie absolute Pfade mit Elternspruengen werden
abgewiesen. Grenzen: 256 Profile, 64 KiB je Datei, 8 MiB insgesamt.
Fehlender Mount oder unvorbereitete Ablage fuehren nicht zu einem stillen
Rueckfall auf die Imageprofile.

Der Host und sein Installationsadapter bleiben vertrauenswuerdig. Diese
Initialisierung ersetzt weder VolumeGuard noch exklusiven Host-Lifecycle,
Mountidentitaet, Lizenzpruefung oder eine fachliche Engine-Profilvalidierung.
Gleichzeitige fremde Hostschreiber sind nicht Teil dieses Vertrags. Die
Container-Verbraucher duerfen Profile nicht veraendern; spaetere Profilverwaltung
benoetigt einen expliziten, gestoppten und geprueften Schreibweg.

## Nachweise und verbleibende Arbeit
