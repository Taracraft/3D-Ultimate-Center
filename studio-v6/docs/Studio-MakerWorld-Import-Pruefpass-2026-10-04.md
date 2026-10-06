# Ultimate Studio · MakerWorld-Import: erster Reparaturabschnitt

Stand des bestätigten PC-Gesamtgates: 04.10.2026, 23:56:02 CEST. Roadmap-Bezug: MW-IMPORT-20261004 aus `Studio-Roadmap-MakerWorld-und-Materialvorschau-2026-10-04.md`.

**Status: Download-/Fehlerbehandlung im kanonischen PC-Quellstand implementiert und getestet. Der tatsächliche Import ist noch nicht erfolgreich abgenommen. Keine HA-Aktivierung.**

## Tatsächlicher Ausgangsbefund

Der vorhandene Zugriff auf Home Assistant erlaubte zwei gezielte lesende Anfragen mit dem bereits konfigurierten Bambu-Kontozugang. Zugangsdaten und signierte URLs wurden nicht ausgegeben, kein Konto verändert.

- Modelldetails für „Folding Box Customizable | Fast“, Design `3376079`: HTTP 200.
- Gewähltes Profil „AMS Text - Customizable“: öffentliche Instanz `3840497`, Download-Profil `1034162562`, interne Modellkennung `US3575d30b9f913b`. Diese unterschiedlichen IDs stammen aus derselben realen Detailantwort.
- Der zu genau diesem Profil gehörende Manifestabruf wurde mit HTTP 401 abgewiesen. Es wurde keine signierte Download-URL geliefert.

Damit sind verfügbare Modelldetails und eine korrekte konkrete Profil-/Modellzuordnung belegt. Nicht belegt ist, warum dieser authentifizierte Manifestabruf abgewiesen wird. Insbesondere wurde ein abgelaufenes Token, ein allgemein ungültiges Konto oder ein gelöschtes Modell nicht nachgewiesen. Ein nachfolgender Kontostatusaufruf wurde vom Werkzeug-Sicherheitscheck blockiert; die Authentifizierung wurde nicht über einen anderen administrativen Weg geprüft oder verändert.

## Implementierte Änderung

Der tatsächliche `MakerWorldRuntime.async_download_instance` verwendet bei vollständig ausgewähltem Profil einen einzigen signierten Downloadpfad. Der vorhandene Cache-Adapter für ältere Ansichtsaufrufer führt auf denselben Pfad. Nach einer Ablehnung wird kein Legacy-Endpunkt mehr als Ersatz ausprobiert und kein anderes Profil als Erfolg ausgegeben. Unvollständige oder ungültige Profilzuordnungen werden vor dem Netzwerkaufruf abgewiesen.

Das neue Modul `makerworld_transfer.py` prüft den HTTP-Status vor der Verarbeitung eines Fehlerbodys. HTML statt JSON kann deshalb eine 401-Ablehnung nicht mehr in einen JSON-Lesefehler verwandeln. 401, 403, 404, 429, Weiterleitungen, Verbindungsabbrüche und Zeitlimits erhalten unterschiedliche, verständliche Fehlermeldungen ohne rohe Antworttexte, Zugangsdaten oder signierte URLs. Ein Abbruch bleibt ein Abbruch und löst keine Wiederholung aus.

Der regionale Manifestpfad erhält die ausdrücklich gewählte Profil-ID und interne Modell-ID. Eine signierte Dateiadresse wird mit erhaltener URL-Kodierung übernommen. Konto-Authorization wird nicht an den Dateispeicher weitergereicht. Nicht freigegebene Hosts, eingebettete URL-Zugangsdaten, abweichende Ports und Weiterleitungen werden abgewiesen.

Manifestantworten sind auf 2 MiB, Downloads auf 500.000.000 Byte begrenzt, jeweils auch bei fehlender Größenangabe über den tatsächlichen Datenstrom. Vor der Übergabe erfolgt eine Containerprüfung des ZIP/3MF: Modell- und Content-Type-Einträge, sichere Pfade, keine mehrfachen Namen, verschlüsselte oder verknüpfte Einträge sowie begrenzte Eintragszahl und deklarierte Entpackgröße. Diese Prüfung ist ausdrücklich keine vollständige XML-/Mesh-/CRC- oder Druckfähigkeitsabnahme. Nachgelagerte Modellprüfungen bleiben erforderlich.

Bei erfolgreicher Containerprüfung werden dieselben empfangenen Bytes zurückgegeben. Geometrie, Teile, Materialfarben und Profilmetadaten werden durch diesen Übertragungsschritt nicht umgeschrieben. Die synthetischen Tests sichern die Bytegleichheit; ein erfolgreicher Abruf des echten Benutzermodells wird daraus nicht abgeleitet.

## Tatsächliches Gesamtgate auf dem PC

Kanonischer Projektpfad: `F:\OneDrive - Bad-Timing\Dokumente\GitHub\3D-Ultimate Studio`.

| Prüfung | Ergebnis |
| --- | --- |
| Source-Policy | Bestanden |
| TypeScript | Exitcode 0, keine Fehler |
| Frontend | 370 bestanden, keine Fehler oder ausgelassenen Tests |
| Produktionsbuild und Home-Assistant-Core-Build | Beide bestanden |
| Python-Syntax, Imports, Komponenten-Compileprüfung | Bestanden |
| Python/Worker | 1.562 bestanden, neun ausgelassen, 15 Untertests bestanden |
| Gesamtstatus | success=true; 2026-10-04T23:56:02.182201+02:00 |

55 neue MakerWorld-Prüfungen sind in den 1.562 enthalten und werden nicht hinzuaddiert. Sie prüfen die tatsächlichen Produktfunktionen mit begrenzten Home-Assistant-/HTTP-Doubles, unter anderem Statuszuordnung, korrektes Profil statt Instanz-ID im Manifestpfad, regionale Hosts, exakte signierte URL, unveränderte Archivbytes, Fehler ohne Ersatzaufruf, Abbruch, Größenlimits und unsichere Archive.

Die neun ausgelassenen Fälle sind die bereits vorhandenen Linux-Prozessgruppenprüfungen auf Windows. Ein neuer vollständiger Linux-Lauf wurde in diesem Abschnitt nicht ausgeführt. Die bereits vorhandenen 45 Duplikatoberflächen-Prüfungen bestehen ebenfalls im aktuellen Gesamtgate; sie sind in den 370 enthalten und keine neue Umsetzung dieses Abschnitts.

Zwei Fehler der neu geschriebenen Testumgebung wurden vor dem erfolgreichen Abschluss korrigiert: ein fehlendes Home-Assistant-Konstanten-Double und die Normalisierung eines absichtlich unsicheren ZIP-Testpfades durch Python unter Windows. Diese Fehler werden nicht als zuvor vorhandene Produktdefekte gezählt. Alle 55 neuen Fälle bleiben aktiv; keine Schutzprüfung wurde zugunsten eines grünen Ergebnisses abgeschaltet.

Die Connector-Aufrufe erreichten ihr Zeitlimit. Der Erfolg wurde erst anhand der tatsächlichen abgeschlossenen Dateien `connector-v6-quality-gate.json`, `python-test-status.json` und `frontend-test-status.json` unter `.test-results` bestätigt. Das Feld `deploy.success` dieses Berichts bezeichnet kanonische Buildartefakte, keine Live-Bereitstellung.

## Quellnachweis und Sicherung

Die drei Produktdateien wurden nach dem erfolgreichen Gesamtgate vom kanonischen PC-Dateiwerkzeug mit Größe und SHA-256 bestätigt:

| Datei unter der Studio-HA-Komponentenquelle | Bytes | SHA-256 |
| --- | ---: | --- |
| `makerworld_runtime.py` | 23386 | `90350bfec7830416fe84468e8b49fd11cad71b59f29b6e33e09cf0e229326298` |
| `makerworld_download.py` | 6332 | `046c09f2f5e140ae3fae61b01c7d4605caadddfdfe4f8a9122501b0c67d44637` |
| `makerworld_transfer.py` | 10004 | `b147558c69061cdc060e2817387cdcf47f39485e3ae9df9c2f9d7b09fc347766` |

Die lokale Arbeitskopie des neuen Transfermoduls stimmt mit dessen PC-Hash überein. Bei den beiden bestehenden Dateien wurde vor dem Überschreiben das jeweilige reversible Textdelta einschließlich Originalinhalt der ersetzten Funktionen und Vorherhash gesichert: `backups/20261004-makerworld-import/rollback.json` und `cache-adapter-rollback.json`. Rücknahmen dürfen nur bei exakt passendem geprüftem Nachherstand erfolgen und müssen den jeweiligen Vorherhash wiederherstellen. Fremde Folgeänderungen dürfen nicht überschrieben werden. Ein produktiver Restore wurde nicht ausgeführt.

## Noch offen

MW-IMPORT-20261004 bleibt teilweise bearbeitet: vorhandene Anmeldung/Berechtigung des Manifestabrufs klären, anschließend echten ausgewählten 3MF-Download und vollständige Übergabe für Studio/Galerie/3MF prüfen. Die neue Fehlermeldung ersetzt keine funktionierende Anmeldung. Keine Kontozugangsdaten wurden zurückgesetzt oder automatisch erneuert.

PREVIEW-COLORS-20261004 und MW-MODAL-95-20261004 bleiben zur Umsetzung offen. In diesem Abschnitt wurde weder der Vorschau-Farbstandard geändert noch das MakerWorld-Popup vergrößert. Die Vorgabe Materialfarben statt Drucktyp sowie 95 Prozent nutzbare Breite/Höhe bleibt verbindlich; die älteren gegenteiligen Farb-Tests sind in diesem Backendabschnitt noch unverändert.

HA-Quellsynchronisierung, abgesicherte Komponentenbereitstellung, Live-Abnahme, Namensmigrationskandidat, Hauptroadmap/zentraler Worklog, privates Dashboard und öffentlicher GitHub-Abgleich sind noch nicht nachgeführt. Der ergänzende Arbeitsnachweis dieses Abschnitts liegt unter `backups/20261004-makerworld-import/LIVE_WORKLOG.md`. Vor der nächsten Quellzusammenführung sind alle parallelen Änderungen erneut zu lesen und zu erhalten.

Kein neuer Slice, kein Job-Release, kein produktiver Jobabbruch, kein Druckerupload, kein Druckstart und kein Dienstneustart. Das Studio bleibt Beta.
