# Einrichtung des Slicer-Servers aus Home Assistant

Status: verbindliches Produktziel, noch kein fertiger Installationsassistent.
Die manuelle Kandidatenpruefung steht in [RUNTIME_INSTALLATION.md](RUNTIME_INSTALLATION.md).

## Ziel fuer Nutzer

Im Studio in Home Assistant startet "Slicer-Server einrichten" einen gefuehrten
Ablauf. Die Standardinstallation soll ohne Terminal, Docker-Kenntnisse,
Bibliotheksauswahl, manuelle Downloads oder manuelle Pfadangaben auskommen.

1. System und vorhandenen Server erkennen; vorhandene Daten erhalten.
2. Dauerhaften Speicher automatisch vorschlagen und pruefen.
3. Benoetigte Slicing-Engines im Hintergrund herunterladen und vorbereiten.
4. Server starten, Verbindung pruefen und automatisch im Studio eintragen.
5. "Bereit" erst anzeigen, wenn die erforderlichen Pruefungen bestanden sind.

Ein eigener Datenpfad, ein externer Docker-Host und eine abweichende Engineauswahl
gehoeren unter "Erweitert". Sichtbare Schritte lauten etwa "System pruefen",
"Speicher vorbereiten", "Slicing-Komponenten laden", "Verbindung pruefen".
Bei Fehlern Ursache und konkrete naechste Aktion anzeigen; kein endloser Spinner.
Abbruch und erneuter Versuch duerfen Daten und bereits funktionierende Versionen
nicht zerstoeren. Ein Druckstart gehoert nicht zur Installation.

## Ausschliesslich serverseitiges Slicing

Installiert werden die headless Slicing-Engines bzw. ihre nutzbaren
Kommandozeilen-/Bibliotheksbestandteile, erforderliche Laufzeitbibliotheken und
zugehoerige Profile. Es werden keine Desktop-Installationen, Desktop-Launcher,
VNC-Oberflaechen oder interaktiven Herstelleranwendungen eingerichtet.

"Nur Bibliotheken" setzt keine von jedem Anbieter separat angebotene Shared
Library voraus. Der vorhandene Backendaufruf kann ein CLI-Programm verwenden.
Technisch verlinkte Bibliotheken bleiben auch dann erforderlich, wenn keine
grafische Oberflaeche gestartet wird. Dateien nur entfernen, wenn die jeweilige
Engine damit nachweislich weiter funktioniert und Lizenzpflichten erfuellt sind.

Ziel sind die drei vorhandenen Dispatcher-Anbindungen: Bambu Studio
(`bambu_studio`), PrusaSlicer (`prusaslicer`) und CuraEngine (`curaengine`).
Sie entsprechen dem bestehenden Backend; OrcaSlicer gehoert nicht zu diesen
vorhandenen drei Zweigen. Die Anbindungen belegen noch keine fertige
Installation oder Funktionsabnahme aller drei Engines im neuen Container.
Einheitliche Bedienung bedeutet nicht identische Downloadformate. Fuer jede
Engine gibt es einen geprueften Adapter mit CLI-Vertrag, Profilformat,
Architektur, Version, Herkunft, Digest und Abnahme. Keine Annahme, alle
Hersteller lieferten austauschbare einzelne Bibliotheksdateien oder AppImages.

## Installationswege und Berechtigungen

Die Bedienung bleibt in Home Assistant; privilegierte Installation gehoert
nicht in den HA-Core-Prozess. Ein begrenzter Installationsdienst bietet feste
Operationen fuer Pruefen, Installieren, Status, Abbrechen und Rueckweg.
Keine freie Shell, beliebigen Download-URLs, allgemeinen Dockerbefehle oder
ungeprueften Mountpfade ueber die HA-Schnittstelle.

Home Assistant OS kann Apps ueber den Supervisor installieren. Home Assistant
Container enthaelt diesen App-Installationsweg nicht. Der Assistent muss die
Betriebsart erkennen:
- HA OS: passende Supervisor-App-Verpackung und vom Supervisor verwalteter
  dauerhafter Speicher; keine beliebigen Hostpfade voraussetzen.
- Verwalteter Linux-Docker-Host: begrenzter, authentifizierter Host-Installer
  und Compose. Ein fehlender Installer erfordert eine einmalige dokumentierte
  Einrichtung/Kopplung. Das kann nicht durch eine HACS-Integration allein ohne
  vorhandene Hostberechtigung ersetzt werden.
- Externer Server: bewusst gekoppelte Zielinstanz mit verifiziertem TLS.

Diese Verpackungsvarianten sind noch zu implementieren und abzunehmen.
Insbesondere ist das heutige Zwei-Dienst-Compose nicht automatisch bereits
eine Supervisor-App. Keine uneingeschraenkte Docker-Socket-Freigabe an HA-Core.

## Dauerhafte Daten

Der Standardpfad liegt auf einem geprueften persistenten lokalen Datentraeger
des Zielhosts; ein geeigneter neuer Unterordner wird automatisch angelegt.
Ein Beispielpfad ist keine fest eingebaute Zusage fuer jeden HA-Installationstyp.

Vor Erstellung: aufgeloester Pfad, Mount-/Datentraegeridentitaet, Schreibbarkeit,
freier Platz, Rechte und bestehende Daten pruefen. Temporaere Containerpfade,
Symlink-Ausbrueche, fremde Verzeichnisse und unbemerkt fehlende Mounts ablehnen.
Fehlt ein erwarteter Datentraeger nach Neustart, nicht still auf dem darunter
liegenden leeren Hostverzeichnis fortfahren.

Dauerhaft trennen: Auftraege/Modelle/Resultate, eigene Profile, Engineversionen,
Installationsmanifest und geschuetzte Verbindungskonfiguration. Imagewechsel
duerfen diese Daten nicht loeschen. Engines werden nach Installation nur lesend
in den Worker eingebunden. Downloadrechte liegen beim Installer; der
Slicing-Worker bleibt netzisoliert.

## Downloads, Updates und Rueckweg

Ein kuratierter Enginekatalog legt pro Architektur feste freigegebene Versionen,
offizielle Herkunft und unabhaengig gepruefte Digests fest. "latest" ist kein
reproduzierbarer Vertrag. Vor Aktivierung pruefen: Downloadgroesse, Digest,
gegebenenfalls Signatur, Archivpfade, Dateirechte, Abhaengigkeiten und
Engine-/Profilversion. Keine ungeprueften Installationsskripte ausfuehren.

Downloads in einen begrenzten Zwischenbereich; erst nach vollstaendiger
Pruefung atomar aktivieren. Doppelte Requests und gleichzeitige Installer
serialisieren. Netzwerkabbruch, Platzmangel und Prozessabbruch muessen einen
erneuten Versuch erlauben. Alte funktionierende Version fuer den Rueckweg
behalten. Keine automatische Aktualisierung waehrend laufender Auftraege.

Bibliotheken, Engineartefakte und Profile haben eigene Lizenz-/Herkunftsnachweise.
Die Bereichslizenz fuer eigenen Code ersetzt keine Fremdlizenzen. Ein
Paketversionsinventar ist noch kein vollstaendiger SBOM-/Lizenznachweis.

## Umsetzungs- und Abnahmefolge

| Schritt | Ergebnis | Abnahme |
| --- | --- | --- |
| Host-Erkennung und Vertrag | Installationstyp, Architektur und begrenzte Operationen | Fremdhost/falsche Rechte und nicht unterstuetzte Architektur sauber abweisen |
| Speicherplanung | Automatischer Standard, erweiterter eigener Pfad | Neustart, fehlender Mount, Rechte, Platzmangel, Bestandsdaten |
| Enginekatalog und Adapter | Drei bestaetigte headless Enginefamilien | Herkunft/Digest, Lizenzen, Profile und CLI je Version |
| Transaktionale Installation | Download, Pruefung, Aktivierung, Fortschritt | Abbruch, Parallelaufruf, Wiederholung, fehlerhafte Archive |
| HA-Assistent und Kopplung | Wenige verstaendliche Schritte, automatischer Verbindungseintrag | TLS/Authentifizierung, Fehleranzeige, kein Geheimnis in Logs |
| Upgrade und Wiederherstellung | Daten bleiben erhalten, Rueckweg funktioniert | Backup/Restore, Versionswechsel, keine aktiven Jobs beeintraechtigen |
| Neue Nutzerinstallation | Dokumentierter End-to-End-Weg auf frischem Zielsystem | Von Einrichtung bis erstem autorisiertem Slicing ohne Desktopinstallation |

Die Enginebibliotheken des aktuellen Linux/amd64-Kandidaten sind ein
Vorbereitungsschritt. Eine statische ELF-Pruefung ist keine reale Slicing-
oder Installationsabnahme. Docker-Fertigstellung bleibt vor der sonstigen
Migrations-Roadmap; GitHub/Wiki und Branchkonsolidierung folgen nach Abnahme.

## Fachliche Quellen

Am 10.10.2026 geprueft:
- [HA Installationstypen](https://www.home-assistant.io/installation/):
  HA OS und HA Container unterscheiden sich beim App-Installationsweg.
- [HA Apps](https://developers.home-assistant.io/docs/apps/):
  Supervisor-verwaltete Containerverpackung.
- [PrusaSlicer-Projekt](https://github.com/prusa3d/PrusaSlicer):
  CLI ohne GUI ist dokumentiert; Linux-Verteilung derzeit ueber Flathub,
  daher keinen universellen offiziellen AppImage-Download annehmen.


Implementierte Grundlage: [Engine-Pfadvertrag](ENGINE_LAYOUT.md) fuer gemeinsame
Erkennung durch Dispatcher und Telemetrie. Installation/Download und die oben
beschriebenen Abnahmen bleiben offen.


[Engine-/Paketkatalog](ENGINE_CATALOG.md): strukturelle Validierung und begrenzte
Digestpruefung sind implementiert. Alle drei echten Paketsaetze bleiben bis zur
Herkunfts-/Ressourcen-/Profilabnahme gesperrt; automatische Installation folgt.


[Download und Paket-Staging](PACKAGE_STAGING.md): begrenzter TLS-Download,
Archivpfad-Zuordnung und Dateipruefung sind implementiert. Aktivierung,
Speichervertrag und HA-Assistent bleiben offen; alle Katalogreleases pending.

## Implementierte Speicher-/Aktivierungsgrundlage

[PACKAGE_ACTIVATION.md](PACKAGE_ACTIVATION.md) beschreibt den implementierten
Installerkern: Store-ID gegen fehlende Mounts, POSIX-Besitz/Modi, echte
Platzreservierung, exklusive Transaktion und atomarer Wechsel einer vollstaendigen
Drei-Engine-Generation. Alle Manifestdateien werden nach bestaetigtem Worker-
Stillstand erneut gehasht; alte Generationen und fremde Nutzerdaten bleiben
erhalten. Crashzustaende blockieren neue Installationen, bis eine explizite
Adopt-/Rollback-Entscheidung mit erneutem Worker-Stillstand erfolgt.

Dies ist noch kein Host-Installer und kein Assistent. Der spaetere Hostdienst
muss die Store-ID ausserhalb des Mounts sichern, Worker eindeutig stoppen, den
aktiven Generationspfad in Compose einsetzen und erst danach API/Worker neu
starten und pruefen. Keine der drei echten Engines ist dadurch freigegeben.

## Implementierter Befehls- und Orchestrierungskern

[RESTRICTED_INSTALLER.md](RESTRICTED_INSTALLER.md) beschreibt Authentifizierung,
feste Operationen, extern gesicherte Storebindung, Stage/Activate/Cancel/Retry
und Crash-Recovery. Der integrierte synthetische Paketdurchlauf ist bestanden.
HostPolicy/Volume-/Stop-Callbacks sind vertrauenswuerdige Provisionierung;
automatische Host-Erkennung und Kopplung sind damit noch nicht implementiert.
Offen bleiben gesicherter Transport, reale Compose-/Supervisor-Adapter und
HA-Backendclient/Einrichtungsflow. Alle echten Engine-Releases bleiben pending.


## Implementierte Linux-Speichergrundlage

[HOST_STORAGE.md](HOST_STORAGE.md) beschreibt Standardpfad, native Mount-/UUID-
Pruefung und dauerhafte Bindung. Der verwaltete Linuxhost kann ein neues Layout
anlegen; Wiederholung erhaelt Nutzerdaten und erkennt verlorenen Speicher.
Die HA-Oberflaeche muss diesen lokalen Kopplungsweg noch anbinden. Workerrechte,
Supervisorvariante, TLS und Laufzeitsteuerung sind weiter offen. Kein echter
Engine-Release ist freigegeben.
\n
## Implementierte Rechtevergabe fuer den verwalteten Linuxhost

[RUNTIME_PERMISSIONS.md](RUNTIME_PERMISSIONS.md): leere Daten-/Profilordner
koennen kontrolliert root:65532/2770 erhalten. Beleg und VolumeGuard erkennen
Teilzustaende und Rechteabweichungen; bestehende Nutzerdaten bleiben erhalten.
Kein pauschales chmod/chown und keine Rechteaenderung an Engines/Steuerdaten.
Die Profilablage muss noch mit ihrem Verbraucher verbunden werden. Transport,
Kopplung, Lifecycle und gefuehrte HA-Einrichtung bleiben offen.


## Implementierte dauerhafte Druckerprofile

[PERSISTENT_PROFILES.md](PERSISTENT_PROFILES.md): Der provisionierte profiles-
Stamm wird ueber SLICER_PROFILES eingebunden. profile-init befuellt ihn einmalig;
API/Worker lesen denselben Bestand inklusive H2S. Wiederholung erhaelt Profile,
Teilzustaende blockieren. Der Hostadapter muss VolumeGuard und gestoppten
Lifecycle voranstellen. Dateninitialisierung, Token-/TLS-Rechte, Hostkopplung
und gefuehrte HA-Einrichtung bleiben offen. Engine-Releases bleiben pending.


## Implementierte Daten- und Zugangsdatenbasis

Der Container-Kandidat besitzt einen separaten, netzwerklosen `data-init`-
Schritt unter UID/GID 65532. Er prueft den bereits provisionierten Mount,
initialisiert ein leeres Layout einmalig und blockiert fremde, verlinkte,
unvollstaendige oder in den Rechten abweichende Bestaende. Bestehende
Nutzerdaten werden weder verschoben noch geloescht.

Der API-Start liest Token, Zertifikat und privaten Schluessel descriptorbasiert
mit Groessen-, Typ-, Link-, Besitz- und Modusgrenzen. Das ist noch keine
Rotation oder Live-Verteilung. Sicherer Host-/Supervisor-Transport,
Dienstrollback und der HA-Einrichtungsflow bleiben nachgelagerte Abnahmen.
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

## 12.10.2026 - Authentifizierter Erstinstallationspfad

Der vorhandene eingeschraenkte Installer routet eine Aktivierung bei fehlender
ACTIVE-Datei jetzt durch das dauerhafte FirstInstall-Journal. Es gibt keine neue
freie Installationsoperation: HA verwendet weiterhin die festen, authentifizierten
Schritte initialize, stage und activate sowie die principalgebundenen Operationen
rollback und resume. Nur ein SHA-256 des bereits authentifizierten Principals
gelangt in das Erstinstallationsjournal; Token werden weder dort noch in
Antworten abgelegt.

Der feste data-init-Helfer darf vor der Aktivierung den zukuenftigen, aus dem
kandidatengebundenen Generation-Identifier abgeleiteten Enginepfad in der
Compose-Umgebung sehen. Dieser Pfad muss in dieser Phase noch nicht existieren
und wird nicht angelegt; API und Worker bleiben aus. Nach Aktivierung, Start und
TLS-/Worker-Pruefung bleibt die Installation ready_paused, bis ein getrennt
authentifiziertes resume die Wartung aufhebt. rollback entfernt nur das eigene
Containerpaar und den ersten ACTIVE-Zeiger; Generationen und Nutzerdaten bleiben.

Synthetischer Verbundnachweis unter Windows: 115 Tests bestanden, 21
plattformbedingte Linux-Socket-Skips. Darin enthalten sind Adapterneustart,
Resume, fremder Principal und Rueckweg zu fehlendem ACTIVE. Kein Dockerdaemon,
keine Engine und kein Dienst wurden gestartet. Offen bleiben der HA-Backendclient
fuer Socket/Handoff, die Darstellung im gefuehrten Einrichtungsflow, echte
Linux-/TLS-/Hostinstallation und die Engine-/Lizenzfreigaben.

## W38: HA-Backendclient und gefuehrter Installer-Controller

Der HA-seitige Backendvertrag ist als eigenstaendiger, noch nicht produktiv aktivierter Baustein vorhanden. Er uebernimmt einen zuvor lokal und geschuetzt bereitgestellten Installer-Handoff nur gegen eine extern gepinnte Host-ID. Der Token wird descriptorbasiert und groessenbegrenzt gelesen, in eine private serverseitige 0600-Datei atomar geschrieben, per Readback bestaetigt und erst danach ueber die unveraenderte Inode-Identitaet aus dem Handoff entfernt. Browser, Formulardaten, Ergebnisobjekte und Diagnoseantworten erhalten den Token nicht.

Der kompatible UnixInstallerClient prueft Sockettyp, Owner und SO_PEERCRED vor der Tokenübertragung, nutzt feste Control-/Mutation-Lanes und absolute Fristen. Der persistente GuidedInstallerSetup erzeugt Request-IDs ausschliesslich serverseitig und bindet preflight, initialize, stage, activate, status, cancel, rollback und resume ohne freie Befehle oder anforderungsabgeleitete Socketpfade. Verlorene Antworten erzeugen keinen automatischen Retry mit neuer Identitaet.

Grenze: Dies ist eine synthetische Backend-/Flow-Abnahme. Der HA-Optionsflow ist noch nicht sichtbar verdrahtet, das Host-Pairing muss die Host-ID und Mounts vertrauenswuerdig provisionieren, und es wurde keine echte Installation, kein Container und keine Engine gestartet.

## W44: Supported host provisioning boundary

The current Supervisor App map interface documents selected Supervisor
directory types, with an optional in-container destination path. The current
Core options endpoint documents Core runtime options but no arbitrary
bind-mount configuration. The existing plan therefore has no documented,
supported mechanism for adding the three W42 pin/endpoint/handoff mounts to
this Core container.

Do not wire the installer flow until the host provisioning mechanism is
supported and its real mount/owner/mode/inode and both SO_PEERCRED values are
measured. Do not substitute writable /share, Docker socket access, or an
unverified TCP listener. Reassess the channel only as a separate design
decision; this note does not perform or authorize a Home Assistant OS
migration.

References:
- https://developers.home-assistant.io/docs/apps/configuration/
- https://developers.home-assistant.io/docs/api/supervisor/endpoints/

## W45: Exklusiver Zielbetrieb

Der native Slicer und der Docker-Slicer duerfen nur im aktuellen, temporaeren
Test-/Uebergangsaufbau gleichzeitig vorhanden sein, wenn der Testaufbau dafuer
Workarounds benoetigt. Diese Workarounds sind keine Installationsanforderung
fuer saubere Systeme.

Eine saubere Zielinstallation richtet ausschliesslich den Docker-Compose-
Slicer ein. Vorhandene native Dienste, Prozesse, Daten-/Steuerpfade oder
Dockerinstallationen muessen erkannt werden; ein zweiter Betrieb wird
fail-closed abgelehnt. Auch der native Startpfad muss den aktiven Dockerbetrieb
erkennen oder im sauberen Zielsystem fehlen. Bis diese Gegensperre abgenommen
ist, ist Exklusivitaet ein offener Installationsgate. Vorhandene Systeme werden
nicht automatisch veraendert oder migriert; Altbestand fuehrt zu Abbruch und
Hinweis auf einen nur nach ausdruecklichem Auftrag geplanten Migrationsschritt.

Tests: sauberer Host -> nur Docker; nativer Bestand -> Docker blockiert;
Dockerbestand -> nativer Start blockiert; Mischhost -> nur isolierter
Testbetrieb mit expliziten Workarounds. Dies beschreibt Sollverhalten, noch
keine vorhandene Implementierung.

## 13.10.2026 - Aufbau des separaten Linux-Testservers

Der aktuelle Live-Host wird nicht fuer einen Compose-Mischtest verwendet.
Der separate Arbeitsplatz-Testserver bildet eine isolierte Supervisor-
Laborumgebung; der Slicer wird dort ausschliesslich ueber Docker Compose
bereitgestellt. Vor jeder ersten Mutation muss der read-only Clean-Host-
Preflight erfolgreich sein. Ein erkannter Altbestand wird gemeldet und
blockiert, aber niemals automatisch entfernt oder migriert.

Die vorbereitete Abnahmefolge und Stop-Kriterien stehen in
[LINUX_TEST_SERVER_RUNBOOK.md](LINUX_TEST_SERVER_RUNBOOK.md). Dies ist noch
keine Installations- oder Supervisor-Abnahme. HAOS-Migration, Live-System,
HACS-Pilot und Public Release bleiben getrennt.


## 15.10.2026 - Implementierter HA-Dialog und geschuetzte Serververbindung

Der native HA-Optionendialog ist jetzt an den vorhandenen Installerkern
angebunden. Lazy ConfigEntry-Sitzung, blockierungsfreie Datei-/Socketarbeit,
Fortschritt, Bestaetigung, Status/Abbruch, Wiederaufnahme und Rueckweg sind
quellseitig vorhanden. Die automatische Installationsfolge endet pausiert;
Resume ist eine gesonderte Entscheidung, keine automatische Auftragsfreigabe.
Diese Einordnung ersetzt die oben dokumentierten historischen Aussagen,
dass der HA-Client und die Dialoganbindung noch vollstaendig fehlen.

Der neue bestaetigte Dialogschritt "Slicer-Verbindung sicher uebernehmen"
verwendet ausschliesslich das bereits gepinnte lokale Handoff-Verzeichnis.
Die Datei slicer-connection.json enthaelt Schema1, host_id, principal,
transfer_id, base_url und api_secret. Host-ID und Principal muessen zur
bereits bestaetigten Hostkopplung passen. Das Schema akzeptiert nur eine
kanonische HTTPS-Basisadresse und einen gueltigen Header-Schluessel; keine
URL-Zugangsdaten, Query/Fragment, beliebigen Pfade oder Remote-Enrollment.
Datei-, Owner-, Modus-, Link-, Groessen- und Identitaetspruefungen erfolgen
vor und nach der vorhandenen authentifizierten info.json-Verbindungsprobe.

URL und Schluessel werden nie in Formularfelder, Fortschritt, Fehlermeldungen
oder Sitzungsstatus uebernommen. Erst der native OptionsFlow-Abschluss
bekommt sie serverseitig als neue Optionen. Gleichzeitige manuelle Aenderungen
der Verbindung verhindern ein Ueberschreiben; andere aktuelle Optionen
bleiben erhalten. Die Host-Uebergabedatei bleibt bis zu einer gesonderten,
dauerhaft bestaetigten Bereinigung bestehen. Eine fluechtige Speicherzusage
wird nicht mit einem gesicherten Persistenznachweis gleichgesetzt.

Der neutrale Baustein slicer_connection_handoff.py stellt fuer einen spaeteren
vertrauenswuerdigen lokalen Linux-Root-Provisionierer einen passenden Producer
bereit. Er erstellt nur in einem bereits provisionierten Verzeichnis,
serialisiert, setzt die Empfaengerrechte und veroeffentlicht atomar ohne eine
vorhandene andere Uebergabe zu ueberschreiben. Ein identischer erneuter Aufruf
ist idempotent. Dies ist kein neuer Netzwerkendpunkt; der echte Hostbootstrap
muss den Producer noch anbinden. Reale Root-/Mount-/Peer- und Zielsystemtests
bleiben bis zu ihrer Ausfuehrung offen.

Nachweis: isolierter Kandidat130Faelle,122PASS/8plattformbedingteSkips;
kanonische gezielte Pruefung126PASS/8Skips/77Untertests. Vier Sprach- und
Platzhalterpruefungen enthalten. Echte Host-/HTTPS-Gegenstellen sind in diesen
Faellen synthetisch; daraus folgt keine praktische Neuinstallationsabnahme.

Aktuelle Release-Reihenfolge: Implementierung, gepruefte Pakete, Dokumentation
und Veroeffentlichung zuerst; die separate saubere Linux-Neuinstallation ist
der letzte Verifikationstest. Sobald alle anderen Release-Arbeiten wirklich
abgeschlossen sind, darf der Release mit offen ausgewiesenem abschliessendem
Installationstest abgeschlossen werden. Fehlende Laufzeit-/Installations-
Nachweise bleiben not_run. Noch offene Enginepakete, Katalogfreigaben und
Hostprovisionierung werden dadurch weder als implementiert noch getestet
behauptet. Live-System und HAOS-Migration bleiben getrennte Auftraege.
