# Docker: vom vollständigen Klon zum prüfbaren Kandidaten

Diese Anleitung gilt für einen **isolierten Linux-Entwicklungspfad**, nicht für
den bestehenden nativen HA-Slicer. Sie startet selbst keine Installation.
Produktivfreigabe, echte Engine-Abnahme und Bestandsmigration bleiben offen.

## 1. Arbeitsverzeichnis richtig wählen

Im eigenständigen Slicer-Repo ist dessen Wurzel das Arbeitsverzeichnis. Im
Studio-Gesamtrepo zuerst nach `studio/` wechseln. Die unten verwendeten relativen
Pfade beziehen sich auf diese Komponentenwurzel. Alle Build-Ausgaben müssen
außerhalb des gesamten Klons liegen; neue absolute Ziele verwenden.

## 2. Quellen und Profilherkunft offline prüfen

```bash
# Nur im eigenständigen Repo vorhanden:
python3 Slicer-Server/build_repository.py --verify .
# In beiden Quellzusammenstellungen verfügbar:
python3 Slicer-Server/verify_profile_sources.py --source-root .
```

Die Profilprüfung verifiziert die mitgelieferten Quellobjekte, Vererbungen und
ausgewählten Werte ohne Download und ohne Engine-Ausführung. Sie installiert
keine vollständige Engine und liefert keinen Drucknachweis.

## 3. Exakten Build-Kontext erzeugen

```bash
SLICER_BUILD_ROOT="$(mktemp -d /tmp/ultimate-slicer-build-XXXXXX)"
python3 Slicer-Server/prepare_context.py --source-root "$PWD" \
  --output "$SLICER_BUILD_ROOT/context"
```

Der Kontext enthält API, Worker, die benötigten Helfer, Metadaten, Provenienz,
Profilquellen und Lizenztexte. Er enthält weder Laufzeitkonfiguration noch
Modelle, API-Token, TLS-Schlüssel oder Engine-Binärdateien. Nur dieser erzeugte
Kontext wird an Docker übergeben, nicht der komplette Entwicklungsordner.

## 4. Base-Image bewusst pinnen und bauen

Zuerst ein für die Dockerfile-Paketnamen und Zielarchitektur geprüftes Python-
Basisimage als vollständige Referenz `Name@sha256:…` festlegen. Kein Digest wird
hier erfunden; ein bewegliches Tag ist kein reproduzierbarer Release-Nachweis.

```bash
export PYTHON_BASE='GEPRUEFTE_REFERENZ@sha256:GEPRUEFTER_DIGEST'
docker build --pull=false --build-arg PYTHON_BASE="$PYTHON_BASE" \
  --tag ultimate-slicer-server:candidate "$SLICER_BUILD_ROOT/context"
docker image inspect ultimate-slicer-server:candidate
```

Das Beispiel wird erst mit einer echten bestätigten Referenz ausführbar. Beim
Imagebau werden Distribution-Pakete installiert; deren konkrete Versionen und
Architektur müssen für einen Release ebenfalls inventarisiert und abgeglichen
werden. Ein gepinntes Base-Image allein pinnt nicht jede apt-Abhängigkeit.

## 5. Rein lesenden Container-Preflight ausführen

```bash
docker run --rm --network none --read-only --user 65532:65532 \
  --cap-drop ALL --security-opt no-new-privileges:true \
  ultimate-slicer-server:candidate check
```

Das Standardkommando ist eine Paketprüfung, kein Slicing-Dienst. Weder Drucker
noch bestehende HA-Daten werden eingebunden. Für genaue Testmatrix und
Kernelgrenzen siehe [CONTAINER_TESTING.md](CONTAINER_TESTING.md).

## 6. Laufzeit-Vertrag verstehen

Für den isolierten Diensttest ist `compose.candidate.yaml` maßgeblich:

| Variable | Inhalt | Rechte und Grenze |
| --- | --- | --- |
| `SLICER_IMAGE` | Exakte lokal vorhandene Image-ID | `pull_policy: never`, kein frei erfundenes Registry-Image |
| `SLICER_DATA` | Neues persistentes Datenverzeichnis | UID/GID 65532; keine produktiven Volumes übernehmen |
| `SLICER_ENGINE` | Separater Engine-Speicher | API/Worker nur lesend; für Leerlauf darf er leer sein |
| `SLICER_PROFILES` | Eigenes persistentes Profilverzeichnis | Initialisierung separat; API/Worker nur lesend |
| `SLICER_TOKEN` | Datei mit lokal erzeugtem starken Secret | Privat, Modus 0600, nicht Secret-Text in Git/Umgebung |
| `SLICER_TLS` | Verzeichnis mit `server.crt` und `server.key` | Hostname und Vertrauen prüfen; Schlüssel privat |
| `SLICER_BIND` | Bewusste Bind-Adresse | Standard Loopback, externe Erreichbarkeit separat freigeben |
| `SLICER_PORT` | Lokaler API-Port | Standard 8099 |
| `SLICER_BOOTSTRAP_REQUEST_ID` | Eigene Initialisierungs-/Wartungskennung | Nur den eigenen bestätigten Wartungszustand aufheben |

Compose trennt API, netzlosen Worker, Dateninitialisierung, Profilinitialisierung
und explizites Wartungsende. Fehlende Hostpfade werden nicht automatisch als
leere Verzeichnisse angelegt. Kein Docker-Socket, keine zusätzlichen
Capabilities, kein Root-Worker und keine automatische Restart-Schleife.

## 7. Erfolg richtig beurteilen

HTTP-Health 200 kann bei fehlender Engine ausdrücklich `degraded` bedeuten.
Eine erfolgreiche Token-Prüfung der Info-API ist keine erfolgreiche Slice-
Prüfung. Ein gesunder Idle-Worker ist keine Engine-/Profil-/Hardwarefreigabe.

Vor einem späteren echten Betriebswechsel werden mindestens genaue Engine-
Herkunft, Bibliotheken, vollständige Profile, unabhängige Linux-Installation,
TLS-Verbindung, kontrollierter Stopp/Wiederanlauf, Upgrade und Restore benötigt.
Diese Laufzeiteigenschaften müssen zur eingesetzten Konfiguration passen.

[Entwicklungsstand](RELEASE_STATUS.md)
