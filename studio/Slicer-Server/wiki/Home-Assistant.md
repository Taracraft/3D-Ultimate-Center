# Home Assistant verbinden

Ultimate 3D Studio wird als Integration in Home Assistant eingerichtet. Für den Slicer stehen in den Optionen zwei getrennte Wege zur Verfügung: die Verbindung zu einem externen Server und die Supervisor-Verwaltung. Wähle den Weg passend zur tatsächlich verfügbaren Installation. Ein sichtbarer Einrichtungsweg belegt noch kein veröffentlichtes Runtime-Paket.

## Voraussetzungen

Ein externer Slicer benötigt seine Adresse, das passende API-Secret und ein TLS-Zertifikat, dem Home Assistant vertraut. Die Zugangsdaten bleiben in Home Assistant; die Browseroberfläche erhält sie nicht. Zusätzlich müssen auf dem Server die benötigte Engine, passende Profile und die Laufzeitkonfiguration bereitstehen.

Die Supervisor-Verwaltung prüft vorhandene Pakete sowie einen gegebenenfalls unterbrochenen Einrichtungszustand. Eine freigegebene App-Paketversion ist derzeit noch nicht hinterlegt. Daraus ergibt sich kein fertiger Installationsweg über die Supervisor-App. Die Einzelheiten stehen unter [Supervisor-Einrichtung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/SUPERVISOR_APP_SETUP.md).

## Verbindung einrichten und prüfen

1. Prüfe den [Entwicklungsstand](Entwicklungsstand.md) und die tatsächlich verfügbare Serverinstallation.
2. Wähle in den Integrationsoptionen den zutreffenden Verbindungsweg.
3. Hinterlege für den externen Server die vorgesehenen Verbindungsdaten und stelle das TLS-Vertrauen her.
4. Prüfe die gemeldete Verbindung und anschließend, ob der Server die benötigte Engine bereitstellt.
5. Bewerte einen tatsächlichen Slicing-Auftrag getrennt vom erfolgreichen Verbindungsaufbau.

## Erwartetes Ergebnis

Die Verbindung ist nachvollziehbar, wenn Home Assistant den vorgesehenen Server mit gültiger Authentifizierung und TLS-Vertrauen anspricht. Eine erfolgreiche Verbindung bestätigt noch keine vollständige Auftragsverarbeitung. Erst der passende Engine-Bestand und die Verarbeitung mit geeigneten Profilen ergänzen diesen Nachweis.

## Fehler und unterbrochene Einrichtung

Bei Verbindungsfehlern kontrolliere zuerst Serveradresse und Zertifikatsnamen, danach Zertifikatsvertrauen und Secret. Ein eingeschränkter Serverzustand kann trotz erreichbarer API auf fehlende Engines hinweisen. Bei einem unterbrochenen Supervisor-Vorgang muss der vorhandene Zustand abgeglichen werden. Ein Journal zu löschen und blind neu zu beginnen ersetzt diesen Abgleich nicht.

Für die API-Anbindung gilt die [API-Dokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/API.md); für vollständige Bedienabläufe das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md). Änderungen an bestehenden Installationen und produktive Freigaben bleiben eigene Entscheidungen. Eine eingerichtete Verbindung erteilt keine Druckfreigabe.
