#!/bin/sh
apt-get update
apt-get install -y --no-install-recommends jq
command -v jq || true
echo "Terminal bleibt offen."