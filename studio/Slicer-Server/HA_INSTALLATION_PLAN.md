# Integration mit Home Assistant

Ultimate 3D Studio speichert die Slicer-Verbindung in der Home-Assistant-Integration. Der Browser arbeitet über deren API und erhält keine dauerhaften Server-Secrets.

## Einrichtungswege

Die [Supervisor-Verwaltung](SUPERVISOR_APP_SETUP.md) übernimmt die App-Einrichtung über den bestehenden HA-Client. Für einen eigenständigen Linux-Slicer bleibt die externe Verbindung über HTTPS verfügbar. Ein ausdrücklich provisionierter Unix-Host besitzt einen separaten Installationskanal; er ist kein automatischer Ersatz für einen fehlenden Supervisor.

## Konfiguration

Adresse, Authentifizierung und Zertifikatsvertrauen gehören zur jeweiligen Verbindung. Bei einem Serverwechsel dürfen vorherige Cacheeinträge und ausstehende Antworten nicht der neuen Verbindung zugeordnet werden. Galerie, CAD und Profilbearbeitung sollen unabhängig von einer vorübergehenden Slicerstörung bedienbar bleiben.

## Abläufe

Einrichtung, Verbindungsprüfung, Slicing und Druckstart sind getrennte Aktionen. Einstellungen werden erst nach ihrer Prüfung übernommen. Fehlgeschlagene oder unterbrochene Vorgänge müssen ihren bestehenden Zustand erhalten, damit ein weiterer Versuch keine fremden Daten überschreibt.

Der App-Adapter prüft Rechte, Paketidentität und Speicherquittungen. Die vollständige App-Auslieferung mit den benötigten Engines ist noch nicht verfügbar. Angaben zu Paketierung und Laufzeit stehen unter [Entwicklungsstand](RELEASE_STATUS.md).

## Schnittstellen

[Transport](INSTALLER_TRANSPORT.md), [Kopplung](HOST_PAIRING.md), [Speicher](HOST_STORAGE.md) und [Lifecycle](HOST_LIFECYCLE.md) beschreiben die technischen Verträge. Updates und Wiederherstellung müssen Versions- und Datenformate gemeinsam berücksichtigen.
