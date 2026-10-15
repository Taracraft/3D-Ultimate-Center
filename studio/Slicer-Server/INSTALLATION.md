# Installation und Vorpruefung

## Status

Docker Compose startet inzwischen den geprueften Dienstkandidaten; siehe
[RUNTIME_INSTALLATION.md](RUNTIME_INSTALLATION.md). Diese Seite beschreibt den
weiterhin standardmaessigen Quell-Preflight. Die folgenden Pruefschritte
starten keine API, keine Engine und keine Auftragsverarbeitung. Es gibt noch
keinen veroeffentlichten Image-Namen und keinen freigegebenen Image-Digest.

## Voraussetzungen fuer die Quellpruefung

- Vollstaendiger Studio-Quellbaum mit Slicer-Server und den bestehenden
  kanonischen Worker-/Komponentendateien.
- Python 3.11 oder neuer fuer die Dateipruefung.
- Ein neues Zielverzeichnis ausserhalb des Repositorys; der Elternordner muss
  existieren und darf kein Link auf einen anderen Speicherort sein.
- Keine vorhandene Installation wird fuer diese Pruefung benoetigt.

Vom Studio-Quellwurzelverzeichnis aus:

    python Slicer-Server/prepare_context.py --output /tmp/ultimate-slicer-context
    python /tmp/ultimate-slicer-context/container_check.py check

Auf Windows kann das Ausgabeziel ein neuer Ordner in einem privaten temporaeren
Verzeichnis sein. Die kanonischen Quellpfade bleiben innerhalb des Repositorys;
keine Standortpfade muessen in den Code eingetragen werden.

Erwartet werden source_integrity=verified, container_deploy_ready=false,
engine_included=false, installation_performed=false und worker_started=false.
Ein anderes Ergebnis ist keine bestandene Vorpruefung. Nach der Pruefung kann
ausschliesslich der selbst erzeugte temporaere Kontext wieder entfernt werden.

## Preflight-Image bauen

Docker Engine und Docker Compose muessen auf dem vorgesehenen Testrechner
vorhanden sein. Ein Build kann das gewaehlte Basisimage herunterladen. Dies ist
kein Installationsschritt auf einem produktiven Home-Assistant-Host.

Waehle ein geprueftes offizielles Python-Linux-Basisimage mit SHA-256-Digest.
PYTHON_BASE muss einen vollstaendigen Wert wie
python:<freigegebener-tag>@sha256:<64-hex-zeichen> enthalten. Die Platzhalter
sind keine lauffaehigen Imageangaben; der konkrete Digest wird bei der
Container-Abnahme dokumentiert. Es wird keine erfundene Referenz vorgegeben.

    docker build --build-arg PYTHON_BASE="$PYTHON_BASE" \
      --tag ultimate-slicer-server-check /tmp/ultimate-slicer-context

Danach aus dem Studio-Quellwurzelverzeichnis:

    SLICER_CHECK_IMAGE=ultimate-slicer-server-check \
      docker compose -f Slicer-Server/compose.preview.yaml run --rm preflight

Die Compose-Datei hat weder Ports noch Daten-/Engine-Mounts. Sie verwendet
einen unprivilegierten Benutzer, ein nur lesbares Dateisystem, keine
Netzwerkschnittstelle ausser Loopback und keine zusaetzlichen Capabilities.
pull_policy=never verhindert einen impliziten Download des Preflight-Images.
Die Datei ist als JSON geschrieben; JSON ist ein gueltiges YAML-Format.

Ein erfolgreicher Lauf belegt nur die Integritaet des eingebauten Quellpakets.
Ein SHA-Manifest kann fehlende Softwarelizenzen oder fehlende Betriebssystem-
und Engine-Abhaengigkeiten nicht ersetzen.

## Installation des spaeteren Betriebsimages

Diese Schritte werden erst nach der Container-Abnahme konkret auslieferbar:

1. Passendes Image fuer die nachgewiesene Prozessorarchitektur waehlen.
   Linux/amd64 ist der erste vorgesehene Testumfang; ARM-Unterstuetzung
   wird erst nach einem echten Engine-Test zugesagt.
2. Image-Digest, Signatur/Herkunft, Komponentenliste und Lizenzhinweise pruefen.
3. Persistente Verzeichnisse fuer Konfiguration, Profile, Auftraege und
   Ergebnisse einrichten; Programmcode und Engine schreibgeschuetzt halten.
4. API-Secret lokal erzeugen und als Datei einbinden. TLS-Zertifikat mit einem
   vom Home-Assistant-Host vertrauten Namen bereitstellen.
5. API und netzisolierten Worker ueber die gepruefte Betriebs-Compose-Datei
   starten. Der Docker-Socket wird nicht in den Dienst eingebunden.
6. Health, Authentifizierung und API-Kompatibilitaet pruefen.
7. In Home Assistant unter Einstellungen -> Geraete & Dienste ->
   Ultimate 3D Studio -> Konfigurieren Adresse und Secret setzen.
8. Erstinstallation, Neustart sowie Backup/Restore protokollieren.

Eine Compose-Kandidatendatei ist vorhanden und synthetisch geprueft; die
Betriebsfreigabe und vollstaendige Engine-Abnahme stehen noch aus. Die Preview-Datei
darf nicht durch Hinzufuegen privilegierter Rechte zur Installation umgedeutet
werden. Die konkrete Engine und ihre Bibliotheken sind ebenfalls noch offen.

## Verbindung und Grenzen

Auf einem entfernten Host benoetigt der Dienst HTTPS mit gueltigem,
vertrauenswuerdigem Zertifikat. Ein Verbindungscheck startet keinen Slice.
Slicer-Installation, Slice, Druckerupload und Druckstart sind getrennte Aktionen.

Ein Docker-Container neben Home Assistant ist kein Teil des HA-Core-Containers.
Bei Home Assistant OS muss ein eigener unterstuetzter App-Auslieferungsweg
oder ein separater Linux-Docker-Host vorgesehen werden.

## Bei Fehlern

source_digest_mismatch bedeutet: Eine kanonische Quelle passt nicht zu ihrem
vorhandenen Pruefmanifest. Nicht einfach die Pruefsumme austauschen; zuerst
Ursache und autoritativen Quellstand ermitteln.

output_already_exists bedeutet: Fuer einen erneuten Build einen anderen neuen
privaten Kontext verwenden oder den eigenen vorherigen Kontext bewusst entfernen.
Es werden keine bestehenden Ziele automatisch geleert.

unexpected_context_file bedeutet: Im Kontext liegt eine nicht erlaubte Datei.
Insbesondere Konfigurationen und Secrets gehoeren nicht in das Image.
