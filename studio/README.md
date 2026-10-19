# Ultimate 3D Studio · Handbuch

[X1 Carbon: Einrichtung, AMS, externe Spule und Kamera](docs/X1C_SETUP.md).

> **Aktuelle Einrichtung:** Home Assistant und Slicer laufen in getrennten Docker-Containern; dein Linuxserver bleibt selbst administrierbar. Mit der separat bereitgestellten `3D-Ultimate-Studio.sh` führt die [ausführliche Anleitung](Slicer-Server/INSTALLATION.md) durch die weitgehend automatisierte HACS-/MQTT-/Slicer-/Dashboard-Einrichtung. Die folgenden älteren manuellen Wege bleiben Alternativen.

**Dein Modell. Deine Materialien. Deine Druckplatte.**

Ultimate 3D Studio bringt Modellbibliothek, CAD-Bearbeitung, Materialzuordnung und Druckvorbereitung in Home Assistant zusammen. Dieses Handbuch begleitet dich vom ersten Grundkörper bis zur Prüfung eines vorhandenen Slicer-Ergebnisses. Du kannst direkt mit dem [ersten Projekt](#erstes-projekt) beginnen oder über die [Arbeitsbereiche](#arbeitsbereiche) eine bestimmte Aufgabe nachschlagen.

[Projektstartseite](../README.md) · [Funktionskatalog](handbook/FEATURES.md) · [CAD-Beispiele](handbook/CAD_EXAMPLES.md) · [Slicer-Dokumentation](Slicer-Server/README.md)

![Vier synthetische Grundkörper auf der Studio-Druckplatte](handbook/images/cad-plate.png)

*Originalaufnahme einer bestehenden Installation. Herkunft und Bildhinweise stehen in [SOURCE_NOTICES.md](../SOURCE_NOTICES.md). Die Aufnahme dokumentiert die Oberfläche, nicht die Abnahme des aktuellen Quellstands.*

**Aktueller Stand:** Die geprüfte Matrix umfasst 77 Funktionen und 41 Zusatzanforderungen. Viele vollständige Funktionsabnahmen sind offen. Beschriebene Quellfunktionen, ein erfolgreiches Gesamtgate und veröffentlichte Dokumentation sind keine vollständige Produktabnahme. Das Studio wird weiterentwickelt; reale Installations-, Hardware- und Betriebsnachweise werden gesondert geführt. Den Auslieferungsstand nennt [RELEASE_STATUS.md](Slicer-Server/RELEASE_STATUS.md).

## Orientierung

- [Arbeitsbereiche und Begriffe](#arbeitsbereiche)
- [Dein erstes Projekt](#erstes-projekt)
- [Modelle importieren und Projekte speichern](#projekte)
- [Galerie und Druckerspeicher](#galerie)
- [MakerWorld gezielt nutzen](#makerworld)
- [CAD: Objekte bearbeiten und Druckplatten aufbauen](#cad)
- [Bemalung, Formen und Text](#bemalung)
- [Materialkanäle, AMS und externe Spule](#material)
- [Profile, Düse und G-Code](#profile)
- [Vorschau und Analyse](#vorschau)
- [Aufgaben, Verlauf und Druckerübersicht](#aufgaben)
- [Kamera](#kamera)
- [Einrichtung, HACS und Slicer-Verbindung](#einrichtung)
- [Bedienung am Smartphone](#mobil)
- [Sichern, aktualisieren und Fehler melden](#betrieb)
- [Fehlersuche](#fehlersuche)
- [Tastenkürzel und Glossar](#nachschlagen)

<a id="arbeitsbereiche"></a>
## 1. Deinen Arbeitsbereich finden

Die Oberfläche besitzt neun sichtbare Arbeitsbereiche. Auf einem breiten Bildschirm stehen sie links; auf schmalen Bildschirmen liegen sie in einer waagerecht scrollbaren Leiste. Der Bereich **3D-Studio** vereint Vorbereitung, Farbbearbeitung und Vorschau. Für diese Ansichten musst du keinen zweiten CAD-Bereich suchen.

| Arbeitsbereich | Hier erledigst du das |
| --- | --- |
| **Steuerzentrale** | Verbundenen Drucker, Fortschritt, Druckphasen, Störungen und Kamera überblicken |
| **Galerie** | Bibliothek durchsuchen, Dateien organisieren sowie SD-Karte und MakerWorld öffnen |
| **3D-Studio** | Modelle bearbeiten, mehrere Druckplatten aufbauen, bemalen und die Vorschau prüfen |
| **Materialsysteme** | Konfiguriertes System, erkannte Hardware, belegte Fächer und externe Spule vergleichen |
| **Profile** | Drucker-, Düsen-, Filament-, Druck- und Plattenprofile sowie Sound- und G-Code-Bausteine verwalten |
| **Aufgaben** | Warteschlange und die verfügbaren Auftragsaktionen ansehen |
| **Verlauf** | Vergangene Einträge und ihren gemeldeten Ausgang nachvollziehen |
| **System** | Verbindungen und Diagnoseinformationen untersuchen |
| **Slicing-Server** | Serverzustand, Modelle, Engines, Slicer-Aufträge und Diagnose ansehen |

Vier Dinge begleiten dich durch das Studio: Eine **Datei** liefert Geometrie oder Projektdaten. Ein **Projekt** enthält deinen bearbeitbaren Arbeitsstand. Eine **Druckplatte** bildet einen getrennten Aufbau innerhalb des Projekts. Ein **Auftrag** beschreibt die Verarbeitung oder einen späteren Druckablauf. Merke dir diese Trennung besonders bei Import, Löschen und Wiederholen: Eine Galeriedatei bleibt eine andere Einheit als das daraus bearbeitete Objekt.

Die Kopfzeile der Karte zeigt Version und Build. Diese Angaben helfen beim Vergleichen einer Anleitung mit deiner Installation. Ein Screenshot einer älteren Installation kann andere Profilwerte oder einen anderen Arbeitsstand zeigen. Entscheidend für deine Bedienung ist die tatsächlich geladene Oberfläche.

<a id="erstes-projekt"></a>
## 2. Dein erstes Projekt in sieben Schritten

Für den Einstieg genügt ein Würfel. So lernst du Auswahl, Transformation und Speichern kennen, ohne eine Datei aus dem Internet zu benötigen. Die folgenden Schritte erzeugen weder einen Slice noch einen Druckauftrag.

1. Öffne **3D-Studio** und sichere gegebenenfalls den bereits geöffneten Arbeitsstand.
2. Wähle **Einfügen → Würfel**. Der Grundkörper erscheint auf der aktiven Druckplatte.
3. Klicke den Würfel in der Objektliste an. Prüfe, dass genau dieses Objekt ausgewählt ist.
4. Wähle **Verschieben**, **Drehen** oder **Skalieren**. Mit **Frei**, **X**, **Y** und **Z** begrenzt du die Bearbeitung auf die gewünschte Richtung.
5. Nutze **Zentrieren** und **Auf Druckbett**. Prüfe anschließend Lage und Abmessungen.
6. Vergleiche Drucker, Düse, Druckprofil, Druckplattenoberfläche und Filamentzuordnung mit deinem geplanten Aufbau.
7. Wähle **Datei → Projekt auf HA speichern** und kontrolliere die Rückmeldung.

**Ergebnis:** Ein gespeicherter, bearbeitbarer Studio-Arbeitsstand. Er ist die Grundlage für weitere Geometrie, Materialzuordnung und eine spätere Druckvorbereitung.

**Wenn etwas fehlt:** Bei einer leeren Arbeitsfläche zuerst die aktive Druckplatte und die Objektliste prüfen. **Ansicht → Alles einpassen** richtet die Kamera wieder auf die Szene aus. Ist das Speichern fehlgeschlagen, die sichtbare Fehlermeldung beachten und den geöffneten Stand erhalten, bis der Fehler geklärt ist.

Das gleiche Prinzip funktioniert mit mehreren Grundkörpern. Erzeuge unter **Einfügen** zusätzlich einen Zylinder, einen Ring und einen Kegel. Wähle **Anordnen**, betrachte die Abstände und passe die Ansicht ein. Die [CAD-Beispielseite](handbook/CAD_EXAMPLES.md) zeigt diesen Aufbau mit Originalaufnahmen.

<a id="projekte"></a>
## 3. Dateien, Modelle und Projekte

Das Menü **Datei** führt zu lokaler STL-/3MF-Auswahl, Galerie, SD-Karte und MakerWorld. Außerdem findest du dort Projektaktionen und den Objektexport. Wähle den Eingang nach dem, was du übernehmen möchtest: eine Geometrie, einen gespeicherten Studio-Stand oder ein bestimmtes Anbieterprofil.

**STL** beschreibt Modellgeometrie. Prüfe nach dem Import Größe, Orientierung und Materialzuordnung. **3MF** kann darüber hinaus Objektstruktur und Materialinformationen enthalten. Welche Angaben übernommen werden, hängt vom Dateiinhalt und dem unterstützten Importumfang ab. Herstellererweiterungen oder fremde Projekteinstellungen sind keine allgemeine Kompatibilitätszusage.

Ein lokales Modell öffnen:

1. Sichere den bestehenden Arbeitsstand, bevor du ihn durch einen anderen ersetzt.
2. Öffne **Datei → Lokale STL/3MF öffnen** und wähle die passende Datei.
3. Warte auf das Ergebnis und prüfe Objektliste, aktive Platte und sichtbare Geometrie.
4. Vergleiche Abmessungen sowie Drucker-, Düsen- und Materialauswahl.
5. Speichere den übernommenen Stand als Studio-Projekt.

**Ergebnis:** Die unterstützten Inhalte stehen für die weitere Bearbeitung bereit. Eine Importbestätigung bedeutet noch keine Druckbarkeitsprüfung.

**Fehlerpfad:** Bei einer abgewiesenen Datei die gemeldete Ursache behandeln. Öffne anschließend nicht blind weitere Dateien in denselben ungeklärten Vorgang. Prüfe zuerst, welcher Projektstand noch sichtbar ist und ob die gewünschte Auswahl erhalten blieb.

**Projekt auf HA speichern** hält deinen Studio-Arbeitsstand fest; **HA-Projekt öffnen** lädt einen solchen Stand. **Objekt exportieren** ist ein eigener Weg für Modellgeometrie. Entscheide deshalb vor dem Export, ob du später weiterarbeiten oder ein Modell in einem anderen Werkzeug verwenden möchtest. Ein exportiertes Modell enthält nicht automatisch fertige Druckbahnen.

Benutze für größere Bearbeitungsschritte nachvollziehbare Projektstände. Sichere beispielsweise den importierten Aufbau, bevor du Teile trennst oder eine aufwendige Bemalung beginnst. Rückgängig und Wiederholen helfen innerhalb der Bearbeitung; eine dauerhafte Sicherung bleibt die Grundlage, wenn du das Gerät oder den Browser wechselst.

<a id="galerie"></a>
## 4. Eine übersichtliche Modellbibliothek

Die Galerie bündelt drei Zugänge: **Galerie**, **SD-Karte** und **MakerWorld**. In der lokalen Galerie stehen Ordnerbaum, Suchfeld und Sortierung bereit. Mit **Raster** und **Liste** wechselst du die Darstellung. Die Auswahl **Name A–Z**, **Neueste zuerst** oder **Größte zuerst** hilft beim Wiederfinden größerer Bestände.

Dateien in die Bibliothek aufnehmen:

1. Öffne den gewünschten Zielordner oder lege mit **Neuer Ordner** einen passenden an.
2. Wähle **Hochladen** und die gewünschten Dateien. Die Galerieauswahl bietet STL, 3MF und OBJ an; der direkte Studio-Dateieingang bietet STL und 3MF.
3. Beobachte Fortschritt, aktuellen Dateinamen und die Liste erfolgreicher Übernahmen.
4. Prüfe bei einem vorhandenen Ziel die angebotene Ersetzen-Entscheidung.
5. Öffne den übernommenen Eintrag über **3D-Studio** oder **Im 3D-Studio öffnen**.

**Ergebnis:** Die Datei liegt in der Bibliothek und kann in einen Studio-Arbeitsstand übernommen werden. Ein Galerie-Upload überträgt das Modell nicht automatisch zum Drucker.

**Fehlerpfad:** Bei einem teilweise fehlgeschlagenen Upload unterscheiden, welche Dateien erfolgreich waren und welche nicht. Einen vollständigen Stapel nicht allein wegen einer einzelnen Fehlermeldung nochmals ersetzen. Die Galerie meldet außerdem, wenn eine laufende Änderung zunächst beendet werden muss.

Für mehrere Einträge gibt es **Alle auswählen**, **Auswahl aufheben**, **Kopieren**, **Verschieben** und **Löschen**. Kontrolliere vor einer Sammelaktion die Auswahlanzahl und den Zielordner. Die Bestätigungsdialoge nennen betroffene Pfade beziehungsweise Einträge. Ein Dateiname allein ist kein ausreichender Grund, eine vermeintliche Dublette zu entfernen.

**Duplikate prüfen** beginnt mit einer Analyse. **ZIP-Export** und **ZIP-Import** unterstützen die Übertragung einer Bibliotheksauswahl. Beim Import zeigt die Oberfläche die geplante Zahl der Dateien und Ordner sowie vorhandene Konflikte. Lies insbesondere den Hinweis auf Dateien, die ersetzt würden, bevor du bestätigst.

Die **SD-Karte** gehört zum angebundenen Druckerspeicher. Ihr Inhalt und die verfügbaren Aktionen hängen vom Druckerzugang ab. Eine Datei auf der SD-Karte, eine Galeriedatei und ein gespeichertes Projekt sind unterschiedliche Bestände. Prüfe bei jeder Löschaktion, welchen davon du gerade bearbeitest.

<a id="makerworld"></a>
## 5. MakerWorld: vom Fund zur bewussten Auswahl

MakerWorld erreichst du über die Galerie oder den gleichnamigen Studio-Zugang. Die Suche verwendet kombinierbare Suchbegriffe und Tags. Mit **Filter hinzufügen** übernimmst du einen Begriff; einzelne Filter lassen sich entfernen, **Alle Filter entfernen** setzt die Kombination zurück. Die angebotene Sortierung umfasst Relevanz, Name, Downloads und Likes.

**Mehr laden** ruft weitere Treffer ab. Eine bereits sichtbare Trefferliste ist daher nicht automatisch der vollständige Bestand. Falls eine Suche leer bleibt, entferne zunächst einzelne Filter, bevor du einen Fehler des Imports vermutest. Suche und Übernahme sind getrennte Schritte.

Ein Modell gezielt übernehmen:

1. Öffne die Details des gewünschten Designs und prüfe Titel, Urheberangaben und Lizenzhinweise.
2. Wähle unter **Druckdateien** die konkrete Variante. Die Druckerfilter helfen, geeignete Angebote einzugrenzen.
3. Vergleiche Druckermodell, Plattenzahl und die gelieferten Angaben zum Druckprofil.
4. Wähle das **Ziel-Druckerprofil** für die Übernahme.
5. Nutze **Im Studio öffnen** für die Bearbeitung, **Galerie** für die Bibliothek oder **3MF** für den entsprechenden Dateidownload.
6. Prüfe im Studio die tatsächlich übernommenen Platten, Düse, Druckprofil und Materialkanäle.

**Ergebnis:** Die bewusst gewählte Variante wird über den vorgesehenen Weg übernommen. Das Designbild allein bestimmt nicht, welche 3MF-Variante du geladen hast.

**Fehlerpfad:** Meldet der Dialog ein fehlendes Ziel-Druckerprofil, ergänze diese Auswahl. Bei Anmeldung, Kontozustand, Region, Ratenlimit oder Anbieterfehler gilt die konkrete Meldung. Eine andere Modellvariante zu öffnen ersetzt keine gültige Anmeldung und klärt keine widersprüchliche Profilzuordnung.

Ein Design kann mehrere Druckprofile beziehungsweise Varianten enthalten. Empfehlungen verweisen auf andere Designs und sind keine zusätzlichen Modellteile der aktuellen Auswahl. Kontrolliere beim Wechsel zwischen Details weiterhin, welches Design und welche Druckdatei aktiv sind.

Die Detailoberfläche kann Beschreibungen, Kommentare, Bewertungen, Antworten und Empfehlungen des Anbieters anzeigen. Sichtbare soziale Bedienelemente sind derzeit keine Zusage, dass du Reaktionen, Antworten, Fotos oder Rezensionen aus dem Studio veröffentlichen kannst. Die aktuelle Quelle enthält dafür ausdrücklich noch nicht ausgeführte Aktionen. Für dieses Handbuch gelten Lesen, Auswählen und die beschriebenen Importwege als getrennte Funktionen.

Beachte die Lizenz des konkreten Modells vor Verwendung oder Weitergabe. Ein Downloadknopf erweitert weder Nutzungsrechte noch Rechte an Vorschaubildern oder Marken. Bewahre bei eigenen Sammlungen die zugehörigen Herkunftsangaben auf.

<a id="cad"></a>
## 6. CAD: den Aufbau auf der Druckplatte gestalten

Im 3D-Studio stehen Objektliste, Arbeitsfläche, Werkzeugleisten und Prozessoptionen nebeneinander. Obere, linke und rechte Leisten lassen sich ein- und ausklappen. Verwende diese Möglichkeit, wenn du mehr Platz für die Szene benötigst; die Modellgeometrie bleibt dabei erhalten.

![Originalaufnahme des CAD-Arbeitsbereichs](handbook/images/cad-overview.png)

### Auswählen und transformieren

Wähle ein Objekt in der Liste oder auf der Arbeitsfläche. **Strg+Klick** und **Shift+Klick** unterstützen die Mehrfachauswahl. Achte auf den sichtbaren Auswahlzustand, bevor du dieselbe Aktion auf mehrere Modelle anwendest. Modelle und Malbereiche besitzen eigene Einträge.

| Werkzeug | Wirkung und anschließende Kontrolle |
| --- | --- |
| **Verschieben** | Position verändern; Bettgrenzen und Auflage prüfen |
| **Drehen** | Orientierung verändern; Unterseite und Überhänge betrachten |
| **Skalieren** | Abmessungen ändern; Größe und Proportionen vergleichen |
| **Spiegeln X/Y/Z** | Geometrie an der gewählten Achse spiegeln; Zuordnungen prüfen |
| **Zentrieren** | Auswahl mittig ausrichten; Abstände zu anderen Objekten prüfen |
| **Auf Druckbett** | Unterseite auf die Bettebene setzen |
| **Flach legen** | Eine geeignete flache Orientierung herstellen; Ergebnis betrachten |
| **Anordnen** | Objekte auf der Platte verteilen; Bettrand und Zwischenräume prüfen |

So richtest du mehrere Modelle aus:

1. Lade die Modelle auf die gewünschte aktive Platte.
2. Kontrolliere einzeln ihre Abmessungen und setze sie auf das Druckbett.
3. Wähle die betroffenen Objekte und verwende bei Bedarf **Anordnen**.
4. Prüfe die Szene aus mehreren Blickrichtungen und mit **Alles einpassen**.
5. Speichere den Aufbau vor weiteren Eingriffen.

**Ergebnis:** Eine übersichtlich angeordnete Platte. Geometrische Platzierung ersetzt noch keine Prüfung von Stützen, Druckreihenfolge oder realen Maschinenfreiräumen.

### Duplizieren, teilen und reparieren

**Duplizieren** erzeugt eine weitere Instanz der Auswahl. Kopieren, Ausschneiden und Einfügen unterstützen das Umorganisieren. Prüfe anschließend den Platzbedarf. **Messen** hilft, Auswahl und Dimensionen einzuschätzen. **Teilen** beziehungsweise **Geometrisch teilen** zerlegt ein geeignetes ausgewähltes Modell; die Werkzeugleiste verlangt dafür genau eine Modellauswahl.

**Mesh prüfen** bearbeitet unterstützte Geometrieprobleme. Bewahre vor Reparatur oder Teilung einen gespeicherten Ausgangsstand auf und kontrolliere das Ergebnis. Eine Reparatur kann unpassende oder widersprüchliche Materialzuordnungen nicht durch bloßes Anzeigen eines fehlerfreien Bildes auflösen.

### Druckplatten und eigene Grundkörper

**Druckplatte → Neue Druckplatte** oder das Plus an der Plattenleiste legt einen weiteren Aufbau an. Vor jedem Import und Slice die aktive Platte prüfen. Beim Entfernen einer Platte auch ihre enthaltenen Objekte berücksichtigen. Das Entfernen einer Platte ist keine allgemeine Bereinigung ungenutzter Bibliotheksdateien.

Unter **Einfügen** gibt es Würfel, Zylinder, Kugel, Kegel, Ring und Platte. Die Form **Platte** ist ein Modellgrundkörper und nicht die Maschinenoberfläche. Der **First-Layer-Test** erzeugt eine düsenabhängige Testgeometrie mit TaraCraft-T und eigener Prozessvorbereitung. Wähle zuvor eine unterstützte Düse; bei bereits belegter Platte legt der Quellablauf dafür eine zusätzliche Platte an. Prüfe Bettgröße und Werte vor einer späteren Verwendung.

<a id="bemalung"></a>
## 7. Bemalung: Material auf Modellflächen legen

Bemalung weist Modellflächen einem Druckmaterial zu. Die sichtbare Farbe folgt dem gewählten Materialkanal. Eine frei gewählte Bildschirmfarbe ist damit nicht gleichbedeutend mit einem verfügbaren Filament. Im Malwerkzeug ist die Farbanzeige entsprechend an **Druckfilament** gebunden.

Bereite die Materialquelle und die tatsächlich verfügbaren Kanäle vor, bevor du größere Flächen bemalst. Bei **Kein belegter AMS-Slot** zunächst die Materialsysteme und die belegten Fächer prüfen. Eine Materialquelle nur im Projekt auszuwählen erzeugt keine passende Hardwarebelegung.

Eine Fläche bemalen:

1. Wähle das gewünschte Modell auf der aktiven Platte.
2. Wähle unter **Druckfilament** den passenden belegten Materialkanal.
3. Aktiviere **Malen AN** und wähle **Pinsel** oder **Stift**.
4. Passe **Größe** an und ziehe über die sichtbare Modelloberfläche.
5. Betrachte die Fläche aus geeigneten Blickrichtungen und prüfe die Malbereiche in der Liste.
6. Speichere den Arbeitsstand.

**Ergebnis:** Modellflächen sind einem ausgewählten Materialkanal zugeordnet. Erst der weitere Export- und Slicer-Ablauf zeigt, ob die Zuordnung für einen konkreten Auftrag vollständig verarbeitet werden kann.

**Fehlerpfad:** Bleibt die Wirkung aus, prüfe zuerst Modellauswahl, Malmodus und Materialkanal. Versuche nicht, fehlende Kanäle durch eine andere Bildschirmfarbe zu ersetzen. Ist Verschieben oder Drehen gesperrt, verlasse den Malmodus mit **Malen AUS** und wähle anschließend das Transformationswerkzeug.

### Pinsel, Formen und Radierer

**Pinsel** und **Stift** sind für freie Striche vorgesehen. **Radierer** entfernt Bemalung lokal. Mit **Rechteck**, **Kreis** und **Linie** ziehst du vom Startpunkt zum gewünschten Ende. Prüfe das Ergebnis auf der Modelloberfläche: Eine Form auf einem gewölbten Objekt lässt sich nicht allein anhand ihres Aufziehrahmens beurteilen.

Die Werkzeuggröße hilft, Details oder größere Flächen zu bearbeiten. Beginne bei kleinen Motiven mit einem überschaubaren Bereich. Betrachte Kanten und gekrümmte Flächen anschließend genauer. Ein gelungenes Farbbild ist keine Aussage über die mechanische Druckqualität.

### Text platzieren

1. Gib im Feld **Text** die gewünschte kurze Beschriftung ein.
2. Passe **Schriftgröße** an und wähle das Werkzeug **Text**.
3. Kontrolliere erneut **Druckfilament**.
4. Klicke an die gewünschte Stelle der Modelloberfläche.
5. Prüfe die vollständige Beschriftung aus mehreren Blickrichtungen und speichere.

**Ergebnis:** Eine materialgebundene Beschriftung der Modelloberfläche. Das Textwerkzeug ist keine Zusage für frei extrudierte dreidimensionale Schriftkörper.

**Fehlerpfad:** Bei unpassender Position zunächst rückgängig machen oder den betreffenden Malbereich bearbeiten. Nicht durch zusätzliche übereinanderliegende Beschriftungen versuchen, einen ungeklärten ersten Versuch zu verdecken.

Malbereiche bleiben von importierten Modellobjekten getrennt. Prüfe vor **Entf** oder **Löschen**, ob du Bemalung, ein Modell oder mehrere Einträge ausgewählt hast. Mehrfarbige Arbeit benötigt eindeutige geeignete Materialkanäle; eine einzelne externe Spule stellt keinen automatischen Mehrfarbenweg bereit.

<a id="material"></a>
## 8. Materialsysteme: Konfiguration und Wirklichkeit vergleichen

Der Bereich **Materialsysteme** trennt vier Angaben: **Konfiguriertes System**, **Live erkannt**, **Aktive Studio-Quelle** und **Belegte Fächer**. Diese Trennung erklärt viele scheinbare Widersprüche. Ein konfiguriertes AMS ist nicht zwangsläufig erreichbar; eine geladene externe Spule kann vorhanden sein, während die aktive Studio-Platte weiterhin eine andere Quelle verwendet.

![Originalaufnahme der Materialsystem-Ansicht](handbook/images/materials.png)

Vor einer Materialzuordnung:

1. Wähle in **Materialsysteme** den richtigen Drucker.
2. Verwende bei Bedarf **Materialsysteme synchronisieren**.
3. Vergleiche konfiguriertes System und Live-Erkennung.
4. Öffne die tatsächlich gemeldeten Fächer beziehungsweise die externe Spule.
5. Prüfe Material, Farbe, Belegung und die Information zur geladenen Zuführung.
6. Vergleiche diese Angaben mit der aktiven Studio-Quelle und den gewählten Filamentprofilen.

**Ergebnis:** Du weißt, welche Quelle der Aufbau verwendet und welche Materialien das System tatsächlich meldet.

**Fehlerpfad:** Fehlen Fächer oder werden keine Materialien gemeldet, zuerst Verbindung und Aktualität prüfen. Leere oder unbekannte Einträge sind keine zusätzlichen Farbkanäle. Ein Systemtyp in einer Auswahlliste beweist keine vollständige reale Hardwareunterstützung für jede Variante.

Die Slotansicht unterscheidet **belegt**, **leer** und **zur Düse geladen**. RFID-Daten können Angaben verbindlich vorgeben. Die Oberfläche kennzeichnet gesperrte Felder, beispielsweise bei erkanntem RFID oder während eines laufenden Drucks. Lies den jeweiligen Hinweis, statt widersprüchliche Angaben an anderer Stelle zu erzwingen.

Die **externe Spule** ist ein eigener Zuführweg mit eigener Profilzuordnung. Kontrolliere besonders eine Meldung, dass sie zwar am Drucker geladen, aber noch nicht als Studio-Quelle gewählt ist. Materialquelle, reale Zuführung und Profil sollen denselben geplanten Aufbau beschreiben. Die Auswahl im Studio lädt das Filament nicht allein dadurch mechanisch in den Drucker.

Die für einen Auftrag gespeicherten Materialfarben gehören zu dessen Zustand. Wenn du später eine andere Spule einlegst, muss ein früheres Ergebnis weiterhin anhand seiner damaligen Zuordnung beurteilt werden. Das ist besonders beim Wiederholen eines älteren Auftrags relevant.

<a id="profile"></a>
## 9. Profile passend kombinieren

Profile beantworten verschiedene Fragen: Welche Maschine arbeitet? Welche Düse ist eingesetzt? Welches Filament wird verwendet? Welche Qualität und welche Oberfläche sind gewünscht? Wähle diese Angaben getrennt. Eine plausible Filamentbezeichnung ersetzt keine passende Maschinen- oder Düsenwahl.

![Originalaufnahme der Profilverwaltung](handbook/images/profiles.png)

| Profilgruppe | Wofür sie zuständig ist |
| --- | --- |
| **Drucker** | Maschinenmodell und Druckraum |
| **Düse** | Durchmesser und Düsenmaterial |
| **Filamentprofile** | Hersteller, Material, Variante und Materialeigenschaften |
| **Druckprofile** | Schichthöhe, Wände, Infill, Geschwindigkeit und Qualität |
| **Druckplatten** | Oberfläche, Abmessungen und zugehörige Werte |
| **Startsound / Endsound** | Gesonderte Sound-Bausteine |
| **G-Code 1 / G-Code 2** | Maschinenstart beziehungsweise Maschinenende gemäß Profilvertrag |

Eine Kombination prüfen:

1. Wähle Maschine beziehungsweise Zieldrucker und die tatsächlich eingesetzte Düse.
2. Wähle Druckplattenprofil und Druckprofil.
3. Ordne für die verwendete Quelle passende Filamentprofile zu.
4. Vergleiche Schichthöhe und weitere Werte mit den angezeigten Grenzen.
5. Prüfe eigene Prozessüberschreibungen und speichere den Projektstand.

**Ergebnis:** Ein nachvollziehbarer Profilaufbau. Für den A1 sind Quellverträge für 0,2, 0,4, 0,6 und 0,8 mm vorhanden. Daraus folgt keine pauschale Abnahme jeder Düse, Oberfläche oder Hardwarefamilie.

**Fehlerpfad:** Bei ungeeigneten Vorschlägen zuerst Maschine, Düsenprofil, Materialquelle und Profilherkunft vergleichen. Ein manuell gesetzter Wert darf eine gemeldete Unverträglichkeit nicht nur optisch überdecken.

Ein leeres Überschreibungsfeld verwendet den vorgesehenen Profilstandard. Ein Platzhalter ist kein bereits eingetragener eigener Wert. Wenn du beispielsweise eine Schichthöhe ausdrücklich setzt, behalte diese Abweichung bei späteren Profilwechseln im Blick. Prüfe auch Werte, die du in einem früheren Versuch gesetzt hast.

### Cloud und eigene Profile

**Cloud synchronisieren** ist eine bewusste Aktion im Bereich **Profile**. Lokale Profile und bereits synchronisierte Cloudprofile sind unterscheidbar. Ein lokal verfügbarer synchronisierter Stand bedeutet nicht, dass der Anbieter gerade erreichbar ist. Kontrolliere bei Fehlern Anmeldung und Rückmeldung, bevor du denselben Vorgang wiederholst.

### Sechs getrennte G-Code- und Sound-Abschnitte

Der Profilvertrag trennt Maschinenstart, Maschinenende, Filamentstart, Filamentende sowie Startsound und Endsound. Filamentbezogene Start-/Endteile gehören zum Filamentprofil. Die getrennten Sound- und Maschinenbausteine dürfen nicht allein durch eine Filamentauswahl unbemerkt ersetzt werden.

Ändere solche Inhalte nur, wenn du ihre Wirkung für die konkrete Maschine kennst. Ein Sound-Baustein besteht ebenfalls aus ausführungsrelevanten Befehlen. Die Oberfläche ersetzt dabei keine Prüfung des später tatsächlich erzeugten Auftrags.

<a id="vorschau"></a>
## 10. Den richtigen Zustand ansehen

Im Studio wechselst du zwischen **Vorbereiten**, **Farben** und **Vorschau**. Die Vorbereitung zeigt den Aufbau; die Farbansicht hilft bei Materialzuordnung und Bemalung. Die Vorschau benötigt passende bereits geslicte Daten, um Druckbahnen darzustellen. Eine leere Toolpath-Ansicht bei einem noch nicht geslicten Modell ist deshalb kein Beleg für verlorene Geometrie.

Ein vorhandenes Ergebnis prüfen:

1. Öffne die gewünschte Platte beziehungsweise den dazugehörigen Auftrag.
2. Wechsle in **Vorschau** und prüfe, welches Ergebnis tatsächlich geladen wurde.
3. Betrachte Schichten, Materialfarben und vorhandene Analyseinformationen.
4. Nutze die angebotenen Diagnosefilter und vergleiche anschließend wieder mit der Materialdarstellung.
5. Lies Warnungen und ausstehende Prüfungen, bevor du den nächsten bewussten Verarbeitungsschritt erwägst.

**Ergebnis:** Du beurteilst ein bestimmtes Ergebnis mit seiner Materialzuordnung. Der Blick auf eine Modellfläche ist von der Prüfung einer Druckbahn zu unterscheiden.

**Fehlerpfad:** Bei fehlenden Bahnen zuerst Auftrag, Ergebnisverfügbarkeit, Schichtauswahl und Filter kontrollieren. Bei unerwarteten Farben den aktiven Ansichtsmodus und die im Auftrag gespeicherten Kanäle vergleichen. Eine später geänderte AMS-Bestückung ist keine verlässliche Farbquelle für einen früheren Auftrag.

Vergleiche eine gewählte Schicht bei Bedarf mit dem Modellaufbau unter **Vorbereiten**, um ihre Lage einzuordnen. Eine transparente Darstellung der verbleibenden Gesamtgeometrie ist für den aktuellen Stand hier nicht als geprüft zugesagt. Ausgeblendete Bahnen oder Diagnosefarben ändern nicht automatisch das gespeicherte Material. Fehlende oder unbekannte Farbkanäle sollen als ungeklärt erkennbar bleiben.

Warnungen können eine bewusste Entscheidung verlangen. Bei einem Dialog zu Stützen insbesondere die genannten Objekte lesen und den vorgesehenen Schritt wählen. Ein minimierter oder geschlossener Hinweis ist nicht automatisch eine bestandene Analyse. Speichere bei umfangreichen Änderungen den Aufbau und prüfe nach einer neuen Vorbereitung erneut das passende Ergebnis.

<a id="aufgaben"></a>
## 11. Aufgaben, Verlauf und Druckerübersicht

**Aufgaben** zeigt Warteschlange und Auftragszustände; **Verlauf** hilft beim Rückblick. Je nach Zustand sind **Erneut einreihen** oder **Aus Warteschlange** verfügbar. Die Bestätigung für erneutes Einreihen weist darauf hin, dass der Druck dadurch noch nicht automatisch startet.

Ein älteres Vorhaben erneut betrachten:

1. Suche den Eintrag im passenden Bereich und prüfe Datei, Drucker, Zustand und Datum.
2. Vergleiche den damaligen Aufbau mit den aktuell verfügbaren Materialien und Profilen.
3. Öffne vorhandene Details beziehungsweise Ergebnisse, bevor du eine Wiederholung wählst.
4. Bestätige eine angebotene Aktion erst für den tatsächlich gewünschten Eintrag.
5. Kontrolliere anschließend den gemeldeten neuen Zustand.

**Ergebnis:** Die Verwaltungsaktion ist nachvollziehbar zugeordnet. Ein Warteschlangeneintrag ist noch keine physische Druckfreigabe.

**Fehlerpfad:** Nach einer unklaren Antwort zuerst die Liste aktualisieren und das Ergebnis prüfen. Nicht allein aufgrund einer unterbrochenen Browserantwort davon ausgehen, dass die erste Aktion folgenlos geblieben ist.

Unterscheide stets: einen Warteschlangeneintrag entfernen, einen gespeicherten Eintrag löschen, einen Slicer-Auftrag abbrechen, einen laufenden Druck abbrechen und eine Datei vom Drucker löschen. Diese Aktionen betreffen unterschiedliche Zustände. Ein bereinigter Verlauf beweist keinen gestoppten Drucker.

Die **Steuerzentrale** zeigt gemeldete Laufzeitbereitschaft, Drucker, Onlinezustand, Störungen, Restzeit, Layer und Tempo. Der dargestellte Druckablauf ergänzt diese Übersicht. Bei widersprüchlichen Informationen zuerst Verbindung und Aktualität klären. Nicht jede Phase wird vom Gerät als eigener Zustand gemeldet.

Der grundsätzliche Ablauf bleibt: Projekt vorbereiten, auf einer dafür eingerichteten Installation bewusst slicen, Ergebnis prüfen, Druckvorbereitung prüfen und erst anschließend die vorgesehenen getrennten Druckfreigaben bestätigen. Profilwechsel, Verbindungstest oder das Öffnen einer Vorschau sind keine solche Freigabe.

<a id="kamera"></a>
## 12. Die Kamera sinnvoll verwenden

In der Steuerzentrale findest du die **Druckerkamera**. Je nach verfügbarem Kamerazugang zeigt sie neue Bilder und zugehörige Statusinformationen. **Einblenden** beziehungsweise **Ausblenden** steuert die Sichtbarkeit. **Aktualisieren** fordert einen Abruf an; **Vollbild** steht bei verfügbarer Darstellung bereit.

1. Öffne die Steuerzentrale und blende die Kamera ein.
2. Prüfe das Kamerabild und die Statusanzeige gemeinsam.
3. Vergleiche vorhandene Frame- beziehungsweise Zeitangaben, wenn du Aktualität beurteilst.
4. Nutze bei Bedarf **Aktualisieren**, ohne den Druckzustand aus dem Bild allein abzuleiten.

**Ergebnis:** Eine zusätzliche visuelle Beobachtung des Druckers. Telemetrie und Kamera ergänzen sich; ein Kamerabild ersetzt keine Statusmeldung des Geräts.

**Fehlerpfad:** Bei einem stehen gebliebenen Bild prüfen, ob tatsächlich neue Frames oder erfolgreiche Abrufe gemeldet werden. Ein erhaltenes letztes Bild kann älter sein. Bei **Keine Studio-Kamera verfügbar** den angebundenen Kamera- und Druckerzugang untersuchen. Die Kamera kann nur Daten anzeigen, die die Installation bereitstellt.

Beim Teilen eines Screenshots auch die Umgebung im Kamerabild beachten. Eigene Modelle, Dateinamen und andere private Inhalte können sichtbar sein, selbst wenn keine Zugangsdaten auf der Seite stehen.

<a id="einrichtung"></a>
## 13. Einrichtung: Integration, Frontend und Slicer

Das Studio besteht aus der Home-Assistant-Integration, der Browseroberfläche und einem separaten Slicer-Dienst. HACS betrifft die Auslieferung der Integration. Der Slicer benötigt seine eigene Installation, passende Engines und Profile. Eine sichtbare Lovelace-Karte installiert diese Bestandteile nicht nachträglich.

Prüfe vor einer neuen Einrichtung den [aktuellen Auslieferungsstand](Slicer-Server/RELEASE_STATUS.md), die [Installationshinweise](handbook/wiki/Installation.md) und den [Docker-Schnellstart](Slicer-Server/DOCKER_QUICKSTART.md). Repositoryquellen, Root-Metadaten und ein geprüftes Archiv sind unterschiedliche Nachweise. Der dokumentierte HACS-Vertrag allein bestätigt noch kein vorhandenes vollständiges Releasepaket und keine frische Installation.

### HACS und Lovelace

Bei einer verfügbaren geprüften Releaseauslieferung übernimmt HACS die Integrationsdateien über den vorgesehenen Installationsweg. Danach müssen Integration und Frontend in Home Assistant korrekt geladen sein. Die registrierte Oberfläche stellt folgenden Kartentyp bereit:

```yaml
type: custom:ultimate-3d-studio-card
title: Ultimate 3D Studio
```

Füge diese Karte erst hinzu, wenn ihre Ressource vorhanden ist. Meldet Home Assistant ein fehlendes Custom Element, zuerst installierte Integration, Frontend-Ressource und geladenen Build vergleichen. Wiederholtes Einfügen derselben Kartenkonfiguration behebt keine fehlenden Dateien.

### Den Slicer serverseitig verbinden

1. Öffne in Home Assistant **Einstellungen → Geräte & Dienste → Ultimate 3D Studio → Konfigurieren**.
2. Pflege die vorgesehene Slicer-Adresse und das zugehörige Secret in der Integration.
3. Verwende für eine entfernte Verbindung den dokumentierten verifizierten HTTPS-/TLS-Weg.
4. Prüfe danach die gemeldete Verbindung unter **System** und **Slicing-Server**.
5. Vergleiche Serverversion, angebotene Fähigkeiten und Engines mit der geplanten Verwendung.

**Ergebnis:** Die Integration kann den konfigurierten Dienst über ihren serverseitigen Zugang ansprechen. Ein erreichbarer Server ist noch keine Abnahme jedes Druckprofils oder jeder Engine.

**Fehlerpfad:** Bei Authentifizierungs- oder Zertifikatsfehlern Adresse, Zugang und Vertrauenskette an dieser Stelle klären. Das Secret gehört nicht in eine Browseradresse, einen Screenshot oder die Lovelace-Kartenkonfiguration. Verbindungsprobleme nicht durch Abschalten der TLS-Prüfung verdecken.

Der Bereich **Slicing-Server** bietet außerdem Servermodelle, Aufträge, Suche, Filter und Diagnose. Dort sichtbare Engine-Auswahlen belegen keine installierten oder vollständig freigegebenen Engines. **Hochladen** und **Slicing starten** sind eigene Aktionen. Zum ersten Kennenlernen des Studios benötigst du sie nicht.

<a id="mobil"></a>
## 14. Am Smartphone und in der Home-Assistant-App

Auf schmalen Bildschirmen liegt die Arbeitsbereichsnavigation waagerecht. Wische innerhalb dieser Leiste, um weitere Einträge zu erreichen. Der Inhalt darunter besitzt eigene scrollbare Bereiche. Unterscheide deshalb zwischen der Navigation, einer Profilliste und der eigentlichen Arbeitsfläche.

Für eine schnelle Kontrolle eignen sich Steuerzentrale, Auftragslisten und Materialübersicht. Für präzise CAD-Bearbeitung helfen ein größerer Bildschirm und die im Arbeitsbereich angebotenen Werkzeuge. Eine Desktop-Geste wie die rechte Maustaste hat auf einem Touchgerät keinen automatisch zugesicherten gleichwertigen Ersatz.

So behältst du auf engem Raum den Überblick:

1. Wähle den gewünschten Arbeitsbereich in der oberen Leiste.
2. Prüfe im Studio zuerst aktive Platte und Modellauswahl.
3. Klappe unbenötigte Leisten ein, wenn sie den Blick auf die Szene verdecken.
4. Blende benötigte Objekt- oder Einstellungsleisten gezielt wieder ein.
5. Speichere vor einem größeren Wechsel des Geräts oder Arbeitskontexts.

**Ergebnis:** Eine auf den verfügbaren Platz angepasste Ansicht mit demselben fachlichen Projektaufbau.

**Fehlerpfad:** Springt die Navigation unerwartet zurück oder bleibt ein Kamerabild stehen, notiere Arbeitsbereich, ausgeführte Geste und Build. Diese Beobachtung ist ein konkreter Fehlerbericht. Vollständige Touch-, Scroll- und Kameraabnahmen bleiben eigene Prüfpunkte; die vorhandenen Quellregeln sind keine pauschale Zusage für jede App- und Gerätekombination.

<a id="betrieb"></a>
## 15. Arbeitsstände sichern und Änderungen nachvollziehen

Speichere Projekte nach klaren Bearbeitungsschritten und behalte die ursprünglichen Modelle. Ein Bibliotheksexport, ein Studio-Projekt und eine Sicherung der gesamten Installation erfüllen verschiedene Zwecke. Prüfe bei einer geplanten Wiederherstellung, welche Daten du tatsächlich gesichert hast.

Für den Slicer dokumentiert [Betrieb und Wiederherstellung](Slicer-Server/OPERATIONS.md) die eigenen Daten- und Betriebsverträge. Befolge für eine konkrete Installation deren Anleitung. Ein Browserprojekt bildet nicht automatisch Serverprofile, Engines, Auftragsdaten und Verbindungsinformationen vollständig ab.

Vor einer Aktualisierung:

1. Notiere installierte Version und Build sowie den bisherigen funktionierenden Zustand.
2. Sichere die betroffenen Projekte und den vorgesehenen Installationsbestand nach dessen Anleitung.
3. Lies Änderungen und Auslieferungsstatus des gewählten Standes.
4. Aktualisiere nur über den dazugehörigen beschriebenen Weg.
5. Prüfe anschließend Integration, Frontend, Projektöffnung und Slicer-Verbindung getrennt.

**Ergebnis:** Du kannst Änderungen einem konkreten Stand zuordnen und weißt, wo eine mögliche Abweichung auftritt.

**Fehlerpfad:** Bei einem Problem nicht gleichzeitig Profile, Serveradresse und Frontendstand verändern. Halte die beobachtete Abweichung fest und arbeite von der betroffenen Komponente aus. Eine neue Oberfläche beweist nicht, dass ein separater Worker oder eine Engine ebenfalls aktualisiert wurde.

Ein guter Fehlerbericht nennt Arbeitsbereich, genaue Aktion, erwartetes Ergebnis, sichtbare Meldung und Build. Ergänze bei Bedarf eine kurze Folge reproduzierbarer Schritte. Entferne private Dateinamen, Kontoinformationen und Geheimnisse aus geteilten Bildern oder Diagnoseauszügen. Die Rohdaten unter Serverdiagnose sind zum Nachsehen hilfreich, aber nicht ungeprüft für öffentliche Beiträge geeignet.

<a id="fehlersuche"></a>
## 16. Fehler eingrenzen

Beginne mit der unmittelbar betroffenen Funktion. Ein Slicer-Verbindungsfehler, eine nicht geladene Kamera und ein fehlerhafter Dateiimport können verschiedene Ursachen haben. Prüfe, was weiterhin funktioniert, und erhalte den aktuellen Arbeitsstand.

| Beobachtung | Erster sinnvoller Schritt | Danach |
| --- | --- | --- |
| **Arbeitsfläche wirkt leer** | Aktive Platte und Objektliste prüfen | **Alles einpassen**; Importergebnis vergleichen |
| **Lokale Datei öffnet nicht** | Dateityp und konkrete Fehlermeldung prüfen | Verbliebenen Projektstand kontrollieren; Original behalten |
| **Galerieeintrag fehlt** | Ordner, Suchfilter und Sortierung prüfen | **Aktualisieren**; erfolgreichen Upload nachsehen |
| **MakerWorld zeigt keine Treffer** | Kombinierte Filter einzeln entfernen | Anmeldung und Anbieterantwort prüfen |
| **MakerWorld-Übernahme stoppt** | Gewählte Druckdatei und Ziel-Druckerprofil prüfen | Fehlermeldung zu Zugriff oder Profilzuordnung behandeln |
| **Objekt lässt sich nicht bewegen** | Malmodus und Werkzeug prüfen | **Malen AUS**, dann Transformation wählen |
| **Bemalung funktioniert nicht** | Modell, Druckfilament und Malmodus prüfen | Belegte Kanäle in Materialsysteme vergleichen |
| **Kein belegter AMS-Slot** | Reale Belegung und Aktualität prüfen | Materialquelle und Profilzuordnung klären |
| **Profilwerte überraschen** | Maschine, Düse und aktives Profil vergleichen | Eigene Überschreibungen kontrollieren |
| **Slicen ist deaktiviert** | Objekte, aktive Platte, laufende Vorgänge und Profile prüfen | Gemeldete Serververfügbarkeit untersuchen |
| **Vorschau hat keine Bahnen** | Vorhandenes Ergebnis und gewählten Auftrag prüfen | Schichtauswahl und Filter vergleichen |
| **Farben wirken anders** | Material- oder Diagnoseansicht unterscheiden | Auftragsgebundene Palette prüfen |
| **Kamera steht** | Frame-/Zeitangaben und Fehlerzustand lesen | Sichtbarkeit und gezielten Abruf prüfen |
| **Auftragsaktion bleibt unklar** | Liste aktualisieren und Zustand prüfen | Keine ungeklärte verändernde Aktion mehrfach auslösen |
| **Karte ist nicht verfügbar** | Integration und registrierte Ressource prüfen | Tatsächlich geladenen Frontend-Build vergleichen |
| **Slicer meldet offline** | Dienstzustand und Integrationskonfiguration prüfen | Authentifizierung, TLS und Enginezustand getrennt klären |

### Eine blockierte Vorbereitung klären

1. Lies die vollständige Meldung und merke dir die betroffene Platte beziehungsweise das Objekt.
2. Prüfe die darin genannte Auswahl oder Voraussetzung.
3. Ändere eine nachvollziehbare Ursache und kontrolliere den Projektstand.
4. Wiederhole den vorgesehenen Schritt erst, wenn die erste Aktion und ihr Ergebnis geklärt sind.

**Ergebnis:** Ein verständlicher nächster Versuch mit derselben bewussten Zielauswahl.

**Wenn die Ursache offen bleibt:** Speichere soweit möglich den Arbeitsstand und erstelle einen bereinigten Fehlerbericht. Eine Schaltfläche wiederholt zu betätigen liefert keinen zusätzlichen Nachweis, dass vorherige Aktionen beendet sind.

Bei einer Störung während eines realen Drucks haben die verlässliche Geräteanzeige und die dafür vorgesehenen Bedienelemente Vorrang. Die Fehlerhilfe dieses Handbuchs ist keine zusätzliche Druckfreigabe und führt keine automatische Wiederaufnahme aus.

<a id="nachschlagen"></a>
## 17. Tastenkürzel und Begriffe

Die Kürzel gelten für die Studio-Bearbeitung im passenden Eingabekontext. In einem Textfeld soll die Texteingabe Vorrang haben. Nutze die angebotenen Menüs, wenn du ohne Tastatur arbeitest.

| Eingabe | Aktion |
| --- | --- |
| **Strg+Z** | Rückgängig |
| **Strg+Umschalt+Z** oder **Strg+Y** | Wiederholen |
| **Strg+C / Strg+X / Strg+V** | Kopieren / Ausschneiden / Einfügen |
| **Strg+D** | Auswahl duplizieren |
| **Strg+A** | Alles im aktuellen Auswahlkontext auswählen |
| **Entf** | Auswahl löschen |
| **Strg+Klick / Shift+Klick** | Mehrfachauswahl |
| **Rechte Maustaste** in der Arbeitsfläche | Ansicht bedienen |
| **Mausrad** | Zoom |

| Begriff | Bedeutung im Studio |
| --- | --- |
| **Aktive Druckplatte** | Der aktuell ausgewählte Aufbau, auf den plattenbezogene Aktionen wirken |
| **Build** | Kennung der tatsächlich geladenen Softwareausgabe |
| **Druckprofil** | Prozesswerte für die geplante Druckqualität |
| **Engine** | Die Software, die vorbereitete Eingaben zu Druckbahnen verarbeitet |
| **Filamentprofil** | Materialeigenschaften und zugehörige ausführungsrelevante Materialangaben |
| **Galerie** | Modellbibliothek mit Dateien und Ordnern |
| **G-Code** | Befehlsdaten für einen konkreten Maschinenablauf |
| **HACS** | Auslieferungsweg für die Home-Assistant-Integration |
| **Malbereich** | Gesondert verwaltete materialgebundene Bearbeitung von Modellflächen |
| **Materialkanal** | Eindeutige Zuordnung einer Fläche zu einem verfügbaren Druckmaterial |
| **Profilüberschreibung** | Ein ausdrücklich gesetzter Wert anstelle des Profilstandards |
| **Projekt** | Gespeicherter bearbeitbarer Studio-Arbeitsstand |
| **Slice** | Ein Verarbeitungsergebnis mit Druckbahnen; getrennt vom physischen Druckstart |
| **Toolpath** | Räumlicher Verlauf einer Druckbahn |

Weiterlesen: [Funktionen im Detail](handbook/FEATURES.md) · [CAD-Beispiele](handbook/CAD_EXAMPLES.md) · [Slicer und Betrieb](Slicer-Server/README.md) · [Lizenzhinweise](../SOURCE_NOTICES.md)
