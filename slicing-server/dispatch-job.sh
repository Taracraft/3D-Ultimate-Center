#!/bin/sh

# V6_VALID_GCODE_ARTIFACT_V1
v6_validate_bambu_gcode() {
  V6_GCODE="$1"
  [ -f "$V6_GCODE" ] || return 1
  V6_BYTES=$(wc -c < "$V6_GCODE" 2>/dev/null | tr -d '[:space:]')
  [ -n "$V6_BYTES" ] && [ "$V6_BYTES" -ge 4096 ] || return 1
  grep -q '^; HEADER_BLOCK_START' "$V6_GCODE" || return 1
  grep -q '^; HEADER_BLOCK_END' "$V6_GCODE" || return 1
  grep -Eq '^; total layer number: [1-9][0-9]*' "$V6_GCODE" || return 1
  grep -q '^; layer num/total_layer_count:' "$V6_GCODE" || return 1
  grep -q '^; EXECUTABLE_BLOCK_END' "$V6_GCODE" || return 1
  validate_bed_type_contract "$V6_GCODE" "$SLICING" "$PROCESS_RUNTIME" >> "$LOG" 2>&1 || return 1
  return 0
}
BASE=/var/lib/homeassistant/3d-printer-slicing-server
. "$BASE/bed-temperature-contract.sh"
DATA="$BASE/data"
JOBS="$DATA/jobs"
UPLOADS="$DATA/uploads"
OUTPUT="$DATA/output"
PROFILES="$BASE/profiles/printers"
RUN="$BASE/run"
mkdir -p "$JOBS" "$UPLOADS" "$OUTPUT" "$RUN"
PROGRESS_READER_PID=""
PROGRESS_PIPE=""
PROGRESS_OPTION=""

start_progress_pipe() {
  PROGRESS_READER_PID=""
  PROGRESS_OPTION=""
  PROGRESS_PIPE="$RUN/$JOB_ID-progress.pipe"
  PROGRESS_FILE="$OUTPUT/$JOB_ID.progress.json"
  PROGRESS_LOG="$OUTPUT/$JOB_ID.progress-reader.log"
  rm -f "$PROGRESS_PIPE"
  if [ ! -x "$BASE/progress-pipe-reader.py" ]; then
    printf '%s\n' 'V6 telemetry reader unavailable; slicing continues without live progress.' >> "$LOG"
    return 0
  fi
  python3 "$BASE/progress-pipe-reader.py" --pipe "$PROGRESS_PIPE" --output "$PROGRESS_FILE" --job-id "$JOB_ID" >> "$PROGRESS_LOG" 2>&1 &
  PROGRESS_READER_PID=$!
  V6_WAIT=0
  while [ "$V6_WAIT" -lt 20 ]; do
    if [ -p "$PROGRESS_PIPE" ] && [ -s "$PROGRESS_FILE" ] && kill -0 "$PROGRESS_READER_PID" 2>/dev/null; then
      PROGRESS_OPTION="--pipe $PROGRESS_PIPE"
      return 0
    fi
    sleep 0.05
    V6_WAIT=$((V6_WAIT + 1))
  done
  printf '%s\n' 'V6 telemetry reader did not become ready; slicing continues without live progress.' >> "$LOG"
  stop_progress_pipe
  return 0
}

stop_progress_pipe() {
  if [ -n "$PROGRESS_READER_PID" ]; then
    kill "$PROGRESS_READER_PID" 2>/dev/null || true
    wait "$PROGRESS_READER_PID" 2>/dev/null || true
  fi
  [ -z "$PROGRESS_PIPE" ] || rm -f "$PROGRESS_PIPE"
  PROGRESS_READER_PID=""
  PROGRESS_PIPE=""
  PROGRESS_OPTION=""
}

trap 'stop_progress_pipe' EXIT INT TERM

if mkdir "$RUN/dispatcher.lock" 2>/dev/null; then
  QUEUED=$(find "$JOBS" -maxdepth 1 -type f -name "*.queued.json" | sort | while IFS= read -r CANDIDATE; do
    if jq -e '(.manual_release != true) or ((.released_at // "") | strings | length > 0)' "$CANDIDATE" >/dev/null 2>&1; then
      printf '%s\n' "$CANDIDATE"
    fi
  done | head -n 1)

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
    NATIVE_MULTIMATERIAL=$(jq -r '.native_multimaterial // false' "$QUEUED")
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
          MACHINE=$(jq -r '.native_machine_profile // empty' "$SLICING")
          PROCESS=$(jq -r '.native_process_profile // empty' "$SLICING")
          if [ "$PRINTER" != "bambu_lab_a1_04" ]; then
            [ -n "$MACHINE" ] || MACHINE=$(jq -r '.engine_profiles.bambu_studio.machine // empty' "$PROFILE_FILE")
            [ -n "$PROCESS" ] || PROCESS=$(jq -r '.engine_profiles.bambu_studio.process // empty' "$PROFILE_FILE")
          fi
          FILAMENT=$(jq -r '.engine_profiles.bambu_studio.filament // empty' "$PROFILE_FILE")
          PROFILE_ROOT="$ROOT/resources/profiles"
          PROCESS_SOURCE="$PROFILE_ROOT/$PROCESS"
          PROCESS_RUNTIME="$RUN/$JOB_ID-process.json"
          MACHINE_RUNTIME="$RUN/$JOB_ID-machine.json"
          XDG_RUNTIME="$RUN/$JOB_ID-xdg"
          rm -rf "$XDG_RUNTIME"
          mkdir -p "$XDG_RUNTIME"
          chmod 700 "$XDG_RUNTIME"
          if [ "$PRINTER" = "bambu_lab_a1_04" ]; then
            case "$MACHINE" in
              'BBL/machine/Bambu Lab A1 0.2 nozzle.json') EXPECTED_PROCESS='BBL/process/0.10mm Standard @BBL A1 0.2 nozzle.json'; EXPECTED_NOZZLE='0.2' ;;
              'BBL/machine/Bambu Lab A1 0.4 nozzle.json') EXPECTED_PROCESS='BBL/process/0.20mm Standard @BBL A1.json'; EXPECTED_NOZZLE='0.4' ;;
              'BBL/machine/Bambu Lab A1 0.6 nozzle.json') EXPECTED_PROCESS='BBL/process/0.30mm Strength @BBL A1 0.6 nozzle.json'; EXPECTED_NOZZLE='0.6' ;;
              'BBL/machine/Bambu Lab A1 0.8 nozzle.json') EXPECTED_PROCESS='BBL/process/0.40mm Standard @BBL A1 0.8 nozzle.json'; EXPECTED_NOZZLE='0.8' ;;
              *) EXPECTED_PROCESS=''; EXPECTED_NOZZLE='' ;;
            esac
            REQUESTED_NOZZLE=$(jq -r '.nozzle_diameter_mm // empty' "$SLICING")
            if [ -z "$EXPECTED_PROCESS" ] || [ "$PROCESS" != "$EXPECTED_PROCESS" ] || [ "$REQUESTED_NOZZLE" != "$EXPECTED_NOZZLE" ]; then
              printf '%s\n' 'Native A1 nozzle profile contract is invalid.' > "$LOG"
              CODE=1
            else
              CODE=0
            fi
          else
            CODE=0
          fi
          if [ "$CODE" -eq 0 ] && [ -f "$PROFILE_ROOT/$MACHINE" ] && [ -f "$PROCESS_SOURCE" ]; then
            python3 "$BASE/materialize-bambu-machine.py" "$PROFILE_ROOT" "$MACHINE" "$MACHINE_RUNTIME" "$SLICING" > "$LOG" 2>&1
            CODE=$?
          elif [ "$CODE" -eq 0 ]; then
            printf '%s\n' 'Native machine or process profile is missing.' > "$LOG"
            CODE=1
          fi

          if [ "$CODE" -eq 0 ] && [ "$PRINTER" = "bambu_lab_a1_04" ]; then
            RUNTIME_NOZZLE=$(jq -r '(.nozzle_diameter | if type == "array" then .[0] else . end) // empty' "$MACHINE_RUNTIME")
            MIN_LAYER=$(jq -r '(.min_layer_height | if type == "array" then .[0] else . end) // empty' "$MACHINE_RUNTIME")
            MAX_LAYER=$(jq -r '(.max_layer_height | if type == "array" then .[0] else . end) // empty' "$MACHINE_RUNTIME")
            MAX_X=$(jq -r '(.machine_max_speed_x | if type == "array" then .[0] else . end) // empty' "$MACHINE_RUNTIME")
            MAX_Y=$(jq -r '(.machine_max_speed_y | if type == "array" then .[0] else . end) // empty' "$MACHINE_RUNTIME")
            WALL_LIMIT=$(awk -v x="$MAX_X" -v y="$MAX_Y" 'BEGIN { if (x+0 <= 0 || y+0 <= 0) exit 1; print (x+0 < y+0 ? x+0 : y+0) }') || CODE=1
            if [ "$CODE" -eq 0 ] && ! awk -v actual="$RUNTIME_NOZZLE" -v wanted="$EXPECTED_NOZZLE" 'BEGIN { exit !((actual-wanted < 0.000001) && (wanted-actual < 0.000001)) }'; then
              printf '%s\n' 'Materialized nozzle diameter does not match the selected nozzle.' >> "$LOG"
              CODE=1
            fi
            LAYER_OVERRIDE=$(jq -r '.process_overrides.layer_height_mm // empty' "$SLICING")
            if [ "$CODE" -eq 0 ] && [ -n "$LAYER_OVERRIDE" ] && ! awk -v value="$LAYER_OVERRIDE" -v minimum="$MIN_LAYER" -v maximum="$MAX_LAYER" 'BEGIN { exit !(value+0 >= minimum+0 && value+0 <= maximum+0) }'; then
              printf '%s\n' 'Layer height is outside the materialized nozzle profile limits.' >> "$LOG"
              CODE=1
            fi
            for SPEED_KEY in outer_wall_speed_mm_s inner_wall_speed_mm_s; do
              SPEED_VALUE=$(jq -r --arg key "$SPEED_KEY" '.process_overrides[$key] // empty' "$SLICING")
              if [ "$CODE" -eq 0 ] && [ -n "$SPEED_VALUE" ] && ! awk -v value="$SPEED_VALUE" -v maximum="$WALL_LIMIT" 'BEGIN { exit !(value+0 >= 1 && value+0 <= maximum+0) }'; then
                printf '%s\n' "$SPEED_KEY exceeds the materialized A1 machine speed limit." >> "$LOG"
                CODE=1
              fi
            done
          fi

          if [ "$CODE" -eq 0 ] && [ "$NATIVE_MULTIMATERIAL" = "true" ]; then
            ASSEMBLE_RUNTIME="$RUN/$JOB_ID-assemble.json"
            PARTS_RUNTIME="$RUN/$JOB_ID-parts"
            MATERIAL_SUMMARY="$RUN/$JOB_ID-materials.json"
            rm -rf "$PARTS_RUNTIME" "$ASSEMBLE_RUNTIME" "$MATERIAL_SUMMARY"
            python3 "$BASE/materialize-bambu-multimaterial.py" \
              --profile-root "$PROFILE_ROOT" \
              --input "$UPLOADS/$INPUT_FILE" \
              --job "$SLICING" \
              --process-source "$PROCESS_SOURCE" \
              --process-output "$PROCESS_RUNTIME" \
              --manifest-output "$ASSEMBLE_RUNTIME" \
              --parts-dir "$PARTS_RUNTIME" \
              --summary-output "$MATERIAL_SUMMARY" >> "$LOG" 2>&1
            CODE=$?

            [ "$CODE" -ne 0 ] || { apply_bed_type_contract "$SLICING" "$PROCESS_RUNTIME" >> "$LOG" 2>&1; CODE=$?; }
            if [ "$CODE" -eq 0 ]; then
              FILAMENTS=$(jq -r '.filament_profile_paths | join(";")' "$MATERIAL_SUMMARY")
              if [ -x "$BINARY" ] && [ -s "$MACHINE_RUNTIME" ] && [ -s "$PROCESS_RUNTIME" ] && [ -s "$ASSEMBLE_RUNTIME" ] && [ -n "$FILAMENTS" ]; then
                start_progress_pipe
                unshare --net -- env \
                  XDG_RUNTIME_DIR="$XDG_RUNTIME" \
                  LD_LIBRARY_PATH="$ROOT/bin" \
                  "$BINARY" \
                  --load-settings "$MACHINE_RUNTIME;$PROCESS_RUNTIME" \
                  --load-filaments "$FILAMENTS" \
                  --load-assemble-list "$ASSEMBLE_RUNTIME" \
                  --allow-multicolor-oneplate \
                  $PROGRESS_OPTION \
                  --slice 0 \
                  --export-3mf "plate_1.gcode.3mf" \
                  --outputdir "$JOB_OUTPUT" >> "$LOG" 2>&1
                CODE=$?
                stop_progress_pipe
              else
                printf '%s\n' 'Native multimaterial runtime is incomplete.' >> "$LOG"
                CODE=1
              fi
            fi
          elif [ "$CODE" -eq 0 ]; then
            ADHESION=none
            BRIM_WIDTH=0
            RAFT_LAYERS=0
            SUPPORT_MODE=off
            SUPPORT_PLATE_ONLY=1
            SUPPORT_ANGLE=30
            SUPPORT_STYLE=standard

            case "$PROCESS_TOKEN" in
              v6:*)
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
              SUPPORT_STYLE=${8:-standard}
                ;;
            esac

            case "$ADHESION" in
              brim) BRIM_TYPE=outer_only; RAFT_VALUE=0 ;;
              raft) BRIM_TYPE=no_brim; BRIM_WIDTH=0; RAFT_VALUE=$RAFT_LAYERS ;;
              *) BRIM_TYPE=no_brim; BRIM_WIDTH=0; RAFT_VALUE=0 ;;
            esac

            case "$SUPPORT_MODE" in
              tree) ENABLE_SUPPORT=1; SUPPORT_TYPE='tree(auto)' ;;
              normal) ENABLE_SUPPORT=1; SUPPORT_TYPE='normal(auto)' ;;
              *) ENABLE_SUPPORT=0; SUPPORT_TYPE='normal(auto)' ;;
            esac

            if [ -f "$PROCESS_SOURCE" ]; then
              LAYER_HEIGHT=$(jq -r '.process_overrides.layer_height_mm // empty' "$SLICING")
              OUTER_WALL_SPEED=$(jq -r '.process_overrides.outer_wall_speed_mm_s // empty' "$SLICING")
              INNER_WALL_SPEED=$(jq -r '.process_overrides.inner_wall_speed_mm_s // empty' "$SLICING")
              REQUEST_SUPPORT_STYLE=$(jq -r '.process_overrides.support_style // empty' "$SLICING")
              [ -z "$REQUEST_SUPPORT_STYLE" ] || SUPPORT_STYLE="$REQUEST_SUPPORT_STYLE"
              jq \
                --arg raft "$RAFT_VALUE" \
                --arg brim_type "$BRIM_TYPE" \
                --arg brim_width "$BRIM_WIDTH" \
                --arg enable_support "$ENABLE_SUPPORT" \
                --arg support_type "$SUPPORT_TYPE" \
                --arg support_style "$SUPPORT_STYLE" \
                --arg plate_only "$SUPPORT_PLATE_ONLY" \
                --arg angle "$SUPPORT_ANGLE" \
                --arg layer_height "$LAYER_HEIGHT" \
                --arg outer_wall_speed "$OUTER_WALL_SPEED" \
                --arg inner_wall_speed "$INNER_WALL_SPEED" \
                '. + {
                  raft_layers:$raft,
                  brim_type:$brim_type,
                  brim_width:$brim_width,
                  enable_support:$enable_support,
                  support_type:$support_type,
                  support_style:$support_style,
                  support_on_build_plate_only:$plate_only,
                  support_threshold_angle:$angle,
                  v6_adhesion_mode:(if $raft != "0" then "raft" elif $brim_type != "no_brim" then "brim" else "none" end),
                  v6_support_mode:(if $enable_support == "0" then "off" elif $support_type == "tree(auto)" then "tree" else "normal" end)
                }
                | if $layer_height == "" then . else .layer_height = $layer_height end
                | if $outer_wall_speed == "" then . else .outer_wall_speed = (if (.outer_wall_speed | type) == "array" then [$outer_wall_speed] else $outer_wall_speed end) end
                | if $inner_wall_speed == "" then . else .inner_wall_speed = (if (.inner_wall_speed | type) == "array" then [$inner_wall_speed] else $inner_wall_speed end) end' "$PROCESS_SOURCE" > "$PROCESS_RUNTIME"
            fi

            [ "$CODE" -ne 0 ] || { apply_bed_type_contract "$SLICING" "$PROCESS_RUNTIME" >> "$LOG" 2>&1; CODE=$?; }
            if [ -x "$BINARY" ] && [ -s "$MACHINE_RUNTIME" ] && [ -s "$PROCESS_RUNTIME" ] && [ -n "$FILAMENT" ]; then
              start_progress_pipe
              unshare --net -- env \
                XDG_RUNTIME_DIR="$XDG_RUNTIME" \
                LD_LIBRARY_PATH="$ROOT/bin" \
                "$BINARY" \
                --load-settings "$MACHINE_RUNTIME;$PROCESS_RUNTIME" \
                --load-filaments "$ROOT/resources/profiles/$FILAMENT" \
                --load-defaultfila \
                --ensure-on-bed \
                --arrange 1 \
                $PROGRESS_OPTION \
                --slice 0 \
                --export-3mf "plate_1.gcode.3mf" \
                --outputdir "$JOB_OUTPUT" \
                "$UPLOADS/$INPUT_FILE" >> "$LOG" 2>&1
              CODE=$?
              stop_progress_pipe
            else
              printf '%s\n' 'Bambu Studio profile or binary missing.' >> "$LOG"
              CODE=1
            fi
          fi
          ;;

        prusaslicer)
          BINARY=/usr/bin/prusa-slicer
          CONFIG=$(jq -r '.engine_profiles.prusaslicer.config // empty' "$PROFILE_FILE")
          GCODE="$JOB_OUTPUT/$JOB_ID.gcode"
          if [ -x "$BINARY" ]; then
            if [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
              unshare --net -- "$BINARY" --load "$CONFIG" --export-gcode --output "$GCODE" "$UPLOADS/$INPUT_FILE" > "$LOG" 2>&1
            else
              unshare --net -- "$BINARY" --export-gcode --output "$GCODE" "$UPLOADS/$INPUT_FILE" > "$LOG" 2>&1
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
            unshare --net -- "$BINARY" slice -j "$DEFINITION" -l "$UPLOADS/$INPUT_FILE" -o "$GCODE" > "$LOG" 2>&1
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

      if [ "$CODE" -eq 0 ] && [ "$OUTPUT_FORMAT" = "gcode" ]; then
        CANONICAL_GCODE="$JOB_OUTPUT/plate_1.gcode"
        GCODE_SOURCE=$(find "$JOB_OUTPUT" -maxdepth 4 -type f -name '*.gcode' | sort | head -n 1)
        if [ -z "$GCODE_SOURCE" ]; then
          printf '%s\n' 'Slicer returned success but no G-code artifact was found.' >> "$LOG"
          CODE=1
        else
          if [ "$GCODE_SOURCE" != "$CANONICAL_GCODE" ]; then
            cp -f "$GCODE_SOURCE" "$CANONICAL_GCODE"
            if [ "$?" -ne 0 ]; then
              printf '%s\n' 'G-code artifact could not be normalized.' >> "$LOG"
              CODE=1
            fi
          fi
          if [ "$CODE" -eq 0 ]; then
            chmod 0644 "$CANONICAL_GCODE"
            if [ ! -s "$CANONICAL_GCODE" ]; then
              printf '%s\n' 'Normalized G-code artifact is empty.' >> "$LOG"
              CODE=1
            fi
          fi
        fi
      fi

      # V6_VALID_GCODE_RECOVERY_V1
      # Bambu Studio kann nach vollständig geschriebenem G-Code mit einem
      # nachgelagerten Signalcode enden. Nur ein strukturell vollständiges
      # Bambu-Artefakt darf diesen Exitcode überstimmen.
      if [ "$OUTPUT_FORMAT" = "gcode" ] && [ "$ENGINE" = "bambu_studio" ]; then
        V6_ORIGINAL_CODE="$CODE"
        CANONICAL_GCODE="$JOB_OUTPUT/plate_1.gcode"
        GCODE_SOURCE=$(find "$JOB_OUTPUT" -maxdepth 4 -type f -name '*.gcode' | sort | head -n 1)

        if [ -n "$GCODE_SOURCE" ] && v6_validate_bambu_gcode "$GCODE_SOURCE"; then
          if [ "$GCODE_SOURCE" != "$CANONICAL_GCODE" ]; then
            cp -f "$GCODE_SOURCE" "$CANONICAL_GCODE"
          fi

          if v6_validate_bambu_gcode "$CANONICAL_GCODE"; then
            if [ "$V6_ORIGINAL_CODE" -ne 0 ]; then
              printf '%s\n' "Bambu Studio exit code $V6_ORIGINAL_CODE ignored after complete G-code validation." >> "$LOG"
            fi
            CODE=0
          else
            printf '%s\n' 'Canonical G-code failed structural validation.' >> "$LOG"
            CODE=1
          fi
        elif [ "$CODE" -eq 0 ]; then
          printf '%s\n' 'Bambu Studio returned success but G-code validation failed.' >> "$LOG"
          CODE=1
        fi
      fi

      # Always validate effective heater commands after any exit-code recovery.
      # Network-isolated slicing must never publish a thermally unsafe artifact.
      if [ "$CODE" -eq 0 ] && [ "$ENGINE" = "bambu_studio" ]; then
        SAFETY_GCODE=$(find "$JOB_OUTPUT" -maxdepth 4 -type f -name '*.gcode' | sort | head -n 1)
        if [ -n "$SAFETY_GCODE" ]; then
          if [ "$NATIVE_MULTIMATERIAL" = "true" ]; then
            python3 "$BASE/gcode_artifact_validation.py" "$SLICING" "$SAFETY_GCODE" "$MATERIAL_SUMMARY" >> "$LOG" 2>&1
          else
            python3 "$BASE/gcode_artifact_validation.py" "$SLICING" "$SAFETY_GCODE" >> "$LOG" 2>&1
          fi
          CODE=$?
        else
          printf '%s\n' 'No G-code was available for the final hardware safety check.' >> "$LOG"
          CODE=1
        fi
      fi

      FILE_COUNT=$(find "$JOB_OUTPUT" -maxdepth 1 -type f -name '*.gcode' -size +0c | wc -l)
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
