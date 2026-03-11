from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillRequires:
    bins: list[str] | None = None
    env: list[str] | None = None
    config: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SkillRequires | None:
        if not data:
            return None
        return cls(
            bins=data.get("bins"),
            env=data.get("env"),
            config=data.get("config"),
        )


@dataclass
class SkillMetadata:
    name: str
    description: str
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] | None = None
    allowed_tools: list[str] | None = None
    disable_model_invocation: bool = False
    requires: SkillRequires | None = None

    def validate(self) -> None:
        errors: list[str] = []
        
        if not self.name:
            errors.append("name is required")
        elif len(self.name) > 64:
            errors.append("name must be 64 characters or less")
        elif not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", self.name):
            errors.append("name must contain only lowercase letters, numbers, and hyphens, and cannot start or end with hyphen")
        elif "--" in self.name:
            errors.append("name cannot contain consecutive hyphens")
        
        if not self.description:
            errors.append("description is required")
        elif len(self.description) > 1024:
            errors.append("description must be 1024 characters or less")
        
        if self.compatibility and len(self.compatibility) > 500:
            errors.append("compatibility must be 500 characters or less")
        
        if errors:
            raise ValueError(f"Skill metadata validation failed: {', '.join(errors)}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillMetadata:
        metadata_raw = data.get("metadata")
        if isinstance(metadata_raw, dict):
            metadata = {str(k): str(v) for k, v in metadata_raw.items()}
        else:
            metadata = None
        
        allowed_tools_raw = data.get("allowed-tools")
        if isinstance(allowed_tools_raw, str):
            allowed_tools = [t.strip() for t in allowed_tools_raw.split() if t.strip()]
        elif isinstance(allowed_tools_raw, list):
            allowed_tools = [str(t) for t in allowed_tools_raw]
        else:
            allowed_tools = None
        
        requires_raw = data.get("requires")
        if isinstance(requires_raw, dict):
            requires = SkillRequires.from_dict(requires_raw)
        else:
            requires = None
        
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            license=data.get("license"),
            compatibility=data.get("compatibility"),
            metadata=metadata,
            allowed_tools=allowed_tools,
            disable_model_invocation=data.get("disable-model-invocation", False),
            requires=requires,
        )


@dataclass
class SkillDiscovery:
    """Discovery 阶段：仅元数据"""
    name: str
    description: str
    path: Path
    metadata: SkillMetadata

    @property
    def disable_model_invocation(self) -> bool:
        return self.metadata.disable_model_invocation


@dataclass
class SkillActivated:
    """Activation 阶段：完整内容"""
    discovery: SkillDiscovery
    content: str

    @property
    def name(self) -> str:
        return self.discovery.name

    @property
    def description(self) -> str:
        return self.discovery.description

    @property
    def path(self) -> Path:
        return self.discovery.path

    @property
    def metadata(self) -> SkillMetadata:
        return self.discovery.metadata


@dataclass
class SkillExecuted:
    """Execution 阶段：包含资源"""
    activated: SkillActivated
    resources: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.activated.name

    @property
    def description(self) -> str:
        return self.activated.description

    @property
    def content(self) -> str:
        return self.activated.content

    @property
    def path(self) -> Path:
        return self.activated.path

    @property
    def metadata(self) -> SkillMetadata:
        return self.activated.metadata


@dataclass
class Skill:
    """Legacy Skill class for backward compatibility"""
    metadata: SkillMetadata
    content: str
    path: Path
    resources: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description
