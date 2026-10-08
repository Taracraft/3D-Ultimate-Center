"""Palette regression checks; no slicer process or printer connection."""
import importlib.util
import io
import os
from pathlib import Path
import zipfile
import pytest
ROOT = Path(os.environ.get("PREVIEW_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
spec = importlib.util.spec_from_file_location("palette_test_parser", ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/gcode_toolpath.py")
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)

@pytest.mark.parametrize("raw,expected", [
    ("#F72323;#FFFFFF;#FBFF00;#000000", ["#F72323", "#FFFFFF", "#FBFF00", "#000000"]),
    ("#FF0000;;#000000", ["#FF0000", "", "#000000"]),
    (";#FFFFFF;", ["", "#FFFFFF", ""]),
    ('["#FF0000",null,"#000000"]', ["#FF0000", "", "#000000"]),
    ('["#FF0000",123456,true,{},"#000000"]', ["#FF0000", "", "", "", "#000000"]),
    ("#ff0000ff;#FFFFFFFF;000000", ["#FF0000", "#FFFFFF", "#000000"]),
    ("#ff0000;garbage;#000000", ["#FF0000", "", "#000000"]),
    ('"#ff0000;;#000000"', ["#FF0000", "", "#000000"]),
    ("", []),
    ("null", []),
])
def test_palette_slots_never_shift_or_gain_invented_colors(raw, expected):
    assert parser._metadata("; filament_colour = " + raw)[0] == expected

def test_physical_extruder_display_color_is_not_a_job_filament_palette():
    assert parser._metadata("; extruder_colour = #00FF00")[0] == []

def test_invalid_palette_does_not_change_tools_paths_or_layers():
    movement = "M83\nM620 S3A\n; Z_HEIGHT: 0.2\n; FEATURE: Outer wall\nG1 X10 Y0 E1\nT1\nG1 X10 Y10 E1\n"
    valid = parser.parse_toolpath(("; filament_colour = #F72323;#FFFFFF;#FBFF00;#000000\n" + movement).encode(), start_layer=0, end_layer=1)
    unknown = parser.parse_toolpath(("; filament_colour = #F72323;;#FBFF00;#000000\n" + movement).encode(), start_layer=0, end_layer=1)
    assert unknown["filament_colors"] == ["#F72323", "", "#FBFF00", "#000000"]
    for key in ["tools", "layers", "chunk", "bounds"]:
        assert unknown[key] == valid[key]
    assert [s[5] for s in unknown["chunk"]["layers"][0]["segments"]] == [3, 1]

def test_same_palette_contract_for_plain_gcode_and_3mf_container():
    data = b"; filament_colour = #FF0000;;#000000\nM83\nT2\n; Z_HEIGHT: 0.2\nG1 X10 Y10 E1\n"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("Metadata/plate_1.gcode", data)
    assert parser.parse_toolpath(archive.getvalue(), start_layer=0, end_layer=1) == parser.parse_toolpath(data, start_layer=0, end_layer=1)
