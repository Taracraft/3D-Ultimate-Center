# Ultimate Studio · GA-09: Duplikatoberfläche

Stand: 4. Oktober 2026. Status: Quellkandidat im kanonischen PC-Projekt gespeichert; gezielte lokale Tests bestanden. Neues PC-Gesamtgate angestoßen, Abschluss nicht bestätigt. Keine HA-Bereitstellung.

## Erneuter HA-Zugriff

Der erste erneute Root-Shell-Leseaufruf war am 04.10.2026 um 19:02:47 CEST erfolgreich. Projektregeln, ausgewählte Quell-/Livehashes, Dienstzustände und Auftragszähler wurden gelesen. Die native Warteschlange enthielt zu diesem Zeitpunkt keine wartenden oder aktiven Aufträge. Das ist eine Momentaufnahme, keine Aussage über einen späteren Zeitpunkt.

Die HA-Quellkopie enthielt noch den älteren Jobabbruch-Helfer. Im produktiven Workerpfad fehlte `job_control.py`. Quellkopie und ausgeliefertes Frontend hatten weiterhin denselben älteren JavaScript-Hash `29fc7bc256736fc7652555668b3a36ba3e9f9a7ac0bd22b7a96a7e346fb54eec`. Die Integrationseinbindung enthielt die neue Duplikatregistrierung noch nicht.

Der weitergehende Leseaufruf für Bereitstellungsnachweise und Deploymentpfad wurde vom Werkzeug-Sicherheitscheck blockiert. Deshalb wurde keine HA-Synchronisierung oder produktive Aktivierung ausgeführt. Kein alternativer administrativer Zugriffsweg wurde dafür benutzt. Die Meldung belegt keinen Defekt des HA-Servers und keine bestimmte OAuth-Ursache.

## Umgesetzte Galerieoberfläche

Der bislang fehlende sichtbare Teil der Duplikatprüfung ist im PC-Quellstand ergänzt. In der vorhandenen Galerie-Werkzeugleiste öffnet „Duplikate prüfen“ einen nativen modalen Dialog. Die Prüfung wird nur durch den bewussten Aufruf gestartet, nicht beim Laden, Polling oder automatischen Aktualisieren der Galerie.

Die Anfrage verwendet den aktuell gewählten Galerieordner einschließlich Unterordnern. Der Dialog erklärt, dass ein Galerie-Suchfilter diesen Prüfumfang nicht einschränkt und dass Dateiinhalte statt geometrisch ähnlicher Modelle verglichen werden. Der vorhandene API-Basispfad bleibt die einzige Autorität; der neue Baustein führt keinen zusätzlichen versionsgebundenen Endpunkt ein.

Ergebnisse zeigen Dateigröße, SHA-256, zugehörige Pfade sowie unabhängige Dateikopien und zusätzliche Hardlink-Verweise. Die Oberfläche behauptet keine tatsächlich freigebbare Speichermenge. Pro Ansicht werden höchstens 20 Gruppen und pro Gruppe 20 Dateipfade aufgebaut. Gruppen und Pfade sind vollständig über Seitenwechsel erreichbar; ein lokaler Dateipfadfilter löst keinen weiteren Serverscan aus. „Ordner öffnen“ nutzt die vorhandene Galerie-Navigation. Es gibt keine automatische Löschung, Zusammenführung, Modellübergabe oder Druckaktion.

Ladezustand, unvollständige Serverantwort, fehlende Backend-Version, abgebrochene Prüfung, echte Fehler und nachgewiesene Abwesenheit bytegleicher Dateien sind getrennt. Ein Gruppenbericht wird nur akzeptiert, wenn Prüfumfang, Ordner, Abschlussstatus, Lesemodus, Zähler, Pfade, Dateitypen und Größenbeziehungen dem Vertrag entsprechen. Unpassende oder unvollständige Daten erscheinen nicht als erfolgreiche leere Liste.

Schließen, Escape, natives Dialogende und Trennung des Elements brechen die Anfrage über AbortSignal ab. Verspätete Antworten und Ereignisse einer alten Sitzung dürfen keinen geschlossenen Dialog wiederherstellen oder dessen Nachfolger beschädigen. Mehrfaches Öffnen desselben Dialogs startet keinen zweiten Scan. Scheitert die native Modalebene, wird keine Anfrage ausgelöst. Der vorherige Fokus wird soweit noch vorhanden ohne erzwungenes Scrollen zurückgegeben.

Dateinamen und Serverfehlermeldungen werden als Text ausgegeben. Der neue Dialog baut keine dynamischen Inhalte per innerHTML ein. Die Gestaltung enthält schmale Ansichten, umbrechende Dateipfade, eine eigene scrollbare Ergebnisfläche, sichtbaren Tastaturfokus und mindestens 44 Pixel hohe Schaltflächen. Diese Quellmerkmale sind keine tatsächlich durchgeführte iPhone-/Browserdarstellungsabnahme.

## Geänderter Quellumfang

Fünf Produktdateien und zwei Testdateien sind betroffen. Neu sind `frontend/gallery-duplicate-contract.ts`, `frontend/gallery-duplicate-api.ts`, `frontend/gallery-duplicates-dialog.ts` und `frontend-tests/gallery-duplicates.test.ts`. Angepasst sind die vorhandenen Dateien `frontend/gallery-api-v2.ts`, `frontend/gallery-library-pane.ts` und `frontend-tests/gallery-detail-request.test.ts`.

Die bestehende Galerie-API erhält ausschließlich die neue Duplikat-Lesemethode samt Import. Die Galerieoberfläche erhält Import, Werkzeugleistenknopf, dauerhaftes Dialogelement und Ereignisbindung. Der vorhandene Detailanfragetest importiert zusätzlich die neue Testsuite, damit diese vom bestehenden Gesamtgate ausgeführt wird. Seine bisherigen Prüfungen bleiben unverändert. Bestehende Galerie-Dateioperationen, CAD, Bemalung, Materialien, Backend und nativer Worker wurden in diesem Abschnitt nicht verändert.

Alle sieben Schreiboperationen im kanonischen PC-Projekt wurden vom Connector erfolgreich bestätigt; die gemeldeten Dateigrößen stimmen mit dem lokalen Kandidaten überein. Ein anschließender vollständiger PC-Quellhashabgleich wird nicht behauptet. Die beigefügten SHA-Werte bezeichnen die tatsächlich lokal geprüften Kandidatenbytes.

## Tatsächlich geprüfte Ergebnisse

45 neue gezielte Tests wurden in der lokalen Linux-Arbeitsumgebung gegen die Produktquellen ausgeführt und nach der PC-Übernahme erneut wiederholt: jeweils 45 bestanden, keine Fehler, keine ausgelassenen Prüfungen. Die Wiederholung erzeugt keine weiteren eindeutigen Tests.

Abgedeckt sind unter anderem Datenvertrag und Ordnerbindung, Fehlerstatus 401/403/409/422/500, fehlendes Backend, ungültige JSON-Antworten, ein einzelner authentifizierter GET mit Abbruchsignal, native Dialog-Lebenszyklen, Mehrfachklicks, verspätete Antworten, Textausgabe nicht vertrauenswürdiger Dateinamen, 43 Gruppen mit Seitennavigation, 57 Pfade innerhalb einer Gruppe und Hardlink-Darstellung. Zusätzlich werden die tatsächliche Galerie-Mountfunktion und die tatsächliche Galerie-API-Anbindung mit begrenzten Abhängigkeiten ausgeführt.

Die Tests verwenden vorhandene, ausdrücklich begrenzte DOM-/API-Doubles. Sie simulieren keine Browser-Layoutengine, keinen tatsächlichen nativen Fokusfang und keine physische Touchbedienung. Keine echten Benutzerdateien oder produktiven Aufträge wurden dafür verwendet.

Eine separate strenge TypeScript-Prüfung der neuen Vertrags- und Dialogmodule besteht mit `strict`, `noUncheckedIndexedAccess` und `exactOptionalPropertyTypes`. Das ist keine vollständige Projekt-Typprüfung.

Der reguläre PC-Bundle-/Gesamtgate-Aufruf wurde anschließend tatsächlich gestartet und erreichte ein Connector-Zeitlimit. Der danach angefragte Frontend-Prüfstatus wurde vom Werkzeug-Sicherheitscheck blockiert. Somit ist das neue PC-Gesamtgate weder als bestanden noch als fehlgeschlagen bestätigt. Die früheren 325 Frontendtests beziehungsweise 1.507 Python-Tests aus dem abgeschlossenen Vorgängergate dürfen nicht als neues Ergebnis ausgegeben werden. Eine erwartete Erhöhung der Testanzahl wird nicht als beobachteter Testlauf gezählt.

Vor produktiver Bereitstellung müssen die tatsächlichen neuen Statusdateien samt Zeitstempel, vollständigem Test-/Buildstatus und aktuellen Artefakthashes gelesen und abgeglichen werden. Zwei noch offene temporäre Quelldownloadfreigaben wurden erfolgreich widerrufen.

## Sicherung und Nachweise

Vor den Überschreibungen wurde `backups/20261004-gallery-duplicate-ui/rollback.json` am PC angelegt. Das exakte reversible Delta nennt die drei geänderten Originaldateien, deren Vorher-/Nachherhash und alle ersetzten Textblöcke. Die neuen Dateien wurden ohne Überschreiben angelegt. Lokal wurde bestätigt, dass die Rückwärtsanwendung des Deltas alle drei aufgenommenen Originaldateien bytegenau rekonstruiert. Es wurde keine Rücknahme auf dem PC ausgeführt. Spätere fremde Änderungen dürfen nicht überschrieben werden.

Zum lokalen Nachweispaket gehören `gallery-duplicate-ui.patch`, `evidence/candidate-source-manifest.json`, `evidence/final-focused-tests.log`, `evidence/final-standalone-types.log` und `evidence/rollback-verification.json`. Der Patch enthält ausschließlich diese sieben Produkt-/Testdateien und keine Zugangsdaten.

## Offen und nicht als abgeschlossen geführt

GA-09 ist um den UI-Kandidaten erweitert, bleibt aber bis zum bestätigten Gesamtgate, HA-Quellabgleich, gemeinsamer Aktivierung mit dem bereits vorbereiteten Backend und echter Browser-/iPhone-Abnahme teilweise bearbeitet. Papierkorb und Tags sind unverändert weitere offene Aufgaben. Der Jobabbruch-Worker, der öffentliche Repository-Abgleich und die Übernahme in den getrennten Namensmigrationskandidaten sind ebenfalls noch offen.

Der Beta-Status und die Dashboard-Gesamtzählung wurden nicht geändert. Kein tatsächlicher Slice, keine Freigabe oder Löschung eines produktiven Auftrags, kein Druckerupload, kein Druckstart, kein Dienstneustart und keine öffentliche Veröffentlichung wurden ausgeführt.
