# Architektur

Ultimate 3D Studio in Home Assistant verwaltet Oberflaeche, Galerie, Projekte, Profile und Auftraege. Ein separater Linux-Slicer fuehrt die aufwendige Verarbeitung aus. Der Entwicklungs-PC wird im Betrieb nicht benoetigt.

Docker Compose wird den Slicer installieren. API, Auftragsverarbeitung und Engine bilden eine eigene Auslieferungseinheit ausserhalb des HA-Core-Containers. Die HA-Integration bleibt ueber HACS installierbar und speichert die Slicer-Verbindung serverseitig.

Eine Containergrenze ersetzt keinen Schnittstellenvertrag. API-Kompatibilitaet, Dateiformate, Prozessbesitzer, Abbruch und Datenwiederherstellung werden explizit geprueft. Programmcode, Engine und Benutzerdaten bleiben getrennt. Verbindungspruefung, Slice, Druckerupload und Druckstart sind verschiedene Aktionen.

Der Produktbereich heisst Slicer-Server im bestehenden Repository. Die gemeinsame Release-Basis bleibt main. Der Build sammelt heute noch bestehende kanonische Quelldateien ein; deren vollstaendige Entkopplung ist ein eigener Migrationsschritt.
