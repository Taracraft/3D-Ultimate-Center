# Vorschau und Analyse

Die Vorschau beantwortet zwei unterschiedliche Fragen: Wie ist das Modell aufgebaut, und welche Bahnen hat der Slicer daraus berechnet? Die Modellansicht zeigt Geometrie und Materialzuordnung. Schicht- und Toolpath-Ansichten benötigen das Ergebnis eines konkreten Slicing-Auftrags.

## Voraussetzungen

Wähle den passenden Auftrag und die richtige Platte. Für eine Bahnenprüfung muss ein Slicing-Ergebnis vorhanden sein. Halte die gewählten Drucker-, Düsen-, Filament- und Prozessdaten bereit, damit eine auffällige Bahn oder Farbe der richtigen Konfiguration zugeordnet werden kann.

## Ein Ergebnis systematisch prüfen

1. Kontrolliere Auftrag und Platte. Vergleiche die sichtbaren Modelle mit deinem vorbereiteten Projekt.
2. Beginne bei der ersten Schicht. Prüfe Auflage, Ausdehnung und die erkennbaren Anfangsbereiche.
3. Gehe schrittweise durch die Höhenbereiche. Achte auf unerwartete Lücken, Stützen und deutliche Formänderungen.
4. Untersuche Materialwechsel und die zugehörigen Kanäle. Vergleiche die Auftragspalette mit deiner bewussten Filamentauswahl.
5. Nutze passende Diagnosefilter für Drucktypen oder Stützen. Lies vorhandene Warnungen, bevor du weitergehst.

Vergleiche eine gewählte Schicht bei Bedarf mit dem Modellaufbau unter **Vorbereiten**, um ihre Lage einzuordnen. Eine transparente Darstellung der verbleibenden Gesamtgeometrie ist für den aktuellen Stand hier nicht als geprüft zugesagt. Für Detailprüfungen bleibt der tatsächlich sichtbare Bahnenbereich maßgeblich. Eine räumliche Darstellung allein bestätigt keine passende Slicing-Konfiguration.

## Farben und typische Irrtümer

Filamentfarben gehören zum jeweiligen Auftrag. Eine später geänderte AMS-Belegung darf nicht als neue Farbquelle für ein älteres Ergebnis interpretiert werden. Prüfe bei einer auffälligen Farbe zuerst Auftrag, Materialkanal und Ansichtsmodus. Unbekannte Kanäle benötigen eine geklärte Zuordnung; eine angenommene Ersatzfarbe löst das fachliche Problem nicht.

Fehlt eine Schichtansicht, kontrolliere zunächst, ob der ausgewählte Auftrag überhaupt ein verwertbares Slicing-Ergebnis besitzt. Ein importiertes Modell ist dafür noch kein Nachweis. Bei einem falschen Ergebnis gehe zur entsprechenden Profil- oder Materialentscheidung zurück und sichere den bisherigen Stand für den Vergleich.

Das erwartete Ergebnis ist eine bewusst geprüfte Druckvorbereitung mit nachvollziehbaren Bahnen und Materialien. Die Vorschau garantiert keine physische Druckqualität und startet keinen Druck. Weitere Erläuterungen enthält das [Handbuch](https://github.com/Taracraft/3D-Ultimate-Center/blob/main/studio/README.md); bei fehlenden Daten hilft die [Fehlerhilfe](Fehlerhilfe.md).
