# API des Ultimate Slicer Server

Die HTTP-Schnittstelle verbindet Ultimate 3D Studio mit dem eigenständigen Slicing-Dienst. Dieses Handbuch beschreibt den vorhandenen Quellvertrag, einschließlich seiner bestehenden `/api/v1/`-Pfade. Es dokumentiert keine neu entworfene REST-API. Grundlage sind die unten verlinkten Server-, Worker- und Home-Assistant-Quellen.

API und Jobsteuerung sind implementiert. Der ausgelieferte Engine-Katalog enthält weiterhin keine freigegebenen Releases für Bambu Studio, PrusaSlicer oder CuraEngine. Ein vollständiges Runtime-Paket und eine freigegebene Supervisor-App-Paketreferenz fehlen. Daraus folgt keine vollständige Produktfreigabe: `full_release_complete=false`. Installation, Laufzeit, Wiederherstellung und Geräteabnahmen benötigen eigene Nachweise.

## Verbindung und Authentifizierung

Home Assistant verwendet die konfigurierte Serverbasisadresse ausschließlich im Backend. Ein Beispiel ist `https://slicer.example.invalid:8099`; Benutzerinformationen, Queryparameter, Fragmente und zusätzliche Basispfade sind unzulässig. HTTP ist im HA-Verbindungsvertrag ausschließlich für Loopback vorgesehen. Der native Server verlangt für einen Netzwerklistener ein vollständiges TLS-Zertifikat-/Schlüsselpaar; TLS beginnt bei Version 1.2. Der Container-API-Pfad verlangt ebenfalls TLS-Dateien.

Geschützte Aufrufe tragen `Authorization: Bearer <API_SECRET>`. Alternativ akzeptiert der Server `X-API-Token`. Bei gleichzeitig vorhandenem Bearer-Header wird dieser verwendet. Das konfigurierte Secret muss aus 32 bis 256 druckbaren ASCII-Zeichen ohne Leerzeichen bestehen. Der Vergleich erfolgt mit `secrets.compare_digest`; ein fehlendes oder ungültiges Serversecret verhindert den Start. Fehlende oder falsche Anfrageauthentifizierung führt zu HTTP 401 mit `{"error":"unauthorized"}`.

Das Secret gehört weder in URL noch Modellnamen, Prozessargumente, Screenshots oder Protokolle. Die folgenden Beispiele sind reine HTTP-Schemata mit Platzhaltern; sie enthalten keine Zugangsdaten und führen keine Aktion aus:

```http
GET /api/v1/info HTTP/1.1
Host: slicer.example.invalid:8099
Authorization: Bearer <API_SECRET_AUS_GESCHUETZTEM_BACKEND>
Accept: application/json
```

Der HA-Client prüft Zertifikate, bindet Anfragen an die konfigurierte Herkunft und folgt keinen Weiterleitungen. Eigene Authentifizierungsheader oder Transportoptionen dürfen seine Schutzvorgaben nicht überschreiben.

## Endpunkte im Überblick

Alle folgenden API-Aufrufe benötigen Authentifizierung, außer den beiden ausdrücklich öffentlichen Health-Adressen. Tabellenwerte nennen den regulären Erfolgsstatus; zusätzliche Fehler stehen weiter unten.

| Methode | Pfad | Inhalt beziehungsweise Wirkung | Erfolg |
| --- | --- | --- | --- |
| GET | `/api/v1/health`, `/health.json` | Öffentlicher Minimalzustand | 200 |
| GET | `/api/v1/info`, `/info.json` | Version, Protokoll und Servermetadaten | 200 |
| GET | `/api/v1/status`, `/status.json` | Gespeicherter Betriebszustand | 200 |
| GET | `/api/v1/engines`, `/engines.json` | Erkannte Engine-Einträge | 200 |
| GET | `/api/v1/capabilities`, `/capabilities.json` | Beschriebene Schnittstellenfähigkeiten | 200 |
| GET | `/api/v1/diagnostics`, `/diagnostics.json` | Betriebs-/Auftragsdiagnose | 200 |
| GET | `/api/v1/printers`, `/printers.json` | Lokale Druckerprofilübersicht | 200 |
| GET | `/api/v1/files` | Uploadübersicht | 200 |
| POST | `/api/v1/files/<filename>` | Rohe Modelldatei speichern | 201 |
| GET | `/api/v1/jobs` | Bis zu 100 jüngste Aufträge | 200 |
| POST | `/api/v1/jobs` | Geprüften Auftrag in die Warteschlange legen | 202 |
| GET | `/api/v1/jobs/<job_id>` | Auftragsdetail | 200 |
| GET | `/api/v1/jobs/<job_id>/download` | Freigegebenes Ergebnisartefakt abrufen | 200 |
| POST | `/api/v1/jobs/<job_id>/cancel` | Kooperativen Abbruch anfordern | 200 |
| POST | `/api/v1/jobs/<job_id>/release` | Manuell gehaltenen Auftrag freigeben | 200 |
| DELETE | `/api/v1/jobs/<job_id>` | Löschbaren abgeschlossenen Auftrag entfernen | 200 |

Zusätzlich bedient der Server öffentlich `/`, `/index.html` und vorhandene `/assets/<filename>`. Fehlt die Server-Weboberfläche, antwortet ihr Einstieg mit 503 und `ui_not_installed`. Diese Oberfläche ist vom HA-Studiofrontend zu unterscheiden. Nicht aufgeführte Pfade und Methoden haben keine hier zugesicherte Fachsemantik.

## Health, Protokoll und Fähigkeiten

Health liefert ausschließlich `status`, `version`, `api_version` und `uptime_seconds`. Erlaubte Health-Zustände sind `starting`, `ready` und `degraded`; auch ein degradierter Health-Zustand wird mit HTTP 200 übertragen. Eine erfolgreiche Health-Antwort beweist weder Authentifizierung noch Engine-Lizenzfreigabe oder erfolgreiches Slicing.

Das authentifizierte Info-Ergebnis ergänzt zuverlässig die Serverversion, `api_version` und die Fähigkeiten `job_cancellation: true` sowie `cancellation_contract: 1`. Der reguläre HA-Provider erwartet Protokoll **2**, einen passenden Versionsstring, ein Objekt `capabilities` und einen bekannten Bereitschaftszustand. Erst `status: ready` macht ihn betriebsbereit. Für die Abbruchfähigkeit werden zusätzlich der boolesche Fähigkeitswert und der ganzzahlige Abbruchvertrag **1** geprüft.

Die separate Einrichtungsprobe liest nur `/info.json`. Sie akzeptiert in ihrer Metadatenprüfung einen ganzzahligen Protokollwert ab 2 und bestätigt den gelesenen Vertrag; das ersetzt die strengere Providerprüfung auf Protokoll 2 und Betriebsbereitschaft nicht.

Die Capability-Datei beschreibt unter anderem `job_schema_version: 2`, Eingabeformate STL/3MF/OBJ/AMF, Ausgabeformate G-Code/3MF, Engineauswahl, erforderliche Druckerprofile, Fortschritt, ETA, Auftragsdetails und Laufzeitzusammenfassungen. Eine angebotene Enginefamilie ist keine Aussage über ein veröffentlichtes oder auf diesem Host betriebsfähig installiertes Enginepaket. Info, Status und Diagnose stammen teilweise aus aktualisierten Zustandsdateien; sie sind keine transaktionale Gesamtsicht aller Prozesse.

## Dateien und Auftragsschema

Der Uploadendpunkt erwartet den Dateiinhalt unmittelbar als Body, kein Multipart-Formular. Er wertet `Content-Length` aus. Der Dateiname ist ein ASCII-Basisname mit höchstens 200 Zeichen, beginnt alphanumerisch und erlaubt danach Buchstaben, Ziffern, Punkt, Unterstrich und Bindestrich. Zulässige Endungen sind `.stl`, `.3mf`, `.obj` und `.amf`. Ein erfolgreicher Upload liefert `filename` und `size`.

Ein Upload mit demselben Namen ersetzt den vorhandenen Upload atomar über eine temporäre Datei. Es gibt hier keinen dokumentierten Unveränderlichkeits- oder Idempotency-Key-Vertrag. Unterschiedliche Modelle sollten deshalb unterschiedliche Transportnamen erhalten.

Aufträge werden als JSON-Objekt angenommen. Folgende Felder sind im Servercode belegt:

| Feld | Vertrag |
| --- | --- |
| `input_file` | Gültiger Name eines vorhandenen Uploads |
| `printer_profile` | Gültige Kennung eines vorhandenen Druckerprofils |
| `engine` | `auto`, `bambu_studio`, `prusaslicer`, `curaengine`; Standard `auto` |
| `output_format` | `gcode` oder `3mf`; Standard `gcode` |
| `job_id` | Optionale eigene Kennung; sonst erzeugt der Server eine Kennung |
| `native_multimaterial`, `manual_release` | Echte JSON-Boolesche Werte; Standard jeweils `false` |
| `material_plan`, `target_printer`, `process_overrides` | Objekte; `null` wird auf ein leeres Objekt abgebildet |
| `process_profile`, `filament_profile` | Gespeicherte Profilbezeichnungen; Standard jeweils `default` |

`material_plan.assignments` muss bei Angabe ein Objekt sein, `filaments` eine Liste. Für die kuratierten A1-/H2S-Profile prüft der Server zusätzlich Druckermodell, Düse, genaue native Maschinen-/Prozessprofile und passende Prozessgrenzen. Formale JSON-Annahme ersetzt nicht den vollständigen Materialisierungs- und Enginevertrag.

Die Antwort `202 {"job_id":"<JOB_ID>","status":"queued"}` bestätigt die Warteschlangenanlage. Bei `manual_release: false` ist der Auftrag sofort für den Dispatcher freigegeben; bei `true` bleibt er gehalten. Deshalb enthält dieses Handbuch keinen ausführbaren Auftragserzeugungs- oder Releaseaufruf. Beide Operationen können Slicing auslösen und benötigen die dafür vorgesehene Autorisierung.

## Zustände, Wiederholungen und Abbruch

| Zustand | Bedeutung im aktuellen Vertrag |
| --- | --- |
| `queued` | Wartet; kann zusätzlich manuell gehalten sein |
| `slicing` | Vom Dispatcher übernommen |
| `cancelling` | Laufender Auftrag mit Abbruchanforderung |
| `completed` | Verarbeitung erfolgreich beendet |
| `failed` | Verarbeitung fehlgeschlagen |
| `cancelled` | Abbruch abgeschlossen |
| `interrupted` | Unterbrochener Bestand; gesondert zu behandeln |
| `not_found` | Kein zugehöriger Auftragsbestand gefunden |

Eine eigene gültige Jobkennung umfasst höchstens 200 Zeichen und enthält keinen Punkt. Der Auftragseingang übernimmt eine ungeeignete optionale Kennung nicht unverändert, sondern erzeugt eine neue. Bei einer bereits vorhandenen Kennung folgt HTTP 409 mit `job_id_exists`, auch bei gleichem Inhalt. Das ist Duplikatschutz, keine automatische Wiederholung des ursprünglichen Erfolgs. Nach einem Timeout erst den Bestand abgleichen; erneutes Erzeugen mit neuer Kennung kann einen zusätzlichen Auftrag anlegen.

Abbruch ist kooperativ. Ein wartender Auftrag wird unmittelbar `cancelled`; ein laufender Auftrag zunächst `cancelling`. Nur der zuständige Supervisor beendet seine eigenen Prozessgruppen. Fehlt der nachweisbare Eigentümer eines laufenden Auftrags, folgt 409 `job_cancellation_owner_unavailable`. Wiederholter Abbruch bestätigt bei bestehender Anforderung `already_requested`, bei bereits beendetem Abbruch `already_cancelled`. Andere terminale Zustände ergeben 409 `job_already_terminal`.

Die Releaseoperation akzeptiert ausschließlich manuell gehaltene `queued`-Aufträge. Wiederholung im weiterhin wartenden Zustand liefert `already_released`; nach dem Zustandswechsel ist dieser Erfolg nicht pauschal wiederholbar. Abbruch und Freigabe sind kein Druckstart.

## Details, Downloads und Löschen

Die Jobliste liefert ein Objekt mit `jobs`; sie ist auf 100 nach Änderungszeit ausgewählte Kennungen begrenzt und bietet keinen dokumentierten Paginierungsparameter. Details enthalten unter anderem `job`, `result`, `progress`, `runtime`, `engine_result`, Abbruchflags, Zeitstempel und optionale Downloadangaben. `cancellation_available` ist bei wartenden und nachweisbar betreuten laufenden Aufträgen wahr.

Downloads sind nur für `completed` ohne Abbruchanforderung verfügbar. Aus dem Ergebnisverzeichnis wird die jüngste passende G-Code-/3MF-Datei ausgewählt; andernfalls folgt 404 `output_not_found`. Die Antwort ist `application/octet-stream` mit Downloadnamen.

DELETE erlaubt genau `completed`, `failed` und `cancelled`; auch `interrupted` ist in diesem Löschvertrag nicht freigegeben. Gelöscht werden zugehörige Zustands-, Ergebnis- und Laufzeitdateien. Der Upload wird nur entfernt, wenn kein gespeicherter Auftrag ihn mehr referenziert. Die Antwort nennt `deleted`, `previous_status`, `removed_paths` und `input_file_deleted`. Ein erneutes DELETE nach erfolgreichem Entfernen liefert 404 statt eines behaupteten zweiten Erfolgs.

## Grenzen und Fehlerbehandlung

| Grenze | Tatsächlicher Umfang |
| --- | --- |
| Serverupload | Standard 512 MiB, über `max_upload_bytes` konfiguriert |
| Auftragsbody | Höchstens 1 MiB |
| HTTP-Body | Positive explizite `Content-Length`; kein zugesicherter Chunked-Upload |
| HA-Modellannahme | 300.000.000 Bytes, getrennt vom Serveruploadlimit |
| HA-Antworten | JSON 128 MiB, Fehlertext 64 KiB, Artefakt 600.000.000 Bytes |
| Einrichtungsprobe | Antwort 16.384 Bytes; gesamt 8 s, Verbindung/Lesen je 4 s |

Clientgrenzen gelten auch für dekomprimierte Antworten. Betriebsaufrufe besitzen eigene Zeitbudgets, beispielsweise 300 Sekunden für Upload/Download und 15 Sekunden für Jobdetail/Abbruch. Ein Timeout bestätigt keinen Mutationsausgang.

| HTTP | Belegte Beispiele |
| --- | --- |
| 400 | `invalid_content_length`, `invalid_json`, `job_must_be_object`, ungültige Kennungen, Engine-/Material-/Profilwerte |
| 401 | `unauthorized` |
| 404 | Fehlender Upload, Druckerprofil, Auftrag oder Download; unbekannter Pfad |
| 409 | Doppelte Jobkennung, unzulässiger Zustand, fehlender Abbrucheigentümer |
| 413 | `invalid_body_size`, auch bei fehlender oder nichtpositiver Länge |
| 500 | `invalid_job_json` bei beschädigtem gehaltenem Releasebestand |
| 503 | `ui_not_installed` am öffentlichen UI-Einstieg |

Serverfehler sind überwiegend JSON-Objekte mit `error`; ein fehlendes Jobdetail hat dagegen den Zustandsbody mit `status: not_found`. Der HA-Code unterscheidet `SlicerServerConfigurationError`, `SlicerServerAuthenticationError`, `SlicerServerCompatibilityError` und allgemeine `SlicerServerError`. Die Einrichtungsprobe verwendet feste Codes wie `slicer_auth_required`, `slicer_certificate_error`, `slicer_redirect_refused`, `slicer_incompatible` und `slicer_unavailable`. Rohantworten und Diagnosen sind kein geeigneter Ort für Zugangsdaten.

## Quellengrundlage

Maßgeblich sind [Serverrouting](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/48fc0f68801389b49cc82561cf7963f913e3df8e/deploy/homeassistant/host/3d-printer-slicing-server/server.py), [Jobsteuerung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/48fc0f68801389b49cc82561cf7963f913e3df8e/deploy/homeassistant/host/3d-printer-slicing-server/job_control.py), [Status-/Capability-Erzeugung](https://github.com/Taracraft/3D-Ultimate-Slicer-Server/blob/48fc0f68801389b49cc82561cf7963f913e3df8e/deploy/homeassistant/host/3d-printer-slicing-server/refresh-state.sh) und die [HA-Protokollprüfung](https://github.com/Taracraft/3D-Ultimate-Center/blob/e8f86c73a6c9993e331e12d6192139d175a80d29/custom_components/ultimate_3d_studio/slicer_native_contract.py). Die begleitende `API_QUELLEN.json` hält zehn geprüfte Quellen, Commit-/Blobkennungen und SHA-256-Werte fest. Dieser Nachweis dokumentiert Quellenidentität; er führt keine Engine, keinen Auftrag und keine Installation aus.

