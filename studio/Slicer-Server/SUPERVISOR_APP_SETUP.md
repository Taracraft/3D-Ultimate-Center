# Home-Assistant-Einrichtung

Die Integration bietet drei getrennte Verbindungswege: eine Supervisor-App, einen externen Slicer und einen bereits provisionierten Unix-Host. Der externe Weg eignet sich für einen eigenständigen Compose-Server. Ein Fehler im App-Pfad führt nicht automatisch zum Host-Installer.

## Supervisor-Verwaltung

Die Module `slicer_supervisor_app.py` und `slicer_installation_flow.py` verwenden den von Home Assistant bereitgestellten Supervisor-Client. Zusätzliche Core-Mounts, Shellzugang und Docker-Socket sind dafür nicht erforderlich. `hassio` ist eine optionale Abhängigkeit; ohne Supervisor bleiben Studio und externer Slicer nutzbar.

Der Dialog prüft die App und bietet eine bestätigte Installation an, sobald eine freigegebene Paketreferenz hinterlegt ist. Der aktuelle Quellstand enthält noch keine solche Referenz. Deshalb bleibt die Installation gesperrt. Das Prüfimage ohne Engines ist kein Ersatz für das App-Paket.

## Rechte und Identität

Vorgänge benötigen einen aktiven Administrator. Die Identität stammt aus dem authentifizierten HA-HTTP-Kontext, nicht aus Formularfeldern. Nach ausstehenden Store-Abfragen wird die Berechtigung unmittelbar vor einer Änderung erneut geprüft.

Repository, App-Slug und Version müssen zur serverseitigen Paketreferenz passen. Die App darf keine unerwarteten Hostrechte, keinen Dockerzugriff und keinen unkontrollierten Autostart erhalten. Die Metadatenprüfung allein bestätigt allerdings noch keine netzwerklose Engine-Laufzeit.

## Installation

Vor dem Installationsaufruf wird eine lokale Vorgangsabsicht gespeichert und zurückgelesen. Nur bei bestätigter Speicherung wird die Anfrage gesendet. Danach werden Appzustand, Version und Abschlussquittung erneut geprüft.

Installation und Start sind getrennt. Der Adapter startet, aktualisiert oder entfernt keine App. Ein bereits laufender Container wird als `running_unverified` gemeldet; daraus werden keine Zugangsdaten oder eine erfolgreiche Slicing-Verbindung abgeleitet.

## Unterbrochene Vorgänge

Ein Timeout oder geschlossener Dialog löst keine zweite Installation aus. Die lokale `pending`-Absicht bleibt erhalten. Ist die erwartete App später vollständig installiert und gestoppt vorhanden, kann der Administrator einen Bestandsabgleich bestätigen.

Dabei werden App, Version, Schutzkonfiguration und sämtliche gelieferten Supervisor-Jobbäume geprüft. Aktive oder unklare Jobs, fremde Daten, ungültige UUIDs, zu tiefe Bäume und geänderte Quittungen blockieren den Abgleich. Die Prüfung ist auf 2.048 Jobs und 64 Kindebenen begrenzt.

Der Abgleich ändert nur die lokale Quittung zu `reconciled_stopped`. Der Ausgang des ursprünglichen Installationsaufrufs bleibt unbekannt. Es werden keine Jobs gelöscht, Schutzbedingungen verändert oder Apps gestartet. Fehlt die App, wird die alte Absicht nicht als Erlaubnis für eine Neuinstallation verworfen.

Die Zustandsabfragen sind keine globale Supervisor-Sperre. Andere Administratoren können den Bestand später verändern; künftige Start- oder Updateaktionen benötigen deshalb eine eigene aktuelle Prüfung.

## Externer Server

Die vorhandenen Optionen für URL, Secret und TLS werden unabhängig vom App-Pfad verwendet. Zugangsdaten verbleiben in Home Assistant. Die Verbindung sollte erst übernommen werden, wenn Zertifikat, Authentifizierung und API-Kompatibilität passen.

[Entwicklungsstand](RELEASE_STATUS.md) · [Laufzeitkonfiguration](RUNTIME_INSTALLATION.md) · [Hostkopplung](HOST_PAIRING.md)

## Integrated runtime sources

The explicit worker policy, app lifecycle and reproducible context builder are
now included in the source distribution. See [Supervisor runtime](SUPERVISOR_RUNTIME.md).
No public image or app release reference is granted by this source integration.
