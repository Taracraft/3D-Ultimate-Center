# Ultimate 3D Studio – unabhängige Linux-Abnahme

**Privates Testpaket; nicht für Produktion oder GitHub-Veröffentlichung freigegeben.**

Dieses Kit ermöglicht die Prüfung des separat installierbaren nativen Linux-Slicers **ohne MCP auf dem Zielserver**. Der Arbeitsserver wird weder über das private Home-Assistant-MCP noch über den Tara-PC-Connector angesprochen.

## Inhalt

- \`native-source.tar.gz\`: SHA-verifizierter Quellkandidat des Linux-Slicers, ohne Bambu-Engine, Plugin, Hostdaten oder Secrets
- \`packages/ultimate-slicer-server/install_native.py\`: identischer Installer aus dem führenden PC-Quellbaum
- \`units/\`: die fünf eigenen, versionsneutral benannten systemd-Definitionen
- \`check_target_host.sh\`: reguläre SSH-Benutzerprüfung ohne Root, Installation, Netzwerkverbindung oder Druckauftrag
- \`run_isolated_test.sh\`: ausschließlich auf ausdrücklichen Aufruf ein synthetischer Linux-Dateisystem-/Rechte-/Rollback-Test in temporären Verzeichnissen. Dieser Test benötigt Root, fängt systemd und Benutzerverwaltung aber intern ab.
- \`tests/native_linux_install_sandbox.py\`: vollständig einsehbarer Quelltext des isolierten Tests
- \`SHA256SUMS\`: Prüfsummen aller Kitdateien außer dieser Liste selbst

## Auf dem Arbeitsserver: nur prüfen

Übertrage die ZIP-Datei mittels eigener SSH-/SCP-Verbindung vom Entwicklungs-PC auf den unabhängigen Linux-Server. Es ist kein MCP und keine Anbindung an das private HA notwendig.

Beispiel im **eigenen** Linux-SSH-Terminal:

\`\`\`bash
mkdir -p "$HOME/ultimate-studio-test"
python3 -m zipfile -e "$HOME/ultimate-slicer-server-testkit.zip" "$HOME/ultimate-studio-test"
cd "$HOME/ultimate-studio-test"
bash check_target_host.sh
\`\`\`

Die Ausgabe zeigt nur Systemarchitektur, Distribution, verfügbare Programme, Paketprüfsummen und eventuell belegte Installationsziele – **keine Hostnamen, IP-Adressen, Schlüssel, Job- oder Druckerdaten**. Teile diese Ausgabe für den nächsten Projektschritt. Fehlende Werkzeuge werden gemeldet, nicht automatisch installiert.

**Optional erst nach manueller Quellprüfung** auf einer wirklich isolierten Linux-Testumgebung:

\`\`\`bash
sudo bash run_isolated_test.sh
\`\`\`

Dieser zweite Test erzeugt einen temporären Dateibaum, simuliert einen Slicer ohne echtes Druck-/Slicingkommando und löscht den Testbereich nach Ende. Auf dem Arbeitsserver bitte nicht automatisch ausführen, wenn er bereits produktiv verwendet wird.

## Klare Verbote und Abnahmeschranken

- **Nicht** \`--install\`, \`--upgrade\` oder \`--rollback\` gegen ein produktives Ziel ausführen.
- \`native_deploy_ready=false\` bleibt im Quellpaket erhalten. Das ist eine echte Sicherheitsgrenze: Die Paketprüfung darf bestehen, die Produktionsinstallation bleibt gesperrt.
- Kein vorhandener Linux-Service wird gestoppt, ersetzt oder gestartet. Keine \`apt\`-Befehle, Ports, Firewallregeln, Zertifikate oder Geheimnisse werden durch das Preflight verändert.
- Die lizenzierte, SHA-geprüfte Engine wird separat nachgewiesen; Bambu-Engine und proprietärer Netzwerk-Plugin werden nicht mitgeliefert.
- Vor dem Firmen-Rollout müssen echter dedizierter systemd-Dienst, TLS zwischen getrennten Hosts, HACS-Neuinstallation, Versions-/Modulmigration, Backup, Restore und unabhängige CI nachgewiesen sein.

Alle technischen Produkt-, Paket-, Service- und Ordnernamen bleiben versionsneutral. Die Softwareversion gehört nur in standardisierte Metadaten und in die sichtbare Frontendanzeige.
