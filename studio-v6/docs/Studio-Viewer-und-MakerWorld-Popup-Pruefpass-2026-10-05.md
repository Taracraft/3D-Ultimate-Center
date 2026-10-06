# Ultimate Studio · Separater Viewer und 95-Prozent-MakerWorld-Popup

Stand: 05.10.2026. Vollständiges PC-Gate abgeschlossen um 01:25:51 CEST.

## Ergebnis und Agenda

Die Anforderungen PREVIEW-COLORS-20261004 und MW-MODAL-95-20261004 sind im kanonischen PC-Quellstand um den separaten G-Code-Viewer und das vergrößerte MakerWorld-Detailfenster ergänzt. Die vorherige Umstellung der Hauptvorschau bleibt erhalten. Die beiden Produktdateien wurden nach Sicherung übernommen und anhand der während des tatsächlichen PC-Testlaufs aufgezeichneten SHA-256 bestätigt.

**Nicht abgeschlossen:** HA-Quellsynchronisierung, produktive Aktivierung, reale Browser-/iPhone-Abnahme, öffentlicher GitHub-Abgleich, privates Prüfdashboard und Übernahme in den Namensmigrationskandidaten. Ein grünes PC-Gate ist kein Nachweis einer Live-Bereitstellung. Die Agenda-Punkte bleiben bis zur vollständigen Abnahme teilweise offen; der Beta-Status bleibt bestehen.

Der MakerWorld-Import-/Authentifizierungsfehler ist in diesem Arbeitsabschnitt nicht erneut behoben oder live erfolgreich abgenommen worden. Die zuvor festgestellte Manifestablehnung HTTP 401 bleibt ein eigener offener Punkt. Änderungen an Anmeldeinformationen wurden nicht ausgeführt.

## Separater G-Code-Viewer

`frontend/slicer-toolpath-viewer.ts` verwendet dieselbe strenge, auftragsgebundene Farbzuordnung wie die Hauptvorschau. Die bisherige frei gewählte Ersatzpalette wurde entfernt. Unbekannte, ungültige oder fehlende Kanäle werden nicht zyklisch auf ein vorhandenes Filament abgebildet. Sie erscheinen neutral und ausdrücklich als „Farbe unbekannt“, einschließlich einer Warnung für die tatsächlich geladenen Bahnen. Unvertrauenswürdige Materialnamen werden weiterhin als Text ausgegeben.

Im Materialmodus behalten aktuelle und frühere Layer ihre Material-RGB-Werte. Die bisherige starke Abdunklung früherer Layer bleibt nur für die ausdrücklich gewählte Drucktyp-Diagnose bestehen. Der Wechsel zwischen Material- und Diagnoseansicht verändert keine Geometrie oder Druckdaten.

Beim Neuladen werden bisherige Bahnen vor Übernahme der neuen Farbpalette verworfen. Der Abruf bleibt an seine ursprüngliche Job-ID gebunden. Neue Abrufe, das Leeren der Jobauswahl und das Trennen des Viewers invalidieren alte Antworten und brechen laufende Anfragen ab. Verspätete Antworten dürfen keine neue Auswahl ersetzen. Schrittweise geladene Datenblöcke erhalten unabhängige Layerlisten, damit Warnungen nicht auf veralteten Cache-Ergebnissen beruhen. Fehler lösen keine automatische Wiederholung aus.

## MakerWorld-Detailfenster

`frontend/makerworld-detail-dialog-v6.ts` legt den Dialog auf die sichtbare Websitefläche aus: regulär 2,5 Prozent Außenabstand auf jeder Seite, entsprechend 95 Prozent Breite und Höhe. Größere mobile Sicherheitsabstände bleiben berücksichtigt. Die früheren festen Obergrenzen von 1.220 Pixeln Breite und 900 Pixeln Höhe entfallen.

Der Dialog besitzt getrennte Kopf-, Inhalts- und Fußbereiche. Die Fußzeile mit Lizenzangabe, Zieldruckerwahl und den drei Aktionen „Im Studio öffnen“, „Galerie“ und „3MF“ befindet sich außerhalb der scrollbaren Inhaltsspalten. Beschreibung, Druckprofile und Empfehlungen erhalten eigene Scrollbereiche; horizontale und vertikale Positionen werden beim Neuzeichnen wiederhergestellt. Fehler erhalten einen begrenzten, scrollbar erreichbaren Bereich mit Alarmrolle und Tastaturfokus.

Die Anordnung reagiert auf die tatsächliche Dialogbreite. Ein optionaler VisualViewport-Listener berücksichtigt Änderungen von sichtbarer Größe und Versatz, etwa durch Bildschirmtastatur oder Vergrößerung. Ungültige Messwerte werden ignoriert. Die Listener werden bei Schließen, erkannter Trennung und pagehide freigegeben. Es gibt dafür weder dauerhaftes Polling noch einen MutationObserver. Die bestehenden Import-, Galerie- und Downloadfunktionen wurden nicht durch neue Übertragungswege ersetzt.

**Abnahmegrenze:** Das 95-Prozent-Layout und die Ereignisbehandlung sind implementiert und automatisiert geprüft. Reale Dialogabmessungen, Fokusfalle, Touch-Scrollen, Safari-/iPhone-Verhalten und die Darstellung des gemeldeten Modells sind noch nicht visuell bestätigt. Der versuchte isolierte Browseraufruf wurde administrativ blockiert; es liegt kein gültiger Screenshotnachweis vor.

## Prüfungen und Ergebnisse

29 neue gezielte Node-Vertragstests prüfen 19 Viewerfälle und zehn Popupfälle. Sie führen Produktionsfunktionen mit ausdrücklich begrenzten DOM-/Netzwerk-Doubles aus. Darunter sind echte RGB-Werte der erzeugten Vertexpuffer, fehlende Kanäle, unveränderte Geometrie, Neuladen, verspätete Antworten, Abbruch, progressive Daten, Fensterereignisse, Aufräumen, Scrollzustand und die Layoutstruktur. Die isolierte Linux-Arbeitskopie und der kanonische Windows-PC bestehen diese Prüfungen.

`tests/test_viewer_modal_node_contract.py` startet diesen Block im regulären Python-Gate als **einen** pytest-Test. Er prüft Rückgabecode, nichtleere Testmenge, Fehler-/Skip-Zahlen und unveränderte Quellhashes. Die 29 internen Tests dürfen nicht noch einmal als 29 zusätzliche Python-Projekttests gezählt werden.

Der erste vollständige PC-Lauf scheiterte an genau einer bestehenden Frontendprüfung: Der Lizenztest suchte noch nach einem div statt der neuen semantischen Fußzeile. Nach vollständiger Sicherung wurde die Prüfung auf den tatsächlichen footer umgestellt und zusätzlich auf alle drei benachbarten Transferaktionen erweitert. Die Lizenz-, Escaping- und Nicht-Vortäuschungsprüfungen bleiben erhalten; kein Test wurde abgeschaltet.

Der zweite vollständige PC-Lauf ist erfolgreich:

| Prüfung | Ergebnis |
| --- | --- |
| Source-Policy | Bestanden |
| TypeScript | Bestanden |
| Frontend-Logiktests | 403 bestanden, keine Fehler, keine ausgelassenen Tests |
| Produktionsbuild und HA-Core-Build | Beide bestanden, 130 gebündelte Module |
| Python-/Worker-Gate | 1.576 bestanden, neun plattformbedingt ausgelassen, zusätzlich 15 Untertests bestanden |
| Python-Syntax, Imports und Komponentencompile | Bestanden |
| Neuer interner Node-Vertragsblock | 29 bestanden, keine Fehler oder ausgelassenen Tests |

Die neun ausgelassenen Fälle erfordern native Linux-Prozessgruppen und wurden auf Windows nicht ausgeführt. Sie werden in diesem Abschnitt nicht als unter Linux erneut bestanden behauptet.

Das PC-Gate lief vom 05.10.2026 01:21:51 bis 01:25:51 CEST. Trotz Connector-Zeitlimit wurde der Abschluss aus der tatsächlichen vollständigen Statusdatei bestätigt. Der gezielte Node-Block endete um 01:25:41 CEST; die erneute Leseprüfung bestätigt dessen Erfolg und identische Vorher-/Nachherhashes.

## Nachweise und Quellhashes

Maßgebliche PC-Dateien: `.test-results/connector-v6-quality-gate.json`, `.test-results/frontend-test-status.json`, `.test-results/viewer-modal-node-contract.json` und `.test-results/python-test-status.json`.

| Quelle | SHA-256 |
| --- | --- |
| Separater Viewer | `81e4c81d2f12b967383c3f3875578112e58c59a5285a06efa9b8bb14814b8e74` |
| MakerWorld-Dialog | `7042d25e4c156653071ef59eb14b2fd313ac7b09c83ef250a0eddb8ea9312d21` |
| Unveränderter gemeinsamer Farbhelfer | `38630b06a08ca1fabd29b09286d472baec9a5c95ea3ce8617c15aafda25d35fe` |
| Neuer Node-Vertragsblock | `2ddd6287d83e57f03020eedfb66146e7a647f43f2c08a452c63f631e07c11967` |

Erzeugtes HA-Core-JavaScript: 662.309 Bytes, SHA-256 `e3d9072a65a06ea3c30e738d5f5be543d7f1b32ddfea66419895673474433c99`. Dies ist das geprüfte **PC-Buildartefakt**, kein produktiver HA-Dateihash.

## Sicherung und Fortsetzung

PC-Sicherungsordner: `backups/20261005-viewer-modal`. Die Dateien `viewer-rollback.json` und `popup-rollback.json` enthalten exakte reversible Änderungen mit Vorher-/Nachherhashes. `makerworld-attribution.before.ts` enthält die vollständige ursprüngliche Lizenzprüfung. Neue Tests wurden ohne Überschreiben angelegt. Rücknahme nur bei passendem aktuellen Nachherhash; spätere Änderungen müssen erhalten bleiben. Kein Rücksetzen wurde ausgeführt.

Dieser Bericht und der ergänzende Arbeitsnachweis im Sicherungsordner führen den Fortschritt fort. Hauptroadmap und zentrales Arbeitsprotokoll wurden in diesem Abschnitt nicht erneut verändert; deren vorheriger Nachtrag bleibt erhalten.

Als Nächstes sind der gesicherte HA-Quellabgleich, die getrennte Bereitstellung und echte Bedienabnahme erforderlich. Parallel bleibt die MakerWorld-Anmeldung beziehungsweise Downloadberechtigung zu klären. Kein Slice, kein Druckerupload, kein Druckstart, keine Änderung laufender Aufträge und kein Dienstneustart wurden ausgeführt.
