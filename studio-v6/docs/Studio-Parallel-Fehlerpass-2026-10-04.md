# Ultimate Studio · Paralleler Fehlerpass vom 04.10.2026

Sechs Agents haben die 53 Roadmap-Einträge in sechs überschneidungsfreie Prüfbereiche aufgeteilt. Produktkorrekturen wurden zentral geprüft, zusammengeführt, auf PC und HA übernommen und mit Sicherung aktiviert. Die Zuordnung aller Einträge bedeutet keine vollständige Bedien-, Browser- oder Hardwareabnahme.

## Ausgelieferte Korrekturen

### Navigation und Kamera · DS-01 / DS-02

Beim Wiederverbinden der bereits aufgebauten Oberfläche fehlten entfernte Listener. Eigene Hashereignisse bauten Arbeitsbereiche nach einem Navigationsklick nochmals auf. Die Listener werden wiederhergestellt; identische Routen bleiben bestehen; tatsächlich während einer Trennung geänderte Routen werden nachgeholt. Back/Forward, Aliasrouten, Job-IDs und der Sonderfall eines geleerten Hashs sind abgedeckt.

Sichtbare Kameraanfragen können nach Wiederverbindung, Seitenrückkehr oder Fokuswechsel gezielt abgelöst werden. Das letzte gültige Bild bleibt bis zum erfolgreichen Ersatz sichtbar. Veraltete Antworten, Hintergrundzustand und Disconnect sind abgesichert.

15 neue Verhaltenstests bestanden; am Ausgangsstand schlugen zwölf fehl. Die tatsächliche iPhone-Navigation und länger laufende Bildfolge bleiben offen.

### Profilauswahl und Supportdialog · PR-06 / DS-08

Drei echte Renderpfade verloren aufgeklappte Filamentgruppen und Scrollpositionen: Umgebungsrefresh, Vollrender und Sidebar-Update. Ein enger Helper erhält beide Bäume unabhängig. Gruppen werden vor der Scrollposition wiederhergestellt, damit der Browser die Position nicht auf einen zusammengeklappten Baum begrenzt. Bewusst geschlossene Gruppen bleiben geschlossen.

Drei Fehler vorher reproduziert, sechs neue Zustandsprüfungen bestanden. Für den Supportdialog wurde kein zusätzlicher Produktfehler belegt. Vier neue Verhaltenstests prüfen bewusste Entscheidung, genau einmalige Auflösung, Escape/Abbruch/Disconnect, Modalfehler und alle 60 sicher ausgegebenen Objektnamen. Kein Slice, Export oder Druckerbefehl wurde für diese Tests ausgelöst.

### CAD · CA-01 / CA-02 / CA-04

Das freigegebene Paket korrigiert echte, perspektivisch korrekte Treffpunkte und Tiefenauswahl. Auf einem groben Dreieck liefern unterschiedliche Zeigerpositionen jetzt unterschiedliche Modellpunkte. Aktualisierte AMS-Materialfarben werden in den Pinsel übernommen. Die Objektliste gibt importierte Namen, Materialnamen und IDs sicher als Text beziehungsweise Attributwerte aus.

Fünf neue Regressionen bestanden; vier schlugen vorher fehl.

**Korrektur der bisherigen Dokumentation:** Die frühere Aussage, die Feintriangulierung werde im aktiven Malpfad verwendet, war nicht durch die aktuelle Verdrahtung gedeckt. Die Verfeinerungsfunktion ist vorhanden, wird dort aber nicht aufgerufen. CA-01 ist deshalb weiterhin unvollständig.

Die Gegenprüfung bestätigt zwei aktuelle Datenhaltungsfehler: Globales Leeren der Paint-Session kann Bemalungen anderer Platten entfernen. Das Löschen einer früheren Platte nummeriert Platten um, ohne die Schlüssel der gespeicherten Layer entsprechend zu übernehmen. CA-04 wird deshalb ausdrücklich als offener Bug mit hoher Priorität geführt.

Ein größerer isolierter Prototyp für Layer-Komposition, Radierer und aktive Verfeinerung wurde nicht übernommen. Alte Projekte können dieselbe Bemalung als Layer und bereits materialisierte Fläche enthalten; deren Herkunft lässt sich nicht pauschal verlustfrei trennen. Zusätzlich müssen ursprüngliche Dreiecksreferenzen vor jeder künftigen Verfeinerung validiert werden. Diese Prototyprisiken werden nicht als bereits produktive neue Fehler ausgegeben. Der Prototyp bleibt getrennt zur weiteren Bearbeitung erhalten.

### Slicing und Aufträge · DS-04 / DS-10 / DS-12

Ein undefinierter Bezeichner beim Objektnamen ließ Warnungen zu schwebenden Objekten abstürzen. Der reale Produktpfad ist korrigiert. Die bisherigen Warnungstests führten eine kopierte Funktion aus; sie prüfen jetzt die tatsächlichen Produktfunktionen.

Auftragsliste und Einzelstatus nutzen vorhandene Analysemetadaten konsistent. Eine bereits erfolgte, unbestätigte Analyse wird verständlich von einer ausstehenden Analyse unterschieden. Bestätigtes Löschen entfernt auch den alten Analysencache. Falsche Profil-, Material- und Hashbindungen bleiben abgewiesen.

Gezielt 124 Python-Prüfungen plus neun Untertests und sieben Frontendprüfungen bestanden. Am Ausgangsstand wurden sieben Backendfehler einschließlich Unterfällen und zwei Frontendfehler reproduziert. Diese gezielten Zahlen überschneiden sich mit dem Gesamtgate und werden nicht hinzuaddiert.

Jobabbruch ist weiterhin eine fehlende Fähigkeit: Der aktuelle Router meldet keine Unterstützung, und der native Worker hat keinen Cancel-Endpunkt. DS-10 ist jetzt als bestätigter offener Punkt geführt. Kein ungesicherter Prozessabbruch wurde ergänzt. Keine neue Vollanalyse, kein Slice oder Job-Release wurde ausgeführt.

### Galerie und Profilverträge · GA-01 / GA-02 / GA-08

Verspätete Listen-/Suchantworten dürfen neuere Ansichten nicht mehr überschreiben. Suchantworten verunreinigen den Startcache nicht. Ein Mehrdateiupload behält den beim Start gewählten Zielordner. Erfolgreiche und teilweise erfolgreiche Mutationen aktualisieren die Liste nach Freigabe der Schreibsperre.

Dateioperationen weisen vor der Mutation Galerie-Hauptordner, Selbstkopien, untergeordnete Ziele und Überschreibziele ab, die die Quelle enthalten. Unabhängige ausdrücklich gewählte Überschreibziele und bestehende No-op-Semantik bleiben erhalten.

Elf neue Frontend- und 29 neue Backendprüfungen bestanden; zuvor waren neun beziehungsweise 20 rot. Dateiprüfungen nutzten ausschließlich temporäre Testordner. Die bestehenden Galerie- und Profilverträge wurden mitgeprüft; weitere Druckermodelle oder physische Materialien werden dadurch nicht pauschal freigegeben.

### System · SY-07 und Namensvorbereitung

Fehlgeschlagene API-Abrufe und lokale Auswahlaktionen geben alte Telemetrie nicht mehr als frisch aus. Veraltete Polls überschreiben keine neuere Jobauswahl. Auditabfragen überlappen nicht; Antworten einer alten Verbindung werden verworfen. Unveränderte Zeilen und Bedienelemente bleiben bestehen. Offene Details, Fokus, veränderte Zuordnungstexte und Fehlermeldungen werden berücksichtigt.

Elf neue Laufzeitregressionen bestanden; zehn waren vorher rot. Tests verwenden begrenzte API-/Element-Doubles und behaupten keine Browserdarstellung.

Der getrennte Konfigurationshelfer erkennt indirekte Jinja-Triggerverweise und rekursive YAML-Aliase. Nicht sicher umbenennbare Trigger führen zu einem kontrollierten Prüfhalt. 15 aktuelle Helperprüfungen bestanden, darunter vier neue Methoden.

## Gemeinsamer Nachweis

| Prüfung | Ergebnis |
| --- | --- |
| Frischer kanonischer Ausgangsstand | 737 Textdateien ohne Drift aufgenommen; zwei Prüfsummendateien zusätzlich gelesen |
| Ausgangsbuild | JavaScript bytegleich zur zuvor laufenden Installation |
| Zusammenführung | 27 Dateien: 14 Produktdateien und 13 Testdateien; davon 13 neue Dateien |
| Source-Policy und TypeScript | Bestanden |
| Frontend | 231 bestanden, keine ausgelassen |
| Backend / Worker | 1.334 Tests und neun Untertests bestanden |
| Beide Produktionsbuilds, Syntax, Imports, Compile | Bestanden |
| Kanonisches PC-Gesamtgate | Bestanden |
| PC-/isolierter Build | JavaScript und CSS bytegleich |
| Quellübernahme | Vorbedingungen, Same-Day-Backups und Rücklesen auf PC und HA |
| HA-Konfiguration / Neustart | Beide erfolgreich |
| Laufende Integration / Health | loaded / HTTP 200 |
| Frontend-Ressource | API und dauerhafter Speicher stimmen überein |
| HTTPS-Auslieferung | HTTP 200, JavaScript und erwarteter SHA-256 |

Aktives JavaScript: `29fc7bc256736fc7652555668b3a36ba3e9f9a7ac0bd22b7a96a7e346fb54eec`.

Die 55 zusätzlichen Frontendtests und 37 zusätzlichen Backendtests sind im Gesamtgate enthalten. Einzelne Tests besitzen mehrere Unterfälle. Rot/Grün-Zahlen pro Agent sind gezielte Reproduktionen und keine zusätzliche Anzahl erledigter Dashboard-Einträge.

Sicherung und Rohbelege: HA `backups/20261004-parallel-defect-pass`, PC `.codex-backups/20261004-parallel-defect-pass`. Der native Slicer-Worker wurde nicht verändert oder neu bereitgestellt. Es gab keinen neuen Slice, keine Freigabe eines Jobs, keinen Druckerupload und keinen Druckstart.

## Namensumstellung weiterhin vorbereitet

Alle freigegebenen Produktkorrekturen sind zusätzlich im getrennten Namenskandidaten enthalten. Dieser besteht 245 Frontendtests, 1.334 Backendtests und neun Untertests sowie dieselben Typ-, Build-, Policy- und Compile-Gates. Browser-Speichertests des vorherigen Kandidaten bleiben enthalten.

Kandidaten-JavaScript: `3e869c5b9625e634d89ee1af55d45501276d3a9bfe17b7d8b1dd55583cb50020`.

Elf HA-Speicherdateien bewahren vier Nutzdatenbereiche. Zwei Konfigurationen aus 27 tatsächlich erreichbaren Dateien sind mit dem Kandidatenhash vorbereitet. Die früher geprüften Worker-/Connectorproben bleiben getrennte Nachweise. Produktive Namensumstellung, kanonische PC-Übernahme dieses Namensraums, koordinierte Worker-/Connectoraktivierung und echte Browserdatenabnahme sind nicht erledigt. Die über die aktuelle Plattform-API nicht editierbare Site-Beschreibung bleibt ein Restpunkt.

## Grenzen und nächste Arbeit

Alle 53 Einträge sind einem Prüfbereich zugeordnet; im Dashboard führt jeder Eintrag seinen eigenen Status. Die echten iPhone-/Touch-/Browserprüfungen, CAD-Datenhaltung und aktive Feintriangulierung, kooperativer Jobabbruch, vollständiger Backup-/Restore-Nachweis und die übrigen beschriebenen Hardware-/Sliceabnahmen bleiben offen. Das Studio bleibt Beta.

Das Dashboard ist weiterhin nur für den Eigentümer freigegeben. Es gab keinen öffentlichen Repository-Schreibvorgang und keine öffentliche Websitefreigabe.
