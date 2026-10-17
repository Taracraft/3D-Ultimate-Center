# Enginebestand in einen vollständigen Imagekontext übernehmen

`prepare_runtime_context.py` verbindet einen bestehenden geprüften
Source-Kontext mit einer vollständig zurückgeprüften Drei-Engine-Distribution.
Es erzeugt den Buildkontext, einen lesenden Image-Dateicheck und eine vollständige
Compose-Datei, deren API und Worker den im Image enthaltenen Enginebestand nutzen.
Das Werkzeug startet weder Docker noch eine Engine, einen Worker oder Aufträge.

## Eingaben festlegen

Zuerst die vorhandenen Werkzeuge
[Source-Kontext](README.md) und
[Engine-Distribution](ENGINE_DISTRIBUTION.md) verwenden. Der ausgelieferte
`pending`-Enginekatalog genügt nicht: Alle drei konkreten Releases samt Dateien,
Ressourcen und Lizenztexten müssen tatsächlich vorhanden sein.

Vier unabhängig überprüfte SHA-256-Werte sind erforderlich:

| Wert | Bindung |
| --- | --- |
| `SOURCE_MANIFEST_SHA256` | `context-manifest.json` des Source-Kontexts |
| `SOURCE_DOCKERFILE_SHA256` | unveränderter `Dockerfile` dieses Kontexts |
| `CATALOG_SHA256` | Katalog der geprüften Engine-Distribution |
| `COMPOSE_SHA256` | geprüfte `compose.candidate.yaml` mit explizitem Wartungsprofil |

Die Werte kommen aus dem eigenen geprüften Liefernachweis. Sie werden nicht aus
einer selbst deklarierten Freigabe oder einem veränderlichen Downloadnamen
abgeleitet. Originalkontexte, Distribution und Compose-Datei bleiben unverändert.
Alle Eingabe- und Ausgabepfade müssen absolut, ohne symbolische Links oder
Junctions und voneinander getrennt sein. Das Ziel darf nicht existieren und sein
übergeordnetes Verzeichnis muss dem Aufrufer gehören und gegen fremde
Schreibzugriffe geschützt sein.

```sh
python Slicer-Server/prepare_runtime_context.py \
  --source-context /absolute/source-context \
  --engine-distribution /absolute/engine-distribution \
  --compose /absolute/compose.candidate.yaml \
  --output /absolute/new-runtime-context \
  --expected-source-manifest-sha256 "$SOURCE_MANIFEST_SHA256" \
  --expected-source-dockerfile-sha256 "$SOURCE_DOCKERFILE_SHA256" \
  --expected-catalog-sha256 "$CATALOG_SHA256" \
  --expected-compose-sha256 "$COMPOSE_SHA256"
```

Das Werkzeug verwendet die vorhandene Distributionsprüfung einschließlich
Prüfung des vollständigen kanonischen Archivinhalts. Es implementiert keinen
weiteren Entpacker. Anschließend kopiert es nur die bereits geprüften regulären
Dateien. Das Distributionsarchiv wird nicht in das Image dupliziert.

## Ausgabe und Rückprüfung

Der neue Kontext enthält den unveränderten Source-Kontext unter `source/`, den
Enginebaum unter `engine/`, Katalog und abgeleitete Quellen-/Lizenzmetadaten unter
`engine-distribution/`, den angepassten Dockerfile sowie `image-manifest.json` und
`runtime_image_check.py`. `compose.source.json` bewahrt die exakten gepinnten
Compose-Eingabebytes; `compose.runtime.yaml` ist die daraus erzeugte vollständige
Laufzeitkonfiguration. `runtime-context.json` bindet jeden ausgegebenen Dateihash
und die erwarteten Unix-Dateirechte.

Die Ausgabe entsteht zunächst in einem privaten Zwischenverzeichnis desselben
Dateisystems. Alle Dateien, Metadaten und Verzeichnisse werden überprüft und
gesichert, bevor das Verzeichnis exklusiv atomar an seinen endgültigen Namen
verschoben wird. Ein inzwischen angelegtes Ziel wird niemals ersetzt. Unterstützt
werden Windows und Linux mit `renameat2(RENAME_NOREPLACE)`; fehlt diese sichere
Operation, schlägt der Abschluss fehl. Nach hartem Prozessabbruch kann ein
verborgenes Zwischenverzeichnis verbleiben; daraus keine fertige Ausgabe ableiten.

```sh
python Slicer-Server/prepare_runtime_context.py \
  --verify /absolute/new-runtime-context \
  --expected-source-manifest-sha256 "$SOURCE_MANIFEST_SHA256" \
  --expected-source-dockerfile-sha256 "$SOURCE_DOCKERFILE_SHA256" \
  --expected-catalog-sha256 "$CATALOG_SHA256" \
  --expected-compose-sha256 "$COMPOSE_SHA256"
```

Die Rückprüfung leitet alle erwarteten Metadaten und Dateiidentitäten erneut aus
den vier extern gepinnten Eingaben ab. Geänderte Enginebytes können nicht durch
ein gleichzeitig geändertes `runtime-context.json` legitimiert werden. Fehlende,
zusätzliche, verlinkte oder mehrfach hartverlinkte Dateien sowie zusätzliche
leere Verzeichnisse werden abgewiesen. Auch Dockerfile, Compose-Ausgabe,
Image-Dateimanifest und Quellenreferenzen sind gebunden.

## Image- und Mountvertrag

Der generierte Dockerfile übernimmt die bisherigen Bibliotheksinstallationen,
FHS-Ressourcenlinks und den unveränderlichen Python-Basisparameter. Er kopiert
den Enginebaum nach `/engine` und die Distributionsmetadaten nach
`/usr/share/ultimate-slicer-server/runtime/engine-distribution`. Ein fester
Buildschritt setzt die im erzeugten Image-Dateimanifest angegebenen Modi, auch
bei einem unter Windows vorbereiteten Kontext, und prüft die kopierten Dateien.
Dabei wird ausschließlich Python-Dateiprüfcode ausgeführt.

Der Standard-Imagebefehl bleibt ein lesender Dateicheck. Er meldet
`engine_included=true`, wenn Source-, Engine- und Metadatenbestand vollständig
und unverändert sind; `engine_executed`, `runtime_approved` und
`license_review_complete` bleiben falsch. Der ursprüngliche Source-Checker bleibt
unverändert und beschreibt weiterhin ausschließlich den Source-Kontext.

`compose.runtime.yaml` entfernt ausschließlich die beiden schreibgeschützten
`/engine`-Bind-Mounts von API und Worker. Die erzeugte Datei ist vollständig und
ersetzt für diesen Imagepfad die Candidate-Datei; sie ist **kein Compose-Overlay**.
Ein Overlay mit der ursprünglichen Datei könnte den Engine-Mount wieder einführen
und dadurch den Imagebestand verdecken. `SLICER_ENGINE` wird für diesen Pfad nicht
mehr benötigt. Daten, Profile, Token, TLS, Ports, Abhängigkeiten und das explizite
Wartungsprofil bleiben erhalten. Der Worker behält `network_mode: none`, den
gemeinsamen API-PID-Namensraum, den nicht privilegierten Benutzer und sämtliche
bestehenden Schutzoptionen. Zusätzliche Mounts oder abweichende Schutzverträge
werden vor der Ausgabe abgewiesen.

Für einen eigenen Imagebau weiterhin ausschließlich die geprüfte unveränderliche
Basis und den geprüften neuen Kontext verwenden. Aufbau, isolierter Start,
TLS-Verbindung und Betrieb folgen
[RUNTIME_INSTALLATION.md](RUNTIME_INSTALLATION.md). Das Wartungsende bleibt eine
gezielte einmalige Aktion; die Erstellung dieses Kontexts löst es nicht aus.

## Was damit belegt ist

Der Nachweis betrifft vollständige Dateien, deren Provenienzbindungen und den
korrekten Übergang von externem Engine-Mount zu Enginebestand im Image. Er belegt
keine tatsächliche ABI-/Plugin-Kompatibilität, keine Engineausführung, keinen
Imagebuild, keine Installation und keine Supervisor-App. Entsprechende Quellen-
und Lizenzpflichten bleiben unabhängig zu prüfen; die kopierten Referenzen
behaupten keine erledigte Lizenzabnahme. Es wird kein vorgetäuschter ausgelieferter
Enginekatalog und keine Supervisor-Release-Referenz eingetragen.

`tests/test_studio_runtime_context.py` verwendet ausschließlich synthetische
Archive und Dateibäume. Es prüft vollständige Übergabe, Metadaten, unveränderte
Isolation, absichtlich verfälschte Selbstdeklarationen, Abbruchbereinigung und
einen konkurrierenden Zielpfad. Herstellerprogramme und Drucker werden dabei
nicht angesprochen.
