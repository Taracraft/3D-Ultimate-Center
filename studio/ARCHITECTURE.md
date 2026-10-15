# Architektur von Ultimate 3D Studio

Ultimate 3D Studio besteht aus einer Home-Assistant-Integration mit Weboberflaeche und einem getrennt installierbaren nativen Linux-Slicer. Home Assistant und der Slicer arbeiten ohne PC; ein Entwicklungsrechner ist keine Laufzeitabhaengigkeit.

## Home Assistant und Slicer

Home Assistant verwaltet Oberflaeche, Galerie, Projekte, Profile und die authentifizierte Auftragskommunikation. Die logische Grenze SlicerClient kapselt die Kommunikation zum nativen Dienst. Die Slicer-Serveradresse und das Slicer-API-Secret werden in der Integration konfiguriert und serverseitig ueber ConfigEntry und OptionsFlow verwaltet. Geheimnisse gehoeren weder in Frontendkonstanten noch in veroeffentlichte Konfigurationen. Verbindungs- und Authentifizierungsfehler werden sichtbar gemeldet.

Der native Slicer wird als eigenstaendiger Linux-Dienst ueber Docker Compose installiert. Der Produktbereich Slicer-Server enthaelt Paketierung, Dokumentation und die versionierten Wiki-Quellen. Der aktuelle Docker-Stand ist ein Quell-Preflight; die Container-Laufzeitabnahme bleibt offen. Die Installation darf administrative Rechte benoetigen; der laufende Dienst verwendet einen eingeschraenkten Benutzer. Programmquellen, Engine-Dateien und veraenderliche Auftragsdaten sind getrennte Bereiche. Eine HA- oder HACS-Installation startet keine Slicer-Installation und keinen Druckauftrag.

## Daten und Bedienung

Galerieobjekte, Projekte, Profile und Auftragsdaten behalten ihre Identitaeten bei Migrationen. Sicherung, Wiederherstellung und Verbraucherabgleich gehoeren zum jeweiligen Migrationsvertrag. Ein API- oder Dateiformatwechsel darf vorhandene Daten nicht stillschweigend verwerfen.

Die Oberflaeche verwendet eine gemeinsame Navigation und einheitliche Zustandsverwaltung. Konfiguration und Berechtigungen werden serverseitig geprueft. Ein erfolgreicher Slice ist keine Druckfreigabe: Slice, Upload und Druckstart sind getrennte Aktionen. Materialzuordnungen muessen vor der Verarbeitung eindeutig und mit den tatsaechlichen Materialkanaelen vereinbar sein.

## Unabhängige historische Altkomponenten

Unabhaengige historische Altkomponenten, insbesondere printer_control_center, sind kein Ziel der Studio-Namensmigration. Bestehende Schnittstellen werden nur mit dokumentiertem Verbraucherabgleich und gepruefter Datenvertraeglichkeit geaendert.

## Quellen und Auslieferung

Technische Produktnamen bleiben versionsneutral. Versionen gehoeren in Paket- und Buildmetadaten. Die HA-Integration und der native Linux-Slicer haben getrennte Pakete und Auslieferungspfade. Gepruefte Quellen, installierte Pakete und geladene Laufzeit sind jeweils eigene Nachweise.

Dieses Dokument beschreibt den oeffentlichen Architekturvertrag. Private Standortkonfigurationen, Arbeitsprotokolle und betriebliche Abnahmen gehoeren nicht zum oeffentlichen Produktpaket.
