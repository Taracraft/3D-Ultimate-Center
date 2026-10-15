# Persistenter Engine-Speicher und Aktivierung

Status: Der Installervertrag fuer einen persistent identifizierten Engine-Speicher,
serialisierte Transaktionen und den atomaren Wechsel kompletter Generationen ist
implementiert. Er startet keine Engine und ist noch nicht mit dem HA-Assistenten
oder einer produktiven Docker-Installation verbunden. Alle echten Releases im
Katalog bleiben pending; container_deploy_ready=false.

## Verantwortungsgrenze

package_activation.py gehoert ausschliesslich zum eingeschraenkten Installer.
API und Worker erhalten weder das Modul noch Schreib- oder Downloadrechte. Der
Installer stellt nach erfolgreicher Aktivierung den exakten Pfad
generations/<generation-id> als SLICER_ENGINE bereit; Compose bindet diesen
Pfad fuer API und Worker nur lesend nach /engine ein.

Eine Aktivierung umfasst immer einen gemeinsamen Satz aus Bambu Studio,
PrusaSlicer und CuraEngine. Einzeldateien oder einzelne Enginewurzeln werden
nicht unter einem laufenden Worker ausgetauscht. Die drei Kandidaten stammen aus
package_staging.prepare_release und werden vor dem Kopieren, nach dem Kopieren
und unmittelbar nach der Stillstandsbestätigung erneut vollstaendig gegen ihre
Dateimanifeste geprueft. Es wird kein enthaltenes Programm oder Skript ausgefuehrt.

## Speicheridentitaet und Rechte

initialize_store() akzeptiert nur einen neuen oder leeren lokalen Ordner.
Symlinks und Windows-Junctions im Pfad werden abgewiesen. Unter POSIX muessen
Besitzer und Schreibrechte privat sein. Angelegt werden:

| Pfad | Zweck |
| --- | --- |
| STORE.json | zufaellige Store-ID und Datentraegerkennung |
| generations/ | unveraenderliche vollstaendige Enginegenerationen |
| transactions/ | atomare Zustandsprotokolle und exklusive Installersperre |
| reservations/ | temporaere echte Platzreservierungen |
| ACTIVE.json | atomarer Zeiger auf genau eine gepruefte Generation |

Die zufaellige Store-ID muss ausserhalb des Mounts in der Installerkonfiguration
aufbewahrt und bei jedem Aufruf mitgegeben werden. Ein nach Neustart fehlender
Bind-Mount faellt dadurch nicht still auf ein leeres Hostverzeichnis zurueck.
Zusaetzlich muessen Datentraegerkennung, Verzeichnisstruktur, Besitz und Modi
passen. Windows-ACL-Vollstaendigkeit wird nicht behauptet; das Produktionsziel
des Installers ist Linux.

Eigene Modelle, Auftraege, Ergebnisse, Profile und Verbindungsdaten gehoeren in
getrennte persistente Pfade. Das Modul verwaltet oder loescht sie nicht.

## Platz und Serialisierung

Vor dem Generationsaufbau wird freier Platz fuer alle manifestierten Dateien
plus Sicherheitsreserve geprueft und durch eine reale Reservierungsdatei
belegt. Linux verwendet posix_fallocate; ein blosses Sparse-Truncate gilt nicht
als Reservierung. Der begrenzte Windows-Fallback dient nur kleinen synthetischen
Pruefungen und ist kein Windows-Produktionsvertrag.

Eine nichtblockierende Dateisperre erlaubt genau einen Installerprozess. Jeder
Versuch besitzt ein atomar geschriebenes Transaktionsprotokoll. Gleichzeitige
Aufrufe scheitern mit einem stabilen Fehler statt parallele Downloads oder
Aktivierungen zu starten.

## Aktivierung, Abbruch und Wiederholung

1. Store-ID, Datentraeger, Rechte und offene Transaktionen pruefen.
2. Alle drei READY-Kandidaten und ihre exakten Dateien pruefen.
3. Platz reservieren und eine neue Generation vollstaendig kopieren.
4. Generationsmanifest schreiben und den gesamten Zielbaum erneut hashen.
5. Vom uebergeordneten Dienst eine eindeutige Worker-Stillstandsbestaetigung
   verlangen; fehlende, falsche oder ausfallende Bestaetigung sperrt den Wechsel.
6. Nochmals alle Dateien pruefen und genau ACTIVE.json atomar ersetzen.
7. Transaktion abschliessen und Platzreservierung entfernen.

Ein kooperativer Abbruch vor dem Zeigerwechsel laesst die aktive Generation
unveraendert. Kandidaten, alte Generationen und fremde Daten bleiben erhalten.
Ein erneuter Versuch darf eine bereits identische, vollstaendig gepruefte
Generation wiederverwenden. Alte Generationen werden nicht automatisch
geloescht; Retention ist eine spaetere, eigene und datenbewahrende Operation.

## Crash und Wiederherstellung

Die Zustandsfolge lautet preparing -> ready -> activating -> activated.
Ein nach Prozessabbruch verbleibender nichtterminaler Zustand blockiert neue
Installationen. Es gibt keinen stillen Auto-Fortschritt und kein automatisches
Loeschen.

- Vor activating darf eine gepruefte Bedienoperation die Transaktion als
  aborted markieren.
- Nach activating muss der Worker weiterhin nachweislich gestoppt sein.
  adopt prueft die neue aktive Generation erneut und uebernimmt sie.
- rollback prueft die vorherige Generation erneut und schaltet den atomaren
  Zeiger auf sie zurueck.

Auch nach einem Rueckweg bleibt die neuere Generation fuer Diagnose oder einen
spaeteren kontrollierten Versuch erhalten. Die spaetere Compose-/HA-Steuerung
muss den aus ACTIVE.json aufgeloesten exakten Generationspfad verwenden und
API/Worker erst danach gemeinsam neu starten.

## Nicht abgenommen

- echte drei freigegebene Enginepakete, Profile, dynamische Plugins und Slices,
- Signatur-, Herkunfts-, Lizenz- und SBOM-Freigabe,
- produktiver Compose-Neustart und Health nach Generationswechsel,
- HA-Host-Erkennung, begrenzter Host-Installer und Einrichtungsassistent,
- frische Installation, Upgrade, Backup/Restore, Cross-Host-TLS und Pilot.

Diese Punkte bleiben Voraussetzungen fuer container_deploy_ready=true.

## 11.10.2026 - Authentifizierter Installer mit Store-/Container-Rueckweg

Der lokal provisionierte InstallerLifecycle verbindet restricted_installer,
host_lifecycle, den festen Dockeradapter und den echten Generationsspeicher.
Activate fuehrt jetzt bei konfigurierter Runtimekopplung zuerst Wartung und
bestaetigten Containerstopp aus, danach Paketaktivierung, Start und Health.
Das Ergebnis ready_paused bleibt gesperrt. Die getrennten Aktionen rollback
und resume beziehen sich auf die urspruengliche Aktivierungs-ID, brauchen
recover-Berechtigung und denselben Principal. Offene/pausierte Wechsel sperren
weitere Installationen. Wiederholung einer bestaetigten Aktion loest sie nicht
nochmals aus; unklarer Resume-Ausgang bleibt explizite Reconciliation.

Storetransaktionen sind an die Aktivierungs-ID und erwartete Generation
gebunden. restore_committed_generation prueft Generationen und Stillstand,
schreibt restoring vor dem Pointerwechsel und restored nach Readback.
Der Rueckweg funktioniert auch nach bereits abgeschlossenem Paketwechsel,
fehlgeschlagenem Containerstart, Orchestratorneustart oder verlorenem
Schreibnachweis. Die alte Generation bleibt erhalten. Ein fremder Vorgang,
abweichende Bindung oder fehlender Stillstandsnachweis blockiert den Rueckweg.

16 neue Integrationstests verbinden Authentifizierung, Store, Lifecycle,
konkreten Adapter und synthetischen Dockerdaemon. Windows zusammen64PASS,
20LinuxSkips,12Untertests; Linux84PASS ohneSkips, inklusive echtem temporaerem
Unix-Socket-Ablauf und falscherLane. Kein Docker-/Engine-/Produktivdienststart.
Installer-/Lifecycle-/Store-Sperren liegen in getrennten Steuerverzeichnissen.

Noch offen: Hostprovisionierung/Erstbootstrap ohne Vorgaenger, HA-Setup und
serverseitige Secretuebernahme, reale Installation/Upgrade/Restore/TLS sowie
freigegebene Enginepakete. Der vorhandene filesystem-only Installerpfad ist
kein Containerinstallationsnachweis. container_deploy_ready bleibt false.
Endgate, PC/HA-SHAs, Originalbackups und trockene Rueckwege im privaten Checkpoint.
