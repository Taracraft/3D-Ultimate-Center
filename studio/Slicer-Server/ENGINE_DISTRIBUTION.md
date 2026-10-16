# Vollständigen Engine-Bestand offline zusammenstellen

Stand: 16. Oktober 2026. `prepare_engine_distribution.py` verbindet die vorhandene
Katalogauswahl, begrenzte Archiventpackung und Dateiverifikation zu **einem
vollständigen Drei-Engine-Paket**. Das Werkzeug bearbeitet ausschließlich neue
lokale Ausgabeverzeichnisse. Es lädt nichts herunter, führt keine Engine aus und
aktiviert keinen laufenden Store, Container oder Supervisor-Dienst.

## Voraussetzung: tatsächliche geprüfte Eingaben

Der Katalog muss alle drei Familien als konkrete Releases enthalten: Bambu Studio,
PrusaSlicer und CuraEngine. Sein SHA-256-Wert kommt aus einem unabhängig
überprüften Liefernachweis. Der aktuell noch `pending` ausgelieferte Katalog ist
absichtlich keine ausreichende Eingabe und wird vor dem Anlegen einer Ausgabe
abgewiesen. Weder fehlende Familien noch fehlende Archive werden durch
Testdaten, andere Enginefamilien, Systemprogramme oder Netzwerkdownloads ersetzt.

Ein vollständiger Katalog ist eine Eingangsdeklaration, keine automatische
Herkunfts-, Rechts- oder Laufzeitfreigabe. Die Bindung der tatsächlichen
Originalmanifeste und die jeweils erforderlichen Quellen-/Lizenznachweise müssen
vor der echten Distribution getrennt vorliegen. Dieser Quellblock umgeht keinen
früher abgewiesenen Zugriff auf Originalarchive oder Originalmanifeste.

Die lokale Archivablage hat einen festen, nach Familie getrennten Aufbau:

```text
archive-cache/
  bambu_studio/<artifact-id>.archive
  prusaslicer/<artifact-id>.archive
  curaengine/<artifact-id>.archive
```

Jede im Katalog genannte Artefakt-ID muss im jeweiligen Familienverzeichnis
vorhanden sein. Ein Artefakt bleibt bytegenau sein ursprüngliches TAR.GZ-, TAR.XZ-,
TAR-, ZIP- oder Debian-Paket; die Endung `.archive` bedeutet keine Konvertierung.
Gleiche Artefakt-IDs verschiedener Familien sind durch die Verzeichnisse getrennt.
Zusätzliche unreferenzierte Dateien im Cache werden nicht übernommen.

## Ein Erzeugungsaufruf für den gesamten Bestand

```sh
python Slicer-Server/prepare_engine_distribution.py \
  --catalog /absolute/reviewed-catalog.json \
  --expected-catalog-sha256 "$CATALOG_SHA256" \
  --archive-root /absolute/archive-cache \
  --output /absolute/new-engine-distribution
```

Die Pfade müssen absolut sein. Die Ausgabe darf noch nicht existieren und muss
außerhalb des Produktquellbaums sowie außerhalb der Eingabeablage liegen. Der
Aufrufer schützt das übergeordnete Verzeichnis gegen fremde Änderungen. Auf POSIX
werden dessen Eigentümer und Schreibrechte geprüft; Symlinks und Windows
Junctions in Pfadketten werden abgewiesen. Eingabedateien mit zusätzlichen
Hardlinks werden nicht als stabile Archivquelle verwendet.

Vor der ersten Ausgabe werden Katalog und alle referenzierten lokalen Archive
vollständig auf ihre angegebenen Größen und Prüfsummen geprüft. Die drei
Enginefamilien durchlaufen anschließend die vorhandene Funktion
`package_staging.prepare_release`. Deren Archivpfad-, Größen-, Typ-, Datei- und
Entpackgrenzen gelten unverändert. Die bestehenden `_candidate`- und
`_validate_tree`-Prüfer aus `package_activation` kontrollieren die vorbereiteten
Dateien nochmals. Es wird kein zweiter unabhängiger Entpacker implementiert.

Fehlschläge bei einer späteren Familie, Abbruch, veränderte Eingaben oder eine
fehlgeschlagene Ausgabeprüfung entfernen nur das neu angelegte private
Arbeitsverzeichnis dieses Aufrufs. Bereits vorhandene Pakete, Eingaben und
aktive Engine-Stores bleiben unangetastet. Ein harter Prozessabbruch kann ein
unfertiges Verzeichnis hinterlassen; dessen bloße Existenz gilt niemals als
Fertigmeldung. Vor Verwendung ist immer die vollständige Prüfung notwendig.

## Erzeugte Struktur

```text
new-engine-distribution/
  CATALOG.json
  DISTRIBUTION.json
  READY.json
  engine-store.tar.gz
  engine/
    GENERATION.json
    bambu_studio/...
    prusaslicer/...
    curaengine/...
```

`CATALOG.json` erhält exakt die geprüften Eingabebytes. `GENERATION.json` verwendet
dasselbe deterministische Generationsformat und dieselbe Generations-ID wie der
bestehende Aktivierungsvertrag. `engine/` besitzt damit die festen Familien- und
Programmeinstiegspfade, die `container_engines.py` erwartet. Es gibt bewusst
keine `ACTIVE.json`, keine Dienständerung und keinen vorgetäuschten Worker-Stopp.
Die spätere Installation beziehungsweise Image-Integration muss ihren eigenen
Aktivierungs- und Isolationsvertrag weiterhin erfüllen.

Das TAR.GZ-Paket enthält ausschließlich den vollständigen Enginebestand sowie
Katalog, Generations- und Distributionsmetadaten. Enthaltene relative Lizenztexte
und Ressourcen bleiben erhalten; ursprüngliche nicht ausgewählte Archivdateien
werden nicht nachträglich als zusätzliche Nutzdateien übernommen. Es enthält
keine absoluten Cachepfade, Benutzerkonfiguration, lokalen Aufträge oder Secrets.

Dateien im TAR haben festgelegte Unix-Rechte: `0755` nur für die im Katalog
festgelegten Engine-Einstiegspunkte, sonst `0644`; Eigentümer-IDs und Zeitstempel
sind konstant. Pfade werden sortiert. Zwei Bauten aus identischen Eingaben mit
demselben Python-/zlib-Werkzeugstand liefern identische Archivbytes. Der konkrete
SHA-256-Wert des erzeugten Archivs und seine Größe stehen in `READY.json` und
werden zusätzlich vom Werkzeug ausgegeben.

## Unabhängige vollständige Rückprüfung

```sh
python Slicer-Server/prepare_engine_distribution.py \
  --verify /absolute/new-engine-distribution \
  --expected-catalog-sha256 "$CATALOG_SHA256"
```

Die Prüfung leitet die erwartete Generation, jede Datei und sämtliche Metadaten
neu aus dem extern gepinnten Katalog ab. Fehlende, zusätzliche oder verlinkte
Ausgabedateien und zusätzliche leere Verzeichnisse sind unzulässig.

Der Archivinhalt wird nicht nur gegen eine selbst angegebene Prüfsumme geprüft:
Das Werkzeug berechnet den kanonischen, unkomprimierten TAR-Bytestrom aus den
bereits verifizierten Quelldateien erneut und vergleicht ihn mit dem begrenzt
dekomprimierten tatsächlichen Archiv. Es interpretiert dabei keine fremden
Archivpfade und extrahiert nichts. Zusätzliche Gzip-Streams, abgeschnittene Daten,
falsche Inhalte und überschrittene Expansionsgrenzen werden abgewiesen.

Damit kann ein geändertes Archiv nicht allein durch das Mitschreiben eines neuen
Hashes in `READY.json` freigegeben werden. Eine andere zulässige Gzip-Kompression
desselben exakten TAR-Inhalts lässt sich dagegen prüfen, ohne vom Empfänger die
identische Kompressorversion zu verlangen. Für die Identität eines bestimmten
veröffentlichten Downloads bleibt dessen unabhängig veröffentlichte
Archivprüfsumme zusätzlich maßgeblich.

## Abnahmegrenzen

Das Ergebnis bestätigt vollständige Dateien und ein überprüftes Paket für die
angegebenen drei Releases. Es bestätigt **nicht**:

- tatsächliche CLI-Ausführung, ABI-/Plugin-Kompatibilität oder erfolgreiches Slicing;
- abgeschlossene entsprechende Quellen-/Lizenzpflichten;
- Supervisor-App-Isolation, Docker-Laufzeit oder eine Neuinstallation;
- einen veröffentlichten und vollständig freigegebenen Produktrelease.

Diese Grenzen stehen als falsche Freigabefelder in den abgeleiteten Metadaten.
Der Engine-Katalog und `SHIPPED_RELEASE` werden durch das Werkzeug nicht geändert.
Die unveränderte Compose-Isolation mit getrenntem API-/Worker-Betrieb wird nicht
aufgehoben. Ein bereits als bind mount eingebundenes `/engine` überlagert außerdem
einen etwaigen Imageinhalt; eine spätere Imageintegration muss diesen Mountvertrag
explizit behandeln und darf die fehlende Enginebereitstellung nicht verstecken.

Die Tests in `tests/test_studio_engine_distribution.py` verwenden synthetische
Archive aller drei Familien und den echten vorhandenen Entpacker. Sie vergleichen
den gesamten extrahierten Bestand, die Generation, Archivmitglieder und Modi,
zwei unabhängige Bauten sowie manipulierte und abgebrochene Abläufe. Es werden
weder echte Hersteller-Engines noch Modelle oder Drucker angesprochen.

Zugehörige Verträge: [Katalog](ENGINE_CATALOG.md),
[Einzelarchive](ENGINE_BUNDLE_BUILD.md), [Staging](PACKAGE_STAGING.md),
[Aktivierung](PACKAGE_ACTIVATION.md) und [Releasegrenzen](RELEASE_STATUS.md).
