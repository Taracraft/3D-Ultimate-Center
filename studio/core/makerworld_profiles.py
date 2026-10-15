"""MakerWorld print-profile selection and snapshot helpers."""

from __future__ import annotations

from dataclasses import asdict

from .makerworld import MakerWorldDestination, MakerWorldModel, MakerWorldPrintProfile


def resolve_print_profile(
    model: MakerWorldModel,
    profile_id: str | None,
    destination: MakerWorldDestination,
) -> MakerWorldPrintProfile | None:
    if profile_id:
        for profile in model.print_profiles:
            if profile.id == profile_id:
                return profile
        raise ValueError(f"unknown MakerWorld print profile: {profile_id}")

    if destination == MakerWorldDestination.SLICER and model.print_profiles:
        raise ValueError("a MakerWorld print profile must be selected for Slicer import")
    return None


def profile_snapshot(profile: MakerWorldPrintProfile | None) -> dict | None:
    return asdict(profile) if profile is not None else None
