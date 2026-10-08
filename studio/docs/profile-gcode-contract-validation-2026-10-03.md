# Profil- und G-Code-Vertrag: Abnahme 2026-10-03

Der A1-Reparaturstand ist in Windows, Home Assistant und GitHub synchronisiert und produktiv installiert. Codecommit: [7c968d7](https://github.com/Taracraft/3D-Ultimate-Center/commit/7c968d7acf697ad285495ff0bc24a58f9466dff4). Die Dokumentation dieses Berichts wird als eigener Folgecommit gespeichert.

## Reparaturen

- Kuratierte und explizite Filamentwerte werden nativ übernommen: normale/erste Düsentemperatur, Bereich, geeignete Plattentemperaturen, Lüfter, Rückzug, Fluss und Volumenstrom. Nicht ausführbare Beratungswerte werden kenntlich gemacht.
- Supertack und Cool-Plate-Zuordnungen verwenden die tatsächlichen nativen Schlüssel. Nicht unterstützte Platten/Materialien werden vorab begründet abgewiesen.
- Drucker-/Düsen-/Prozess-/Filamentpayloads und Kompatibilitätsbericht sind an den Workerauftrag gebunden. Unabhängige A1-Grenzen bleiben auch bei manipulierten/neuen Hashes wirksam.
- Die Abschlussprüfung kontrolliert native Profilwerte, ausgeführte Düsen-/Bettheizbefehle, Druckermodell, lineare und vollständige Kreisbogengeometrie. Kompakte/nummerierte Bewegungen werden geprüft; nicht endliche Koordinaten und Homing im Druckteil werden abgewiesen.
- Gültige Cloud-Prozessprofile ohne eigenes Overlay funktionieren. Unzulässige Temperaturfelder im Prozessprofil sowie übergroße Erstschichthöhen werden früh abgewiesen.
- Maschinenstart/-ende, beide Sounds und filamentbezogene Start-/Endteile bleiben als sechs Abschnitte erhalten.

## Nachweise

| Prüfung | Ergebnis |
| --- | --- |
| Filament-/Düsen-/Platten-/Quellen-Vorprüfungen | 13.888 Fälle; 6.527 zulässig, 7.361 begründet abgewiesen |
| Prozess-/Düsen-Vorprüfungen | 147 Fälle; 73 zulässig |
| Repräsentative echte native Slices | 322 Archive; alle bestehen Parameter-, Heiz-, Geometrie- und Ergebnisbestätigung |
| Cloudprofil ohne Overlay | Echter nativer Slice bestanden |
| Mehrmaterial | Zwei PLA und PLA/PETG mit ausdrücklich abgestimmtem Bett bestanden; unterschiedliche Bettanforderungen abgewiesen |
| Installierte Laufzeit | 21/21 Slices für PLA/PETG/TPU und sieben A1-Düsenprofile bestanden; nach beiden Codebereitstellungen wiederholt |
| Windows-Gesamtgate | 614 Python-Tests, 3 Untertests; Frontend, TypeScript, beide Builds, Source-Policy und Compile-Prüfung bestanden |
| Negative Tests | Manipulierte Profile/Hashbindungen, 350 °C, falsche ausgeführte Heizwerte trotz korrekter Header, ungültige Größen/Koordinaten und Druckpfade abgewiesen |
| Puppet-Port 5000 | HTTP 200, image/png, PNG-Signatur geprüft; verbundenes Studio ohne aktiven Druckauftrag |

Die 13.888 Kombinationen sind Vorprüfungen, nicht 13.888 reale Slices. Beide Deployments hatten Backups, atomaren Austausch, eigenen Worker-Deploy, Live-Prüfsummen, HA-Konfigurationsprüfung und anschließenden HA-Neustart. Worker und Dispatch-/Refresh-Timer sind aktiv. Bundle der letzten Codebereitstellung: `7a5296fa97000d60f123cc20d87c3b2c8c3d95a86f658aa01eda510edbccac97`.

## Noch offen

Weitere/größere Druckermodelle benötigen eigene native Maschinen-/Hardware-/G-Code-Verträge. Die Katalogprofile bleiben erhalten. Kleine physische A1-Platten benötigen eigene Start-/Wisch-/Ursprungsverträge; eine virtuelle Verkleinerung genügt nicht. Physische Druckqualität und interaktive Touch-/Maus-Abnahme sind durch diese isolierten Slices nicht bewiesen. Kein Testartefakt wurde zum Drucker hochgeladen; kein Druck wurde gestartet.
