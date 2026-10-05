# Ultimate Studio · Linux-Neuaufbauvertrag

## Umfang und Status

REL-BOOTSTRAP-20261005 bleibt teilweise umgesetzt. Der bisherige destruktive Einstieg `scripts/rebuild-homeassist.sh` wird im Release-Arbeitsbranch durch eine ausschließlich lesende Paketprüfung beziehungsweise die explizite Erstellung eines neuen isolierten Quellpakets ersetzt. Keine Paketinstallation, keine Kopie der alten Anwendung, keine Löschung bestehender Verzeichnisse und kein Dienststart sind darin enthalten. `main` bleibt bis zum geprüften vollständigen Abgleich und der Abnahme unverändert.

Der neue Python-Prüfer akzeptiert ausschließlich die festgelegten nativen Runtime- und Abhängigkeitsdateien sowie fünf Systemd-Units. Er prüft beide Manifeste, jeden Inhalt und die tatsächlichen Dateilisten des Deployskripts. Absolute Pfade, Traversierung, unbekannte Manifesteinträge, Verknüpfungen, Größenüberschreitungen und Änderungen während der Aufnahme werden abgewiesen. Öffentliche Systemd-Dateien werden aus `deployment/systemd/` dem nativen Paketpfad `systemd/` zugeordnet. Vorhandene produktive Abhängigkeiten werden niemals heimlich als Ersatz für fehlende Quellpaketdateien verwendet.

Die kanonische Scriptkopie unter `studio-v6/scripts/` ist bytegleich mit dem öffentlichen Kompatibilitätseinstieg unter `scripts/`; CI überprüft dies. Beide enthalten keine automatische Aktivierung. Hashnachweise belegen nur die Übereinstimmung mit dem geprüften Quellstand, keine Hersteller-Signatur oder Releasefreigabe.

## Bedienung nach vollständigem Quellabgleich

```bash
bash scripts/rebuild-homeassist.sh --check
bash scripts/rebuild-homeassist.sh --stage /neuer/isolierter/kandidat
```

Der erste Aufruf liest nur. Der zweite reserviert ausschließlich einen noch nicht existierenden Zielordner außerhalb der Quelle und bekannten Produktivpfade, schreibt einen begrenzten Dateiumfang, liest die Dateien zurück und erzeugt den Abschlussnachweis zuletzt. Auch ein bereits existierender leerer Ordner wird nicht ersetzt. Bei einem Fehler bleibt der unvollständige neue Ordner zur Diagnose zurück; er gilt nicht als freigegeben.

Dies ist ausdrücklich KEIN vollständiger Installer. Bambu-Engine und Hostbibliotheken, private Konfiguration/Authentifizierung, HA-Komponente und Frontend, aktuelle Druck-/Jobzustände, Rückweg, vollständiges Qualitätsgate und Live-/Browserabnahme bleiben zusätzliche Voraussetzungen. Der bestehende native Deployer wird von diesen Aufrufen nicht ausgeführt.

## Nachweise und bestehende Paketlücke

57 isolierte Linuxfälle bestanden ohne Fehler oder Auslassung. Sie verwenden synthetische Quellbäume und Fallen für frühere Installations-, Lösch- und Dienstbefehle. Das tatsächliche öffentliche Quellarchiv des Ausgangscommits `0880ccf9bda0a0c40c92b50b48c63ac787b34364` wurde zusätzlich gelesen: Dessen Abhängigkeitsmanifest enthält `job_control.py` noch nicht. Der neue Prüfer verweigert diesen unvollständigen Stand. Das ist ein offener Synchronisierungsbefund, kein Fehler, der durch Lockerung des Prüfers verdeckt werden darf.

Der neue Workflow trennt die 57 synthetischen Vertragstests ausdrücklich von der Prüfung des tatsächlichen öffentlichen Pakets. Letztere muss rot bleiben, solange Bestand oder Prüfsummen nicht zusammenpassen. Ein grüner Vertragstest allein ist keine Installationserlaubnis.

## Lokaler Gesamttest und Anschlussarbeit

PC-Gesamtgate am 06.10.2026, 00:15:47 CEST: 440 Frontendtests, 1.648 Python-/Worker-Tests und 15 Untertests bestanden; 40 explizit plattformabhängige Prüfungen unter Windows ausgelassen. Davon neun neue Symlink-/Bashfälle, die im isolierten Linuxlauf erfolgreich geprüft wurden. Source-Policy, TypeScript, beide Builds, Syntax, Imports und Komponentencompile bestanden. Die Testzahlen sind nicht additiv als neue Gesamtsumme zu verstehen.

Eine vorhandene Sourceprüfung der fünf Systemd-Units scheiterte zuvor allein an der einzeiligen Schreibweise der Shellschleife. Sie prüft jetzt die tatsächliche vollständige Wortliste; fünf zusätzliche Fälle sichern gültige Schreibweisen sowie Ablehnung fehlender, doppelter und fremder Units ab. Die produktive Host-Vorabprüfung wurde dafür nicht verändert. Zusammen mit den neuen Paketfällen bestanden isoliert 66 Prüfungen.

Die drei neuen Quell-/Testdateien und diese Testkorrektur sind im PC-Projekt vorhanden. Die HA-Quellkopie wurde um 00:22:45 CEST für diese fünf zusammengehörigen Dateien (einschließlich der unveränderten Host-Vorabprüfung) per Hash abgeglichen. Keine Live-Bereitstellung, kein Dienstneustart und keine Aktion an der Firmen-VM.

Offen: vollständiger kanonischer und öffentlicher Quellenumfang einschließlich nativer Abhängigkeiten, Versions-/Namensmigration, tatsächlicher Installations-/Wiederanlaufvertrag und koordinierte Aktivierung. Der Termin ersetzt die Beta-Abnahmekriterien nicht.
