# Historische Aenderungen

Diese Zusammenfassung beschreibt den historischen Ausgangsstand bis zum 7. Oktober 2026. Sie ist kein Abnahmenachweis fuer den aktuellen Lieferkandidaten. Linux, TLS, Installation, Upgrade, Restore, frisches HACS und Release benoetigen eigene aktuelle Nachweise.

## Studio und Profile
- Mehrere Druckplatten, persistente Arbeitsbereiche, Transformationen, Materialzuordnungen und editierbare Drucker-, Duesen-, Filament- und Prozessprofile.
- Getrennte Anzeige fuer gewaehlte, im Slicer angewandte und im Artefakt bestaetigte Einstellungen.
- Explizite AMS-/Einzelspulenwahl, Artefaktpruefung und zweistufige Druckfreigabe.

## Layer und Prozesseinstellungen
- Durchgaengige Extrusionsgeometrie, verbundene Konturen, Endflaechen, Beleuchtung und Layerfokus.
- Variable Schichthoehen mit Duesengrenzen, Presets, Kurvenbearbeitung und Vorschaukopplung.
- Layernavigation, Direktspruenge, Supportstile und Warnungen bei widerspruechlichen Zeitangaben.

## Malwerkzeuge und Oberflaeche
- Eigenstaendige Malbereichsauswahl und kontinuierliche Pinsel-/Stiftstriche.
- Kreis, Rechteck und Text mit exportierbarer verfeinerter Geometrie.
- Persistente Kamera-/Fortschrittsdialoge, stabile Scrollposition und mobile Navigation.
- MakerWorld-Modelldetails und Profilablaeufe.

## Historische Versionen
Der Ausgangsstand dokumentiert Beta-Meilensteine im Juli 2026 und Version 6.0.0 am 6. Oktober 2026. Diese historischen Angaben erteilen keine aktuelle Deploymentfreigabe und ersetzen keine Test- oder Lizenzpruefung. Private Betriebspfade, lokale Zugriffsdiagnosen und fortgeltende Neustartfreigaben sind aus dieser Zusammenfassung ausgeschlossen.

## 7. Oktober 2026
- Aktive Studio-Integration, Frontend und Worker auf einen versionsneutralen Namensraum umgestellt; Releaseversion bleibt in zentralen Metadaten.
- Historische Bereitstellungs- und Sichtpruefungen belegen keine Abnahme des aktuellen Quellkandidaten.

## 17. Oktober 2026 - 6.0.2
- First-Layer-Vorlage hinter dem unveraenderten einzigen Menuepunkt CAD > Einfuegen > First Layer auf eine einzelne physische Schicht und eine sparsame Vollbett-Diagnosegeometrie umgestellt. Das mittige TaraCraft-T besitzt drei getrennte Konturen; Vollbett-Vollflaeche und gestapelte Logo-Geometrie entfallen. Rund 20 Minuten bleiben bis zu einem gesonderten echten Nachweis nur Zielwert.
- Externe Spule unter Materialsysteme nutzt dieselbe Farb-, Hersteller-, Filamentart- und Sortenbedienung wie AMS, ausschliesslich aus dem vorhandenen A1-Katalog. Auswahlzustand ist pro Drucker und Ziel isoliert; andere AMS-Slots werden nicht veraendert.
- Fuer beide Repositories wurden kompakte animierte GIFs aus tatsaechlichen, zugeschnittenen Nutzeraufnahmen vorbereitet. Herkunft und Grenzen sind dokumentiert; die Slicer-Animation behauptet keine eigenstaendige Runtime- oder Engine-Lieferung.
- Vollstaendiger Frontendlauf: 658 Tests bestanden, Produktionsbuild erfolgreich. Keine echte Drucker-, Slice-, Live-HACS- oder Migrationsaktion.