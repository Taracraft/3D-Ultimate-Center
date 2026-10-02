#!/bin/bash
set -euo pipefail
container="app_0f1cc410_puppet"
if ! running="$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null)" || [[ "$running" != "true" ]]; then
  exit 0
fi
gateway="$(docker network inspect hassio --format '{{(index .IPAM.Config 0).Gateway}}')"
[[ "$gateway" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
docker exec "$container" node --input-type=module -e '
import fs from "node:fs";
const address = process.argv[1];
const host = "homeassist.bad-timing.eu";
const before = fs.readFileSync("/etc/hosts", "utf8");
const lines = before.split("\n");
if (lines.some(line => {
  const fields = line.split("#")[0].trim().split(/\s+/);
  return fields[0] === address && fields.includes(host);
})) process.exit(0);
const after = lines.map(line => {
  const [entry, ...comments] = line.split("#");
  const fields = entry.trim().split(/\s+/);
  if (!fields.includes(host)) return line;
  const remaining = fields.filter(field => field !== host);
  return remaining.length >= 2 ? remaining.join("\t") + (comments.length ? " #" + comments.join("#") : "") : "";
}).filter(Boolean).join("\n") + "\n" + address + "\t" + host + "\n";
fs.writeFileSync("/etc/hosts", after);
console.log("Puppet Split-DNS restored: " + host + " -> " + address);
' "$gateway"
