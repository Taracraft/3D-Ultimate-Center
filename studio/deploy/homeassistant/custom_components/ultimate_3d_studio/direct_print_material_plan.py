"""Authoritative material-source resolution for Studio direct printing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


class DirectPrintMaterialPlanError(ValueError):
    """Raised when a slicer job has no safe, immutable material source."""


@dataclass(frozen=True, slots=True)
class AuthoritativeAmsStart:
    use_ams: bool
    mapping: tuple[int, ...]
    labels: tuple[str, ...]
    source: str
    target_printer_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "use_ams": self.use_ams,
            "ams_mapping": list(self.mapping),
            "labels": list(self.labels),
            "source": self.source,
            "target_printer_id": self.target_printer_id,
        }


def _slot_index(slot: Mapping[str, Any]) -> int | None:
    try:
        value = int(slot.get("slot_index"))
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 255 else None


def derive_authoritative_ams_start(
    job: Mapping[str, Any],
    *,
    printer_id: str,
    printer_slots: Iterable[Mapping[str, Any]],
) -> AuthoritativeAmsStart:
    """Resolve the immutable AMS or external-spool source stored by the slicer."""
    plan = job.get("material_source_plan")
    if not isinstance(plan, Mapping):
        plan = job.get("ams_material_plan")
    if not isinstance(plan, Mapping):
        raise DirectPrintMaterialPlanError(
            "Der Slicerauftrag enthält keinen autoritativen Materialquellenplan."
        )
    source = str(plan.get("source", "")).strip()
    if source not in {
        "authoritative_ams_runtime",
        "authoritative_external_spool_runtime",
    }:
        raise DirectPrintMaterialPlanError(
            "Der Slicerauftrag wurde nicht mit einer autoritativen Materialquelle erstellt."
        )

    target = str(plan.get("target_printer_id", "")).strip()
    target_printer = job.get("target_printer")
    if not target and isinstance(target_printer, Mapping):
        target = str(target_printer.get("printer_id", "")).strip()
    if not target:
        raise DirectPrintMaterialPlanError(
            "Im Materialquellenplan fehlt der Ziel-Drucker."
        )
    if target != printer_id:
        raise DirectPrintMaterialPlanError(
            "Der Materialquellenplan gehört zu einem anderen Drucker."
        )

    filaments = plan.get("filaments")
    if not isinstance(filaments, list) or not filaments:
        raise DirectPrintMaterialPlanError(
            "Der Materialquellenplan enthält kein Filament."
        )
    if not all(isinstance(item, Mapping) for item in filaments):
        raise DirectPrintMaterialPlanError(
            "Der Materialquellenplan enthält eine ungültige Filamentliste."
        )

    if source == "authoritative_external_spool_runtime":
        if len(filaments) != 1:
            raise DirectPrintMaterialPlanError(
                "Die externe Spule unterstützt genau einen Materialkanal."
            )
        item = filaments[0]
        try:
            extruder = int(item.get("extruder"))
        except (TypeError, ValueError) as exc:
            raise DirectPrintMaterialPlanError(
                "Der Materialquellenplan der externen Spule enthält keinen gültigen Extruder."
            ) from exc
        if extruder != 1 or str(item.get("source", "")).strip() != "external_spool":
            raise DirectPrintMaterialPlanError(
                "Der Materialquellenplan der externen Spule ist ungültig."
            )
        name = str(item.get("name", "Externes Filament")).strip() or "Externes Filament"
        return AuthoritativeAmsStart(
            use_ams=False,
            mapping=(),
            labels=(f"Externe Spule: {name.removeprefix('Externe Spule: ').strip()}",),
            source=source,
            target_printer_id=target,
        )

    if len(filaments) > 4:
        raise DirectPrintMaterialPlanError(
            "Der AMS-Materialplan enthält mehr als vier Materialkanäle."
        )

    present_slots = {
        value
        for slot in printer_slots
        if bool(slot.get("present"))
        for value in [_slot_index(slot)]
        if value is not None
    }
    ordered = sorted(filaments, key=lambda item: int(item.get("extruder", 0) or 0))
    mapping: list[int] = []
    labels: list[str] = []
    for expected_extruder, item in enumerate(ordered, start=1):
        try:
            extruder = int(item.get("extruder"))
            slot_index = int(item.get("slot_index"))
        except (TypeError, ValueError) as exc:
            raise DirectPrintMaterialPlanError(
                "Der AMS-Materialplan enthält ungültige Extruder- oder Slotwerte."
            ) from exc
        if extruder != expected_extruder:
            raise DirectPrintMaterialPlanError(
                "Der AMS-Materialplan enthält keine lückenlose Extruderreihenfolge."
            )
        if slot_index not in present_slots:
            raise DirectPrintMaterialPlanError(
                f"Der vorgesehene AMS-Slot {slot_index + 1} ist leer oder nicht verfügbar."
            )
        display_slot = int(item.get("display_slot", slot_index + 1) or slot_index + 1)
        name = str(item.get("name", f"Filament {extruder}")).strip()
        mapping.append(slot_index)
        labels.append(f"AMS {display_slot}: {name}")

    return AuthoritativeAmsStart(
        use_ams=True,
        mapping=tuple(mapping),
        labels=tuple(labels),
        source=source,
        target_printer_id=target,
    )
