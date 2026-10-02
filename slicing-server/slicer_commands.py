"""CLI command builders for local slicer providers."""

from __future__ import annotations

from pathlib import Path


def build_bambu_cli_command(
    *,
    executable: str,
    input_model: str | Path,
    output_file: str | Path,
    printer_profile: str | Path,
    process_profile: str | Path,
    filament_profiles: tuple[str | Path, ...],
) -> tuple[str, ...]:
    command = [
        executable,
        "--slice",
        "0",
        "--load-settings",
        str(printer_profile),
        "--load-settings",
        str(process_profile),
    ]
    for profile in filament_profiles:
        command.extend(("--load-filaments", str(profile)))
    command.extend(("--export-3mf", str(output_file), str(input_model)))
    return tuple(command)


def build_orca_cli_command(
    *,
    executable: str,
    input_model: str | Path,
    output_file: str | Path,
    config_file: str | Path,
) -> tuple[str, ...]:
    return (
        executable,
        "--load",
        str(config_file),
        "--output",
        str(output_file),
        "--slice",
        str(input_model),
    )