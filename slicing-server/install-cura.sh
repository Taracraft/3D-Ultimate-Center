#!/bin/sh
apt-get update
apt-get install -y --no-install-recommends cura-engine
command -v CuraEngine || true
CuraEngine version || true
echo "Terminal bleibt offen."