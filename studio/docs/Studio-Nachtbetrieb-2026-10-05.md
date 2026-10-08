# Ultimate Studio – Nachtfortsetzung ab 05.10.2026

## Auftrag und Zeitplan

Tara hat die selbstständige Fortsetzung der bestehenden Roadmap bis zu einem ausdrücklichen Stopp beauftragt. Eine ChatGPT-Fortsetzung ist ab 05.10.2026 23:28 Europe/Berlin stündlich ohne Enddatum eingerichtet. Dies ist eine Folge geplanter Bearbeitungen, kein Nachweis eines lückenlos laufenden Agenten oder dauerhaft erreichbarer Werkzeuge. Vor jedem Lauf ein zwischenzeitliches Stopp beachten und dann die geplante Fortsetzung deaktivieren.

Priorität bleibt der vollständige, geprüfte Abgleich des kanonischen PC-Projekts, der privaten HA-Quellkopie und des öffentlichen GitHub-Kandidaten. Keine neue Druck-/Slice-/Uploadfreigabe aus diesem Auftrag ableiten. MCP-Homeassist läuft nativ auf der privaten VM homeassist. KI-VM und Firmen-VM aks-homeaasist-3d bleiben ausgeschlossen.

## Tatsächlich neu untersuchter Bereitstellungsblocker

Quell-/Liveprüfung am 05.10.2026 um 22:29 CEST: Die neue Workerquelle enthält job_control.py mit SHA-256 1226e2818657d5d069bbcd6ae994144f2ba05240ce3b9e600f4cf1c6357b3935. Auf dem produktiven Worker fehlt diese Datei. Der bisherige Deployer nennt sie nur in DEPENDENCY-SHA256SUMS, nicht in RUNTIME_FILES und nicht in SHA256SUMS. Damit ist sie als bereits vorhandene Voraussetzung behandelt, obwohl sie mit dem neuen Worker installiert werden muss. Das ist eine Paketinkonsistenz, unabhängig von Werkzeugzugangsproblemen.

Die rein lesende Aufnahme zählte null *.queued.json, null *.slicing.json und keinen Dispatcher-Lock. Dies ist eine Momentaufnahme und keine dauerhafte Deploymentfreigabe; vor jeder Aktivierung erneut prüfen, einschließlich Druckerzustand.

## Isolierter Reparaturkandidat – noch nicht kanonisch übernommen

Ablage auf HA:
`/var/lib/homeassistant/homeassistant/backups/20261005-native-deploy-closure/`

Darin source-before/, candidate/, patch-status.json und candidate-tests.xml. Veränderte Dateien im Kandidaten:

- deploy/homeassistant/host/3d-printer-slicing-server/deploy-native-slicer.sh
- deploy/homeassistant/host/3d-printer-slicing-server/SHA256SUMS
- deploy/homeassistant/host/3d-printer-slicing-server/DEPENDENCY-SHA256SUMS
- tests/test_v6_native_slicer_canonical_sources.py
- neu: tests/test_native_deploy_package.py

Korrektur: job_control.py wird eigenes, quellhashgeprüftes Laufzeitmodul und Teil der vorhandenen Backup-/Installations-/Rollbackschleifen. Änderungen am Modul verlangen ebenso wie server.py den Worker-Neustart. Die Python-Syntax wird vor Dienständerungen geprüft. Abschließend werden die installierten Laufzeit- und Unitdateien bytegenau mit der Quelle verglichen, bevor ein Deploymenterfolg gemeldet wird.

SHA-256 des Kandidaten:

| Datei | SHA-256 |
| --- | --- |
| deploy-native-slicer.sh | 077dfb5eaed8fef2fba2d674992a4c0ebf0f8f862e0db410fecba66661b19f98 |
| SHA256SUMS | 73bf4cf8991c4777bf24c2ae9fb05dd318f4e17c309333ab3a3c9f3e779e5e65 |
| DEPENDENCY-SHA256SUMS | 6bd6181e06e82a80686443ec5a4e83cb4e1d893118935706b352327d6c6e2e33 |
| test_v6_native_slicer_canonical_sources.py | 0568fac67043f7a3fda95e4088f831db617d0c3caef726f98e5fcd35f0b00b55 |
| test_native_deploy_package.py | afa02802198a576471b07f8d10994382744f88b9e8a3fd5477f28d67a4c08c81 |

## Ausgeführte Verifikation

Bash-Syntaxprüfung bestanden. Isolierter Linux-Prüflauf: **24 bestanden in 3,86 Sekunden**, kein Fehler und keine ausgelassene Prüfung. Davon 18 neue Paketprüfungen und sechs bestehende kanonische Prüfungen.

Die Shellprüfungen führen den tatsächlichen Deployer in einem privaten Dateibaum mit umgebundenen Zielverzeichnissen aus. systemctl und curl sind Testdoubles; die Statusauffrischung ist ein ausdrücklich wirkungsloser Testpayload. Die Privilegienprüfung ist nur im Test rebound, nicht im Produkt geändert. Keine echten Dienste, Netzwerkverbindungen, Workerjobs oder Drucker werden durch diese Tests angesprochen. Geprüft wurden fehlendes/älteres Helfermodul, unveränderter Paketstand, aktive/queued/Dispatcher-Sperren, ungültige Python-Syntax, unverändert strenge externe Abhängigkeiten sowie Rücknahme bei Restart-, Health- und Dateiintegritätsfehlern.

Die geplante Gegenprobe der neuen Tests am alten Original wurde vom Werkzeug-Sicherheitscheck VOR Ausführung gesperrt. Kein Rot/Grün-Nachweis am Original wird behauptet.

Die anschließende Übernahme der fünf Dateien nach PC und HA-Entwicklungsquelle wurde ebenfalls VOR Ausführung gesperrt. Es wurde kein alternativer Zugriff zum Umgehen dieser Sperre verwendet. Daher: **Kandidat vorhanden und gezielt geprüft, kanonische Produktquellen unverändert, neues Gesamtgate offen, GitHub-Übernahme offen, keine Live-Aktivierung.**

## Nächste Fortsetzung

1. Dieses Protokoll und den tatsächlichen aktuellen Quellenstand lesen; Kandidatenhashes und Originalhashes gegen patch-status.json prüfen. Zwischenzeitliche Änderungen erhalten.
2. Reguläre, nicht umgehende Werkzeugverfügbarkeit prüfen. Bei freigegebener Operation Kandidat nach frischem PC-Abgleich und Originalsicherung zuerst im kanonischen PC-Projekt übernehmen; dann HA-Quelle und öffentlichen Kandidaten synchronisieren.
3. Vollständiges PC-Gate und Linux-Tests einschließlich der nativen Paketfälle ausführen. Ergebnisse aus den echten Statusdateien lesen, Zeitlimits nicht als Erfolg ausgeben.
4. Gesamten noch offenen Releaseumfang abgleichen. Erst danach kontrollierte getrennte HA-/Frontend- und Workerbereitstellung mit neuer Live-Vorabprüfung, Tagesbackup und verifiziertem Rückweg; anschließend reale Bedienabnahme.
5. Weitere bestehende Roadmap bearbeiten. Bei fehlenden Restaufgaben kleine reversible Verbesserungen planen, keine kostenpflichtigen Dienste, neue Berechtigungen oder Architekturwechsel eigenmächtig einführen.

GitHub-Stand während dieser Aufnahme: PR #1 weiterhin Entwurf, Branch sync/studio-release-20261005 bei 2dd294721d24d4dcfbcd905a4789be23ce32184d, kein Merge. Dieser Nachtkandidat ist dort noch nicht enthalten. Produktbetrieb und Beta-Abnahmestatus wurden nicht verändert.
