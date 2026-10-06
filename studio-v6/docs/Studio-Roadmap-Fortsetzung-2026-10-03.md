# Studio-Roadmap · Verifizierter Stand vom 03.10.2026

Privater Prüfstand: https://taracraft-pruefstand.fassinator1982dn.chatgpt.site

53 Prüfpunkte in Druckstudio, System, Galerie, Profilverwaltung und CAD-Studio; 13 vollständige Quellberichte einschließlich Tiefenanalyse und aktuellem Arbeitsnachweis. Zugriff ausschließlich für den Site-Eigentümer. Die fünf automatisierten Prüfungen für Filter, Suche, Merkliste, URL-Zustand und Export sind bestanden. Eine tatsächliche Browser-Bedienabnahme ist wegen der blockierten Browsersitzung nicht verfügbar und wird nicht als bestanden gewertet.

## Tatsächlich ausgelieferte Kamerakorrektur

Bildlistener werden vor dem Laden gesetzt. Abbruch und Zeitlimit umfassen die Bildphase; Anfragen werden bei Trennung oder Kamerawechsel beendet. Veraltete Anfragen können weder neue Bilder überschreiben noch deren Ladezustand zurücksetzen. Nicht übernommene Objekt-URLs werden freigegeben. Fünf zusätzliche Regressionen sind im kanonischen Gesamtgate enthalten.

Der ausgelieferte Kamerabuild besteht 172 Frontendtests, 1290 Python-Tests plus drei Untertests, Typprüfung, Source-Policy, beide Builds und Compile-Prüfung. PC-Build, HA-Quellartefakte und Live-Dateien sind abgeglichen.

Live-JavaScript SHA-256: 57acf6c99c7010688f75b5f15ae83e0ea6cf053ee93d506d828b928eed6ba437.

Zusätzlich wurde die veraltete Home-Assistant-Ressourcenverknüpfung über die laufende HA-WebSocket-Schnittstelle auf diesen Dateihash aktualisiert. API-Rücklesen, dauerhaft gespeicherte Ressource und tatsächlich per HTTPS ausgelieferte JavaScript-Bytes sind geprüft. Andere Dashboard-Ressourcen bleiben erhalten. Backup: backups/20261003-camera-resource-cache-fix. Der bisherige Produktnamensraum ist dabei weiterhin aktiv. Die fortlaufende Aktualisierung in der iPhone-App ist noch nicht visuell abgenommen.

## Aktueller Kandidat für die Namensmigration

Der isolierte Kandidat basiert jetzt auf 734 frisch gelesenen kanonischen PC-Textdateien einschließlich Dienstdefinitionen. Keine Lesefehler und keine Änderungen während der Aufnahme. Textzeilenenden sind für den Quellvergleich vereinheitlicht; keine Bytegleichheit ungelesener Binärdateien behauptet. Der erforderliche große STL-Testfall stammt aus dem vorhandenen Leistungstestalgorithmus.

373 bestehende Dateien sind umbenannt oder angepasst. Zwei neue Dateien enthalten die Browser-Speicherübernahme und zehn zusätzliche Regressionen. Komponenten-Domain, API-Prefix, Imports, Ereignisse, Klassennamen, Frontendpfade und Speicherbezeichnungen sind im Kandidaten versionsfrei. Release-Metadaten: 1.0.0-beta.4; keine veröffentlichte Releaseversion. Bestehende PC-Weiterentwicklungen werden erhalten. 34 zuvor festgelegte Abhängigkeitshashes sind gegen den PC-Snapshot geprüft und nur für die nachgewiesenen Namensänderungen erneuert.

Kandidat: backups/20261003-studio-namespace-candidate/canonical/source.
Manifest: canonical/final-candidate-manifest.json.
Kandidat-JavaScript SHA-256: 6b229d9dd0dd293489d1a1fe09bb90044b206fa4bedb517a668537da796edcac.

| Prüfung | Ergebnis |
| --- | --- |
| Source-Policy und TypeScript | Bestanden |
| Frontendregressionen | 182 bestanden, keine ausgelassen |
| Produktionsbuild und HA-Core-Build | Beide bestanden |
| Python-Syntax, Imports und Backendregressionen | 1290 Tests plus drei Untertests bestanden |
| Speicher- und Konfigurationsmigration | Elf zusätzliche Prüfungen bestanden |
| Bestehende Druck-Automationen | Drei IDs, Trigger und Aktionen unverändert geprüft |

## Daten und Verknüpfungen

Elf HA-Speicherdateien und zwei aktive Konfigurationsdateien sind außerhalb der laufenden Installation vorbereitet. Konfigurations-, Geräte-, Entitäts- und Automationsidentitäten bleiben erhalten. Vier Nutzdatenbereiche einschließlich Audit, Profile, Projekte und Jobs behalten ihren Dateninhalt. Instanzname, Dashboardtitel und die drei Druck-Automationen sind in der Vorbereitung ebenfalls umbenannt. Die neue Frontend-Ressource verweist auf den verifizierten Kandidatenhash. Kollisionen, ungültige Daten, fehlende Hashes, unveränderte Nutzdaten und Rücklesen sind geprüft.

Die Browserübernahme erkennt frühere numerische Studio-Speicherstände. Einstellungen werden mit Sicherung und Rücklesen übertragen; vorhandene aktuelle Werte bleiben erhalten. Fehlgeschlagene Übernahmen halten die bisherigen Werte verfügbar. Workspace-Geometrie und Jobreferenzen werden unverändert übernommen; der jüngste gültige Speicherstand wird gewählt. Die bisherige IndexedDB bleibt bis zur tatsächlichen Browserabnahme als Rückweg erhalten. Modell- und Rollbackregressionen sind bestanden; die tatsächliche IndexedDB-Transaktion im Benutzerbrowser wurde nicht ausgeführt.

Der native Worker wurde erneut vollständig inventarisiert: 353 gespeicherte Jobzustände, davon 320 abgeschlossen und 33 fehlgeschlagen; keine aktiven oder wartenden Zustandsdateien. Die API zeigt 100 aktuelle Verlaufsjobs, davon 87 abgeschlossen und 13 fehlgeschlagen; 98 Kennungen tragen den früheren Produktprefix. 2471 Dateien liegen im Laufzeitbestand. Jobverlauf und binäre Artefakte sind unverändert.

## Verbleibende Roadmap

Die Produktmigration ist noch nicht aktiviert. Offen sind die sichere Umstellung der Worker-Kennungen und ihrer Artefaktverknüpfungen, die Connector-Namen und Verträge, die Anwendung des aktuellen Kandidaten am PC, eine atomare HA-Aktivierung mit Rückweg sowie echte Browser- und iPhone-Abnahmen. Vor Aktivierung müssen Quell- und Datensnapshots erneut gegen den laufenden Stand geprüft werden.

Die Site-Adresse, der Titel, die Oberfläche und Exporte sind versionsfrei. Die ältere Site-Beschreibung ist mit der bereitgestellten Metadatenschnittstelle nicht editierbar; dieser Plattformpunkt bleibt offen. Es gab keine öffentliche Freigabe und keinen öffentlichen Repository-Write. Kein Slice, Job-Release, Druckerupload oder Druckstart wurde ausgelöst. Beta bleibt bestehen.

Die sechs aktuellen Vorbereitungsskripte und Regressionen sind am PC und auf HA mit Rücklesen gesichert. Aktuelle PC-Codeablage: .codex-backups/20261003-studio-namespace-candidate/migration-code-revision3. HA-Codeablage: backups/20261003-studio-namespace-candidate/migration-code-revision3.
