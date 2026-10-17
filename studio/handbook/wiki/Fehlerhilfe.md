# Fehlerhilfe

| Problem | Zuerst prüfen |
| --- | --- |
| Slicing ist nicht verfügbar | Aktive Platte, Modelle, Profile und Serververbindung |
| Keine Schichtvorschau | Ob ein Slicing-Ergebnis für den ausgewählten Auftrag vorliegt |
| Materialfarbe wirkt falsch | Auftragspalette, Materialkanal und Ansichtsmodus |
| Kamera bleibt stehen | Netzwerk, letzten erfolgreichen Abruf und Gerätefehler |
| MakerWorld liefert keine Daten | Anmeldung, Region und sichtbare Anbieterfehlermeldung |
| Einstellungen wirken unerwartet | Profilstandard und eigene Prozessüberschreibungen |

Ein Fehlerbericht sollte Version, betroffenen Bereich, auslösende Schritte und die genaue Meldung enthalten. Screenshots sind hilfreich, sofern private Dateinamen und Zugangsdaten entfernt wurden.

## Kamera-Bildquelle

Die Kameravorschau lädt Bilder ausschließlich über den Home-Assistant-Kameraproxy für die aktuell ausgewählte Kamera. Externe Bildadressen und Proxyadressen anderer Kameraentitäten werden nicht übernommen. Unterstützt werden JPEG, PNG, WebP, GIF und AVIF; SVG und ungewöhnlich große Einzelbilder werden zurückgewiesen.

Wenn die Kamera nach einem Netzwechsel kein neues Bild anzeigt, zuerst die Verbindung in Home Assistant prüfen und die Schaltfläche **Aktualisieren** verwenden. Bei Rückkehr des Fensters startet die Bildabfrage erneut. Zugriffstokens aus Kameraadressen gehören nicht in öffentliche Fehlerberichte.
