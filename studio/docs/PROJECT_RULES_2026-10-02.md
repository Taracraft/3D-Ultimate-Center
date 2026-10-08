# Projektregeln ab 2026-10-02

## V6-Langlaeufer

- Lange V6-Builds, Gates und Deploys in kleine pruefbare Schritte teilen.
- Ein MCP/Connector-Timeout 504 ist nicht automatisch ein Fehlschlag; Statusdateien, Hashes und Artefakte danach direkt pruefen.
- Live-Deploys bleiben nur mit Backup, SHA-256-Pruefung, Rollbackpfad und nach gruenem Gate zulaessig.

## Home Assistant, Tara, Puppet

- Fuer HA-lokale Pruefungen Tara MCP, HA MCP und Puppet-Port 5000 nutzen.
- Nicht auf Opera als Pflichtpfad ausweichen; Browsercache-Probleme separat behandeln.
- Python-Aenderungen an der HA-Custom-Component werden erst nach HA-Core-Neustart oder echtem Komponentenreload aussagekraeftig.
- Puppet-Wrapperfehler `INVALID_ARGUMENT` fuer Dashboardpfade nicht mit einem defekten Puppet-Port verwechseln; direkter Port-5000-Test kann gueltig sein.

## Druck und Sicherheit

- Kein realer Druckstart ohne explizite zweistufige Benutzerfreigabe.
- Read-only Status-, Profil-, Slicer- und Joblistenpruefungen sind erlaubt.
- Ein Bambu-LAN-Reststatus `failed` kann bei kaltem, verbundenem Drucker stale sein. Vor Druckstart sichtbar machen und pruefen, aber nicht automatisch loeschen oder als aktiven Druck interpretieren.

## Profile und Duesen

- Bambu-Cloud-Profilsynchronisation bleibt manuell im Bereich Profile.
- Studio-Filamentauswahl heisst einheitlich `Filamentprofile`; AMS und externe Spule bleiben als Materialquelle auswählbar bzw. automatisch erkennbar.
- A1-Duesenprofile duerfen nicht auf vier Eintraege reduziert werden. Der sichtbare Katalog muss 0,2 mm Edelstahl, 0,4/0,6/0,8 mm Edelstahl und 0,4/0,6/0,8 mm gehaerteter Stahl enthalten, solange die kuratierten Profile diese Varianten fuehren.
- Startsound, Endsound, G-Code 1 und G-Code 2 sind druckprofilgekoppelte Bausteine. Sie muessen im Studio als vier Auswahlfelder und in Profile als vier separat pflegbare Kategorien vorhanden sein, ohne als normales aktives Druckprofil zu erscheinen.

## MakerWorld

- MakerWorld-Detailansicht soll als vollwertiger Clone behandelt werden: Kommentare, Reaktionen, Antworten, alle Druckprofile, alternative/kompatible Profile, Empfehlungen/Vorschlaege und Beschreibungsbilder duerfen nicht ausgeblendet werden.
- HTML/Bilder aus Beschreibungen muessen sicher normalisiert werden, aber sichtbare Nutzinhalte sollen erhalten bleiben.

## Malwerkzeug

- Farben fuer Malen/Zeichnen duerfen nur aus aktuell geladenen AMS- oder externen Spulen-Filamenten nutzbar sein.
- Malobjekte muessen in der Objektliste getrennt unter `Malbereich` erscheinen und wie normale Objekte auswählbar, mehrfach auswählbar und loeschbar sein.
- Pinsel/Stift sollen echte kontinuierliche Striche ermoeglichen; Formen brauchen einen Ziehrahmen wie in Paint/Photoshop. Dreiecksbemalung allein ist nicht ausreichend.
