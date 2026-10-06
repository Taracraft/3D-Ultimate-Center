# Ultimate Studio · Jobabbruch-Schreibkonflikt

Stand: 4. Oktober 2026. Der kanonische PC-Gesamttest wurde am 04.10.2026 um 17:58:22 CEST erfolgreich abgeschlossen. Status: PC-Quellkorrektur verifiziert; HA-Synchronisierung, produktive Aktivierung und öffentlicher Abgleich sind nicht erledigt.

## Ausgangsfehler

Der bisherige Gesamtstand scheiterte reproduzierbar unter Windows in `tests/test_worker_cancellation.py::WorkerCancellationTests::test_polling_and_cancellation_share_consistent_state`. Mehrere unabhängige Abbrüche aktualisieren neben ihren eigenen Zustandsdateien dieselbe Datei `last_job.json`. Der atomare Austausch in `job_control.atomic_json` wurde zeitweise mit `PermissionError: [WinError 5]` abgewiesen. Die vorangehenden Gates vom 04.10.2026 um 16:43 und 17:18 dokumentieren diesen Fehler.

Die Korrektur bleibt eng auf den Austausch einer bereits vollständig geschriebenen und per fsync gesicherten temporären JSON-Datei begrenzt. Es wird weder die ganze Abbruchoperation noch ein HTTP-Aufruf, Slice oder Druckerbefehl wiederholt.

## Implementierte Korrektur

Neue interne Funktion `_replace_json_file` im vorhandenen Worker-Modul `job_control.py`. Sie wiederholt ausschließlich `os.replace` bei Windows-Fehlercodes 5, 32 oder 33. Höchstens neun Versuche; die acht konfigurierten Warteintervalle summieren sich auf 815 Millisekunden. Das begrenzt die Zahl der Versuche und die angeforderte Wartezeit, nicht die Dauer eines blockierenden Betriebssystemaufrufs.

Die gleiche temporäre Datei wird erneut verwendet. JSON-Erzeugung und fsync geschehen genau einmal. Bei dauerhaftem Fehler wird die Ausnahme weitergegeben und die ursprüngliche Zieldatei weder gelöscht noch gekürzt. Die vorhandene Bereinigung entfernt die temporäre Datei. Andere Fehler und andere Betriebssysteme erhalten keine Wiederholung. Unter Linux bleibt es bei einem einzelnen atomaren Austausch.

Job-ID-Prüfung, Freigabe-/Abbruchvertrag, Prozesszuordnung, Prozessgruppenbeendigung und Auftragssperren bleiben unverändert. Die bestehende ursprüngliche Fehlerregression wurde weder abgeschwächt noch übersprungen. Frontend, Galerie-, CAD-, Material- und Druckfunktionen wurden in diesem Schritt nicht geändert.

## Sicherung und Quellumfang

Vor dem Überschreiben wurde `backups/20261004-worker-atomic-json/rollback.json` auf dem PC angelegt. Das exakte reversible Delta enthält alle drei überschriebenen Dateien, Vorher-/Nachherhash und die vollständigen ersetzten Textblöcke. Eine Rücknahme darf nur bei exakt passendem Nachherhash erfolgen und muss anschließend den Vorherhash reproduzieren. Fremde Folgeänderungen dürfen nicht überschrieben werden.

Geändert wurden eine Produktdatei und zwei zugehörige Prüfsummenreferenzen. Neu angelegt wurde `tests/test_worker_atomic_json.py` ohne Überschreiben einer vorhandenen Datei. Die Änderungen an Prüfsummenreferenzen ersetzen ausschließlich den Hash der tatsächlich geänderten Workerdatei; ihre Prüflogik bleibt erhalten.

| Datei | SHA-256 nach Korrektur |
| --- | --- |
| `deploy/homeassistant/host/3d-printer-slicing-server/job_control.py` | `1226e2818657d5d069bbcd6ae994144f2ba05240ce3b9e600f4cf1c6357b3935` |
| `deploy/homeassistant/host/3d-printer-slicing-server/DEPENDENCY-SHA256SUMS` | `cfe8739125b5a58482e5b3bb58ad91c901075086610f95029bc3387c91bf5b25` |
| `tests/test_v6_native_slicer_canonical_sources.py` | `1bfbc9b8eeb872e56694c011348388c0ce57b6ec050fe437715b08c73e6333d5` |
| `tests/test_worker_atomic_json.py` | `cb83dc674e218b697fabab741c64f603894ad1ced0e276f361d7db866301e68c` |

Workerdatei und Abhängigkeitsmanifest wurden nach dem Gesamtgate zusätzlich vom PC-Connector per SHA bestätigt. Der ursprüngliche Workerhash war `1d86259fdaf1e3617a01d440bd36890827a532f084ebb0346b595e6eeb39f231`.

## Tatsächlich ausgeführte Prüfungen

### Neue gezielte Regressionen

27 neue Tests gegen die tatsächliche Workerfunktion: zeitweise und dauerhafte Windows-Sperren, andere Fehlercodes, Linux-/macOS-Verhalten, unveränderter Altinhalt bei Fehlschlag, einmalige Serialisierung und fsync, begrenzte Wiederholungen, Bereinigung sowie parallele Abbrüche und lesende Zugriffe.

Die Gegenprobe in der isolierten Linux-Arbeitsumgebung scheitert am unveränderten Ausgangscode mit zwölf Fehlern bei 15 bestandenen Tests. Mit der Korrektur bestehen alle 27 Tests. Windows-Fehler werden in den gezielten Fehlerpfadtests kontrolliert injiziert; zusätzlich läuft der ursprüngliche reale Windows-Konkurrenztest unverändert im PC-Gesamtgate.

Fünf neue Belastungsrunden verwenden jeweils 30 synthetische gehaltene Aufträge mit sechs parallelen Abbruch- und zwei Leseraufgaben. Alle terminalen Auftragszustände bleiben erhalten. Es werden keine produktiven Aufträge verwendet und keine Slicer-Engine oder Druckeraktion gestartet.

### Vollständiger kanonischer Windows-PC-Test

- Gesamtstatus `success: true`, abgeschlossen `2026-10-04T17:58:22.612207+02:00`.
- Source-Policy ohne Verstöße.
- 325 Frontendtests bestanden; keine fehlgeschlagen oder übersprungen.
- Produktionsbuild und Home-Assistant-Core-Build bestanden.
- Python-Syntax, Core-Imports und Komponenten-Compileprüfung bestanden.
- Python: 1.507 Tests bestanden, keine fehlgeschlagen; 15 Untertests bestanden.
- Neun Linux-spezifische Prozessgruppentests wurden auf Windows ausdrücklich mit Plattformbegründung übersprungen.
- Der vorher fehlgeschlagene ursprüngliche Test `test_polling_and_cancellation_share_consistent_state` und alle 27 neuen Tests sind einzeln als bestanden protokolliert.

Die 27 neuen Tests sowie die vorherigen Galerie-Duplikat- und Backupprüfungen sind in den 1.507 enthalten und werden nicht hinzuaddiert. Ein unabhängiger, separat protokollierter TypeScript-Compilerlauf wird aus dem Connector-Gesamtstatus nicht zusätzlich abgeleitet.

Der Connector-Aufruf erreichte zunächst sein Zeitlimit. Erst die anschließend gelesenen tatsächlichen Statusdateien belegen den erfolgreichen Abschluss. Das Zeitlimit wurde nicht als Testergebnis gewertet. `deploy.success` innerhalb des Gateberichts bezeichnet vorhandene kanonische Buildartefakte, keine produktive HA-Bereitstellung.

Unveränderte Frontendartefakte gegenüber dem vorherigen PC-Gate: HA-Core-JavaScript `0b2a6fc2f76b667ea5c6a7439f40ccba16afcb548f9b57a883c8d17db9ce60d2`, CSS `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.

### Ergänzende Linux-Prüfung

Alle neun unter Windows ausgelassenen `LinuxCancellationTests` wurden anschließend in einer isolierten Linux-Arbeitsumgebung gegen die korrigierte Workerdatei ausgeführt: neun bestanden. Zusammen mit der Wiederholung der 27 neuen Schreibtests: 36 bestanden, keine ausgelassen.

Die Prüfungen umfassen gehaltene und nicht verwaltete Aufträge, Abbruch gegen einen verspäteten Abschluss, ungültige Auftragsdateien, einen noch nicht beendeten Prozessbaum, unerwarteten Programmabbruch und nicht lesbare Prozessinformationen. Eigene kurzlebige Testprozessgruppen werden kontrolliert beendet; andere Fälle verwenden begrenzte Prozess-Doubles.

Der Test des tatsächlichen Dispatch-Shellskripts verwendet ausschließlich die absichtlich unbekannte Engine `test-engine` und prüft deren Fehlerpfad. Das unveränderte Skript ist per SHA `731d90aa5aa4138e905b68cc9f4a217bb3bf60d21d2ae74adb0ede678b111ad1` gegen den kanonisch geprüften Quellstand bestätigt. Keine echte Slice-Engine wurde gestartet.

Das ist ein gezielter Linux-Nachweis, kein vollständiges Linux-Gesamtgate und keine Abnahme des laufenden Home-Assistant-Hosts. Die 27 erneut ausgeführten Fälle dürfen nicht als 27 weitere eindeutige Projektprüfungen gezählt werden.

## Nachweise und Arbeitsfortsetzung

Windows-Rohbelege im PC-Projekt: `.test-results/connector-v6-quality-gate.json`, `.test-results/python-test-status.json` und `.test-results/python-pytest-progress.log`. Ergänzende strukturierte Zusammenfassung und Arbeitsnachweis: `backups/20261004-worker-atomic-json/verification-summary.json` und `LIVE_WORKLOG.md` im selben Sicherungsverzeichnis. Das zentrale ältere Arbeitsprotokoll wurde nicht überschrieben.

Die HA-Regeln und das Arbeitsprotokoll waren zu Beginn dieses Abschnitts lesbar. Ein anschließender HA-Detailaufruf wurde vom Werkzeug-Sicherheitscheck blockiert. Deshalb wurden weder der HA-Quellbaum synchronisiert noch produktive Komponenten oder der native Worker aktiviert; ein alternativer administrativer Zugriffsweg wurde nicht verwendet. Der öffentliche Repository-Abgleich und die Übernahme in den getrennten Namensmigrationskandidaten bleiben ebenfalls offen.

Der konkrete PC-Gateblocker ist behoben. DS-10 ist dadurch nicht automatisch vollständig live abgenommen. Für die Fortsetzung stehen Quellabgleich, kontrollierte getrennte HA-/Worker-Bereitstellung mit Backup und Live-SHA sowie Laufzeitabnahme an. GA-09 hat weiterhin keine sichtbare Duplikatoberfläche; Papierkorb und Tags bleiben offen. Namensmigration, echte iPhone-Bedienabnahme und vollständiger System-Restore sind nicht abgeschlossen. Dashboard-Gesamtzählung und Beta-Status wurden nicht geändert.

Es gab in diesem Abschnitt keinen produktiven Jobabbruch, keinen realen Slice, kein Job-Release, keinen Druckerupload, keinen Druckstart, keinen Dienstneustart und keine öffentliche Veröffentlichung.
