# Der Funktionskatalog

[Handbuch](../README.md) · [CAD-Beispiele](CAD_EXAMPLES.md) · [Slicer-Dokumentation](../Slicer-Server/README.md)

Hier steht nicht nur „CAD“ oder „Mehrfarben“, sondern welche Arbeitsschritte
dahinterliegen. **Vorhanden** bedeutet im aktuellen Quellstand implementiert;
es ist keine pauschale Live-, Hardware- oder Produktivabnahme. Die Bedienung
steht im Handbuch, die technischen Einstiegspunkte am Ende jeder Gruppe.

Die Originalaufnahmen zeigen eine bestehende Installation. Nur die ausdrücklich
genannten Beispielaktionen wurden für die Bilder tatsächlich bedient. Keine
neuen Slices oder Drucke wurden für diese Dokumentation ausgeführt.

## 1. Modelle öffnen, Projekte sichern

| Funktion | Was du damit machst | Wichtige Grenze |
| --- | --- | --- |
| Lokales STL öffnen | Geometrie vom eigenen Rechner auf die aktive Platte laden | Material und Prozess anschließend prüfen |
| Lokales 3MF öffnen | Unterstützte Geometrie, Objektstruktur und vorhandene Zuordnungen importieren | Nicht jede beliebige Herstellererweiterung ist automatisch unterstützt |
| Aus Galerie öffnen | Eine vorhandene Bibliotheksdatei ins Studio übernehmen | Bibliotheksdatei und bearbeitete Szene sind getrennt |
| Von SD-Karte öffnen | Geeignete gespeicherte Dateien über den angebundenen Druckerzugang auswählen | Erfordert unterstützte Verbindung und Zugriffsrechte |
| Aus MakerWorld öffnen | Modell-/Druckprofil-Auswahl gezielt übernehmen | Anbieterantwort und Zugriffsberechtigung bestimmen die Verfügbarkeit |
| Objekt importieren | Weitere Geometrie zur bestehenden Bearbeitung hinzufügen | Bestehende Materialzuordnungen danach kontrollieren |
| Objekt exportieren | Bearbeitete Modellgeometrie separat ausgeben | Kein automatisch erzeugter G-Code |
| Projekt speichern | Studio-Arbeitsstand auf HA dauerhaft ablegen | Speichern startet keinen Slice und keinen Druck |
| Projekt öffnen | Gespeicherten Studio-Arbeitsstand wieder laden | Vor dem Ersetzen eigenen aktuellen Stand sichern |

Quellen: [Studio-Arbeitsbereich](../frontend/studio-mega-workspace-v2.ts),
[Projekt-API](../frontend/studio-project-api.ts),
[Export](../frontend/studio-export-service.ts).

## 2. CAD und Geometrie

| Funktion | Bedienung und Nutzen | Wichtige Grenze |
| --- | --- | --- |
| Auswahl | Objekt in Liste oder Arbeitsfläche anklicken | Modell und Malbereich sind unterschiedliche Ebenen |
| Mehrfachauswahl | Strg/Shift+Klick für mehrere Objekte | Vor Sammelaktionen die Auswahl prüfen |
| Verschieben | Frei oder auf X/Y/Z eingeschränkt positionieren | Danach Bettgrenzen und Auflage kontrollieren |
| Drehen | Orientierung des Modells ändern | Im aktiven Malmodus gesperrt |
| Skalieren | Größe über die vorhandenen Transformationsfelder ändern | Geänderte Abmessungen prüfen |
| Spiegeln | An X-, Y- oder Z-Achse spiegeln | Material-/Bemalungszuordnung nachprüfen |
| Zentrieren | Auswahl auf der Platte mittig ausrichten | Ersetzt keine Kollisionsprüfung |
| Auf Druckbett | Unterseite auf die Bettebene setzen | Druckbarkeit der Auflage bleibt zu beurteilen |
| Flach legen | Geeignete flache Orientierung herstellen | Nicht jede Geometrie hat eine eindeutige beste Auflage |
| Automatisch anordnen | Mehrere Objekte auf der aktiven Platte verteilen | Abstände, Bettrand und spätere Stützen kontrollieren |
| Duplizieren | Weitere Instanz der Auswahl erzeugen | Zusätzlicher Platzbedarf |
| Kopieren/Ausschneiden/Einfügen | Szenenelemente im Bearbeitungsablauf übertragen | Kein Ersatz für dauerhafte Projektsicherung |
| Rückgängig/Wiederholen | Bearbeitungsschritte zurücknehmen oder wiederholen | Kein vollständiges Backup-System |
| Messen | Auswahl und Dimensionen untersuchen | Keine Hardwarekalibrierung |
| Geometrisch teilen | Ein ausgewähltes Modell in unterstützte Teile zerlegen | Ergebnis und Materialbereiche kontrollieren |
| Mesh prüfen/reparieren | Unterstützte Geometrieprobleme erkennen und bearbeiten | Keine Garantie, jedes fehlerhafte Mesh zu heilen |
| Löschen | Bewusst ausgewählte Elemente entfernen | Original oder Projektstand vorher sichern |

Quellen: [Werkzeugoberfläche](../frontend/studio-mega-ui-v2.ts),
[Mesh-Reparatur](../frontend/studio-mesh-repair.ts),
[Teilen](../frontend/studio-mesh-split.ts).

## 3. Eigene Grundkörper und Druckplatten

| Funktion | Ergebnis | Wichtige Grenze |
| --- | --- | --- |
| Würfel | Direkt bearbeitbarer Grundkörper | In den Originalbildern tatsächlich erzeugt |
| Zylinder | Runde Basisgeometrie | In den Originalbildern tatsächlich erzeugt |
| Kugel | Kugelförmige Geometrie | Geometrieerzeugung ist kein Drucknachweis |
| Kegel | Spitz zulaufender Grundkörper | In den Originalbildern tatsächlich erzeugt |
| Ring | Torus-Geometrie | In den Originalbildern tatsächlich erzeugt |
| Platte | Flacher Grundkörper | Nicht mit der Maschinen-Druckplatte verwechseln |
| First-Layer-Testgeometrie | Düsenabhängig vorbereitete Testgeometrie und zugehörige Prozesswerte | Kein automatisch gestarteter Kalibrierdruck |
| Neue Druckplatte | Zusätzlicher getrennt auswählbarer Plattenaufbau | Aktive Platte vor Aktionen prüfen |
| Plattenwechsel | Zwischen Objekten und Einstellungen verschiedener Platten arbeiten | Vorschau und Auftrag bleiben plattenbezogen |
| Platte entfernen | Eine nicht mehr benötigte Platte entfernen | Enthaltene Objekte vorher sichern |
| Alles einpassen | Kamera wieder auf den Plattenaufbau ausrichten | Bei Bedarf anschließend mit Mausrad zoomen |
| Leisten einklappen | Mehr Platz für CAD-Fläche schaffen | Verändert nicht die Modellgeometrie |

Quellen: [Grundkörper](../frontend/primitive-geometry.ts),
[Druckplatten](../frontend/studio-build-plates.ts),
[WebGL-Ansicht](../frontend/webgl-studio-viewport.ts).

## 4. Profile, Material und Prozess

| Funktion | Was getrennt gewählt oder angezeigt wird | Wichtige Grenze |
| --- | --- | --- |
| Druckerprofil | Maschinenmodell und Druckraum | Nicht jede Hardwarefamilie ist real abgenommen |
| Düsenwahl | Durchmesser und Düsenmaterial | Nicht automatisch aus einem Filamentprofil ableiten |
| Filamentprofil | Hersteller, Material, Variante und Eigenschaften | Muss zur Maschine und Düse passen |
| Druckprofil | Qualität, Schichthöhe und Prozessparameter | Eigene Überschreibungen gesondert prüfen |
| Druckplattenprofil | Oberfläche und zugehörige Plattenwerte | Oberfläche und Temperatur müssen zum Material passen |
| Start-/Endsound | Getrennte Bausteine | Ausführungsrelevante Einstellungen, nicht nur Dekoration |
| G-Code 1/2 | Maschinen-Start-/Endbausteine | Nur bewusst und maschinengerecht ändern |
| Cloud synchronisieren | Bewusste manuelle Profilübernahme | Anmeldung und Anbieterantwort erforderlich |
| AMS/Materialsystem | Konfigurierten Typ und erkannte Hardware unterscheiden | Auswahl ist kein Nachweis tatsächlich belegter Slots |
| Externe Spule | Separate Materialquelle | Eine externe Spule bedeutet keinen Mehrfarbendruck |
| Slot-Belegung | Tatsächlich gemeldete Fächer und Materialdaten | Fehlende Telemetrie wird nicht erfunden |
| Betthaftung | Aus, Brim oder Raft vorbereiten | Resultat erst im tatsächlichen Slice beurteilen |
| Stützen | Unterstützte Stützoptionen auswählen | Modell und Orientierung bestimmen den Bedarf |
| Variable Schichten | Höhenbereiche und Schichtwerte pflegen | Düsen-/Profilgrenzen beachten |
| Prozessüberschreibungen | Explizite Werte statt Profilstandard setzen | Leeres Feld ist kein eigener Wert |

Quellen: [Profiloberfläche](../frontend/studio-profile-ui.ts),
[Prozesspanel](../frontend/studio-process-options-panel.ts),
[Prozesszustand](../frontend/studio-process-options-state.ts).

## 5. Bemalung und Mehrfarben

| Funktion | Was du machst | Wichtige Grenze |
| --- | --- | --- |
| Materialkanal wählen | Druckfilament für Malbereiche bestimmen | Nur tatsächlich vorhandene geeignete Kanäle |
| Pinsel | Flächen frei bemalen | Größe und ausgewähltes Modell prüfen |
| Stift | Feinere freie Striche setzen | Zuordnung folgt dem Materialkanal |
| Radierer | Bemalung lokal entfernen | Modellgeometrie und Farbe sind getrennt |
| Rechteck/Kreis | Flächen per Klick-Ziehen auswählen | Ergebnis auf der Modelloberfläche prüfen |
| Linie | Strich zwischen Start und Ende aufziehen | Nicht nur die Bildschirmprojektion beurteilen |
| Text | Text, Schriftgröße und Platzierung wählen | Oberfläche und exportierte Zuordnung kontrollieren |
| Malbereiche verwalten | Gemalte Bereiche separat von Modellen auswählen | Vor Löschen die Ebene prüfen |
| Malmodus-Sperre | Konkurrierende Transformationen verhindern | Zum Bewegen/Drehen zuerst Malen verlassen |
| Mehrfarbenexport | Flächen-/Materialzuordnungen im unterstützten Export erhalten | Sichtbare Farbe allein beweist keinen ausführbaren Auftrag |

Quellen: [Malwerkzeuge](../frontend/studio-paint-ui.ts),
[Malzustand](../frontend/studio-paint-state.ts),
[Bemalter Export](../frontend/studio-painted-export.ts).

## 6. Vorschau, Bibliothek und Betriebsübersicht

| Funktion | Nutzen | Wichtige Grenze |
| --- | --- | --- |
| Vorbereiten | Geometrie und Plattenaufbau beurteilen | Noch keine Druckbahnen |
| Farben | Materialzuordnung und Bemalung betrachten | Keine Simulation eines fertigen Slices |
| Vorschau | Vorhandene geslicte Daten und Toolpaths ansehen | Benötigt ein tatsächliches Ergebnis |
| Schichtauswahl | Einzelne Schichten im räumlichen Zusammenhang prüfen | Filter können Bahnen ausblenden |
| Auftragsgebundene Farben | Filamentfarben des gespeicherten Jobs verwenden | Nicht nachträglich durch aktuelle AMS-Belegung ersetzen |
| Diagnosefilter | Merkmale und Stützen getrennt hervorheben | Diagnosefarben sind keine neue Materialzuordnung |
| Galerie und Ordner | Modelle geordnet verwalten und finden | Private Inhalte bleiben privat |
| Upload/ZIP/Duplikatprüfung | Modelle in die Bibliothek aufnehmen und Doppelungen erkennen | Grenzen und Dateiprüfungen beachten |
| MakerWorld | Modelle und Druckprofile ansehen und gezielt übernehmen | Kein unkontrollierter automatischer Download beliebiger Inhalte |
| Aufgaben | Warteschlange und Auftragszustände überblicken | Verwaltungsaktion ist nicht gleich Druckstart |
| Verlauf | Frühere Aufträge und Ergebnisse nachvollziehen | Aufträge enthalten unter Umständen private Dateinamen |
| Steuerzentrale | Druckerstatus, Fortschritt, Störungen und Kamera überblicken | Abhängig von tatsächlicher Verbindung und Berechtigung |
| System | Verbindungs- und Diagnoseinformationen sehen | Sensible Diagnosewerte nicht öffentlich teilen |
| Slicing-Server | Getrennten Dienstzustand und verfügbare Engines erkennen | Health 200 allein ist keine Slicing-Abnahme |

Quellen: [Arbeitsbereich](../frontend/studio-mega-workspace-v2.ts),
[MakerWorld-Ansicht](../frontend/makerworld-workspace-studio.ts),
[Aufgabenansicht](../frontend/jobs-workspaces-studio.ts).

## Was noch kein fertiger Produktivablauf ist

Die neue unabhängige Linux-/Docker-Erstinstallation, vollständige freigegebene
Engine-Lieferkette, verifizierte Cross-Host-TLS-Verbindung, echtes Upgrade und
Restore, HACS-Neuinstallation und privater Pilot brauchen ihre eigenen
Abnahmen. Das Repo dokumentiert diese Grenzen, statt sie aus einem grünen
Quelltest oder einer sichtbaren Schaltfläche abzuleiten.
