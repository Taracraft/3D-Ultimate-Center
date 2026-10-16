# Engine-Herkunft und Paketzuordnung

Jedes Engine-Paket benötigt eine nachvollziehbare Verbindung zwischen Binärdateien, Quellversion, Ressourcen und Lizenztexten. Der Engine-Katalog hält Version, Downloadadresse, Archivgröße und SHA-256 sowie die erwarteten einzelnen Dateien fest.

## Referenzen

`ENGINE_BUNDLE_REFERENCE.json` beschreibt die Engine-Bundles. `BAMBU_BUILD_REFERENCE.json` enthält die zugehörige Bambu-Buildreferenz. `TARGET_BASE_REFERENCE.json` und `TARGET_IMAGE_REFERENCE.json` dokumentieren die Linux-Basis des Containerbaus. Die konkreten Werte stehen in diesen Dateien; sie werden nicht unabhängig in der Anleitung dupliziert.

## Dateien zuordnen

Ein Paket umfasst den Programmeinstieg, Laufzeitbibliotheken, Profile, Ressourcen und Lizenzdateien. Die Dateiliste muss vollständig sein. Ein passender Archivhash bestätigt die Byteidentität, aber nicht automatisch die Eignung aller enthaltenen Bibliotheken oder die Vollständigkeit der Quellenauslieferung.

Für Bibliotheken sind Paketversion, Quellpaket und gegebenenfalls Buildoptionen zu berücksichtigen. Das betrifft insbesondere eingebundene FFmpeg-Komponenten: sichtbare Versionsangaben allein ersetzen nicht die Zuordnung des konkreten Builds.

## Prüfung und Auslieferung

Die [Bundle-Werkzeuge](ENGINE_BUNDLE_BUILD.md) erstellen Dateimanifeste. [Staging](PACKAGE_STAGING.md) prüft Archive vor der Übernahme; die [Distribution](ENGINE_DISTRIBUTION.md) stellt die drei Enginefamilien gemeinsam bereit. Die Laufzeit muss anschließend die benötigten Loader-, Plugin- und Profilpfade verwenden.

Der aktuelle Katalog enthält noch keine freigegebenen Engine-Downloads. Die vorhandenen Referenzen sind deshalb nicht mit einer vollständigen installierbaren Engine-Veröffentlichung gleichzusetzen.

## Lizenztexte

Eigene und übernommene Komponenten behalten ihre jeweiligen Lizenzbedingungen. Welche Texte und Quellen beizulegen sind, richtet sich nach den tatsächlich verteilten Dateien. Siehe [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [REPOSITORY_NOTICES.md](REPOSITORY_NOTICES.md) und die Lizenzdateien unter `licenses/`.

Upstream-Lizenzquellen: [Bambu Studio](https://github.com/bambulab/BambuStudio/blob/master/LICENSE), [PrusaSlicer](https://github.com/prusa3d/PrusaSlicer/blob/master/LICENSE) und [CuraEngine](https://github.com/Ultimaker/CuraEngine).
