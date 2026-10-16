# Ultimate Slicer Server

Der eigenständige Slicer-Dienst für **Ultimate 3D Studio**: HTTP-API, kontrollierter Worker, native Linux-Pakete und Docker-Compose-Kandidat – mit den vollständigen zugehörigen Quellen, Profilnachweisen, Tests und Betriebsanleitungen.

[Anleitung](Slicer-Server/README.md) · [Docker-Schnellstart](Slicer-Server/DOCKER_QUICKSTART.md) · [Natives Linux-Paket](packages/ultimate-slicer-server/README.md) · [Wiki-Dateien](Slicer-Server/wiki/Home.md) · [Quellumfang](Slicer-Server/REPOSITORY_CONTENTS.md) · [Lizenzen](SOURCE_NOTICES.md) · [Gemeinsame Abschlussmatrix](Slicer-Server/wiki/Release-Abnahme.md)

> Entwicklungs- und Prüfkandidat. Vollständige Komponentenauslieferung bedeutet nicht Produktivfreigabe. Engine-Binärdateien und private Betriebsdaten sind nicht enthalten. Die vollständige Engine-/Host-/Paketfreigabe fehlt noch. Der letzte frische Linux-Test folgt erst auf den ansonsten vollständigen Release; eine Produktivmigration bleibt gesondert.

## Was hier jetzt vollständig liegt

| Bestandteil | Inhalt und Einstieg |
| --- | --- |
| API und Jobsteuerung | Server, Jobzustände, Dispatcher, Fortschrittsleser, Statusaufbereitung und Journal unter `deploy/homeassistant/host/3d-printer-slicing-server/` |
| Worker-Abhängigkeiten | Die zehn tatsächlich eingebundenen Geometrie-, Filament-, Maschinen- und Artefaktverträge unter `deploy/homeassistant/custom_components/ultimate_3d_studio/` |
| Native Linux-Auslieferung | Deterministischer Paketbau, lesender Installer-Preflight, Erstinstallations-/Code-Upgrade-/Rollback-Verträge und fünf eigene systemd-Units unter `packages/ultimate-slicer-server/` |
| Docker | Dockerfile, Kontextgenerator, Compose-Dateien, API-/Worker-Supervisor, Netzwerkisolationsprüfung, Persistenz- und Wartungsverträge unter `Slicer-Server/` |
| Engine-Verwaltung | Katalog-, Staging-, Aktivierungs-, Herkunfts- und Ressourcenprüfungen; kein ungeprüfter automatischer Engine-Download |
| Profile | Maschinenbeispiele, mitgelieferte Standardwerte, offline prüfbare Upstream-Quellen und Vererbungsnachweise |
| Prüfungen | Komponententests plus manuell nutzbare Linux-/TLS-Prüfwerkzeuge unter `tests/`; eigene GitHub-Quell-CI |
| Dokumentation | Installation, Docker, HA-Verbindung, Speicher, Berechtigungen, Wartung, Migration, Sicherung, Wiederherstellung, Fehlerhilfe, Lizenzgrenzen und Wiki-Quellen |
| Nachweis | `slicer-source-manifest.json` bindet jede aktuelle Lieferdatei an Größe und SHA-256 |

Die Verzeichnisstruktur bleibt absichtlich erhalten: Die Paketbauer finden so ihre tatsächlichen Abhängigkeiten. Das ist kein Archiv mit fehlenden relativen Importen und auch keine zweite unabhängig gepflegte Kopie des Workers. [Quellautorität und Aktualisierung](Slicer-Server/REPOSITORY_CONTENTS.md).

## Warum das Repo nicht 10 GB groß sein muss

Ein am 15.10.2026 rein lesend inventarisierter bestehender Slicer belegt rund **10,45 GB**. Davon liegen etwa **7,26 GB in Daten**, **1,80 GB in Laufverzeichnissen**, **0,60 GB in Validierungsergebnissen** und **0,78 GB im lokalen Engine-Verzeichnis**. Modelle, Aufträge, Caches, Ergebnisse, Zugangsdaten und lokale Backups sind keine fehlenden Programmquellen.

Dieses Repo liefert den vollständigen überprüften **Komponenten-Quellumfang**. Engine-Artefakte brauchen zusätzlich eine bestätigte Herkunft, passende Bibliotheken, Ressourcen, Profile und ihre eigenen Lizenzbedingungen. Ein Git-Klon allein ist deshalb noch keine vollständige betriebsbereite Engine-Installation. Details und beobachtete Hashes: [Bestands- und Engine-Abgrenzung](Slicer-Server/LIVE_ENGINE_INVENTORY.md).

## Ohne Installation prüfen und bauen

Alle folgenden Befehle laufen ab der Wurzel dieses Repos. Ausgaben liegen in neuen absoluten Pfaden **außerhalb des Klons**. Es werden keine Dienste gestartet und keine Slices erzeugt.

```bash
python3 Slicer-Server/build_repository.py --verify .
python3 Slicer-Server/verify_profile_sources.py --source-root .
python3 -m venv /tmp/ultimate-slicer-check-venv
/tmp/ultimate-slicer-check-venv/bin/python -m pip install --only-binary=:all: --no-deps --require-hashes -r requirements-test.txt
/tmp/ultimate-slicer-check-venv/bin/python -m pytest -q tests

SLICER_BUILD_ROOT="$(mktemp -d /tmp/ultimate-slicer-build-XXXXXX)"
python3 packages/ultimate-slicer-server/build_native_package.py \
  --source-root "$PWD" --output "$SLICER_BUILD_ROOT/native.tar.gz"
python3 Slicer-Server/prepare_context.py \
  --source-root "$PWD" --output "$SLICER_BUILD_ROOT/context"
python3 Slicer-Server/prepare_test_server_package.py \
  --source-root "$PWD" --output "$SLICER_BUILD_ROOT/testserver"
```

Ein Build prüft Quellen, nicht reale Maschinen. Der native Installer bleibt mit `native_deploy_ready=false` gegen eine neue Betriebsinstallation gesperrt. Ein Docker-Kontext enthält keine Engine und ist kein veröffentlichtes fertiges Container-Image.

## Die Betriebswege

| Ziel | Richtige Anleitung | Nicht damit verwechseln |
| --- | --- | --- |
| Quellen und Paket offline prüfen | Obige Befehle und [Build-Wiki](Slicer-Server/wiki/Build-und-Tests.md) | Echter Linux-/Engine-Betrieb |
| Docker auf neuer Testumgebung | [Docker-Schnellstart](Slicer-Server/DOCKER_QUICKSTART.md), danach [Linux-Runbook](Slicer-Server/LINUX_TEST_SERVER_RUNBOOK.md) | Migration des bestehenden nativen Slicers |
| Nativen Linux-Dienst vorbereiten | [Paket-Handbuch](packages/ultimate-slicer-server/README.md) | HACS-Installation |
| Home Assistant anbinden | [HA-Wiki](Slicer-Server/wiki/Home-Assistant.md), [Einrichtungsplan](Slicer-Server/HA_INSTALLATION_PLAN.md) | Direkte Secret-Verteilung an den Browser |
| Bestehenden Betrieb sichern | [Betrieb](Slicer-Server/OPERATIONS.md), [Persistenz](Slicer-Server/DATA_PERSISTENCE.md), [Migration](Slicer-Server/MIGRATION.md) | Private Daten ins Git-Repo kopieren |

## Status und Grenzen

- Quell-/Build-/Testumfang: in diesem Repository versioniert und per Manifest prüfbar.
- Dockerfile, Compose und reales Source-Preflight-Image: vorhanden und an feste Referenzen gebunden. Dies ist noch kein Engine-Laufzeitimage. [Belegter Stand und Releasegrenzen](Slicer-Server/RELEASE_STATUS.md).
- Engines: Katalogeinträge noch nicht produktiv freigegeben; `engine_catalog.json` enthält eine leere Release-Liste und drei ausdrücklich ausstehende Enginefamilien. Die vorhandene Bambu-/Prusa-/Cura-Installation ist nicht automatisch ein reproduzierbar genehmigtes Engine-Paket.
- GitHub-Wiki: vollständige Markdown-Seiten im Repo. Die separate Wiki-Funktion war bei der Lieferung deaktiviert; die Dateien sind nicht gleichbedeutend mit einem veröffentlichten Wiki-Tab.
- Historische Testpakete und `continuity/`: bleiben zur Nachvollziehbarkeit erhalten. Maßgeblich für neue Builds sind die aktuellen Quellen und das aktuelle Manifest, nicht das alte W53-Archiv.
- Keine Produktivfreigabe, keine automatische HA-Migration, keine ARM-Zusage und keine Druckeraktion durch diese Quelllieferung.

## Lizenz und Nutzung

Es gibt **keine einheitliche neue Lizenz für alle Dateien**. Frühere Studio-Quellen behalten ihre bisherigen Bedingungen; neues ursprüngliches Slicer-Material unterliegt dem abgegrenzten [Slicer-Lizenztext](Slicer-Server/LICENSE). Importierte Profile und Drittanbieterkomponenten behalten ihre eigenen Rechte. [SOURCE_NOTICES.md](SOURCE_NOTICES.md) und [THIRD_PARTY_NOTICES.md](Slicer-Server/THIRD_PARTY_NOTICES.md) sind Bestandteil der Lieferung. Repository-Sichtbarkeit und Lizenzfreigabe wurden durch diese Aktualisierung nicht erweitert.


## Getrennte Abschlüsse ohne verlorene Anforderungen

Die [gemeinsame Statusseite](Slicer-Server/RELEASE_STATUS.md) und die
[Abnahmematrix](Slicer-Server/wiki/Release-Abnahme.md) unterscheiden R, V und L:
Zuerst Funktionen, unterstützte Hostintegration, tatsächliche Engine-/Runtime- und
HACS-Pakete, Rechte, Dokumentation und öffentliche Auslieferung vollständig
abschließen (R). Danach den unveränderten veröffentlichten Release auf dem
separaten sauberen Linux-Testserver installieren und verifizieren (V).
Produktiver Pilot und Migration bleiben gesondert (L).

Vorhandene Quell-/Image-/Profilnachweise werden weiterverwendet. Die vollständige
Betriebskette wird nicht aus einem erfolgreichen Quellenbuild abgeleitet.
Fehlende Enginepakete und ein unvollständiger Hostkanal sind Releaseblocker,
keine Aufgaben, die erst beim letzten Systemtest implementiert werden dürfen.
Eine fehlende Messung bleibt `not_run` oder `blocked`.
