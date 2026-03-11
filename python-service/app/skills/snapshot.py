from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import _cfg  # noqa: SLF001
from app.skills.discovery import discover_skills_with_priority
from app.skills.gating import filter_eligible_skills
from app.skills.loader import activate_skill
from app.skills.model import SkillActivated, SkillDiscovery

_SNAPSHOT_TTL = 60.0


@dataclass
class SkillSnapshot:
    discovered: dict[str, SkillDiscovery]
    activated: dict[str, SkillActivated] = field(default_factory=dict)
    expires_at: float = field(default_factory=lambda: time.time() + _SNAPSHOT_TTL)
    file_timestamps: dict[str, float] = field(default_factory=dict)

    def _file_mtime(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    def update_file_timestamps(self) -> None:
        self.file_timestamps = {
            name: self._file_mtime(skill.path)
            for name, skill in self.discovered.items()
        }

    def has_changes(self) -> bool:
        for name, skill in self.discovered.items():
            if self._file_mtime(skill.path) != self.file_timestamps.get(name, 0.0):
                return True
        return False

    def activate_skill(self, name: str) -> SkillActivated | None:
        if name in self.activated:
            return self.activated[name]
        discovery = self.discovered.get(name)
        if not discovery:
            return None
        try:
            activated = activate_skill(discovery)
            self.activated[name] = activated
            return activated
        except Exception:
            return None


_cached: SkillSnapshot | None = None


def _build_snapshot() -> SkillSnapshot:
    now = time.time()
    discovered = discover_skills_with_priority()
    config = _cfg.get("skills", {})
    eligible = filter_eligible_skills(discovered, config)
    snapshot = SkillSnapshot(discovered=eligible, expires_at=now + _SNAPSHOT_TTL)
    snapshot.update_file_timestamps()
    return snapshot


def get_skill_snapshot() -> SkillSnapshot:
    global _cached
    now = time.time()
    if _cached is not None and now < _cached.expires_at and not _cached.has_changes():
        return _cached
    _cached = _build_snapshot()
    return _cached


def invalidate_skill_snapshot() -> None:
    global _cached
    _cached = None


def create_skill_snapshot() -> SkillSnapshot:
    return get_skill_snapshot()


def refresh_skill_snapshot() -> SkillSnapshot:
    invalidate_skill_snapshot()
    return get_skill_snapshot()
