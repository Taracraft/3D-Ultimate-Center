#!/bin/sh
BASE=/var/lib/homeassistant/3d-printer-slicing-server
DATA="$BASE/data"
JOBS="$DATA/jobs"
UPLOADS="$DATA/uploads"
OUTPUT="$DATA/output"
PROFILES="$BASE/profiles/printers"
RUN="$BASE/run"
mkdir -p "$JOBS" "$UPLOADS" "$OUTPUT" "$RUN"

if mkdir "$RUN/dispatcher.lock" 2>/dev/null; then
  QUEUED=$(find "$JOBS" -maxdepth 1 -type f -name "*.queued.json" | sort | head -n 1)

  if [ -z "$QUEUED" ]; then
    echo "No queued jobs."
  elif ! jq empty "$QUEUED" >/dev/null 2>&1; then
    JOB_ID=$(basename "$QUEUED" .queued.json)
    mv "$QUEUED" "$JOBS/$JOB_ID.failed.json"
    printf '%s\n' '{"status":"failed","error":"invalid_job_json"}' > "$OUTPUT/$JOB_ID.result.json"
    cp "$OUTPUT/$JOB_ID.result.json" "$BASE/last_job.json"
  else
    JOB_ID=$(basename "$QUEUED" .queued.json)
    PRINTER=$(jq -r '.printer_profile // empty' "$QUEUED")
    ENGINE=$(jq -r '.engine // "auto"' "$QUEUED")
    INPUT_FILE=$(jq -r '.input_file // empty' "$QUEUED")
    OUTPUT_FORMAT=$(jq -r '.output_format // "gcode"' "$QUEUED")
    PROCESS_TOKEN=$(jq -r '.process_profile // "default"' "$QUEUED")
    PROFILE_FILE="$PROFILES/$PRINTER.json"
    ERROR=""

    case "$INPUT_FILE" in
      ""|/*|*..*) ERROR="invalid_input_file" ;;
    esac

    if [ -z "$ERROR" ] && [ ! -f "$UPLOADS/$INPUT_FILE" ]; then
      ERROR="input_file_not_found"
    fi
    if [ -z "$ERROR" ] && [ ! -f "$PROFILE_FILE" ]; then
      ERROR="printer_profile_not_found"
    fi

    if [ -z "$ERROR" ] && [ "$ENGINE" = "auto" ]; then
      ENGINE=$(jq -r '.preferred_engine // empty' "$PROFILE_FILE")
    fi

    if [ -z "$ERROR" ]; then
      COMPATIBLE=$(jq --arg engine "$ENGINE" -r '(.compatible_engines // []) | index($engine) != null' "$PROFILE_FILE")
      if [ "$COMPATIBLE" != "true" ]; then
        ERROR="engine_not_compatible"
      fi
    fi

    SLICING="$JOBS/$JOB_ID.slicing.json"
    JOB_OUTPUT="$OUTPUT/$JOB_ID"
    LOG="$OUTPUT/$JOB_ID.log"
    mkdir -p "$JOB_OUTPUT"

    if [ -n "$ERROR" ]; then
      mv "$QUEUED" "$JOBS/$JOB_ID.failed.json"
      jq -n --arg id "$JOB_ID" --arg error "$ERROR" '{job_id:$id,status:"failed",error:$error}' > "$OUTPUT/$JOB_ID.result.json"
      cp "$OUTPUT/$JOB_ID.result.json" "$BASE/last_job.json"
    else
      mv "$QUEUED" "$SLICING"
      CODE=1

      case "$ENGINE" in
        bambu_studio)
          ROOT="$BASE/engines/bambu-studio/squashfs-root"
          BINARY="$ROOT/bin/bambu-studio"
          MACHINE=$(jq -r '.engine_profiles.bambu_studio.machine // empty' "$PROFILE_FILE")
          PROCESS=$(jq -r '.engine_profiles.bambu_studio.process // empty' "$PROFILE_FILE")
          FILAMENT=$(jq -r '.engine_profiles.bambu_studio.filament // empty' "$PROFILE_FILE")
          PROFILE_ROOT="$ROOT/resources/profiles"
          PROCESS_SOURCE="$PROFILE_ROOT/$PROCESS"
          PROCESS_RUNTIME="$RUN/$JOB_ID-process.json"
          MACHINE_RUNTIME="$RUN/$JOB_ID-machine.json"
          python3 "$BASE/materialize-bambu-machine.py" "$PROFILE_ROOT" "$MACHINE" "$MACHINE_RUNTIME"

          ADHESION=none
          BRIM_WIDTH=0
          RAFT_LAYERS=0
          SUPPORT_MODE=off
          SUPPORT_PLATE_ONLY=1
          SUPPORT_ANGLE=30

          case "$PROCESS_TOKEN" in
            studio:*)
              OLD_IFS=$IFS
              IFS=:
              set -- $PROCESS_TOKEN
              IFS=$OLD_IFS
              ADHESION=${2:-none}
              BRIM_WIDTH=${3:-0}
              RAFT_LAYERS=${4:-0}
              SUPPORT_MODE=${5:-off}
              SUPPORT_PLATE_ONLY=${6:-1}
              SUPPORT_ANGLE=${7:-30}
              ;;
          esac

          case "$ADHESION" in
            brim)
              BRIM_TYPE=outer_only
              RAFT_VALUE=0
              ;;
            raft)
              BRIM_TYPE=no_brim
              BRIM_WIDTH=0
              RAFT_VALUE=$RAFT_LAYERS
              ;;
            *)
              BRIM_TYPE=no_brim
              BRIM_WIDTH=0
              RAFT_VALUE=0
              ;;
          esac

          case "$SUPPORT_MODE" in
            tree)
              ENABLE_SUPPORT=1
              SUPPORT_TYPE='tree(auto)'
              ;;
            normal)
              ENABLE_SUPPORT=1
              SUPPORT_TYPE='normal(auto)'
              ;;
            *)
              ENABLE_SUPPORT=0
              SUPPORT_TYPE='normal(auto)'
              ;;
          esac

          if [ -f "$PROCESS_SOURCE" ]; then
            jq \
              --arg raft "$RAFT_VALUE" \
              --arg brim_type "$BRIM_TYPE" \
              --arg brim_width "$BRIM_WIDTH" \
              --arg enable_support "$ENABLE_SUPPORT" \
              --arg support_type "$SUPPORT_TYPE" \
              --arg plate_only "$SUPPORT_PLATE_ONLY" \
              --arg angle "$SUPPORT_ANGLE" \
              '. + {
                raft_layers:$raft,
                brim_type:$brim_type,
                brim_width:$brim_width,
                enable_support:$enable_support,
                support_type:$support_type,
                support_on_build_plate_only:$plate_only,
                support_threshold_angle:$angle,
                studio_adhesion_mode:(if $raft != "0" then "raft" elif $brim_type != "no_brim" then "brim" else "none" end),
                studio_support_mode:(if $enable_support == "0" then "off" elif $support_type == "tree(auto)" then "tree" else "normal" end)
              }' "$PROCESS_SOURCE" > "$PROCESS_RUNTIME"
          fi

          if [ -x "$BINARY" ] && [ -s "$MACHINE_RUNTIME" ] && [ -s "$PROCESS_RUNTIME" ] && [ -n "$FILAMENT" ]; then
            LD_LIBRARY_PATH="$ROOT/bin" "$BINARY" \
              --load-settings "$MACHINE_RUNTIME;$PROCESS_RUNTIME" \
              --load-filaments "$ROOT/resources/profiles/$FILAMENT" \
              --load-defaultfila \
              --ensure-on-bed \
              --arrange 1 \
              --slice 0 \
              --outputdir "$JOB_OUTPUT" \
              "$UPLOADS/$INPUT_FILE" > "$LOG" 2>&1
            CODE=$?
          else
            printf '%s\n' 'Bambu Studio profile or binary missing.' > "$LOG"
          fi
          ;;

        prusaslicer)
          BINARY=/usr/bin/prusa-slicer
          CONFIG=$(jq -r '.engine_profiles.prusaslicer.config // empty' "$PROFILE_FILE")
          GCODE="$JOB_OUTPUT/$JOB_ID.gcode"
          if [ -x "$BINARY" ]; then
            if [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
              "$BINARY" --load "$CONFIG" --export-gcode --output "$GCODE" "$UPLOADS/$INPUT_FILE" > "$LOG" 2>&1
            else
              "$BINARY" --export-gcode --output "$GCODE" "$UPLOADS/$INPUT_FILE" > "$LOG" 2>&1
            fi
            CODE=$?
          else
            printf '%s\n' 'PrusaSlicer binary missing.' > "$LOG"
          fi
          ;;

        curaengine)
          BINARY=/usr/bin/CuraEngine
          DEFINITION=$(jq -r '.engine_profiles.curaengine.definition // empty' "$PROFILE_FILE")
          GCODE="$JOB_OUTPUT/$JOB_ID.gcode"
          if [ -x "$BINARY" ] && [ -n "$DEFINITION" ] && [ -f "$DEFINITION" ]; then
            "$BINARY" slice -j "$DEFINITION" -l "$UPLOADS/$INPUT_FILE" -o "$GCODE" > "$LOG" 2>&1
            CODE=$?
          else
            printf '%s\n' 'CuraEngine definition or binary missing.' > "$LOG"
          fi
          ;;

        *)
          printf '%s\n' "Unknown engine: $ENGINE" > "$LOG"
          CODE=1
          ;;
      esac

      FILE_COUNT=$(find "$JOB_OUTPUT" -maxdepth 2 -type f | wc -l)
      if [ "$CODE" -eq 0 ] && [ "$FILE_COUNT" -gt 0 ]; then
        mv "$SLICING" "$JOBS/$JOB_ID.completed.json"
        jq -n --arg id "$JOB_ID" --arg engine "$ENGINE" --arg output "$JOB_OUTPUT" --arg format "$OUTPUT_FORMAT" '{job_id:$id,status:"completed",engine:$engine,output_directory:$output,output_format:$format}' > "$OUTPUT/$JOB_ID.result.json"
        cp "$OUTPUT/$JOB_ID.result.json" "$BASE/last_job.json"
      else
        mv "$SLICING" "$JOBS/$JOB_ID.failed.json"
        jq -n --arg id "$JOB_ID" --arg engine "$ENGINE" --argjson code "$CODE" '{job_id:$id,status:"failed",engine:$engine,exit_code:$code}' > "$OUTPUT/$JOB_ID.result.json"
        cp "$OUTPUT/$JOB_ID.result.json" "$BASE/last_job.json"
      fi
    fi
  fi

  /bin/sh "$BASE/refresh-state.sh"
  rmdir "$RUN/dispatcher.lock" 2>/dev/null || true
else
  echo "Dispatcher is already running."
fi

echo "Terminal bleibt offen."
