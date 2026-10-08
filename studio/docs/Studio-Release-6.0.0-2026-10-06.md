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

## Native Worker und Linux-Vertrag

- A1-Profil meldet nur noch den tatsächlich materialisierten Engine-Pfad `bambu_studio`.
- Gezielte Linux-Regressionsprüfung nach der A1-Korrektur: 100 bestanden; nur die bekannte asyncio_mode-Warnung.
- Realer kanonischer 27-Dateien-Preflight: success=true.
- Paket-SHA256: 549b199adc64b7bff9a5698335f6aa3e1d219d40bbb224285bf1afab1139db5c.
- Native Dienste aktiv; queued=0, slicing=0, kein dispatcher.lock.
- Runtime-, Unit- und Profil-SHAs entsprechen dem kanonischen Quellstand.
- Kein realer Slice, Upload oder Druckstart wurde für diesen Nachweis ausgeführt.

## Öffentliche Finalisierung

- Erlaubter öffentlicher Releaseumfang gegen den kanonischen PC-Fingerprint geprüft: 0 fehlende und 0 abweichende Dateien.
- Nicht veröffentlicht: generierte lokale frontend/dist-Duplikate, drei private operative Release-/P0-Arbeitsberichte sowie zwei lokale STL-Testmodelle.
- Release-Branch letzter geprüfter Head vor Merge: fa441a711fee5e45b9993840bbd18267663ff332.
- CI an diesem Head:
  - Linux Bootstrap Contract Run 37467621861: SUCCESS
  - Rebuild Check Run 37467621889: SUCCESS
  - Native Deploy Contract Run 37467622045: SUCCESS
- PR #1 aus Draft genommen und erfolgreich nach main gemergt.
- Öffentlicher Merge-Commit: 9c20c7ab3bdb6de2b74500287b1021316e5a633b.
- Mergezeit: 06.10.2026 15:04:16 CEST.

## Rückweg und Sicherheit

- PC-Vorherstände: backups/20261006-stable-6.0.0/before
- HA-Quellvorherstände: /var/lib/homeassistant/homeassistant/backups/20261006-stable-6.0.0-source-before
- HA-Livevorherstände: /var/lib/homeassistant/homeassistant/backups/20261006-stable-6.0.0-live-before
- Nativer Worker wurde für den Stable-Versionswechsel nicht neu deployt.
- Keine Druckerbefehle, realen Test-Slices, Job-Releases, Druckeruploads, Bewegungen, Heiz-/Filamentaktionen oder Druckstarts.

## Post-Release

- MakerWorld-Liveanmeldung/-Import bleibt als Post-Release-Arbeit bestehen.
- Nicht ausgeführte interaktive/physische Abnahmen werden nicht rückwirkend als bestanden dargestellt.
