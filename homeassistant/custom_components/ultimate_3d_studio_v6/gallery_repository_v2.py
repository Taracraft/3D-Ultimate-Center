"""Extended canonical V6 gallery repository."""
from __future__ import annotations

import shutil
from typing import Any

from .gallery_repository import (
    V6GalleryRepository,
    _real_path,
    _safe_relative,
)


class V6GalleryRepositoryV2(V6GalleryRepository):
    """Add verified copy semantics to the canonical V6 gallery."""

    def copy(
        self,
        path: str,
        target_folder: str,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        source = self.resolve(path)
        directory = _real_path(self.root, _safe_relative(target_folder))
        if not directory.is_dir():
            raise NotADirectoryError(target_folder)
        if source.is_dir() and source in directory.parents:
            raise ValueError("Ordner kann nicht in sich selbst kopiert werden")
        target = directory / source.name
        if source == target:
            raise ValueError("Quelle und Ziel sind identisch")
        if target.exists():
            if not overwrite:
                raise FileExistsError(target.name)
            shutil.rmtree(target) if target.is_dir() else target.unlink()
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        if not target.exists():
            raise RuntimeError("Galeriekopie konnte nicht bestätigt werden")
        return self._folder_item(target) if target.is_dir() else self._file_item(target)