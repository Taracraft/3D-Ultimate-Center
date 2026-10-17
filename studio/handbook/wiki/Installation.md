# Installation und Komponenten

Ultimate 3D Studio besteht aus einer Home-Assistant-Integration, der Browseroberfläche und dem getrennten Ultimate Slicer Server. Diese Aufteilung ist wichtig für die Planung: Eine geladene Oberfläche bestätigt noch keinen eingerichteten Slicing-Dienst, und ein vorhandenes Quellrepository ersetzt kein vollständiges Installationspaket.

## Aktueller Paketstand

Die HACS-Quellstruktur mit `hacs.json` und `custom_components/ultimate_3d_studio` ist im Repository vorbereitet. Ein vollständiger veröffentlichter HACS-Download und eine bestätigte frische HACS-Installation stehen weiterhin aus. Auch die Supervisor-App besitzt noch kein freigegebenes vollständiges Engine-Laufzeitpaket. Die folgenden Schritte dienen daher der Orientierung und Vorbereitung; verwende für eine Installation ausschließlich den tatsächlich verfügbaren, geprüften Paketstand.

## Komponenten vor der Einrichtung zuordnen

1. Prüfe die Version von Home Assistant und den gewählten Installationsweg.
2. Lies die Einrichtung im [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md). Identifiziere Integration, Frontend-Ressourcen und vorhandene Konfiguration.
3. Entscheide, welcher unterstützte Slicer-Weg vorgesehen ist: externer Server oder Supervisor-Verwaltung. Beides sind getrennte Wege.
4. Für einen externen Server halte Adresse, API-Secret und das passende TLS-Vertrauen bereit.
5. Sichere eine vorhandene Konfiguration und Nutzdaten vor Änderungen. Plane Update und Rückweg passend zum verwendeten Paket.

Das erwartete Ergebnis dieser Vorbereitung ist ein eindeutiger Komponentenplan mit passender Versionszuordnung. Ein vorhandenes laufendes System sollte nicht durch ungeprüfte Dateien oder einen parallel aufgebauten Mischbetrieb verändert werden.

## Verbindung und erste Kontrolle

Trage die externe Slicer-Verbindung in den Integrationsoptionen ein und prüfe die Rückmeldung. Das Secret gehört in die dafür vorgesehene Konfiguration. Stelle es weder in Screenshots noch in öffentliche Fehlerberichte. Kontrolliere getrennt, ob die Oberfläche lädt, der Server erreichbar ist und die benötigten Engines sowie Profile tatsächlich verfügbar sind.

Bei einer fehlgeschlagenen Verbindung prüfe URL, Zertifikatsname, Zertifikatsvertrauen und Zugangsdaten. Bleibt ein Einrichtungszustand unklar, gleiche den Bestand ab, bevor du einen weiteren Installationsversuch unternimmst. Die [Slicer-Dokumentation](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/main/Slicer-Server/HANDBUCH.md) erklärt Laufzeit, Datenhaltung und Betrieb. Prüfe die tatsächlich verfügbaren Pakete und die benötigten Systemvoraussetzungen vor einer Änderung.
