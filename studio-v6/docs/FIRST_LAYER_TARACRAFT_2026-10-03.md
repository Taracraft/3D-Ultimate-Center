# TaraCraft First-Layer-Test – 03.10.2026

## Umsetzung und Bedienung

Im 3D-Studio unter Einfügen den First-Layer-Test neu erzeugen. Bereits vorhandene Testobjekte werden nicht nachträglich verändert. Bei belegter Platte erhält der Test eine neue Platte, damit vorhandene Modelle erhalten bleiben.

- Fläche: gesamtes rechteckiges Bett mit 5 mm Abstand zum Rand; beim A1 246 × 246 mm.
- Großes mittiges T mit drei separat geschlossenen Konturbändern; vier schmale freie T-Nuten machen die Konturen sichtbar.
- Eine physische Schicht. Bei 0,4-mm-Düse: 0,28 mm Schichthöhe und 0,60 mm Linienbreite.
- Unterstützte Düsen: 0,2 / 0,4 / 0,6 / 0,8 mm. Höhe 70 % und Linienbreite 150 % des Durchmessers, innerhalb des bestehenden Düsenvertrags.
- Füllrichtung 135°: in der Draufsicht von oben links nach unten rechts. Erste Schicht 25 mm/s, Flächenfüllung 30 mm/s.
- Ein Bodenlayer, kein Decklayer, kein Support/Brim/Raft, keine variablen Layerbereiche.
- Sparse-Infill 0 %: Die Bodenschicht füllt die Fläche vollständig. 100 % Sparse-Infill ist mit dem vorhandenen nativen Gitterprofil ungültig.
- Materialtemperaturen und Filamentauswahl folgen weiterhin dem ausgewählten Profil. Die First-Layer-Werte werden als bearbeitbare Platten-Overrides gespeichert.
- Neue validierte Editor-/API-/Workerfelder: erste Linienbreite, Füllrichtung und erste Füllgeschwindigkeit.

## Fachlicher Vergleich

Eine richtige erste Schicht zeigt gleichmäßig leicht abgeflachte, miteinander verbundene Bahnen ohne offene Zwischenräume, aufgeworfene Ränder oder herausgedrückte Grate. Größere Schichthöhe ersetzt keine korrekte Bett-/Z-Kalibrierung. Die gewählten 0,28/0,60 mm sind die TaraCraft-Testwerte für die vorhandene 0,4-mm-Düse, keine universelle Hersteller-Vorgabe.

Quellen:
- https://help.prusa3d.com/article/first-layer-calibration-i3_112364
- https://help.prusa3d.com/article/layers-and-perimeters_1748
- https://github.com/bambulab/BambuStudio/blob/master/src/libslic3r/PrintConfig.cpp

## Nachweise und Grenzen

Gesamtgate am kanonischen Tara PC erfolgreich, beendet 03.10.2026 18:21:33 +02:00: Source-Policy, TypeScript, 167 Frontendtests, beide Produktionsbuilds, 1285 Python-/Worker-Tests plus 3 Subtests und HA-Compile-Prüfung.

Die Geometrieprüfungen bestätigen geschlossene, konsistent orientierte Meshes, Bettgrenzen, Volumen und exakt fünf zusammenhängende Bereiche: Außenfläche, drei Konturen und inneres T.

Isolierter nativer Bambu-Studio-2.7.1-Slice auf der VM, ohne Jobanlage oder Druckerzugriff: genau ein Layer, Z 0,28 mm, Linienbreite 0,60 mm. Die langen extrudierten Bodenbahnen liegen ausschließlich bei 135° (100426 mm Gesamtbahnlänge). Das geprüfte Profil verwendet monotonic als Bodenmuster. Andere benutzerdefinierte Bodenmuster sind durch diesen Nachweis nicht abgedeckt. Slicer-Schätzung: rund 20,09 g und 1 h 8 min inklusive Startablauf; kein physischer Drucknachweis.

HA-Quellkopie, aktive Komponente, Frontend und separater Worker nach grünem Gate mit Same-Day-Backup und atomarem Dateitausch aktualisiert. Alle betroffenen Live-SHAs geprüft. HA-Konfigurationsprüfung und anschließend ha core restart erfolgreich. Native MCP-, Slicer- und Dispatch-Timer-Dienste aktiv; keine V6-Fehler im geprüften Neustart-Log.

JavaScript SHA-256: 2a25080cf03dbe9b4573bfcabfc15e1d48e32e37eca1ef36e8f1d0e6a80fadb8
Worker-Materializer SHA-256: a2a6499f9019bb051eaa89f0f57328dfd4066d6a27bb8249d84c5ae095a2121c
HA-Backup: /var/lib/homeassistant/homeassistant/backups/20261003T182753-taracraft-first-layer

Puppet über Host-Port 5000: HTTP 200, image/png, PNG-Signatur geprüft und Bild gesichtet. Verbundenes 3D-Studio sichtbar; SHA-256 b3477cf9efa6cfc9350e8116263fc719b1a0d44baa70fa2c2f13142525a537eb. Dieser Screenshot zeigt noch kein neu erzeugtes T und ersetzt keine interaktive Endabnahme. Keine Druckerübertragung und kein Druckstart.

## Verbindliche Zugriffserinnerung

Die Lösung vom 01./02.10. bleibt maßgeblich:
- Kanonische PC-Quelle: F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Ultimate Studio (kein zusätzliches v6-Unterverzeichnis).
- PC-Dienst JARVISPCConnector. Alte doppelte Aufgabe JARVIS ChatGPT PC MCP LAN Server wurde bereits deaktiviert. Nicht reaktivieren.
- Der PC-Tunnel jarvis-pc-tunnel.service läuft auf dem Raspberry, nicht auf der Home-Assistant-VM.
- Am 03.10. war TCP 8767 erreichbar, aber der Connector antwortete nicht korrekt. Kontrollierter Neustart von JARVISPCConnector stellte den Dateizugriff wieder her. Keine Tunnel-/OAuth-/HA-MCP-Neuinstallation.
- Ein langer v6_prepare_bundle-Aufruf kann 504 liefern, während das Gate weiterläuft. Kein zweiter Build oder Dienstneustart in dieser Situation. .test-results/connector-v6-quality-gate.json und Artefakt-SHAs entscheiden.
- Homeassist_MCP läuft nativ als admin-mcp.service. Alten HA-Add-on-MCP nicht als Voraussetzung testen.
- Puppet ist getrennt: Host-Port 5000, Container 10000, bestehender Split-DNS-Timer. Kein Opera-Ersatz und keine neue Puppeteer-Installation.
- Öffentliches Repository: Taracraft/3D-Ultimate-Center. PC zuerst, danach HA und geprüfter Git-Abgleich.

## Veröffentlichungsstatus

GitHub ist noch offen: Der Schreibaufruf create_blob wurde mit „user rejected MCP tool call“ abgewiesen. Kein Commit/Ref-Update, kein alternativer Schreibweg. Veröffentlichung benötigt eine Freigabe des GitHub-Schreibzugriffs. Öffentliche Basis: d490faad38a18b64e9c6f6a4548a23a4662b55b3.

Vorhandene PC/HA-Abweichungen in network_plugin/__init__.py, network_plugin/commands.py und slicer_backend_router.py wurden bei diesem First-Layer-Schritt nicht überschrieben. Ein vollständiger Gesamt-Repository-Gleichstand wird nicht behauptet.
