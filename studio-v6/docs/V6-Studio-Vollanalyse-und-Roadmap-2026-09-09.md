# V6-Studio – Vollanalyse und Roadmap

Stand: 9. September 2026, 21:19 Uhr (Europe/Berlin)  
Vorgeschlagener sichtbarer Modulname: **3D Ultimate Studio**  
Übergeordnetes Produkt gemäß Projektregel: **3D-Printer Control Center for Home Assistant**

## 1. Kurzfazit

Das V6-Studio ist bereits eine umfangreiche, eigenständige 3D-Druck-Arbeitsumgebung und deutlich mehr als ein Prototyp. Es vereint Druckertelemetrie, Kamera, Galerie, Drucker-SD-Karte, MakerWorld, einen WebGL-Arbeitsbereich, Multi-Plate-Projekte, Profil- und Materialverwaltung, Linux-Slicing, G-Code-Vorschau, Direktdruck, Aufgaben, Verlauf und Diagnose in einer Oberfläche.

Die aktuelle Version ist trotzdem noch als Beta einzuordnen. Vor einer stabilen Produktfreigabe fehlen insbesondere:

1. sichere und korrekt gefilterte Auditprotokollierung,
2. eine lückenlose Profil- und Materialkompatibilitätsprüfung,
3. die nachweisbare Anwendung des ausgewählten Prozessprofils,
4. Abbruch laufender Slicer-Jobs und eine echte Warteschlangensteuerung,
5. benannte, versionierte Projekte statt nur eines Browser-Arbeitsstands,
6. echte Browser-, Bedien-, Barrierefreiheits- und visuelle Regressionstests,
7. Bereinigung der vielen alten Versions-, Patch-, Backup- und Migrationsdateien.

## Aktueller Umsetzungsstand

Seit der ersten Analyse wurden folgende Punkte quellseitig, per vollständigem Gate und kontrolliertem HA-Deploy umgesetzt:

- Aufklappzustände von Materialsystemen, Spulen und Slots bleiben über Telemetrie-Renderzyklen erhalten. Die Lösung liegt im TypeScript-Zustandsmodell; es gibt keinen Reload-, DOM-Injection-, Prototype- oder MutationObserver-Patch.
- Der Galerie-Modellupload läuft verbindlich über 4-MiB-Chunks. Ein Live-Test mit einer 18.371.616 Byte großen 3MF wurde in fünf Chunks erfolgreich abgeschlossen; nur die Testkopie wurde danach entfernt.
- Klartextantworten und HTTP 413 erzeugen eine verständliche Fehlermeldung statt `Unexpected token M`.
- Die in der aktiven Galerie verlorenen Funktionen Sortierung, Raster-/Listenansicht, Mehrfachauswahl, Sammel-Kopieren/-Verschieben/-Löschen sowie ZIP-Import/-Export sind wieder in der aktuellen Galeriekomponente integriert.
- Inaktive Zuführlinien werden nicht mehr grau gezeichnet; nur der tatsächlich aktive Telemetriepfad bleibt grün sichtbar.
- Der offizielle, lokal installierte Bambu-A1-Systemkatalog 02.08.00.06 wurde auf exakt 84 für `@BBL A1` instanziierte Profile reduziert. Enthalten sind Bambu Lab, Generic, SUNLU, Polymaker, Overture und eSUN mit den offiziellen Profil-, Filament- und Temperaturkennungen.
- Der Hersteller- und Filamentkatalog ist live aktiv: 84 ausschließlich für `@BBL A1` freigegebene Systemprofile aus Bambu Studio 02.08.00.06, gruppiert nach Bambu Lab, Generic, Overture, Polymaker, SUNLU und eSUN.
- Der Fehler beim Öffnen/Anwenden der Filamenteinstellung war eine falsche Frontend-Route (`/slicer/direct-print/filament-color`). Sie wurde im TypeScript-Quellcode auf den registrierten Endpunkt `/slicer/filament-color` korrigiert und durch einen Regressionstest abgesichert.
- Die Zwei-Schritt-Sicherung wurde live ohne Druckeränderung geprüft: Eine abweichende Farbvorschau lieferte einen 120-Sekunden-Token; der Token wurde nicht bestätigt. Die anschließende Telemetrie meldete unverändert PETG, `GFG99`, `#161616`.
- Ein Materialquellen-Konflikt wird jetzt sichtbar erklärt: Ist die externe Spule real geladen, während die aktive Druckplatte noch `AMS / Materialsystem` nutzt, zeigt die Materialseite Material und Telemetriefarbe sowie einen direkten Weg zur bewussten Auswahl `Externe Spule` im Studio. Es gibt weiterhin kein automatisches Umschalten.
- Der zweite Aufklapppfad im Studio ist repariert: Hersteller-, Material- und Profilgruppen in der rechten Filament-Seitenleiste sowie die obere Profilgruppe behalten ihren nativen Offen-/Geschlossen-Zustand über reguläre Renderzyklen. Gleichzeitig wurde der fehlerhafte Austausch des inneren `.profilebar`-Abschnitts durch ein vollständiges äußeres `<details>` auf den korrekten `.profilebar-shell`-Austausch berichtigt.

Die sichtbare Umbenennung in **3D Ultimate Studio** ist sinnvoll. Sie darf aber zunächst ausschließlich die Anzeige betreffen. Technische IDs und Speicherpfade müssen erhalten bleiben, bis eine eigene, getestete Migration existiert.

## 2. Verifizierter Ist-Zustand

### Laufzeit

| Bereich | Verifizierter Stand |
| --- | --- |
| Home Assistant Core | 2026.9.1 |
| Supervisor | 2026.08.0 |
| Host | Debian 13, Docker 29.5.3 |
| V6-Version | 6.0.0-beta3 |
| V6-Provider | 1 aktiv, 1 Drucker |
| Galerie | 137 Dateien, 15 Ordner, rund 509 MB |
| Profile | 186 insgesamt: 11 Drucker, 9 Düsen, 27 Prozesse, 8 Druckplatten, 131 Filamente; zusätzlich 84 live aktive A1-Druckerprofile für Hersteller-/Filamentwahl |
| Slicing-Server | 0.1.0-alpha5, 3 Engines, zuletzt Bambu Studio |
| Slicer-Jobs | bis 100 gelistet, Abbruch nicht unterstützt |
| Druckaufträge | persistent; Warteschlangenausführung derzeit deaktiviert |
| Auditprotokoll | persistent, Obergrenze von 10.000 Einträgen erreicht |

### Aktuelles Qualitätsgate

Das Qualitätsgate vom 9. September 2026, 21:19 Uhr, war vollständig grün:

- 285 Python-Tests bestanden,
- 62 Frontend-Logiktests bestanden,
- TypeScript-Prüfung erfolgreich,
- Frontend-Build erfolgreich,
- Python-Compileall für die HA-Komponente erfolgreich,
- keine verbotenen DOM-/Prototype-/MutationObserver-Patches im Build.

Der kontrolliert deployte JavaScript-Build hat SHA-256 `5eca1eab436035b845476ddec5038f5ecdc79dc7ef51ce795daf5a6d1b447710`. Das serverseitige Rollback-Backup liegt unter `/homeassistant/pcc-backups/v6-frontend/20260909-211934`.

Diese Tests sind wertvoll, ersetzen aber keine reale Browser- und Bedienprüfung. Der Frontend-Testlauf weist selbst aus, dass kein synthetisches DOM und kein Browser verwendet wurde.

## 3. Was bereits gut gelöst ist

### Architektur und Sicherheit des Druckpfads

- Eigenständiger, local-first Betrieb ohne funktionale Abhängigkeit von einer separaten Bambu-Lab-HA-Integration.
- Slicing läuft auf dem Linux-Slicing-Server und nicht auf dem PC.
- Der eigentliche Slicer wird ohne Netzwerkzugriff gestartet.
- Dateinamen und Erweiterungen werden serverseitig validiert.
- Gerenderter G-Code wird auf Pflichtblöcke, Extrusion, ungelöste Platzhalter und wichtige Bambu-Sequenzen geprüft.
- Direktdruck ist zweistufig: erst vorbereiten und übertragen, danach separat und ausdrücklich drucken.
- Materialquelle und Ziel-Drucker werden im Slicerauftrag fest gebunden; es gibt keinen automatischen AMS-Fallback.
- Der Druckstart arbeitet mit Bestätigung, Prüfsumme und Telemetrieprüfung.

### Studio

- Ein gemeinsamer WebGL-Arbeitsbereich statt mehrerer konkurrierender Canvas-Instanzen.
- STL- und 3MF-Import, Multi-Plate-Unterstützung sowie Übergabe aus Galerie, SD-Karte und MakerWorld.
- Verschieben, Drehen, Skalieren, Zentrieren, auf Druckbett setzen, flach legen, duplizieren und löschen.
- Grundkörper: Würfel, Zylinder, Kugel, Kegel, Torus, Platte und First-Layer-Test.
- Mehrfachauswahl, Zwischenablage, Objektliste, ein- und ausklappbare Bedienbereiche.
- Plattengrenzen werden anhand der real transformierten Geometrie vor dem Upload geprüft.
- Große Geometrien werden kooperativ verarbeitet, damit die Oberfläche nicht unnötig blockiert.
- Reale G-Code-/Layer-Vorschau mit Strukturfiltern und Materialanalyse.

### Materialsysteme

- AMS Lite, AMS Gen 1, AMS 2 Pro, AMS HT, BMCU/BCMU-kompatible Systeme und externe Spule sind getrennt darstellbar.
- Systeme, Spulen und Slots sind aufklappbar.
- Belegte und tatsächlich aktive Zuführwege beruhen auf Druckertelemetrie.
- Externe Spule und AMS werden als verschiedene Materialquellen behandelt.
- Farbe und Filamentart können nach Vorschau und ausdrücklicher Bestätigung am Drucker gesetzt werden.
- RFID-geladene Werte werden gesperrt und nicht überschrieben.
- Manuell auswählbare Materialien sind bewusst begrenzt: AMS Lite PLA/PETG/PVA, externe Spule zusätzlich TPU.
- Unzuverlässige Restmengen werden nicht als scheinbar genauer Wert ausgegeben.

### Galerie und externe Quellen

- Der reparierte Galerie-Upload verwendet kleine Chunks und umgeht damit das 16-MiB-Request-Limit von Home Assistant.
- Fortschritt, übertragene Bytes und erfolgreiche Dateien werden angezeigt.
- Ordner, Suche, Vorschau, Umbenennen, Kopieren, Verschieben, Löschen, Download und Studio-Übergabe sind vorhanden.
- Die Drucker-SD-Karte bietet Lesen, Suche, Ordner, Upload, Umbenennen, Kopieren, Verschieben, Löschen und Download.
- MakerWorld unterstützt kombinierbare Suchbegriffe/Tags, Pagination, Sortierung, Modelle, Druckprofile, Bilder, Download, Galerie-Speicherung und Studio-Übergabe.

## 4. Kritische Punkte vor Produktreife

### P0-A – Auditprotokoll muss sofort gehärtet werden

Die Live-Prüfung hat zwei konkrete Fehler ergeben:

1. Kamera-Zustandsattribute werden vollständig in das persistente Auditprotokoll übernommen. Darin befinden sich auch Kamera-Zugriffstokens und tokenhaltige Bild-URLs. Die aktuelle Bereinigung erkennt nur den exakten Schlüssel `token`, nicht beispielsweise `access_token` oder Tokens innerhalb einer URL.
2. Die Zuordnung verwendet einfache Teilwortsuche. Dadurch wird `ams` auch in Namen wie Samsung oder TeamSpeak gefunden. Fremde Entitäten landen dann fälschlich in der Kategorie AMS.

Folgen:

- sensible Daten werden persistent gespeichert,
- der Puffer ist bereits mit 10.000 Einträgen voll,
- Kamera- und fremde Entitätsänderungen verdrängen nützliche V6-Ereignisse,
- 113 Warnungen enthalten überwiegend fremde oder falsch kategorisierte Zustände,
- unnötige Schreiblast und Diagnose-Rauschen entstehen.

Erforderlicher Fix:

- genaue V6-Entity-/Domain-Whitelist statt Teilwortsuche,
- Attribut-Whitelist statt vollständiger Zustandskopie,
- rekursive Schlüssel- und URL-Redaktion für Token, Secret, Passwort und Authorization,
- Drosselung/Deduplizierung schneller Kameraereignisse,
- sichere Migration oder Bereinigung des vorhandenen Auditbestands,
- betroffene Zugriffstokens nach der Bereinigung erneuern,
- Tests mit verschachtelten Secrets und tokenhaltigen URLs.

### P0-B – Profilwahl und tatsächliches Slicing müssen identisch sein

Im Studio sind 27 Prozessprofile auswählbar. Der aktuelle Linux-Slice-Pfad verwendet jedoch nachweisbar ein festes validiertes Basis-Prozessprofil je Düsendurchmesser und überträgt nur die sichtbaren Overrides für Haftung, Support, Layerhöhe sowie Außen-/Innenwandgeschwindigkeit. Das ausgewählte `process_profile_id` wird zwar gespeichert und mit der Platte übertragen, aber im nativen Slicerauftrag nicht vollständig als Prozessprofil materialisiert.

Damit kann die Oberfläche eine Profilwahl anzeigen, deren vollständige Werte nicht im Ergebnis landen. Das muss vor einer stabilen Freigabe fail-closed korrigiert werden.

Zusätzlich fehlen zentrale Prüfungen für:

- `slicing_supported`,
- AMS-Lite-Kompatibilität,
- gehärtete Düse bei abrasivem Filament,
- Temperaturgrenzen von Düse und Druckbett,
- erforderliches Gehäuse bei offenem A1,
- Filament ↔ Druckplatte,
- Filament ↔ Düse,
- Prozess ↔ Düse,
- Drucker ↔ verfügbare Slicer-Engine.

Ein aktuelles Live-Warnsignal bestätigt die Lücke: Die Vererbung des lokalen Profils `SUNLU PLA+ 2.0 @FF AD3 - Tara` kann wiederholt nicht aufgelöst werden, weil das angegebene Bambu-Basisprofil nicht gefunden wird. Der Katalog meldet insgesamt trotzdem einen gesunden Sync. Warnungen dieser Art müssen im Profilstatus sichtbar und vor dem Slicing verbindlich bewertet werden.

### P0-C – Betriebs- und Wiederherstellungszustand

Der Home-Assistant-Supervisor meldet:

- System nicht unterstützt: Betriebssystem,
- kein aktuelles vollständiges Home-Assistant-Backup.

Das V6-Dateibackup und ein vollständiges Systembackup sind nicht dasselbe. Vor größeren Umbauten oder einer Namensmigration sollte ein aktuelles Full Backup erstellt und die Debian-13-Unterstützung des Supervisor-Setups geklärt werden.

### P0-D – Abbruch und Warteschlange

- Der Slicing-Server meldet `job_cancellation: false`.
- Laufende oder blockierte Slicer-Jobs können nur beobachtet, nicht sauber abgebrochen werden.
- Die Druckwarteschlange ist persistent, ihre automatische Ausführung ist aber deaktiviert.

Erforderlich sind ein kooperativer Abbruch, Prozessgruppenbeendigung, Status `cancelled`, Aufräumregeln, UI-Bestätigung und Tests für Abbruch während Upload, Materialisierung, Slicing und Vorschauerzeugung. Die Druckwarteschlange sollte zunächst manuell bestätigte Ausführung pro Auftrag erhalten; automatischer Druckstart bleibt verboten.

## 5. Fehlende Produktfunktionen

### Priorität 1 – Projekte und Wiederherstellung

Derzeit wird genau ein aktiver Arbeitsstand in IndexedDB des jeweiligen Browsers gespeichert. Es fehlen:

- benannte Projekte,
- Projektliste,
- manuelle Speicherstände,
- automatische Versionen/Snapshots,
- Wiederherstellung nach Fehlbedienung,
- Vergleich zweier Versionen,
- Übernahme auf ein anderes Gerät/Browserprofil,
- serverseitige Sicherung im lokalen HA-System,
- klare Trennung zwischen Projektdatei, Slicerauftrag und Druckhistorie.

Empfehlung: ein lokaler Projektservice mit unveränderlichen Revisionen, Vorschaubild, Platte/Objekte/Profile/Materialplan und Referenzen auf Galerie-Assets. Der bestehende eine WebGL-Arbeitsbereich bleibt erhalten.

### Priorität 1 – Undo/Redo und Kernwerkzeuge

Für ein „Ultimate Studio“ fehlen mindestens:

- Undo/Redo mit sichtbarer Historie,
- Spiegeln an X/Y/Z,
- Schneiden an einer Ebene und Modell teilen,
- Teile zusammenfassen/trennen,
- Messwerkzeug für Abstand, Winkel und Abmessungen,
- Meshprüfung und geführte Reparatur,
- Text, Prägen und Gravieren,
- einfache Boolesche Operationen,
- Modifier-Meshes,
- objektbezogene Druckeinstellungen.

Undo/Redo und zerstörungsfreies Schneiden sollten vor komplexen CAD-Funktionen kommen.

### Priorität 1 – Vollständige Slicer-Einstellungen

Aktuell sichtbar sind Haftung, automatische Supports, Layerhöhe und Wandgeschwindigkeiten. Noch nicht als vollständige Studio-Steuerung vorhanden sind unter anderem:

- Wandanzahl und Wandreihenfolge,
- Infill-Dichte und -Muster,
- obere/untere Schichten,
- Linienbreiten,
- Nahtposition,
- Bügeln/Ironing,
- Brücken- und Überhangparameter,
- Support-Interface, Abstand und Dichte,
- Beschleunigung, Travel und Jerk-ähnliche Profile,
- Retraction, Wipe und Z-Hop,
- Flow Ratio und maximale Volumenrate,
- Kühlung und Mindestschichtzeit,
- variable Schichthöhe,
- per Objekt/Teil/Platte abweichende Einstellungen.

Diese Werte dürfen nicht einfach als neue Regler erfunden werden. Sie müssen aus dem tatsächlich materialisierten Profil kommen, validiert werden und im G-Code-Analysebericht wieder auffindbar sein.

### Priorität 1 – Malwerkzeuge und Vorschau

- Support malen, Blocker und Erzwinger,
- Naht malen,
- Material/Farbe auf Flächen statt nur Objekt/Teil zuweisen,
- variable Layerhöhe grafisch bearbeiten,
- automatische Problemmarker direkt am Modell,
- Vergleich „Profilwert → angewandter Wert → G-Code-Wert“.

### Priorität 2 – Galerie

Die bei der Analyse festgestellten Funktionsverluste der aktiven Galerieansicht sind am 9. September 2026 behoben worden: Sortierung, Raster-/Liste, Mehrfachauswahl, Sammelaktionen und ZIP-Import/-Export sind wieder vorhanden. Der normale Modellupload wurde zusätzlich mit einer realen Datei oberhalb des 16-MiB-Limits verifiziert.

Zusätzlich sinnvoll:

- Favoriten,
- Tags und Sammlungen,
- Duplikaterkennung per Prüfsumme,
- Versionen desselben Modells,
- Projekt-/Druckverknüpfungen,
- Filter nach Format, Material, Drucker und zuletzt gedruckt,
- Speicherverbrauch pro Ordner,
- Papierkorb mit Wiederherstellung statt sofortigem endgültigem Löschen.

### Priorität 2 – MakerWorld

Die API liefert Lizenzdaten, die Oberfläche zeigt sie jedoch nicht. Gleichzeitig wird bei jedem Ersteller pauschal ein Verifizierungs-Häkchen angezeigt, obwohl das Datenmodell keinen verifizierten Status enthält.

Erforderlich:

- Lizenz und Nutzungsbedingungen sichtbar vor Download/Speicherung,
- Verifizierungs-Häkchen nur bei echter Quellinformation,
- Zielordner auswählbar statt automatisch erster Galerieordner,
- Kompatibilitätsfilter für realen Ziel-Drucker, Düse und Materialsystem,
- klare Anzeige, welche MakerWorld-Werte übernommen und welche ersetzt werden,
- Caching mit Herkunft, Abrufzeit und Quell-URL,
- Fehlerstatus bei unvollständigen oder entfernten Druckprofilen.

### Priorität 2 – Materialverwaltung

Das aktuelle System soll weiterhin keine Restmengen erfinden. Sinnvoll wäre eine optionale, nachvollziehbare Inventarverwaltung:

- Startgewicht und Leerrollengewicht manuell erfassen,
- Verbrauch aus erfolgreich analysiertem G-Code abziehen,
- RFID-Wert und berechneten Wert getrennt anzeigen,
- Unsicherheit/Vertrauensgrad sichtbar machen,
- Trocknungsstatus und Zeitstempel,
- Rollenwechsel-Historie,
- Warnung bei voraussichtlich zu wenig Material,
- Lagerort, Hersteller, Charge und Kaufpreis,
- Verbrauchs- und Kostenstatistik pro Projekt.

### Priorität 2 – Multi-Plate und Auftragsplanung

- mehrere Platten gesammelt slicen,
- ausgewählte Platten in gewünschter Reihenfolge vorbereiten,
- Profile und Materialplan plattenspezifisch vergleichen,
- Platte duplizieren und Vorlagen speichern,
- Material-/Zeit-/Kostenvergleich vor dem Druck,
- Warteschlange mit manueller Freigabe jedes Druckstarts,
- automatische Prüfung, ob der vorherige Druck wirklich entfernt wurde, ohne daraus einen automatischen Start abzuleiten.

### Priorität 3 – Wartung und Assistenz

- geführte Druckerwartung mit bestätigten, vom Drucker unterstützten Schritten,
- Düsenwechsel-Assistent mit Profilabgleich,
- Kalibrierhistorie,
- Wartungszähler für Düse, Wischer, Cutter und Schmierung,
- HMS-/Fehlercode-Wissensbasis mit lokal gespeicherten Handlungsanweisungen,
- Benachrichtigung bei Druckende, Störung und Materialmangel über Home Assistant,
- Energie- und Kostenmessung, wenn echte Sensoren verfügbar sind.

Lade-, Entlade-, Heiz- oder Bewegungsbefehle sollten erst ergänzt werden, wenn der jeweilige Befehl verifiziert, in den Fähigkeiten des Druckers gemeldet und mit Sicherheitsbestätigung geschützt ist.

## 6. UX-, Qualitäts- und Wartbarkeitsanalyse

### Navigation und Bedienung

Die linke Navigation ist grundsätzlich schlüssig: Steuerzentrale, Galerie, Studio, Materialsysteme, Profile, Aufgaben, Verlauf, System und Slicing-Server. Eine zusätzliche obere Hauptnavigation ist nicht vorhanden. Das entspricht der bisherigen Projektregel.

Verbesserungen:

- „3D-Studio“ in der Navigation kurz als „Studio“ benennen,
- komplexe rechte Studioleiste in klar benannte Akkordeons gliedern,
- aktive Platte, Drucker, Düse, Materialquelle und Prozess als kompakte Statuszeile zeigen,
- ungültige Kombinationen direkt an der Auswahl erklären,
- globale Suche/Kommandopalette für Modell, Projekt, Profil und Auftrag,
- einheitliche leere Zustände, Fehlertexte und Wiederholen-Aktionen.

### Barrierefreiheit und Geräte

Responsive CSS ist vorhanden, aber es fehlen automatisierte Nachweise für:

- vollständige Tastaturbedienung,
- Fokusfallen und Fokusrückgabe in Dialogen,
- Screenreader-Namen und Dialogrollen,
- Kontrast,
- Zoom und große Schrift,
- Touch-Ziele auf Tablet und Smartphone,
- Hoch-/Querformat,
- HA Hell-/Dunkel-Themes.

Empfehlung: Playwright plus axe, definierte Desktop-/Tablet-/Mobil-Viewports und Screenshots für Kernabläufe.

### Test- und Releaseinfrastruktur

Die vorhandenen Python- und Logiktests sind stark. Die GitHub-Automatisierung führt derzeit jedoch nur HACS- und Hassfest-Prüfungen aus. V6-Typecheck, Build, Python-Tests und Frontend-Logiktests sind nicht als verpflichtender CI-Workflow erkennbar.

Es fehlen:

- CI für das komplette V6-Quality-Gate,
- echter Browser-E2E-Test von Galerie → Studio → Slicing → Vorbereitung,
- Browser-Test für großen Chunk-Upload,
- visuelle Regressionstests,
- Barrierefreiheitstest,
- Performancebudgets,
- Live-API-Smoke-Test gegen eine isolierte Testinstanz,
- Test für Backup und Rollback,
- Test für Versions-/Branding-Konsistenz.

### Technische Schulden

Der V6-Stamm enthält 176 Einträge, das Frontend 184 Dateien. Darunter befinden sich viele alte `v2`/`v3`/`v4`/`v9`-Varianten, winzige Weiterleitungsdateien, leere oder 11 Byte große Platzhalter, `before-*`-Backups, temporäre Snippets sowie zahlreiche einmalige Patch- und Migrationsskripte. Auch im deployten Backend liegen alte und neue View-/Repository-Versionen parallel.

Das ist aktuell durch Import-Weiterleitungen beherrschbar, erhöht aber das Risiko jeder größeren Änderung und insbesondere einer Umbenennung.

Empfehlung:

1. aktiven Importgraph automatisch aus dem Build-Metafile bestimmen,
2. inaktive Dateien zunächst nur in ein versioniertes Archiv verschieben,
3. Tests und Bundle-Prüfsumme vergleichen,
4. aktive Komponenten auf eindeutige Namen ohne Versionssuffix vereinheitlichen,
5. das 165-KB-Mega-Workspace-Modul in klar getrennte Controller zerlegen,
6. Migrations- und Patchskripte aus dem Produktstamm in ein Archiv verschieben,
7. README, Roadmap und API-Dokumentation auf den tatsächlich deployten Stand aktualisieren.

## 7. Umbenennung zu „3D Ultimate Studio“

### Empfohlenes Namensmodell

| Ebene | Name |
| --- | --- |
| Gesamtprodukt | 3D-Printer Control Center for Home Assistant |
| Studio-Modul | 3D Ultimate Studio |
| Navigation | Studio |
| Versionsanzeige | Version 6.0.0-beta3, nur unter System/Über |
| Technische V6-Identität | zunächst unverändert |

Damit wird die verbindliche Projektbezeichnung nicht gebrochen. „3D Ultimate Studio“ bezeichnet die leistungsfähige Arbeitsoberfläche innerhalb des Control Centers.

### Phase 1 – sichtbares Branding, geringes Risiko

Ändern:

- sichtbare Überschriften,
- Navigationslabel,
- HA-Anzeigename und Einrichtungsdialog,
- Kartenbeschreibung,
- Build-Produktbezeichnung,
- README/Changelog/Architekturtext,
- System-/Über-Seite mit sauberer Versionsanzeige.

Unverändert lassen:

- HA-Domain `ultimate_3d_studio_v6`,
- API-Basis `/api/ultimate_3d_studio_v6/v1`,
- Custom-Element-Namen,
- IndexedDB- und LocalStorage-Keys,
- Galerie- und Audit-Store-Keys,
- Deployverzeichnisse,
- Config-Entry- und Entity-IDs,
- Ereignisnamen,
- bestehende Cache-Buster-/Ressourcenpfade.

Alle sichtbaren Namen sollten aus einer zentralen Branding-Konstante kommen, damit künftig keine verstreuten String-Ersetzungen nötig sind.

### Phase 2 – Produktreife

Erst nach P0-Fixes:

- vollständiges Browser-E2E-Gate,
- visuelle Regression,
- Dokumentation der unterstützten Drucker/Materialien,
- Projektservice und Undo/Redo,
- Profilkompatibilitätsmatrix,
- Release-Checkliste.

### Phase 3 – technische Migration, nur wenn wirklich nötig

Eine spätere Änderung der Domain oder internen IDs wäre eine echte Datenmigration. Dafür wären Alias- und Migrationslogik für Config Entries, Entity Registry, LocalStorage, IndexedDB, HA Stores, URLs und Dashboards nötig. Ein einfaches globales Umbenennen würde bestehende Konfiguration, Projekte, Ressourcen und Karten beschädigen und ist deshalb ausdrücklich nicht empfohlen.

## 8. Empfohlene Reihenfolge der nächsten Releases

### Release A – Sicherheits- und Diagnose-Härtung

1. Audit-Redaktion und exakte Filterung.
2. vorhandenen Auditbestand nach Backup sicher bereinigen.
3. Kamera-/Entitätsereignisse drosseln.
4. vollständiges HA-Backup und Rollbacknachweis.
5. Live-Smoke-Test ohne Druckstart.

### Release B – Profilwahrheit

1. Prozessprofil tatsächlich materialisieren.
2. zentrale Kompatibilitätsmatrix und Fail-closed-Preflight.
3. SUNLU-Vererbungswarnung beheben.
4. im UI „gewählt / angewandt / G-Code bestätigt“ getrennt zeigen.
5. Referenz-Slices für 0,2 / 0,4 / 0,6 / 0,8 mm und erlaubte Materialien.

### Release C – 3D Ultimate Studio Branding

1. zentrale Branding-Konstante.
2. sichtbare Namen umstellen.
3. interne IDs unverändert lassen.
4. Browser-, Cache-, Neustart- und Rollbacktest.
5. deutsche und englische Release Notes.

### Release D – Projekte und Undo/Redo

1. benannte Projekte und Revisionen.
2. serverseitige lokale Speicherung.
3. Undo/Redo.
4. Galerie-Projektverknüpfung.
5. Wiederherstellungstest.

### Release E – Ultimate-Werkzeuge

1. Spiegeln, Schneiden, Messen, Reparieren.
2. vollständige Prozessparameter.
3. variable Layerhöhe.
4. Support-/Naht-/Material-Malwerkzeuge.
5. Sammel-Slicing und manuell freigegebene Warteschlange.

## 9. Entscheidung

**Ja, der Name „3D Ultimate Studio“ passt inzwischen.** Das System hat dafür bereits die funktionale Breite. Der Name sollte jetzt als Zielmarke eingeführt werden, aber nicht als Behauptung, dass die Beta schon vollständig produktionsreif ist.

Der nächste sichere Schritt ist nicht ein globales Rename, sondern:

1. Audit-Sicherheitsfehler reparieren,
2. Profilwahrheit herstellen,
3. sichtbares Branding kontrolliert umstellen,
4. interne V6-Kompatibilität vollständig bewahren.

Bis zur ausdrücklichen Freigabe wurden im Rahmen dieser Analyse keine Projekt-, Home-Assistant-, Drucker- oder Slicerdateien verändert und kein Druckauftrag ausgelöst.

## 10. Fortschrittsnachtrag 2026-09-10 – Galerie-3MF und Düsenmatrix

### Abgeschlossen und live bereitgestellt

- Galerie- und Slicerpfad unterstützen jetzt auch 3MF-Produktionsmodelle, deren logisches Hauptobjekt seine Meshes über `components` und `p:path` aus weiteren `.model`-Dateien bezieht.
- Logische Objekt-ID, verschachtelte Materialfarbe sowie verkettete Komponenten- und Build-Transformationen bleiben erhalten.
- Archivpfade werden normalisiert; Traversal, Zyklen, übergroße Graphen und zu tiefe Verknüpfungen werden fail-closed abgewiesen.
- Bei genau einem verfügbaren Filament wird ein noch nicht explizit zugeordnetes Objekt sicher Materialkanal 1 zugewiesen. Für mehrere Kanäle bleibt eine eindeutige Objektzuordnung Pflicht.
- Liegt die gemeinsam transformierte Objektgruppe außerhalb der Druckplatte, wird sie als Gruppe mittig in X/Y platziert. Relative Bauteilpositionen bleiben erhalten; ein zu großes Modell wird abgewiesen.
- Der geprüfte Fall `Deko/obj_1_Körper10.3mf` enthält 3.646 Dreiecke und misst 142 × 100,5 × 80 mm. Nach der Platzierung liegt er vollständig bei X 57…199, Y 77,75…178,25 und Z 0…80 mm.
- Die externe Spule wurde im Native-Slice als SUNLU High Speed Matte PETG, Filament-ID `GFG99`, Farbe `#000000` verarbeitet. Damit ist der zuvor rote Modellfallback für diesen Pfad nicht mehr maßgeblich.

### Verifikation

| Düse | Native Basis | Ergebnis | Artefaktgröße |
| --- | --- | --- | ---: |
| 0,2 mm | Bambu Lab A1 0.2 / 0,10-mm-Prozessvertrag | erfolgreich | 4.951.243 Byte |
| 0,4 mm | Bambu Lab A1 0.4 / 0,20 mm Standard | erfolgreich | 3.673.951 Byte |
| 0,6 mm | Bambu Lab A1 0.6 / 0,30 mm Strength | erfolgreich | 3.419.715 Byte |
| 0,8 mm | Bambu Lab A1 0.8 / 0,40 mm Standard | erfolgreich | 2.144.280 Byte |

Alle vier Läufe nutzten dasselbe reale Galerieobjekt. Es wurde kein Druckauftrag erzeugt oder an den Drucker übertragen.

Das vollständige Qualitätsgate war nach jeder finalen Korrektur grün: 64 Frontend-Tests, 311 Python-Tests einschließlich der neuen Graph-, Ein-Kanal- und Plattenplatzierungsregressionen, TypeScript-/Frontend-Build, Home-Assistant-Build, Python-Compileall und Quellrichtlinienprüfung ohne verbotene DOM-/Runtime-Patches.

### Backups und Aktivierung

- kanonische Quellbackups unter `v6/backups/2026-09-10T12-30-00-linked-production-3mf`, `2026-09-10T13-08-00-single-filament-assignment` und `2026-09-10T14-25-00-linked-3mf-placement`
- Home-Assistant-Rollbackbackups unter `/homeassistant/pcc-backups/v6-linked-production-3mf/`
- Native-Slicer-Rollbackbackups unter `/var/lib/homeassistant/3d-printer-slicing-server/backups/`
- Native-Materializer ist aktiv, da er pro Slice neu geladen wird.
- Das neue Home-Assistant-Galerie-Analysemodul ist auf Datenträger bereitgestellt, benötigt aber noch einen ausdrücklich freigegebenen HA-Core-Neustart zum Laden in den laufenden Prozess.

### Nächster Roadmap-Schritt

1. HA-Core kontrolliert neu starten, anschließend Galerie-Inspect und Studio-Handoff des realen verknüpften 3MF read-only prüfen.
2. Danach Release B mit der UI-Anzeige „gewählt / angewandt / im Artefakt bestätigt“ abschließen.
3. Anschließend das sichtbare Branding „3D Ultimate Studio“ zentral einführen; interne Domain, APIs, Speicher- und Entity-IDs bleiben unverändert.
4. Danach Release D: benannte Projekte, Revisionen sowie Undo/Redo.

## 11. Fortschrittsnachtrag 2026-09-10 – Release B/C und Release D

### Release B und C abgeschlossen

- Die Profilwahrheit wird im Frontend getrennt als „gewählt“, „im Slicer angewandt“ und „im Artefakt bestätigt“ angezeigt.
- Das sichtbare Produktbranding lautet „3D Ultimate Studio“ beziehungsweise „3D Ultimate Slicer“.
- Interne Domain, API-Pfade, Custom-Element-Namen, Karten-ID und Speicher-IDs blieben unverändert.
- Beide Releases wurden mit vollständigem Qualitätsgate, Quell- und Live-Backups sowie kontrolliertem Frontend-Deploy abgeschlossen.

### Release D – aktueller kontrollierter Stand

- Der aktive Workspace-/Persistenzpfad und die HA-Registrierung wurden vollständig inventarisiert.
- Eine persistente HA-Projektablage wurde als eigener `Store` implementiert:
  - maximal 40 benannte Projekte,
  - maximal 30 Revisionen je Projekt,
  - maximal 12 MiB je JSON-Snapshot,
  - finite JSON-Werte und Snapshot-Version 1 werden strikt validiert,
  - Schreibzugriffe sind adminpflichtig,
  - veraltete Schreibstände werden mit einer optimistischen Revisionsprüfung und HTTP 409 fail-closed abgewiesen,
  - Wiederherstellen einer alten Revision erzeugt eine neue Revision und überschreibt die Historie nicht.
- Neue authentifizierte Endpunkte sind vorbereitet: Projektliste/Erstellen, Laden/Speichern/Löschen, Revisionsliste und Wiederherstellung.
- Der Frontend-Vertrag serialisiert `Float32Array`-Geometrie explizit und rekonstruiert sie beim Laden.
- Echte Modellzustands-Historie für Undo/Redo ist implementiert und auf 20 Zustände begrenzt. Redo wird nach einer neuen Änderung korrekt verworfen; laufendes Slicing sperrt Undo/Redo.
- Im Studio-Quellstand sind HA-Projekt öffnen/speichern sowie Strg+Z, Strg+Umschalt+Z und Strg+Y angebunden. Das Öffnen verwendet einen echten Dialog und ersetzt den lokalen Zustand erst nach erfolgreichem Serverabruf.

### Qualität und Deployment-Haltepunkt

- Kanonisches Quellbackup: `v6/backups/2026-09-10T17-30-00-project-revisions-release-d`.
- HA-Live-Backup: `/homeassistant/pcc-backups/v6-backend/20260910-2136-project-revisions`.
- Die drei Backenddateien wurden mit SHA-256-Verifikation auf HA bereitgestellt und per `compileall` geprüft.
- Das vollständige V6-Gate ist grün: Frontendtests/TypeScript/Build, Python-Tests, HA-Build, Compileall und Quellrichtlinie ohne DOM-/Runtime-Patches.
- Der gemeinsame neue Frontend-Build hat SHA-256 `901a846f94fe33b3ff970a037b1a3e0cad8ec54e1b344952a2f8228ea69fa951`.
- HA Core wurde nicht neu gestartet. Der read-only Routen-Probe liefert daher erwartungsgemäß noch HTTP 404.
- Das neue Frontend wurde aus Sicherheitsgründen noch nicht live geschaltet, damit keine sichtbaren Projektbuttons gegen noch nicht registrierte Backendrouten laufen.

### Nächster kontrollierter Schritt

1. ausdrückliche Freigabe für genau einen HA-Core-Neustart,
2. danach Projekt-API read-only prüfen,
3. neuen Frontend-Build mit Rollbackbackup deployen,
4. Projekt anlegen, Revision erhöhen, Konfliktfall und Wiederherstellung ohne Druckauftrag testen,
5. anschließend Galerie-Projektverknüpfung und Release-E-Werkzeuge fortsetzen.

### Aktivierungsprüfung 2026-09-10, 21:43–21:46 Uhr

- Der freigegebene HA-Core-Neustart wurde nach erfolgreichem `ha core check` genau einmal kontrolliert ausgeführt.
- HA Core 2026.9.1 kam sauber online; die neue Projektliste antwortete mit HTTP 200.
- Ein temporäres, eindeutig benanntes Smoke-Testprojekt wurde angelegt. Dabei deckte der Live-Test auf, dass `HomeAssistantView` den vorgesehenen `PUT`-Handler nicht registrierte und HTTP 405 lieferte.
- Der Testdatensatz wurde anschließend erfolgreich gelöscht; die Projektliste ist wieder leer.
- Der Speichervertrag wurde auf authentifiziertes `POST` am einzelnen Projektpfad korrigiert. Frontend, Backend-Test und Vollgate sind erneut grün.
- Der korrigierte Backendstand liegt kompiliert auf HA; Rollbackbackup: `/homeassistant/pcc-backups/v6-backend/20260910-2146-project-post-contract`.
- Das zwischenzeitlich bereitgestellte Projektfrontend wurde kontrolliert auf den vorigen Live-Build mit SHA-256 `228c277502e6fa57d89c8dcd96e1ec44a945aeaab10dc2ebddf037b2c6549538` zurückgerollt. Damit bleibt live keine halb aktive Projektfunktion sichtbar.
- Für das Laden der korrigierten POST-Methodentabelle ist ein weiterer ausdrücklich freigegebener HA-Core-Neustart erforderlich. Erst danach folgt der vollständige Create/Save/409/Restore/Delete-Smoke-Test und das finale Frontend-Deploy.

### Zweite Aktivierung und Abschlussprüfung 2026-09-10, 22:00–22:03 Uhr

- Der ausdrücklich freigegebene zweite HA-Core-Neustart wurde nach erfolgreichem `ha core check` genau einmal kontrolliert ausgeführt. HA Core 2026.9.1 ist wieder online; ein weiterer Neustart erfolgte nicht.
- Der zuvor gemeldete Slicing-Abbruch wegen fehlender validierter Temperaturgrenzen wurde an der Profilquelle korrigiert. Ein ausgewähltes A1-Cloud-Druckerprofil erhält fehlende Hardwaregrenzen ausschließlich von genau einem lokalen A1-Profil mit exakt gleichem Düsendurchmesser. Für den aktuellen 0,4-mm-Fall ist die Autorität `local.printer.bambu_a1_0_4` mit 300 °C maximaler Düsen- und 100 °C maximaler Betttemperatur.
- Es gibt keinen allgemeinen Temperaturfallback: nicht eindeutige, fehlende oder nicht exakt zur Düse passende Autoritäten werden weiterhin fail-closed abgewiesen. Prozess-, Filament- und benutzerdefinierte Maschinenfelder werden nicht als Hardwaregrenzen missbraucht.
- Der Live-Projektvertrag wurde vollständig geprüft: Erstellen HTTP 200/Revision 1, Speichern per POST HTTP 200/Revision 2, veraltetes Speichern HTTP 409 `revision_conflict`, zwei Revisionen lesbar, Wiederherstellung als neue Revision 3, Löschen HTTP 200. Der temporäre Testdatensatz wurde vollständig entfernt.
- Das finale Release-D-Frontend ist kontrolliert aktiv. Live-SHA-256: JavaScript `647ad171528a1ba7963b4fe338de82631b4ea40a8752daff8186cc5703de2469`, CSS `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`. Rollbackbackup: `/homeassistant/pcc-backups/v6-frontend/20260910-220318`.
- Die ausgelieferte JavaScript-Datei enthält die erwarteten Funktionen „Projekt auf HA speichern“, „HA-Projekt öffnen“, „Rückgängig (Strg+Z)“ und den Projekt-API-Pfad. Die letzten 300 Core-Logzeilen enthalten keinen V6-Fehler.
- Das vollständige V6-Qualitätsgate war vor dem Deploy grün. Es wurde weder ein neuer Slicing-Job noch ein Druckauftrag gestartet.

### Fortsetzung der Roadmap

1. Galerieobjekte mit benannten HA-Projekten verknüpfen und Öffnen/Speichern/Wiederherstellen durchgängig absichern.
2. Release E mit Spiegeln, Schneiden, Messen und Reparieren beginnen.
3. Danach vollständige Prozessparameter, variable Layerhöhe sowie Support-/Naht-/Material-Malwerkzeuge schrittweise mit denselben Sicherheitsgates ergänzen.

## 12. Fortschrittsnachtrag 2026-09-10 – Galerie/Projekt und Release E, Stufe 1

### Galerie-Projektverknüpfung abgeschlossen

- Galerie-3MF werden serverseitig über ihre `asset_id` an das Studio übergeben; große Dateien werden für den Handoff nicht erneut durch den Browser geladen.
- Das Öffnen eines Galerieprojekts setzt den bisherigen Workspace synchron zurück, bevor die asynchrone Modellinspektion beginnt. Alte Platten, Slicer-Jobs, Materialzuordnungen und Vorschaudaten können dadurch nicht in das neue Projekt hineinragen.
- Lazy Preview, Galeriecache, Projektname, Multi-Plate-Informationen und der reparierte 4-MiB-Chunk-Upload bleiben erhalten.
- Die Galerie-/Projekt-, Direktdruck- und HMS-Regressionsverträge sind Bestandteil des vollständigen Gates.

### Release E – Spiegeln und Messen live

- Das aktive Mega-Studio bietet „Spiegeln X“, „Spiegeln Y“, „Spiegeln Z“ und „Messen“ sowohl in der Werkzeugleiste als auch im Objektmenü.
- Spiegeln arbeitet auf den realen Meshpunkten um die lokale Geometriemitte. Die Dreiecksreihenfolge wird nach der Reflexion umgekehrt und die Normalen werden neu berechnet; negative Skalierung dient nicht als Abkürzung.
- Messen wertet die tatsächlich transformierten Eckpunkte aller sichtbaren ausgewählten Objekte aus und meldet X/Y/Z-Ausdehnung, Objektzahl und Dreiecksanzahl.
- Die Änderungen laufen über den bestehenden Quellzustand, Undo/Redo, IndexedDB-Persistenz und HA-Projektrevisionen. Es gibt keine DOM-, Prototyp-, Runtime- oder Reload-Patches.
- Quellbackup: `v6/backups/2026-09-10T22-35-00-release-e-mirror-measure`.
- Das vollständige Gate ist grün: 68 Frontendtests, 317 Python-Tests, TypeScript-/Frontend-Build, HA-Core-Build, `compileall` und Quellrichtlinie.
- Live-JavaScript-SHA-256: `f7bdd4351ccb57b20a90e1abdfc2a937f95a5495b5054cd9a4fbf5790f43e381`.
- Live-Rollbackbackup: `/homeassistant/pcc-backups/v6-frontend/20260910-223012`.
- Datei- und Fehlerprotokollkontrolle: Alle neuen UI-/Audit-Marker sind im ausgelieferten Bundle vorhanden; die letzten 300 Core-Logzeilen enthalten keinen V6-Fehler.
- Kein HA-Core-Neustart, kein Slicing-Job und kein Druckauftrag wurden für diese Stufe ausgelöst.

### Nächster kontrollierter Schritt

1. Mesh-Reparatur zunächst read-only analysieren und nur eindeutig sichere Operationen anbieten, beispielsweise degenerierte/duplizierte Dreiecke und ungültige Zahlen erkennen.
2. Geometrisches Teilen mit expliziter Schnittebene, Vorschau und Bestätigung implementieren; bestehendes Zwischenablage-„Ausschneiden“ bleibt davon getrennt.
3. Danach Prozessparameter und variable Layerhöhe erweitern.

## 13. Fortschrittsnachtrag 2026-09-10 – Release E, sichere Mesh-Reparatur

### Abgeschlossen und live

- Das Objektmenü und die Werkzeugleiste enthalten jetzt „Mesh prüfen / reparieren“ beziehungsweise „Mesh prüfen“.
- Die erste Stufe ist immer read-only und zählt pro ausgewähltem sichtbarem Mesh:
  - Dreiecke mit nicht-endlichen Koordinaten,
  - exakt flächenlose Dreiecke,
  - exakte Dreiecksduplikate unabhängig von ihrer Laufrichtung,
  - offene Kanten,
  - nicht-manifold Kanten.
- Ohne sicher reparierbaren Befund bleibt die Geometrie unverändert. Offene und nicht-manifold Kanten werden ausschließlich gemeldet.
- Vor jeder Änderung erscheint ein eigener Vorschau- und Bestätigungsdialog mit den Befunden je Objekt. Abbrechen lässt die Geometrie vollständig unverändert.
- Nach Bestätigung werden ausschließlich die drei eindeutig sicheren Fehlerklassen entfernt. Löcher werden nicht automatisch geschlossen und es gibt keine heuristische Topologieänderung.
- Würde die Bereinigung ein vollständig leeres Mesh erzeugen, wird die Änderung fail-safe nicht angewandt.
- Reparierte Meshes verwenden neu berechnete Grenzen und Normalen und laufen über die bestehende Undo/Redo-, IndexedDB- und HA-Projektrevisionskette.

### Qualität und Deployment

- Kanonisches Quellbackup: `v6/backups/2026-09-10T22-50-00-release-e-safe-mesh-repair`.
- Vollständiges Gate grün: 72 Frontendtests, 317 Python-Tests, TypeScript-/Frontend-Build, HA-Core-Build, `compileall` und Quellrichtlinie ohne DOM-/Runtime-/Reload-Patches.
- Live-JavaScript-SHA-256: `6e5453f74ec5c79a012836fd9912fd5a3b3fd9e302bb4cb5f029105530ed6fff`.
- Live-Rollbackbackup: `/homeassistant/pcc-backups/v6-frontend/20260910-224236`.
- Die Live-Datei enthält Diagnose-, Bestätigungs- und Auditmarker; die letzten 300 Core-Logzeilen enthalten keinen V6-Fehler.
- Kein HA-Core-Neustart, kein Slicing-Job und kein Druckauftrag wurden ausgelöst.

### Nächster kontrollierter Schritt

1. Geometrisches Teilen mit definierter X/Y/Z-Schnittebene implementieren.
2. Beide resultierenden Seiten vor der Übernahme als getrennte Objekte anzeigen und eine ausdrückliche Bestätigung verlangen.
3. Offene Schnittflächen zunächst nicht automatisch schließen; ein Modell mit notwendiger Kappenbildung wird fail-closed behandelt, bis eine robuste triangulierte Kappenlogik separat geprüft ist.

## 14. Fortschrittsnachtrag 2026-09-10 – Release E, sichere Ebenenteilung

### Abgeschlossen und live

- Werkzeugleiste und Objektmenü bieten jetzt ein eigenständiges „Geometrisch teilen“. Das bisherige Zwischenablage-„Ausschneiden“ bleibt davon vollständig getrennt.
- Die Teilung verlangt genau ein sichtbares Objekt sowie eine explizite X-, Y- oder Z-Ebene mit Position in Weltkoordinaten.
- „Teilung prüfen“ verändert das Modell nicht. Die Vorschau zeigt die negative und positive Seite als zwei getrennte Ergebnisobjekte mit ihren jeweiligen Dreieckszahlen.
- Erst „Als zwei Objekte übernehmen“ ersetzt nach ausdrücklicher Bestätigung das Original durch zwei Objekte. Material-/Plattenzuordnung, Auswahl, Auditspur, Undo/Redo, IndexedDB-Persistenz und HA-Projektrevisionen bleiben erhalten.
- Die sichere Stufe trennt ausschließlich bereits durch die Ebene getrennte Geometriegruppen. Sobald ein Dreieck die Ebene kreuzt oder berührt, wird die Übernahme fail-closed gesperrt und die noch nicht freigegebene Kappenbildung klar benannt.
- Es gibt keine heuristische Schnittflächenfüllung und keine ungeprüfte Topologieänderung.

### Qualität und Deployment

- Kanonisches Quellbackup: `v6/backups/2026-09-10T23-05-00-release-e-safe-plane-split`.
- Das erste Gate erkannte ausschließlich einen TypeScript-Typfehler bei einem unveränderlichen Punkt-Tupel; es fand kein Deploy statt. Der Quelltyp wurde gezielt korrigiert und das vollständige Gate erneut ausgeführt.
- Finales Vollgate grün: 76 Frontendtests, 317 Python-Tests, TypeScript-/Frontend-Build, HA-Core-Build, `compileall` und Quellrichtlinie ohne DOM-, Prototyp-, Runtime- oder Reload-Patches.
- Live-JavaScript-SHA-256: `d547a10d39ce37a329d72962551aee1b644a96fb019a0add2e2aa08e0fdb22a9`.
- Live-CSS-SHA-256: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.
- Live-Buildmanifest-SHA-256: `3ed8bb7c4da7f22d50253139fba21b4bab54359d93ac22722256d622e62e715a`.
- Live-Rollbackbackup: `/homeassistant/pcc-backups/v6-frontend/20260910-225527`.
- Die unabhängige Live-Prüfung bestätigt alle drei Hashes sowie sämtliche Bedien-, Sperr- und Auditmarker. Die letzten 300 Core-Logzeilen enthalten keinen V6-Fehler.
- Kein HA-Core-Neustart, kein Slicing-Job und kein Druckauftrag wurden ausgelöst.

### Nächster kontrollierter Schritt

1. Eine robuste, triangulierte Kappen-Engine für echte durchtrennte Volumenkörper separat entwerfen und mit schwierigen Konturen testen; bis zur Freigabe bleibt dieser Fall gesperrt.
2. Prozessparameter und variable Layerhöhe ausbauen.
3. Support-, Naht- und Material-Malwerkzeuge anschließend mit Vorschau, Bestätigung, Persistenz und denselben Sicherheitsgates ergänzen.

## 15. Fortschrittsnachtrag 2026-09-11 – Prozesswertnachweise

### Numerische Overrides korrigiert und aktiviert

- Die G-Code-Bestätigung berücksichtigt jetzt manuelle Schichthöhe sowie Außen-/Innenwandgeschwindigkeit und verlangt für diese Änderungen zusätzlich native Materialisierungswerte.
- 24 Regressionstests prüfen korrekte und alte Werte, fehlende/falsche Nachweise, zusätzliche Schlüssel, Materialabweichungen und Vertragsabweichungen.
- Das vollständige V6-Gate war grün. Der erste Fix wurde nach Freigabe aktiviert; HA-Start wurde um 07:12 Uhr deutscher Zeit nachgewiesen.
- Rückfallstand: /homeassistant/pcc-backups/v6-backend/20260911-051015-numeric-override-proof.

### Einzelanzeige im aktiven Slicer-Jobdialog bereitgestellt

- Drei Parameter werden einzeln angezeigt: Schichthöhe, Außenwand und Innenwand.
- Spalten: Profilwert, angeforderter Wert, angewandter Laufzeitwert, G-Code-Wert sowie Einzelstatus.
- Manuelle Änderungen sind gekennzeichnet. Fehlende Werte werden nicht erfunden; nicht separat bekannte geerbte Profilwerte bleiben „Nicht nachgewiesen“.
- Einzelstatus: bestätigt, Abweichung oder nicht nachgewiesen. Dieser ergänzt den unveränderten Gesamtstatus; er ersetzt keine Material-, Vertrags- oder Toolpathprüfung.
- Anzeige im vorhandenen Jobdialog, ohne neue Aufklappzustände oder Runtime-/DOM-Injection.
- Zwei weitere Python-Regressionstests prüfen die Einzelwerte, widersprüchliche Nachweise und vollständig fehlende Daten. Ein anfänglicher Testimportfehler wurde korrigiert; anschließend vollständiges V6-Gate grün.
- Quellbackup: v6/backups/2026-09-11-process-value-proof.
- Backendbackup: /homeassistant/pcc-backups/v6-backend/20260911-172535-process-value-proof.
- Frontendbackup: /homeassistant/pcc-backups/v6-frontend/20260911-192549.
- Backend SHA-256: 067b21f89ba85abef19ca461505803bebb7cc2b8f3baacbadc065c7bdb8de5a6.
- Frontend SHA-256: a66b306c0badbfe2f790ca2e9ce9cc8e5e7328e4a031502641d6dfd4e292b788.
- Freigegebener Core-Neustart einmal angestoßen; SSH-Aufruf lief in ein Timeout. Die anschließende unabhängige Prüfung bestätigt HA running mit Startzeit 19:26:14 deutscher Zeit und beide erwarteten Hashes. Im geprüften Logausschnitt nur die übliche Custom-Integration-Warnung, kein passender Setupfehler/Traceback.
- Kein Slicing- oder Druckauftrag ausgelöst. Visueller Browser-Abnahmetest und neuer realer Slice wurden nicht durchgeführt.
- Benutzerfreigabe: Dateivergleich/SHA-256 anstelle des fehlenden Git-Working-Tree-Aufrufs; weitere kontrollierte Roadmap-Arbeit ohne erneute Rückfrage. Kein Commit/Tag/Push behauptet.

### Weiter offen

- Vollständiger Prozessparametereditor mit validierten Profilwerten und Materialisierung.
- Grafische variable Layerhöhe einschließlich nativer Übergabe und Vorschau.
- Robuste Schnittflächen-Kappen, Malwerkzeuge und Sammel-Slicing/Warteschlange.

## 16. Fehlerkorrektur 2026-09-12 – Filamentsynchronisation beider Materialquellen

- Benutzerbefund bestätigt: Der Studio-Sync war ausschließlich im AMS-Zweig erreichbar. Er las auch die externe Spule neu ein, brach aber ohne belegte AMS-Slots mit einem AMS-Fehler ab.
- AMS und externe Spule besitzen jetzt dieselben Aktionen „Filamente synchronisieren“ und „Projektfarben zurücksetzen“.
- Bei externer Quelle prüft der Sync externe Telemetrie unabhängig von belegten AMS-Slots. Bei AMS bleibt die Meldung bei fehlenden belegten Slots erhalten.
- Nach erfolgreichem manuellem Sync werden Modellfarben aus dem neuen Materialstatus abgeleitet und die Ansicht gespeichert. Keine zusätzliche automatische Abfrage, kein Browser-/HA-Reload und keine Runtime-Injection.
- Projektfarben zurücksetzen behält die vorhandene Rücksetzfunktion bei; die Statusmeldung erklärt bei externer Spule die erneute Farbübernahme per Sync.
- Zwei Regressionstests decken extern ohne AMS, fehlende externe Telemetrie, AMS ohne belegte Slots, gemeinsame Aktionen, Sperre während Sync und HTML-Escaping ab.
- Vollständiges Qualitätsgate grün: Frontendtests/Build, HA-Frontend-Build, Python-Tests, compileall und Quellrichtlinie.
- Quellbackup: `v6/backups/2026-09-11-filament-sync`.
- Live-Rollback: `/homeassistant/pcc-backups/v6-frontend/20260912-012723`.
- JavaScript SHA-256: `943370a312b772e1e0d2c321a7904dade0859fd7ff7e4800c111f73ad1901614`.
- CSS SHA-256: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.
- Buildmanifest SHA-256: `70a801fb92e84817bfcb1c84b732acf26bf1edf7300e6845afa8def4587c4163`.
- Alle drei Hashes nach Deployment unabhängig per HA-SSH bestätigt. Keine Core-/Worker-/Drucker-Neustarts und kein Druck-/Slicingauftrag.
- Visuelle Browser-Abnahme und realer Farbwechsel am Drucker wurden nicht durchgeführt.
- Die zuvor begonnene Prozesseditor-Erweiterung liegt nur als unvollständiger Arbeitsentwurf vor und wurde für diesen priorisierten Fehler unterbrochen. Sie ist nicht Bestandteil dieses Deployments; die weitere Roadmap bleibt offen.

## 17. Prozesseditor abgeschlossen 2026-09-12 – bestehende neun lokale Prozesswerte

- Der vor dem Filament-Sync begonnene Arbeitsschritt ist bereitgestellt: beschriftete Felder für Schichthöhe, erste Schicht, Wandlinien, Deck-/Bodenschichten, Füllgrad, Außen-/Innenwandgeschwindigkeit und Verfahrgeschwindigkeit.
- Lokale bzw. aus Standardprofilen erstellte Prozessprofile verwenden diese Eingabe. Andere Profilarten und der vorhandene Cloud-Editor bleiben bestehen.
- Düsenbereich aus bestehendem A1-Vertrag; Ganzzahl-/Endlichkeitsprüfung, Prozentbereich und Wandgeschwindigkeitsgrenzen. Leere Felder lassen Werte ungesetzt; vollständig leere Prozessprofile werden abgewiesen.
- Dezimalkomma wird angenommen; ungültige Eingaben bleiben sichtbar. Vor dem Speichern erscheint eine Änderungsvorschau, deren Bestätigung nach weiteren Änderungen erneut erforderlich ist.
- Bestehender Fehler korrigiert: Die interne Belegtsperre übersprang „nach Speichern auswählen“. Die Profilauswahl wird jetzt innerhalb der Speicherkette ausgeführt.
- Zwei Regressionstests für Validierung, Düsenbereiche 0,2/0,4/0,6/0,8, Fehlwerte und unverändernde Änderungsübersicht ergänzt. Filament-Sync-Tests bleiben enthalten. Vollständiges V6-Gate grün.
- Browser-Dialogtest vorbereitet, aber nicht ausgeführt: kein lokales Chromium, Download wegen Netzwerk-Timeout abgebrochen. Visuelle Abnahme und vollständiger realer Speichern/Slicing-Durchlauf bleiben unbestätigt.
- Quellbackup: `v6/backups/2026-09-12-process-editor`.
- Live-Rollbackbackup: `/homeassistant/pcc-backups/v6-frontend/20260912-014712`.
- JavaScript SHA-256: `a52cdca85854a359b4c1e69ec8366103841a1c6ea31f2db6b9da9930cb0ada6e`.
- CSS SHA-256: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.
- Manifest SHA-256: `1ba41312b72e359f0d02e992c8649776f66fc6a31fc8465cae88ca9ed26a4e5d`.
- Drei Live-Hashes unabhängig per HA-SSH bestätigt. Kein Neustart, kein Druckstart/-abbruch, kein Slicingauftrag ausgelöst.

### Neue priorisierte Befunde und verbindliche Reihenfolge

1. Nach abgebrochenem Druck und erneutem Senden startet die Transferanzeige offenbar bei der alten Endgröße. Versuche und Zähler auf korrekte Zuordnung prüfen.
2. Bestätigung „Druck abbrechen“ schließt nach etwa 1,5 Sekunden. Dialog-Lebensdauer gegen Telemetrie-Neurendern prüfen; keine automatischen Druckbefehle zum Testen.
3. Screenshot enthält `0300-4000` und `HMS_0300-1800-0001-0005`. Aktuelle Druckerfehler und stehengebliebene Meldungen anhand realer Telemetrie unterscheiden; Ursache bislang offen.
4. Danach Layerdarstellung deutlich verbessern: reale zusammenhängende Druckbahnen, statt ausgedünnt wirkender Darstellung. Der Benutzer ist mit dem aktuellen Funktionsstand zufrieden: Bedienung, Filter, Farbauswahl, Zoom, Layerregler, Vorschau- und Slicingfunktionen erhalten; eigener kontrollierter Änderungsschritt.
5. Weitere Roadmap: zusätzliche Prozessparameter über die vorhandenen neun hinaus, variable Layerhöhe, Schnittflächen-Kappen, Malwerkzeuge und Sammel-Slicing/Warteschlange bleiben offen.

## 18. Fortschrittsnachtrag 2026-09-12 – vorhandener Transfer-/Dialogstand nachgeprüft

- Zu Beginn der Fortsetzung war gegenüber Abschnitt 17 bereits ein neuerer Quell- und Live-Stand vorhanden. Diese Änderungen wurden nicht in diesem Arbeitsschritt neu implementiert.
- `frontend/transfer-attempt.ts` und der Direktdruckpfad unterscheiden den vorherigen serverseitigen Startzeitpunkt von einem neuen Transferversuch. Antworten werden zusätzlich an die aktive clientseitige Trace-ID gebunden.
- `global-job-popup-v3.ts` behält die Druckeraktionskomponente beim Aktualisieren der Störungsliste bei. `printer-command-store-v2.ts` bindet die Bestätigung an den weiterhin aktuellen Drucker und Auftrag.
- Gespeichertes Vollgate dieses vorgefundenen Standes: 343 Python-Tests sowie Frontendtests, TypeScript und Builds erfolgreich. Vor Beginn der Layeränderung unabhängig auf HA bestätigter JavaScript-Hash: `4c61b47b8cfb23e9fb57f59d0e7747ff93559ef3199d43737ad2e295194df9ed`.
- Vorhandenes Live-Backup dieses früheren Deployments: `/homeassistant/pcc-backups/v6-frontend/20260912-122336`.
- Die physische Wiederholung eines abgebrochenen Drucks wurde hier nicht getestet. Kein automatischer Druckstart oder Druckabbruch zur Reproduktion.
- Der Benutzer hat die weitere Untersuchung des Drucker-/Z-Homing-Fehlers ausdrücklich zurückgestellt („vergiss den fehler“). Vorhandene Fehlercodefunktionen bleiben erhalten; es gibt hier keine neue Ursachenbehauptung oder Herstellerdiagnose.

## 19. Fortschrittsnachtrag 2026-09-12 – durchgängige Layerdarstellung

### Benutzerziel und Arbeitsreihenfolge

- Aktueller Schwerpunkt bleibt ausdrücklich die Layeransicht. Reale zusammenhängende G-Code-Bahnen sollen sichtbar sein, ohne den akzeptierten Bedienumfang zu verlieren.
- Der Druckeinstellungseditor gehört weiterhin zur Roadmap und folgt nach diesem Schritt. Die neun vorhandenen lokalen Prozesswerte gelten nicht als vollständiger Prozesseditor.
- Roadmap, Übergabe, technische Dokumentation und deutsche/englische Änderungsnotizen werden mit dem tatsächlichen Umsetzungsstand fortgeschrieben. Ältere Abschnitte bleiben als Historie vollständig erhalten; neuere Nachträge berichtigen ältere Haltepunkte.

### Befund im kanonischen Quellcode

- Der alte aktive Vorschaupfad übersprang bei großen kumulativen Ansichten einzelne frühere Modell-/Supportsegmente über Schrittweiten.
- Modellbahnen wurden auf 80 % bzw. 76 % ihrer geschätzten Breite reduziert.
- Frühere Seitenflächen bildeten nur 72 % der Schichthöhe ab. Diese Kombination begünstigte die ausgedünnte Darstellung.
- Die bestehende Auswahl der historischen Außen-/Oberflächenansicht wurde beibehalten. Der neue Schritt bedeutet nicht, dass bisher ausgeblendete innere Historienbahnen plötzlich vollständig eingeblendet werden.

### Implementiert und live bereitgestellt

- Neuer reiner TypeScript-Geometriebaustein: `v6/frontend/toolpath-ribbon-geometry.ts`.
- `studio-mega-workspace-v2.ts` verwendet diesen Baustein im bisherigen Vorschaupfad.
- Alle nach den bestehenden Sichtbarkeitsregeln angenommenen, gültigen Extrusionssegmente werden gezeichnet. Es gibt in diesem aktiven Pfad keine schrittweise Segmentausdünnung mehr.
- Modellbahnen erhalten Seitenflächen bis zur vollen Schichthöhe. Die obere Bahnfläche liegt an der gelieferten Z-Höhe.
- Die Breite wird aus Extrusion, Bahnlänge und Schichthöhe unter der bestehenden 1,75-mm-Filamentannahme geschätzt. Sie wird nicht mehr auf 80/76 % verkleinert. Darstellungsgrenzen: 0,08 bis 1,6 mm; dies ist kein neuer Düsen- oder Slicingparameter und keine Behauptung einer exakt gemessenen Strangform.
- Die Beleuchtungsnormalen der Seitenflächen machen einzelne Bahnen kenntlich, ohne künstliche Lücken zwischen den Schichten einzufügen. Diese Beleuchtung ist eine Darstellungsnäherung, keine Änderung am G-Code.
- Float32-Seiten mit maximal `54 * 4096` Zahlen pro Geometrieseite vermeiden große temporäre JavaScript-Zahlenlisten. Die Gesamtgeometrie bleibt proportional zur Zahl der sichtbaren Bahnen; die Seiten begrenzen nicht den gesamten Speicherverbrauch.
- Support-Einzelansicht bleibt flach und behält alle geladenen, gültigen Supportbahnen. Modell-/Materialfarben, Strukturfarben und die bisherigen Filterentscheidungen bleiben im bestehenden Workspace.
- Einzellayer/kumulative Ansicht, Kategorienfilter, Alle/Keine, Materialzusammenfassung, Zoom-/Kameraautorität, Layerregler, Vorschaufortschritt und Slicingpfad wurden nicht durch neue Bedienwege ersetzt.
- Ungültige Koordinaten, nichtpositive Extrusion und praktisch längenlose Segmente erzeugen keine ungültigen WebGL-Puffer.
- Keine DOM-/Prototype-/Runtime-Injection, kein Frontend-Reload. Keine Änderungen an technischen Domain-/API-/Storage-IDs, V5, Worker oder Port 5000.

### Tests und konkrete Grenzen der Verifikation

- Vier neue ausführbare Geometrietests:
  1. 180.001 Bahnen oberhalb des alten Vorschau-Budgets: jede Bahn bleibt erhalten, eindeutige Mesh-IDs, begrenzte Geometrieseiten.
  2. Durchgängige aufeinanderfolgende Schichthöhen und 0,2-mm-Bahnbreite.
  3. Einzellayer, Support-Isolation, Farbzuordnung und ausgeblendete Kategorien.
  4. Ungültige Koordinaten/Travel sowie unveränderte Eingangsdaten.
- Erstes Vollgate stoppte vor Build/Deploy, weil eine alte Quellprüfung ausdrücklich die bisherige Sampling-Ausnahme für Brim/Raft/Skirt/Tower verlangte. Die Prüfung wurde auf den neuen vollständigen Renderpfad umgestellt; alle übrigen Gates bleiben erhalten.
- Finales vollständiges Gate: **87 Frontendtests und 343 Python-Tests bestanden**, TypeScript, Frontend-Build, HA-Frontend-Build und Python-Compileall grün, Quellrichtlinie ohne Verstöße.
- Das Deployment-Werkzeug führte das vollständige Gate erneut erfolgreich aus. Abschlusszeit: **12.09.2026, 19:31:44 Europe/Berlin**.
- Zusätzlicher synthetischer Lastlauf vor der abschließenden Beleuchtungskorrektur: 500.000 Bahnen / 3.000.000 Dreiecke, rund 206 MiB reine Positions-/Normaldaten, rund 403 MiB Prozess-RSS in der Testumgebung, Geometrieerzeugung rund 1,37 s. Dies ist kein Browser-/GPU- oder Tablet-Benchmark und kein garantierter Produktwert.
- Nach der Beleuchtungskorrektur blieben die vier Geometrietests grün; Seiten-/Oberflächennormalen und unveränderte Höhen/Breiten wurden zusätzlich numerisch geprüft.
- Visuelle Browserabnahme wurde versucht, aber nicht durchgeführt: zuerst Nutzungslimit bei der automatischen Freigabeprüfung, danach Browser-URL-Sperre für die isolierte Testansicht. Keine Umgehung dieser Sperre.
- Ein tatsächliches großes Nutzerprojekt im Browser, sichtbare Kantendarstellung, Endgeräte-Speicherverbrauch und subjektive Bildqualität bleiben noch zu prüfen. Kein neuer realer Slice und kein Drucktest durchgeführt.
- Die Slicing-/Geometriequelle, Objekttransformationen und Kameraimplementierung wurden nicht verändert. Die Anzeigequalität ist damit quellseitig verbessert, aber noch nicht vom Benutzer visuell abgenommen.

### Deployment, Prüfsummen und Rollback

- Kanonisches Quellbackup: `v6/backups/2026-09-12-continuous-layer-preview` mit vorherigem Workspace, Frontend-Testdatei und Testläufer.
- Live-Rollbackbackup: `/homeassistant/pcc-backups/v6-frontend/20260912-193144`.
- Live-Ziel: `/homeassistant/www/3d-studio-v6/`.
- **JavaScript:** `cb80e49ca21bd748228b99e1346c945e6f1983a15ef5155af822c5e083d78aaa`.
- **CSS:** `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`.
- **Live-Buildmanifest:** `8a4f3eb10fcedb2c0f70ffdbce76f5e435c60de78e9117ad48c0654716c0f488`.
- Der vorherige vorbereitete Manifest-Hash war anders, weil das Deployment neu gebaut wurde. Maßgeblich ist der oben unabhängig auf HA bestätigte Live-Hash.
- Alle drei Artefakte nach Deployment unabhängig über HA-SSH bestätigt. Zusätzlich wurden Marker für vollständige Supportbahnen, Kategorienfilter, Materialzusammenfassung und Alle/Keine im ausgelieferten Bundle nachgewiesen.
- Kein HA-Core-, Worker- oder Druckerneustart; kein Druckstart/-abbruch, keine Materialänderung und kein Slicingauftrag.
- Kein Commit, Tag oder Push behauptet. Die bereits dokumentierte Freigabe für Datei-/SHA-256-Vergleich statt nicht verfügbarem Git-Working-Tree-Aufruf wurde beibehalten.

### Dokumentationsstand und nächste Schritte

1. Layerdarstellung am tatsächlichen Nutzerprojekt visuell abnehmen; bei Auffälligkeiten zuerst diesen Renderpfad korrigieren, ohne Filter/Farben/Zoom zu entfernen.
2. Danach Druckeinstellungseditor über die neun vorhandenen Werte hinaus erweitern, ausschließlich anhand tatsächlich materialisierter und validierter Prozessparameter.
3. Bestehende neun Werte: Schichthöhe, erste Schicht, Wandlinien, Deckschichten, Bodenschichten, Füllgrad, Außenwandgeschwindigkeit, Innenwandgeschwindigkeit, Verfahrgeschwindigkeit.
4. Grafische variable Layerhöhe einschließlich nativer Übergabe und Vorschau bleibt offen.
5. Robuste Schnittflächen-Kappen, Support-/Naht-/Material-Malwerkzeuge und Sammel-Slicing/Warteschlange bleiben offen.
6. Beta-Ausstieg nicht allein durch Entfernen des Labels erklären: verbleibende Browser-/E2E-/visuelle Prüfungen, dokumentierte Kompatibilität, Restore-/Rollback-Nachweise und Releasekriterien weiter verfolgen.
7. Langfristige Roadmap einschließlich nativer Slicer-Unabhängigkeit erhalten; keine vorschnelle Entfernung des funktionierenden Linux-Slicers.


## 20. Verbindliche Priorität nach Benutzerkorrektur – 12.09.2026

- Zuerst die bisher zurückgestellte Erweiterung des Druckeinstellungseditors bearbeiten. Danach hat Layering oberste Priorität; dies ersetzt die Reihenfolge der älteren Abschnitte 19 und der damaligen Übergabe.
- Die Roadmap fortlaufend umsetzen und dokumentieren. Schwierigkeiten sind Anlass zur Fehlersuche und zur Prüfung zulässiger Alternativen, kein Grund für einen stillen Abbruch oder das Vergessen weiterer Aufgaben.
- Technische Blockaden, fehlende Abnahmen und notwendige Freigaben konkret dokumentieren; keine bestandenen Prüfungen oder vollständigen Chat-Erinnerungen behaupten, die nicht vorliegen.
- Bestehende Freigaberegeln für Neustarts und Druckerbefehle sowie Schutzregeln bleiben bestehen. Dokumentation einschließlich deutscher/englischer Änderungsnotizen bei jedem abgeschlossenen Arbeitsschritt fortschreiben.


## 21. Prozesseditor-Erweiterung auf 25 Werte – geprüft und zur Aktivierung vorbereitet, 12.09.2026

### Umsetzung und Funktionsumfang

- Die bestehende Eingabe für neun lokale Prozesswerte wurde um 16 Werte erweitert. Die Feldanzahl wird aus dem tatsächlichen Feldkatalog ermittelt.
- Bestehende Suche, Änderungsvergleich und ausdrückliche Speicherbestätigung bleiben erhalten. Leere Eingaben bleiben ungesetzt; geerbte Werte werden nicht erfunden.
- Zusätzliche Zahlen werden im Frontend und im lokalen Python-Prozessvertrag auf Endlichkeit, Mindestwert und gegebenenfalls Ganzzahligkeit geprüft. Boolesche Werte, leere Strings und ungültige Zahlen werden als Zahlen abgewiesen.
- Die zusätzlichen Schlüssel wurden sowohl im installierten Bambu-Profilbestand auf dem PC als auch im tatsächlichen nativen Linux-Profilbestand nachgewiesen. Es wurden keine Profilvorgaben verändert und keine neuen Hardwaregrenzen behauptet.
- Die vorhandene native Materialisierung übernimmt die Werte über den SHA-256-gebundenen Prozessvertrag. Ihre Rückmeldung enthält jetzt alle angeforderten Prozessschlüssel sowie die bisherigen drei Auftragswerte.
- Der Analysebericht zeigt zusätzlich zu den bisherigen drei Zeilen die weiteren Editorwerte, sobald sie tatsächlich angefordert wurden. Profil, Anforderung, native Rückmeldung und G-Code-Nachweis bleiben getrennt; fehlende Belege bleiben „Nicht nachgewiesen“, Abweichungen „Abweichung“.
- Arraywerte aus nativen Profilen bleiben in der Rückmeldung erhalten und werden vom bestehenden Tabellenrenderer unterstützt.
- Keine Slicer-Engine-, Dispatcher- oder Serveränderung. Der Worker benötigt für diesen Schritt keinen Neustart: geändert wird sein bei Bedarf gestarteter Materialisierungshelfer. Seine kanonische Abhängigkeitsprüfsumme wurde entsprechend aktualisiert.
- Die bisherigen neun Felder und alle Layeränderungen bleiben erhalten. Cloudprofile, Druckerbefehle und Materialschreibpfade wurden in diesem Schritt nicht erweitert.

### Neue lokale Werte und native Zuordnung

| Eingabe | Lokaler Schlüssel | Nativer Schlüssel |
|---|---|---|
| Linienbreite (mm) | `line_width_mm` | `line_width` |
| Außenwand-Linienbreite (mm) | `outer_wall_line_width_mm` | `outer_wall_line_width` |
| Innenwand-Linienbreite (mm) | `inner_wall_line_width_mm` | `inner_wall_line_width` |
| Deckflächen-Linienbreite (mm) | `top_surface_line_width_mm` | `top_surface_line_width` |
| Support-Linienbreite (mm) | `support_line_width_mm` | `support_line_width` |
| Infillgeschwindigkeit (mm/s) | `sparse_infill_speed_mm_s` | `sparse_infill_speed` |
| Massivfüllung-Geschwindigkeit (mm/s) | `internal_solid_infill_speed_mm_s` | `internal_solid_infill_speed` |
| Deckflächengeschwindigkeit (mm/s) | `top_surface_speed_mm_s` | `top_surface_speed` |
| Geschwindigkeit erste Schicht (mm/s) | `initial_layer_speed_mm_s` | `initial_layer_speed` |
| Brückengeschwindigkeit (mm/s) | `bridge_speed_mm_s` | `bridge_speed` |
| Supportabstand oben (mm) | `support_top_z_distance_mm` | `support_top_z_distance` |
| Supportabstand unten (mm) | `support_bottom_z_distance_mm` | `support_bottom_z_distance` |
| Supportabstand seitlich (mm) | `support_object_xy_distance_mm` | `support_object_xy_distance` |
| Support-Interface-Abstand (mm) | `support_interface_spacing_mm` | `support_interface_spacing` |
| Support-Interfaceschichten oben (Schichten) | `support_interface_top_layers` | `support_interface_top_layers` |
| Support-Interfaceschichten unten (Schichten) | `support_interface_bottom_layers` | `support_interface_bottom_layers` |

### Prüfung

- Vollständiges Gate vom **12.09.2026, 19:49:26 Europe/Berlin**: **88 Frontendtests und 361 Python-Tests bestanden**; TypeScript, beide Frontendbuilds, Quellrichtlinie und HA-Compileall erfolgreich.
- Neue Tests prüfen alle 16 zusätzlichen Schlüssel, fehlerhafte Eingaben, Null-/Leerwertbehandlung, native Zuordnung, Materialisierungsrückmeldung sowie bestätigte/fehlende/abweichende Artefaktnachweise.
- Der vorhandene ausführbare Zwei-AMS-Materialisierungstest wurde um die 16 Werte ergänzt. Er erstellt die nativen Prozessdateien und prüft jeden Rückgabewert; er startet weder Slicer noch Drucker.
- Der erste Gate-Lauf zeigte 88 erfolgreiche Frontendtests und 360 erfolgreiche Python-Tests. Ein alter Mengenvergleich erwartete vier Einstellungen bei nun 20 Einstellungen im erweiterten Testprofil. Der Vergleich wurde auf den tatsächlichen Testvertrag umgestellt; alle einzelnen Werte werden weiterhin geprüft. Der folgende Vollgate-Lauf war vollständig grün.
- Im Scratch-Python war pytest nicht installiert; maßgeblich ist das ausgeführte vollständige Gate im kanonischen PC-Projekt mit dessen vorhandener Testumgebung.
- Reales Slicing mit den neuen Werten und visuelle Browserabnahme bleiben offen. Keine Aussage, dass alle 25 Werte bereits an einem echten Druck überprüft wurden.
- Read-only-Abgleich am nativen Worker: alle 16 Schlüssel vorhanden, Helfer noch mit altem Hash, zum Prüfzeitpunkt keine eingereihten oder laufenden Slicingjobs. Dieser Zeitpunkt ersetzt keine erneute Aktivierungsprüfung.

### Bereitstellung, Backups und Status

**Status: geprüft und auf HA im Staging bereitgelegt, noch nicht live aktiviert.** Die laufende Oberfläche ist weiterhin der erfolgreich bereitgestellte Layerstand aus Abschnitt 19.

- Kanonisches Quellbackup: `v6/backups/2026-09-12-process-editor-25/before/`.
- HA-Staging: `/homeassistant/pcc-staging/20260912-editor25/`.
- Geprüftes Paket: `editor-bundle.zip`, 470.920 Byte, SHA-256 `35314679a9d78a097c11e74567848ecb3b3d54e12636f8cf7b344c4c44e62836`.
- Ausgewählte Backend-/Frontenddateien und Abhängigkeitsmanifest aus diesem Paket extrahiert; Pythonquellen auf HA zusätzlich kompiliert.
- Vorabbackup der sechs vorhandenen HA-Dateien: `/homeassistant/pcc-backups/v6-editor25/20260912-pre-activation/`.
- Exakte Alt-/Neuhashes und Stagingstatus: `/homeassistant/pcc-staging/20260912-editor25/activation-manifest.json`.
- Die separate native Workerdatei wurde nur gelesen. Vor ihrer späteren Änderung zusätzlich direkt am Worker sichern und den weiterhin erwarteten Althash prüfen.
- Vorheriger und weiterhin laufender nativer Helfer: `5037431dc78cfddb17722b843621b54dd1687ac054e46ef0680e2b4fed84e681`.
- Keine Live-Datei durch den neuen Editorstand ersetzt, kein HA-/Worker-/Druckerneustart, kein Reload, kein Slice, kein Druckauftrag.

| Datei relativ zum HA-Staging | Geprüfter neuer SHA-256 |
|---|---|
| `custom_components/ultimate_3d_studio_v6/process_profile_contract.py` | `81fb9ce4581ada5ab83a0b4acf85512f23a99c4667afe8353c0fe5548117c67d` |
| `custom_components/ultimate_3d_studio_v6/slicer_backend_router.py` | `d38281a8500e03fac528f12343f6d2068eb5fd3241cfde0e6e47bba6842c08aa` |
| `custom_components/ultimate_3d_studio_v6/materialize-bambu-multimaterial.py` | `2bdc065f62cbf81e71732c6bf9b78836f93cf8d5cbcceb826d8dc9db7c82259d` |
| `www/3d-studio-v6/ultimate-3d-studio.js` | `8f92f68a1388305948d1d7cc3789bb566ac067acd7c7fdb3ee761e2906aa6f0f` |
| `www/3d-studio-v6/ultimate-3d-studio.css` | `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c` |
| `www/3d-studio-v6/ultimate-3d-studio-build.json` | `f3f00da11316c8d3d5806a71eb8358e721334cd4e31f5455d2cc0c79a5f2d253` |
| `host/3d-printer-slicing-server/DEPENDENCY-SHA256SUMS` | `35124b8497491e0135c9f0743a2267a54abe9760a0103b2b911a7a6fc83b37d0` |

### Konkrete Aktivierung nach erforderlicher Freigabe

1. Zunächst exakte Freigabe für **einen HA-Core-Neustart** einholen. Die bestehende Roadmap verlangt für diesen Eingriff ausdrücklich eine Freigabe; die neue Beharrlichkeitsregel hebt sie nicht auf.
2. Gate-/Quellstand, Staginghashes und weiterhin passende Live-Althashes erneut vergleichen. Bei zwischenzeitlichen Änderungen stoppen und abgleichen, nichts überschreiben.
3. Native Warteschlange und laufende Jobs erneut prüfen. Für den atomaren Austausch des Materialisierungshelfers dieselbe exklusive `run/dispatcher.lock`-Verzeichnissperre wie der Dispatcher erwerben; eine fremde Sperre niemals entfernen. Helfer und dessen Abhängigkeitsmanifest separat sichern.
4. Ausschließlich `process_profile_contract.py`, `slicer_backend_router.py` und `materialize-bambu-multimaterial.py` aus dem geprüften Staging in die V6-Komponente übernehmen. Den gleichen Helfer in `/var/lib/homeassistant/3d-printer-slicing-server/` mit passendem Abhängigkeitsmanifest bereitstellen; keinen Worker-Neustart ausführen.
5. Python-/HA-Konfigurationsprüfung; bei Fehlern die gesicherten Dateien zurücklegen. Nach erfolgreicher Prüfung den ausdrücklich freigegebenen einzelnen HA-Core-Neustart ausführen und Zustand/Logs prüfen.
6. Erst nach bestätigtem Backendstart die drei geprüften Frontendartefakte bereitstellen und unabhängig per SHA-256 verifizieren. Keine automatische Seitenneuladung.
7. Beim Rückrollen die zu diesem Schritt gesicherten Backend-/Workerdateien und den zuvor live bestätigten Layer-Frontendstand zusammengehörig wiederherstellen. Ein erneuter HA-Neustart zum Laden zurückgerollter Pythonmodule benötigt wiederum die dafür erforderliche Freigabe.

### Fortsetzung und weiterhin offene Roadmap

- Nach Aktivierung und Prüfung dieser Editorstufe hat **Layering oberste Priorität**, entsprechend der jüngsten Benutzeranweisung in Abschnitt 20.
- Der vollständige Prozesseditor ist damit noch nicht abgeschlossen: unter anderem Infillmuster, Wandreihenfolge, Naht, Bügeln, weitere Beschleunigungs-/Brücken-/Überhangparameter und die passende Trennung von Maschinen-/Filamentparametern bleiben offen. 25 Werte sind keine Behauptung vollständiger Herstellerprofilabdeckung.
- Variable Layerhöhe einschließlich nativer Übergabe und Vorschau, Malwerkzeuge, Schnittflächen-Kappen, Warteschlange und Beta-Releasekriterien weiter verfolgen. Bestehende Funktionen erhalten.
- Roadmap und Projektkontext enthalten die verbindliche Regel: bei Schwierigkeiten weiter untersuchen und zulässige Alternativen nutzen; Hindernisse und notwendige Freigaben offen festhalten. Kein stiller Abbruch und keine erfundenen Erfolgsmeldungen.



## 22. Fortgeltende Freigabe und Aktivierung des 25-Werte-Editors – 12.09.2026

### Verbindliche Benutzerfreigabe

- Der Benutzer hat ausdrücklich zugestimmt: „ja darfst und auch zukünftig, fahre nach plan fort“.
- Diese Freigabe gilt für die jetzt notwendige und für künftig notwendige HA-Core-Neustarts innerhalb der Roadmap. Für denselben bereits freigegebenen Eingriff nicht erneut um Zustimmung bitten.
- Frühere Aussagen, jeder einzelne HA-Core-Neustart benötige eine neue Rückfrage, sind insoweit durch diese neuere Benutzeranweisung ersetzt.
- Zustand, Backup, Qualitätsgate, Datei-/SHA-Abgleich und Rückweg weiterhin prüfen. Keine Freigabe für automatische Druckstarts, Druckerbefehle oder Worker-/Druckerneustarts daraus ableiten.
- Dauerhafter Projektkontext unter `C:\Users\Taracraft\.codex\context\PROJECT_3D_PRINTER_CONTROL_CENTER.md` entsprechend ergänzt. Arbeitsreihenfolge bleibt Editorstufe abschließen, dann Layering vorrangig weiterführen.

### Aktivierung durchgeführt

- Das kanonische Paket wurde erneut gegen alle sieben Staging-Prüfsummen abgeglichen; alle Werte passten. Sämtliche vorhandenen Live-Althashes passten ebenfalls.
- HA-Konfigurationsprüfung vor und nach dem Dateiaustausch erfolgreich. Der erste Aufruf unter sudo hatte keinen Supervisor-Token; der reguläre authentifizierte HA-CLI-Aufruf war erfolgreich. Keine Zugangsdaten ausgegeben.
- Exklusive native `run/dispatcher.lock`-Sperre erworben und anschließend freigegeben. Keine eingereihten oder laufenden Slicingjobs beim Austausch.
- Drei HA-Komponentendateien, der native Materialisierungshelfer und dessen Abhängigkeitsmanifest atomar und mit Prüfsummenprüfung übernommen; Eigentümer und Dateimodi erhalten.
- Aktivierungsbackup: `/homeassistant/pcc-backups/v6-editor25/20260912-200542-activation/` (im Hilfscontainer als `/config/pcc-backups/...` sichtbar). Enthält vorherige HA-Dateien und zuvor vorhandene Workerdateien.
- Ein anfänglicher Installationsaufruf stoppte vor jeglicher Dateiveränderung wegen eines JSON-/Python-Literalfehlers; korrigierter Aufruf war erfolgreich.
- **Genau ein HA-Core-Neustart** ausgelöst. Der aufrufende Connector lieferte nach Wartezeit keinen Erfolgsstatus; der Neustart wurde nicht wiederholt. Unabhängige Prüfung bestätigte HA `running`, Startzeit **2026-09-12T20:06:18.113744912Z** beziehungsweise 22:06:18 Europe/Berlin.
- HA-Konfigurations-API bestätigt geladene Integration `ultimate_3d_studio_v6`. Im gefilterten aktuellen Logausschnitt keine passende V6-Fehler-/Setup-/Tracebackmeldung.
- Profil-API des laufenden HA antwortet erfolgreich: 186 Profile, benutzerdefinierte Profile unterstützt. Dieser Read-only-Test hat kein Benutzerprofil angelegt oder verändert.
- Danach die drei geprüften Editor-Frontendartefakte übernommen und alle sechs HA-Dateihashes unabhängig bestätigt. Die Editorstufe mit 25 Werten ist **aktiv**, nicht mehr nur vorbereitet.
- Kein Worker- oder Druckerneustart, kein Seitenreload, kein realer Slice und kein Drucker-/Materialbefehl.
- Der Editor-JavaScript-Hash `8f92f68a1388305948d1d7cc3789bb566ac067acd7c7fdb3ee761e2906aa6f0f` wurde anschließend durch den nachfolgenden Layerbuild aus Abschnitt 23 abgelöst. Die Editorfunktionen sind darin weiterhin enthalten.

## 23. Layering – verbundene Bahnecken und Konturschluss, 12.09.2026

### Befund und Umsetzung

- Nach der Editoraktivierung wurde entsprechend der Priorität am Layering weitergearbeitet.
- Der zuvor ausgerollte Renderpfad erhielt alle angenommenen Segmente und volle Schichthöhen, erzeugte aber jedes Segment als eigenen rechteckigen Streifen. An Richtungswechseln konnte dadurch eine unbedeckte äußere Ecke zwischen den Streifen bleiben.
- `frontend/toolpath-ribbon-geometry.ts` ergänzt jetzt abgeschrägte Eckverbindungen einschließlich Seitenfläche. Diese füllen die äußere Ecke, ohne unbeschränkt lange Gehrungsspitzen zu erzeugen.
- Ein zusammenhängender Konturzug wird auch an seiner Schlussnaht verbunden, wenn das letzte Ende wieder den tatsächlichen Anfang erreicht.
- Verbindungen nur zwischen direkt aufeinanderfolgenden, akzeptierten Extrusionssegmenten mit übereinstimmendem End-/Startpunkt, Z, Werkzeug, Feature, Kategorie und Darstellungsstil. Toleranzen: XY 0,00001 mm, Z 0,000001 mm.
- Travel, ungültige Geometrie und ausgeblendete Segmente unterbrechen die Verbindungskette. Zwischen versetzten Endpunkten, Werkzeug-/Material- oder Featurewechseln wird keine künstliche Verbindung eingefügt.
- Support-Einzelansicht bleibt flach. Bestehende Glanzmarkierung wird über die Eckverbindung fortgeführt. Farben, Kategorienfilter, Einzellayer/kumulative Darstellung, Zoom, Popup und Slicingpfad bleiben erhalten.
- Keine Segmentausdünnung eingeführt und keine G-Code-Koordinaten verändert. Die Eckgeometrie ist eine Darstellungsnäherung und keine Simulation der exakt gedruckten Strangform.
- Pro nicht geradliniger Verbindung kommen bei räumlicher Darstellung drei Dreiecke hinzu; bei flacher Darstellung eines, optional eines für die Glanzmarkierung. Gesamtgeometrie und Speicher bleiben linear in der sichtbaren Bahnzahl. Kein neuer Gesamt-Speicherdeckel und kein Browser-/GPU-Leistungsnachweis.

### Tests und Deployment

- Drei neue kanonische Frontendtests prüfen:
  1. Numerische Flächenabdeckung der vorher offenen Außenecke bei Links- und Rechtskurven, endliche Normalen und unveränderte Eingangsdaten.
  2. Trennung bei Travel, ausgeblendeten Segmenten, versetzten Endpunkten sowie Werkzeug- und Featurewechseln.
  3. Geschlossene Konturen einschließlich Schlussnaht, flache Darstellung und Glanzmarkierungen.
- Die vier bestehenden Geometrietests einschließlich 180.001 vollständig erhaltener Bahnen bleiben grün. Separater lokaler Lauf: sieben Geometrietests bestanden.
- Vollständiges kanonisches Gate beim Deployment: **91 Frontendtests und 361 Python-Tests bestanden**, Quellrichtlinie, TypeScript, beide Frontendbuilds und HA-Compileall erfolgreich.
- Gate-/Deploymentabschluss: **12.09.2026, 22:11:34 Europe/Berlin**.
- Quellbackup: `v6/backups/2026-09-12-layer-corners/before/`.
- Live-Frontendbackup: `/homeassistant/pcc-backups/v6-frontend/20260912-221134`.
- Alle drei Live-Prüfsummen nach Deployment erneut unabhängig über HA-SSH bestätigt:

| Live-Artefakt | SHA-256 |
|---|---|
| JavaScript | `a16ac1748e6280ba428707f9331d1f1e95a316893ea2c331d38412f5e58e561b` |
| CSS | `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c` |
| Buildmanifest | `1cbe14c292705385a30cb1cd110e89ffba6bf0e87d80e3e34816cc8df135c597` |

- Dieser Layerdeploy erforderte keinen weiteren HA-Neustart. Insgesamt in dieser Fortsetzung genau ein HA-Core-Neustart für den Editor, kein Worker-/Druckerneustart.
- Visuelle Browserabnahme weiterhin offen. Die zuvor gesperrte Browser-Testfläche wurde nicht über andere Wege umgangen. Die Geometrietests ersetzen keine visuelle Bestätigung am tatsächlichen Nutzerprojekt.
- Beta-Version bleibt 6.0.0-beta3. Weder vollständiger Beta-Ausstieg noch vollständiger Hersteller-Prozesseditor behauptet.

### Dokumentation und nächster Roadmapstand

- Vollständige alte Roadmap erhalten und um Abschnitte 22–23 ergänzt; Projektkontext, langfristige Roadmap, Übergabe, Editor-/Layer-Prüfnachweise und deutsche/englische Changelogs fortgeschrieben.
- Layering bleibt oberste aktuelle Priorität: tatsächliche Projektansicht und große reale Modelle visuell prüfen, sobald der zulässige Zugriff verfügbar ist. Variable Layerhöhe einschließlich nativer Übergabe bleibt als eigener noch nicht implementierter Schritt offen.
- Weitere Editorparameter, Schnittflächen-Kappen, Malwerkzeuge, Sammel-Slicing/Warteschlange und Releasekriterien aus der bisherigen Roadmap bleiben offen. Keine Aufgaben stillschweigend entfernt.


## 24. Layering – offene Bahnenden und äußere Flächennormalen, 12.09.2026

### Befund und umgesetzte Korrektur

- Die nach Abschnitt 23 zusammenhängend gezeichneten Bahnen hatten an offenen Anfangs-/Endpunkten noch keine Stirnflächen.
- Die Dreiecksreihenfolge beider seitlichen Bahnflächen erzeugte nach innen gerichtete Normalen. Das war ein Fehler der Beleuchtungsgeometrie; eine visuelle Browserbeobachtung wird damit nicht behauptet.
- Beide Seitenflächen in `frontend/toolpath-ribbon-geometry.ts` sind jetzt nach außen orientiert. Die vorhandene Schichtbeleuchtung bleibt erhalten.
- Offene räumliche Bahnketten erhalten genau eine Stirnfläche mit zwei Dreiecken am Anfang und am Ende. Zusammenhängende gerade Segmente bekommen keine innere Trennfläche.
- Geschlossene Konturen bleiben ohne zusätzliche Stirnflächen an der Schlussnaht; die Eckverbindungen aus Abschnitt 23 bleiben erhalten.
- Travel, ungültige oder ausgeblendete Segmente und unvereinbare Endpunkte/Styles beenden die aktuelle Kette mit Stirnflächen. Neue Ketten beginnen unabhängig.
- Richtungsumkehrungen werden als getrennte offene Läufe behandelt. Die Richtungsprüfung trennt bei einem normierten Skalarprodukt von höchstens -0,999999; damit wird eine direkt zurücklaufende Bahn nicht fälschlich als geschlossene Kontur behandelt.
- Die flache Supportansicht erhält keine senkrechten Stirnflächen. Filter, Farben, Materialzuordnung, Layersteuerung, Zoom, Popup und Slicing bleiben in ihren bisherigen Pfaden.
- Es werden weiterhin alle akzeptierten Segmente gezeichnet, und die Eingangsdaten werden nicht verändert. Je offener räumlicher Kette entstehen vier zusätzliche Dreiecke, unabhängig von deren Segmentzahl.
- Diese Darstellung ist weiterhin eine Vorschaugeometrie aus geschätzten Bahnbreiten. Keine Behauptung einer vollständig geschlossenen Volumengeometrie oder exakt simulierter Extrusionsform.

### Nachweise

- Drei neue Regressionstests zuerst gegen den bisherigen Stand ausgeführt: alle drei schlugen wie erwartet fehl (innere Normalen, fehlende Stirnflächen, ungeschlossene Umkehrläufe).
- Nach der Korrektur sind diese Tests erfolgreich. Geprüft werden positive/negative sowie diagonale Bahnausrichtungen, ausschließlich äußere Flächennormalen, Stirnflächen nur an Kettenenden, fehlende innere Trennflächen und die weiterhin flache Supportdarstellung.
- Die bestehenden Tests für 180.001 vollständig erhaltene Bahnen, Seitenpuffergrenzen, volle Schichthöhen, Filter/Materialwechsel, Eckabdeckung, Konturschluss und Glanzmarkierungen bleiben erfolgreich.
- Bestehende Dreieckszahl-Erwartungen wurden gezielt um die nun zusätzlich notwendigen Stirnflächen erweitert; die unabhängigen Flächen- und Grenzprüfungen bleiben erhalten.
- Separater Geometrielauf: **10 Tests bestanden**.
- Vollständiges kanonisches Deployment-Gate: **94 Frontendtests und 361 Python-Tests bestanden**; Quellrichtlinie, TypeScript, beide Frontendbuilds und HA-Compileall erfolgreich.
- Deploymentabschluss: **12.09.2026, 22:20:52 Europe/Berlin**.

### Live-Stand und Rückweg

- Kanonisches Quellbackup: `v6/backups/2026-09-12-layer-ends/before/`.
- Live-Frontendbackup: `/homeassistant/pcc-backups/v6-frontend/20260912-222052`.
- Alle drei Live-Dateihashes nach Deployment unabhängig über HA-SSH bestätigt:

| Artefakt | Live-SHA-256 |
|---|---|
| JavaScript | `5b0d64c0e6c79022d5cf495ab5f59723edb0ef543248633411eeea69c1bd6a73` |
| CSS | `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c` |
| Buildmanifest | `1025d70bd4fdc5102fd905c0bb624041bb77d2341997d8d3f6099bf912eb7896` |

- In dieser Fortsetzung kein HA-/Worker-/Druckerneustart, kein Seitenreload, kein realer Slice und kein Drucker-/Materialbefehl.
- Der aktive 25-Werte-Editor und die zugehörigen Backend-/Workeränderungen aus Abschnitt 22 bleiben aktiv.
- Die Benutzerfreigabe für künftig notwendige HA-Core-Neustarts im Rahmen der Roadmap gilt weiterhin; keine erneute Rückfrage für denselben Freigabeumfang.

### Offene Abnahme und weitere Roadmap

- Die visuelle Browserabnahme und die Prüfung großer tatsächlicher Nutzerprojekte bleiben offen; der bisherige Browserzugriff war gesperrt und wurde nicht umgangen.
- Grafische variable Layerhöhe mit nativer Übergabe ist weiterhin ein separater offener Schritt. Die hier ergänzten Stirnflächen implementieren diese Funktion nicht.
- Layering bleibt die höchste aktuelle Priorität. Weitere Prozessparameter, Malwerkzeuge, Schnittflächen-Kappen, Sammel-Slicing/Warteschlange und Beta-Abnahmekriterien bleiben unverändert in der fortlaufenden Roadmap.
- Vollständige ursprüngliche Roadmap und alle bisherigen Nachträge erhalten. Deutsche/englische Änderungsnotizen, Übergabe, Layer-/Editor-Prüfnachweise und dauerhafter Projektkontext wurden auf diesen Stand fortgeschrieben.

## 25. Layering - Variable Schichthoehen: native Uebergabe aktiviert (2026-09-13)

Status: aktiviert in Quelle, Home Assistant und echtem Worker-Pfad; grafischer Kurveneditor folgt als naechster Layering-Block.

Umgesetzt:
- Die Studio-Slice-API kann `layer_height_ranges` als JSON-Parameter uebergeben.
- `slicer_plate_views_v2.py` akzeptiert die Bereiche nur als Array und reicht sie durch die bestehende Nozzle-Validierung.
- `slicer_nozzle_profiles.py` validiert maximal 32 geordnete Z-Bereiche ohne Ueberlappung, Z 0..256 mm und Schichthoehen innerhalb des aktiven A1-Duesenvertrags.
- `materialize-bambu-multimaterial.py` schreibt die Bereiche in Bambu Studios nativen `assembled_params[].height_ranges[].range_params.layer_height`-Pfad fuer die zusammengesetzte Modellgruppe 1.
- Der Worker prueft dieselben Bereiche nochmals gegen die aus `target_printer` uebergebenen Min/Max-Layerhoehen.
- Frontend-Typ, Speicherung und Upload-Serialisierung behalten `layer_height_ranges`; bestehende globale/per-Plate Optionen bleiben kompatibel.

Validierung:
- Kanonisches V6-Gate: gruen am 2026-09-13 08:31 Europe/Berlin.
- Gate-Stufen: Frontend-Test/Build gruen, HA-Core-Build gruen, Python 366 Tests gruen, HA compileall gruen.
- Live HA-Core nach Restart verifiziert: Container gestartet 2026-09-13T06:28:12Z, `ultimate_3d_studio_v6` geladen, 186 Profile erreichbar.
- Live Worker materializer-only Probe ohne Druckauftrag: `assembled_params` enthaelt `height_ranges` mit `layer_height: "0.12"`, Summary meldet `variable_layer_heights.applied: true`.
- Kein echter Druck und kein echter Slicer-CLI-Lauf mit Druckjob wurde gestartet.

Hashes / Backups:
- `materialize-bambu-multimaterial.py`: `696f4e68552bfdcfcb7bc29e198d1412dabb273ed2597db44d456950a32a1916`
- `slicer_nozzle_profiles.py`: `e02b7e511524f447ec8183914e74b11f6e80f966408e64e5965afee393327b4f`
- `slicer_plate_views_v2.py`: `ca81d4de0cc1cfa793c66b4010c6f53dc9542ed12bfcec3be2135694cd949e33`
- Worker `DEPENDENCY-SHA256SUMS`: `8af27bee45994bea083a0fc772c8b4d372557feb78c0557342befae1ae0796ad`
- Live Frontend JS: `46853f80e4b815347d2e5e557c681caa821d578e1c836e18e5e8c5fbd929fc54`
- Live Frontend Buildmanifest: `30fdfc58d7452bdc5951c85a05ad32572e4cbf56f5331460a2721e5d9a8ad901`
- Repo-Backup: `backups/2026-09-13-variable-layer-heights/before/`
- HA/Worker-Backup: `/homeassistant/pcc-backups/v6-variable-layer-heights/20260913-062744` und Host-Worker-Backup `/config/pcc-backups/v6-variable-layer-heights/20260913-063413`
- Frontend-Backup: `/homeassistant/pcc-backups/v6-frontend/20260913-083139`

Wichtig fuer den naechsten Schritt:
- Die native Grundlage ist aktiv, aber der sichtbare grafische Editor fuer eine Hoehenkurve ist noch offen.
- Naechster Layering-Block: UI fuer variable Schichthoehen in der aktiven Studio-Oberflaeche, inklusive einfacher Bereichsliste/Preview-Markierung und danach echter nativer Slicer-CLI-Akzeptanztest ohne Druck.

## 26. Layering - Variable Schichthoehen: sichtbare Bereichs-UI aktiviert (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; baut auf der nativen Uebergabe aus Abschnitt 25 auf.

Umgesetzt:
- Das sichtbare `studio-process-options-panel` enthaelt jetzt eine kompakte Liste fuer variable Schichthoehenbereiche.
- Nutzer koennen Bereiche hinzufuegen, Z-Start/Z-Ende/Layerhoehe bearbeiten und Bereiche entfernen.
- Die UI speichert dieselbe Struktur `layer_height_ranges[{min_z_mm,max_z_mm,layer_height_mm}]`, die HA-API und Worker bereits validieren.
- Bestehende Druckeinstellungen bleiben kompatibel; ohne Bereiche wird weiterhin die Standard-Layerhoehe verwendet.
- Die Upload-Serialisierung schreibt aktive Bereiche in den Query-Parameter `layer_height_ranges`, der native Worker schreibt daraus `assembled_params.height_ranges`.

Validierung:
- Kanonisches V6-Gate nach UI-Aenderung: gruen am 2026-09-13 08:39 Europe/Berlin.
- Gate-Stufen: Frontend-Test/Build gruen, HA-Core-Build gruen, Python 366 Tests gruen, HA compileall gruen.
- Frontend live deployed mit unabhängiger Hashpruefung.

Live Frontend:
- `ultimate-3d-studio.js`: `de2d6b5946bb5a47f3b33f8c43146b5616e4bb8958872ecfc119fbae3d5c1607`
- `ultimate-3d-studio.css`: `0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c`
- `ultimate-3d-studio-build.json`: `fcd3b9525ca1ee60c71d2eef7b4f58c52b4b61fbc9d77f42e8b1bbb92fb98da8`
- Frontend-Backup: `/homeassistant/pcc-backups/v6-frontend/20260913-083919`

Offen als naechster Layering-Punkt:
- Preview-Markierungen in der Layeransicht fuer die aktiven Hoehenbereiche.
- Nativer Slicer-CLI-Akzeptanztest mit variablen Hoehen ohne echten Druck.
- Danach feinere Hoehenkurve statt nur Bereichsliste.

## 27. Layering - Preview-Markierungen fuer variable Schichthoehen (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; baut auf Abschnitt 26 auf.

Umgesetzt:
- Die aktive Layeransicht liest die gespeicherten layer_height_ranges und zeigt sie in der Vorschau-Seitenleiste als kompakte Bereichsliste.
- Der aktuelle Layerregler-Z-Wert markiert den gerade passenden Bereich direkt in der Vorschau.
- Die Darstellung ist rein im bestehenden Previewpfad umgesetzt: keine DOM-/Runtime-Injection, kein Reload, keine Aenderung an G-Code, Slicing, Filtern, Farben, Zoom oder Kamera.
- Bereiche ohne aktive variable Schichthoehe zeigen keinen Zusatzblock; bestehende Vorschau bleibt unveraendert.
- Quellbackup: v6/backups/2026-09-13-variable-layer-preview-markers/before/.

Validierung und Live-Stand:
- Kanonisches V6-Gate gruen am 2026-09-13 09:09 Europe/Berlin.
- Frontend live deployed am 2026-09-13 09:10 Europe/Berlin.
- Live ultimate-3d-studio.js: a4615ba32cc43543ce370dff8d715aee14b82c22137294bd751868a475fd8cab
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 2da7976d988b6f5f0810689f48a531262d3d0aec6b02218b331a8ec273a1f571
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-091010
- Kein HA-Core-/Worker-/Druckerneustart, kein Druckerbefehl und kein realer Druckstart in diesem Schritt.
- Visuelle Browserabnahme am echten Nutzerprojekt bleibt offen; diese Markierungen sind quellseitig und per Gate/Hash belegt, nicht per Browser-Screenshot abgenommen.

## 28. Layering - Native Bambu-Akzeptanz fuer variable Schichthoehen (2026-09-13)

Status: synthetischer nativer Slicing-Server-Lauf erfolgreich; kein Druckauftrag und kein Druckerbefehl.

Befund und Korrekturen:
- Ein erster nativer Bambu-CLI-Akzeptanzversuch erreichte load_assemble_plate_list, scheiterte aber an min_z/max_z als Strings. Der Bambu-Manifestpfad war richtig, der JSON-Typ war falsch.
- _native_height_ranges schreibt min_z und max_z jetzt als JSON-Zahlen; range_params.layer_height bleibt als String erhalten.
- Ein zweiter Lauf erzeugte G-Code und G-Code-3MF, zeigte aber noch invalid json type for layer_height im Runtime-Prozessprofil.
- _apply_selected_process_profile behandelt layer_height jetzt gezielt als Bambu-Stringwert. Der vorherige Logfehler ist im anschliessenden Lauf verschwunden.
- Aktueller Materializer-Hash in Quelle, HA-Komponente und echtem Worker-Pfad: e7bb755a74e467f891a9dccf597f16f78b67a816f2196f83a2a17b4e751d650f.
- Worker-Dependency-Hash nach Deployment: 33229942abb41de4bfd16be840226b866ba0ab6b18039994d5bc50802d6007f3.

Native Akzeptanz:
- Job v6-vlh-accept-20260913T071923Z lief ueber den echten Slicing-Server/Dispatcher-Pfad mit synthetischem Mini-3MF und ohne Druckstart.
- Ergebnisstatus: completed, Engine bambu_studio, Ausgabe plate_1.gcode, plate_1.gcode.3mf und result.json.
- assembled_params enthaelt fuer assemble_index: 1 zwei native height_ranges: 0..5 mm mit layer_height 0.12 und 5..20 mm mit layer_height 0.2.
- summary.variable_layer_heights.applied ist true, range_count ist 2.
- Gezielt analysierte G-Code-Layer-Marker: 116 monotone Layer; eindeutige Layerdifferenzen 0.0, 0.12, 0.2. Die Auswertung fand 40 Schritte im 0,12-mm-Bereich und 74 Schritte im 0,20-mm-Bereich; um 5 mm wechseln die Marker von 0,12 auf 0,20 mm.
- Bambu-Log enthaelt weiterhin Wayland-/glfw-Hinweise der headless Umgebung, der Job wurde dennoch abgeschlossen und erzeugte die erwarteten Artefakte.
- Kein realer Druck, kein Druckstart, kein Materialschreiben und kein Druckerneustart.

Backups / Gate:
- Schema-Fix-Backup: v6/backups/2026-09-13-variable-layer-cli-schema/before/.
- Layerheight-Type-Fix-Backup: v6/backups/2026-09-13-variable-layer-cli-layerheight-type/before/.
- HA/Worker-Backup fuer den finalen Type-Fix: /homeassistant/pcc-backups/v6-variable-layer-layerheight-type/20260913-071841.
- Kanonisches Gate nach finaler Korrektur gruen am 2026-09-13 09:18 Europe/Berlin.

Weiter offen:
- Visuelle Browserabnahme der Layeransicht am echten Nutzerprojekt.
- Grafischer Hoehenkurveneditor statt nur Bereichsliste.
- Weitere zurueckgestellte Prozesseditor-Erweiterungen jenseits der aktivierten 25 Werte.
- Support-/Naht-/Material-Malwerkzeuge, robuste Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Releasekriterien. Version bleibt 6.0.0-beta3.

## 29. Layering - Hoehenkurven-Vorschau im Prozessoptions-Editor (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; kleiner Editor-/Layering-Schritt nach der nativen Bambu-Akzeptanz.

Umgesetzt:
- Das Panel fuer variable Schichthoehen zeigt oberhalb der Bereichsliste jetzt eine kompakte Kurven-/Balkenvorschau.
- Die horizontale Balkenbreite folgt der Z-Ausdehnung des Bereichs, die Balkenhoehe folgt der jeweiligen Schichthoehe.
- Die Vorschau wird direkt aus den gespeicherten layer_height_ranges erzeugt; sie fuehrt keine zweite Datenstruktur und keine neue Slicer-Logik ein.
- Ohne aktive Bereiche bleibt der bestehende Leerzustand erhalten.
- Native Uebergabe, HA-/Worker-Validierung, Bambu-Manifestpfad und G-Code-Erzeugung aus Abschnitt 28 bleiben unveraendert.
- Quellbackup: v6/backups/2026-09-13-variable-layer-curve-preview/before/.

Validierung und Live-Stand:
- Neuer Frontend-Quelltest: process options panel exposes a source-owned variable layer-height curve preview.
- Vollstaendiges V6-Gate gruen am 2026-09-13 09:31 Europe/Berlin.
- Deploy-Gate ebenfalls gruen am 2026-09-13 09:31 Europe/Berlin.
- Live ultimate-3d-studio.js: a9754054ff6dbd0c67cd36ee1a0684a267fa3b1edfeca996435b898dc67e08b9
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 013f5580619eb4e8cd09f0ba7c1b08aa2c2a0a4e540b647cb930e8b994906915
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-093136
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browserabnahme der Layeransicht und des Kurveneditors am echten Nutzerprojekt.
- Echte grafische Hoehenkurvenbearbeitung mit Zieh-/Pinselinteraktion statt nur Balkenvorschau und Zahlenliste.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 30. Layering - Direkte Pointer-Bearbeitung der Hoehenkurve (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 29 von reiner Vorschau zu direkter Bedienung.

Umgesetzt:
- Die Hoehenkurve im Prozessoptions-Editor reagiert jetzt auf Pointer/Klick innerhalb vorhandener variabler Schichthoehenbereiche.
- Die X-Position waehlt den betroffenen Z-Bereich, die Y-Position setzt dessen layer_height_mm zwischen 0,04 und 0,56 mm.
- Nach der Aenderung wird derselbe layer_height_ranges-Speicherpfad genutzt wie bei der Zahlenliste; HA-/Worker-Validierung und nativer Bambu-Manifestpfad bleiben unveraendert.
- Der bearbeitete Zahlenwert bekommt Fokus, damit die Aenderung sofort sichtbar und bei Bedarf exakt korrigierbar ist.
- CSS nutzt touch-action:none und Crosshair-Cursor fuer diese Kurvenflaeche. Keine DOM-/Runtime-Injection, kein Reload, keine zweite Datenquelle.
- Quellbackup: v6/backups/2026-09-13-variable-layer-curve-edit/before/.

Validierung und Live-Stand:
- Neuer Frontend-Quelltest: process options panel supports pointer editing for the variable layer-height curve.
- Vollstaendiges V6-Gate gruen am 2026-09-13 14:31 Europe/Berlin.
- Deploy-Gate ebenfalls gruen am 2026-09-13 14:31 Europe/Berlin.
- Live ultimate-3d-studio.js: 4f677c0e13dc3d1c995fb0274d3a307e0f6c5195bb37680339b75ef116dd63b4
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 90dfeb9dbdfa986dde0aaf8492f400db49022252bac67b3c09e8d165e31e83ba
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-143143
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browserabnahme am echten Nutzerprojekt und Bedienpruefung der Kurve mit Maus/Touch.
- Komfortfunktionen fuer echte Hoehenkurvenbearbeitung: Ziehen statt Einzelklick, Bereich teilen/zusammenfuehren, Snap/Presets je Duesenvertrag und Darstellung direkt in der 3D-Layeransicht.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 31. Layering - Drag-Bearbeitung der Hoehenkurve (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 30 von Einzelklick auf Ziehen.

Umgesetzt:
- Die Hoehenkurve fuer variable Schichthoehen unterstuetzt jetzt Pointer-Drag.
- Beim Pointerdown wird die betroffene Kurve verarbeitet, der Pointer wird fuer die Kurvenflaeche gefangen, Pointermove setzt fortlaufend die Schichthoehe, Pointerup oder Pointercancel raeumt die Listener wieder auf.
- Die Berechnung bleibt gleich: X waehlt einen vorhandenen Z-Bereich, Y setzt layer_height_mm im validierten Bereich 0,04..0,56 mm.
- Der Editor schreibt weiterhin ausschliesslich in layer_height_ranges; kein neuer Slicerpfad, kein neues Persistenzmodell und kein Druckerbefehl.
- Quellbackup: v6/backups/2026-09-13-variable-layer-curve-drag/before/.

Validierung und Live-Stand:
- Neuer Frontend-Quelltest: process options panel cleans up drag listeners for variable layer-height curve editing.
- Vollstaendiges V6-Gate gruen am 2026-09-13 14:35 Europe/Berlin.
- Deploy-Gate ebenfalls gruen am 2026-09-13 14:36 Europe/Berlin.
- Live ultimate-3d-studio.js: 6c916f93ecfeea0bb7b57541d2bde78c3d33e2642d8d2cdd7b4be4a52a5acf4d
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 93c3fa1ae38a2b54beff4c9ed64b11ae86841dc107efe1c9c09e6e7035337152
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-143625
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Bereich teilen/zusammenfuehren und Snap/Presets je Duesenvertrag.
- Darstellung der editierbaren Hoehenkurve direkt gekoppelt an die 3D-Layeransicht.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 33. Layering - Duesenvertrag-Presets und Kurven-Snap (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 32 um duesenspezifische Presets fuer variable Schichthoehen.

Umgesetzt:
- Der Workspace reicht den aktiven Nozzle-Durchmesser als nozzle-diameter in das Prozessoptions-Panel.
- Das Panel nutzt den bestehenden nozzle-process-contract und erzeugt daraus Presets zwischen minimaler und maximaler Layerhoehe der aktiven A1-Duese.
- Kurvenbearbeitung per Pointer/Drag snapt jetzt auf diese Presetwerte; die Zahlenfelder bleiben weiterhin direkt editierbar.
- Preset-Buttons setzen die Layerhoehe des aktiven Bereichs und fokussieren danach das zugehoerige Zahlenfeld.
- Ohne erkannte Duese bleibt ein allgemeiner 0,04-0,56-mm-Fallback sichtbar; HA/Worker validieren weiterhin fail-closed gegen den echten Duesenvertrag.
- Keine neue Persistenz und kein zweites Datenmodell: gespeichert wird weiter layer_height_ranges.
- Bei der Umsetzung wurde eine durch den begrenzten Text-Reader abgeschnittene Workspace-Datei aus dem letzten vollstaendigen Source-Backup rekonstruiert und danach mit dem vollen Gate validiert.
- Quellbackup: v6/backups/2026-09-13-variable-layer-nozzle-presets/before/.

Validierung und Live-Stand:
- Frontend-Source-Vertrag in test_v6_nozzle_process_controls.py erweitert.
- Vollstaendiges V6-Gate gruen am 2026-09-13 15:04 Europe/Berlin.
- Deploy-Gate gruen am 2026-09-13 15:04 Europe/Berlin.
- Live ultimate-3d-studio.js: e5aac4dcad1bb02557754379702cadf175f4a2aa62ac59a41bbb56ebd3d6b9cb
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 6f19c4d605e5b16da727fd09b182c589b6f99fd4df1736e83f55f87938394b1f
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-150432
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Darstellung der editierbaren Hoehenkurve direkt gekoppelt an die 3D-Layeransicht.
- Staerkere Inline-Validierung der Zahlenfelder gegen die aktive Duese, ohne Backend-Sicherheitsnetz zu ersetzen.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 34. Layering - Preview-Z-Kopplung der Hoehenkurve (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; koppelt die editierbare Hoehenkurve direkt an die aktuelle Layeransicht.

Umgesetzt:
- Der Workspace berechnet aus der aktuellen Layeransicht die sichtbare Z-Hoehe als visibleLayerZ.
- Der UI-Renderer reicht diesen Wert als preview-z-mm in das Prozessoptions-Panel.
- Das Panel beobachtet preview-z-mm und markiert in der Hoehenkurve den Bereich, dessen Z-Spanne zur aktuellen Preview-Hoehe passt.
- Die Markierung ist rein visuell; layer_height_ranges, Presets, Pointer-/Drag-Bearbeitung und native Bambu-Uebergabe bleiben unveraendert.
- Der bestehende Kurvenvorschau-Test wurde auf die gekoppelte Signatur aktualisiert; der Source-Contract prueft preview-z-mm und visibleLayerZ.
- Quellbackup: v6/backups/2026-09-13-variable-layer-preview-coupling/before/.

Validierung und Live-Stand:
- Vollstaendiges V6-Gate gruen am 2026-09-13 15:09 Europe/Berlin.
- Deploy-Gate gruen am 2026-09-13 15:10 Europe/Berlin.
- Live ultimate-3d-studio.js: 049f6bab056fdd30392f71e911d9ee6b7583e4e4c26a465a3983679afa6a0bba
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 194b2e70dfa26307db0bfa58fe2e37e8a125fe2281daf12919ba408399ea0bfc
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-151021
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Inline-Zahlenvalidierung gegen aktive Duese im Bereichseditor.
- Weitere Prozesseditorparameter, Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## 35. Layering - Inline-Duesenvalidierung im Bereichseditor (2026-09-13)

Status: Frontend live nach vollstaendigem V6-Gate; erweitert Abschnitt 33/34 um direkte Zahlenfeld-Validierung gegen die aktive Duese.

Umgesetzt:
- Die Layerhoehen-Eingaben der variablen Bereiche erhalten min/max direkt aus dem aktiven nozzle-process-contract.
- Manuelle Zahlenwerte ausserhalb des aktiven Duesenbereichs werden direkt am Feld mit einer klaren Meldung blockiert.
- Presetleiste, Pointer-/Drag-Snap und Preview-Z-Markierung nutzen weiter denselben Nozzle-Vertrag.
- Das Backend-/Worker-Sicherheitsnetz bleibt unveraendert fail-closed; die UI-Validierung ersetzt keine native Pruefung.
- Keine neue Persistenz und kein Druckerpfad: gespeichert wird weiter layer_height_ranges.
- Quellbackup: v6/backups/2026-09-13-variable-layer-inline-nozzle-validation/before/.

Validierung und Live-Stand:
- Frontend-Logic-Test und Python-Source-Contract um die Inline-Duesenvalidierung erweitert.
- Vollstaendiges V6-Gate gruen am 2026-09-13 15:14 Europe/Berlin.
- Deploy-Gate gruen am 2026-09-13 15:14 Europe/Berlin.
- Live ultimate-3d-studio.js: d594c76e0b5f935f20f1c7e9e60d9e85d1b5dcd1686491388b9b3ccded2c356e
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c
- Live ultimate-3d-studio-build.json: 2052c33c11647b44979ee96e499a5a71633ab54f7bbaabd398bc336d0c5b17fb
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-151433
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Druckerbefehl, kein Materialschreiben und kein Druckstart.

Weiter offen:
- Visuelle Browser-/Touch-Abnahme am echten Nutzerprojekt.
- Weitere Prozesseditorparameter ueber die 25-Werte-Stufe hinaus.
- Malwerkzeuge, Schnittflaechen-Kappen, Batch-Slicing/Warteschlange und Beta-Ausstiegskriterien. Version bleibt 6.0.0-beta3.

## Nachtrag 2026-09-13 - Druckeinstellungseditor 31 Prozesswerte

Der zurueckgestellte Ausbau des Druckeinstellungseditors wurde fortgesetzt: sechs weitere Speed-/Flow-Parameter sind nun im Frontend modelliert, im HA-Backend fail-closed validiert und in native Bambu-Schluessel materialisiert. Vollstaendiges Gate, Frontend-Deploy, Backend-Backup und HA-Core-Neustart sind abgeschlossen. Die Layeransicht bleibt danach die oberste Folgeprioritaet.

## Nachtrag 2026-09-13 - Layeransicht mit Touch-Schrittsteuerung

Die Layeransicht wurde nach dem Editor-Ausbau fortgesetzt: variable Schichthoehenbereiche werden wieder in der aktiven G-Code-Vorschau-Sidebar angezeigt und der Layer-Slider wurde um Erster/Zurueck/Weiter/Letzter erweitert. Der stabile Preview-Refresh-Pfad bleibt erhalten, Gate und Deploy sind gruen. Die echte Browser-/Touch-Abnahme am Nutzerprojekt bleibt offen.

## Nachtrag 2026-09-13 - Layeransicht schnelle Spruenge

Die Layeransicht wurde fuer grosse Modelle weiter bedienbar gemacht: -10/+10 und direkte Layernummer-Eingabe ergaenzen den Slider. Alle Wege aktualisieren denselben Preview-Zustand inklusive Z-Hoehe, Bahnanzahl, Extrusion und aktiver variabler Schichthoehen-Range. Gate und Deploy sind gruen; Browser-/Touch-Abnahme bleibt offen.

## Nachtrag 2026-09-13 - Layeransicht Fokus-Highlight

Der aktuelle Layer wird in der Toolpath-Vorschau deutlicher fokussiert: Highlight-Flächen werden nur fuer die aktuelle Ebene erzeugt, Historien-Layer bleiben gedimmt. Das verbessert die Lesbarkeit echter G-Code-Bahnen ohne Sampling oder zweite Datenstruktur. Live-Screenshot des HA-Tabs war moeglich, zeigte aber noch die Druckanalyse/Vorgangsliste statt der interaktiven 3D-Layeransicht; die vollstaendige Browser-/Touch-Abnahme bleibt offen.

## 2026-09-13 - Layeransicht: Stage-Badge und Opera-Sichttest

- Aktueller Stand: Layering bleibt oberste Prioritaet nach abgeschlossenem 31-Werte-Druckeinstellungseditor.
- Neu live: Preview-Stage-Badge in `frontend/studio-mega-ui-v2.ts` fuer aktive Layeransicht (`Aktive Layeransicht`, Layer X/Y, Z-Hoehe).
- Test: `layer preview stage exposes current layer badge in the canvas`.
- Gate: vollstaendig gruen 2026-09-13 20:53 Europe/Berlin; Deploy gruen 20:54.
- Live-Hashes: JS e8d36e267b294edd44afade152be941d87c6aaed6327e991d2d04eff166d37f2; CSS 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c; Build JSON b3ee5c54bc2a2defb1a27d8db0f0dda0da404bb88c302601e182dc0b5985f50d.
- HA-Backup: /homeassistant/pcc-backups/v6-frontend/20260913-205452; Source-Backup: v6/backups/2026-09-13-layer-preview-stage-badge/before/.
- Opera-MCP: erster V6-Tab war HA-Websocket-disconnected, frischer Tab zeigte echte G-Code-Vorschau mit 399 Layern und 2.176.118 Bahnen. Neues Stage-Badge ist im Live-Bundle vorhanden, aber im Browserbild noch nicht separat bestaetigt.
- Keine Druckerbefehle, kein Materialschreiben, kein Druckstart, kein HA-Core- oder Worker-Neustart.


## 41. Vorgänge-Scroll, Bambu-Supportstile und Zeitprüfung (2026-09-14)

Status: Quellstand geprüft, vollständiges V6-Gate grün, Backend- und Frontend-Dateien kontrolliert auf HA abgelegt. Version bleibt 6.0.0-beta3.

Umgesetzt:
- Das globale Vorgänge-/Slicing-Popup merkt sich Scrollpositionen über Telemetrie-Rerender hinweg. Die Slicing-Warteschlange darf beim Nachladen nicht mehr auf Anfang springen.
- Der Druckeinstellungseditor bietet Bambu-nahe Supportauswahl: Typ Aus/Normal(auto)/Baum(auto) und Stil Standard, Baum schlank, Baum stark, Baum-Hybrid, Baum Organisch.
- "Nur vom Druckbett" ist jetzt ein echter Pipeline-Wert. Deaktiviert bedeutet: Support darf direkt auf Modellflächen starten; support_build_plate_only=false wird nicht mehr versehentlich normalisiert.
- support_style wird vom Frontend an die Plate-Slice-Route gesendet, dort validiert, in der A1-Nozzle-/Prozessvalidierung abgesichert und im nativen Multimaterial-Materializer in die Prozesssettings geschrieben.
- Der native Materializer legt Support-Nachweise für support_mode, support_style, support_on_build_plate_only und support_threshold_angle ab.
- Die G-Code-Zeitanalyse erzeugt einen consistency-Status für fehlende, widersprüchliche oder unplausible Zeitfelder. Das Analysepanel zeigt dann eine Warnung statt einer stillen Scheingenauigkeit.
- Die Zeitkorrektur ist absichtlich eine Plausibilitätswarnung, keine Behauptung, dass ältere bereits erzeugte Slices nachträglich korrekte Zeiten erhalten.
- Quelltests ergänzt für Popup-Scrollstabilität, Bambu-Supportstile, support_style-Routing und support_build_plate_only=false mit Modellkontakt.

Validierung und Live-Stand:
- Vollständiges V6-Gate grün am 2026-09-14 07:05 Europe/Berlin: Frontend-Test/Build, HA-Core-Build, Python-Tests und homeassistant_compileall erfolgreich.
- Bundle SHA-256: b54f7d72b76b560b29fee67fa473fe2d39bf287cb9b6c5aac4f20ca86e15decb.
- Backend-Dateien auf HA installiert und kompiliert: gcode_analysis.py bf68c42cbd2eb09533d06b1fd2548b37099fd3f1688114c16408db8ab34f1f85, slicer_nozzle_profiles.py 1eb163fcef3ff94112d78c9096a313d869f2cd3806a59dbcf550741b1e38c9fc, materialize-bambu-multimaterial.py 17be3820f6983b53e27fe939fc9e1bc54729f70e82400a90371e2b21dd9d18e4, slicer_plate_views_v2.py 5126d5a84a6993699e0e18a7593ef4296b56795184a50755e3e4b423d9a68659.
- Backend-Backup: /homeassistant/pcc-backups/v6-backend/20260914-070545.
- Frontend-Deploy-Gate grün am 2026-09-14 07:06 Europe/Berlin.
- Live ultimate-3d-studio.js: da4ef294589cdf948bf77d421fcde55f1605887f28347e826307dfb6451203a7.
- Live ultimate-3d-studio.css: 0ec340b2b24dca9bdcd9bb5528e9aa7f72e64acf6b83d82f2c81871c0a03901c.
- Live ultimate-3d-studio-build.json: d8fde1d978a9a9e31f4a1d0e250e25e183f8a3c6b2cf871dfc7a072cc361ce05.
- Frontend-Backup: /homeassistant/pcc-backups/v6-frontend/20260914-070608.
- Kein HA-Core-Neustart, kein Worker-Neustart, kein Slicingjob, kein Druckerbefehl, kein Materialschreiben und kein Druckstart. Die auf HA abgelegten Python-Routen sind nach HA-Core-Reload/Neustart sicher im laufenden Prozess aktiv.

Weiter offen, höchste Priorität:
- Die geslicte Layeransicht muss der Bambu-Studio-Vorschau deutlich genauer entsprechen: dichtere/flächigere Layerdarstellung statt dünner transparenter Linien, Support und Überhänge sichtbar und farblich nachvollziehbar.
- Support-/Überhang-Analyse muss Fälle melden, die Bambu Studio als problematisch erkennt, insbesondere bei deaktiviertem "Nur vom Druckbett" und Baum-Support am Modell.
- Browser-/Touch-Abnahme am echten Nutzerprojekt mit frischem Cache bleibt erforderlich; keine visuelle Akzeptanz behaupten, bis sie wirklich geprüft wurde.


## Reparaturstand 24.09.2026 – bestätigter Prüfzyklus

Die fünf zuvor fehlgeschlagenen Frontendtests sind behoben. Cache-Invalidierung, vollständige Koordinatenprüfung, exakte Z-Schlüssel, sichere Schnittübernahme und Kappenorientierung wurden korrigiert; zwei fehlerhafte Testprüfungen wurden berichtigt. Vorher-Backups: `.bak.20260924-repair-frontend` an den vier betroffenen Dateien.

Kanonischer Windows-Nachweis: **132/132 Frontendtests bestanden, TypeScript-Prüfung und Frontend-Produktionsbuild erfolgreich**. Die HTTP-504-Rückmeldung des Bundle-Aufrufs bedeutete keinen Abbruch; die Ergebnisdateien wurden anschließend direkt ausgelesen.

Zusätzlich ist die HTTP-Antwort des Worker-Release-Endpunkts repariert: HTTP 200 bei Jobstatus `queued`, beschädigte Jobdaten bleiben unverändert. Backup `server.py.bak.20260924-release-response`. Neue echte Handler-Tests ohne Netzwerk-/Druckerzugriff bestehen auch unter Windows. Python-Gesamtstand: **508 bestanden, 2 Hash-Prüfungen fehlgeschlagen, 3 Untertests bestanden**.

Noch offen: Quellhash-/Manifestabgleich nach Abschluss der Queue-Integration. Der Dispatcher verlangt `released_at`, normale Slice-Aufträge liefern diesen Marker noch nicht. Die Batch-View hat weiterhin einen unvollständigen Profilvertrag, einen fehlenden `os`-Import und die Einzel-Release-URL doppelte Platzhalterklammern. Keine vollständige Queue-/Produktionsabnahme behaupten. Nächster Arbeitsschritt: diesen Vertrag gezielt reparieren, funktional testen und danach Hashes/Manifeste aktualisieren.

In diesem Prüfzyklus kein HA-/Worker-Deployment, kein Neustart und kein Druckerbefehl. Filamentprofil-Scrollfix und produktive Druckvorschau unverändert. Die Pflicht zu einer zweiten Änderungsfreigabe hat der Benutzer im vorherigen Verlauf aufgehoben; vor Änderungen gelten weiterhin Ist-Prüfung, Backup, Tests und Rollback. Keine erneute Änderungsfreigabe für die bereits beauftragte Reparatur nötig.


## 12. Fortschrittsnachtrag 2026-09-24 – Queue-/Worker-Lifecycle

### Abgeschlossen und geprüft

- Normale Slice-Aufträge werden bei der Worker-Erstellung automatisch freigegeben.
- Manuelle Queue-Aufträge können explizit gehalten werden; der Worker akzeptiert nur boolesche Werte und die Freigabe ist idempotent.
- Alte Queue-Dateien ohne `manual_release` bleiben kompatibel: sie können manuell freigegeben werden und der Dispatcher blockiert normale Altaufträge nicht.
- Die Release-Route enthält wieder den korrekten URL-Platzhalter; HTTP-Status und fachlicher Jobstatus sind getrennt.
- Regressionstests prüfen normale und manuell gehaltene Jobs, ungültige Werte, idempotente Freigabe, Legacy-Verhalten und beschädigte Jobdateien. Die Tests starten weder Netzwerkdienste noch Druckeraktionen.
- SHA-256-Quellprüfungen und Manifeste sind auf den geprüften Stand gesetzt.

### Qualitätsgate

- 511 Python-Tests und 3 Subtests bestanden.
- Frontend-Logiktests, TypeScript-Prüfung, Produktionsbuild, Home-Assistant-Core-Build und Python-Compileall bestanden.
- Vollständiges Qualitätsgate am 24.09.2026 grün.
- Es gab keine Bereitstellung, keinen HA-Core- oder Worker-Neustart und keinen Druckerbefehl.

### Noch offen – Batch-Aufträge

Die aktuelle Batch-UI liefert noch nicht die vom normalen Studio-Slice-Pfad verlangten aufgelösten Drucker-, Material- und Prozessprofilangaben. Der Batch-Endpunkt weist die Anfrage deshalb derzeit mit HTTP 422 zurück, bevor ein Worker-Upload oder Auftrag angelegt wird. Das verhindert ungültige oder materialseitig erfundene Jobs, bedeutet aber, dass Sammel-Slicing noch nicht nutzbar ist.

Nächster Schritt: denselben Studio-Profilvertrag und dieselben Kompatibilitätsprüfungen für jede Batch-Datei verfügbar machen, die Ergebnisse vor Upload validieren und anschließend Queue-/Freigabeablauf end-to-end testen. Erst nach grünem Gate und abgeschlossenem Batch-Vertrag folgt eine Bereitstellung. Visuelle Browser-/Touch-Abnahme und Beta-Ausstiegskriterien bleiben offen.
