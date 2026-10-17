# HACS-Release-Artefakte prüfen

`verify_hacs_release.py` prüft ein bereits vorhandenes ZIP für den HACS-Modus `zip_release: true`. Es liest ausschließlich Dateien und schreibt sein Ergebnis als JSON nach stdout. Es erzeugt und entpackt kein Archiv, importiert keinen Python-Code aus dem Archiv und führt keine Installation oder Veröffentlichung aus.

## Installationsvertrag

HACS entpackt dieses Release-Asset direkt nach `custom_components/<manifest.domain>`. Das ZIP muss deshalb `manifest.json`, `__init__.py` und die übrigen Integrationsdateien relativ zu seiner Wurzel enthalten. Ein zusätzlicher Ordner `custom_components/ultimate_3d_studio/` ist für diesen Modus ungeeignet. Führendes `./` ist zulässig. `hacs.json` liegt im öffentlichen Repository; `filename` muss zum ausgewählten Release-Asset passen. `content_in_root` beschreibt die Repositorystruktur und entfernt keinen ZIP-Wrapper.

## Prüfung

```sh
python3 packages/ultimate-ha-integration/verify_hacs_release.py \
  --archive /path/to/ultimate-studio.zip \
  --hacs-json /path/to/hacs.json \
  --expected-files-json /path/to/reviewed-member-hashes.json \
  --version "$RELEASE_VERSION" --build-id "$FRONTEND_BUILD_ID" \
  --sha256 "$REVIEWED_ARCHIVE_SHA256"
```

Die erwartete Dateiliste ist ein JSON-Objekt mit integrationsrelativen Dateinamen und SHA-256-Werten. Diese Liste und der Archivhash müssen aus einem unabhängig geprüften Quell-/Paketbestand stammen. Eine vom ungeprüften ZIP selbst erzeugte Liste beweist keine Quellidentität.

Der Prüfer vergleicht exakt alle Dateien, Domain, zentrale Version, Frontend-Build sowie JavaScript-/CSS-Größen und Prüfsummen. Er prüft relative Python-Modulziele statisch. Bei `from . import NAME` kann NAME ein dynamisches Paketattribut sein; dessen tatsächliche Verfügbarkeit ist erst im Laufzeitimport prüfbar. Er akzeptiert nur Stored/Deflate-Kompression und begrenzt Archivgröße, Anzahl, Einzeldateien, Gesamtinhalt und externe JSON-Metadaten. Absolute Pfade, Traversal, doppelte normalisierte Namen, Links, Sonderdateien und nicht zugeordnete Dateien werden abgewiesen.

Die feste Studio-Version-/Buildbindung, erlaubten Dateitypen und zusätzlichen Pfadgrenzen sind Produktregeln. Sie sind keine Behauptung, dass HACS selbst alle diese Bedingungen erzwingt. Ein positives Prüfergebnis bestätigt den ausgewählten Artefaktvertrag; Repositoryerkennung, echte HACS-Neuinstallation, Update, Wiederherstellung und Produktfreigabe bleiben eigene Nachweise.

## Primärquellen

- [HACS-Publikationsmetadaten](https://www.hacs.xyz/docs/publish/start/#hacsjson)
- [Repositorystruktur für Integrationen](https://www.hacs.xyz/docs/publish/integration/#repository-structure)
- [Gepinnte Extraktionslogik](https://github.com/hacs/integration/blob/b3bce77447bff70e7d50ad3d87935b098270620a/custom_components/hacs/repositories/base.py#L576-L598)
- [Offizieller ZIP-Bau mit führendem ./](https://github.com/hacs/integration/blob/c0dfd8b44297c3673c21973e2539375a53687a9c/.github/workflows/publish.yml#L52-L57)
