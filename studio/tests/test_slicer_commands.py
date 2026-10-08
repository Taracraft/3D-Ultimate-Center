from core.slicer_commands import build_bambu_cli_command, build_orca_cli_command


def test_bambu_command_contains_profiles_and_output() -> None:
    command = build_bambu_cli_command(
        executable="bambu-studio",
        input_model="model.3mf",
        output_file="output.3mf",
        printer_profile="printer.json",
        process_profile="process.json",
        filament_profiles=("pla.json", "petg.json"),
    )
    assert command[0] == "bambu-studio"
    assert "--export-3mf" in command
    assert "printer.json" in command
    assert "process.json" in command
    assert "pla.json" in command
    assert "petg.json" in command
    assert command[-1] == "model.3mf"


def test_orca_command_contains_input_and_output() -> None:
    command = build_orca_cli_command(
        executable="orca-slicer",
        input_model="model.stl",
        output_file="output.gcode",
        config_file="config.ini",
    )
    assert command == (
        "orca-slicer",
        "--load",
        "config.ini",
        "--output",
        "output.gcode",
        "--slice",
        "model.stl",
    )
