# Puppet auf Homeassist

Host-Port 5000, Container-Port 10000. Vorhandenes Add-on 0f1cc410_puppet benutzen.
Die gespeicherte home_assistant_url muss ohne abschließenden Slash lauten:
https://homeassist.bad-timing.eu:8123
Der vorhandene Zugangstoken bleibt unverändert und gehört niemals ins Repository.

Die WebSocket-Bibliothek hängt /api/websocket unmittelbar an die URL an.
Ein abschließender Slash erzeugt //api/websocket und verhindert die Verbindung.

Puppet benötigt Split-DNS. v6-puppet-hosts.sh ermittelt das IPv4-Gateway des
Docker-Netzes hassio und setzt ausschließlich homeassist.bad-timing.eu im
laufenden Puppet-Container. Der Timer wiederholt die idempotente Prüfung alle
15 Sekunden; die Zuordnung übersteht damit auch Container-Neuanlage und
Host-Neustart. Ein gestopptes Add-on wird nicht gestartet.

Installation nach Backup und Prüfung:
- Script nach /usr/local/sbin/v6-puppet-hosts.sh, Modus 0755.
- Units nach /etc/systemd/system/, Modus 0644.
- bash -n und systemd-analyze verify ausführen.
- systemctl daemon-reload
- systemctl enable --now v6-puppet-hosts.timer

Rollback: Timer deaktivieren; zuvor vorhandene Dateien aus dem Backup
wiederherstellen oder neu angelegte Dateien entfernen; daemon-reload.

Abnahme 2026-10-02: Add-on erneut gestartet; Hosts-Zuordnung automatisch
wiederhergestellt. Port 5000 zeigt Screenshot Preview. V6-Dashboard:
HTTP 200, image/png, gültige PNG-Signatur; 101646 Bytes,
SHA256 b44fdd9384df0991efa967ce6fa441734c6e29b0b60a907a86c1daec84c42956.
Der Screenshot zeigt das verbundene Studio. Interaktive Maus-/Touch-Prüfung
und realer Slice bleiben gesonderte, offene Abnahmen.
