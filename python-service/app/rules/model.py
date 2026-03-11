from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RuleLevel(str, Enum):
    SYSTEM = "system"
    USER = "user"
    WORKSPACE = "workspace"


@dataclass
class RuleMetadata:
    description: str = ""
    always_apply: bool = False
    globs: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuleMetadata:
        globs_raw = data.get("globs")
        if isinstance(globs_raw, str):
            globs = [g.strip() for g in globs_raw.split(",") if g.strip()]
        elif isinstance(globs_raw, list):
            globs = [str(g) for g in globs_raw]
        else:
            globs = None
        return cls(
            description=data.get("description", ""),
            always_apply=bool(data.get("alwaysApply", False)),
            globs=globs,
        )


@dataclass
class Rule:
    name: str
    path: Path
    metadata: RuleMetadata
    content: str
    level: RuleLevel = field(default=RuleLevel.WORKSPACE)
