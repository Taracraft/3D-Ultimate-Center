"""Canonical runtime path layout."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class StudioPaths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def runtime(self) -> Path:
        return self.root / "runtime"

    @property
    def database(self) -> Path:
        return self.data / "studio.sqlite3"

    @property
    def assets(self) -> Path:
        return self.data / "assets"

    @property
    def jobs(self) -> Path:
        return self.data / "jobs"

    @property
    def profiles(self) -> Path:
        return self.data / "profiles"

    @property
    def uploads(self) -> Path:
        return self.runtime / "uploads"

    @property
    def logs(self) -> Path:
        return self.runtime / "logs"

    def create(self) -> None:
        for path in (
            self.data,
            self.runtime,
            self.assets,
            self.jobs,
            self.profiles,
            self.uploads,
            self.logs,
        ):
            path.mkdir(parents=True, exist_ok=True)
