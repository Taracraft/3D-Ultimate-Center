<!-- 2026-09-30 Supportwarnung Filamentprofile Puppet -->
# V6 Supportwarnung, Filamentprofile und Puppet-Reparatur – 2026-09-30

## Ergebnis

Die V6-Studio-Reparatur wurde gebaut, getestet, live deployed und über HA-Dateihashes verifiziert.

## Fachliche Änderungen

- Links in der Studio-Profilbar entfällt das überflüssige Druckerprofil-Menü.
- Rechts bleiben Düse und Druckprofil/Prozess erhalten.
- "Filamentprofile" ist ein gemeinsames Menü für lokale, Standard- und bereits synchronisierte Cloud-Profile.
- AMS/AMS Lite und Externe Spule bleiben explizit als Materialquelle auswählbar.
- Cloud-Profile werden nicht automatisch synchronisiert; Synchronisation bleibt ein manueller Vorgang im Bereich Profile.
- Supportwarnungen erscheinen als native Modal-Dialoge und blockieren Slice/Upload/Print bis zur Entscheidung.
- Supportwarnungen zeigen alle betroffenen Objekte, escapen Namen sicher und benennen Dreieck-/Überhangwerte korrekt.

## Tests

- Frontend TypeScript/Build: grün.
- Frontend Logic Tests: 145 bestanden.
- Python/Backend-Gate: 519 Tests + 3 Subtests bestanden.
- Source-Policy-Gate: keine Verstöße gemeldet.
- Live-Hash-Verifikation auf HA:
  - JS: cfb87956f95d4384752ad201bc05015bd462e93005a2b7018fd6de8efd973677
  - CSS: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
  - Build JSON: 99dbdb2cef3721b20599cfd7cde0a34132d4d3465bd99fe350c6b3c27e5f1f20
- Puppet: Port 5000 antwortet mit HTTP 200, Content-Type image/png und gültiger PNG-Signatur.

## Puppet-Regel

Puppet ist nicht Opera und nicht Puppeteer aus Codex heraus. Der gültige Prüfweg ist lokal auf dem Home-Assistant-Host:

`http://127.0.0.1:5000/3d-studio-v6-test?viewport=1280x720&dark&wait=5000`

Die Add-on-Option verwendet:

`home_assistant_url=https://homeassist.bad-timing.eu:8123/`

Damit Zertifikat und interne Erreichbarkeit gleichzeitig stimmen, braucht der Puppet-Container Split-DNS:

`172.30.32.1 homeassist.bad-timing.eu`

Am 2026-09-30 wurde diese Zuordnung im laufenden Container gesetzt und der Screenshotdienst erfolgreich getestet. Wenn der Puppet-Container später neu gestartet wird, muss diese Split-DNS-Zuordnung dauerhaft im Add-on-/Host-DNS nachgezogen oder erneut gesetzt werden.

## Rollback-Hinweise

Vor dem Live-Deploy wurden vorhandene HA-Frontend-Dateien als `.bak.20260930-support-filament` gesichert, sofern vorhanden. Quelländerungen im Repository wurden ebenfalls als `.bak.20260930-support-filament` neben den bearbeiteten Dateien gesichert.

## 2026-09-30 Slicing-Druckpfad-Prüfung

Nachträgliche Betriebsprüfung:

- Drucker: Bambu A1 online und idle.
- V6 Status: ready.
- Native Slicing Server: ready, aktive Jobs 0, wartende Jobs 0.
- Erfolgreicher Test ohne Druckstart: `codex-v6-reslice-known-good-20260930`, Bambu Studio `return_code: 0`, Output erzeugt.
- Drucker blieb danach idle.
- Diagnose-Falschmeldung repariert: `last_error` wird bei abgeschlossenem letztem Job auf `none` gehalten.
- Offen: Minimal-STL/Defaultprofil-Fall separat analysieren.
