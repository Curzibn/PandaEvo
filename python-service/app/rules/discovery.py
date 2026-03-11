from __future__ import annotations

from pathlib import Path

from app.config import get_service_data_dir, get_workspace_root
from app.rules.loader import load_rule
from app.rules.model import Rule, RuleLevel

_WORKSPACE_SUBDIRS = [".agents/rules", ".cursor/rules", ".claude/rules", ".codex/rules"]
_USER_SUBDIRS = [".pandaevo/rules", ".cursor/rules", ".claude/rules", ".codex/rules"]
_SYSTEM_SUBDIRS = ["rules"]


def _discover_level(subdirs: list[str], root: Path, level: RuleLevel) -> dict[str, Rule]:
    discovered: dict[str, tuple[Rule, int]] = {}

    for priority, subdir in enumerate(subdirs):
        directory = root / subdir
        if not directory.exists() or not directory.is_dir():
            continue

        for rule_file in directory.iterdir():
            if not rule_file.is_file() or rule_file.suffix not in {".mdc", ".md"}:
                continue

            rule = load_rule(rule_file)
            if not rule:
                continue

            rule.level = level
            name = rule.name.lower()

            if name not in discovered or priority < discovered[name][1]:
                discovered[name] = (rule, priority)

    return {name: rule for name, (rule, _) in discovered.items()}


def discover_rules_with_priority() -> dict[str, Rule]:
    workspace = get_workspace_root()
    data_dir = get_service_data_dir()
    user_home = Path.home()

    system_rules = _discover_level(_SYSTEM_SUBDIRS, data_dir, RuleLevel.SYSTEM)
    user_rules = _discover_level(_USER_SUBDIRS, user_home, RuleLevel.USER)
    workspace_rules = _discover_level(_WORKSPACE_SUBDIRS, workspace, RuleLevel.WORKSPACE)

    return {**system_rules, **user_rules, **workspace_rules}
