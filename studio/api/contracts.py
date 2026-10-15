from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class ApiError:
    code: str
    message: str
    details: dict[str, Any] | None = None


@dataclass(slots=True, frozen=True)
class ApiResponse:
    data: Any = None
    error: ApiError | None = None
    request_id: str | None = None
    version: str = "v1"
