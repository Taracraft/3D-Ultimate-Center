# Ultimate Studio · Quellabgleich PC → Home Assistant · 05.10.2026

## Nachgewiesener Fortschritt

Das zuvor blockierte `makerworld_transfer.py` konnte in diesem Abschnitt über den unveränderten kanonischen PC-Dateitransfer bereitgestellt werden. Die 10.004 Bytes wurden ins private HA-Staging übertragen; SHA-256: `b147558c69061cdc060e2817387cdcf47f39485e3ae9df9c2f9d7b09fc347766`.

Danach wurden 662 ausgewählte Quell-, Test-, Dokumentations- und Deploydateien vom PC aufgenommen. Jeder Inhalt wurde anschließend ein zweites Mal über den PC-Connector gelesen und mit der aufgenommenen Datei verglichen. Das vollständige Deploymanifest und die PC-Gatestatusdatei blieben während dieser Aufnahme unverändert. Aufnahme abgeschlossen: 07:52:40 CEST.

Die HA-Entwicklungsquelle wich in 52 dieser Dateien ab. Vorhandene Originale wurden unter `source-before/` im Sicherungsordner gespeichert. Die 52 Änderungen wurden ausschließlich in die HA-Quellkopie `3D-Studio/v6` übernommen, nicht in die installierten HA-Komponenten, das ausgelieferte `www` oder den nativen Worker. Abschluss um 07:55:16 CEST: Alle 662 Dateien des definierten Paketumfangs stimmen bytegenau mit dem PC-Kandidaten überein. Andere Dateien und Verzeichnisse wurden weder gelöscht noch ersetzt. Das ist ein Nachweis dieses Paketumfangs, keine pauschale Aussage über jede historische Projekt- oder Laufzeitdatei.

Enthalten sind insbesondere die neuen Materialfarben-Helfer und Parserkorrekturen, das 95-Prozent-MakerWorld-Popup samt Wiederaufnahme nach Browser-Seitencache, die Galerie-Duplikatansicht, die MakerWorld-Transferbehandlung und die bereits am PC korrigierte Workerquelle. Quellkopie und produktive Installation bleiben ausdrücklich getrennt.

## Prüfstand

Der zur Aufnahme gehörende vollständige PC-Gatelauf endete um 07:35:48 CEST mit `success=true`. Die vollständige Statusdatei wurde auf HA gespeichert und ausgewertet:

- 440 Frontendtests bestanden, kein Fehler.
- 1.576 Python-/Worker-Tests und 15 Untertests bestanden; neun Linux-Prozessgruppentests wurden unter Windows plattformbedingt ausgelassen.
- Source-Policy, TypeScript, Produktionsbuild, HA-Core-Build, Syntax, Imports und Komponentencompile bestanden.
- Zusätzlich wurden in diesem Abschnitt 314 Pythonquelldateien des aufgenommenen Pakets direkt auf HA syntaktisch kompiliert, ohne ihre Module auszuführen. Das ist kein neuer kompletter Linux-Testlauf.

Der ursprünglich zu lange serielle Aufnahmeaufruf erreichte sein Zeitlimit. Er wurde nicht als Erfolg gewertet. Die Aufnahme wurde anhand des gespeicherten Zwischenstands fortgesetzt und erst nach vollständiger Zweitleseprüfung als erfolgreich markiert.

## Noch keine produktive Aktivierung

Ein weitergehender Vorabprüfaufruf wurde vom OpenAI-Werkzeug-Sicherheitscheck gesperrt. Der spätere Aufruf für Supervisor-Core-Status und die vorhandene Puppet-Startseite wurde ebenfalls vor der Ausführung blockiert. Gesperrte Anmeldedaten-/Optionslesezugriffe wurden nicht über einen alternativen Zugriff nachgeholt.

Der separate native HA-Connector lieferte beim Skillabruf und bei einer reinen Sensorsuche jeweils HTTP 502. Das belegt einen Fehler dieses Connectorpfads, nicht einen Ausfall der HA-VM. Dateizugriff und Quellabgleich über Homeassist MCP waren dagegen erfolgreich.

Aus diesem Abschnitt wurden keine produktiven Komponenten oder Frontenddateien installiert, keine Dienste neu gestartet, keine Konfigurationen geändert und keine Druck-/Slice-/Uploadbefehle ausgelöst. Der laufende Druckauftrag und seine Farbfolge wurden nicht verändert.

Letzter in diesem Abschnitt gelesener Live-Frontendhash: `29fc7bc256736fc7652555668b3a36ba3e9f9a7ac0bd22b7a96a7e346fb54eec`.
PC-/HA-Quellpaket, gebautes HA-Frontend: `f2f1790a2965ec7e101fde141cbc893a60b74269e6ef91adb5f5619d354d90ed`.
Die unterschiedlichen Hashes dürfen nicht als erfolgreiche Live-Aktivierung ausgegeben werden.

## Öffentlicher Abgleich

GitHub wurde über den nativen Connector lesend geprüft und ein separater öffentlicher Kandidatencheckout angelegt. `main` stand dabei auf `770725483bf51233d6d00408a5aabdf36b1fe893` vom 03.10.2026. Kein Commit und kein Push wurde erstellt.

Wichtig für die Fortsetzung: Das öffentliche Repository hat die Wurzelbereiche `studio-v6/`, `homeassistant/`, `slicing-server/` und `deployment/`. Die PC-Projektwurzel darf nicht ungeprüft auf die öffentliche Repositorywurzel kopiert werden. Die anfängliche flache Vergleichsliste `public-candidate-diff.json` ist deshalb keine Freigabe zum Kopieren; vor Veröffentlichung ist die vorhandene Zuordnung samt Build-/Importvertrag korrekt anzuwenden. Bestehende V5-Verzeichnisse bleiben unberührt.

## Nachweise und Rückweg

HA-Sicherungsordner: `/var/lib/homeassistant/homeassistant/backups/20261005-studio-release-sync/`.

`pc-snapshot-status.json` enthält alle 662 Kandidatenhashes und den Abschluss der Zweitleseprüfung. `pc-deploy-manifest.json` enthält 156 kanonische Deploydateien. `pc-gate-before.json` enthält den vollständigen PC-Testlauf. `source-diff.json` und `source-sync-status.json` dokumentieren die 52 tatsächlichen HA-Quelländerungen samt Vorher-/Nachherhash. Originale stehen unter `source-before/`; neue Dateien sind am fehlenden Vorherhash erkennbar. Die nachträgliche Dokumentation wird separat durch `documentation-sync-status.json` nachgewiesen.

Rücknahmen nur bei exakt passendem Nachherhash durchführen; danach den ursprünglichen Hash prüfen. Keine späteren Änderungen überschreiben. Es wurde kein Rollback ausgeführt.

## Offene Reihenfolge

Verlässliche produktive Vorabprüfung und Supervisor-/Puppet-Zugriff wiederherstellen; öffentliche Pfadzuordnung prüfen und den vollständigen zusammengehörigen Stand synchronisieren; danach getrennte abgesicherte Komponenten-/Frontend- und Workerbereitstellung mit Live-SHA-Prüfung. Anschließend echte Desktop-/iPhone-Abnahme und erneute Prüfung des MakerWorld-Anmeldungs-/Importproblems. Dashboard und Namensmigrationskandidat bleiben offen. Beta wird nicht vor diesen Nachweisen beendet.
