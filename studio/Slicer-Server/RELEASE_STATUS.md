# Release, Systemverifikation und Betrieb

**Aktueller Produktstatus: Release noch nicht abgeschlossen.** Stand: 16. Oktober 2026.
Diese Seite ist der gemeinsame Einstieg für den Veröffentlichungsumfang. Sie
unterscheidet eine belegte Quelllieferung, den vollständigen Produktrelease und
die danach vorgesehene frische Systemverifikation. Sie ändert keine Freigabefelder.

## R – Vollständiger Release vor der letzten Neuinstallation

Meilenstein R ist erst erreicht, wenn alle beauftragten Funktionen und ihre
notwendigen Vorabprüfungen, die Host-/HA-Integration, konkrete Enginepakete,
Quellen-/Lizenz-/Noticepflichten, Installationspakete, Dokumentation und
Veröffentlichungen abgeschlossen sind. Benötigte Downloads müssen tatsächlich
verfügbar sein. Ein leerer Enginekatalog, ein privater Pflichtdownload oder eine
unimplementierte Hosteinrichtung darf nicht auf den letzten Linux-Test verschoben
werden. Vollständige öffentliche Releasepakete sind von Quellcommits zu trennen.

Die frische Installation auf dem separaten Linux-Testserver ist der vereinbarte
letzte Verifikationstest und darf bei R als einzige vereinbarte abschließende
Systemverifikation noch `not_run` sein. Das ersetzt keine vorab erforderliche
Funktions-, Integritäts- oder Integrationsprüfung in einer zulässigen Prüfumgebung.

## V – Frische Systemverifikation nach dem Release

Meilenstein V prüft den bereits veröffentlichten, unveränderten Release auf einem
sauberen separaten Linux-System: Installation, Mounts und Rechte, Hostkommunikation,
TLS/Auth, HA/HACS, Neustart und Persistenz, Upgrade, Rollback und Restore.
Das [Linux-Runbook](LINUX_TEST_SERVER_RUNBOOK.md) beschreibt den getrennten Ablauf.
Nicht veröffentlichte Hilfsdateien dürfen nicht heimlich ergänzt werden.

`not_run`, `blocked`, `partial` und tatsächlich bestandene Ergebnisse bleiben
unterscheidbar. Gefundene Fehler erfordern eine nachvollziehbare Produktkorrektur
und betroffene Wiederholprüfungen. Ein auf einer Maschine funktionierender
Sonderweg ersetzt keinen reproduzierbaren Installationsweg.

## L – Produktiver Betrieb und Migration bleiben getrennt

R ist keine Freigabe einer ungeprüften Produktionsinstallation. Ein bestehendes
natives Live-System wird durch Quellveröffentlichung und Systemtest nicht
migriert. Ein produktiver Pilot oder eine HAOS-Migration braucht den gesonderten
Auftrag und geeignete Betriebsnachweise; er ist keine stillschweigende Voraussetzung
für die Quellveröffentlichung. Kein Test startet allein einen Slice, Upload,
Druckerbewegung, Heizvorgang oder Druck. Ein echter Slice und ein Druckstart sind
getrennte Aktionen; der Druckstart behält seine zweistufige Bestätigung.

## Zuletzt belegter Bestand und tatsächliche Lücken

| Ebene | Belegter Bestand | Noch keine daraus folgende Zusage |
| --- | --- | --- |
| Studioquellen | Öffentlicher Studio-Stand `95d8d594851e2c8d8ea5938cb0a333d17a3bf237`; genaue Quell-CI erfolgreich, einschließlich 571 Frontendfällen | Keine vollständige reale Desktop-/iPhone-/Druckerabnahme |
| Slicerquellen | Komponentenstand `074c89bfd18c0ee806906e2499c182a8746a5666` mit eigener erfolgreicher Quell- und Image-CI | Kein veröffentlichter fertiger Slicer-Release |
| Prüfimage | Am genannten Slicer-Stand gebautes Source-Preflight-Image mit 357 erfassten Debian-Paketen und 42 Pflichtpaketen | Keine Engine-Binaries, kein veröffentlichtes Runtime-Image, keine Betriebsfreigabe |
| Engineauswahl | Vorhandene Bundle-, Auswahl-, Staging- und Aktivierungsverträge sowie abgegrenzte Originalnachweise | Reale Katalogbindung, vollständige Herkunfts-/Datei-/Ressourcen-/Bibliothekszuordnung und konkrete Auslieferung noch offen |
| HACS | Reproduzierbarer privater Kandidat, 135 Dateien, Build `9b8ccfd212` | Kein veröffentlichter HACS-Release; keine behauptete Aufnahme in einen offiziellen Katalog |
| Host und HA | Geprüfte Teilmodule und Verbindungskonfiguration | Vollständiger unterstützter Provisionierungsweg noch nicht integriert |
| Veröffentlichungswege | Vollständige versionierte Wiki-Quellen | Slicer-Repository beim letzten Abgleich privat, Wiki deaktiviert, beide Release-Listen leer |

Die Zahlen sind datierte Nachweise der genannten Stände, keine dynamische Anzeige
der heute installierten Version. Nach Änderungen zählt die CI des jeweiligen
Commits. Ein alter Imagebeleg wird gegen seine erhaltene ursprüngliche
Quellprojektion geprüft, nicht gegen ein inzwischen geändertes `main`.

## Konkrete Lieferprüfung für R

| Liefergegenstand | Erforderlicher Nachweis |
| --- | --- |
| Studio/HACS | Version, Build, vollständige Paketmitglieder, passende Integrations-/Frontendquellen, veröffentlichte Paketbytes und Hashes |
| Slicer/Container | API, Worker und benötigte Ressourcen; reproduzierbares Runtime-Image oder fest gebundener Installationsweg; kein Entwicklungs-PC als Voraussetzung |
| Engines | Reale Bambu-/Prusa-/Cura-Paketmetadaten und Dateiauswahl, passende Profile/Plugins/Bibliotheken, Herkunft und erforderliche Quell-/Noticebereitstellung |
| Hosteinrichtung | Dokumentierter unterstützter Bootstrap und Kommunikationsvertrag, Fehler-/Wiederanlauf-/Datenerhaltungsnachweise vor dem letzten Systemtest |
| Bedienung | Zugeordnete Funktionsnachweise; Bild- und Mobilabnahme nur am tatsächlich geladenen Build, nicht aus einer Testanzahl abgeleitet |
| Öffentliche Lieferung | Slicer-Sichtbarkeit, echtes Wiki, vorhandene Releaseassets und bezogene Paket-/Image-Digests ohne private Sonderfreigabe |
| Dokumentation | README, Handbuch, Wiki, Paketversionen und Abnahmematrix widerspruchsfrei; keine Secrets oder privaten Betriebsdaten |

## Aussagen der bestehenden Prüfwerkzeuge

`verify_image_evidence.py` prüft Quellen und das Source-Preflight-Image; sein
`release_complete=false` und `production_approved=false` bleiben bewusst erhalten.
Es ist kein Produktrelease-Freigabewerkzeug. Der optionale Linux-Nachweis kann
fehlen, ohne einen bestandenen Image-/Quelltest rückwirkend ungültig zu machen.

Auch `linux_test_evidence.py` belegt nur die von ihm geprüften Systemphasen. Ein
Exitcode 0 ist keine zusätzliche Lizenz-, Veröffentlichungs- oder allgemeine
Produktivfreigabe. `engine_catalog.json`, `container_deploy_ready`,
`native_deploy_ready` und alle anderen Schutzfelder werden nicht aufgrund dieser
Dokumentationskorrektur umgeschrieben. [Vertragsdetails](IMAGE_EVIDENCE.md).

## Belegquellen

- [Studio-Quellcommit](https://github.com/Taracraft/3D-Ultimate-Center/commit/95d8d594851e2c8d8ea5938cb0a333d17a3bf237) und [zugehörige CI](https://github.com/Taracraft/3D-Ultimate-Center/actions/runs/38941284916)
- [Slicer-Quellcommit](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/commit/074c89bfd18c0ee806906e2499c182a8746a5666) und [zugehörige CI](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/actions/runs/38881788130); solange privat nicht allgemein zugänglich
- [Enginekatalog](engine_catalog.json), [Provenienz](ENGINE_PROVENANCE.md), [Paket-/Imagebeleg](IMAGE_EVIDENCE.md) und [Abnahmematrix](wiki/Release-Abnahme.md)

Erst ein eigener vollständig belegter Releaseabschluss darf R bestätigen.
Die unveränderten technischen Prüfer geben diese Bestätigung nicht stellvertretend.
