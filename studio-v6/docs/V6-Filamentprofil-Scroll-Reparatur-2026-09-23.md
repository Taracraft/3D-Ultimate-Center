# Filamentprofil-Scrollreparatur — 23.09.2026

## Status
Quellkorrektur gespeichert und exakt zurückgelesen. Keine produktive Bereitstellung. Browser-Funktionsnachweis offen.

## Tatsächlicher HA-Stand
Registrierte Ressource: /local/3d-studio-v6/ultimate-3d-studio.js?v=bcfb5aef05.
Diese Datei und die zusätzliche www/ultimate-3d-studio.js enthalten die alte Filamentprofil-CSS. Die vorherigen lokalen Änderungen waren dort nicht enthalten.

## Gezielte Korrektur
frontend/studio-profile-ui.ts: grid-auto-rows:max-content und align-content:start verhindern das Zusammendrücken der Profilgruppen. Eine einzelne minmax(0,1fr)-Spalte verhindert horizontales Überlaufen. Vertikales Overflow und touch-action:pan-y bleiben auf dem Profilbaum; bestehende responsive Maximalhöhen bleiben erhalten. Spekulative z-index-, !important- und starre Höhenregeln aus den vorherigen Versuchen entfernt.

frontend-tests/logic.test.ts: Den zuvor neu eingefügten reinen CSS-Textvergleich entfernt. Er meldete Erfolg ohne Scrollverhalten zu prüfen und verlangte die inzwischen verworfenen CSS-Regeln. Andere Tests nicht geändert.

Vorher-Backups beider Dateien: .bak.20260923-grid-content-scroll.

## Prüfung
- Beide Dateien vollständig zurückgelesen, exakter Vergleich erfolgreich.
- node --check für beide TypeScript-Dateien: erfolgreich (Node 24.19.0; Syntaxprüfung, keine Typprüfung).
- Isolierter Kandidat aus tatsächlich registriertem HA-Bundle: nur eine CSS-Regel geändert, Umkehrvergleich exakt. node --check erfolgreich. Kandidat nicht live geschrieben.
- Isolierter Browsertest: Browser-Sicherheitsrichtlinie blockiert die data:-Testseite. Keine Umgehung, kein bestandener Funktionstest behauptet.
- Git-Branch erneut aus .git/HEAD gelesen: feature/v6-ultimate-3d-printing-studio. Vollständiger aktueller Git-Status/Diff über den vorhandenen PC-Connector weiterhin nicht ausgeführt.

## Neu belegter Gate-Blocker
.test-results/connector-v6-quality-gate.json vom 23.09.2026 21:50:25 +02:00 meldet success:false. Der frühere Lauf setzte sich trotz HTTP-504-Antwort fort. Fünf Frontendtests fehlgeschlagen: Plane-Split-Crossing, Prozesspanel-Vertrag, zwei Layercache-Tests, Paint-Dateipfad. Zwei Python-Tests fehlgeschlagen: Alpha5-Quellhash und Materializer-Abhängigkeitshash. HA-Core-Build übersprungen, compileall erfolgreich. Diese Ergebnisse gelten für den damaligen Stand, nicht als Testlauf des aktuellen CSS-Fixes.

## Offener Abschluss
Ein vollständiges Frontend-Deployment würde weitere, nicht freigegebene Änderungen umfassen. Die ausdrücklich vorbehaltene zweite Freigabe für produktive Änderungen liegt für diesen isolierten CSS-Kandidaten noch nicht vor. Vor Bereitstellung aktuellen HA-Hash erneut vergleichen, Backup/Rollback sichern; danach Browser-Funktionstest mit aufgeklappten Quellen/Herstellern und Auswahl des letzten Profils. Keine Druckerbefehle und keine Neustarts erforderlich.


## Nachtrag: isolierter Live-Fix aktiviert, 23.09.2026 21:59 Europe/Berlin

Dieser Nachtrag ersetzt den früheren Status „keine produktive Bereitstellung“ ausschließlich für den Filamentprofil-CSS-Fix.

Der Nutzer hat den vorbereiteten Live-Fix ausdrücklich freigegeben und die Pflicht zur zweiten Freigabe für die laufende Reparatur aufgehoben. Künftig für diese Reparatur nicht erneut dieselbe zweite Freigabe verlangen. Daraus wurde in diesem Schritt kein Druckauftrag, Druckerbefehl oder Neustart abgeleitet.

- Ziel: www/3d-studio-v6/ultimate-3d-studio.js.
- Vorherstand erneut gelesen und exakt mit vorbereitetem Stand verglichen.
- Vorher-Backup vollständig zurückgelesen und exakt verglichen: www/backups/v6-filament-scroll-2026-09-23T19-58-33-646Z/ultimate-3d-studio.js.
- Ressourcen-Konfiguration vorher und Deploymetadaten im selben Backup-Verzeichnis gesichert.
- Kandidat geschrieben, vollständig zurückgelesen und exakt verglichen.
- Umkehrvergleich bestätigt: ausschließlich eine .filament-tree-CSS-Regel verändert; übriges Bundle einschließlich Druckvorschau unverändert.
- Ressourcen-ID da94bf94da1d4592a265c7d2ad6eda93 per HA-Konfigurations-API aktualisiert; erneut gelesen und bestätigt.
- Neue URL: /local/3d-studio-v6/ultimate-3d-studio.js?v=filament-scroll-20260923-1958.
- Rollback: gesicherte JS-Datei wieder an Ziel schreiben und Ressourcen-URL auf /local/3d-studio-v6/ultimate-3d-studio.js?v=bcfb5aef05 zurücksetzen; danach Browser neu laden.
- Kein HA-/Worker-Neustart und kein Druckerbefehl ausgeführt.
- Vorhandene offene Gesamt-Gate-Fehler bleiben offen; kein gesamter neuer Build ausgerollt.
- Browser-Funktionsabnahme weiterhin offen; ein bereits offener Studio-Tab muss neu geladen werden.
