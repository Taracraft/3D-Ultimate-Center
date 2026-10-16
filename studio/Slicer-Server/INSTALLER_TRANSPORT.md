# Lokaler Installationskanal und geschuetzte Tokenuebergabe

Status W32C: zusammenhaengender Linux-Bibliotheksvertrag mit echten temporaeren
Unix-Socket-Tests. Kein produktiver Listener, Dienst oder Container wurde
aktiviert. Der gefuehrte HA-Einrichtungsdialog und der Host-Lifecycle fehlen
weiterhin. container_deploy_ready=false.

## Zustands- und Vertrauensgrenzen

installer_transport.py verbindet einen /W32A-Installer mit exakt dem
snapshot-Provider der W32B-Registry. Es entsteht keine zweite Zugangsdatenbank
und kein neuer frei aufrufbarer Installationsbefehl. Der bestehende
Requestvertrag mit protocol, operation und dauerhaften request_id bleibt erhalten.

Der Hostadapter provisioniert einen absoluten Socketordner unter einem
vertrauenswuerdigen Elternpfad. Besitzer ist der Installer-Benutzer, Gruppe
die gezielt freigegebene Clientgruppe; beispielsweise Modus0750. Gruppen-
Schreibrechte und Rechte fuer andere sind ausgeschlossen. Die festen Sockets
control.sock und mutation.sock erhalten0660. Pfade mit Symlinks und bereits
belegte Socketnamen werden nicht uebernommen oder geloescht. Auch ein verwaister
Socket verlangt eine separate lokale Wiederherstellungsentscheidung.

Der Server liest SO_PEERCRED direkt aus jeder angenommenen AF_UNIX-Verbindung
und akzeptiert nur die lokal konfigurierte Client-UID. Der Client prueft
Verzeichnis-/Socketbesitzer und die echte Server-UID vor Uebertragung des Tokens.
Die aus der Registry gepinnte Installations-ID muss im Frame und in der Antwort
passen. Requestfelder/Forwarded-Header koennen diese Pruefungen nicht ersetzen.

UIDs beziehen sich auf die Linux-Kernelzuordnung des jeweiligen Hosts.
Eine reale HA-Container-/Usernamespace-/Gruppenzuordnung ist noch abzupruefen.
Ein Prozess mit der gleichen privilegierten OS-Identitaet bleibt Teil der
vertrauenswuerdigen Hostgrenze. Die lokale Installations-ID ersetzt kein
Zertifikat fuer entfernte Hosts. Dieses Modul oeffnet keinen TCP-Port;
Cross-Host-TLS ist ein separater ausstehender Kanal.

## Begrenzte Annahme und Protokoll

Zwei unabhaengige Socketannahmen trennen Kontrolloperationen preflight/status/
cancel von initialize/stage/retry/activate/recover. Eine Operation auf dem
falschen Socket wird abgewiesen. Der Kern prueft danach unveraendert Scopes,
Principal-/Belegbesitz, Hostvoraussetzungen und Transaktionssperren.

Standard: zwei Kontrollplaetze und ein Mutationsplatz, hoechstens acht
konfigurierbare Kontrollplaetze. Ein Platz wird vor Peerpruefung, Frameleseweg
und Authentifizierung reserviert. Es gibt keine unbeschraenkte Executorqueue.
Eine volle Spur schliesst weitere angenommene Verbindungen, ohne blockierende
Fehlerausgabe. Die Kernel-Listenbacklogs sind ebenfalls begrenzt.
Ueberlastung garantiert keine Fairness gegen missbraeuchliche berechtigte
Clients; Kontrollkapazitaet ist aber unabhaengig von einer laufenden Mutation.

Frame: Magic STI1,32ASCII-Hexzeichen Installations-ID,2Byte Authlaenge und4Byte
Bodylaenge in Netzwerkbyteordnung, danach Bearerheader und JSON-Body.
Authheader maximal135Bytes; Body1..8192Bytes. Die Laengen werden vor
Payloadallokation geprueft. Antwort:4Byte Laenge plus JSON bis16384Bytes mit
host_id und result. Pro Verbindung genau eine Anfrage/Antwort, kein Pipelining.

Fristen sind positive endliche Sekundenwerte bis300; NaN, Unendlich und bool
werden abgewiesen. Absolute monotone Fristen begrenzen Verbindungsaufbau,
vollstaendige Frameuebertragung und Antwortwartezeit; ein langsamer Bytefluss
erneuert die Frist nicht. Der Server authentifiziert vor dem Routing und der
Kern erneut unmittelbar vor Annahme, jeweils gegen den aktuellen Registryzustand.

Eine Socketfrist unterbricht keine Python-Funktion, blockierende Dateisystem-
Abfrage oder angenommene Mutation. Die maximale Anzahl solcher Arbeiten bleibt
durch die Plaetze begrenzt. Dateisystem-/Hostadapterfristen sind eigenstaendige
Betriebsanforderungen. Kein globaler Authentifizierungslock blockiert beide Spuren.

## Client, Timeout und Herunterfahren

UnixInstallerClient.request(token, request) uebertraegt nur den festen
Kernvertrag. Er stellt die Verbindung nicht automatisch erneut her und
wiederholt keine Mutation. Bei nicht sicher empfangener Antwort meldet er
response_unavailable/outcome=unknown und behaelt eine gueltige request_id.
Dieser Zustand bedeutet weder Erfolg noch Abbruch. Status unter derselben
Identitaet pruefen; bestehende idempotente Wiederholung/Recovery verwenden.

Tokenwechsel behaelt den Principal und den Belegzugriff. Ein widerrufenes Token
sperrt neue Anfragen; bereits angenommene Arbeit darf abschliessen. Status und
Cancel funktionieren waehrend eines synthetisch blockierten Downloads auch
nach einer Tokenrotation. Cancel bestaetigt eine Anforderung; den endgueltigen
Zustand weiterhin per status lesen.

Server.start() startet explizit die lokalen Listener. Import und Konstruktion
aktivieren keinen Dienst. close() stoppt neue Annahmen, entfernt nur eigene
unveraenderte Socket-Inodes und meldet, ob angenommene Arbeit noch auslaeuft.
Es gibt keinen Thread-Kill und kein verdecktes Cancel. ThreadPoolExecutor kann
den Prozess bis zum Abschluss seiner Arbeit am Leben halten; ein echter
Hostdienst muss diesen Auslauf und den bestehenden Recoveryvertrag beachten.

## Geschuetzte lokale Tokenuebergabe

installer_handoff.py ist eine lokale privilegierte Hostfunktion, keine
Remote-Enrollmentroute. Der Hostadapter provisioniert einen separaten privaten
Uebergabeordner unter vertrauenswuerdigen Eltern, beispielsweise0750 mit
Installerbesitzer und Clientgruppe. Weder dieser Ordner noch die Registry
gehoert in einen allgemein beschreibbaren Container- oder Nutzerdatenmount.

publish_handoff erzeugt oder rotiert ueber die vorhandene Registry ein Token
und publiziert ausschliesslich installer-token.json. Die Datei ist0400,
einfach verknuepft und gehoert der konfigurierten Client-UID. Ein separater
nichtblockierender Dateilock serialisiert die Publikation ueber Prozesse.
Datei-fsync, atomarer Austausch, Verzeichnis-fsync und Readback pruefen den
Abschluss. Die Rueckgabe enthaelt keinen Token, sondern nur Principal,
Installations-ID und delivered. Direkte Registry-Administration muss mit
Einrichtung/Rotation desselben Empfaengers koordiniert werden.

read_handoff liest als Clientidentitaet maximal2048Bytes, prueft Besitzer,
exakte Dateirechte, Linkzahl, Schema und extern erwartete Installations-ID.
Das Handoff-Objekt verbirgt Tokens in repr. Die Datei bleibt eine geschuetzte
Klartext-Credentialdatei; nur die Registry ist Digest-only. Tokens niemals in
Browser, Logs, Chat, Kommandozeilenargumente oder Diagnoseantworten uebernehmen.
Die spaetere Uebernahme in HA-Backend-Credentials und anschliessende kontrollierte
Dateibereinigung sind Teil des noch offenen HA-Einrichtungsflows.

Fehlerzustaende:
- credential_commit_unconfirmed: Bereits Registry-Erzeugung/Rotation schlug
  fehl. Der Commit kann trotzdem sichtbar sein; keine erfolgreiche Zustellung
  oder bestaetigte Revokation behaupten. Lokal Zustand abgleichen.
- delivery_failed_revoked: Token wurde erzeugt, aber die Publikation scheiterte;
  der Principal wurde danach erfolgreich widerrufen und bleibt reserviert.
- delivery_failed_revoke_unconfirmed: Auch der Widerruf konnte nicht bestaetigt
  werden. Vor erneuter Erreichbarkeit lokal abgleichen und Zugang sperren.
Ein eventuell vorhandenes Uebergabefile wird nicht als Erfolg gewertet.
Keine automatische Wiederherstellung alter Tokens. Keine Registry-/File-
Mehrdateientransaktion wird vorgetaeuscht. Neue Kopplung nach Widerruf braucht
einen neuen Principal und eine explizite lokale Bereinigung des alten Files.

## Tests und Einschränkungen

Linux:20 Transport- und13 Uebergabetests, dazu61 angrenzende Registry-/Installer-
Pruefungen. Echte temporaere Unix-Sockets, echtes SO_PEERCRED und eine kurzlebige
Clientausfuehrung unter UID/GID65532 lesen eine0400-Token-Datei und erreichen
preflight. Synthetische ZIP-Engines pruefen initialize/stage/activate/status,
Rotation, Widerruf, fremden Principal, Ueberlastung, Timeout/Cancel, Auslauf und
Fehler vor/nach Publikation. Kein echtes Engineprogramm wird ausgefuehrt.

Windows prueft portable Protokoll-/Fristenlogik und angrenzende Kerne. Linux-
Socket-/UID-/Rechtetests sind dort bewusst uebersprungen. Ein Testimport musste
an den bestehenden pytest-Importmodus angepasst werden; kein Produktfehler.

Offen bleiben Host-/Supervisor-Provisionierung und Dienstentrypoint, feste
Lifecycle-Operationen fuer Idle/Stop/Mount/Start/Health/Rueckweg, realer HA-Client
und gefuehrter Setupflow, Cross-Host-TLS, Engine-/Lizenz-/SBOM-Abschluss sowie
reale Installation, Upgrade/Restore und privater Pilot.

## Transport bleibt fuer Erstinstallation unveraendert

Die Erstinstallation benoetigt keine neue Transportoperation. initialize,
stage und activate laufen weiterhin auf der Mutationsspur; rollback und resume
verwenden denselben principalgebundenen Wiederherstellungsweg. Der Kern
entscheidet anhand des verifizierten Stores und des Runtimejournals zwischen
Erstinstallation und spaeterem Generationswechsel. Token, Pfade und
Dockerargumente werden dadurch nicht Teil des Requestschemas.

Der synthetische Windows-Verbund aus Installer, Dockeradapter, FirstInstall,
Lifecycle und Transport umfasst 115 bestandene Tests bei 21 erwarteten
Linux-Socket-Skips. Die echten Unix-Peer-/UID-Nachweise werden nach dem
kontrollierten HA-Quellsync auf Linux erneut ausgefuehrt. Ein HA-Backendclient,
Dienstentrypoint und die sichere Uebernahme/Bereinigung des Handoff-Tokens
bleiben der naechste Integrationsblock.

## HA-seitiger Client und Secret-Uebergabe ()

Die HA-Integration enthaelt einen protokollkompatiblen STI1-Unixclient und einen privaten Credential-Store. Die Host-ID wird nicht aus Request-/Forwarded-Daten oder dem Handoff selbst als Vertrauensanker abgeleitet, sondern muss bereits serverseitig gepinnt sein. Vor dem Senden des Tokens werden Sockettyp, Server-UID und Kernel-Peer geprueft. Antworten mit Secret-/Token-/Passwortfeldern werden verworfen.

Der Handoff wird erst nach atomarem 0600-Write, fsync und Readback der gespeicherten Credentials geloescht. Ein unbestaetigter Store- oder Cleanup-Schritt bleibt explizit fehlgeschlagen. Der gefuehrte Setup-Controller speichert nur Host-ID, Principal-Digest, Request-IDs und bereinigte Ergebnisse. Es gibt keine Shell, keine beliebigen Pfade und keinen Docker-Socket in HA Core.

## Implementierter HA-Dialog und geschuetzte Serververbindung

Der native HA-Optionendialog ist jetzt an den vorhandenen Installerkern
angebunden. Lazy ConfigEntry-Sitzung, blockierungsfreie Datei-/Socketarbeit,
Fortschritt, Bestaetigung, Status/Abbruch, Wiederaufnahme und Rueckweg sind
quellseitig vorhanden. Die automatische Installationsfolge endet pausiert;
Resume ist eine gesonderte Entscheidung, keine automatische Auftragsfreigabe.
Diese Einordnung ersetzt die oben dokumentierten historischen Aussagen,
dass der HA-Client und die Dialoganbindung noch vollstaendig fehlen.

Der neue bestaetigte Dialogschritt "Slicer-Verbindung sicher uebernehmen"
verwendet ausschliesslich das bereits gepinnte lokale Handoff-Verzeichnis.
Die Datei slicer-connection.json enthaelt Schema1, host_id, principal,
transfer_id, base_url und api_secret. Host-ID und Principal muessen zur
bereits bestaetigten Hostkopplung passen. Das Schema akzeptiert nur eine
kanonische HTTPS-Basisadresse und einen gueltigen Header-Schluessel; keine
URL-Zugangsdaten, Query/Fragment, beliebigen Pfade oder Remote-Enrollment.
Datei-, Owner-, Modus-, Link-, Groessen- und Identitaetspruefungen erfolgen
vor und nach der vorhandenen authentifizierten info.json-Verbindungsprobe.

URL und Schluessel werden nie in Formularfelder, Fortschritt, Fehlermeldungen
oder Sitzungsstatus uebernommen. Erst der native OptionsFlow-Abschluss
bekommt sie serverseitig als neue Optionen. Gleichzeitige manuelle Aenderungen
der Verbindung verhindern ein Ueberschreiben; andere aktuelle Optionen
bleiben erhalten. Die Host-Uebergabedatei bleibt bis zu einer gesonderten,
dauerhaft bestaetigten Bereinigung bestehen. Eine fluechtige Speicherzusage
wird nicht mit einem gesicherten Persistenznachweis gleichgesetzt.

Aktuelle Release-Reihenfolge: Implementierung, gepruefte Pakete, Dokumentation
und Veroeffentlichung zuerst; die separate saubere Linux-Neuinstallation ist
der letzte Verifikationstest. Sobald alle anderen Release-Arbeiten wirklich
abgeschlossen sind, darf der Release mit offen ausgewiesenem abschliessendem
Installationstest abgeschlossen werden. Fehlende Laufzeit-/Installations-
Nachweise bleiben not_run. Noch offene Enginepakete, Katalogfreigaben und
Hostprovisionierung werden dadurch weder als implementiert noch getestet
behauptet. Live-System und HAOS-Migration bleiben getrennte Auftraege.
