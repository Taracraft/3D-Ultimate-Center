# Docker-Installation

Der aktuelle Stand stellt ein Preflight-Image bereit. Es prueft Quellen, startet aber keine API oder Engine. Es ist noch keine installierbare Slicing-Loesung.

Voraussetzungen fuer den Preflight: vollstaendiger Quellbaum, Python ab 3.11, ein neues privates Ausgabeverzeichnis sowie fuer den Image-Test Docker und Compose. Zuerst prepare_context.py aus Slicer-Server ausfuehren. Danach container_check.py im erzeugten Kontext starten. Die Ausgabe muss source_integrity=verified und container_deploy_ready=false enthalten.

Fuer den Docker-Build ist ein geprueftes Python-Linux-Basisimage mit Digest erforderlich. Die Datei compose.preview.yaml fuehrt ausschliesslich die lesende Pruefung ohne Netzwerk, Ports oder Engine aus. Die vollstaendigen Befehle stehen in INSTALLATION.md im Produktbereich.

Die fertige Installation wird einen freigegebenen Image-Digest, getrennte persistente Speicherorte, ein lokal erzeugtes API-Secret und TLS verwenden. Die Engine-, Plattform- und Wiederherstellungsabnahmen muessen davor abgeschlossen sein. Ein allgemeiner ARM- oder NAS-Support wird nicht ohne entsprechende Tests zugesagt.

Bei Home Assistant OS ist eine eigene App-Paketierung oder ein separater Docker-Host erforderlich. HACS installiert nur die Integration.
