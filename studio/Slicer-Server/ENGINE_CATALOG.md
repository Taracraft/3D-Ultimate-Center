# Enginekatalog fuer die HA-Installation

Status: Katalogvertrag, begrenzter Download, manifestgeprueftes Staging und
transaktionale Generationsaktivierung sind implementiert. Noch keine
freigegebenen Downloadpakete oder fertige HA-Installation.

## Was bereits funktioniert

engine_catalog.py liest ausschliesslich einen vertrauenswuerdig ausgelieferten
Katalog, prueft dessen Struktur und liefert unveraenderliche Installationsplaene.
Die kuenftige HA-Anfrage waehlt nur eine bekannte Engine-ID und die Zielplattform.
Sie darf weder einen eigenen Katalog noch eine URL oder einen Befehl liefern.

engine_catalog.json nennt alle drei Familien explizit als pending. select()
weist sie mit engine_not_approved ab. Es gibt keine erfundenen Downloadadressen,
Digests oder Freigaben im ausgelieferten Katalog. Synthetische Beispiele stehen
ausschliesslich in den Tests und duerfen nicht als Releasepakete verwendet werden.

Unterstuetzter Vertragsumfang ist vorerst Linux/amd64. Andere Architekturen
werden explizit abgewiesen, bis Bibliotheken und Enginepakete abgenommen sind.

## Datenvertrag

| Ebene | Pflichtangaben |
| --- | --- |
| Katalog | schema als Ganzzahl, releases, pending; jede der drei Familien genau einmal |
| Release | engine, feste version, system, architecture, vollstaendiger artifacts-Satz |
| Artefakt | id, component_version, url, sha256, size_bytes, format, license, source_url, source_revision, files |
| Datei | relativer Zielpfad path, sha256, size_bytes, role, executable; optional archive_path |

Ein Release bindet Engine, Ressourcen und Profile als gemeinsamen Satz.
component_version dokumentiert gegebenenfalls eine abweichende Ressourcen-
Paketversion; ihre Kompatibilitaet muss vor Aufnahme in den Katalog belegt werden.
Ein Versionsstring allein beweist diese Kompatibilitaet nicht.

Jeder Pfad gilt relativ zur festen Familienwurzel aus ENGINE_LAYOUT.md.
Die Rollen sind engine, runtime, resources, profiles und license.
Jedes Artefakt muss eine nichtleere Lizenzdatei enthalten. Die Dateiliste
beschreibt die nach Extraktion zu erwartenden regulaeren Dateien; Archive
duerfen spaeter weder weitere Dateien noch Links/Geraete/Installationsskripte
ungeprueft aktivieren. Die begrenzte Auswahl und Integritaetspruefung sind in
[PACKAGE_STAGING.md](PACKAGE_STAGING.md) beschrieben; Aktivierung bleibt offen.

| Engine | Strukturelle Mindestanforderungen |
| --- | --- |
| bambu_studio | bin/bambu-studio; Ressourcen und JSON-Profile unter resources/profiles/ |
| prusaslicer | bin/prusa-slicer; Ressourcen, INI-Profile und OCCTWrapper.so als Laufzeitmodul |
| curaengine | bin/CuraEngine; Ressourcen und *.def.json unter resources/definitions/ |

Diese Mindestanforderungen erkennen unvollstaendige Paketplaene. Sie sind
keine Pruefung der Profilinhalte, Vererbungen, Plugin-Ladepfade, ABI oder echten
Slicing-Funktion. Die kuenftigen Paketadapter muessen diese Luecken schliessen.

## Eingabe- und Integritaetsgrenzen

- Unbekannte Felder, doppelte JSON-Schluessel, doppelte Releases/Artefakte,
  fehlende Familien und widerspruechliche Freigabezustaende werden abgewiesen.
- Feste SHA-256-Digests und Groessen fuer Archiv und jede erwartete Datei;
  keine beweglichen Versionsbezeichnungen wie latest oder nightly.
- HTTPS-Quellen nur aus fest vorgegebenen Hersteller-/Projekt-Releasepfaden
  oder dem Debian-Paketpool; Herkunft separat an die Enginefamilie gebunden.
  Keine Zugangsdaten, Queryparameter, Fragmente, Escape-Sequenzen oder
  Traversalbestandteile in URLs. Die Liste ist keine Downloadfreigabe.
- Relative Dateipfade ohne Traversal, Windows-Pfadvarianten, Streams oder
  kollidierende Datei-/Verzeichnisziele; keine weiteren ausfuehrbaren
  Einstiegsskripte als der feste Programmeinstieg.
- Grenzen: 4 MiB Katalog, 16 Artefakte je Release, 2 GiB je Downloadartefakt,
  insgesamt 100000 Dateien und 8 GiB entpackte Dateien je Release.
  Das ist keine Speicherplatzreservierung fuer Download, Staging und Backup.
- verify_artifact() prueft einen begrenzt gelesenen Bytestrom auf exakte
  Laenge und SHA-256. Abbruch, zusaetzliche Bytes oder falscher Digest scheitern.
  Die Funktion schreibt nichts und startet keine Engine.

Ein Digest aus derselben untrusted Quelle ist kein Herkunftsnachweis.
Die Vertrauenswuerdigkeit des ausgelieferten Katalogs, Release-Signaturen,
unabhaengige Herkunftsverifikation, Lizenzfreigabe und SBOM bleiben eigene
Releaseanforderungen. Ein erfolgreich geparster Testkatalog ist keine Freigabe.

## Naechste Umsetzung

1. Tatsaechliche headless Paketsaetze fuer die drei Familien kuratieren:
   Archive und Quellrevisionen unabhaengig verifizieren, Lizenztexte aufnehmen,
   Datei-Digests erzeugen, Ressourcen/Profile und Pluginpfade pruefen.
2. Implementierten Download/Staging an den Installationsablauf anbinden.
   Ein einzelner GitHub-Asset-Wechsel ist jetzt streng begrenzt implementiert;
   Ketten, fremde Zielhosts und sonstige Weiterleitungen bleiben gesperrt.
3. Den implementierten [Speicher- und Aktivierungsvertrag](PACKAGE_ACTIVATION.md)
   an den begrenzten Host-Installer und dessen eindeutigen Worker-Stop anbinden.
4. Begrenzte Installer-Operationen an den HA-Assistenten anbinden und
   Neuinstallation, Upgrade, Abbruch/Restore und autorisiertes Slicing abnehmen.

Das Modul liegt beim kuenftigen Installer. Es wird noch nicht in den API-/Worker-
Imagekontext kopiert: Der Worker soll keine Downloads oder Installation erhalten.
Der bestehende Docker-Dienstkandidat und seine native Rueckfallinstallation
werden durch diesen Katalogschritt nicht umgeschaltet.


[Statische Ressourcenpruefung](RESOURCE_VALIDATION.md): Cura-Vererbungsgraph,
Extruderreferenzen und Dateiintegritaet sind pruefbar. Echte Cura-/Prusa-Archive
wurden untersucht; mehrdeutige Cura-Daten bleiben gesperrt. Der gepruefte
Teilbestand ist noch kein freigegebenes Installations- oder Druckerpaket.


[Download und Paket-Staging](PACKAGE_STAGING.md): begrenzter TLS-Download,
Archivpfad-Zuordnung und Dateipruefung sind implementiert. Aktivierung,
Speichervertrag und HA-Assistent bleiben offen; alle Katalogreleases pending.

## Aktueller Provenienzvertrag

Die aktuell statisch belegten Archive, Dateimanifeste, Paketversionen, direkten ELF-Abhaengigkeiten und offenen Lizenzgrenzen stehen in [ENGINE_PROVENANCE.md](ENGINE_PROVENANCE.md). Der Vertrag ist fail-closed: Alle drei Releases bleiben pending; weder ein vorhandener Hash noch ein erfolgreicher statischer Bibliotheksabschluss setzt release_approved, legal_approved oder container_deploy_ready.

Vor jeder spaeteren Freigabe muessen Herkunft und Quellrevision, Lizenz-/Notice-Closure, transitive Laufzeitbibliotheken, Profile/Ressourcen/Plugins, SBOM sowie die getrennten realen Installations- und Laufzeitabnahmen erneut gegen die eingefrorenen Artefakte geprueft werden.


## Begrenzter GitHub-Asset-Download

Der Katalog speichert weiterhin ausschliesslich feste Release-URLs ohne
Queryparameter, Zugangsdaten oder bewegliche Versionsmarker. Nur der interne
Downloader darf einen einmaligen HTTP302-Wechsel einer solchen erlaubten
GitHub-Releaseadresse annehmen: exakte HTTPS-Asset-Domain, begrenzter
Release-Asset-Pfad, eindeutiger Location-Header und kein weiterer Hop.
Die temporaere signierte Zieladresse ist kein neuer Katalogeintrag und wird
nicht im READY-Beleg gespeichert. Abbruch, Gesamtfrist, Archivgroesse und
SHA-256 bleiben ueber beide Verbindungen unveraendert gebunden.
Details: [Download-/Stagingvertrag](PACKAGE_STAGING.md).

Dies erweitert weder die echten Katalogfreigaben noch unterstuetzte
Archivformate. AppImages werden nicht ausgefuehrt; eine geeignete
manifestgebundene Archivauswahl muss gesondert kuratiert werden. Alle drei
ausgelieferten Enginefamilien bleiben pending.


## Dediziertes Slicer-Release-Repository (15.10.2026)

Der vorhandene begrenzte Downloadvertrag akzeptiert jetzt auch exakt
https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/
als erste Quelle fuer gepruefte Releaseartefakte. Das Studio-Repository und
die bisherigen Hersteller-/Debian-Urspruenge bleiben erhalten. Dies ist
keine Freigabe beliebiger GitHub-Repositories: Owner, Repository, HTTPS
und Releasepfad bleiben fest; Querys, Zugangsdaten, andere Ports,
Namensverwechslungen und Traversal sind weiterhin unzulaessig.

Die Herkunft der enthaltenen Engine bleibt unabhaengig an die bisherige
Hersteller-Quellrevision gebunden. Das eigene Download-Repository darf
nicht die source_url oder source_revision der Engine ersetzen. Vollstaendige
Archiv-/Dateihashes, Groessen, Lizenz- und Profilangaben bleiben erforderlich.
Alle drei echten Katalogfamilien bleiben pending, bis ihre Paketsaetze
tatsaechlich bereitstehen. Ein akzeptierter Downloadursprung ist kein
veroeffentlichtes Artefakt und keine technische oder rechtliche Enginefreigabe.


## Dateiauswahl aus vorhandenen Engine-Archiven

`prepare_catalog_selection.py` verbindet das vorhandene Bundlemanifest mit
dem bestehenden Katalog- und Stagingvertrag. Es baut keine Enginearchive neu,
veraendert keine Originalmanifeste und schaltet keine Engine im ausgelieferten
`engine_catalog.json` frei. Die erwartete Manifestpruefsumme muss aus einem
unabhaengig geprueften Build-/Lieferbeleg kommen.

```sh
python Slicer-Server/prepare_catalog_selection.py \
  --manifest bundle-manifest.json \
  --expected-manifest-sha256 "$MANIFEST_SHA256" \
  --output /absolute/new/private-selection
```

Das neue, ausserhalb des Produktquellbaums liegende Ausgabe-Verzeichnis darf
noch nicht existieren. Es enthaelt nur `file-selection.json`, keinen aktiven
Installationskatalog. Die Quellbytes werden vor und nach der Ausgabe geprueft.
Dateinamen, Groessen, Pruefsummen und Ausfuehrungskennzeichen aller Eintraege
bleiben erhalten. Die Ausgabe enthaelt keine lokalen Wurzelverzeichnisse.

### Cura-Basisdefinition: Rolle statt Archivinhalt korrigieren

Im erfassten Cura-Bestand sind alle861Definitionsdateien als `profiles`
klassifiziert, obwohl der unveraenderte Katalog getrennt Ressourcen verlangt.
Die Datei `resources/definitions/fdmprinter.def.json` ist die Basisdefinition
mit allgemeinen Einstellungen. Ausschliesslich dieser exakte, nichtleere,
nichtausfuehrbare Eintrag darf von `profiles` nach `resources` abgebildet
werden. Die Aenderung wird mit Pfad, Ursprung/Ziel, Groesse und SHA protokolliert.
Bereits passende `resources` bleiben unveraendert; andere Rollen, eine fehlende
Basisdefinition oder das Fehlen weiterer Profile werden abgewiesen.

Bambu- und Prusa-Rollen bleiben unveraendert. Alle drei Familien verwenden
dieselben vorhandenen Bundle-, Katalog-Datei- und portablen Zielpfadpruefer.
`bind_release(...)` ergaenzt ausdruecklich bereitgestellte Artefaktmetadaten und
verwendet den vollstaendigen vorhandenen Katalogverifikator. Version, Herkunft,
Downloadadresse, Archivpruefsumme und Lizenzdeklaration werden nicht erfunden.
Der Prusa-OCCT-Vertrag und alle bestehenden Kataloggrenzen bleiben bestehen.

### Anschluss an das vorhandene Staging

Die Katalogauswahl kann das bestehende `prepare_release` verwenden. Das
urspruengliche `bundle-manifest.json` im Archiv bleibt gewoehnliche, nicht
ausgewaehlte Metadatei; es wird weder ausgefuehrt noch als Engine-Payload
installiert. Die ausgewaehlten Nutzdateien werden weiterhin gegen Archiv-
und Dateihashes geprueft. Rollen in der Auswahl sind installerbezogene
Metadaten und kein Anlass, das unveraenderte Originalarchiv neu zu packen.

Die Regressionen gehen fuer alle drei Familien mit synthetischen TAR.GZ-
Archiven durch den unveraenderten Katalog und den echten lokalen Entpacker.
Sie vergleichen anschliessend die vollstaendigen Nutzdateibytes und pruefen
den unveraenderten Archivhash sowie `activated=false`/`engine_executed=false`.
Sie fuehren kein echtes Slicing durch und sind keine Pruefung der realen
Engine-Binaries. Eine weitere synthetische Matrix bildet861Cura-Definitionen
auf860Profile plus eine Ressource ab; diese Zahlen sind kein erzeugter
Auslieferungsnachweis fuer ein Originalarchiv.

### Noch getrennt nachzuweisen

Ein als gueltig erkanntes Dateischema ist weder Archiv- noch Herkunfts-/
Lizenz- oder Betriebsfreigabe. Die drei vollstaendigen Originalmanifeste
mussen am zulaessigen lokalen Pruefort gegen ihre unabhaengigen Hashes
verarbeitet und mit den tatsaechlich veroeffentlichten Artefaktmetadaten
gebunden werden. Bis dahin bleibt der ausgelieferte Katalog `pending`.
Die normale Auswahl-CLI meldet deshalb `archive_verified=false`,
`catalog_updated=false` und `release_approved=false`. Sie kontaktiert
keinen Host, kein GitHub, keinen Drucker und startet keine Engine.
