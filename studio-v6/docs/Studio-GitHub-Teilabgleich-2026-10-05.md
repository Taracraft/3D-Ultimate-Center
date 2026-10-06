# Ultimate Studio · GitHub-Teilabgleich · 5. Oktober 2026

## Tatsächliches Ergebnis

Neun Quell-/Testdateien wurden in zwei zusammengehörigen Schritten in das öffentliche Repository `Taracraft/3D-Ultimate-Center` übertragen. Zwei Prüfmanifeste und ein GitHub-Actions-Workflow ergänzen den Nachweis. Insgesamt umfasst der Entwurfs-Pull-Request zwölf geänderte Dateien. Das ist ausdrücklich **kein vollständiger Upload des gesamten PC-Projekts und keine produktive HA-Bereitstellung**.

Der neuere öffentliche STL-Testcommit wurde erhalten. Ausgangsstand und zuletzt erneut gelesener Stand von `main`: `ce86ff53db9bdeb05e603fe6230eac7810989f6d`. Vor dem Abgleich wurde die Sicherungsreferenz `backup/before-studio-release-sync-20261005` auf diesen Stand gesetzt.

Arbeitsbranch: `sync/studio-release-20261005`.

- Erster Commit: `fec52fe26791fc0e3743fe17beeeec0fef73da7d` – MakerWorld-Transfer und Quellidentität.
- Zweiter Commit: `748b6a276b4891ba5b0fa8779888a2957f72a867` – auftragsgebundener Farbparser und gemeinsamer Palettenhelfer.
- Entwurfs-Pull-Request: https://github.com/Taracraft/3D-Ultimate-Center/pull/1
- Erfolgreicher aktueller Prüflauf: https://github.com/Taracraft/3D-Ultimate-Center/actions/runs/37282487015

Kein Force-Push, keine Zusammenführung nach `main` und keine Änderung an den öffentlichen V5-Verzeichnissen wurden ausgeführt. Die vorhandene öffentliche Pfadstruktur bleibt erhalten: Projektquellen unter `studio-v6/`, HA-Komponenten unter `homeassistant/custom_components/`.

## Übertragener Quellumfang

| Bereich | Tatsächlich übertragene Dateien |
| --- | --- |
| MakerWorld | `makerworld_transfer.py`, `makerworld_runtime.py`, `makerworld_download.py`, `test_makerworld_transfer_contract.py` |
| Materialfarben | `gcode_toolpath.py`, `toolpath-material-colors.ts`, `test_toolpath_palette_integrity.py` |
| Abgleichnachweis | `studio_source_fingerprint.py`, `test_source_fingerprint.py` |

Die GitHub-Prüfmanifeste binden jede dieser Dateien an SHA-256 und die bytegenaue Git-Blob-Identität. Die zurückgegebenen Git-Blob-IDs für den Downloadpfad, den Parser und den TypeScript-Helfer wurden mit dem auf dem PC erzeugten Quellinventar verglichen. Der kleine Parserregressionstest wurde zusätzlich anhand des vollständig gelesenen PC-Textes, seiner Bytezahl und seines daraus berechneten Hashes abgeglichen.

Die beiden neu auf dem PC angelegten Fingerprint-Dateien führen weder Quellcode aus noch Netzwerkzugriffe, Veröffentlichungen oder Deployments durch. Sie erzeugen als Testnachweis ein zweifach gelesenes lokales Inventar. Dessen 869 Einträge bezeichnen den Umfang dieser Aufnahme und **nicht** die Zahl bereits hochgeladener oder systemübergreifend synchroner Dateien. Private Arbeitsprotokolle, Zugangsdaten und produktive Laufzeitdaten wurden nicht als Inhalt hochgeladen.

## Verifizierte Tests

Der zweite GitHub-Lauf wurde mit `conclusion=success` bestätigt. Das Ergebnisartefakt mit ID `11333150138` wurde heruntergeladen und gegen seinen von GitHub gelieferten SHA-256 geprüft:

`2765a902ceac8ba68e41ebdb23bab5613f6cb45130db3e3d708fd4bce9dd3111`

Die tatsächliche JUnit-Datei enthält **78 Pythonprüfungen, null Fehler, null ausgelassene Prüfungen**. Der tatsächliche Node-Ausgabelog enthält nach strenger TypeScript-Kompilierung des Palettenhelfers **acht bestandene Prüfungen, null Fehler, null ausgelassene Prüfungen**. Die Pythonfälle teilen sich in 55 MakerWorld-, 13 Paletten- und zehn Fingerprint-Prüfungen auf. Die 65 Prüfungen des ersten GitHub-Laufs sind im zweiten enthalten und werden nicht hinzuaddiert.

Der Workflow hat nur `contents: read`. Er installiert isolierte Testabhängigkeiten, stellt im temporären Checkout die bestehende Komponenten-Pfadzuordnung für die Tests her, verifiziert die Quellhashes und prüft den ausgewählten Quellumfang. Er greift nicht auf HA, ein Bambu-Konto oder einen Drucker zu und veröffentlicht selbst keine Änderungen.

Auf dem PC wurde ebenfalls ein erneuter vollständiger Gate-Aufruf angestoßen. Der Connector-Aufruf lief ins Zeitlimit; danach wurde die neue tatsächliche Gate-Statusdatei gelesen. Sie meldet `success=true` für den um 09:42:03 CEST begonnenen Lauf. Die vollständig gelesene Python-Statusdatei bestätigt `phase=completed`, `pytest_code=0`, erfolgreiche Syntax und Imports. Eine neue genaue Gesamtzahl der PC-Pythontests wurde in diesem Abschnitt nicht aus dem vollständigen Langlog ausgelesen und wird daher nicht aus älteren Zahlen hochgerechnet.

Diese Nachweise sind keine Browser-/iPhone-Abnahme, kein erfolgreicher Import des tatsächlich gemeldeten MakerWorld-Modells und keine Bestätigung einer laufenden neuen HA-Komponente.

## Grenzen und blockierte Schritte

Die erneuten administrativen HA-Vorabprüfungen wurden vom Werkzeug-Sicherheitscheck vor der Ausführung gesperrt. Ebenso wurde das Anlegen eines größeren Quellpaket-Vorbereiters auf dem PC gesperrt. Dieser vorbereitete Bulk-Transfer wurde deshalb nicht ausgeführt. Gesperrte Aktionen wurden nicht über andere administrative Zugänge nachgeholt. Die bereits erlaubten nativen GitHub-Einzeldateiaktionen wurden für den oben vollständig aufgeführten Quellumfang genutzt.

Es wurde kein HA-Deploy, kein Komponentenreload, kein Dienstneustart, kein Slice, kein Job-Release, kein Druckerupload und kein Druckstart ausgeführt. Aus diesem Abschnitt wird kein aktueller Live-Frontendhash behauptet, da die erneute Live-Prüfung nicht durchlief.

Der letzte zuvor verifizierte PC-/HA-Abgleich von 662 ausgewählten Dateien bleibt ein Nachweis seines damaligen Umfangs. Die hier neu angelegten Fingerprint-Dateien und ergänzenden Nachweise wurden noch nicht in die HA-Quellkopie übernommen. Somit sind auch jetzt nicht sämtliche Projektdateien auf PC, HA und GitHub identisch.

## Offene Reihenfolge

1. Restliche zusammengehörige Hauptvorschau-, eigenständige Viewer-, Popup-, Galerie-, CAD- und Workerquellen einschließlich Tests öffentlich abgleichen. Der hier hochgeladene Palettenhelfer allein ist noch nicht der vollständige Materialfarben-Standard der Hauptansicht.
2. Den gesamten öffentlichen Kandidaten mit dem aktuellen PC- und HA-Quellstand abgleichen; die passenden Buildartefakte und das vollständige gemeinsame Gate bestätigen. Den aktuellen Entwurf erst dann zusammenführen.
3. Vorabprüfung der produktiven HA-Ziele, gesicherte getrennte Frontend-/Komponenten- und Workerbereitstellung, Live-Hashes und reale Desktop-/iPhone-Abnahme.
4. MakerWorld-Anmeldung/Berechtigung und echten Import abschließen; danach Prüfdashboard, Namensmigrationskandidat und die weiteren offenen Roadmap-Themen nachführen.

Die Release-Abnahme und der Beta-Ausstieg bleiben offen. Der Entwurfs-Pull-Request enthält diese offenen Punkte ausdrücklich als Checkliste.
