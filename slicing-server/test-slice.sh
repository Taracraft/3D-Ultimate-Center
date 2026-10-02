#!/bin/sh
BASE=/var/lib/homeassistant/3d-printer-slicing-server/data
/usr/bin/prusa-slicer --export-gcode --output "$BASE/output/alpha1-test.gcode" "$BASE/uploads/alpha1-test.stl" > "$BASE/output/alpha1-test.log" 2>&1
echo $? > "$BASE/output/alpha1-test.exitcode"
