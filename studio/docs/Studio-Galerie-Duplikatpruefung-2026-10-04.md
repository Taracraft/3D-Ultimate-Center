# Ultimate Studio · GA-09: Duplikatprüfung

Stand: 4. Oktober 2026. Kanonisches PC-Gate abgeschlossen um 17:18:41 CEST.

## Ergebnis und Abgrenzung

Der bisher offene Galeriepunkt GA-09 ist um einen tatsächlich implementierten, rein lesenden Backend-/API-Baustein erweitert. Er erkennt bytegleiche STL-, OBJ- und 3MF-Dateien im gewählten Galerieordner einschließlich Unterordnern. Gleichnamige Dateien oder gleiche Dateigrößen reichen nicht als Duplikatnachweis. Unterschiedliche Dateiformate mit gleicher Geometrie werden nicht als geometrisch gleich erkannt.

Der neue Endpunkt ist im PC-Quellstand in der tatsächlichen Home-Assistant-Integrationsinitialisierung registriert. Keine Aktivierung auf Home Assistant, keine neue Galerie-Schaltfläche, keine Papierkorb- oder Tagfunktion. GA-09 bleibt teilweise bearbeitet und wird nicht insgesamt abgeschlossen. Die Dashboard-Gesamtzählung wurde nicht verändert.

Es gab keine Änderung an vorhandenen Galerie-Dateioperationen, CAD-, Bemalungs-, Slicer- oder Workerquellen. Die bestehenden parallelen Änderungen am Backup-Prüfer wurden erhalten. Das Projekt bleibt Beta.

## Vertrag

`GET {API_BASE}/gallery/duplicates?folder=<relativer Galerieordner>`

Die Route nutzt die bestehende API-Basis und Komponenten-Domain. Damit erhält der neue Routenname keinen zusätzlichen Versionssuffix; die noch ausstehende übergreifende Namensmigration bleibt getrennt.

Anmeldung ist erforderlich. Der Aufruf verwendet das vorhandene kanonische Galerie-Repository beziehungsweise dessen unveränderten konfigurierten Archivpfad. Ein fehlender Galerieordner wird nicht automatisch angelegt. Es gibt keine Lösch-, Zusammenführungs-, Schreib- oder Druckaktion. Ergebnisse werden nicht zwischengespeichert (`Cache-Control: no-store`).

Die Prüfung gruppiert zuerst nach Dateigröße und hasht nur potenzielle Vergleichsdateien. Inhalt wird blockweise mit höchstens 1 MiB pro Leseanforderung verarbeitet. Pfadtraversierung und verknüpfte Zielordner werden abgewiesen; Links innerhalb des Baums werden gezählt und nicht verfolgt. Hardlinks sind ausdrücklich von unabhängigen Kopien unterschieden. Aus redundanten Inhaltsbytes wird keine tatsächlich rückgewinnbare physische Speichermenge abgeleitet.

Begrenzungen: höchstens 20.000 inventarisierte Einträge, 2 GiB zu hashender Inhalt und 64 Ordnerebenen. Ein kooperatives Zeitbudget von 20 Sekunden wird zwischen Dateioperationen kontrolliert; ein blockierter Betriebssystem-Leseaufruf wird dadurch nicht präemptiv beendet. Änderungen des Bestands während der Prüfung, Lesefehler oder Grenzverletzungen führen zu einem ausdrücklichen Fehler und nicht zu einer scheinbar vollständigen leeren Ergebnisliste.

Nur ein Scan pro Integration läuft gleichzeitig. Bei Abbruch des HTTP-Aufrufs wird dem Prüfer der Abbruch signalisiert. Die Sperre bleibt bis zum tatsächlichen Ende des Executor-Auftrags erhalten. Ein alter Abschlusscallback kann keine neue Prüfung freigeben. Der Befund ist eine zeitlich begrenzte Leseaufnahme und keine Berechtigung für eine spätere Löschung.

## Tatsächliche Tests

58 neue Tests bestehen sowohl in der isolierten Linux-Arbeitskopie als auch im vollständigen Windows-PC-Testlauf:

- 41 Scannerprüfungen: gleiche/verschiedene Inhalte, Unterordner, leere Dateien, Größen-Vorfilter, relative Pfade, Limits, Links, Hardlinks, Lesefehler, Abbruch, Änderungen während der Aufnahme und blockweises Lesen von insgesamt 32 MiB.
- 16 API-/Lebenszyklusprüfungen: tatsächlicher Scanner mit begrenzten Home-Assistant-Doubles, Authentifizierungsdeklaration, Fehlerantworten, unveränderte kanonische Ablage, keine Ordneranlage, genau ein aktiver Scan und Abbruch-/Callback-Konflikte.
- Ein Verdrahtungstest führt die tatsächliche `async_setup`-Funktion mit begrenzten Abhängigkeiten aus und prüft die einmalige zusätzliche Registrierung sowie die erhaltene Galerie-/Queue-Registrierung.

Die Doubles ersetzen keine laufende HA-Instanz und keine Prüfung mit Browser, iPhone oder realer Benutzerbibliothek.

## Vollständiges PC-Gate

Source-Policy, 325 Frontendtests, Produktionsbuild, HA-Core-Build, Python-Syntax-/Importprüfung und Komponenten-Compileprüfung bestanden. Python-Ergebnis: **1.479 bestanden, ein Fehler, neun übersprungen, 15 Untertests bestanden**. Die neun ausgelassenen Prüfungen sind ausdrücklich Linux-spezifische native Prozessgruppenprüfungen auf Windows. Die 58 neuen Tests sind in den 1.479 enthalten und dürfen nicht hinzuaddiert werden.

Verbleibender Fehler:
`tests/test_worker_cancellation.py::WorkerCancellationTests::test_polling_and_cancellation_share_consistent_state`

Der bestehende native Worker-Helfer `job_control.atomic_json` scheitert beim parallelen `os.replace` auf `last_job.json` unter Windows mit `PermissionError: [WinError 5]`. Derselbe Fehler war bereits vor dem Galeriepaket nachgewiesen. Er wurde weder ausgeblendet noch mit einer Testausnahme kaschiert. **Das Gesamtgate ist rot; es gibt keine Deploymentfreigabe.**

Der Connector-Aufruf meldete einen Netzwerkfehler. Die anschließend gelesenen realen Statusdateien beweisen trotzdem den abgeschlossenen Testlauf. Der Werkzeugfehler wurde nicht als Testergebnis gewertet.

Nachweise im kanonischen PC-Projekt:
`.test-results/connector-v6-quality-gate.json`, `.test-results/python-pytest-progress.log`, `.test-results/python-test-status.json` und `.pytest_cache/v/cache/lastfailed`.

## Quellen und Rückweg

Neu: `gallery_duplicate_scan.py` und `gallery_duplicate_views.py` in der HA-Komponentenquelle; drei zugehörige Testdateien unter `tests/`. Bestehende `__init__.py`: ausschließlich ein Import und ein Registrierungsaufruf ergänzt.

Die drei Produktdateien wurden mit dem kanonischen Connector-Quellmanifest per SHA-256 gegen die isoliert geprüfte Arbeitskopie bestätigt:

| Datei | SHA-256 |
| --- | --- |
| `gallery_duplicate_scan.py` | `a35728a923995d3a760319c9f2c56bd47e334a6e8569e4aca2c0a5af56e96930` |
| `gallery_duplicate_views.py` | `ecbbd6e1db58fa814542cb91cd470d071e087769296ed13cc1764b67bb81dfb7` |
| `__init__.py` | `8a5283ac089376ec7a8eb35113f75dd0ad347f5ceb696fafad6c2aa6dbd99c0f` |

Sicherung: `backups/20261004-gallery-duplicates-api/integration-init-rollback.json`. Das exakte reversible Delta nennt Vorher-/Nachherhash und beide Einfügungen. Rücksetzen ist nur bei passendem Nachherhash zulässig; fremde Folgeänderungen dürfen nicht überschrieben werden. Neue Dateien wurden ausschließlich ohne Überschreiben angelegt. Kein Rücksetzen wurde ausgeführt.

## Verbleibende Arbeit

Zunächst den reproduzierten Worker-Gatefehler getrennt korrigieren und den gesamten zusammengeführten Stand erneut prüfen. Danach gesicherte HA-Quellsynchronisierung, Komponentenbereitstellung und angemeldeter Live-GET mit kontrollierter Testbibliothek. Die GUI für Duplikatbefunde, Papierkorb und Tags sind eigenständige verbleibende GA-09-Teile. Der neue Baustein muss außerdem vor Aktivierung in den getrennten Namensmigrationskandidaten übernommen werden.

Die HA-Root-Shell wurde in diesem Arbeitsabschnitt vom Werkzeug-Sicherheitscheck blockiert; kein alternativer administrativer Zugriffsweg wurde dafür verwendet. Kein HA-Deployment, kein öffentlicher GitHub-Schreibvorgang, kein Slice, kein Druckerupload und kein Druckstart.
