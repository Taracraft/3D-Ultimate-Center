#!/bin/sh

apply_bed_type_contract() {
  contract_job=$1
  contract_process=$2
  contract_bed_type=$(jq -r '.process_overrides.bambu_bed_type // empty' "$contract_job" 2>/dev/null)
  [ -n "$contract_bed_type" ] || return 0
  contract_tmp="$contract_process.bed-type.tmp"
  jq --arg bed_type "$contract_bed_type" '. + {curr_bed_type:$bed_type}' "$contract_process" > "$contract_tmp" || {
    rm -f "$contract_tmp"
    return 1
  }
  mv "$contract_tmp" "$contract_process"
}

bed_temperature_key() {
  case "$1" in
    'Textured PEI Plate') echo textured_plate_temp_initial_layer ;;
    'High Temp Plate') echo hot_plate_temp_initial_layer ;;
    'Cool Plate') echo cool_plate_temp_initial_layer ;;
    'Engineering Plate') echo eng_plate_temp_initial_layer ;;
    'Supertack Plate') echo supertack_plate_temp_initial_layer ;;
    'Smooth Cool Plate'|'Textured Cool Plate') echo cool_plate_temp_initial_layer ;;
    *) return 1 ;;
  esac
}

validate_bed_type_contract() {
  contract_gcode=$1
  contract_job=$2
  contract_process=$3
  contract_bed_type=$(jq -r '.process_overrides.bambu_bed_type // empty' "$contract_job" 2>/dev/null)
  [ -n "$contract_bed_type" ] || return 0
  contract_key=$(bed_temperature_key "$contract_bed_type") || return 1
  contract_expected=$(jq -r --arg key "$contract_key" '.[$key] | if type == "array" then .[0] else . end // empty' "$contract_process" 2>/dev/null)
  contract_m140=$(sed -n -E 's/^M140 S(-?[0-9]+([.][0-9]+)?).*/\1/p' "$contract_gcode" | head -n 1)
  contract_m190=$(sed -n -E 's/^M190 S(-?[0-9]+([.][0-9]+)?).*/\1/p' "$contract_gcode" | head -n 1)
  [ -n "$contract_expected" ] && [ -n "$contract_m140" ] && [ -n "$contract_m190" ] || return 1
  awk -v actual="$contract_m140" -v expected="$contract_expected" 'BEGIN { difference=actual-expected; if (difference<0) difference=-difference; exit(difference<=0.01 ? 0 : 1) }' || return 1
  awk -v actual="$contract_m190" -v expected="$contract_expected" 'BEGIN { difference=actual-expected; if (difference<0) difference=-difference; exit(difference<=0.01 ? 0 : 1) }' || return 1
  printf '%s\n' "Build plate temperature validated: $contract_bed_type, expected $contract_expected C, M140 $contract_m140 C, M190 $contract_m190 C."
}
