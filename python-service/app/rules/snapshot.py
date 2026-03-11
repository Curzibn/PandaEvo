from __future__ import annotations

import time
from dataclasses import dataclass

from app.rules.discovery import discover_rules_with_priority
from app.rules.model import Rule

_SNAPSHOT_TTL = 60.0


@dataclass
class RuleSnapshot:
    rules: dict[str, Rule]
    expires_at: float


_cached: RuleSnapshot | None = None


def get_rule_snapshot() -> RuleSnapshot:
    """获取全局规则快照，TTL 过期后自动重建
    
    Returns:
        RuleSnapshot 对象
    """
    global _cached
    now = time.time()
    if _cached is None or now >= _cached.expires_at:
        rules = discover_rules_with_priority()
        _cached = RuleSnapshot(rules=rules, expires_at=now + _SNAPSHOT_TTL)
    return _cached


def invalidate_rule_snapshot() -> None:
    """强制使快照失效（规则文件变更时调用）"""
    global _cached
    _cached = None
