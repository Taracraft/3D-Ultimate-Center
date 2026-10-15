# Fehlerdiagnose

| Meldung / Symptom | Bedeutung | Naechster Schritt |
|---|---|---|
| source_digest_mismatch | Quelle und bestehendes Pruefmanifest weichen ab | Autoritativen Quellstand und Aenderung pruefen |
| output_already_exists | Ziel ist bereits belegt | Neuen privaten Kontext waehlen; nichts blind loeschen |
| unexpected_context_file | Kontext enthaelt nicht erlaubte Dateien | Fremddatei ermitteln; keine Secrets verpacken |
| source_integrity=failed | Paketpruefung ist fehlgeschlagen | Kontext neu aus geprueften Quellen erstellen |
| container_deploy_ready=false | Docker-Betrieb noch nicht freigegeben | Offene Abnahmen bearbeiten; Flag nicht manuell umstellen |
| HTTP 401 | Authentifizierung abgelehnt | Gespeichertes Secret serverseitig pruefen |
| TLS-/Namensfehler | Zertifikat und Ziel passen nicht oder CA fehlt | Zertifikat und Vertrauenskette korrigieren |
| Verwaister slicing-Zustand | Besitzer/Wiederanlauf ungeklaert | Daten sichern und kontrolliert wiederherstellen |

Ein Fehlerbericht nennt Softwareversion, Image-Digest, Architektur, Zeitpunkt und bereinigten Fehlercode. Keine Zugangsdaten, privaten Modelle oder vollstaendigen Konfigurationsdateien veroeffentlichen. Ein erfolgreicher HTTP-Aufruf allein belegt weder Slicing-Funktion noch sicheren Betrieb.
