# Projekterinnerung: Homeassist-MCP läuft nativ

Verbindliche Benutzerkorrektur vom 03.10.2026. Die Migration wurde bereits am 02.10.2026 festgelegt. Am 03.10.2026 um 14:32 CEST direkt erneut bestätigt.

## Aktueller Zugriffsweg

- Für die Home-Assistant-VM den Connector `Homeassist_MCP` verwenden, insbesondere `execute_root_shell` für kontrollierte Host-Diagnose und Verwaltung.
- MCP läuft nativ als systemd-Dienst `admin-mcp.service`, nicht als Home-Assistant-Integration, nicht im SSH-Add-on und nicht im alten `ha-mcp`.
- Host `homeassist`, Benutzer `root`, UID/GID `0/0`, Arbeitsverzeichnis beim Test `/root`.
- Startbefehl: `/usr/bin/node /opt/admin-mcp/source/server.js`.
- Listener `0.0.0.0:8765`; öffentlicher Connector-Endpunkt `https://homeassist.bad-timing.eu/mcp`.
- Keine Zugangstoken, Passwörter oder privaten Schlüssel in Erinnerungen oder GitHub speichern.

## Direkter Testnachweis

Authentifizierter Aufruf über `Homeassist_MCP.execute_root_shell`: erfolgreich, Exit-Code 0. Dienst: `loaded`, `active`, `running`. Prozesszuordnung: `/system.slice/admin-mcp.service`. Alter `ha-mcp.service`: `not-found`, `inactive`, `dead`; kein Listener auf Port 8086.

Lokaler anonymer GET auf `/mcp`: erwartetes HTTP 401 mit Bearer-Challenge. OAuth-Protected-Resource-Metadaten: HTTP 200, Resource `https://homeassist.bad-timing.eu/mcp`, Authorization Server `https://ki.bad-timing.eu/realms/admin-mcp`. Ein zusätzlicher Direktabruf der öffentlichen Adresse von der VM aus scheiterte mit `Connection refused`; die Host-zu-WAF-Rückschleife ist nicht bestätigt. Der authentifizierte Connector-Test selbst war erfolgreich.

## Historische Zugriffswege nicht wiederverwenden

Der alte `HA.ha_*`-Connector und `ha-mcp.service` sind nicht mehr der erforderliche Zugriffsweg. Deren Fehler sind kein Beleg für einen Defekt des nativen MCP oder von Home Assistant. Nicht wiederholt als Voraussetzung testen, nicht neu installieren und nicht reaktivieren. Ältere Erinnerungen zu HA-Webhook-Proxy oder verpflichtendem Add-on-/SSH-Zwischenweg sind hinsichtlich MCP durch diese Benutzerkorrektur ersetzt.

## Puppet ist eine getrennte Komponente

Vorhandenes Add-on `app_0f1cc410_puppet`: Host-Port **5000**, Container-Port **10000**. Diesen bestehenden Dienst für UI-Prüfungen verwenden. Kein Opera-Ersatz und kein zusätzliches Puppeteer installieren oder betreiben.

Eine visuelle Abnahme benötigt HTTP 200, `image/png`, gültige PNG-Signatur und tatsächlich gesichteten passenden Bildinhalt. Ein verbundenes Dashboard allein bestätigt weder Druckvorschau noch Ladebalken oder Maus-/Touch-Bedienung.

## Schutz und offener Projektstand

Diese Erinnerung ändert keine Drucker-, Slicer-, Frontend-, Service- oder OAuth-Konfiguration. V5 bleibt unangetastet. Ist-Prüfung, Backup, Tests, Live-Hashes und Trennung von Slice und Druckstart bleiben verbindlich. Die Vorschau-Reparatur bleibt bis zur visuellen Endabnahme und Veröffentlichung ihres eigenen Code-Deltas offen; diese Erinnerung erklärt sie nicht für abgeschlossen.
