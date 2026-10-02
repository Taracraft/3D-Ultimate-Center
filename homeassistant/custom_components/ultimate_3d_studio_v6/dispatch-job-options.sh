#!/bin/sh
BASE=/var/lib/homeassistant/3d-printer-slicing-server
DATA="$BASE/data"
JOBS="$DATA/jobs"
UPLOADS="$DATA/uploads"
OUTPUT="$DATA/output"
PROFILES="$BASE/profiles/printers"
RUN="$BASE/run"
mkdir -p "$JOBS" "$UPLOADS" "$OUTPUT" "$RUN"

apply_bed_type_contract() {
  JOB_FILE=$1
  PROCESS_FILE=$2
  BED_TYPE=$(jq -r '.process_overrides.bambu_bed_type // empty' "$JOB_FILE")
  if [ -z "$BED_TYPE" ]; then
    return 0
  fi
  TEMP_FILE="$PROCESS_FILE.bed-type.tmp"
  jq --arg bed_type "$BED_TYPE" '. + {curr_bed_type:$bed_type}' "$PROCESS_FILE" > "$TEMP_FILE"
  CODE=$?
  if [ "$CODE" -ne 0 ]; then
    rm -f "$TEMP_FILE"
    return "$CODE"
  fi
  mv "$TEMP_FILE" "$PROCESS_FILE"
}

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
            python3 "$BASE/materialize-bambu-machine.py" "$PROFILE_ROOT" "$MACHINE" "$MACHINE_RUNTIME" > "$LOG" 2>&1
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

            if [ "$CODE" -eq 0 ]; then
              apply_bed_type_contract "$SLICING" "$PROCESS_RUNTIME" >> "$LOG" 2>&1
              CODE=$?
            fi

            if [ "$CODE" -eq 0 ]; then
              FILAMENTS=$(jq -r '.filament_profile_paths | join(";")' "$MATERIAL_SUMMARY")
              if [ -x "$BINARY" ] && [ -s "$MACHINE_RUNTIME" ] && [ -s "$PROCESS_RUNTIME" ] && [ -s "$ASSEMBLE_RUNTIME" ] && [ -n "$FILAMENTS" ]; then
                unshare --net -- env \
                  XDG_RUNTIME_DIR="$XDG_RUNTIME" \
                  LD_LIBRARY_PATH="$ROOT/bin" \
                  "$BINARY" \
                  --load-settings "$MACHINE_RUNTIME;$PROCESS_RUNTIME" \
                  --load-filaments "$FILAMENTS" \
                  --load-assemble-list "$ASSEMBLE_RUNTIME" \
                  --allow-multicolor-oneplate \
                  --slice 0 \
                  --outputdir "$JOB_OUTPUT" >> "$LOG" 2>&1
                CODE=$?
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
              jq \
                --arg raft "$RAFT_VALUE" \
                --arg brim_type "$BRIM_TYPE" \
                --arg brim_width "$BRIM_WIDTH" \
                --arg enable_support "$ENABLE_SUPPORT" \
                --arg support_type "$SUPPORT_TYPE" \
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
                  support_on_build_plate_only:$plate_only,
                  support_threshold_angle:$angle,
                  v6_adhesion_mode:(if $raft != "0" then "raft" elif $brim_type != "no_brim" then "brim" else "none" end),
                  v6_support_mode:(if $enable_support == "0" then "off" elif $support_type == "tree(auto)" then "tree" else "normal" end)
                }
                | if $layer_height == "" then . else .layer_height = $layer_height end
                | if $outer_wall_speed == "" then . else .outer_wall_speed = (if (.outer_wall_speed | type) == "array" then [$outer_wall_speed] else $outer_wall_speed end) end
                | if $inner_wall_speed == "" then . else .inner_wall_speed = (if (.inner_wall_speed | type) == "array" then [$inner_wall_speed] else $inner_wall_speed end) end' "$PROCESS_SOURCE" > "$PROCESS_RUNTIME"
              CODE=$?
            fi

            if [ "$CODE" -eq 0 ]; then
              apply_bed_type_contract "$SLICING" "$PROCESS_RUNTIME" >> "$LOG" 2>&1
              CODE=$?
            fi

            if [ "$CODE" -eq 0 ] && [ -x "$BINARY" ] && [ -s "$MACHINE_RUNTIME" ] && [ -s "$PROCESS_RUNTIME" ] && [ -n "$FILAMENT" ]; then
              unshare --net -- "$BINARY" --load-settings "$MACHINE_RUNTIME;$PROCESS_RUNTIME" --load-filaments "$ROOT/resources/profiles/$FILAMENT" --load-defaultfila --ensure-on-bed --arrange 1 --slice 0 --outputdir "$JOB_OUTPUT" > "$LOG" 2>&1
              CODE=$?
            elif [ "$CODE" -eq 0 ]; then
              printf '%s\n' 'Bambu Studio profile or binary missing.' > "$LOG"
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
          if [ "$CODE" -eq 0 ] && [ "$ENGINE" = "bambu_studio" ]; then
            if [ ! -f "$BASE/validate-bambu-bed-temperature.py" ] || [ ! -f "$BASE/build_plate_contract.py" ]; then
              printf '%s\n' 'Bambu build-plate temperature validator is missing.' >> "$LOG"
              CODE=1
            else
              PYTHONPATH="$BASE" python3 "$BASE/validate-bambu-bed-temperature.py" --job "$SLICING" --process "$PROCESS_RUNTIME" --gcode "$CANONICAL_GCODE" >> "$LOG" 2>&1
              CODE=$?
            fi
          fi
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