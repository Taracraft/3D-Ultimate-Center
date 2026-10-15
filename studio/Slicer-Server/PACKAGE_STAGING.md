# Gepruefte Vorbereitung von Enginepaketen

Status: Download und isoliertes Archiv-Staging sind implementiert und statisch
geprueft. Der getrennte persistente Speicher-/Aktivierungsvertrag ist ebenfalls
implementiert; HA-Assistent und echte Releasefreigaben bleiben offen.
Alle drei echten Releases in engine_catalog.json bleiben pending.

## Aufruf und Verantwortungsgrenze

package_staging.prepare_release(release, parent, archives=None, cancelled=None)
ist eine interne Installer-Schnittstelle. Sie erhaelt einen bereits aus dem
vertrauenswuerdig ausgelieferten Katalog ausgewaehlten Release. Die Struktur
wird erneut validiert; diese Validierung bestaetigt keine Herkunftsfreigabe.
Eine spaetere HA-Anfrage darf nur feste IDs auswaehlen, keine Releaseobjekte,
Archivpfade, URLs oder Befehle vorgeben.

Ohne archives erfolgt der Download. Optional bezeichnet archives eine exakte
Zuordnung aller Artefakt-IDs zu lokalen Cachedateien. Auch Cachedateien werden
vollstaendig anhand Groesse und SHA-256 geprueft und in den eigenen Bereich kopiert.

Der Aufruf erzeugt ein neues privates Unterverzeichnis mit payload/<engine>
und schreibt READY.json erst nach Abschluss aller Artefakte. prepared bedeutet
nur geprueft vorbereitet: activated=false und engine_executed=false.
Es wird kein Dienst gestartet, kein Paketmanager aufgerufen und kein Skript
aus dem Archiv ausgefuehrt. Auch ein vollstaendiger Zwischenbereich ist noch
keine installierte oder betriebsbereite Engine.

Der Aufrufer muss den Elternordner vor fremden Schreibzugriffen schuetzen und
stabil halten. Symlinks/Junctions in diesem Pfad werden abgewiesen; unter Linux
sind eigener Besitzer und keine Schreibrechte fuer Gruppe/Andere erforderlich.
Eine Windows-ACL-Pruefung wird damit nicht behauptet. Gegen einen gleichzeitig
eingreifenden privilegierten Prozess bietet dieser Vertrag keinen Schutz.

## Downloadvertrag

- Nur die festen HTTPS-Quellen des validierten Katalogs; Zertifikat und
  Hostname werden geprueft. Keine automatischen Proxys, Cookies oder Credentials.
- HTTP 200 erforderlich. Alle Weiterleitungen werden abgewiesen; insbesondere
  sind GitHub-Asset-Weiterleitungen noch nicht freigegeben.
- Identitaetskodierung, eindeutige Laengen-/Transferheader und exakte erwartete
  Downloadgroesse. Daten werden in begrenzten Bloecken geschrieben und gehasht.
- 20 Sekunden Socket-Timeout; kooperatives Gesamtbudget von 1800 Sekunden pro
  Aufruf. Abbruch und Zeitbudget werden zwischen Verarbeitungsschritten geprueft.
  Dies ist keine harte Prozessfrist und keine garantierte DNS-Zeitbegrenzung.
- Fehler liefern feste Codes statt Rohantworten oder lokaler Pfade. Kein
  automatischer Wiederholungssturm; ein neuer Aufruf startet einen neuen Versuch.

## Archivpfad und Zielpfad

FileSpec kann zusaetzlich archive_path enthalten. path bleibt der Zielpfad
relativ zur festen Enginewurzel. Ohne archive_path gilt derselbe relative Pfad
auch im Archiv; bestehende Kataloge bleiben lesbar. Doppelte Archivquellen,
kollidierende Ziele und mehrdeutige Gross-/Kleinschreibung werden abgewiesen.

Nur explizit ausgewaehlte regulaere Dateien werden geschrieben. Ihr Inhalt muss
exakt zur Dateigroesse und SHA-256 aus dem Manifest passen. Fehlende Dateien,
doppelte Archiveintraege, Traversal und ausgewaehlte Links scheitern.
Nicht ausgewaehlte regulaere Dateien und Links werden nicht materialisiert
oder verfolgt. Geraete/Sonderdateien werden abgewiesen. Archiv-Rechte,
Eigentuemer und privilegierte Modusbits werden nicht uebernommen.
Zieldateien erhalten 0644, der deklarierte Engineeinstieg 0755.
Es gibt kein extractall und keine automatische Desktopinstallation.

## Formate und Grenzen

| Bereich | Unterstuetzung / Grenze |
| --- | --- |
| TAR | regulaere POSIX-Header und begrenzte GNU-Langnamen |
| Kompression | unkomprimiert, gzip oder XZ; genau ein komprimierter Stream |
| Debian | Format 2.0, drei ar-Mitglieder, data.tar beziehungsweise .gz/.xz |
| Debian-Steuerteil | wird uebersprungen, niemals entpackt oder ausgefuehrt |
| ZIP | einzelnes Archiv, Stored/Deflate, ohne Verschluesselung oder ZIP64 |
| Download | maximal 2 GiB pro Artefakt nach Katalog |
| TAR-Ausgabe / deklarierter Inhalt | maximal 2 GiB pro Artefakt |
| Einzeldatei | maximal 512 MiB |
| Eintraege / physische TAR-Header | maximal 100000 pro Artefakt |
| XZ-Dekompressorspeicher | maximal 256 MiB |
| ZIP-Zentralverzeichnis | maximal 16 MiB vor Metadatenaufbau |
| GNU-Langnameneintrag | maximal 1024 Bytes, danach normale Pfadpruefung |

PAX, sparse TAR, GNU-Langlinkmetadaten, zstd und weitere Debian-Erweiterungen
bleiben explizit nicht unterstuetzt. Ein kuenftiges Paket muss dazu passend
kuratiert oder der jeweilige Formatvertrag gezielt erweitert und getestet werden.
Die Staging-Grenzen sind teilweise strenger als die allgemeinen Kataloggrenzen.

## Fehler und Wiederaufnahme

Bei einem normalen Fehler oder kooperativen Abbruch wird ausschliesslich das
selbst erzeugte Zwischenverzeichnis entfernt. Vorhandene Daten und erfolgreiche
andere Vorbereitungen bleiben erhalten. Ein harter Prozessabbruch kann einen
verwaisten Ordner hinterlassen. Ohne READY.json darf er nicht aktiviert werden;
auch mit dieser Datei ist vor Aktivierung das gesamte Manifest erneut zu pruefen.
Crashfeste Aktivierung, Orphan-Bereinigung, Serialisierung, Speicherreservierung
und Wiederaufnahme ueber Prozessgrenzen gehoeren in die kommende Transaktion.

## Verifizierter Stand

Am 11.10.2026: 64 gezielte PC-Tests bestanden, eine reine POSIX-Rechtepruefung
unter Windows ausgelassen, 129 Teilpruefungen bestanden. Die 37 neuen
Staging-Tests bestehen unter Linux ohne Auslassung. Geprueft sind unter anderem
Formatvarianten, manipulierte Pfade/Digests/Groessen, fehlende Dateien,
Links, begrenzte Dekompression, Abbruch, Netzwerkfehler und Redirect-Ablehnung.

Der neue Downloadpfad hat Cura 5.0.0-6 auf beiden Plattformen per TLS geladen.
Auswahl: die zuvor geprueften 861 Definitions-/Extruderdateien plus Lizenztext,
zusammen 862 Dateien und 1896942 Bytes. Der Definitionsgraph bleibt gueltig.
Aus dem bereits geprueften Prusa-Archiv 2.9.2+dfsg-1 wurden CLI, OCCTWrapper.so,
37 INI-Dateien und Lizenztext ausgewaehlt: 40 Dateien, 40051687 Bytes.
Dateimanifeste und statischer Gesamtbeleg sind nach plattformunabhaengiger
Pfadsortierung bytegleich. Keine Engineausfuehrung, keine Releasefreigabe.

Der echte Cura-Test machte GNU-Langnamen sichtbar. Die begrenzte Verarbeitung
wurde ergaenzt und mit ausgewaehlten, manipulierten und unvollstaendigen Namen
getestet. Es wurden keine Archiv-Quelldateien korrigiert oder Filter gelockert.
Die echten Archivtests verwenden die unteren Download-/Extraktionsbausteine;
mangels freigegebener Herkunfts-/Lizenzmetadaten wird daraus kein gueltiger
Release erfunden. Der komplette prepare_release-Ablauf ist synthetisch geprueft.

## Naechster Installationsschritt

1. [Persistenten Speicher und Aktivierung](PACKAGE_ACTIVATION.md) in den
   begrenzten Host-Installer einbinden und den exakten aktiven Generationspfad
   bei gestopptem Worker an Compose uebergeben.
2. Quellrevisionen, Herkunft, Lizenzen/SBOM, Ressourcen, Profile und Ladepfade
   aller drei Engines fuer echte Katalogfreigaben abschliessen.
3. Begrenzten Host-Installer beziehungsweise Supervisor-Verpackung mit dem
   HA-Assistenten verbinden; Neuinstallation, Upgrade und Restore abnehmen.

Diese Module bleiben beim Installer. API-/Worker-Image und dessen Netzisolation
wurden nicht geaendert. Docker-Betriebsfreigabe bleibt container_deploy_ready=false.
