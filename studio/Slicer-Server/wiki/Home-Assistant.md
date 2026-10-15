# Home Assistant verbinden

Der Einstellungsort ist Einstellungen -> Geraete & Dienste -> Ultimate 3D Studio -> Konfigurieren. Dort gehoeren Slicer-Serveradresse und Slicer-API-Secret hin. HACS ist fuer Installation und Updates der Integration zustaendig.

Fuer die Verbindung zu einem entfernten Server wird eine HTTPS-Adresse benoetigt. Zertifikatsname und Hostname muessen passen, die Zertifikatskette muss auf dem HA-Host vertrauenswuerdig sein. Zertifikatspruefung nicht als Fehlerumgehung deaktivieren. Ein API-Secret ist kein Ersatz fuer TLS.

Der Verbindungstest muss Authentifizierung, Erreichbarkeit und Protokollkompatibilitaet unterscheiden. Er darf keine Auftraege freigeben oder Druckeraktionen ausloesen. Das Secret wird nicht in Browserdaten oder Diagnoseexporte uebernommen.

Bei Serverwechsel oder Secret-Rotation werden zuerst die neue Konfiguration und der Rueckweg gesichert. Danach wird die Verbindung geprueft. Die vorhandenen Galerie-/Projekt-/Profildaten bleiben erhalten. Ein nicht erreichbarer Slicer darf unabhaengige Studio-Funktionen nicht unbenutzbar machen.

Die Docker-Verbindung wird erst nach dem echten Container-/TLS-Test als abgenommen dokumentiert.
