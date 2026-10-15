# Ultimate Slicer Server

Slicer-Server ist der eigene Produktbereich im bestehenden Ultimate-3D-Studio-
Repository. Docker wird der regulaere Installationsweg. Ein separates Repository
und ein dauerhaft separater Git-Branch sind dafuer nicht erforderlich. Nach der
abgeschlossenen Migration soll das Produkt weiterhin aus main ausgeliefert werden.

**Aktueller Stand: Docker-Dienstkandidat mit API, Worker und Telemetrie.**
Compose-Start, TLS/Authentifizierung, Stop/Neustart sowie synthetischer
Anchor-Ausfall und Backup/Restore sind geprueft. Eine Engine ist noch nicht
enthalten; reale Engine-Abnahme und produktive Datenmigration bleiben offen.
Der Standardbefehl des Images bleibt der lesende Preflight.
`container_deploy_ready=false` kennzeichnet die fehlende Betriebsfreigabe.

## Einstieg

- [Installation und Voraussetzungen](INSTALLATION.md)
- [Docker-Dienstkandidat einrichten](RUNTIME_INSTALLATION.md)
- [Docker-Architektur und Migrationsschritte](MIGRATION.md)
- [Betrieb, Sicherung und Wiederherstellung](OPERATIONS.md)
- [Container-Tests und Abnahmegrenzen](CONTAINER_TESTING.md)
- [Linux-Testserver: Vorbereitung und Abnahme](LINUX_TEST_SERVER_RUNBOOK.md)
- [Lizenzbedingungen](LICENSE)
- [Fremdsoftware und bisherige Lizenzrechte](THIRD_PARTY_NOTICES.md)
- [Wiki-Quellen fuer den spaeteren GitHub-Release](wiki/Home.md)

## Was der Bereich enthaelt

| Datei / Bereich | Aufgabe |
|---|---|
| prepare_context.py | Stellt ausschliesslich erlaubte, SHA-gepruefte Quellen zusammen |
| Dockerfile | Baut Quellpruefung und explizit startbaren Dienstkandidaten |
| container_check.py | Prueft Paketintegritaet ohne Import oder Start des Workers |
| container_runtime.py | Prueft Kernelisolation und ueberwacht einen eigenen Supervisor |
| container_probe.py | Prueft ausschliesslich synthetische Prozesse in einem temporaeren Baum |
| container_service.py | Betreibt API, Worker und einen Telemetrie-Schreiber |
| compose.candidate.yaml | Startet den noch nicht freigegebenen Dienstkandidaten |
| compose.preview.yaml | Fuehrt ausschliesslich den isolierten Preflight aus |
| LICENSE | Privatnutzung und Aenderungsverbot fuer neuen eigenen Code |
| THIRD_PARTY_NOTICES.md | Begrenzt den Lizenzumfang und dokumentiert offene Herkunftspruefung |
| wiki/ | Versionierte Texte fuer das spaetere GitHub-Wiki |

Der Build-Kontext besteht aus 20 vorhandenen Laufzeit-/Metadatendateien sowie
den expliziten Docker-Pruefdateien und seinem Manifest. Er wird ausserhalb des
Quellbaums erzeugt. Ein bereits vorhandenes Ziel wird nicht ueberschrieben.
Es wird niemals das gesamte Studio-Verzeichnis als Docker-Kontext uebergeben.

## Geplantes fertiges Produkt

Der regulaere Weg beginnt im Studio in Home Assistant mit
"Slicer-Server einrichten". Der Assistent erkennt das Zielsystem, bereitet einen
dauerhaften Datenpfad vor, laedt gepruefte headless Slicing-Komponenten samt
Profilen und verbindet den Server automatisch. Ein eigener Datenpfad und ein
externer Server stehen unter "Erweitert". Keine Desktopinstallation.

Die drei vorhandenen Anbindungen sind Bambu Studio, PrusaSlicer und CuraEngine.
Ihre Laufzeitbibliotheken sind im Linux/amd64-Kandidaten statisch geprueft;
Engineartefakte und Profile werden damit noch nicht automatisch installiert.
Der [HA-Installationsplan](HA_INSTALLATION_PLAN.md) beschreibt die offenen Schritte.

HA OS benoetigt eine Supervisor-App-Verpackung. Fuer HA Container wird ein
begrenzter Host-Installer einmalig eingerichtet und gekoppelt. Die HACS-
Integration allein kann keine beliebigen Docker-Hosts verwalten. Beide
Auslieferungswege und der Assistent sind noch zu implementieren.

## Vorhandene Quellen und Uebergang

Die Laufzeitquellen liegen momentan noch im kanonischen nativen Worker-Bereich
und teilweise in der Studio-Integration. prepare_context.py liest diese
ausdruecklichen Quellen; es legt keine zweite gepflegte Worker-Kopie an.
Die 10 noch komponenteneigenen Hilfsdateien werden in einem gesonderten Schritt
mit ihren Verbrauchern entkoppelt. Erst danach ist Slicer-Server auch vollstaendig
die Quellautoritaet der Laufzeit.

Vorhandene native Installer und Host-Dienste bleiben bis zur geprueften
Container-Migration als Rueckweg erhalten. Ihre alten Abnahmeergebnisse gelten
nicht automatisch fuer Docker.

## Versions- und Freigabevertrag

Die Softwareversion und API-Kompatibilitaet kommen weiterhin aus
packages/ultimate-slicer-server/release.json. Produkt-, Datei-, Dienst- und
API-Namen erhalten keine Releaseversion. Image-Tags und Digests identifizieren
spaeter die konkreten Artefakte; fuer produktive Installation wird der Digest
festgeschrieben.

Das Manifest ist ein Integritaetsinventar, keine Signatur und kein Beleg fuer
Vertriebsrechte. Erst Build, Containerrechte, Isolation, Prozessabbruch,
Engine-/Profiltest, TLS, HA-Verbindung, Upgrade und Restore erlauben die
Kennzeichnung als installierbares Produkt.

## Nutzungsrechte

Neue eigene Dateien dieses Bereichs erhalten eine individuelle Lizenz:
privater, nichtkommerzieller Einsatz; keine Aenderungen am Programmquellcode.
Dokumentierte Einstellungen und eigene Modelle/Profile bleiben anpassbar.
Fremdsoftware und bereits anders lizenzierte Fassungen behalten ihre Rechte.
Das Projekt darf deshalb nicht pauschal als vollstaendig unter dieser Lizenz
oder als Open Source bezeichnet werden.

## Beitrag und Support

Fehlerberichte sollen Version, Image-Digest, Architektur, Fehlerzeitpunkt und
bereinigte Pruefergebnisse enthalten. Keine Secrets, Zertifikatsschluessel,
personenbezogenen Pfade oder privaten Modelle in Issues kopieren. Entwicklung
durch vom Rechteinhaber beauftragte Entwickler bleibt moeglich; eine allgemeine
Erlaubnis fuer Code-Forks mit Aenderungen wird dadurch nicht erteilt.


Ziel fuer den regulaeren Installationsweg: [HA-Einrichtungsassistent](HA_INSTALLATION_PLAN.md),
mit automatisch verwaltetem Dauerspeicher und headless Slicing-Komponenten.
Noch Roadmap, keine fertige Ein-Klick-Installation.


[Gemeinsamer Container-Enginepfadvertrag](ENGINE_LAYOUT.md): Dispatcher und
Telemetrie verwenden gepruefte Eintraege desselben Engine-Speichers. Die
automatische Bereitstellung bleibt der naechste Implementierungsschritt.


[Engine-/Paketkatalog](ENGINE_CATALOG.md): strukturelle Validierung und begrenzte
Digestpruefung sind implementiert. Alle drei echten Paketsaetze bleiben bis zur
Herkunfts-/Ressourcen-/Profilabnahme gesperrt; automatische Installation folgt.


[Statische Ressourcenpruefung](RESOURCE_VALIDATION.md): Cura-Vererbungsgraph,
Extruderreferenzen und Dateiintegritaet sind pruefbar. Echte Cura-/Prusa-Archive
wurden untersucht; mehrdeutige Cura-Daten bleiben gesperrt. Der gepruefte
Teilbestand ist noch kein freigegebenes Installations- oder Druckerpaket.


[Download und Paket-Staging](PACKAGE_STAGING.md): begrenzter TLS-Download,
Archivpfad-Zuordnung und Dateipruefung sind implementiert.

[Persistenter Speicher und Aktivierung](PACKAGE_ACTIVATION.md): Store-Identitaet,
Platzreservierung, Installer-Sperre und atomare Drei-Engine-Generationen sind
synthetisch geprueft. HA-Assistent, echte Releases und Livebetrieb bleiben offen.


[Authentifizierter Installationskern](RESTRICTED_INSTALLER.md): feste Operationen,
Scopes, dauerhafte Request-IDs und Stage-/Aktivierungs-/Recovery-Anbindung sind
synthetisch geprueft. Erreichbarer Hostdienst und HA-Assistent folgen separat.


[Dauerhafter Hostspeicher](HOST_STORAGE.md): automatischer Linux-Standardpfad,
Mount-/UUID-Bindung und Installer-VolumeGuard sind implementiert. Laufzeitrechte,
Supervisorvertrag und HA-Einrichtungsflow bleiben offen.


[Container-Dateirechte](RUNTIME_PERMISSIONS.md): gezielte Gruppenfreigabe fuer
Daten/Profile und geschuetzte Engine-/Steuerablagen sind synthetisch geprueft.
Hostkopplung, Laufzeitsteuerung und HA-Assistent bleiben weitere Schritte.


[Dauerhafte Druckerprofile](PERSISTENT_PROFILES.md): einmalige Initialisierung,
erhaltender Neustart und gemeinsamer lesender Profilmount fuer API/Worker sind
isoliert geprueft. Auch der H2S-Sonderpfad ist angebunden. Dateninitialisierung,
Token/TLS und der HA-Einrichtungsflow folgen; noch keine Ein-Klick-Installation.


## Datenablage und Zugangsdaten

Der einmalige, netzwerklose `data-init`-Schritt bindet die vorhandene
provisionierte Datenablage eindeutig und legt nur die kanonischen
Unterverzeichnisse fuer Uploads, Jobs, Ausgaben, API, Web und Laufzeitbelege an.
Fremde, verlinkte oder teilweise vorbereitete Bestaende werden nicht automatisch
uebernommen. Wiederholung erhaelt bestehende Nutzerdaten.

API und Worker starten erst nach erfolgreicher Daten- und Profilinitialisierung.
Token, Zertifikat und privater Schluessel werden nur als begrenzte regulaere
Dateien ohne Links oder Mehrfachverknuepfungen gelesen; unter POSIX gelten enge
Besitz- und Modusregeln. Ein Token darf genau einen LF- oder CRLF-Abschluss
haben. Rotation, Widerruf, Hostkopplung und Live-Neustart folgen separat.

[Dauerhafte Dateninitialisierung](DATA_PERSISTENCE.md): ready wird erst nach
Synchronisation aller fertigen Verzeichniseintraege gesetzt. Die Regression zur
Commit-Reihenfolge und zum Erhalt von preparing bei Flushfehlern ist bestanden.

## Lokaler Installationskanal

Der gepruefte Unix-Client/Server und die geschuetzte lokale Tokenuebergabe sind
in [INSTALLER_TRANSPORT.md](INSTALLER_TRANSPORT.md) beschrieben. Dies ist noch
keine produktive Dienstinstallation oder fertige HA-Einrichtung.


Der dauerhafte Wartungszustand vor Containerwechseln ist in [MAINTENANCE.md](MAINTENANCE.md) beschrieben. Host-Lifecycle und HA-Einrichtung bleiben offene Abnahmen.

[Transaktionaler Host-Lifecycle](HOST_LIFECYCLE.md): gepruefter Wechsel-/Rueckwegkern mit dauerhaftem Journal. Dockeradapter, Erstinstallation und HA-Verdrahtung bleiben offen.

### Fester Docker-Lifecycle-Adapter (synthetisch)

Der transaktionale Hostkern besitzt nun einen lokalen, fest konfigurierten
Dockeradapter mit begrenzten Prozessen, exakten Container-/Image-/Mount- und
Isolationsnachweisen, Wartungsmarkerbindung sowie TLS-/Worker-Healthvertrag.
Details und Grenzen stehen in [HOST_LIFECYCLE.md](HOST_LIFECYCLE.md).
Der Adapter ist noch nicht mit Installer, Hostdienst oder HA-Flow verdrahtet;
es wurde kein Container gestartet und container_deploy_ready bleibt false.
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

## Exklusiver Zielbetrieb

Das aktuelle Live-System behaelt ausschliesslich seinen vorhandenen nativen
Slicer; dort wird kein Docker-Compose-Test gestartet. Der getrennte saubere
Linux-Testserver erhaelt ausschliesslich den Docker-Compose-Slicer zusammen
mit Home Assistant Supervisor als Laborumgebung. Vor jeder Erstinstallation
blockiert ein read-only Clean-Host-Preflight bekannte native Units, Marker,
Prozesse und vorhandene Slicer-Container. Er bereinigt oder migriert nichts.
Die HAOS-Migration bleibt ein separater Plan und wird nicht ausgefuehrt.
