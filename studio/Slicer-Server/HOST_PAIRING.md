# Lokale Host-Kopplung und Tokenregistrierung

Status: W32B implementiert die persistente lokale Tokenregistrierung fuer den
Installationskern. Ein erreichbarer Kopplungsdienst, geschuetzte Tokenzustellung,
Unix-/TLS-Transport und der HA-Einrichtungsdialog sind noch offen.
container_deploy_ready bleibt false.

## Provisionierung und Zustandsgrenze

pairing_registry.py wird ausschliesslich von vertrauenswuerdigem Hostcode
aufgerufen. Es bietet keine HTTP-Route, Shell, Docker-Schnittstelle oder
automatische Host-Erkennung. Die Registrierung gehoert neben die externe
Installer-Steuerablage, niemals in den Engine-, Profil- oder Datenmount der
eingeschraenkten Container. Worker und Browser erhalten keinen Zugriff.

Der Hostadapter provisioniert ein leeres absolutes Verzeichnis. Unter Linux
muss es dem Installer-Benutzer gehoeren und darf keine Gruppen-/Fremdrechte
haben (0700). REGISTRY.json und .registry.lock sind regulaere, einfach
verknuepfte private Dateien (0600). Verlinkte Pfadkomponenten, Symlinks,
Hardlinks und Spezialdateien werden abgewiesen. Der Leser prueft sowohl
Pfadmetadaten als auch den geoeffneten Dateideskriptor und begrenzt die Daten
auf 65536 Bytes. Ein FIFO darf den Leseweg nicht blockieren.

Die Windows-Pruefungen sichern portable Kernlogik und Dateisperren ab.
Eine Windows-ACL-Abnahme ist damit nicht erbracht; die Produktinstallation
bleibt Linux/amd64. Prozesse mit derselben privilegierten OS-Identitaet koennen
die Registrierung veraendern und liegen ausserhalb dieser Schutzgrenze.
Elternpfade und ihre Schreibberechtigungen gehoeren zur Host-Provisionierung.

initialize(directory) legt einmalig eine zufaellige Installations-ID und einen
leeren Zustand an. Vorhandene Registrierungen oder Fremddaten werden nicht
uebernommen. Die zurueckgegebene host_id muss der Hostadapter ausserhalb dieser
Datei fest binden. Registry(directory, expected_host_id) liest nur eine exakt
passende Registrierung. Diese lokale Installations-ID ist noch kein
kryptografischer Nachweis der Identitaet eines entfernten TLS-Hosts.

## Lokale Verwaltungsfunktionen

- issue(principal, scopes) erzeugt ein zufaelliges Token aus 48 Zufallsbytes.
  Der Aufrufer erhaelt es einmal als Rueckgabewert; gespeichert wird nur SHA-256.
- rotate(principal, scopes=None) ersetzt das Token eines aktiven Principals.
  Optional werden zugleich die Scopes eingeschraenkt oder neu lokal festgelegt.
  Alte Tokens sind ab der naechsten Authentifizierung ungueltig.
- revoke(principal) markiert den Eintrag dauerhaft als widerrufen. Wiederholung
  ist idempotent. Der Principal bleibt reserviert und kann weder erneut angelegt
  noch durch rotate reaktiviert werden.
- snapshot() liefert den aktuellen unveraenderlichen Satz aktiver Credentials
  direkt an Installer(..., credentials=(), credential_provider=registry.snapshot).

Principals besitzen dauerhaft ihre Operationsbelege. Tokenrotation aendert
diesen Besitzer nicht. Die Wiedervergabe eines widerrufenen Namens koennte
einer neuen Kopplung Zugriff auf alte Belege geben und wird deshalb abgewiesen.
Eine neue Kopplung braucht einen neuen Principal; eine administrative
Beleguebertragung ist nicht implementiert. Maximal 128 Eintraege einschliesslich
Widerrufsbelegen. Keine automatische Loeschung, kein Wiederverwenden alter Namen.

Die Daten enthalten Schema, gepinnte Installations-ID, Revision und die
eindeutigen Principals/Digests/Scopes mit active oder revoked. Doppelte
JSON-Schluessel, Principals, Digests und Scopes sowie fremde Felder werden
abgewiesen. Nur inspect, install und recover sind erlaubt.
Snapshot-Fehler sperren im W32A-Kern neue Anfragen mit credentials_unavailable;
es gibt keinen Rueckfall auf zuvor geladene Zugangsdaten.

## Konkurrenz, Persistenz und Fehler

Eine nichtblockierende Dateisperre serialisiert lokale Verwaltungsaktionen.
Ein zweiter Schreiber erhaelt registry_busy. Leser verwenden den vorherigen
oder den neuen vollstaendigen Zustand und warten nicht auf die Schreibsperre.
Nach jeder Aenderung steigt die Revision. Temporaere Datei, Datei-fsync,
atomarer Austausch und Verzeichnis-fsync schuetzen den Commit.

Scheitert der Austausch vor os.replace, bleibt der bisherige Zustand erhalten.
Ein Fehler NACH dem Austausch kann bedeuten, dass die Aenderung bereits
sichtbar ist, ihre Haltbarkeit aber unklar bleibt. Der Aufrufer darf keinen
Erfolg melden oder einen automatischen Rueckweg auf alte Credentials ausfuehren.
Er liest den Zustand neu und fuehrt gegebenenfalls eine explizite erneute
Rotation durch. Gleiches gilt bei verlorenem Rueckgabewert/fehlgeschlagener
Zustellung: ein bereits erzeugtes Token ist nicht aus der Registry abrufbar.

Widerruf beendet keine bereits angenommene Anfrage. Ein laufender
Generationenwechsel darf nicht durch einen versteckten Token-Abbruch
inkonsistent werden; Notstopp und kooperativer Stage-Abbruch bleiben eigene
Lifecycle-/Installer-Operationen.

Die Revision ist kein externer Anti-Rollback-Zaehler. Ein administrativ
zurueckgespieltes altes Backup derselben Installation kann alte Zugangsdaten
wiederherstellen. Ein Restore muss deshalb isoliert erfolgen und vor erneuter
Erreichbarkeit eine frische Registrierung/Kopplung oder vollstaendige
Credential-Rotation/Widerruf nach einem gesonderten Wiederherstellungsplan
erhalten. Dieser reale Restore-Ablauf ist noch nicht abgenommen.

## Offene Auslieferung

Die Funktionen erzeugen keine produktiven Secrets waehrend der Tests.
Alle Proben laufen in temporaeren Verzeichnissen mit synthetischem
Installerzustand; es gibt keine Engine-, Container-, Service- oder Druckaktion.

Noch umzusetzen und getrennt abzunehmen:
1. Geschuetzte lokale Zustellung und hostseitige Bindung der Installations-ID.
2. Echter Unix-Peer-Nachweis oder direkt verifiziertes TLS; keine Ableitung
   eines sicheren Kanals aus Requestfeldern oder Forwarded-Headern.
3. Begrenzter Transport mit reservierter Status-/Cancel-Kapazitaet und Fristen.
4. Lifecycle/Health/Rueckweg sowie der HA-Backendclient und Einrichtungsdialog.
5. Reale Installation, Rechte-/Dateisystem-/Restore- und Cross-Host-Abnahmen.

## W32C - Lokaler Verbindungsblock

Der lokale Unix-Kanal und die geschuetzte Tokenuebergabe sind jetzt als
zusammenhaengende, Linux-getestete Bibliotheken implementiert. Details,
Aufrufvertrag, Fristen, Auslauf und Fehlerzustaende stehen in
[INSTALLER_TRANSPORT.md](INSTALLER_TRANSPORT.md). Die oben als offen beschriebenen
lokalen Teilfunktionen sind damit auf Quellebene umgesetzt; produktive
Hosteinrichtung, HA-Setup und Cross-Host-TLS bleiben offen.
