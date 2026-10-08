# Namensmigration · Prüfpass vom 04.10.2026

Stand: 06:10 CEST. Arbeitsgrundlage ist SY-11 im privaten Prüfdashboard. Die laufende Installation ist in diesem Prüfpass nicht auf den neuen Namensraum umgestellt worden. Alle folgenden Migrationsnachweise betreffen isolierte Kandidaten und ausdrücklich genannte Leseprüfungen.

## Ergebnis

Die noch fehlenden Vorbereitungen für Worker-Verlauf, Connectorverträge und verschachtelte Home-Assistant-Konfigurationen sind implementiert und geprüft. Zusätzlich ist die Übernahme gespeicherter Browser-Auftragsverweise ergänzt. Der aktualisierte Produktkandidat besteht 190 Frontendtests, 1.297 Backendtests plus drei Untertests, Typprüfung, Source-Policy, beide Builds und Compile-Prüfung. Weitere 45 Migrationsprüfungen bestehen ohne Fehler oder ausgelassene Fälle.

Der Gesamtbefund SY-11 bleibt teilweise abgeschlossen. Der aktuelle PC-Produktquellbaum muss vor Anwendung erneut vollständig abgeglichen werden. Produktive Aktivierung, Connector-Neustart, echte Browser-Speicherübernahme und iPhone-Abnahmen stehen aus. Beta bleibt bestehen.

## Home Assistant: tatsächliche Einbindungen

Die bisherige Aufnahme berücksichtigte fest benannte Konfigurationsordner. Der laufende Stand bindet jedoch auch `jarvis_intents` ein. Die neue Aufnahme folgt den tatsächlichen YAML-Tags rekursiv. Sie parst Tags, ohne Geheimnisse aufzulösen oder fremden YAML-Code auszuführen. Direkt eingebundene .yml-Dateien werden berücksichtigt; Ordner-Einbindungen folgen dem installierten HA-Loader mit .yaml-Dateien und dem Ausschluss versteckter Dateien sowie secrets.yaml.

Geprüft werden fehlende Dateien, Verweisschleifen, Pfadflucht, symbolische Verknüpfungen, ungültiges YAML und Änderungen während der Aufnahme. Kommentare, Formatierung und unbeteiligte Werte bleiben erhalten. Die Kandidaten werden vollständig geplant und zurückgelesen; die laufenden Konfigurationen werden nicht überschrieben.

Im aktuellen Bestand sind 27 tatsächlich erreichbare Konfigurationsdateien gelesen und zwei Dateien zur Anpassung vorbereitet. Dazu kommen elf frisch aufgenommene HA-Speicherdateien. Vier Nutzdatenbereiche – Audit, Profile, Projekte und Jobs – bleiben inhaltlich erhalten.

Drei Druck-Automationen behalten IDs, Trigger und Aktionen unverändert; ihre Bezeichnungen werden angepasst. Eine weitere Automation für den Modulstatus erhält drei umbenannte Entitätsverweise, den angepassten Anzeigetext und eine versionsfreie lokale Auslösekennung. Diese Kennung ist innerhalb der konkreten Automation nicht referenziert. Alle drei neuen Entitäten sind im vorbereiteten Register vorhanden; die Automation-ID bleibt erhalten. Gleichnamige Auslöser anderer Anwendungen bleiben unverändert. Referenzierte oder kollidierende Auslösekennungen werden nicht stillschweigend geändert.

22 Speicher-/Konfigurationsprüfungen bestanden, darunter elf neue Prüfungen für Einbindungen und Auslösekennungen.

## Worker: vollständige Probekopie und Verknüpfungen

4.980 Dateien mit 9.017.698.873 Byte wurden außerhalb des laufenden Workers aufgenommen und kopiert. Die Probe umfasst gespeicherte Zustände, Ausgaben, Uploads, Laufzeitdateien und den letzten Auftrag. Es gibt 353 Zustandsdateien: 320 abgeschlossen und 33 fehlgeschlagen; keine wartenden oder laufenden Zustandsdateien. Mit einem zusätzlichen Auftrag aus dem Ergebnisbestand sind 354 Auftragskennungen vorhanden.

324 Kennungen werden angepasst. Darunter sind 13 ältere Diagnosekennungen ohne Trennzeichen nach dem früheren Versionsprefix. 4.708 Dateipfade und 1.021 JSON-Metadatendateien werden konsistent angepasst. Die übrigen 3.959 Dateiinhalte sind bytegleich erhalten. Geometrie, G-Code, 3MF-Dateien, Logs und geschützte Material-/Prozesssnapshots werden nicht inhaltlich umgeschrieben. Benutzerbenennungen und historische Nachweise bleiben erhalten.

Dateikollisionen, widersprüchliche Kennungen, mehrere Zustände pro Auftrag, aktive Aufträge, ungültige Metadaten, symbolische Links, beschädigte Kopien und Änderungen während der Aufnahme führen zum Abbruch. Dateizeitstempel bleiben erhalten. Quell- und Zielprüfsummen sind kontrolliert; ein fehlgeschlagener Kopierversuch hinterlässt keinen halbfertigen Kandidaten. Zwei frühe abgeschlossene Aufträge ohne redundantes job_id-Feld behalten ihre gültige historische Form. Der tatsächliche Worker verwendet hier die Dateikennung; es werden keine Daten erfunden.

Mit den tatsächlichen Lesefunktionen des Worker-Codes wurden Quellbestand und Probekopie verglichen:

| Prüfung | Ergebnis |
| --- | --- |
| Auftragsdetails | 354 konsistent |
| Aktuelle Verlaufsliste | 100 Einträge, gleiche Reihenfolge |
| Ausgewählte Downloads | 327 identisch gebundene Artefakte |
| Datei- und Eingabeverweise | 1.871 geprüft, keine neuen fehlenden Verweise |
| Verbleibende Versionskennung in vorbereiteten Job-IDs | 0 |
| Regressionen der Worker-Migration | 15 bestanden |

Die Lesefunktionen wurden isoliert aus dem tatsächlichen Quellcode geladen. Kein HTTP-Server wurde gestartet und kein Slice, Job-Release, Druckerupload oder Druckstart ausgelöst. Dies ist eine Funktionsprüfung der vorbereiteten Daten, keine Abnahme eines bereits umgestellten Live-Workers. Abgeleitete API-Diagnosecaches müssen bei späterer Aktivierung neu erzeugt werden.

## PC-Connector: Verträge und Namen

13 beobachtete Connector-Quelldateien wurden aufgenommen; zehn davon sind im Kandidaten angepasst oder umbenannt. Der aktuelle PC-Stand wurde erneut vollständig textuell gegen diese Aufnahme verglichen, mit vereinheitlichten Zeilenenden, BOM und abschließenden Zeilenumbrüchen. Es gibt keine inhaltliche Abweichung.

Die sechs tatsächlich registrierten Produktwerkzeuge haben im Kandidaten versionsfreie Namen. Argumente und Standardwerte bleiben erhalten. Acht Tests sichern Registrierung, geschützte Quellpfade, die Beschränkung auf drei Frontend-Artefakte, symbolische Pfadflucht, fehlgeschlagene Qualitätsgates, notwendige Freigaben, zeitlich begrenzte Einmal-Downloads und die Ablehnung veränderter Downloadinhalte ab. Sämtliche 13 Module lassen sich kompilieren. Die bestehenden Startverknüpfungen sind im Kandidaten konsistent umbenannt; es wurden keine Berechtigungsgrenzen erweitert.

Die aktiven Connector-Dateien wurden nicht ersetzt und der PC-Dienst wurde nicht neu gestartet. Der Kandidat setzt die koordinierte Produktumbenennung voraus.

## Gespeicherte Browserprojekte

Bei der Übernahme eines alten Studio-Workspace werden jetzt ausschließlich die gespeicherten Auftragskennungen der Druckplatten auf den passenden neuen Worker-Namen abgebildet. Geometrie, Profilwahl, Bemalung, Benutzernamen und die unveränderte Rückwegsicherung bleiben erhalten. Unbekannte Formate werden nicht geraten; vorhandene aktuelle Daten behalten Vorrang.

Vier neue Frontendregressionen prüfen die gezielte Anpassung, frühe Diagnosekennungen, Wiederholbarkeit, unveränderte Archive und ungültige Werte. Zusätzlich wurde der tatsächlich kompilierte Browser-Helfer mit allen 354 Kennungen des Worker-Kandidaten verglichen: Jede Zuordnung stimmt überein, einschließlich der 324 Änderungen.

Die echte IndexedDB-Transaktion in einem Benutzerbrowser und die Wiederaufnahme eines realen Projekts sind weiterhin nicht abgenommen. Der Modell-/Codevergleich ersetzt diese Prüfung nicht.

## Kandidat, Sicherungen und Abschlussgrenzen

Der vorbereitete Produktstand basiert weiterhin auf 737 kanonischen PC-Textquellen mit 375 umbenannten oder angepassten Bestandsdateien; die zwei zusätzlichen Browser-Migrationsdateien sind aktualisiert. Version 1.0.0-beta.4 bleibt ein unveröffentlichter Kandidat.

Kandidaten-JavaScript SHA-256: `eb03e6232db722263d1b23b85caff9e06c395f85eb78e332e229a91b5375948c`.

Prüfnachweise, Vorbereitungscode, ursprüngliche Zwischenstände, Worker-Probekopie und Connector-Kandidat liegen unter `backups/20261004-studio-migration` auf HA. Die reproduzierbaren Vorbereitungsskripte, Berichte und Connector-Kandidaten werden zusätzlich in `.codex-backups/20261004-studio-migration` im kanonischen PC-Projekt gesichert. Die große Worker-Datenkopie bleibt auf HA.

Vor Aktivierung bleiben erforderlich: vollständiger erneuter PC-Abgleich, koordinierte Übernahme der Quellen und Dienste mit Rückweg, frischer Vergleich der laufenden Speicher und Worker-Daten, Cache-Neuerzeugung sowie tatsächliche Browser-/iPhone-Abnahmen. Die alte Site-Beschreibung ist mit der verfügbaren Sites-Metadatenschnittstelle weiterhin nicht editierbar.

Das Dashboard bleibt ausschließlich für seinen Eigentümer zugänglich. Keine öffentliche Veröffentlichung und kein öffentlicher Repository-Schreibvorgang. 53 Prüfpunkte, 22 dokumentierte Abschlüsse und 31 ausstehende Einträge bleiben korrekt erhalten. Die Teilnachweise der Namensmigration schließen den Gesamtbefund nicht automatisch.
