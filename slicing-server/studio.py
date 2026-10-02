"""Project and scene graph types."""

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(slots=True, frozen=True)
class Bounds3D:
    minimum: Vector3
    maximum: Vector3

    @property
    def size(self) -> Vector3:
        return Vector3(
            self.maximum.x - self.minimum.x,
            self.maximum.y - self.minimum.y,
            self.maximum.z - self.minimum.z,
        )

    @property
    def center(self) -> Vector3:
        return Vector3(
            (self.minimum.x + self.maximum.x) / 2.0,
            (self.minimum.y + self.maximum.y) / 2.0,
            (self.minimum.z + self.maximum.z) / 2.0,
        )


@dataclass(slots=True, frozen=True)
class Transform3D:
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)


@dataclass(slots=True, frozen=True)
class SceneObject:
    id: str
    asset_id: str
    name: str
    transform: Transform3D = field(default_factory=Transform3D)
    visible: bool = True
    locked: bool = False
    color: str | None = None
    bounds: Bounds3D | None = None


@dataclass(slots=True, frozen=True)
class PlateRecord:
    id: str
    name: str
    order_index: int
    objects: tuple[SceneObject, ...] = ()
    size: tuple[float, float] = (256.0, 256.0)


@dataclass(slots=True, frozen=True)
class ProjectRecord:
    id: str
    name: str
    revision: int
    plates: tuple[PlateRecord, ...]
    created_at: str
    updated_at: str