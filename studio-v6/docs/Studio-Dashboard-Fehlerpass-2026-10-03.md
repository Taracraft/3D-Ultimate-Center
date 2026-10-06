# Dashboard-Fehlerpass · 03.10.2026 · 23:34 CEST

Arbeitsgrundlage sind die 53 Einträge des privaten Prüfdashboards. Reihenfolge: P0-Sicherheitsbefund, bestätigter Profilfehler, historischer MakerWorld-Befund. Alle fünf Produktbereiche und die vollständige Tiefenanalyse bleiben im Register enthalten.

## SY-01 · Audit-Ausgabe

Der aktuelle Quellstand filtert bereits Kameraattribute und verwendet Wortgrenzen für die AMS-Kategorisierung. Die erneute Prüfung bestätigt jedoch fünf verbleibende Fehlerfälle: Geheimnisse in zitierten JSON-/Python-Texten, Basic-Anmeldedaten und URL-Benutzerinformationen sowie ungefilterte Metadaten und alte Audit-Ausgaben.

Korrektur in audit_safety.py und audit_log.py: vollständige zitierte Werte, Basic-/Bearer-Werte und URL-Anmeldedaten werden maskiert. Neue Einträge schützen auch ihre Metadaten. Historische Einträge und die Zusammenfassung werden bei der Ausgabe geschützt. Die Reihenfolge und die Anzahl der Einträge bleiben erhalten; gespeicherte Altbestände werden durch das Lesen nicht umgeschrieben. Die bestehende Vorschau und ausdrückliche Bestandsbereinigung funktionieren weiterhin.

Sieben neue verhaltensbezogene Regressionen: fünf scheitern am alten Code, alle sieben bestehen mit der Korrektur. Sechs Fälle der unveränderten tatsächlichen Kategorisierungsfunktion bestätigen AMS/Wortgrenzen. Der vollständige Prüfstand umfasst außerdem die bestehenden Audit-Vertragsprüfungen.

Nach Aktivierung liefert die echte Audit-Schnittstelle HTTP 200. 5.000 zurückgegebene Einträge und die Zusammenfassung benötigen keine weitere Maskierung durch die geprüften Regeln. Keine echten Geheimnisse wurden in Prüfausgaben oder Dashboard-Nachweise übernommen. Kein Audit-Eintrag wurde gelöscht.

## PR-08 · Profilkopf

Die Korrektur war im kanonischen PC-/HA-Quellstand bereits vorhanden; der Dashboard-Eintrag war veraltet. Die Anzeige verwendet Werte des ausgewählten Prozesses, mit den passenden Schlüsseln für lokale und Cloud-Profile. Explizite Benutzerwerte bleiben erhalten. Bei fehlenden oder geerbten Werten wird keine generische Geschwindigkeit erfunden.

Acht bestehende Regressionen für 70/150 mm/s, Profilwechsel, Düsendurchmesser, Cloud-Werte, Eingaben und fehlende Werte sind im aktuellen Gesamtgate bestanden. Der frisch gebaute unveränderte Ausgangsstand entspricht bytegenau dem zuvor aktiven JavaScript: 57acf6c99c7010688f75b5f15ae83e0ea6cf053ee93d506d828b928eed6ba437.

Der Anzeige-Code ist damit im ausgelieferten Produkt nachgewiesen. Eine tatsächliche Sichtabnahme im iPhone-Browser ist weiterhin offen und wird nicht aus dem Quell-/Buildnachweis abgeleitet.

## GA-06 · MakerWorld-Lizenz und Kennzeichnung

Das feste Verifizierungs-Häkchen ohne Quelldatum wurde entfernt. Der vorhandene API-Vertrag enthält keinen belastbaren Verifizierungsstatus; deshalb wird keiner behauptet.

Die Lizenz steht nun direkt neben den Aktionen zur Übernahme und zum Download. Fehlende Angaben werden ausdrücklich als fehlend angezeigt. Vorhandener Lizenztext bleibt unverändert inhaltlich erhalten und wird HTML-sicher ausgegeben; es werden keine Nutzungsrechte erfunden. Vier neue Frontendregressionen sichern Text, fehlende Angaben, HTML-Escaping und die Verdrahtung im Dialog.

Die Korrektur ist ausgeliefert. Die vollständige interaktive MakerWorld-Abnahme bleibt unter GA-05/GA-08 separat offen.

## Gates und laufende Installation

| Prüfung | Ergebnis |
| --- | --- |
| Frischer kanonischer PC-Textstand | 734 Dateien vollständig und während der Aufnahme unverändert; zwei Prüfsummendateien zusätzlich gelesen |
| Source-Policy, TypeScript, beide Builds | Bestanden |
| Frontend | 176 bestanden, keine ausgelassen |
| Backend/Worker | 1.297 Tests plus drei Untertests bestanden |
| Syntax, Imports und Compile-Prüfung | Bestanden |
| Kanonisches PC-Gesamtgate | Statusdateien erfolgreich; tatsächliche Artefakte abgeglichen |
| PC-/isolierter Build | JavaScript und CSS bytegleich |
| Home-Assistant-Konfigurationsprüfung und Neustart | Erfolgreich; Integration loaded |
| Ressourcenverknüpfung | API und dauerhafter Speicher auf neuen Hash aktualisiert |
| HTTPS-Auslieferung | HTTP 200, erwarteter SHA-256 |

Aktives JavaScript: 486590a08b9aecbb54ef73168900c78fe2a0cae4f693a2f9d2bbf47fb4f9a1a3.

Sieben Quelländerungen wurden mit Vorabgleich, Backups und Rücklesen auf PC und HA übernommen. Acht Live-/Quellartefaktziele wurden mit Sicherung atomar je Datei aktualisiert. Andere Dashboard-Ressourcen blieben unverändert. Ein Connector-Zeitlimit wurde anhand der tatsächlich erfolgreichen PC-Statusdateien geklärt und nicht als Testresultat gewertet.

Backup und Nachweise: backups/20261003-dashboard-defect-pass auf HA; .codex-backups/20261003-dashboard-defect-pass im PC-Projekt. Neue Tests enthalten ausschließlich künstliche Prüfwerte.

## Namensmigration bleibt in Arbeit

Die sieben Korrekturen sind zusätzlich in den vorbereiteten Namensmigrationskandidaten übernommen. Das aktualisierte Manifest umfasst 737 kanonische Textquellen und 375 angepasste/umbenannte Dateien. Kandidat: 186 Frontendtests, 1.297 Backendtests plus drei Untertests, beide Builds, Source-Policy, Typ- und Compile-Prüfung bestanden. Elf HA-Speicher- und zwei Konfigurationssnapshots sind mit dem neuen Kandidatenhash erneut vorbereitet; vier Nutzdatenbereiche bleiben erhalten. Die elf bereits bestandenen Speicher-/Konfigurationsregressionen bleiben unverändert.

Kandidaten-JavaScript: 163f9b1367046654d6b8912ce0d99c1d96815aee8bf6830f0852cd7830be93a9.

Die vollständige Produktumbenennung ist noch nicht aktiviert. Worker-Verlauf und Artefaktverweise, Connectorverträge, sämtliche Konfigurationseinbindungen, Anwendung der Migration am PC und echte Browser-Speicherabnahme bleiben offen. Der aktuelle Produktbetrieb verwendet weiterhin den bisherigen Namensraum. Die nicht editierbare Site-Beschreibung bleibt ein eigener Plattformrestpunkt.

## Erweitertes privates Dashboard

Arbeitsboard mit vier Schritten: Als Nächstes, In Prüfung, Voraussetzung offen und Abgeschlossen. Alle 53 Einträge haben Einordnung, nächsten Schritt und eine nachvollziehbare Reihenfolge; tatsächlich verknüpfte Voraussetzungen öffnen den zugehörigen Befund.

Register mit zusätzlichem Schrittfilter und Sortierung. Einzelne Befunde haben private Direktlinks. Persönliche Prüfschritte und Notizen bleiben auf dem jeweiligen Gerät und verändern niemals den dokumentierten Status. Der JSON-Export folgt exakt der gewählten Ansicht und enthält die vollständigen Nachweise.

Neun automatisierte Prüfungen der tatsächlich verwendeten Filter-, URL-, Export-, Abhängigkeits- und Notizlogik sind bestanden. Datenintegrität, Quellen, vollständige Zuordnung zum Arbeitsboard und zyklusfreie Voraussetzungen sind geprüft. Eine echte Browser-/Touch-Bedienabnahme ist weiterhin nicht verfügbar; sie wird nicht als bestanden ausgewiesen.

Drei Befunde im dokumentierten Softwareumfang abgeschlossen: SY-01, PR-08 und GA-06. Damit 22 von 53 Prüfpunkten abgeschlossen, 31 ausstehend; fünf Bugbefunde bleiben teilweise abgenommen. Beta bleibt bestehen. Keine öffentliche Freigabe, kein öffentlicher Repository-Schreibvorgang. Kein Slice, Job-Release, Druckerupload oder Druckstart.
