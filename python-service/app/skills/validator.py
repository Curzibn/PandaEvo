from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.skills.loader import parse_skill_file
from app.skills.model import SkillMetadata


def validate_skill(path: Path) -> tuple[bool, list[str]]:
    """验证技能文件，返回 (是否有效, 错误列表)
    
    Args:
        path: SKILL.md 文件路径
    
    Returns:
        (是否有效, 错误列表)
    """
    errors: list[str] = []
    
    if not path.exists():
        return False, [f"File does not exist: {path}"]
    
    if not path.is_file():
        return False, [f"Path is not a file: {path}"]
    
    if path.name != "SKILL.md":
        return False, [f"File must be named SKILL.md, got: {path.name}"]
    
    skill_dir = path.parent
    if not skill_dir.is_dir():
        return False, [f"Parent directory does not exist: {skill_dir}"]
    
    try:
        frontmatter, content = parse_skill_file(path)
    except Exception as e:
        return False, [f"Failed to parse skill file: {e}"]
    
    if not frontmatter:
        errors.append("Missing YAML frontmatter")
    
    if "name" not in frontmatter:
        errors.append("Missing required field: name")
    elif not isinstance(frontmatter["name"], str):
        errors.append("Field 'name' must be a string")
    
    if "description" not in frontmatter:
        errors.append("Missing required field: description")
    elif not isinstance(frontmatter["description"], str):
        errors.append("Field 'description' must be a string")
    
    if not content or not content.strip():
        errors.append("Skill content is empty")
    
    try:
        metadata = SkillMetadata.from_dict(frontmatter)
        metadata.validate()
    except ValueError as e:
        errors.append(f"Metadata validation failed: {e}")
    except Exception as e:
        errors.append(f"Failed to create metadata: {e}")
    
    if errors:
        return False, errors
    
    return True, []


def validate_skill_directory(skill_dir: Path) -> tuple[bool, list[str]]:
    """验证技能目录结构
    
    Args:
        skill_dir: 技能目录路径
    
    Returns:
        (是否有效, 错误列表)
    """
    errors: list[str] = []
    
    if not skill_dir.exists():
        return False, [f"Directory does not exist: {skill_dir}"]
    
    if not skill_dir.is_dir():
        return False, [f"Path is not a directory: {skill_dir}"]
    
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        errors.append("Missing SKILL.md file")
    else:
        is_valid, file_errors = validate_skill(skill_file)
        if not is_valid:
            errors.extend(file_errors)
    
    valid_resource_dirs = {"scripts", "references", "assets"}
    for item in skill_dir.iterdir():
        if item.is_dir() and item.name not in valid_resource_dirs:
            errors.append(f"Unexpected directory: {item.name} (allowed: {', '.join(valid_resource_dirs)})")
    
    if errors:
        return False, errors
    
    return True, []
