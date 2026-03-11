from __future__ import annotations

import re
from typing import Any

from app.skills.discovery import discover_skills_with_priority
from app.skills.model import Skill, SkillDiscovery


def _extract_manual_skill(user_input: str) -> str | None:
    match = re.search(r"/(\w+(?:-\w+)*)", user_input)
    if match:
        return match.group(1)
    return None


def _keyword_match(user_input: str, skill: Skill | SkillDiscovery) -> float:
    user_lower = user_input.lower()
    desc_lower = skill.description.lower()
    name_lower = skill.name.lower()

    score = 0.0

    if name_lower in user_lower:
        score += 2.0

    desc_words = set(desc_lower.split())
    user_words = set(user_lower.split())
    common_words = desc_words & user_words
    if common_words:
        score += len(common_words) * 0.5

    if any(word in desc_lower for word in user_words if len(word) > 3):
        score += 1.0

    return score


def match_skills(
    user_input: str,
    all_skills: dict[str, SkillDiscovery] | None = None,
    auto_match: bool = True,
    max_skills: int = 3,
) -> list[SkillDiscovery]:
    """匹配技能
    
    Args:
        user_input: 用户输入
        all_skills: 技能发现字典，如果为 None 则自动发现
        auto_match: 是否自动匹配
        max_skills: 最大匹配数量
    
    Returns:
        匹配的技能发现列表
    """
    if all_skills is None:
        all_skills = discover_skills_with_priority()

    manual_skill_name = _extract_manual_skill(user_input)
    if manual_skill_name:
        normalized_name = manual_skill_name.lower()
        for name, skill in all_skills.items():
            if name == normalized_name or name.replace("_", "-") == normalized_name:
                return [skill]

    if not auto_match:
        return []

    scored_skills: list[tuple[SkillDiscovery, float]] = []
    for skill in all_skills.values():
        score = _keyword_match(user_input, skill)
        if score > 0:
            scored_skills.append((skill, score))

    scored_skills.sort(key=lambda x: x[1], reverse=True)
    return [skill for skill, _ in scored_skills[:max_skills]]


def match_skills_legacy(
    user_input: str,
    all_skills: list[Skill] | None = None,
    auto_match: bool = True,
    max_skills: int = 3,
) -> list[Skill]:
    """Legacy function for backward compatibility"""
    if all_skills is None:
        from app.skills.discovery import discover_skills
        from app.skills.loader import load_skill
        skill_paths = discover_skills()
        all_skills = []
        for path in skill_paths:
            skill = load_skill(path)
            if skill:
                all_skills.append(skill)

    manual_skill_name = _extract_manual_skill(user_input)
    if manual_skill_name:
        for skill in all_skills:
            if skill.name.lower() == manual_skill_name.lower() or skill.name.lower().replace("_", "-") == manual_skill_name.lower():
                return [skill]

    if not auto_match:
        return []

    scored_skills: list[tuple[Skill, float]] = []
    for skill in all_skills:
        score = _keyword_match(user_input, skill)
        if score > 0:
            scored_skills.append((skill, score))

    scored_skills.sort(key=lambda x: x[1], reverse=True)
    return [skill for skill, _ in scored_skills[:max_skills]]
