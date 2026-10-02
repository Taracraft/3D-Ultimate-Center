# Full Import Policy

Stand: 2026-10-02

## Grundsatz

Für die Wiederherstellung des 3D Ultimate Center V6 gilt:

**Alles projekt- und rebuild-relevante wird übernommen.**

Ausgeschlossen werden ausschließlich Inhalte, die sicherheitskritisch oder reine Laufzeit-/Logdaten sind.

## Mitnehmen

- kompletter V6-Quellcode
- kompletter Slicing-Server
- Home-Assistant Custom Components
- Printer Control Center
- Printer Slicing Server Integration
- Frontend-Quellen
- Backend-/API-Quellen
- Tests
- Build-Skripte
- Deploy-Skripte
- Systemd Units
- Profile
- Druckerdefinitionen
- Materialdefinitionen
- Maschinenprofile
- Beispielkonfigurationen
- Dashboard-/Lovelace-Definitionen
- Web-Assets
- Icons/Logos/Bilder, sofern Bestandteil der Anwendung
- Migrationsskripte
- Datenbankschemas
- SQL-Schemas
- Dokumentation
- Roadmaps
- Validierungs-/Gate-Skripte
- Abhängigkeitslisten
- Checksums
- Installationsskripte
- Rebuild-Skripte
- Test-Fixtures, sofern für Reproduzierbarkeit notwendig
- notwendige Beispielmodelle/Testdateien, sofern sie Teil des Test-/Buildflows sind
- relevante Backups nur dann, wenn darin Quellbestand enthalten ist, der im aktuellen kanonischen Baum fehlt

## Nicht mitnehmen

- Logs
- Zugangsdaten
- Passwörter
- Tokens
- Session-Cookies
- API-Keys
- private Schlüssel
- Home-Assistant Auth-Storage
- Bambu Cloud Access-/Refresh-Tokens
- MQTT Credentials
- Keycloak Secrets
- MCP Tokens
- produktive .env-Dateien mit Secrets

## Generierte Laufzeitdaten

Generierte Dateien wie Output-GCode, temporäre Queue-Dateien, Cache, __pycache__, node_modules und ähnliche Artefakte werden nicht als kanonischer Quellbestand betrachtet, sofern sie reproduzierbar sind.

Falls ein generiertes Artefakt für einen Test, eine Regression oder den vollständigen Neuaufbau zwingend erforderlich ist, wird es gezielt als Fixture/Testasset übernommen.

## Zielzustand

Ein frisches System muss ausschließlich mit dem Inhalt dieses GitHub-Repositories plus neu gesetzten Secrets/Zugangsdaten vollständig aufgebaut werden können.

Der Neuaufbau gilt erst als vollständig, wenn folgende Kette auf einer frischen Maschine erfolgreich verifiziert wurde:

1. Abhängigkeiten installieren
2. V6 bauen
3. Home-Assistant-Komponenten deployen
4. Slicing-Server installieren
5. Systemd Units aktivieren
6. Profile/Materialien/Drucker laden
7. Frontend bereitstellen
8. Home Assistant Integration laden
9. Slicing durchführen
10. Druckjob vorbereiten
11. Druckerstatus/AMS/Materialien erkennen
12. Direct Print / Queue / History / Gallery / CAD / System testen
