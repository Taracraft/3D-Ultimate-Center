# Supervisor-App-Einrichtung und unabhängiger Compose-Slicer

Stand: 16. Oktober 2026. Der native HA-Einrichtungsweg wird auf Supervisor-App-Verwaltung umgestellt; Docker Compose bleibt als eigenständiger Linux-Slicer erhalten. Diese Seite beschreibt den implementierten Verwaltungsadapter, nicht eine bereits ausgelieferte oder auf einem Host installierte Slicer-App.

## Drei ausdrücklich getrennte Wege

Unter Geräte & Dienste → Ultimate 3D Studio → Optionen führt „Slicer einrichten“ jetzt zu einer nativen Auswahl:

| Weg | Verhalten |
| --- | --- |
| Supervisor-App | Unterstützte Store-/App-Schnittstellen des bereits von Home Assistant verwalteten Supervisor-Clients. Keine eigenen Core-Mounts, kein Shell-/Dockerzugriff und kein zusätzlich ausgelesenes Supervisor-Token. |
| Externer Slicer | Bestehende Serveradresse-/Secret-/Verbindungsprüfung, beispielsweise für den eigenständigen Compose-Slicer. Vorhandene Einstellungen bleiben erhalten. |
| Provisionierter Host | Bewusster Zugriff auf den bisherigen gepinnten Unix-Installer. Dessen Schutzvorgaben bleiben unverändert. Dieser Weg ist kein automatischer Fallback bei einem Appfehler. |

Die Integration hängt nur optional von `hassio` ab. Auf HA Container ohne Supervisor bleiben Studio und externe Slicerverbindung nutzbar. Weder Import noch Setup starten einen Supervisor-Aufruf oder eine Installation.

## Implementierter App-Verwaltungsvertrag

Die Integration liefert die beiden Module `slicer_supervisor_app.py` und `slicer_installation_flow.py`. Sie verwenden den HA-eigenen `get_supervisor_client(hass)` und dessen bestehende Methoden `store.repository_info`, `store.addon_info`, `addons.addon_info` und `store.install_addon`.

Die Verwaltungsoperationen sind auf **Status und bestätigte Installation** begrenzt. Es gibt in diesem Adapter keinen Appstart, Stopp, Neustart, Update, Uninstall, Repository-Import oder Options-Write. Diese Einschränkung verhindert insbesondere ein unbemerkbares Starten wartender Slicing-Arbeit während der Einrichtung. Ein bestehender Container wird nicht neu installiert oder vorsorglich gestoppt.

Vor Zugriff wird die aktuelle HA-Benutzeridentität geprüft: aktiver Administrator, nicht lediglich ein übergebenes Wahrheitsfeld. Der Browser liefert weder Repository, App-Slug, Version, Adresse, Schlüssel noch Kommandotext. Die Paketreferenz kommt ausschließlich aus dem geprüften Quellstand.

Repository und App-Slug müssen genau zusammenpassen. Die konkrete Store-/App-Version muss zur freigegebenen Referenz passen. Abgewiesen werden unter anderem lokale/detached Builds, andere Architekturen, deaktiviertes AppArmor, Hostnetz-/PID-Nutzung, Docker-/HA-/Supervisor-API-Zugriff der Ziel-App, Zusatzprivilegien, ausgeschalteter Schutzmodus und unkontrollierter Autostart/Auto-Update. Die spätere App hat ihre Arbeit pausiert bereitzustellen; dieses Modul hebt keine Wartungssperre auf.

Diese Metadatenprüfung ist **kein Nachweis einer tatsächlich netzwerklosen Engine**. App-Metadaten können die später nötigen Kernel-, Prozess-, Mount-, Ressourcen- und Dateirechtemessungen nicht ersetzen.

## Einzelner Vorgang und dauerhafte Wiederholungssperre

Vor dem Installationsaufruf wird eine kleine private HA-Store-Absicht gespeichert. Sie enthält nur Schema, Referenz-Fingerprint und Zustand – keine Zugangsdaten. Eine erfolgreiche Schreibbestätigung ist Voraussetzung für den Aufruf. Unlesbare Daten werden nicht als „noch nichts installiert“ behandelt.

Nach der Absicht werden Referenz, Benutzerberechtigung und Storezustand erneut geprüft. Erst danach wird genau ein Installationsaufruf gesendet. Der native HA-Fortschrittsdialog beobachtet diesen Vorgang; Schließen des Dialogs cancelt nicht die vom Adapter gehaltene Aufgabe und löst keine zweite Installation aus.

Nach eindeutigem Erfolg wird erneut geprüft, dass genau die erwartete App installiert und gestoppt ist. Erst eine erfolgreich gespeicherte Abschlussquittung erlaubt `installed_stopped`. Eine bereits laufende App wird lediglich als `running_unverified` beschrieben; daraus werden keine Verbindung, Engine-Abnahme oder neuen Optionswerte abgeleitet.

Timeout, HA-Unload, uneindeutige Antwort, Versionswechsel oder Fehler der Abschlussquittung behalten die gespeicherte Absicht. Der nächste Dialog beziehungsweise die nächste Runtime verweigert dann eine automatische Wiederholung mit `app_reconciliation_required`. Es gibt keinen Knopf, der diese Absicht blind löscht. Ein expliziter, belegter Abgleich mit dem tatsächlichen Supervisor-Vorgang bleibt eine getrennte Recovery-Aufgabe.

Der offizielle Store-Installaufruf hat keinen Parameter für eine frei gewählte exakte Version. Deshalb werden die Versionen vor und nach dem Vorgang verglichen. Ein währenddessen verschobener Storestand kann erst nach dem Aufruf erkennbar sein; der Adapter darf dann weder Erfolg melden noch selbst starten oder zerstörend rückgängig machen. Der spätere Distributionsvertrag muss unveränderliche Artefakte zusätzlich binden. Ein Versionsstring ist keine Signatur.

## Gegenwärtige ehrliche Releasegrenze

**Es existiert noch keine freigegebene App-Referenz (`SHIPPED_RELEASE = None`).** Der normale App-Dialog meldet deshalb verständlich `app_release_unavailable`. Das Angebot „Installieren“ bleibt ausgeblendet; auch ein künstlich eingesendeter Installationsschritt erzeugt keinen Store-Aufruf.

Eine Referenz darf erst mit dem tatsächlichen App-Paket, seinen Engine-/Quellen-/Lizenznachweisen und dem beibehaltenen Isolationsmodell geliefert werden. Der vorhandene Slicer-Source-Preflight-Container ist dafür nicht ausreichend. Ein Fingerprintfeld oder eine erfolgreiche synthetische Prüfung darf nicht zur vermeintlichen Laufzeitfreigabe umgeschrieben werden.

Der hier umgestellte Dialog und Verwaltungsadapter schließen den bisherigen Widerspruch „jede Einrichtung verlangt zusätzliche Core-Mounts“. Sie schließen noch nicht die vollständige App-Paketierung, Worker-Isolation, sichere Verbindungsübernahme, Upgrade-/Restore-Steuerung oder reale HAOS-Abnahme. Diese Arbeiten bleiben sichtbar im Gesamtabschlussplan.

## Schutz der bestehenden Umgebung

`compose.candidate.yaml`, Container-/Engine-Laufzeit, Host-Endpoint, geschützte Verbindungsübergabe und Engine-Katalog werden durch diesen Block nicht verändert. Keine bereits abgewiesene Hostprovisionierung wird auf einem anderen Weg wiederholt. Es findet keine Live-Migration, zusätzliche Browseranmeldung oder echte Supervisor-/Druckeraktion statt.

Die neue Testmatrix verwendet den echten Adapter und echte asyncio-Abläufe mit ausdrücklich synthetischen Supervisor-Modellen, Benutzer-/Storegrenzen und HA-Formularrendering. Sie prüft unter anderem Adminentzug, ausstehende Absicht, parallele Dialoge, Versions-/Repository-Verwechslung, Zeitlimit, Unload, fehlende Freigabe sowie unveränderte externe/alte Einrichtungswege. Sie ist keine echte Appinstallation und keine visuelle iPhone-Abnahme.

## Geprüfte Schnittstellenquellen

- Home Assistant Core 2026.10.1: `homeassistant/components/hassio/__init__.py`, Export `get_supervisor_client` und bestehende `AddonManager`-Verwendung.
- Offizieller Supervisor-Client: `aiohasupervisor/store.py`, Git-Blob `b4af6bee915d824d741519c62cf8cd6b8494ab04`, sowie `models/addons.py`, Blob `5b71ec27dc8613a45712ca3c823affb5f1802ea2`.
- https://contributors.home-assistant.io/apps/reference/configuration/
- https://contributors.home-assistant.io/apps/supervisor-api/
- https://contributors.home-assistant.io/apps/supervisor-api/apps/

Die aktuellen API-Pfade heißen weiterhin `/store/addons` und `/addons`. Die experimentelle `/v2`-API wird nicht vorausgesetzt. `map` in einer App-Konfiguration beschreibt App-Mounts und nicht beliebige zusätzliche Mounts in Core.

Die vollständige Releaseabgrenzung bleibt in [RELEASE_STATUS.md](RELEASE_STATUS.md) beschrieben: echte Pakete und Integration zuerst, frische separate Linux-Neuinstallation zuletzt. Dieser Verwaltungsblock ist kein Gesamt-Releaseabschluss.


### Konkrete HTTP-Benutzerbindung

Home Assistant Core 2026.10.1 übergibt dem normalen OptionsFlow keinen
`context.user_id`: `FlowManagerIndexView.get_context` liefert dort ein leeres
Dictionary. Der Adapter verwendet deshalb den authentifizierten Benutzer aus
dem HA-eigenen `current_request` und dessen `ha_authenticated`-Markierung.
Ein vom Formular oder Flowkontext übergebener Benutzername ist kein Ersatz.
Ohne authentifizierten HTTP-Kontext wird kein Supervisor-Aufruf gestartet.
Die Benutzer-ID wird vor Erzeugung der Fortschrittsaufgabe übernommen, die
aktuelle Aktiv-/Adminberechtigung unmittelbar vor der Mutation erneut geprüft.
Auch ein Rechteentzug während einer ausstehenden Store-Abfrage wird dadurch
vor dem Installationsaufruf erkannt. Unload und Referenzwechsel während der
letzten Benutzerabfrage werden ebenfalls abgewiesen.

Quellen: `homeassistant/helpers/http.py`,
`homeassistant/helpers/data_entry_flow.py` und
`homeassistant/components/config/config_entries.py`, jeweils Core 2026.10.1.
Die Quelltests simulieren diese HTTP-/Benutzergrenze ausdrücklich; sie sind
keine echte HA-HTTP-Anmeldung oder visuelle Formularabnahme.
