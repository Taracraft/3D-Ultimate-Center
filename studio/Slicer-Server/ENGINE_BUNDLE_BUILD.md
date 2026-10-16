# Konkrete Engine-Archive aus geprueften Dateien bauen

build_engine_bundle.py erzeugt deterministische TAR/GZip-Archive fuer Bambu
Studio, PrusaSlicer oder CuraEngine. Es verpackt tatsaechliche Programmdateien,
Bibliotheken, Profile, Ressourcen und Lizenztexte; es startet keine dieser
Dateien. Der Build installiert keine Engine oder Dienste und aendert den
freigegebenen Enginekatalog nicht.

## Eingaben

Ein privates Inventar enthaelt schema=1, engine, version, upstream_archives
und files. Jede Ursprungsarchivzeile bindet id, SHA-256 und Bytezahl. Jede
Dateizeile bindet einen lokalen root-Alias, einen relativen source-Pfad,
einen relativen Zielpfad path, sha256, bytes, role und executable. Die
separate Roots-Datei ordnet die Aliase administrativ geprueften lokalen
Verzeichnissen zu. Private absolute Quellpfade gelangen nicht ins Paket.

Zugelassene Rollen: engine, runtime, resources, profiles, license und source.
Genau eine Engine-Datei muss zum festen Einstieg passen: bin/bambu-studio,
bin/prusa-slicer oder bin/CuraEngine. Profile, Ressourcen und mindestens ein
nichtleerer Lizenztext sind Pflicht. Diese strukturelle Pruefung behauptet
keine abgeschlossene Lizenzpflichten- oder Laufzeitabnahme.

```bash
python Slicer-Server/build_engine_bundle.py --inventory inventory.json --roots roots.json --output ../engine-bundle
```

Das Ziel muss neu sein und darf nicht innerhalb einer Quellwurzel liegen.
Der Builder verweigert Links, Spezialdateien, unbekannte Felder, doppelte
oder kollidierende Zielnamen, absolute Pfade, Traversal und unpassende
Dateigroessen. Quellidentitaeten werden vor und nach dem Lesen verglichen.
Dateihashes werden beim Schreiben und erneut aus dem fertigen Archiv geprueft.

## Ausgaben und Reproduzierbarkeit

Das Ergebnis enthaelt das versionsneutral benannte Engine-TAR/GZip-Archiv,
bundle-manifest.json, SHA256SUMS und BUILD_RESULT.json. Archivdateien sind
sortiert, mit festen Unix-Modi, leeren Eigentuemernamen, UID/GID 0 und
Zeitstempel 0 versehen. Auch der GZip-Zeitstempel ist fest. Ein zweiter Build
mit denselben Bytes und derselben Python/zlib-Toolchain liefert identische
Archivbytes. GNU-TAR-Langnamen werden verwendet, keine PAX-Metadaten.

Ein fehlgeschlagener Build laesst nur seinen neu angelegten Ausgabeordner zur
Diagnose zurueck. Vor vollstaendiger Rueckpruefung existiert ausschliesslich
.archive-incomplete, kein als erfolgreich markiertes Archiv. Bestehende
Ausgabeordner oder Quelldateien werden nicht ersetzt oder geloescht.

## Freigabegrenze

Ein echter Binaerbestand im Archiv ist ein Fortschritt gegenueber reinen
Quell- oder Testpaketen, jedoch kein Nachweis seiner Startfaehigkeit. Die
Manifeste behalten release_approved=false, runtime_approved=false und
license_review_complete=false. Die im Zielimage bereitgestellten dynamischen
Bibliotheken, konkrete Plugin-/Profilkompatibilitaet, Quellbereitstellung und
zugehoerige Lizenzpflichten muessen separat dem Bestand zugeordnet werden.
Diese Angaben werden nicht aus erfolgreichen Pakettests abgeleitet.

Die abschliessende Neuinstallation bleibt gemaess Projektauftrag der letzte
Verifikationstest. Der Paketbauer fuehrt diesen Test nicht aus und beruehrt
weder das bestehende native Live-Slicing noch Home-Assistant-Einstellungen.

Technische Referenz: https://docs.python.org/3/library/tarfile.html


## Drei geprüfte Familien als gemeinsames Auslieferungspaket

Die neue [Offline-Distributionsbildung](ENGINE_DISTRIBUTION.md) verwendet die
vorhandenen Katalog-/Staging-/Generationsprüfer für einen gemeinsamen Bestand
aus Bambu Studio, PrusaSlicer und CuraEngine. Sie übernimmt nur einen extern
gepinnten vollständigen Katalog und die angegebenen lokalen Archivbytes.
Fehlende oder noch `pending` Familien verhindern jede fertige Ausgabe.
Originalarchive bleiben unverändert; kein Download, Engineaufruf, Aktivieren
oder Supervisor-Vorgang. Das daraus erzeugte Archiv und jede Nutzdatei werden
inhaltsgebunden zurückgeprüft. Ein Dateipaket ist weiterhin keine Engine-,
Lizenz- oder Produktreleasefreigabe.
