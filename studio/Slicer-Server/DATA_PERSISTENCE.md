# Dateninitialisierung: dauerhafte Verzeichniseintraege

Die Datenablage wird durch den vorhandenen data-init-Dienst einmalig vorbereitet.
API und Worker verlangen einen vollstaendigen ready-Beleg. Bestehende Uploads,
Auftraege und Ausgaben werden bei Wiederholung erhalten.

## Korrigierte Commit-Reihenfolge

1. Den preparing-Beleg schreiben und seinen Stammordner synchronisieren.
2. Alle fest vorgegebenen Datenverzeichnisse mit den vereinbarten Rechten anlegen.
3. Nach Abschluss aller mkdir-Aufrufe die fertigen Verzeichnisinhalte von den
   tiefsten Unterordnern bis zu ihren Eltern synchronisieren, zuletzt den Stamm.
4. Erst jetzt den ready-Beleg als temporaere Datei schreiben und synchronisieren.
5. Den Beleg atomar ersetzen und dessen Stammordner erneut synchronisieren.

Ein frueheres fsync eines Elternverzeichnisses bestaetigt keine spaeter darin
angelegten Unterordner. Genau diese Reihenfolge fehlte in der ersten -Fassung:
data und run wurden bereits vor ihren Kindern synchronisiert. Der neue Ablauf
schliesst diese Luecke, ohne einen vorhandenen Bestand umzuschreiben.

Scheitert eine Verzeichnissynchronisation vor dem ready-Commit, bleibt preparing
erhalten. Ein erneuter Aufruf verweigert die automatische Uebernahme und verlangt
die vorhandene explizite Recovery. Die Sperre bleibt ueber den Vorgang gehalten.
Der kanonische Server und JobControl behalten ihre vorhandenen mkdir-Aufrufe.

## Nachweise und Grenzen

Die neue Regression modelliert, welche Verzeichniseintraege beim jeweiligen
fsync bereits existierten. Sie schlug vor der Korrektur nachweislich fehl.
Nach der Korrektur pruefen drei Faelle die Commit-Voraussetzung, eine injizierte
fehlgeschlagene Elternsynchronisation und den unveraenderten Wiederholungsfall.
