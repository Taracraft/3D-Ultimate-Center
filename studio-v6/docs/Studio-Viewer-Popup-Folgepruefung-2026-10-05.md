# Ultimate Studio · Viewer, 95-Prozent-Popup und Rückkehr aus dem Seitencache

**Prüfstand: 5. Oktober 2026, PC-Gate abgeschlossen laut Dateizeit 01:42:19 CEST.**

## Ergebnis

Der frisch gelesene PC-Quellstand enthielt bereits die Materialfarben-Anpassung des eigenständigen Viewers und das 95-Prozent-Layout der MakerWorld-Detailansicht. Diese Änderungen gingen über den vorherigen Abschlussbericht hinaus. Sie wurden nicht zurückgesetzt oder doppelt neu implementiert. In diesem Abschnitt wurden sie geprüft, die Tests in den regulären Testlauf aufgenommen und ein zusätzlicher Fehler bei der Rückkehr aus dem Browser-Seitencache behoben.

Der zusammengeführte PC-Stand besteht das Qualitätsgate. Das ist kein Nachweis einer erfolgten HA-Bereitstellung, kein erfolgreicher echter MakerWorld-Import und keine Browser-/iPhone-Abnahme. Die betreffenden Agenda-Punkte bleiben bis zu diesen Nachweisen teilweise offen.

## Erhaltener und jetzt mitgeprüfter Funktionsstand

Der eigenständige `slicer-toolpath-viewer.ts` verwendet dieselbe auftragsgebundene Palette wie die Hauptvorschau. Fehlende Einträge behalten ihren Kanalplatz; unbekannte Kanäle werden neutral und ausdrücklich als unbekannt dargestellt. RGB-Werte von Rot, Weiß, Gelb und Schwarz bleiben auch in vorherigen Layern erhalten. Laden, Auftragswechsel und Abbruch verhindern, dass alte Druckbahnen mit einer neuen Palette kombiniert werden. Die Tests vergleichen tatsächliche erzeugte Vertexfarben; ein WebGL-Bild wurde hier nicht abgenommen.

Die MakerWorld-Detailansicht verwendet 2,5 Prozent Abstand je Seite beziehungsweise größere notwendige Safe-Area-Abstände. Ohne zusätzliche Sicherheitsabstände ergibt sich damit eine Fläche von 95 Prozent der sichtbaren Breite und Höhe. Der sichtbare Viewport, nicht die physische Bildschirmgröße, ist maßgeblich. Alte feste Größenobergrenzen sind entfernt. Kopfzeile und Importfußbereich liegen außerhalb der zentralen Scrollbereiche; Fehler besitzen einen eigenen begrenzten Bereich. Beschreibung, Profile, Empfehlungen, Filter und Bilder bleiben vorhanden. Größe und Erreichbarkeit auf einem echten iPhone müssen trotzdem noch visuell geprüft werden.

**Wichtige Verdrahtungsgrenze:** Der eigenständige Viewer ist nicht unter den 130 Eingaben des gelesenen Haupt-Buildmanifests aufgeführt. Seine Quell- und Controllerprüfung belegt daher nicht, dass er als zusätzliche Ansicht in diesem Hauptbundle ausgeliefert wird. Die aktive Hauptvorschau und MakerWorld-Detailansicht sind im Hauptbundle enthalten. Vor einer Aussage zu sämtlichen Laufzeit-Einstiegspunkten ist die eigenständige Einbindung gesondert zu klären.

## Zusätzlicher reproduzierter Fehler und Korrektur

`bindMakerWorldViewport` entfernte bei jedem `pagehide` seine Größen-/Scrollbeobachtung dauerhaft. Eine eingefrorene Seite kann jedoch mit demselben offenen Dialog zurückkehren. Dafür sah die gelesene Funktion keine Wiederaufnahme vor. Der neue Code unterscheidet nun:

- Temporär gespeicherte Seite: Viewport-Ereignisse pausieren; `pageshow` nimmt sie genau einmal wieder auf und liest die aktuellen Maße sofort neu.
- Endgültiges Verlassen oder Schließen: sämtliche Listener werden entfernt; spätere Ereignisse können den Dialog nicht wieder aktivieren.
- Bereits entfernter Dialog oder ungültige Maße: kein Schreiben in einen ungültigen Zustand; gültige letzte Maße bleiben erhalten, bis wieder verwertbare Maße eintreffen.

Keine zusätzlichen Timer, Beobachtung des gesamten DOM, Netzwerkanfragen, Downloads oder Druckaktionen wurden eingeführt. Die vorhandene Importlogik und das bereits geänderte Layout wurden erhalten.

Technische Referenz für den Ereignisvertrag: MDN, „Window: pageshow event“ und „VisualViewport“, am 05.10.2026 gelesen. `pageshow` umfasst dort ausdrücklich die Wiederherstellung eingefrorener mobiler Seiten und die Rückkehr aus dem Back/Forward-Cache. Die Fehlerdiagnose selbst stammt aus dem gelesenen Projektcode und den Regressionstests.

## Tatsächliche Verifikation

| Prüfung | Nachweis |
| --- | --- |
| Acht neue Rückkehr-/Listenerregressionen am kopierten Originalfunktionsstand | Vier bestanden, vier fehlgeschlagen |
| Dieselben acht Prüfungen am korrigierten Funktionsstand, isolierte Linux-Arbeitsumgebung | Acht bestanden, keine ausgelassen |
| Regulärer PC-Frontendlauf einschließlich der 29 vorhandenen Viewer-/Modalprüfungen und acht neuen Prüfungen | **440 bestanden, null Fehler, null ausgelassen** |
| Strenge TypeScript-Prüfung und Produktionsbuild | Rückgabecode jeweils null |
| Python-Prüfung | `success=true`, `pytest_code=0`, Syntax und Imports erfolgreich |
| Kanonisches Gesamtgate | `success=true`; gestarteter Lauf 01:38:26 CEST, neue Statusdatei 01:42:19 CEST |
| Separater protokollierter Viewer-/Modal-Lauf | 29 bestanden; Quellhashes vor und nach dem Lauf identisch |

Die 37 zusätzlich in den regulären Frontend-Testgraphen aufgenommenen Fälle sind bereits in den 440 enthalten. Die nochmals separat ausgeführten 29 Fälle dürfen nicht hinzuaddiert werden. Die aktuelle genaue Python-Testanzahl wurde in diesem Abschnitt nicht ausgelesen; es wird deshalb keine alte Zahl als neues Ergebnis wiederholt.

Die Tests nutzen explizite Ereignis-, DOM- und Netzwerk-Doubles beziehungsweise extrahierte tatsächliche Produktionsfunktionen. Das sind keine Messungen von Browserlayout, Touchbedienung oder nativer Fokusführung. Der Connector meldete beim Gate-Aufruf ein Zeitlimit; das Ergebnis wurde anschließend aus den neuen tatsächlichen Statusdateien gelesen.

## Dateien, Hashes und Sicherung

Neu geändert: ausschließlich die Viewport-Lebenszyklusfunktion in `frontend/makerworld-detail-dialog-v6.ts`; neu `frontend-tests/makerworld-resume.test.mjs`; zwei explizite Testimporte im bereits vom Haupt-Testentry geladenen `makerworld-attribution.test.ts`. Der eigenständige Viewer, seine bestehende Palette und seine 29 Tests wurden in diesem Abschnitt nicht überschrieben.

| Datei | SHA-256 laut PC-Prüfnachweis |
| --- | --- |
| `frontend/makerworld-detail-dialog-v6.ts` | `8ade7c101d8298dd117f3e7caef2ba5d4e768151f880485c13ce26201ff8d6ba` |
| `frontend/slicer-toolpath-viewer.ts` | `81e4c81d2f12b967383c3f3875578112e58c59a5285a06efa9b8bb14814b8e74` |
| `frontend/toolpath-material-colors.ts` | `38630b06a08ca1fabd29b09286d472baec9a5c95ea3ce8617c15aafda25d35fe` |
| HA-Core-JavaScript im PC-Deploybaum | `f2f1790a2965ec7e101fde141cbc893a60b74269e6ef91adb5f5619d354d90ed` |

Vollständige vorab erstellte Originalsicherung auf HA: `backups/20261005-viewer-modal-pass/original/` unter dem HA-Konfigurationsverzeichnis. Ursprünglicher Dialoghash: `7042d25e4c156653071ef59eb14b2fd313ac7b09c83ef250a0eddb8ea9312d21`.

Auf dem PC: `backups/20261005-modal-resume-followup/rollback.json` mit dem genauen Originalfunktionsblock und ursprünglichen Gesamthash; die kleine geänderte Testdatei liegt dort zusätzlich vollständig als `makerworld-attribution.before.ts`. Ein Rückweg darf keine späteren fremden Änderungen überschreiben. Kein Rollback wurde durchgeführt. Die Produktdatei wuchs genau um die 603 Bytes des Funktionsdeltas von 39.081 auf 39.684 Bytes.

## Offene Bereitstellungs- und Agenda-Punkte

Die weitergehende HA-Quelldateiprüfung wurde in diesem Abschnitt vom Werkzeug-Sicherheitscheck gesperrt. Danach wurde kein alternativer administrativer HA-Zugangsweg verwendet. Es erfolgten keine HA-Quellsynchronisierung, kein Austausch produktiver Dateien und kein Neustart. Der neue PC-Build ist daher nicht mit einer Live-Aktivierung gleichzusetzen.

GitHub wurde über den nativen Connector lesend geprüft: `Taracraft/3D-Ultimate-Center`, Standardbranch `main`; die gelesenen Metadaten nennen den letzten Push am 03.10.2026. Es wurde kein unvollständiger Einzeldatei-Abgleich als vollständige Synchronisierung veröffentlicht. Der öffentliche Quellabgleich, das private Prüfdashboard und der Namensmigrationskandidat bleiben offen.

Nächste erforderliche Abnahme: zusammengeführte PC-/HA-Quellen inklusive der bisherigen Reparaturen abgleichen, getrennte geprüfte Bereitstellungsziele verwenden, Live-Hashes bestätigen und anschließend Hauptvorschau sowie Popup auf Desktop und iPhone prüfen. Das MakerWorld-Anmeldungs-/Berechtigungsproblem und der echte Modellimport bleiben getrennt offen. Keine Änderung an Auftragsdaten, Materialzuordnung, G-Code oder Druckreihenfolge; kein Slice und kein Druckerupload.
