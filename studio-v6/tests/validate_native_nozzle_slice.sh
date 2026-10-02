#!/bin/sh
set -eu

BASE=${VALIDATION_BASE:-/host/3d-printer-slicing-server}
ROOT=$BASE/engines/bambu-studio/squashfs-root
WORK=${VALIDATION_WORK:-/work/native-validation}

case "${TEST_KEY:-}" in
  02) DIAMETER=0.2; LAYER=0.08 ;;
  04) DIAMETER=0.4; LAYER=0.12 ;;
  06) DIAMETER=0.6; LAYER=0.2 ;;
  08) DIAMETER=0.8; LAYER=0.3 ;;
  *) printf '%s\n' 'invalid TEST_KEY' >&2; exit 2 ;;
esac

DIR=$WORK/nozzle-$TEST_KEY
OUTPUT=$DIR/slice-output-host-pathfix4
XDG=/tmp/v6-xdg-$TEST_KEY
LOG=$DIR/slice-host-pathfix4.log
test -s "$DIR/machine.json"
test -s "$DIR/process-custom.json"
test -s "$DIR/assemble-custom.json"
test ! -e "$OUTPUT"
mkdir -p "$OUTPUT" "$XDG"
chmod 700 "$XDG"

. "$BASE/bed-temperature-contract.sh"
apply_bed_type_contract "$DIR/job-custom.json" "$DIR/process-custom.json"
jq --arg target "$WORK" \
  'walk(if type=="string" then sub("^/work/native-validation";$target) else . end)' \
  "$DIR/assemble-custom.json" > "$DIR/assemble-host.json"
FILAMENTS=$(jq -r '.filament_profile_paths | join(";")' "$DIR/summary-custom.json")
FILAMENTS=$(printf '%s' "$FILAMENTS" | sed "s#/host/3d-printer-slicing-server#$BASE#g")
test -n "$FILAMENTS"

env \
  XDG_RUNTIME_DIR="$XDG" \
  LD_LIBRARY_PATH="$ROOT/bin" \
  "$ROOT/bin/bambu-studio" \
  --load-settings "$DIR/machine.json;$DIR/process-custom.json" \
  --load-filaments "$FILAMENTS" \
  --load-assemble-list "$DIR/assemble-host.json" \
  --allow-multicolor-oneplate \
  --slice 0 \
  --export-3mf "plate_1.gcode.3mf" \
  --outputdir "$OUTPUT" >"$LOG" 2>&1

ARTIFACT=$(find "$OUTPUT" -maxdepth 2 -type f -name '*.3mf' | head -n 1)
test -n "$ARTIFACT"
test -s "$ARTIFACT"
python3 -c 'import sys, zipfile; open(sys.argv[2], "wb").write(zipfile.ZipFile(sys.argv[1]).read("Metadata/plate_1.gcode"))' \
  "$ARTIFACT" "$DIR/plate_1.gcode"
GCODE=$DIR/plate_1.gcode
test "$(wc -c < "$GCODE")" -ge 4096
grep -q '^; HEADER_BLOCK_START' "$GCODE"
grep -Eq '^; total layer number: [1-9][0-9]*' "$GCODE"
grep -q "^; nozzle_diameter = $DIAMETER$" "$GCODE"
grep -q "^; layer_height = $LAYER$" "$GCODE"
grep -q '^; outer_wall_speed = 60$' "$GCODE"
grep -q '^; inner_wall_speed = 90$' "$GCODE"
validate_bed_type_contract "$GCODE" "$DIR/job-custom.json" "$DIR/process-custom.json" >/dev/null

printf '%s mm: native slice + 3MF + G-code verified, %s bytes, %s layers\n' \
  "$DIAMETER" "$(wc -c < "$GCODE" | tr -d '[:space:]')" \
  "$(sed -n -E 's/^; total layer number: ([1-9][0-9]*).*/\1/p' "$GCODE" | head -n 1)"