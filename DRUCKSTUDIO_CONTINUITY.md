# 3D Ultimate Center V6 – Continuity / Projektübergabe

Stand: 2026-10-02

> Zweck dieser Datei: belastbarer Projektanker für die Fortsetzung des 3D Ultimate Center / Druckstudio V6, insbesondere solange der Tara-PC nicht verfügbar ist. Sie soll verhindern, dass Architektur, Regeln, offene Punkte, technische Abhängigkeiten und bereits getroffene Entscheidungen verloren gehen.
>
> Diese Datei ist **kein Ersatz für den Quellcode**. Das eigentliche Ziel ist weiterhin, den aktuellen V6-Stand **inklusive Slicing-Server** sauber in dieses Repository zu übernehmen, sobald der PC wieder verfügbar ist und der reale lokale Stand verifiziert wurde.

---

## 1. Projektziel

Das Projekt ist ein umfassendes 3D-Druck-Control-Center / „3D Ultimate Center V6“ für:

- Bambu Lab A1
- AMS / externe Spulen
- Materialverwaltung
- Druckprofile
- Slicing
- Druckvorschau
- Galerie
- CAD-/Zeichenfunktionen
- Steuerzentrale
- Aufgaben
- Verlauf
- System-/Diagnosebereich
- Home-Assistant-Integration
- MQTT-/Worker-Integration
- perspektivisch GitHub als kanonische Versionsbasis

Ziel ist **nicht** eine Demo, sondern ein belastbarer, produktiv nutzbarer Gesamtworkflow vom Modell bis zum Druck.

---

## 2. Aktuelle Situation / warum dieses GitHub-Repo existiert

Der Tara-PC mit dem primären lokalen Projektstand ist aktuell nicht verfügbar.

Deshalb wurde dieses GitHub-Repository als **neue externe Basis / Sicherungs- und Übergabeebene** angelegt.

Parallel wurde ein nativer MCP-Zugang auf der Home-Assistant-VM aufgebaut, damit trotz nicht verfügbarem PC weiterhin kontrolliert auf die relevante Linux-/HA-Infrastruktur zugegriffen werden kann.

Wichtig:

- Das Repository ist aktuell **noch nicht automatisch der vollständige Quellcode-Stand** des Druckstudios.
- Der lokale V6-Stand auf dem Tara-PC muss später sauber gegen dieses Repo abgeglichen werden.
- Der Slicing-Server gehört ausdrücklich mit in die spätere GitHub-Konsolidierung.
- Bis dahin dient diese Datei als Projekt- und Kontinuitätsanker.

---

## 3. Relevante lokale Repositories / bisherige Quellpfade

### Druckstudio V6

Bisheriger lokaler Windows-Pfad:

```text
F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Printer-Control-Center\v6
```

### Slicing-Server

Bisheriger lokaler Windows-Pfad:

```text
F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Printer-Slicing-Server
```

### Ziel

Beide Komponenten sollen künftig konsistent unter:

```text
Taracraft/3D-Ultimate-Center
```

geführt bzw. mindestens sauber miteinander versioniert und dokumentiert werden.

---

## 4. Verbindliche Arbeitsregeln

Diese Regeln gelten für jede Fortsetzung des Projekts:

1. **Nur V6 bearbeiten.**
   - V5 niemals verändern.

2. **Realen Zustand zuerst prüfen.**
   - Reale Repositories
   - Roadmap
   - Gates
   - Live-Zustand
   - laufende Services
   - vorhandene Backups

3. **Vor riskanten Änderungen Backup / Rollback sicherstellen.**

4. **Änderungen verifizieren, bevor der nächste Punkt begonnen wird.**

5. **LIVE_WORKLOG.md laufend aktualisieren**, sobald der eigentliche Quellstand wieder vorhanden ist.

6. Nach relevanten Arbeitspaketen sichtbare Statusblöcke / kurze Zwischenstände.

7. Am Ende eines Arbeitsabschnitts:
   - Änderungssummary
   - Test-/Verifikationsstatus
   - offene Punkte
   - ggf. Rollback-Hinweis

8. Nicht blind „neu bauen“, wenn ein funktionierender Bestand vorhanden ist.

9. Keine unnötige Token-/Kontextverschwendung durch ständiges vollständiges Neueinlesen des Projekts.

10. Bei Infrastrukturänderungen:
    - keine unnötigen Reboots
    - keine unkontrollierten Löschaktionen
    - Backup / Restore-Pfad vorhalten

---

## 5. Infrastruktur

### Home-Assistant-VM

Hostname:

```text
homeassist
```

Bekannte Host-IP:

```text
20.20.20.102
```

Home Assistant läuft nativ/Container-basiert mit Supervisor-Umgebung.

Wichtige aktuelle Komponenten:

- Home Assistant
- Supervisor
- MQTT-nahe Projektkomponenten
- Slicing-Server
- Puppet Add-on
- native Admin-MCP-Instanz
- verschiedene HA-Add-ons

### Homeassist nativer MCP

Der alte normale `ha-mcp` wurde entfernt.

Aktiv bleibt nur:

```text
admin-mcp.service
```

Code:

```text
/opt/admin-mcp/source/server.js
```

Port:

```text
8765
```

Öffentlicher MCP-Endpunkt:

```text
https://homeassist.bad-timing.eu/mcp
```

Der Connector wurde erfolgreich bis zur Root-Shell getestet.

Erfolgreich bestätigt:

- Hostname: `homeassist`
- Benutzer: `root`
- UID/GID: `0/0`
- Arbeitsverzeichnis: `/root`
- Exit-Code: `0`

Der native MCP besitzt vollständige Root-Shell-Fähigkeit und ist aktuell die Brücke, solange der Tara-PC nicht verfügbar ist.

---

## 6. OAuth / Keycloak für MCP

Authorization Server:

```text
https://ki.bad-timing.eu/realms/admin-mcp
```

Keycloak läuft auf der KI-Infrastruktur.

Wichtige funktionierende OAuth-Komponenten:

- Protected Resource Metadata
- RFC8414 Authorization Server Metadata
- OIDC Discovery
- Dynamic Client Registration
- PKCE S256
- ChatGPT CIMD
- private_key_jwt
- JWKS

### ChatGPT CIMD Client

Client-ID:

```text
https://chatgpt.com/oauth/client.json
```

Redirect URI:

```text
https://chatgpt.com/connector_platform_oauth_redirect
```

JWKS:

```text
https://chatgpt.com/oauth/jwks.json
```

Keycloak Client Authentication:

```text
Signed JWT
```

JWKS URL verwenden:

```text
AN
```

Ergebnis: Homeassist-MCP ist über ChatGPT erfolgreich authentifiziert und Root-Shell-Aufrufe funktionieren.

---

## 7. Slicing-Server

Der Slicing-Server gehört zum Gesamtprojekt und muss bei der GitHub-Konsolidierung ausdrücklich mit übernommen werden.

Bekannter Laufzeitpfad auf Homeassist:

```text
/var/lib/homeassistant/3d-printer-slicing-server
```

Bekannter Serverprozess:

```text
server.py
```

Bekannte Konfiguration:

```text
config.json
```

Ein lokaler Prozess lief zuletzt über:

```text
/usr/bin/python3 /var/lib/homeassistant/3d-printer-slicing-server/server.py /var/lib/homeassistant/3d-printer-slicing-server/config.json
```

Bekannter lokaler Listen-Port:

```text
8099
```

### Bekannte Auffälligkeit

Im Journal wurde zuletzt gesehen:

```text
dispatch-job.sh: 1: #!/bin/sh: not found
```

Das ist separat zu prüfen.

Außerdem trat auf:

```text
mv: ... diagnostics.json.tmp ... Datei oder Verzeichnis nicht gefunden
```

Diese Punkte dürfen bei der späteren Bereinigung des Slicing-Servers nicht vergessen werden.

---

## 8. MQTT / Druckerkommunikation

Der eigentliche Druckstart über Home Assistant wurde bereits erfolgreich getestet.

Bekannter Status:

- Druckstart über HA: funktioniert
- AMS wurde dabei grün / aktiv erkannt

Es existiert außerdem eine Cloud-MQTT-Komponente des Printer Control Centers.

Bekannter aktueller Fehler:

```text
cloud MQTT connection rejected: Not authorized
```

Dieser Fehler ist vom MCP unabhängig und muss separat behandelt werden.

---

## 9. Drucker / Material

Primärer Drucker:

```text
Bambu Lab A1
```

Materialquellen:

- AMS
- externe Spulen

Ziel für Materialanzeige:

- Darstellung soll sich an Bambu Lab orientieren
- geladenes Filament muss visuell eindeutig erkennbar sein
- auch externe Spule muss sichtbar dargestellt werden
- Farben / Materialauswahl sollen nur aus real verfügbaren AMS-/externen Spulen stammen

---

## 10. Druckstudio UI – aktueller positiver Stand

Bereiche, die in früheren Tests bereits positiv bewertet wurden:

- Druckvorschau: „nahezu perfekt“
- Galerie
- Materialeinstellung
- Slicing im UI
- System
- Steuerzentrale
- Verlauf
- Aufgaben

Diese Bereiche trotzdem bei einer Gesamtprüfung erneut verifizieren.

---

## 11. UI-/Funktionsänderungen – verbindlich

### 11.1 Druckprofil / Düse

Wichtige zuletzt festgelegte Regel:

> Bei einem Druckerprofil soll **nur der Drucker** ausgewählt werden, **nicht zusätzlich die Düse**.

Die Düsenauswahl darf nicht doppelt bzw. redundant auftauchen.

Bekannter Fehler in der Home-Assistant-App:

- rechte Seite unten teilweise nicht weiter scrollbar
- bei Druckerprofil war nur eine 0,2-mm-Düse auswählbar
- dieses zusätzliche Feld soll verschwinden, wenn die Düse bereits an anderer Stelle korrekt gewählt wird

Weitere Vorgaben:

- rechte Bezeichnung „Prozess“ → **„Druckprofil“**
- linke redundante Spalte „Druckprofil“ entfernen
- Menüpunkt „Druckprofile“ entfernen
- Düsen-/Druckprofilsteuerung rechts sinnvoll beibehalten
- altes Profil mit nur 0,2 mm löschen
- Cloud-Profil-Sync nur manuell unter „Profile“

### 11.2 Filament / Material

- Filamentprofil-Liste muss scrollbar sein
- Filament-/Material-Menü darf keine Fehler erzeugen
- AMS-Navigation passend umbenennen
- alle relevanten Materialquellen anzeigen
- externe Spule sichtbar machen
- geladene Materialien mit passenden Symbolen/Farben anzeigen

### 11.3 Support

Fehlendes / gewünschtes Support-Popup:

- Überhang
- Brücken
- Objektname

### 11.4 Zeichnen / CAD

Aktuelle Probleme:

- Zeichnen erzeugte teilweise Dreiecke
- Kreis defekt
- Rechteck defekt

Ziel ist eine Photoshop-artige Werkzeuglogik mit:

- Pinsel / Brush
- Radierer
- Linien
- Text
- Kreis
- Rechteck
- Auswahl
- Strg
- Shift
- Strg+A
- Entfernen
- sichtbare Rahmen-/Preview-Darstellung während des Ziehens

### 11.5 Objektliste / Malbereich

In der Objektliste soll ein eigener Bereich entstehen:

```text
Malbereich
──────────
[Objekte darunter]
```

---

## 12. PLA-Test / Druckqualität

Bekannter separater PLA-Test:

Material:

```text
Sunlu PLA+
```

Temperatur:

```text
220 °C
```

Platte:

- zuvor Smooth PEI
- danach Texturplatte

Profil:

```text
0.20 mm
Generic PLA
```

Problem:

- erster Layer klumpig

Getestete Z-Offsets:

```text
-0.05
-0.02
 0.00
+0.02
```

`+0.02` war besser.

Zusätzliche Vorgabe:

- Bed-Bedingung entfernen
- Standardwert verwenden
- Teststreifen ist Pflicht

---

## 13. System-/Monitoring-Wünsche

Das Monitoring soll:

- kompakt
- technisch tief
- visuell hochwertig
- live
- ohne Duplikate

sein.

Gewünscht:

- animierte Graphen
- Live-Logs
- Token/s
- klarer Ausführungsstatus
- keine redundanten Daten

Puppet:

> Port niemals blind als 1000 annehmen.

Bekannter veröffentlichter Host-Port war zuletzt:

```text
5000 -> Container 10000
```

---

## 14. Entwicklungs-/Autopilot-Regeln

Historisch wurden folgende Skills/Arbeitsprinzipien genutzt:

- ultimate-druckstudio
- project-continuity
- transparent-execution
- nonstop-goal-execution
- transactional-recovery
- verification-loop

Arbeitsmodus:

```text
AUTOPILOT
```

Zielverhalten:

- höchstpriorisierten offenen V6-Punkt finden
- bearbeiten
- testen
- verifizieren
- Worklog aktualisieren
- danach selbstständig nächster Punkt

Wichtig:

> Nicht nach jedem einzelnen Schritt auf Bestätigung warten, sofern keine riskante/destruktive Entscheidung ansteht.

---

## 15. Bekannte strukturelle Probleme / zu prüfende Punkte

Bei der nächsten vollständigen Tiefenanalyse mindestens prüfen:

### Navigation
- doppelte Einträge
- inkonsistente Begriffe
- redundante Profil-/Düsenwahl
- mobile/HA-App-Scrollprobleme

### Profile
- Drucker vs. Düse korrekt getrennt
- keine veralteten 0,2-mm-only-Profile
- Cloud-Sync nur manuell
- Profilverwaltung konsistent

### Material
- AMS
- externe Spule
- Symbole
- Farben
- Scrollbarkeit
- Auswahlfehler

### CAD / Zeichnen
- Kreis
- Rechteck
- Linie
- Text
- Brush
- Eraser
- Selection
- Keyboard-Modifikatoren
- Live-Preview

### Slicing
- API
- Queue
- dispatch-job.sh
- diagnostics.json
- Fehlerbehandlung
- Jobstatus
- Integration in UI

### System
- echte Livewerte
- keine toten / doppelten Datenquellen
- keine falschen Ports
- Logging
- Healthchecks

### Galerie
- Persistenz
- Auswahl
- Übergabe an Slicing
- Metadaten

### Aufgaben / Verlauf
- echte Statuskette
- keine Phantom-Jobs
- Wiederaufnahme / Retry

---

## 16. GitHub-Zielstruktur

Sobald der Tara-PC wieder verfügbar ist, soll **nicht blind alles in main kopiert** werden.

Empfohlener Ablauf:

1. lokalen V6-Stand inventarisieren
2. lokalen Slicing-Server inventarisieren
3. Secrets / Tokens / lokale Credentials identifizieren
4. Build-Artefakte / Cache / node_modules / venv / temporäre Dateien ausschließen
5. passende `.gitignore` erstellen
6. Verzeichnisstruktur für gemeinsames Repo festlegen
7. initialen Source-Import in separatem Branch erstellen
8. Diff gegen laufenden Homeassist-/Slicer-Stand
9. Funktionstests
10. erst dann sauber nach `main` übernehmen

Mögliche spätere Struktur:

```text
/
├─ app/                     # Druckstudio V6
├─ slicing-server/          # Slicing-Server
├─ docs/
├─ deployment/
│  ├─ homeassistant/
│  └─ systemd/
├─ scripts/
├─ tests/
├─ README.md
├─ LIVE_WORKLOG.md
└─ DRUCKSTUDIO_CONTINUITY.md
```

Diese Struktur ist ein Vorschlag und muss gegen den realen Quellstand geprüft werden.

---

## 17. Sicherheits-/Secret-Regel für GitHub

Dieses Repository ist öffentlich.

Daher **niemals** committen:

- Home-Assistant Long-Lived Tokens
- MQTT-Passwörter
- Keycloak Client Secrets
- MCP-Shell-Token
- private Schlüssel
- API Keys
- interne Zugangsdaten
- Browser-/Session-Cookies
- produktive `.env` mit Secrets

Stattdessen:

- `.env.example`
- dokumentierte Variablennamen
- Secrets lokal / in Secret Stores halten

---

## 18. Aktueller MCP-Status

Der Homeassist-MCP funktioniert aktuell erfolgreich über ChatGPT.

Zielkette:

```text
ChatGPT
→ Homeassist MCP
→ OAuth / Keycloak
→ nativer admin-mcp
→ Root Shell
```

Der alte zusätzliche `ha-mcp.service` wurde entfernt.

Aktiv:

```text
admin-mcp.service
```

Port:

```text
8765
```

Damit besteht eine belastbare Remote-Basis für die Zeit ohne Tara-PC.

---

## 19. Was als Nächstes zu tun ist

### Solange der Tara-PC NICHT verfügbar ist

1. Homeassist-Livestate nur kontrolliert prüfen.
2. Slicing-Server vollständig inventarisieren.
3. bestehende Deployments / Konfigurationen dokumentieren.
4. keine riskanten Quellcode-Rekonstruktionen aus Runtime-Dateien machen, wenn der echte Source-Stand später verfügbar wird.
5. GitHub-Dokumentation / Projektstruktur vorbereiten.
6. vorhandene Bugs und Anforderungen konsolidieren.

### Sobald der Tara-PC wieder verfügbar ist

1. V6-Repository vollständig lesen.
2. Slicing-Server-Repository vollständig lesen.
3. aktuellen Git-Status / Branches / uncommitted changes sichern.
4. Backups erzeugen.
5. realen lokalen Stand gegen laufenden HA-/Slicer-Stand diffen.
6. gemeinsame Zielstruktur festlegen.
7. Source in `Taracraft/3D-Ultimate-Center` übernehmen.
8. Secrets entfernen.
9. Tests / Build / Slicing / UI / HA-Integration durchführen.
10. erst nach erfolgreicher Verifikation `main` als kanonische Basis festlegen.

---

## 20. Definition of Done für die GitHub-Konsolidierung

Die Übernahme gilt erst als abgeschlossen, wenn:

- vollständiger V6-Source im Repo
- vollständiger Slicing-Server-Source im Repo
- keine Secrets committed
- Build reproduzierbar
- App startet
- Slicing funktioniert
- HA-Kommunikation funktioniert
- Druckerstatus funktioniert
- AMS / externe Spule funktionieren
- Profilverwaltung konsistent
- Galerie funktioniert
- CAD/Zeichnen grundlegend funktioniert
- Aufgaben / Verlauf funktionieren
- Systembereich liefert echte Daten
- Tests/Gates dokumentiert
- LIVE_WORKLOG.md vorhanden
- README mit Setup / Architektur / Deployment vorhanden
- Backup-/Rollback-Pfad dokumentiert

---

## 21. Wichtigster Grundsatz für die Fortsetzung

> **Der aktuelle Livezustand und der echte Quellcode haben Vorrang vor Erinnerungen oder Annahmen.**

Diese Datei dokumentiert den bekannten Projektstand und die verbindlichen Entscheidungen. Sobald reale Repositories / Laufzeitstände davon abweichen, muss die Abweichung untersucht und diese Datei anschließend aktualisiert werden.
