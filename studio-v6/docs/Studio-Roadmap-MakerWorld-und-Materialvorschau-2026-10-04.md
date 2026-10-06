# Ultimate Studio · Roadmap-Nachtrag: MakerWorld und echte Vorschaufarben

Stand: 04.10.2026. Verbindlicher Benutzerauftrag; alle drei Umsetzungspunkte sind offen. Dieser Nachtrag ergänzt `docs/ROADMAP.md` und die bestehende Prüfagenda, ersetzt aber keine noch offenen Arbeiten. Die bisherigen 53 Dashboard-Einträge werden weder neu nummeriert noch als erledigt gezählt. Die nachstehenden Kennungen dienen der eindeutigen Nachverfolgung dieses Nachtrags.

## MW-IMPORT-20261004 · P1 · MakerWorld-Import reparieren

**Beleg:** Im Benutzerscreenshot zu „Folding Box Customizable | Fast“ ist „AMS Text - Customizable“ ausgewählt. Der angezeigte Fehler nennt zunächst HTTP 401 beim Profilmanifest und anschließend HTTP 404 bei Legacy-Downloadversuchen. Dies belegt den fehlgeschlagenen Import, aber weder die genaue Ursache noch, dass das Modell gelöscht oder das gesamte Konto ungültig ist. Eine neue Live-Reproduktion wurde für diesen Nachtrag nicht ausgeführt.

**Ziel:** Das ausdrücklich ausgewählte Druckprofil lässt sich zuverlässig und vollständig über „Im Studio öffnen“, „Galerie“ und „3MF“ übernehmen. Bestehende Modell-, Material- und Projektdaten bleiben bei einem Fehler erhalten.

- [ ] Authentifizierungszustand, Region/Host und Berechtigung des Manifestabrufs prüfen. Anmeldefehler, fehlende Datei, verweigerter Zugriff und abgelaufener signierter Download müssen unterscheidbar sein. Keine Zugangssperren umgehen und keine Zugangsdaten in Logs ausgeben.
- [ ] Öffentliche Design-ID, Druckprofil-/Instanz-ID und interne Download-Modell-ID eindeutig dem gewählten Profil zuordnen. Alternative Druckerprofile dürfen nicht auf das Standardprofil oder ein fremdes Modell zurückfallen.
- [ ] Die 401-Primärursache darf nicht durch nachgeschaltete 404-Fallbacks verdeckt werden. Eine gegebenenfalls notwendige erneute Anmeldung muss verständlich angeboten werden; keine ungeprüften Endpunkte ausprobieren und keine endlose Wiederholung.
- [ ] Nach erfolgreichem Abruf das tatsächliche 3MF prüfen und unverändert mit Platten, Teilen, Geometrie, Materialzuordnung und verfügbaren Profilinformationen übergeben. Kein stiller STL-Ersatz, kein stiller Profilwechsel und kein Slicerjob als Nebenwirkung des Imports.
- [ ] Regressionen für gültige/fehlende/abgelaufene Anmeldung, 401/403/404/429, Zeitlimit, falsche IDs, ungültige Downloadantwort, Doppelklick und Schließen während des Imports ergänzen. Fehlversuche dürfen weder Scheinerfolg noch doppelte Assets erzeugen.
- [ ] Das gemeldete Modell und mindestens ein weiteres Modell beziehungsweise alternatives Druckprofil über alle drei Zielaktionen abnehmen. Ein erfolgreicher Download allein ist noch keine vollständige Studio-Übergabeabnahme.

Zuordnung: bestehender MakerWorld-Import-/Übergabebereich, insbesondere GA-05/GA-08. Status: offen, hohe Priorität.

## PREVIEW-COLORS-20261004 · P1 · Echte Filamentfarben als Standard

**Neue verbindliche Vorgabe:** Die G-Code-Druckvorschau zeigt standardmäßig die dem Auftrag zugeordneten echten Filamentfarben. „Drucktyp“ ist nur eine ausdrücklich manuell wählbare Diagnoseansicht. Die frühere Anforderung „Drucktyp/feature ist Standard“ ist damit ersetzt; alte Tests dürfen diesen früheren Standard nicht wieder erzwingen.

- [ ] Materialmodus beim ersten Öffnen, nach dem Slicen und beim Wiederherstellen eines bestehenden Auftrags aktivieren. Ein aktiver Materialmodus darf bei Layer-/Plattenwechsel, Reconnect, Tabwechsel oder Aktualisierung nicht auf Drucktyp zurückspringen.
- [ ] Farben aus den zum jeweiligen G-Code/Auftrag gehörenden Filamentdaten und dessen Kanalzuordnung beziehen. Eine inzwischen andere AMS-Bestückung darf die historische Vorschau nicht umfärben.
- [ ] Rot, Weiß, Gelb und Schwarz des gemeldeten Vierfarbenmodells an ihren tatsächlichen Modellbereichen anzeigen; keine türkis-rote Drucktyp-Palette als Materialansicht. Normale 3D-Schattierung ist kein Anlass, Materialien durch andere Farbtöne zu ersetzen.
- [ ] Ungültige oder fehlende Kanal-/Farbinformationen sichtbar kennzeichnen. Keine frei erfundenen Ersatzfarben und keine zyklische/moduloartige Zuordnung eines unbekannten Kanals auf einen vorhandenen.
- [ ] Die bisherigen Default-Prüfungen insbesondere in `run_frontend_logic_tests.mjs`, die Initialisierung und Rücksetzpfade in `frontend/studio-mega-workspace-v2.ts` sowie die zugehörigen Verhaltenstests auf den neuen Vertrag umstellen. Die Prüfungen aktualisieren, nicht abschalten.
- [ ] Einfarbige/externe und mehrfarbige AMS-Aufträge, Schwarz/Weiß, bestehende Aufträge, Layer-/Plattenwechsel und Reload/Reconnect prüfen. Die tatsächliche Browseransicht zusätzlich zum Parser-/Logiktest abnehmen.

**Abgrenzung zur Druckreihenfolge:** Dieser Punkt verändert weder G-Code noch AMS-Mapping oder Druckreihenfolge. Die frühere Frage nach einem schwarzen Unterboden bleibt eine getrennte Geometrieprüfung der ursprünglichen Galerie-3MF. „Schwarz zuerst“ innerhalb einer Schicht erzeugt keinen schwarzen Boden unter den Buchstaben. Aus diesem Auftrag wird kein pauschales Umsortieren von Farben abgeleitet.

Zuordnung: bestehender Druckvorschau-/Mehrfarbenbereich. Status: offen, hohe Priorität.

## MW-MODAL-95-20261004 · P2 · MakerWorld-Popup auf 95 Prozent vergrößern

**Zielmaß:** 95 Prozent der aktuell sichtbaren nutzbaren Website-/App-Inhaltsfläche in Breite und Höhe, zentriert. Das entspricht ungefähr 2,5 Prozent Außenabstand je Seite. Gemeint ist nicht die physische Bildschirmgröße einschließlich Browserleisten oder Betriebssystemoberfläche. Das bestehende Erscheinungsbild bleibt erhalten.

- [ ] Dynamische, responsive Größe statt einer zu kleinen festen Pixelobergrenze verwenden. iPhone-Safe-Areas, wechselnde Browserleisten und Bildschirmtastatur dürfen keine wichtigen Bedienelemente außerhalb der sichtbaren Fläche platzieren.
- [ ] Kopfzeile und Schließen sowie untere Importaktionen und verständliche Fehleranzeige erreichbar halten. Beschreibung/Bilder und Druckprofilliste erhalten funktionierende innere Scrollbereiche; kein abgeschnittener Inhalt und keine überlappenden Empfehlungen.
- [ ] Native Modalität, Tastaturfokus, Escape, Fokus-Rückgabe und Scrollpositionen beim Profil-/Tabwechsel erhalten. Vergrößerung darf keine zusätzlichen Downloads, Profiländerungen oder automatischen Aktionen auslösen.
- [ ] Größe und Bedienung bei typischen Desktopfenstern, Browserzoom sowie iPhone-Hoch- und Querformat messen und visuell prüfen. Im normalen Desktopfall soll der äußere Dialog etwa 95 Prozent beider nutzbaren Abmessungen belegen; mobile Sicherheitsabstände haben Vorrang vor abgeschnittenen Aktionen.

Zuordnung: bestehende MakerWorld-Detailansicht und mobile Bedienabnahme. Status: offen, nach den beiden P1-Punkten.

## Reihenfolge und Abschlussbedingungen

1. MakerWorld-Importursache eingrenzen und den gemeinsamen Download-/Übergabevertrag reparieren.
2. Echte Materialfarben und stabile Auswahl in allen Vorschau-Einstiegspfaden umsetzen.
3. MakerWorld-Popup auf das vereinbarte 95-Prozent-Layout bringen und responsiv abnehmen.

Datensicherheit, vorhandene P0-Blocker und noch offene Bereitstellungsvoraussetzungen bleiben vorrangig. Papierkorb/Tags, Duplikatabnahme, Namensmigration und sonstige bestehende Agenda-Punkte entfallen nicht.

Vor Produktbereitstellung: Änderungen sichern; Source-Policy, TypeScript, Frontend-/Backendtests, Builds und Compile-Prüfung bestehen; PC- und HA-Quellen abgleichen; gezielte Bereitstellung mit Rückweg und Live-Hashprüfung; anschließend echte Bedien-/Importabnahme. Der Namensmigrationskandidat muss die neuen Anforderungen ebenfalls übernehmen, bevor er aktiviert wird.

Dieser Nachtrag ist eine Anforderungs- und Roadmapänderung, keine Behauptung einer bereits ausgeführten Reparatur oder Abnahme. Keine Produktivdatei, kein laufender Auftrag, keine Druckerzuordnung und keine Druckreihenfolge wird durch seine Aufnahme verändert. Dashboard-Aktualisierung und öffentlicher Quellabgleich sind separat zu bestätigen. Das Studio bleibt bis zur vollständigen Abnahme im Beta-Status.
