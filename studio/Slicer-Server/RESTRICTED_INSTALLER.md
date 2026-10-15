# Eingeschraenkter Installationskern

Status: implementierter und synthetisch gepruefter Backendvertrag.
Noch kein erreichbarer Installationsdienst und kein fertiger HA-Assistent.
Es werden keine Engine, Container, Dienste, Jobs oder Drucker gestartet.

## Verantwortung

restricted_installer.py verbindet den kuratierten Enginekatalog mit
package_staging.py und package_activation.py. Der Hostadapter stellt bei
lokaler Einrichtung eine feste HostPolicy, Zugangsdigests und zwei eng
begrenzte Funktionen bereit: dauerhaften Datentraeger pruefen und die zu
dieser Installation gehoerenden Worker stoppen/bestaetigen.

Diese Funktionen und HostPolicy kommen niemals aus einer HTTP-/HA-Anfrage.
Die HostPolicy ist ein vom vertrauenswuerdigen Adapter erhobener Befund,
keine bereits implementierte automatische Host-Erkennung. Ein fehlender
Hostinstaller wird als installer_pairing_required ausgewiesen; fehlende
Laufzeitanbindung als runtime_adapter_required. Nur Linux/amd64 und die
Verpackungsarten managed_docker bzw. supervisor_app werden akzeptiert.

Die externe Steuerablage muss vorab privat angelegt sein und darf weder
innerhalb des Engine-Stores liegen noch diesen enthalten. BINDING.json
speichert dort die Store-ID und den festen Pfad. Der Store wird ausschliesslich
neu/leer angelegt; bestehende Benutzerdaten werden nicht vereinnahmt.
Ein verlorener Mount darf nicht durch Neuanlage am Ersatzpfad verdeckt werden.
verify_volume muss deshalb schon VOR der allerersten Anlage die erwartete
persistente Volume-Identitaet unabhaengig nachweisen.

Der Standardpfad und ein erweiterter eigener Pfad werden spaeter vom
Hostadapter nach dessen Pfad-/Mountpruefung provisioniert. Freie Pfade,
Shellbefehle, Dockerargumente, URLs, Archive und Kataloge sind im Remotevertrag
ausgeschlossen. Der Kern allein erzeugt noch keinen passenden Standardpfad
fuer jeden HA-Installationstyp.

## Authentifizierter Befehlsvertrag

Installer.dispatch(authorization, body, secure_channel=...) erwartet:
- einen vom TLS-/Unix-Socket-Transport bewiesenen sicheren Kanal;
- exakt einen Bearer-Wert mit einem starken zufaelligen Provisionierungstoken;
- lokal konfigurierte SHA-256-Token-Digests, getrennte Principals und Scopes;
- maximal 8192 JSON-Bytes, keine doppelten Schluessel, unbekannten Felder oder
  booleschen Protokollnummern; protocol ist exakt Integer 1.

secure_channel ist eine lokale Transportaussage. Weder ein JSON-Feld noch
X-Forwarded-Proto darf diese Aussage setzen. Authentifizierung erfolgt vor
JSON-Verarbeitung, Digestvergleich in konstanter Zeit. Der Kern generiert
oder verteilt keine Tokens; der spaetere Kopplungsweg muss kryptografisch
zufaellige Tokens erzeugen, geschuetzt speichern, rotieren und widerrufen.
Ein SHA-256-Digest macht ein schwaches Passwort nicht sicher.

Alle Antworten bestehen aus stabilen Codes/Status/IDs. Kein Token, Hostpfad,
Download-URL, Rohfehler oder Kandidatenmanifest wird an den Aufrufer gespiegelt.
Kein eigener Logger erhaelt Header oder Anfragekoerper.

| Operation | Scope | Zusatzfelder | Wirkung |
| --- | --- | --- | --- |
| preflight | inspect | keine | Host-/Volume-/Release-Voraussetzungen und Blocker |
| status | inspect | target | Status einer eigenen Operation |
| initialize | install | request_id | Leeren Store erstellen und externe Identitaet binden |
| stage | install | request_id | Alle drei freigegebenen Engines vorbereiten |
| retry | install | request_id, target | Fehlgeschlagene/abgebrochene Vorbereitung neu versuchen |
| activate | install | request_id, target | Genau die aktuelle gepruefte Vorbereitung aktivieren |
| cancel | install | target | Kooperativen Abbruch einer laufenden Vorbereitung anfordern |
| recover | recover | request_id, target, action | Explizites abort/adopt/rollback nach Prozessabbruch |

request_id und target sind 32 kleine Hexzeichen. Requests enthalten sonst
nur protocol und operation. Principals duerfen fremde Operationsbelege nicht
lesen, abbrechen, aktivieren oder uebernehmen.

Eine ID bindet einen kanonischen Requestdigest dauerhaft. Wiederholungen
geben das belegte Ergebnis zurueck; gleiche ID mit anderem Inhalt wird
abgelehnt. Wiederholung einer noch laufenden/verwaisten Operation verlangt
Recovery. Ein bewusst neuer Versuch verwendet retry mit einer neuen ID.
Status unterscheidet prepared, activated, failed, cancelled und running.
activated belegt nur den Generationenwechsel, nicht einen gesunden Dienst
oder einen fertigen Slicer.

## Transaktionen und Katalogautoritaet

Eine nichtblockierende Dateisperre serialisiert alle Mutationen ueber Prozesse.
Status und kooperativer Stage-Abbruch bleiben waehrend eines Downloads
verfuegbar. Ein paralleler Mutationsaufruf wird abgewiesen. Der spaetere
Transport muss parallele Status-/Cancel-Anfragen bedienen koennen.

Die drei Releases kommen ausschliesslich aus den bei Provisionierung geladenen
Katalogbytes. Vor Aktivierung werden Katalogdigest, interne Kandidatenpfade,
vollstaendige READY-Inhalte und Releasegleichheit nochmals geprueft.
Ein nachtraeglich geaenderter READY-Beleg ist keine Freigabe.
Der folgende Aktivierungskern hasht die Dateien erneut, bestaetigt Worker-
Stillstand, prueft Volume/Store nochmals und wechselt erst dann ACTIVE.json.
Der Hostadapter darf dabei keine laufenden Auftraege unterbrechen; er muss
den vereinbarten Idle-/Wartungszustand selbst nachweisen.

Der derzeit ausgelieferte engine_catalog.json hat KEINEN freigegebenen Release.
Deshalb bleiben echte Stage-/Activate-Anfragen mit engine_releases_pending
gesperrt. Initialisierung und Recovery sind davon unabhaengig; eine spaetere
Katalogsperre darf keinen notwendigen Rueckweg verhindern.

Staging prueft freien Platz fuer deklarierte Downloads, Kandidaten und Kopien
plus Reserve. Dies ist eine Vorpruefung, keine exklusive Speicherreservierung
fuer jeden Archiv-Zwischenstrom. Begrenzte W25-Archive und Fehlerbereinigung
bleiben massgeblich. W26 reserviert fuer die Aktivierung echten Linux-Platz.
Gemeinsame Datentraegernutzung, Quoten, Dateisystem- und Stromausfalltests sind
weiterhin echte Hostabnahmen.

## Abbruch und Wiederherstellung

Cancel bestaetigt die Anforderung, nicht den schon abgeschlossenen Abbruch.
Der endgueltige Zustand muss per status gelesen werden. Ein Rennfall am
Stage-Ende kann bereits prepared liefern; Aktivierung bleibt immer separat.
Die Aktivierungsphase wird nicht als kooperativ abbrechbar beworben.

Crash waehrend Stage: running-Beleg blockiert neue Arbeit. Explizites abort
markiert ihn abgebrochen; retry verwendet eine neue private Vorbereitung.
Alte Kandidaten und Nutzerdaten bleiben erhalten.

Crash waehrend Aktivierung: Recovery ist an die erwartete Generation gebunden.
Ein passender innerer W26-Vorgang kann explizit uebernommen/zurueckgerollt werden.
War ACTIVE schon gewechselt und der innere Vorgang abgeschlossen, kann adopt
nach erneutem Worker-Stopp und Manifestcheck den aeusseren Beleg abschliessen.
Abort ist nur moeglich, wenn die alte Generation noch aktiv ist. Unklare
Zustaende und Initialisierungsabbrueche verlangen host_reconciliation_required.
Es erfolgt keine automatische Reparatur, Loeschung oder Wiederaufnahme.

Der Rueckweg nach einem unsicheren W26-Wechsel ist implementiert. Ein frei
waehlbares Downgrade nach bereits vollstaendig erfolgreicher Installation,
Compose-Umschaltung, Worker-Neustart und Health-bestaetigter Dienstrollback
sind noch keine implementierten Operationen dieses Kerns.

Maximal 128 Operationsbelege; bei vollem Verlauf history_capacity.
Keine automatische Loeschung von Belegen oder Waisen. Fuer Dauerbetrieb fehlt
noch eine nachvollziehbare administrative Archivierungs-/Bereinigungsregel.
Nur der Installer darf seine Steuerablage/Storemetadaten schreiben.
Ein privilegierter konkurrierender Dateimutator liegt ausserhalb dieses Vertrags.

## Nachweise und naechste Schritte

31 neue synthetische Szenarien pruefen Berechtigungen, Payloadgrenzen, feste
Operationen, Idempotenz, echten ZIP-Staging-/Aktivierungsdurchlauf mit
Testbytes, Manipulation, Katalogwechsel, Platzmangel, Prozesssperre, Thread-
Abbruch, Neustart und Recovery. Keine Testdatei ist eine echte Engine.
Der integrierte Durchlauf deckte eine Luecke zwischen W25 und W26 auf:
asdict serialisiert optionale archive_path-Felder als null. Der READY-Leser
normalisiert diese auf den impliziten Quellpfad, bevor er den Katalogvertrag
anwendet. Bestehende explizite Pfadzuordnungen bleiben erhalten.

Offen fuer den naechsten zusammenhaengenden Block:
1. Reale Host-/Supervisor-Erkennung, Volume-Provisionierung und gesicherte
   lokale Kopplung; Hostrechte/TLS/Tokenrotation und begrenzter Transport.
2. Feste Compose-/Supervisor-Laufzeitoperationen inklusive Idle, Stop,
   Mountumschaltung, Start/Health und Dienstrollback.
3. HA-Backendclient und gefuehrter Einrichtungsflow mit kurzen Fehlertexten,
   Fortschritt und automatischer Verbindungseintragung; keine Secrets im Browser.
4. Herkunft/Lizenzen/SBOM/Profile aller drei Releases und echte autorisierte
   Neuinstallation, Upgrade/Restore, Cross-Host-TLS und Pilot.

container_deploy_ready bleibt false. Dieses Modul gehoert zum Hostinstaller,
nicht zum aktuellen Worker-Image oder HACS-Frontend.

## Aktuelle Zugangssaetze fuer Hostkopplung (W32A)

Der optionale lokale credential_provider liefert pro Authentifizierung genau
einen unveraenderlichen Tuple-Snapshot mit hoechstens 128 Credential-Eintraegen.
Bei Verwendung dieses Providers muss die statische credentials-Liste leer sein.
Ohne Provider bleibt die bisherige statische Einrichtung erhalten. Der Provider
ist vertrauenswuerdiger Hostcode und niemals ein Requestfeld.

Ein leerer Snapshot sperrt alle neuen Anfragen. Ein fehlgeschlagener Abruf oder
ein ungueltiger Snapshot liefert credentials_unavailable; es gibt keinen Cache
und keinen Rueckfall auf alte Tokens. Principals und Digests sind eindeutig,
Scopes werden bei jedem Snapshot erneut geprueft. Die sichere Kanalpruefung und
Headergrenzen erfolgen weiterhin vor dem Abruf.

Rotation ersetzt den Digest unter demselben Principal. Dadurch bleiben eigene
Operationsbelege und idempotente Wiederholung erreichbar; ein anderer Principal
erhaelt diese Rechte nicht. Rechteentzug gilt fuer die naechste Authentifizierung.
Bereits angenommene Anfragen duerfen mit ihrem Snapshot abschliessen; Widerruf
bedeutet keinen automatischen Abbruch laufender Aktivierung oder Vorbereitung.
Ein administrativer Notstopp ist ein gesonderter Lifecycle-Vertrag.

Der kuenftige Provider muss die vollstaendige lokale Registry atomar publizieren,
bei Speicherfehlern geschlossen bleiben und bounded/blockierungsarm lesen.
Diese Schnittstelle allein persistiert, generiert oder verteilt keine Tokens.
Geschuetzte Registry, Kopplung/Rotation/Widerruf als lokale Verwaltungsaktionen,
Unix-Peer- bzw. direkte TLS-Pruefung und begrenzter paralleler Transport sind
weiterhin offen. Der Kern startet weiterhin keinen Listener.

## Persistente Registrierung (W32B)

pairing_registry.Registry.snapshot ist als lokaler credential_provider nutzbar.
Einrichtung, Tokenwechsel, Widerruf, Rechte und Commit-/Restore-Grenzen sind in
[HOST_PAIRING.md](HOST_PAIRING.md) beschrieben. Der sichere erreichbare Transport
und die geschuetzte Zustellung sind weiterhin offen.

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

### Lokale Provisionierung und Remotevertrag

Installer(..., runtime=InstallerLifecycle(...)) aktiviert die Kopplung nur aus
vertrauenswuerdiger lokaler Konfiguration. Weder Request noch HA duerfen Driver,
Callbacks, Image-/Composebindung oder Dateipfade liefern. Der bestehende
filesystem-only Aufruf ohne runtime bleibt separat verfuegbar.

rollback/resume haben genau die Felder protocol=1, operation und target mit der
urspruenglichen 32Hex-Aktivierungs-ID. Sie erzeugen keine zweite Transaktions-ID.
Der vorhandene Lifecycle-Beleg serialisiert und korreliert die Aktion. Beide
laufen ausschliesslich auf der begrenzten mutation.sock-Lane; status bleibt auf
control.sock. Verbindungsverlust liefert outcome=unknown plus urspruengliche
request_id. Es gibt keinen automatischen Retry und keinen behaupteten Abbruch.

Status ist ein gespeicherter Beleg, keine Live-Gesundheitspruefung. ready_paused,
restored_paused und complete sind getrennt. recover/adopt/abort darf eine
Runtimeaktivierung nicht als blossen Dateizeigerwechsel quittieren. Ein
pausierter Vorgang muss ueber rollback/resume fortgesetzt werden; nach unklarem
Resume bleibt ein gesonderter lokaler Abgleich erforderlich.

## 12.10.2026 - Erstinstallation hinter derselben Befehlsgrenze

activate verwendet bei fehlender aktiver Generation jetzt die separat
journalisierte FirstInstall-Transaktion. Eine vorhandene Generation verwendet
unveraendert den bisherigen Upgrade-Lifecycle. Der Installer uebergibt nur den
SHA-256 des authentifizierten Principalnamens an den Runtimeadapter. rollback
und resume pruefen weiterhin Recover-Scope, Belegbesitz, Hostbindung und
request_id und werden bei passendem FirstInstall-Beleg dorthin geroutet.

Die oeffentliche Requestform, Scopes und Transportspuren wurden nicht erweitert.
Insbesondere existiert kein callerdefinierter Dockerbefehl, Hostpfad oder
Downloadziel. rolled_back_absent ist ein idempotent erneut lesbarer
Runtimezustand. Die Aktivierungsbelege behalten transaction_id und
previous_generation_id=null, damit der fehlende Vorgaenger nicht erfunden wird.

Der data-init-Aufruf kann den festen zukuenftigen Generationspfad vor dessen
atomarer Kopie an Compose uebergeben, ohne ihn als vorhandene Engine zu
bestaetigen. Alle normalen Starts verlangen weiterhin einen vorhandenen,
geprueften Generationsordner. 115 angrenzende synthetische Tests bestanden
unter Windows, 21 Linux-Socket-Faelle wurden plattformbedingt uebersprungen.
Keine reale Installation oder Deploymentfreigabe.
