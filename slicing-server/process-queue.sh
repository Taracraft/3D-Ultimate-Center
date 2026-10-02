#!/bin/sh
BASE=/var/lib/homeassistant/3d-printer-slicing-server/data
JOBS="$BASE/jobs"
UPLOADS="$BASE/uploads"
OUTPUT="$BASE/output"
mkdir -p "$JOBS" "$UPLOADS" "$OUTPUT"
for QUEUED in "$JOBS"/*.queued; do
  [ -f "$QUEUED" ] || break
  JOB_ID=$(basename "$QUEUED" .queued)
  MODEL=$(head -n 1 "$QUEUED" | tr -d "\r\n")
  case "$MODEL" in
    ""|/*|*..*) mv "$QUEUED" "$JOBS/$JOB_ID.failed"; break ;;
  esac
  INPUT="$UPLOADS/$MODEL"
  SLICING="$JOBS/$JOB_ID.slicing"
  GCODE="$OUTPUT/$JOB_ID.gcode"
  LOG="$OUTPUT/$JOB_ID.log"