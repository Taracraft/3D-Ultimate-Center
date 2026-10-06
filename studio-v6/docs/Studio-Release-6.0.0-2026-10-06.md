# Ultimate Studio 6.0.0 · Stable-Release-Nachweis · 06.10.2026

## Releaseentscheidung

Der Projekteigner hat den Beta-Ausstieg ausdrücklich freigegeben. Interaktive UI-/iPhone-Abnahme und Druckertelemetrie bei ausgeschaltetem Drucker sind keine 6.0.0-Release-Gates mehr. Das ist eine Scope-Entscheidung; nicht ausgeführte Abnahmen werden nicht als bestanden behauptet. MakerWorld-Liveanmeldung/-Import bleibt als Post-Release-Thema dokumentiert.

## Autoritative Version

- package.json / package-lock.json: 6.0.0
- Home-Assistant-Integration manifest.json / const.py: 6.0.0
- Historische Beta-Dokumentation bleibt unverändert.

## Finales PC-Gesamtgate

- Abschluss: 06.10.2026 13:37:13 CEST
- Frontend: 442/442 bestanden, 0 Fehler
- Python/Worker: 1.686 bestanden
- Plattformabhängige Windows-Auslassungen: 66
- Untertests: 15 bestanden
- Source-Policy: grün
- TypeScript: grün
- Produktionsbuild: grün
- Home-Assistant-Core-Build: grün
- Python Syntax/Imports: grün
- Home-Assistant-Compileall: grün
- Buildmanifest erwartet und bestätigt Version 6.0.0, 130 gebündelte Frontendmodule.

## Stable-Live-Aktivierung Home Assistant

- HA-Komponente live: 6.0.0
- manifest.json SHA256: 9e2cbe7c012eee71c4b1e64d634d7dce6cedbe8155f5db34ac6c10adae9cf589
- const.py SHA256: 5b912f55eeac5cefc271231a77a24d2eb7f3fb5412b5cf0e3d5b874fff4543a4
- Frontend-JS SHA256: a003082a45d2d658c2bc1daa2fc49bbea9a374b40fc8c04c68c00930d923caa0
- Frontend-CSS SHA256: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live-Buildmanifest: Version 6.0.0, JS-SHA a003082a..., 130 Module.
- HA-Konfigurationscheck vor dem Restart erfolgreich.
- Genau ein HA-Core-Restart ausgelöst; der Aufruf selbst lief in das erwartete Timeout und wurde nicht wiederholt.
- Home-Assistant-Container danach neu gestartet: StartedAt 2026-10-06T11:50:47.281788574Z (13:50:47 CEST).
- HA-Konfigurationscheck nach dem Restart erneut erfolgreich.

## Rückweg und Sicherheit

- PC-Vorherstände: backups/20261006-stable-6.0.0/before
- HA-Quellvorherstände: /var/lib/homeassistant/homeassistant/backups/20261006-stable-6.0.0-source-before
- HA-Livevorherstände: /var/lib/homeassistant/homeassistant/backups/20261006-stable-6.0.0-live-before
- Nativer Worker wurde für den Stable-Versionswechsel nicht neu deployt.
- Keine Druckerbefehle, realen Test-Slices, Job-Releases, Druckeruploads, Bewegungen, Heiz-/Filamentaktionen oder Druckstarts.

## Noch nachzuführen

- Öffentlichen GitHub-Head mit dem Stable-Quellstand synchronisieren.
- Alle Release-CI-Gates am Stable-Head grün bestätigen.
- PR #1 aus Draft nehmen.
- Danach diesen Nachweis um öffentlichen Commit/CI ergänzen.
- MakerWorld-Liveanmeldung/-Import als Post-Release-Arbeit weiterführen.
