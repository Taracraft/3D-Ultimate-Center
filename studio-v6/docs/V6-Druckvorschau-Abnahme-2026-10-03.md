# Druckvorschau: Reparatur und getrennte Abnahme am 03.10.2026

## Geltender Auftrag

Originale Druckvorschau und ursprünglichen Ladebalken ohne Neugestaltung erhalten. Zugriff auf Homeassist nativ über Homeassist_MCP; vorhandenes Puppet auf Host-Port 5000. Kein Codex, kein alter HA-Connector, kein zusätzliches Puppeteer und kein Ersatzrenderer.

## Erneut bestätigte Softwareprüfung

Der bereits erzeugte Live-Testjob `server__v6-preview-restore-20261003T121119Z` ist erfolgreich. Die authentifizierte Job-API liefert HTTP 200 und `succeeded`; die produktive Toolpath-Route mit `start=0&end=1` liefert HTTP 200, einen Layer und 690 Segmente. Es wurde in dieser Fortsetzung kein neuer Slice und kein Druck gestartet.

38 gezielte Artefakt- und kanonische Worker-Regressionsprüfungen erneut bestanden. Der HA-Testlauf meldet zusätzlich eine Pytest-Konfigurationswarnung zum dort nicht verfügbaren asyncio_mode-Plugin; kein fehlgeschlagener Test. Das bereits vor der Bereitstellung bestandene PC-Gesamtgate umfasst 149 Frontendtests, 1250 Python-Tests und drei Untertests. Alle 213 zuvor geprüften A1-/H2S-Artefakte bestehen die korrigierte Abschlussprüfung.

Die Reparatur betrifft ausschließlich den Bett-Phasenvertrag: Bei nachgewiesen genau einer tatsächlichen Druckschicht wird kein Heizbefehl für eine nicht existierende Folgeschicht verlangt. Parameterübernahme, Erstschichtheizung, Hardwaregrenzen sowie Mehrschicht- und Manipulationsprüfungen bleiben verbindlich.

## Originaldarstellung bleibt unverändert

Alle 207 Frontend-Quelldateien wurden erneut gegen die Sicherung geprüft: keine Änderung. Produktives JavaScript SHA256: `0bcc578072e2fd23ff5bd81cedf8a2bfa919cb5795cbc66fe82f6ad5d4d0ed9e`. Produktives CSS SHA256: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.

Das ist ein Gleichheitsnachweis gegenüber dem Zustand vor dieser Reparatur, keine automatisch bestandene Pixel-Abnahme gegenüber einem früher akzeptierten Screenshot.

## Tatsächlicher Puppet-Befund

Puppet auf Port 5000 liefert HTTP 200, image/png, eine gültige PNG-Signatur und 96614 Bytes. Das Bild wurde tatsächlich betrachtet: Es zeigt die Steuerzentrale, nicht die Druckvorschau. Der bisherige Dashboard-Screenshot ist daher kein visueller Nachweis für gerenderte Druckbahnen oder den Vorschau-Ladebalken.

Die bereits vorhandene Puppet-Browsersitzung ist mit Home Assistant verbunden. Das reine Auslesen ihrer Navigation ergab ein vorhandenes Bedienelement 3D-Studio. Der anschließende Werkzeugaufruf für den Navigationsklick wurde von den Sicherheitschecks blockiert. Diese Sperre wird nicht durch alternative Browser, DOM-Injektion oder einen anderen Navigationsweg umgangen. Die Prüfskripte verändern keine produktiven Frontend-Dateien.

## Noch offen

- Echte Vorschau und ursprünglichen Ladebalken in der bestehenden Puppet-Sitzung sichtbar prüfen.
- Einlagigen und mehrschichtigen Fall sowie Plattenwechsel und erneutes Slicen visuell abnehmen; UI-Fortschritt und Abschluss müssen zusammenpassen.
- Die vorhandene Anzeige pending_gcode_analysis nach tatsächlich angeforderter Vollanalyse prüfen; sie wurde nicht künstlich auf bestätigt gesetzt.
- Reparatur und Dokumentation über PC, HA und öffentlichen GitHub-Commit per Datei-/Blobhash abschließen. Ein vorbereiteter Import oder erfolgreicher API-Test ist kein Veröffentlichungsnachweis.

Die Gesamt-Reparatur bleibt bis zur visuellen Endabnahme offen. Kein Beta-Ausstieg und keine Freigabe eines Druckstarts. In dieser Fortsetzung kein Dienstneustart, kein Druckerupload, kein Materialschreiben und keine Änderung der Renderer-/Popup-Optik.
