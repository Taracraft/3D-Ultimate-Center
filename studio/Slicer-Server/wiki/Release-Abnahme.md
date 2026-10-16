# Gemeinsame Release- und Systemabnahme

**Release noch offen.** Maßgeblich ist die Trennung in
[R – vollständiger Release, V – letzte Linux-Systemverifikation und L – gesonderter Betrieb](../RELEASE_STATUS.md).
Diese Reihenfolge ersetzt ältere Abschnitte, die den frischen Testserver oder
einen produktiven Pilot zwingend vor den Release gestellt haben. Fehlende
Implementierung oder Auslieferung wird dadurch nicht freigegeben.

## R: vor Veröffentlichung des vollständigen Releases schließen

| Bereich | Vorhanden | Vor R noch vollständig zu belegen |
| --- | --- | --- |
| Studiofunktionen | Versionierte Implementierung und konkrete Teilprüfungen, einschließlich datenerhaltender Projektimporte | Vollständige beauftragte Abläufe und notwendige echte Bedien-/Bildabnahmen; keine Vollabnahme aus Teiltestzahlen |
| Quell- und Paketidentität | Manifestgebundene Studio-/Slicerquellen und genaue Commit-CI | Finale zusammenpassende Studio-, HACS-, Slicer-, Engine-/Quell- und Containerartefakte |
| Engines | Originalinventare und Bundle-/Katalog-/Staging-/Aktivierungsverträge | Alle konkreten Pakete und Dateiauswahlen, Profile, Ressourcen, Plugins und passende Bibliotheken; echte Funktionsnachweise im freigegebenen Umfang |
| Herkunft und Rechte | Abgegrenzte Original- und Quellnachweise, vorhandene Notice-Texte | Vollständige Datei-/Komponentenbindung und erforderliche Quellen-/Noticeauslieferung; keine Freigabe allein aus einem Hash |
| Runtime-Image | Reales geprüftes Source-Preflight-Image vorhanden | Vollständiges nutzbares Engine-Laufzeitpaket beziehungsweise fester geprüfter Installationsweg; Prüfimage nicht als Runtime vermarkten |
| Host-/HA-Integration | Registry-, Transport-, Verbindungs-, Transaktions- und Lifecycle-Teilmodule | Unterstützte Provisionierung und geführter Gesamtweg, notwendige Rechte und Vertrauensgrenzen, Fehler- und Rückwegbehandlung |
| Betriebsvorbereitung | Persistenz-, Wartungs-, Upgrade-, Abbruch-, Rollback- und Restoreverträge | Erforderliche isolierte Integrationsprüfungen vor Release und vollständige Anleitungen; keine Quelllücke für V übriglassen |
| HACS und Dokumentation | Reproduzierbarer privater Paketkandidat, Handbuch und echte CAD-Dokumentationsbilder | Passender veröffentlichter HACS-Download, Build-/Versionszuordnung und aktuelle Bedien-/Installationsdokumentation |
| Öffentliche Lieferung | Quellrepository und versionierte Wiki-Dateien | Öffentlicher Slicer, echtes Wiki, vorhandene Releaseassets und Runtime-Verteilung mit tatsächlichem Download-Readback |

**R ist erst fertig, wenn außer der ausdrücklich letzten frischen
Linux-Systemverifikation keine beauftragte Releasepflicht offen bleibt.**
Die aktuelle Engine-/Host-/Veröffentlichungslücke verhindert R weiterhin.

## V: erst danach den veröffentlichten Release auf sauberem Linux prüfen

| Systemphase | Tatsächlich am Ziel zu prüfen |
| --- | --- |
| Sauberer Host und Installation | Richtige Plattform, kein nativer/fremder Slicer, unveränderte veröffentlichte Pakete, konkrete Image-ID |
| Rechte und Isolation | Tatsächliche UID, Mounts, Schreibrechte, Read-only-Root, CapDrop und NoNewPrivileges |
| Verbindung | Erforderliche Hostkommunikation und Gegenstellen; korrekte und falsche TLS-/Authkonfigurationen sowie Offline-/Timeoutfälle |
| HA/HACS | Geladene Assets, Einrichtung, Optionen, Reload/Unload, Upgrade und erhaltene Nutzerdaten |
| Neustart/Persistenz | Container- und Hostneustart mit erhaltenen Daten- und Profildigests |
| Upgrade/Rollback | Zwei reale gepinnte Stände, Teilfehler, Wartung, Rückweg und getrennte Wiederfreigabe |
| Backup/Restore | Vollständige Sicherung in ein neues Ziel, überprüfte Datei-/Datenidentitäten |

Das [Linux-Runbook](../LINUX_TEST_SERVER_RUNBOOK.md) und seine unveränderten
technischen Stop-Kriterien gelten weiter. Die Vorlage beginnt mit `not_run`;
fehlende Messungen werden nicht aus Quelltests ergänzt. Der letzte Testserver
bleibt MCP-frei und wird manuell mit bereinigten Ergebnissen geprüft.

## L: keine automatische Live-Migration oder Druckfreigabe

Das bestehende native Live-System bleibt unverändert. Ein produktiver Pilot,
eine Bestandsmigration oder HAOS-Umstellung ist ein gesonderter Auftrag. Ein
Slice, Upload und Druckstart sind unterschiedliche Handlungen; ein Druckstart
behält seine zweistufige Bestätigung. Ein erfolgreicher R- oder V-Nachweis startet
keine Hardwareaktion und hebt keine Schutzgrenze auf.

## Rückverfolgbare Belege statt pauschaler Freigabe

Jedes Ergebnis benötigt Datum, Software-/Plattformversion, die geprüften
Commit-/Paket-/Image-/Assetidentitäten, Voraussetzungen und tatsächliche
Beobachtungen. Screenshots belegen nur den wirklich geladenen Build. Private
Modelle, Rohlogs, Secrets und standortspezifische Zugangsdaten gehören nicht in
öffentliche Belege. Wiki-Dateien im Repository ersetzen den veröffentlichten
Wiki-Tab nicht.

Die Bestandsschutzfelder werden durch diese Abnahmematrix nicht umgeschrieben.
`release_complete=false` in einem Komponentenprüfer bedeutet, dass dieser Prüfer
keinen Produktrelease freigibt; R und V benötigen ihre eigenen belegten Abschlüsse.

## Historischer Herkunftshinweis vom 15.10.2026

Im untersuchten BambuStudio-Quellstand lagen die FFmpeg-Schalter `--enable-gpl`
und `--enable-nonfree` in einer im betrachteten CMake-Aufruf nicht verwendeten
Variablen `_extra_cmd`. Daraus folgt weder die tatsächliche Binärlizenz noch eine
Freigabe oder ein Verbot der konkreten Weitergabe. Die damals gesicherten
Quellarchiv- und Notice-Kandidaten waren noch keine vollständige Zuordnung zu
allen gepackten Komponenten. Dieser begrenzte historische Befund bleibt erhalten;
maßgeblich ist die konkrete [Engine-Provenienz](../ENGINE_PROVENANCE.md).
