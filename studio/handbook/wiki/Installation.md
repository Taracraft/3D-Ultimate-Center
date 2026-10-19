# Installation und Einrichtung

Der reguläre Weg besteht aus Home Assistant Container und einem eigenständigen
Docker-Compose-Slicer auf deinem Linuxserver. Der TaraCraft-Assistent heißt
`3D-Ultimate-Studio.sh` und wird mit `sudo bash 3D-Ultimate-Studio.sh` gestartet.

Die [ausführliche Anleitung](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/docs/GUIDED_SETUP.md)
führt durch HACS, die persönliche GitHub-Geräteanmeldung, das automatische
Repository, Drucker/MQTT, Slicer/TLS und das automatisch erzeugte Dashboard.
Die [X1C-Anleitung](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/docs/X1C_SETUP.md)
erklärt außerdem Düsen, Herstellerprofile, AMS-Generationen, externe Spule und
RTSPS-Kamera. Es ist kein zusätzlich eingerichteter MQTT-Broker notwendig.

HACS-Dateien werden installiert; die persönliche HACS-Anmeldung bleibt ein
benutzergesteuerter Schritt. Die Integration wird danach in Einstellungen →
Geräte & Dienste hinzugefügt. Das automatische Studio-Dashboard benötigt kein
manuell kopiertes YAML. Bei einem vorhandenen HA ist nach neuen Integrationsdateien
ein vollständiger Neustart erforderlich.

Vorhandene eigene Sitzungen lassen sich fortsetzen. Für die vollständige
Neuinstallation gibt es eine Bereinigung mit Sicherung und eine ausdrücklich
bestätigte Löschung ohne Backup. Den angezeigten Umfang vor der Bestätigung lesen.
Ein vom Setup neu angelegtes HA verliert beim vollständigen Löschen seine Daten.

Oberfläche, Druckerverbindung und Slicer werden getrennt geprüft. Ein geladenes
Dashboard beweist keine erreichbare Kamera und keine fertige Hardwareabnahme.
Slice, Upload und Druck werden nicht automatisch als Einrichtungstest gestartet.
