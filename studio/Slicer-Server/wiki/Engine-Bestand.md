# Engine-Bestand und 10-GB-Frage

Rund 10,45 GB einer bestehenden Installation sind überwiegend private Daten,
Laufzustand und Validierungsergebnisse. Der lokale Engine-Ordner umfasst rund
0,78 GB; CuraEngine, PrusaSlicer und Systembibliotheken liegen zusätzlich als
Systempakete außerhalb dieses Ordners.

Die vollständige Aufschlüsselung samt beobachteten Paketständen, Artefakthashes
und offenen Herkunftsprüfungen steht in
[LIVE_ENGINE_INVENTORY.md](../LIVE_ENGINE_INVENTORY.md).

Ein vollständiges Quellrepo ist nicht dasselbe wie ein Rohbackup der aktiven
Installation. Für einen Betriebs-Restore braucht es zusätzlich eine private,
geprüfte Datensicherung und die identifizierten Engine-Artefakte. Keine
Benutzerdaten oder Zugangsdaten in Git übernehmen.
