# Materialien und Profile

Eine zuverlässige Druckvorbereitung verbindet fünf getrennte Entscheidungen: Drucker, Düse, Filament, Prozess und Plattenoberfläche. Ein passender Druckername allein macht ein fremdes Profil noch nicht geeignet. Düsendurchmesser, Material und Platte beeinflussen die erlaubten beziehungsweise sinnvollen Einstellungen gemeinsam.

## Voraussetzungen

Halte die tatsächlich eingebaute Düse, die Plattenoberfläche und das verwendete Filament fest. Bei mehreren Filamenten müssen Materialkanal und reale Zuführung eindeutig sein. Geräteinformationen und gespeicherte Auftragseinstellungen sind unterschiedliche Quellen; bei unklarer Slotbelegung solltest du keine Materialzuordnung aus einer vermuteten Farbe ableiten.

## Eine Profilkombination auswählen

1. Wähle den Drucker und danach die eingebaute Düse. Berücksichtige Durchmesser und Ausführung.
2. Lege die verwendete Plattenoberfläche fest.
3. Wähle die reale Materialquelle: die betreffenden AMS-Slots oder die externe Einzelspule.
4. Ordne die Filamente den Materialkanälen des Modells zu. Prüfe bei mehreren Farben jeden Kanal einzeln.
5. Wähle einen dazu passenden Prozess. Kontrolliere Schichthöhe, Haftung und Stützen sowie bewusst gesetzte eigene Werte.
6. Speichere das Projekt und prüfe die Kombination vor Slicing erneut.

Das erwartete Ergebnis ist eine vollständige Zuordnung ohne unbekannte Kanäle. Eine externe Spule steht für eine einzelne Zuführung. Mehrere sichtbare Bildschirmfarben erzeugen keine zusätzlichen realen Filamente. Bei einer fehlenden oder mehrdeutigen Zuordnung muss die Ursache vor der weiteren Verarbeitung geklärt werden.

## Eigene Werte und G-Code-Bausteine

Eigene Prozesswerte überschreiben den jeweiligen Profilstandard. Wenn sich ein Ergebnis unerwartet ändert, vergleiche deshalb zuerst Profilwahl und aktive Überschreibungen. Drucker-Start und Drucker-Ende, Filament-Start und Filament-Ende sowie Start- und Endsound haben getrennte Zuständigkeiten. Ein Filamentwechsel darf nicht versehentlich die Soundauswahl erklären müssen.

Cloud-Profile werden im Profilbereich bewusst manuell abgeglichen. Nach einem Abgleich kontrollierst du die ausgewählte Kombination erneut; ein Profilwechsel startet keinen Druck. Bei falschen Vorschlägen erfasse Drucker, Düse, Material und Prozess gemeinsam, damit sich die Zuordnung nachvollziehen lässt. Einzelheiten enthält das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md); den nächsten Schritt erklärt [Bemalung und Mehrfarben](Bemalung.md).
