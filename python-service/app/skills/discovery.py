from __future__ import annotations

from pathlib import Path

from app.config import get_service_data_dir, get_workspace_root
from app.skills.loader import discover_skill
from app.skills.model import SkillDiscovery


def get_user_home_skills_dir() -> Path:
    """获取用户主目录下的技能目录"""
    return Path.home() / ".cursor" / "skills"


def get_skill_directories() -> list[tuple[Path, int]]:
    """获取技能目录列表，返回 (路径, 优先级) 元组列表
    
    优先级从高到低：
    1. workspace/.agents/skills (优先级 1)
    2. workspace/.cursor/skills (优先级 2)
    3. workspace/.claude/skills (优先级 3)
    4. workspace/.codex/skills (优先级 4)
    5. ~/.cursor/skills (优先级 5)
    6. ~/.claude/skills (优先级 6)
    7. ~/.codex/skills (优先级 7)
    8. data_dir/skills (优先级 8)
    """
    workspace = get_workspace_root()
    data_dir = get_service_data_dir()
    user_home = Path.home()

    directories: list[tuple[Path, int]] = [
        (workspace / ".agents" / "skills", 1),
        (workspace / ".cursor" / "skills", 2),
        (workspace / ".claude" / "skills", 3),
        (workspace / ".codex" / "skills", 4),
        (user_home / ".cursor" / "skills", 5),
        (user_home / ".claude" / "skills", 6),
        (user_home / ".codex" / "skills", 7),
        (data_dir / "skills", 8),
    ]

    return [(d, priority) for d, priority in directories if d.exists() and d.is_dir()]


def discover_skills() -> list[Path]:
    """Legacy function: 返回所有技能文件路径列表（不按优先级去重）"""
    skill_paths: list[Path] = []

    for directory, _ in get_skill_directories():
        for skill_dir in directory.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists() and skill_file.is_file():
                skill_paths.append(skill_file)

    return skill_paths


def discover_skills_with_priority() -> dict[str, SkillDiscovery]:
    """发现所有技能，按优先级去重，返回 name -> SkillDiscovery 映射
    
    如果同名技能出现在多个目录中，只保留优先级最高的（优先级数字越小越高）。
    """
    discovered: dict[str, tuple[SkillDiscovery, int]] = {}

    for directory, priority in get_skill_directories():
        for skill_dir in directory.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists() or not skill_file.is_file():
                continue

            discovery = discover_skill(skill_file)
            if not discovery:
                continue

            name = discovery.name.lower()
            if name not in discovered:
                discovered[name] = (discovery, priority)
            else:
                existing_discovery, existing_priority = discovered[name]
                if priority < existing_priority:
                    discovered[name] = (discovery, priority)

    return {name: discovery for name, (discovery, _) in discovered.items()}
