# HACS-Auslieferung und lesende Vertragsprüfung

Ultimate 3D Studio verwendet den normalen HACS-Repositorymodus. Die vollständige Integration liegt unter `custom_components/ultimate_3d_studio/`, einschließlich ihrer drei Frontenddateien in `assets/`. HACS lädt den ausgewählten Repositorystand über GitHubs automatisch erzeugtes Quellarchiv und installiert daraus den Integrationsordner. Ein selbst erzeugtes oder hochgeladenes ZIP-Release-Asset ist für diesen Modus nicht erforderlich.

## Aktuelle Publikationsmetadaten

Die kanonische Konfiguration in `packages/ultimate-ha-integration/hacs.json` wird an die öffentliche Repositorywurzel projiziert:

```json
{
  "name": "Ultimate 3D Studio",
  "content_in_root": false,
  "render_readme": true,
  "zip_release": false,
  "hide_default_branch": true
}
```

`filename` entfällt. `zip_release` ist bei HACS standardmäßig falsch; Studio setzt den Wert ausdrücklich. `content_in_root: false` bezeichnet die normale Struktur mit genau einer Integration unter `custom_components/`. Alle benötigten Python-, JSON-, Übersetzungs- und Frontenddateien müssen innerhalb dieses Integrationsordners liegen. Die Rootprojektion und die bestehende Kompatibilitätsprojektion stammen aus demselben kanonischen Datei- und Lizenzinventar.

Im Integrationsmanifest müssen mindestens `domain`, `documentation`, `issue_tracker`, `codeowners`, `name` und `version` vorhanden sein. Die Domain bleibt `ultimate_3d_studio`; die Version folgt der zentralen Produktversion. Der lesende Studio-Vertrag bindet zusätzlich Config-Flow, Frontend-Build, Dateigrößen, Hashes und relative Python-Modulziele an den unabhängig geprüften Quellbestand.

## Versionierte Veröffentlichung

Ein veröffentlichter GitHub Release verweist auf einen Tag des geprüften vollständigen Repositorystands. HACS verwendet dessen Tagnamen als verfügbare Releaseversion. Ein Git-Tag allein genügt für diese Releaseauswahl nicht. Der GitHub Release benötigt im Repositorymodus kein angehängtes Studio-ZIP.

Die aktuelle Einstellung `hide_default_branch: true` blendet den Standardbranch in der Versionsauswahl aus. Der vorgesehene öffentliche Kanal ist daher ein veröffentlichter Release des geprüften Stands. HACS unterstützt grundsätzlich auch die Auslieferung des Standardbranches ohne GitHub Releases; dazu darf dieser Branch nicht durch die Publikationsmetadaten ausgeblendet werden.

Ein Release muss die geänderte Root-`hacs.json`, die vollständige Rootintegration und die passenden Frontendbytes gemeinsam enthalten. Das Umstellen der Metadaten veröffentlicht noch keinen GitHub Release. Eine HACS-Testinstallation und andere externe Abnahmen bleiben separat dokumentierte Ergebnisse und gehören nicht zur Releasebewertung.

## Repositorystruktur lesend prüfen

`verify_hacs_release.py` liest ausschließlich vorhandene Dateien und schreibt sein Ergebnis als JSON nach stdout. Es erzeugt oder entpackt kein Archiv, importiert keinen Python-Code aus den geprüften Integrationsdateien und führt keine Installation oder Veröffentlichung aus:

```sh
python3 packages/ultimate-ha-integration/verify_hacs_release.py \
  --repository-root /path/to/reviewed-repository \
  --expected-files-json /path/to/reviewed-member-hashes.json \
  --version "$RELEASE_VERSION" --build-id "$FRONTEND_BUILD_ID"
```

Die erwartete Dateiliste ist ein JSON-Objekt mit integrationsrelativen Dateinamen und SHA-256-Werten. Sie muss aus einem unabhängig geprüften Quellbestand stammen. Eine aus der ungeprüften Projektion selbst erzeugte Liste beweist keine Quellidentität.

Der Repositoryprüfer akzeptiert die aktuellen Normalmetadaten ohne `filename`; auch ein fehlender `zip_release`-Schlüssel entspricht dem HACS-Standardwert falsch. Zur Prüfung vorhandener älterer Quellprojektionen akzeptiert er weiterhin `zip_release: true` zusammen mit einem sicheren ZIP-Dateinamen. Diese Metadatenwahl erzeugt oder prüft kein Release-Asset. Im normalen Studio-Modus wird ein übrig gebliebener `filename`-Schlüssel als widersprüchliche Konfiguration abgewiesen.

Die Prüfung verlangt exakt eine Rootintegration, dieselben extern geprüften Dateihashes und vollständige Manifest-, Frontend- und Modulziele. Grenzen für Anzahl, Einzelgrößen und Gesamtinhalt bleiben bestehen. Links, Sonderdateien, Aliasnamen, nicht zugeordnete Dateien und während des Lesens veränderte Bestände werden abgewiesen.

Ein positives `repository_structure_verified` bestätigt die geprüfte Quellprojektion. Im Normalmodus ist `release_filename` null. `release_asset_verified`, `installation_verified` und `product_release_complete` bleiben falsch: Der Prüfer trifft keine Produktfreigabeentscheidung und behauptet keine Testinstallation. Ein eigener ZIP-Assetnachweis ist für den gewählten Repositorymodus nicht erforderlich.

## Vorhandenes ZIP optional prüfen

Für bereits vorhandene Legacy-ZIP-Artefakte bleibt der separate Modus verfügbar. Er verlangt ausdrücklich `zip_release: true` sowie einen sicheren zum Archiv passenden `filename` in der übergebenen Metadatendatei. Die aktuelle Normalmodus-Konfiguration ist dafür ungeeignet und wird vor dem Archivzugriff abgewiesen.

HACS entpackt ein solches Release-Asset direkt nach `custom_components/<manifest.domain>`. Das ZIP muss deshalb `manifest.json`, `__init__.py` und die übrigen Integrationsdateien relativ zur ZIP-Wurzel enthalten. Ein zusätzlicher `custom_components/ultimate_3d_studio/`-Ordner ist für diesen Legacy-Modus ungeeignet; führendes `./` ist zulässig.

```sh
python3 packages/ultimate-ha-integration/verify_hacs_release.py \
  --archive /path/to/existing-studio.zip \
  --hacs-json /path/to/legacy-zip-hacs.json \
  --expected-files-json /path/to/reviewed-member-hashes.json \
  --version "$RELEASE_VERSION" --build-id "$FRONTEND_BUILD_ID" \
  --sha256 "$REVIEWED_ARCHIVE_SHA256"
```

Der ZIP-Prüfer verlangt einen externen Archivhash, akzeptiert nur Stored/Deflate-Kompression und behält seine Pfad-, Größen-, Hash-, Manifest- und Frontendprüfungen bei. Eine aus dem ungeprüften ZIP selbst abgeleitete Dateiliste ersetzt keinen unabhängigen Nachweis. Auch dieser Modus erzeugt oder entpackt kein Archiv.

Die zusätzlichen Studio-Identitäts- und Pfadregeln sind Produktverträge. Sie behaupten nicht, dass HACS selbst alle diese Regeln erzwingt. Bei `from . import NAME` kann NAME ein dynamisches Paketattribut sein; dessen tatsächliche Verfügbarkeit wird durch eine statische Modulprüfung nicht bewiesen.

## Frontend und Bambu-Anmeldung nach einem Update

Nach der Installation über HACS Home Assistant neu starten und anschließend die Studio-Seite neu laden. Studio stellt dann das mitgelieferte Frontend bereit und aktualisiert genau eine vorhandene Studio-Ressource auf diesen Build. Die Ressourcen-ID bleibt erhalten; PCC und andere Ressourcen bleiben unverändert. Bei widersprüchlichen Studio-Einträgen oder fehlenden Paketdateien erfolgt keine Änderung.

Wird die Bambu-Anmeldung beim MakerWorld-Import abgewiesen, bietet Studio direkt die erneute Anmeldung an. Passwort und gegebenenfalls der anschließende Verifikationscode werden über den bestehenden Home-Assistant-Optionsdialog verarbeitet. Nach erfolgreicher Anmeldung den gewünschten Import erneut anklicken. Studio wiederholt ihn nicht automatisch.

## Primärquellen

- [HACS-Publikationsmetadaten und Releaseversionen](https://www.hacs.xyz/docs/publish/start/)
- [Normale Integrationsstruktur und optionale GitHub Releases](https://www.hacs.xyz/docs/publish/integration/)
- [Gepinnte HACS-Pfadauswahl und Manifestbezug](https://github.com/hacs/integration/blob/adc26ec798021d2c2db1e6aa90eabe2e208b8c04/custom_components/hacs/repositories/integration.py#L71-L105)
- [Gepinnter Repositorydownload und Auswahl des Integrationsunterbaums](https://github.com/hacs/integration/blob/adc26ec798021d2c2db1e6aa90eabe2e208b8c04/custom_components/hacs/repositories/base.py#L616-L708)
- [Derselbe Repositorymodus in HACS 2.0.5](https://github.com/hacs/integration/blob/2.0.5/custom_components/hacs/repositories/base.py#L621-L713)
- [Gepinnte Auswahl zwischen Release-Asset und Repositoryinhalt](https://github.com/hacs/integration/blob/adc26ec798021d2c2db1e6aa90eabe2e208b8c04/custom_components/hacs/repositories/base.py#L917-L967)
