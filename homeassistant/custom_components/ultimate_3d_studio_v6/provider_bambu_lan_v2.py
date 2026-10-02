"""Bambu LAN provider V2 with stage telemetry and confirmed stop handling."""
from __future__ import annotations

import asyncio
from dataclasses import replace

from .commands import PrinterCommandResult, create_sequence_id
from .models import PrinterSnapshot
from .network_plugin import NetworkCommand, build_print_control, build_print_speed
from .print_stage import resolve_print_stage
from .provider_bambu_lan import BambuLanProvider
from .telemetry import find, number

_STOP_CONFIRMED_STATES = {
    "idle",
    "finish",
    "finished",
    "complete",
    "completed",
    "failed",
    "cancelled",
    "stopped",
}
_STOP_ACTIVE_STATES = {
    "running",
    "printing",
    "prepare",
    "preparing",
    "pause",
    "paused",
}
_REMAINING_TIME_STATES = _STOP_ACTIVE_STATES | {"starting"}


class BambuLanProviderV2(BambuLanProvider):
    """Add print stages, remaining time, Bambu error retry and confirmed stop."""

    def _remaining_time_minutes(self) -> int | None:
        if self.telemetry.printer_state.casefold() not in _REMAINING_TIME_STATES:
            return None
        value = number(find(self.telemetry.raw, (
            "mc_remaining_time",
            "remaining_time_minutes",
            "remaining_minutes",
        )))
        if value is None or value < 0:
            return None
        return max(0, int(round(value)))

    async def async_printers(self) -> tuple[PrinterSnapshot, ...]:
        base_snapshots = await super().async_printers()
        if not base_snapshots:
            return ()
        stage = resolve_print_stage(self.telemetry.raw)
        return (
            replace(
                base_snapshots[0],
                remaining_time_minutes=self._remaining_time_minutes(),
                print_stage_code=stage.code,
                print_stage_key=stage.key,
                print_stage_label=stage.label,
                print_stage_detail=stage.detail,
                print_stage_active=stage.active,
            ),
        )

    async def async_command(
        self,
        printer_id: str,
        command: str,
        *,
        speed_level: int | None = None,
    ) -> PrinterCommandResult | None:
        if printer_id != self.serial:
            return None

        if command == "speed":
            if speed_level is None:
                raise RuntimeError("Für die Druckgeschwindigkeit fehlt speed_level.")
            result = await self._async_submit(build_print_speed(speed_level), timeout=12.0)
            confirmed = await self._async_wait_for_speed_level(speed_level)
            return PrinterCommandResult(
                printer_id=self.serial,
                provider=self.provider_id,
                command="speed",
                sequence_id=result.sequence_id,
                accepted=result.printer_accepted,
                confirmed=confirmed,
                final_state=self.telemetry.printer_state,
                message=(
                    f"Geschwindigkeit auf Stufe {speed_level} gesetzt."
                    if confirmed
                    else "Telemetriebestätigung steht noch aus; der Befehl wurde gesendet."
                ),
            )

        if command == "retry":
            sequence_id = create_sequence_id()
            result = await self._async_submit(
                NetworkCommand(
                    section="print",
                    command="ams_control",
                    sequence_id=sequence_id,
                    payload={
                        "print": {
                            "sequence_id": sequence_id,
                            "command": "ams_control",
                            "param": "resume",
                        }
                    },
                    qos=1,
                ),
                timeout=15.0,
            )
            return PrinterCommandResult(
                printer_id=self.serial,
                provider=self.provider_id,
                command="retry",
                sequence_id=result.sequence_id,
                accepted=result.printer_accepted,
                confirmed=result.printer_accepted,
                final_state=self.telemetry.printer_state,
                message=(
                    "Der Drucker hat den erneuten Filament-/AMS-Versuch angenommen. "
                    "Der Störungsstatus wird weiter überwacht."
                ),
            )

        if command != "stop":
            return await super().async_command(printer_id, command, speed_level=speed_level)

        attempts = 0
        last_sequence = ""
        for attempt in range(1, 3):
            attempts = attempt
            result = await self._async_submit(
                build_print_control("stop"),
                timeout=12.0,
            )
            last_sequence = result.sequence_id
            if await self._async_wait_for_stop_confirmation(
                timeout=14.0 if attempt == 1 else 18.0,
            ):
                final_state = self.telemetry.printer_state
                return PrinterCommandResult(
                    printer_id=self.serial,
                    provider=self.provider_id,
                    command="stop",
                    sequence_id=last_sequence,
                    accepted=result.printer_accepted,
                    confirmed=True,
                    attempts=attempts,
                    final_state=final_state,
                    message=(
                        "Der Drucker hat den Abbruch bestätigt."
                        if attempts == 1
                        else "Der Drucker hat den Abbruch nach automatischer Wiederholung bestätigt."
                    ),
                )
            if attempt == 1:
                await asyncio.sleep(1.5)

        final_state = self.telemetry.printer_state
        raise RuntimeError(
            "Der Drucker hat den Stop-Befehl angenommen, den Druckabbruch "
            f"aber nicht bestätigt. Aktueller Zustand: {final_state}. "
            "Der Stop-Befehl wurde zweimal gesendet."
        )


    async def _async_wait_for_speed_level(
        self,
        expected: int,
        *,
        timeout: float = 8.0,
    ) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if self.telemetry.speed_level == expected:
                return True
            await asyncio.sleep(0.5)
        return False

    async def _async_wait_for_stop_confirmation(
        self,
        *,
        timeout: float,
    ) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            state = self.telemetry.printer_state.casefold()
            if state in _STOP_CONFIRMED_STATES:
                return True
            if state not in _STOP_ACTIVE_STATES and state != "unknown":
                return True
            await asyncio.sleep(0.75)
        return False