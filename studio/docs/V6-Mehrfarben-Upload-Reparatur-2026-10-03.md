# V6 – Mehrfarben-Upload repariert – 03.10.2026

## Ursache und Korrektur

Der konkrete Benutzerauftrag scheiterte am internen Dateinamen `Base_1_-_color_1_+4_Teile.3mf`. Die beiden nativen Serveraufrufe um 17:58:53 und 17:59:08 CEST endeten mit HTTP 400 `invalid_filename`. Der HA-Router erlaubte Pluszeichen und Umlaute, der native Worker ausschließlich ASCII-Zeichen aus seinem bestehenden Dateinamenvertrag.

Nur `slicer_backend_router.py` wurde produktiv geändert: interner ASCII-Uploadname, einschließlich Präfix und Endung auf 200 Zeichen begrenzt. Der ursprüngliche Projektname bleibt in den Metadaten erhalten. Keine Änderung an Modellgeometrie, Farb-/Materialplan, Frontend oder nativem Worker.

## Nachweise

- Fünf gezielte Regressionen führen die tatsächliche Router-Methode gegen `safe_filename` aus dem tatsächlichen Workerquelltext aus. Alter Code: vier Fehler, ein Erfolg. Korrigierter Code: fünf Erfolge. Identische Modelldaten, Materialplan und Upload-/Jobdateinamen werden geprüft.
- Vollständiges isoliertes Gate: 1.277 Python-Tests und drei Untertests, 161 Frontendtests, TypeScript, beide Builds, Source-Policy und Compile-Prüfung erfolgreich.
- Isolierung war erforderlich: Im PC-Arbeitsbaum liegen separate, noch nicht vollständig abgeglichene First-Layer-Änderungen. Deren Workerdatei und Hash-Pins wurden nicht verändert. Der isolierte Prüfbaum basiert auf HA-Quellen; fehlende kanonische Begleitdateien wurden vom PC ergänzt, die Netzwerk-Komponente dabei mit Live verglichen. Die generierte 50.000-Dreiecke-Testdatei wurde entsprechend dem bestehenden Performance-Test hergestellt. Die Gate-Protokolle sind im Backupverzeichnis aufbewahrt.
- Same-Day-Backups auf PC und HA: `backups/20261003-multicolor-upload-filename`. Atomarer Austausch nur der Router-Datei, vorheriger SHA geprüft. HA-Konfigurationsprüfung und HA-Core-Neustart erfolgreich.
- Originaldatei `AMS-lite A1_A1mini 4 color test.3mf`, 55.693 Bytes, SHA-256 `18f2c54c5a714f6bdcb87471f245243d35c8483b5c662f6fca3f670219c10c78`: echter nativer Upload mit altem Namen HTTP 400; mit vom korrigierten Live-Quelltext erzeugtem Namen HTTP 201. Hochgeladene Bytes identisch. Ausschließlich die eigene einmalige Testkopie danach entfernt.
- HA-API nach Neustart HTTP 200. Router-SHA-256: `ed35207b1a762509f18f06a8c5d537188ca46838289d57e8e7ed77c2e1648bad`.
- GitHub-Codecommit `60e9b53d1e77335377b74d5d7bd00cc502a0b9a0`, Regressioncommit `9e5b3f26bacb4dda70a22312b3f91fc563ab4a7a`.

## Grenze der Abnahme

Der echte Test bestätigt den Modellupload an den Slicer, nicht den vollständigen Vierfarben-Slice oder einen physischen Druck. Kein Job wurde dabei erzeugt, kein Upload zum Drucker und kein Druckstart ausgeführt. Die Originaldatei enthält vier PLA-Farben (Blau, Grau, Grün, Rot); die abweichenden Studiofarben können durch AMS-Zuordnung entstehen. Eine unverändert korrekte tatsächliche Slotzuordnung und ein vollständiges Slice-Ergebnis dieses Modells sind mit diesem Uploadtest nicht bewiesen. Beta bleibt bestehen.
