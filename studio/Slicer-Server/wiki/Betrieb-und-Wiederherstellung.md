# Betrieb und Wiederherstellung

Vor Updates werden Image-Digest, Konfiguration und Datenstand erfasst. Auftraege werden kontrolliert angehalten; aktive Jobs und freigegebene Warteschlangeneintraege duerfen nicht unbeachtet bleiben. Eine konsistente Sicherung wird zurueckgelesen, bevor eine Migration beginnt.

Code-Rollback und Daten-Restore sind verschiedene Schritte. Ein vorheriges Image kann ein neues Datenschema unter Umstaenden nicht lesen. Releasehinweise muessen deshalb kompatible Datenstaende und die notwendige Wiederherstellungsreihenfolge nennen.

Ein Containerneustart darf keine verwaisten Prozesse und keine scheinbar fertigen Teil-G-Codes hinterlassen. Slicing-Zustaende ohne bestaetigten Besitzer werden als Wiederherstellungsfall behandelt. Der Worker darf weder fremde Prozesse beenden noch einen vorhandenen Auftrag stillschweigend erneut slicen.

Das Entfernen eines Containers entfernt nicht automatisch Benutzerdaten. Datenloeschung bleibt eine eigene bewusste Aktion. Geheimnisse und private Modelle machen auch Backups zu schutzbeduerftigen Dateien.

Der ausfuehrliche Betriebsvertrag steht in OPERATIONS.md. Die echte Docker-Upgrade-/Restore-Abnahme ist noch offen.
