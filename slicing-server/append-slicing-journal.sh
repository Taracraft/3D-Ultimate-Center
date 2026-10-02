#!/bin/sh
BASE=/var/lib/homeassistant/3d-printer-slicing-server
FILE="$BASE/api/diagnostics.json"
TMP="$FILE.tmp-journal"
WORKER=$(journalctl -u 3d-printer-slicing-server.service -n 1 --no-pager -o cat 2>/dev/null | tr '\r\n' ' ' | cut -c1-500)
REFRESH=$(journalctl -u 3d-printer-slicing-refresh.service -n 1 --no-pager -o cat 2>/dev/null | tr '\r\n' ' ' | cut -c1-500)
[ -n "$WORKER" ] || WORKER=none
[ -n "$REFRESH" ] || REFRESH=none
if [ -s "$FILE" ] && jq empty "$FILE" >/dev/null 2>&1; then
  jq --arg worker_journal "$WORKER" --arg refresh_journal "$REFRESH" '. + {worker_journal:$worker_journal,refresh_journal:$refresh_journal}' "$FILE" > "$TMP"
  mv "$TMP" "$FILE"
fi
echo "Terminal bleibt offen."
