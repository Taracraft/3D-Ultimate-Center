# Ultimate Studio · Materialvorschau · Prüfpass 05.10.2026

## Ergebnis

PREVIEW-COLORS-20261004 ist teilweise umgesetzt. Die Hauptvorschau in `studio-mega-workspace-v2.ts` startet im kanonischen PC-Quellstand mit echten auftragsgebundenen Filamentfarben. Der erneute Abgleich eines geslicten Auftrags setzt die Ansicht nicht mehr auf Drucktyp zurück. Neue Projekte starten im Materialmodus; eine ausdrücklich gewählte Drucktyp-Diagnose bleibt beim erneuten Laden innerhalb der Sitzung ebenfalls erhalten.

Die Änderung ist nicht im laufenden Home Assistant aktiviert. Die HA-Quellkopie wurde nicht synchronisiert, und ein öffentlicher GitHub-Abgleich wurde nicht vorgenommen. Der isolierte Prüfstand auf der HA-VM ist keine produktive Bereitstellung.

## Implementierter Umfang

- Hauptvorschau: Initialisierung und Projektneustart mit Materialmodus; der automatische Drucktyp-Reset bei der Jobübernahme entfällt. Die Schaltfläche heißt nun „Filamentfarben“; ihre bestehende Kennung bleibt erhalten.
- Die Hauptvorschau verwendet die Palette aus dem jeweiligen Auftrag. Der frühere Rückgriff auf die inzwischen aktuelle AMS-Bestückung ist entfernt.
- Direkte Kanalzuordnung statt Modulo-Umlauf: Ein unbekannter Kanal erhält niemals die Farbe eines anderen vorhandenen Kanals.
- Fehlende oder fehlerhafte Paletteinträge bleiben an ihrer ursprünglichen Position erhalten. Nachfolgende Filamentkanäle verschieben sich nicht.
- Unbekannte Farben werden im Hauptviewer ausdrücklich mit Text und neutraler grauer Kennzeichnung dargestellt. Grau ist kein behauptetes Filament.
- Historische Layer behalten im Materialmodus ihre Material-RGB-Werte. Bestehende separate schmale Glanz-/Hervorhebungsgeometrie und normale 3D-Beleuchtung bleiben erhalten. Im Diagnosemodus bleiben die unterschiedlichen Drucktypfarben sowie ihre Abblendung erhalten.
- G-Code-Parser: Ungültige Paletteinträge werden nicht mehr durch ein erfundenes Grün ersetzt. Eine physische Extruder-Anzeigefarbe wird nicht als belegte Filamentpalette ausgegeben. Die bestehende API-Struktur bleibt unverändert.
- Die bisherige Source-Policy, die Drucktyp als Standard verlangt hatte, und die historische Testannahme zur pauschalen Abblendung wurden an die neue Benutzeranforderung angepasst. Schutzprüfungen wurden nicht abgeschaltet.

G-Code-Erzeugung, Druckreihenfolge, AMS-Zuordnung, native Worker, Projektgeometrie und Druckersteuerung sind nicht verändert.

## Tests und Gegenprobe

33 neue Frontendtests führen tatsächliche Produktionsfunktionen für Farbzuordnung, Ribbon-Geometrie und Auftragsübernahme mit ausdrücklich begrenzten Zustands-/Netzwerk-Doubles aus. Darunter sind Schwarz/Weiß/Rot/Gelb, ungültige Farben, lückenhafte Paletten, unbekannte Kanäle, historische Layer, bewusster Diagnosemodus, Featurefilter, Supportisolierung, unveränderte Quelldruckbahnen und das Unterlassen eines Rückgriffs auf aktuelle AMS-Farben.

Gegen den ursprünglichen Studioquelltext: 26 bestanden und sieben fehlgeschlagen. Mit dem Kandidaten: alle 33 bestanden, keine ausgelassen. Die Gegenprobe verwendet den ursprünglichen Studioquelltext, nicht ein künstlich defektes Modell. Vier anfängliche Testassertionen wurden berichtigt, weil der reale Ribbon-Renderer Glanzstreifen als separate Meshes mit eigenen Farben und beschriftetem Namenspräfix ausgibt. Die abschließenden Prüfungen unterscheiden deshalb Grundmaterial und separate Glanzgeometrie; dies ist keine entfernte Materialprüfung.

13 neue Parserprüfungen plus drei vorhandene G-Code-Toolpath-Tests bestehen unter Linux. Sie prüfen unter anderem leere Semikolonfelder, JSON-null, ungültige Nicht-Stringwerte, RGBA-/RGB-Formate, fehlende Palette, identische Kanal-/Layer-/Bewegungsdaten und denselben Vertrag für Klartext-G-Code und 3MF-Container. Kein Slicerprozess und keine Druckerverbindung wird dafür benutzt.

Die TypeScript-Prüfung des isolierten Frontendstands ist bestanden. Der erste vorhandene Frontend-Gesamtlauf hatte genau einen Widerspruch zur alten pauschalen Abblendungsanforderung; der betreffende Test wurde auf die neue Benutzeranforderung umgestellt und die neuen Verhaltenstests in den Standard-Testeinstieg aufgenommen.

## Vollständiges kanonisches PC-Gate

Abschluss: **05.10.2026, 00:35:28 CEST**.

| Prüfung | Ergebnis |
| --- | --- |
| Source-Policy und TypeScript | Bestanden |
| Frontendtests | 403 bestanden, keine Fehler, keine ausgelassen |
| Produktionsbuild und HA-Core-Build | Beide bestanden |
| Python-/Worker-Tests | 1.575 bestanden, keine Fehler |
| Python-Untertests | 15 bestanden |
| Linux-spezifische Prozessgruppentests | Neun auf Windows plattformbedingt ausgelassen |
| Python-Syntax, Imports und Komponenten-Compileprüfung | Bestanden |

Die 33 neuen Frontendtests sind in 403 enthalten; die 13 neuen Python-Prüfungen sind in 1.575 enthalten. Die nochmals lokal ausgeführten Prüfungen werden nicht doppelt hinzugezählt. Die Windows-Auslassungen sind kein neuer Linux-Testnachweis.

Der Connector-Aufruf zum Erzeugen des Bundles lief ins Zeitlimit. Anschließend wurde das vollständige tatsächliche `connector-v6-quality-gate.json` gelesen: Abschlusszeit, Gesamtstatus, einzelne Prüfschritte und Artefakte sind bestätigt. Das Zeitlimit wurde nicht selbst als Prüfergebnis gewertet. Das Feld `deploy` dieser Datei beschreibt hier die erzeugten PC-Artefakte, nicht eine Live-Auslieferung.

PC-HA-Core-JavaScript: 659.246 Byte, SHA-256 `e2ebb242d6c787e8e1998cd997be2f651eb1830b59eac99925bd11f442d2e4d5`.
CSS: SHA-256 `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.
Buildmanifest: SHA-256 `0215fad8b2bea6c5e3767c7053de7b3b3d2514cd967c3752f41fe507721d609e`.

## Sicherung und Quellübernahme

Vier bestehende PC-Dateien wurden zunächst frisch gelesen und per SHA-256 gegen die Prüfstandsgrundlage geprüft. Vor der Änderung wurden vollständige Originale gesichert. Drei neue Dateien wurden ohne Überschreiben angelegt. Alle sieben PC-Ziele wurden nach dem Schreiben vollständig rückgelesen.

PC-Sicherung: `backups/20261005-material-preview-colors/` mit Originalen, `rollback.json` und `source-application.json`. Rücknahme nur bei Übereinstimmung mit dem dokumentierten Nachherhash; spätere fremde Änderungen dürfen nicht überschrieben werden. Kein automatisches Rücksetzen ausgeführt.

Isolierter HA-Prüfstand: `/config/backups/20261005-preview-popup-local/`, einschließlich Originalquellen, exakter Änderungen, gezielter Testlogs, PC-Übernahmenachweis und vollständig gelesener PC-Gatedatei. Die tatsächliche Hostablage liegt unter `/var/lib/homeassistant/homeassistant/backups/`.

## Weiter offen

1. Der alternative eigenständige Viewer `slicer-toolpath-viewer.ts` wurde in diesem Abschnitt nicht angepasst. Dort bleibt der bisherige Ersatzfarbenpfad bestehen. PREVIEW-COLORS darf deshalb nicht als über alle Viewer vollständig abgeschlossen gelten.
2. Das 95-Prozent-MakerWorld-Popup wurde nicht verändert. Die vorbereiteten Layoutänderungen wurden vom Werkzeug-Sicherheitscheck blockiert und nicht über einen alternativen administrativen Zugriff erzwungen. Größe, mobile Bildschirmtastatur und echte Browserabnahme bleiben offen.
3. Die HA-Quellsynchronisierung wurde ebenfalls blockiert. Weder produktive Python-Dateien noch das ausgelieferte Frontend wurden ersetzt. Die zuvor vorbereiteten CAD-, Galerie-, Worker- und MakerWorld-Änderungen müssen für eine koordinierte Bereitstellung berücksichtigt werden; nur das neue PC-JavaScript unkontrolliert zu kopieren ist kein vollständiger Abgleich.
4. Der versuchte zusätzliche reine Lesevergleich gegen den bestehenden realen Vierfarben-G-Code wurde blockiert. Für diesen Arbeitsabschnitt wird deshalb kein neuer Realjob-/Pixelnachweis behauptet; die Aussage stützt sich auf die ausgeführten Produktionsfunktions- und Parserregressionen.
5. Der tatsächliche MakerWorld-Manifestabruf aus dem vorherigen Prüfpass bleibt ohne erneute Anmeldung/Berechtigungsdiagnose und erfolgreichen Live-Import offen. Seine Fehlerbehandlung ist eine getrennte bereits getestete PC-Änderung, kein in diesem Abschnitt gelöster Zugangsnachweis.
6. Zentrale Dokumentverknüpfung, privates Prüfdashboard, öffentlicher Repository-Abgleich, Namensmigrationskandidat und echte Browser-/iPhone-Abnahme sind jeweils separat zu bestätigen.

Keine neuen Slice-/Release-Aufträge, keine Druckeruploads, keine Druckstarts und keine Dienstneustarts. Das Studio bleibt Beta.
