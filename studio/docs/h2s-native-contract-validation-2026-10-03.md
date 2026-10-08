# H2S-Artefaktvertrag – Reparatur und native Prüfung, 2026-10-03

## Ergebnis und Reichweite

Die installierten nativen H2S-Maschinen-, Prozess- und Filamentprofile erzeugen gültigen G-Code. Der bisherige Streamingvalidator verlangte jedoch drei A1-spezifische Erkennungsmerkmale. Alle 16 H2S-Artefakte wurden dadurch als unvollständig abgewiesen. Die getrennte H2S-Prüfung erkennt jetzt die ausgeführten H2S-Befehle und kontrolliert zusätzliche Heizkanäle.

Dies ist ein abgeschlossener Baustein des größeren Druckervertrags, keine vollständige H2S-Freigabe im Studio. `job_hardware_limits`, Düsenauflösung, lokale Filamentzuordnung und vier Maschinenvorlagen bleiben im produktiven Auftrag auf den geprüften A1-Vertrag beschränkt. Die H2S-Artefakte wurden mit nativen Herstellerprofilen erzeugt; individuelle Studio-Filamentprofile und Mehrmaterial wurden hier noch nicht auf dem H2S nachgewiesen. Das Prüfresultat kennzeichnet daher `filament_parameter_contract_verified=false`.

## Änderung

- Nur ein explizit ausgewählter H2S mit vollständig geprüften Hardwaregrenzen aktiviert die H2S-Befehlsprüfung. Ein Dateikommentar erteilt keine Hardwareautorität.
- Flow-Kalibrierung: ausgeführtes `M983.3`; Düsenreinigung: ausgeführtes `G150 T...`; Kalibrierstreifen: positive XY-Extrusion innerhalb des nativen Load-Line-Abschnitts. Kommentare allein genügen nicht.
- Zusätzlich zu den normalen Heizbefehlen werden `G150 T`, `M620.10 T/P` sowie `M141/M191 S/R` geprüft. Nicht endliche oder negative Temperaturen werden abgewiesen.
- H2S-Hardwareobergrenzen: 340 × 320 × 340 mm, Düse 350 °C, Bett 120 °C, Kammer 65 °C. Auch mitgelieferte Grenzwerte dürfen diese Obergrenzen nicht erhöhen.
- Der A1-Prüfpfad bleibt unverändert. Eine 300-mm-Geometrie erhält keine A1-Freigabe.

Herstellerquellen, abgerufen am 2026-10-03: [H2S-Spezifikation](https://store.bblcdn.com/s7/default/3f91ec86de1a4ce28fe8fb660b95cd3e/h2s.pdf), [H2S-Produktseite](https://bambulab.com/de-de/h2s), [Herstellerankündigung](https://blog.bambulab.com/h2s-the-ultimate-single-nozzle-3d-printer-now-bigger-than-ever/).

## Reale native Prüfung

Testkörper: 300 × 8 × 2,4 mm. Die Breite bleibt auch bei automatischer Zentrierung größer als die A1-Druckfläche. Der native H2S nutzt die vollständige 340 × 320 mm Platte; eine 300-mm-Platte wurde hier nicht als physische Ersatzplatte behauptet.

| Düse | Native Schichthöhe | Materialien | Oberflächen | Native Slices / H2S-Artefakte |
|---|---|---|---|---|
| 0,2 mm | 0,10 mm | Generic PLA, Generic PETG | Textured PEI, Smooth PEI (`High Temp Plate`) | 4 / 4 bestanden |
| 0,4 mm | 0,20 mm | Generic PLA, Generic PETG | Textured PEI, Smooth PEI (`High Temp Plate`) | 4 / 4 bestanden |
| 0,6 mm | 0,30 mm | Generic PLA, Generic PETG | Textured PEI, Smooth PEI (`High Temp Plate`) | 4 / 4 bestanden |
| 0,8 mm | 0,40 mm | Generic PLA, Generic PETG | Textured PEI, Smooth PEI (`High Temp Plate`) | 4 / 4 bestanden |

Alle 16 Artefakte werden mit A1-Hardwaregrenzen wegen der extrudierenden X-Geometrie abgewiesen. Sieben reale Artefaktmutationen werden abgewiesen: fehlende Reinigung, fehlende Kalibrierung, fehlender Load-Line-Druckpfad, 351 °C Reinigungsziel, 351 °C Spülziel, 66 °C Kammer sowie falsches Druckermodell. Alle 322 vorhandenen A1-Artefakte bestehen die neue Prüfung weiterhin einschließlich gebundener Filamentparameter und ausgeführter Heizwerte. Zusätzlich bestehen 20 gezielte Python-Tests.

Ausführung: natives Bambu-CLI in `unshare --net`, isolierte Validierungsverzeichnisse, keine produktive Jobwarteschlange und keine Druckerkommunikation. Die ersten Probeversuche mit einem unvollständigen 3MF-Container wurden als Testaufbaufehler verworfen; erst die korrigierten nativen Artefakte zählen. Eine kleine erste Würfelprobe wurde vom CLI zentriert und beweist keine große Geometrie; ausschließlich der finale 300-mm-Streifen zählt für den Größenvergleich.

## Offene Folgearbeit

1. Modellregister für Hardware, Düsen, Materialzuführung und native Profilquellen durchgängig einführen; H2S-Vorlagen in die vier passenden Studio-Abschnitte aufteilen.
2. H2S-spezifische Filamentgrundlagen mit vollständigen Quellen-/Parameterbindungen; eigene Kammer- und AMS-Verträge; Einzel- und Mehrmaterialmatrix.
3. H2D/H2C separat prüfen: nutzbare Fläche hängt von physischer Werkzeug-/Düsenkonfiguration ab; der Profilpolygon allein ist keine Einzeldüsenautorität.
4. Kleinere physische Platten benötigen weiterhin gesonderte Maschinenbewegungs-, Ursprungs- und Wischverträge. Sie werden nicht durch kleinere Zahlen in `printable_area` freigegeben.

Prüfbelege liegen dauerhaft unter `/var/lib/homeassistant/homeassistant/backups/20261003-h2s-contract-candidate/`. Native Archive: `/var/lib/homeassistant/3d-printer-slicing-server/validation/h2s-native-contract-20261003T080938263220Z`. Kein Upload zum Drucker und kein Druckstart.


## Gesamtgate und installierte Abnahme

Vollständiges Windows-Gate: 632 Python-Tests plus drei Untertests, Source-Policy, TypeScript, Frontend-Tests, Produktions-/HA-Build und Compile-Prüfung bestanden. Gesichertes Deployment: /var/lib/homeassistant/homeassistant/backups/20261003T082551Z-v6-h2s-artifact-contract. HA-Konfigurationsprüfung und Neustart erfolgreich, Profil-API HTTP 200, acht Worker-Abhängigkeiten per SHA bestätigt. Installierter Stand: 16 H2S-Artefakte und sieben Negativmutationen bestanden sowie 21 neue A1-Slices ohne Parameterverlust oder native Optionenwarnungen. Bundle-SHA256: 80f2440e60fcdb7a0bdfc209487b1b12710768ba02a75f4eb9b60924316b6831.
