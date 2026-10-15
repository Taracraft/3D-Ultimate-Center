#!/bin/sh
BASE=${STUDIO_WORKER_BASE:-/var/lib/homeassistant/3d-printer-slicing-server}
SOURCE_ROOT=${STUDIO_WORKER_SOURCE_ROOT:-$BASE}
RELEASE_FILE="$SOURCE_ROOT/release.json"
if [ -f "$RELEASE_FILE" ]; then
  VERSION=$(jq -er '.version | strings | select(test("^[0-9]+[.][0-9]+[.][0-9]+([-+][A-Za-z0-9.-]+)?$"))' "$RELEASE_FILE") || exit 1
  API_VERSION=$(jq -er '.api_protocol | numbers | select(. >= 2 and floor == .)' "$RELEASE_FILE") || exit 1
else
  # Legacy host installations do not yet have the standalone release file.
  # Reuse their last own status metadata instead of a source-embedded number.
  VERSION=$(jq -er '.version | strings | select(length > 0)' "$BASE/api/info.json" 2>/dev/null) || VERSION=${STUDIO_WORKER_RELEASE_VERSION:-unknown}
  API_VERSION=$(jq -er '.api_version | numbers | select(. >= 2 and floor == .)' "$BASE/api/info.json" 2>/dev/null) || API_VERSION=${STUDIO_WORKER_API_PROTOCOL:-2}
fi
API="$BASE/api"
DATA="$BASE/data"
JOBS="$DATA/jobs"
UPLOADS="$DATA/uploads"
OUTPUT="$DATA/output"
PROFILES=${STUDIO_WORKER_PROFILE_ROOT:-$BASE/profiles/printers}
LAST_JOB="$BASE/last_job.json"
mkdir -p "$API" "$JOBS" "$UPLOADS" "$OUTPUT" "$PROFILES"

BAMBU_ROOT=${STUDIO_BAMBU_ROOT:-$BASE/engines/bambu-studio/squashfs-root}
BAMBU="$BAMBU_ROOT/bin/bambu-studio"
PRUSA=$(command -v prusa-slicer || true)
CURA=$(command -v CuraEngine || true)

ACTIVE=$(find "$JOBS" -maxdepth 1 -type f -name "*.slicing.json" 2>/dev/null | wc -l)
QUEUED=$(find "$JOBS" -maxdepth 1 -type f -name "*.queued.json" 2>/dev/null | wc -l)
COMPLETED=$(find "$JOBS" -maxdepth 1 -type f -name "*.completed.json" 2>/dev/null | wc -l)
FAILED=$(find "$JOBS" -maxdepth 1 -type f -name "*.failed.json" 2>/dev/null | wc -l)
UPLOAD_COUNT=$(find "$UPLOADS" -maxdepth 1 -type f 2>/dev/null | wc -l)
OUTPUT_COUNT=$(find "$OUTPUT" -type f \( -name "*.gcode" -o -name "*.3mf" \) 2>/dev/null | wc -l)
PROGRESS_COUNT=$(find "$OUTPUT" -maxdepth 1 -type f -name "*.progress.json" 2>/dev/null | wc -l)
PROFILE_COUNT=$(find "$PROFILES" -maxdepth 1 -type f -name "*.json" 2>/dev/null | wc -l)
DISK_BYTES=$(du -sb "$BASE" 2>/dev/null | awk '{print $1}')
[ -n "$DISK_BYTES" ] || DISK_BYTES=0

LAST_JOB_ID=null
LAST_STATUS=none
LAST_ENGINE=null
LAST_OUTPUT=null

if [ -s "$LAST_JOB" ] && jq empty "$LAST_JOB" >/dev/null 2>&1; then
  LAST_JOB_ID=$(jq -c '.job_id // null' "$LAST_JOB")
  LAST_STATUS=$(jq -r '.status // "none"' "$LAST_JOB")
  LAST_ENGINE=$(jq -c '.engine // null' "$LAST_JOB")
  LAST_OUTPUT=$(jq -c '.output_directory // null' "$LAST_JOB")
fi

LATEST_LOG=$(find "$OUTPUT" -maxdepth 1 -type f -name "*.log" -printf "%T@ %p\n" 2>/dev/null | sort -nr | head -n 1 | cut -d" " -f2-)
LATEST_RESULT=$(find "$OUTPUT" -maxdepth 1 -type f -name "*.result.json" -printf "%T@ %p\n" 2>/dev/null | sort -nr | head -n 1 | cut -d" " -f2-)
LAST_LOG_LINE="none"
LAST_ERROR="none"
LAST_LOG_FILE=null
if [ -n "$LATEST_LOG" ] && [ -f "$LATEST_LOG" ]; then
  LAST_LOG_FILE=$(printf '%s' "$LATEST_LOG" | jq -R .)
  LAST_LOG_LINE=$(tail -n 1 "$LATEST_LOG" 2>/dev/null | tr '\r\n' ' ' | cut -c1-500)
fi
if [ "$LAST_STATUS" = "failed" ]; then
  if [ -n "$LATEST_LOG" ] && [ -f "$LATEST_LOG" ]; then
    ERROR_LINE=$(grep -Ei 'error|failed|exception|traceback|fatal' "$LATEST_LOG" 2>/dev/null | tail -n 1 | tr '\r\n' ' ' | cut -c1-500)
    [ -z "$ERROR_LINE" ] || LAST_ERROR="$ERROR_LINE"
  fi
  if [ -n "$LATEST_RESULT" ]; then
    RESULT_ERROR=$(jq -r '.error // empty' "$LATEST_RESULT" 2>/dev/null)
    [ -z "$RESULT_ERROR" ] || LAST_ERROR="$RESULT_ERROR"
  fi
fi

RECENT_JOBS=$(find "$OUTPUT" -maxdepth 1 -type f -name "*.result.json" -printf "%T@ %p\n" 2>/dev/null | sort -nr | head -n 10 | cut -d" " -f2- | while read -r FILE; do jq -c '{job_id:(.job_id // "unknown"),status:(.status // "unknown"),engine:(.engine // null),output_directory:(.output_directory // null),exit_code:(.exit_code // null)}' "$FILE" 2>/dev/null; done | jq -s .)
[ -n "$RECENT_JOBS" ] || RECENT_JOBS='[]'
WORKER_JOURNAL=$(journalctl -u 3d-printer-slicing-server.service -n 1 --no-pager -o cat 2>/dev/null | tr "\r\n" " " | cut -c1-500)
REFRESH_JOURNAL=$(journalctl -u 3d-printer-slicing-refresh.service -n 1 --no-pager -o cat 2>/dev/null | tr "\r\n" " " | cut -c1-500)
[ -n "$WORKER_JOURNAL" ] || WORKER_JOURNAL=none
[ -n "$REFRESH_JOURNAL" ] || REFRESH_JOURNAL=none

if [ "${STUDIO_WORKER_ISOLATION:-}" = "container" ]; then
  ENGINES=$(python3 "$SOURCE_ROOT/../container_engines.py" list) || exit 1
  COUNT=$(printf '%s' "$ENGINES" | jq -er 'length') || exit 1
else
COUNT=0
ITEMS=""
if [ -x "$BAMBU" ]; then
  ITEMS="{\"id\":\"bambu_studio\",\"name\":\"Bambu Studio\",\"type\":\"bambu_studio\",\"path\":\"$BAMBU\",\"version\":\"02.07.01.62\",\"available\":true}"
  COUNT=$((COUNT+1))
fi
if [ -n "$PRUSA" ]; then
  [ -n "$ITEMS" ] && ITEMS="$ITEMS,"
  ITEMS="$ITEMS{\"id\":\"prusaslicer\",\"name\":\"PrusaSlicer\",\"type\":\"prusaslicer\",\"path\":\"$PRUSA\",\"version\":\"2.9.2+dfsg-1\",\"available\":true}"
  COUNT=$((COUNT+1))
fi
if [ -n "$CURA" ]; then
  [ -n "$ITEMS" ] && ITEMS="$ITEMS,"
  ITEMS="$ITEMS{\"id\":\"curaengine\",\"name\":\"CuraEngine\",\"type\":\"curaengine\",\"path\":\"$CURA\",\"version\":\"unknown\",\"available\":true}"
  COUNT=$((COUNT+1))
fi

ENGINES="[$ITEMS]"
fi
[ "$COUNT" -gt 0 ] && STATUS=ready || STATUS=degraded
NOW=$(date -Iseconds)

jq -n --arg application "3D-Printer Slicing Server" --arg version "$VERSION" --argjson api_version "$API_VERSION" --arg status "$STATUS" '{application:$application,version:$version,api_version:$api_version,status:$status}' > "$API/health.json.tmp"

jq -n --arg application "3D-Printer Slicing Server" --arg version "$VERSION" --argjson api_version "$API_VERSION" --arg status "$STATUS" --argjson engine_count "$COUNT" --argjson active_jobs "$ACTIVE" --argjson queued_jobs "$QUEUED" --argjson last_job_id "$LAST_JOB_ID" --arg last_job_status "$LAST_STATUS" --argjson last_engine "$LAST_ENGINE" '{application:$application,version:$version,api_version:$api_version,status:$status,engine_count:$engine_count,active_jobs:$active_jobs,queued_jobs:$queued_jobs,last_job_id:$last_job_id,last_job_status:$last_job_status,last_engine:$last_engine}' > "$API/info.json.tmp"

jq -n --arg status "$STATUS" --argjson active_jobs "$ACTIVE" --argjson queued_jobs "$QUEUED" --argjson last_job_id "$LAST_JOB_ID" --arg last_job_status "$LAST_STATUS" --argjson last_engine "$LAST_ENGINE" --argjson last_output "$LAST_OUTPUT" --argjson engines "$ENGINES" '{status:$status,active_jobs:$active_jobs,queued_jobs:$queued_jobs,last_job_id:$last_job_id,last_job_status:$last_job_status,last_engine:$last_engine,last_output:$last_output,engines:$engines}' > "$API/status.json.tmp"

jq -n --arg generated_at "$NOW" --arg status "$STATUS" --arg last_log_line "$LAST_LOG_LINE" --arg last_error "$LAST_ERROR" --argjson last_log_file "$LAST_LOG_FILE" --argjson completed_jobs "$COMPLETED" --argjson failed_jobs "$FAILED" --argjson upload_count "$UPLOAD_COUNT" --argjson output_count "$OUTPUT_COUNT" --argjson progress_file_count "$PROGRESS_COUNT" --argjson printer_profile_count "$PROFILE_COUNT" --argjson disk_bytes "$DISK_BYTES" --argjson recent_jobs "$RECENT_JOBS" '{generated_at:$generated_at,status:$status,completed_jobs:$completed_jobs,failed_jobs:$failed_jobs,upload_count:$upload_count,output_count:$output_count,progress_file_count:$progress_file_count,printer_profile_count:$printer_profile_count,disk_bytes:$disk_bytes,last_log_file:$last_log_file,last_log_line:$last_log_line,last_error:$last_error,recent_jobs:$recent_jobs}' > "$API/diagnostics.json.tmp"

printf '{"engines":%s}\n' "$ENGINES" > "$API/engines.json.tmp"
jq -n --argjson api_version "$API_VERSION" '{application:"3D-Printer Slicing Server",api_version:$api_version,mode:"universal_multi_engine",job_schema_version:2,input_formats:["stl","3mf","obj","amf"],output_formats:["gcode","3mf"],engine_selection:["auto","bambu_studio","prusaslicer","curaengine"],printer_profile_required:true,supports_custom_printer_profiles:true,live_progress:true,progress_source:"bambu_cli_pipe",progress_history:true,progress_eta:true,job_detail:true,engine_result:true,runtime_summary:true,live_warnings:true}' > "$API/capabilities.json.tmp"

for NAME in health info status engines diagnostics capabilities; do
  mv "$API/$NAME.json.tmp" "$API/$NAME.json"
done

echo "Terminal bleibt offen."
