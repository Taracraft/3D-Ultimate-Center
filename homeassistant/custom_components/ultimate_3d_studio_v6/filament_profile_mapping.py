"""Map selected V6 filament profiles to authoritative physical AMS channels."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

_MATERIALS = ("PETG", "PLA", "ABS", "ASA", "TPU", "PA", "PC")
_IGNORED_TOKENS = {
    "bbl", "bambu", "lab", "filament", "profile", "standard", "cloud",
    "tara", "a1", "a1m", "x1", "x1c", "p1", "p1s", "hs", "plus",
    "pla", "petg", "abs", "asa", "tpu", "generic",
}


def _payload(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("payload")
    return value if isinstance(value, dict) else {}


def _material(profile: dict[str, Any]) -> str:
    payload = _payload(profile)
    values = (
        payload.get("material"), payload.get("filament_type"),
        payload.get("type"), profile.get("name"),
    )
    text = " ".join(
        " ".join(str(item) for item in value) if isinstance(value, list)
        else str(value or "")
        for value in values
    ).upper()
    for material in _MATERIALS:
        if re.search(rf"(^|[^A-Z]){material}([^A-Z]|$)", text):
            return material
    return ""


def _tokens(value: object) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) >= 3 and token not in _IGNORED_TOKENS
    }


def all_filament_profiles(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = catalog.get("profiles") if isinstance(catalog.get("profiles"), list) else []
    return [
        deepcopy(item)
        for item in profiles
        if isinstance(item, dict) and item.get("kind") == "filament"
    ]


def selected_filament_profiles(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    selection = catalog.get("selection") if isinstance(catalog.get("selection"), dict) else {}
    selected = selection.get("filament_profile_ids") if isinstance(selection, dict) else []
    selected_ids = [str(item) for item in selected] if isinstance(selected, list) else []
    by_id = {str(item.get("id")): item for item in all_filament_profiles(catalog)}
    return [deepcopy(by_id[profile_id]) for profile_id in selected_ids if profile_id in by_id]


def _channel_text(filament: dict[str, Any]) -> str:
    return " ".join(
        str(filament.get(key) or "")
        for key in (
            "name", "sub_brand", "material", "filament_id", "tray_id",
            "global_id", "display_slot",
        )
    ).casefold()


def _score(profile: dict[str, Any], filament: dict[str, Any], single_candidate: bool) -> int:
    payload = _payload(profile)
    profile_name = str(profile.get("name") or "")
    vendor = str(payload.get("vendor") or "").casefold().strip()
    profile_tokens = _tokens(profile_name) | _tokens(vendor)
    channel_text = _channel_text(filament)
    channel_tokens = _tokens(channel_text)
    score = 1 if single_candidate else 0

    setting_ids = {
        str(payload.get("setting_id") or "").casefold().strip(),
        str(payload.get("filament_id") or "").casefold().strip(),
        str(payload.get("base_id") or "").casefold().strip(),
    } - {""}
    if any(identifier in channel_text for identifier in setting_ids):
        score += 120
    if vendor and vendor != "generic" and vendor in channel_text:
        score += 70
    if vendor == "generic" and "generic" in channel_text:
        score += 55
    score += 12 * len(profile_tokens & channel_tokens)
    return score


def _material_family(value: object) -> str:
    text = str(value or "").upper().strip()
    for material in _MATERIALS:
        if re.search(rf"(^|[^A-Z]){material}([^A-Z]|$)", text):
            return material
    return ""


def _compatible(profile: dict[str, Any], filament: dict[str, Any]) -> bool:
    material = _material(profile)
    channel_material = _material_family(filament.get("material"))
    return not material or not channel_material or material == channel_material


def _attach(profile: dict[str, Any], filament: dict[str, Any]) -> None:
    filament["selected_profile"] = {
        "id": str(profile.get("id") or ""),
        "name": str(profile.get("name") or ""),
        "source": str(profile.get("source") or ""),
        "payload": deepcopy(_payload(profile)),
    }


def _best_catalog_fallback(
    catalog: dict[str, Any],
    filament: dict[str, Any],
    excluded_ids: set[str],
) -> dict[str, Any] | None:
    candidates = [
        profile for profile in all_filament_profiles(catalog)
        if str(profile.get("id") or "") not in excluded_ids
        and _compatible(profile, filament)
    ]
    if not candidates:
        return None
    scored = [(_score(profile, filament, len(candidates) == 1), profile) for profile in candidates]
    best_score = max(score for score, _profile in scored)
    best = [profile for score, profile in scored if score == best_score]
    if len(best) != 1 or best_score <= 1:
        return None
    return best[0]


def attach_selected_profiles(
    catalog: dict[str, Any],
    filaments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach selected profile metadata to authoritative material channels.

    The studio selection order is authoritative when one profile is selected per
    channel. A single compatible profile may intentionally be reused for several
    physical AMS slots, for example the same PLA+ process profile for two colors.
    Name-based matching is retained only for incomplete legacy selections.
    """
    selected = selected_filament_profiles(catalog)
    if not selected:
        return filaments

    if len(selected) == len(filaments):
        for index, (profile, filament) in enumerate(zip(selected, filaments, strict=True)):
            if not _compatible(profile, filament):
                if len(selected) == 1 and len(filaments) == 1:
                    fallback = _best_catalog_fallback(
                        catalog,
                        filament,
                        {str(profile.get("id") or "")},
                    )
                    if fallback is not None:
                        _attach(fallback, filament)
                        return filaments
                raise ValueError(
                    f"Filamentprofil {profile.get('name')} passt nicht zum Material von "
                    f"AMS-Slot {filament.get('display_slot') or index + 1}."
                )
            _attach(profile, filament)
        return filaments

    attached_profile_ids: set[str] = set()
    for filament in filaments:
        compatible = [profile for profile in selected if _compatible(profile, filament)]
        if len(compatible) == 1:
            profile = compatible[0]
            _attach(profile, filament)
            attached_profile_ids.add(str(profile.get("id") or ""))

    unresolved_profiles = [
        profile for profile in selected
        if str(profile.get("id") or "") not in attached_profile_ids
    ]
    unresolved_channels = [
        index for index, filament in enumerate(filaments)
        if not isinstance(filament.get("selected_profile"), dict)
    ]
    # The material plan contains only channels that are actually used by this
    # plate. Global/profile UI selections may still contain profiles for other
    # occupied AMS slots. Once every used channel is resolved, those unused
    # selections must not block slicing.
    if not unresolved_channels:
        return filaments
    if not unresolved_profiles:
        return filaments

    occupied: set[int] = set(index for index in range(len(filaments)) if index not in unresolved_channels)
    for profile in unresolved_profiles:
        material = _material(profile)
        candidates = [
            index for index in unresolved_channels
            if not material or str(filaments[index].get("material") or "").upper() == material
        ]
        if not candidates:
            raise ValueError(
                f"Filamentprofil {profile.get('name')} passt zu keinem Material der aktiven AMS-Slots."
            )
        scored = [
            (_score(profile, filaments[index], len(candidates) == 1), index)
            for index in candidates if index not in occupied
        ]
        if not scored:
            raise ValueError(
                f"Für Filamentprofil {profile.get('name')} ist kein freier kompatibler AMS-Slot vorhanden."
            )
        best_score = max(score for score, _index in scored)
        best = [index for score, index in scored if score == best_score]
        if len(best) != 1 or (best_score <= 1 and len(candidates) > 1):
            raise ValueError(
                f"Filamentprofil {profile.get('name')} kann keinem AMS-Slot eindeutig zugeordnet werden. "
                "Bitte die Profile in derselben Reihenfolge wie die Materialkanäle auswählen."
            )
        index = best[0]
        occupied.add(index)
        _attach(profile, filaments[index])
    return filaments
