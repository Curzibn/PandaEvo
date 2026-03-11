from __future__ import annotations

import os
import shutil
from typing import Any

from app.skills.model import SkillDiscovery


def check_binary_exists(bin_name: str) -> bool:
    """检查二进制文件是否在 PATH 中"""
    return shutil.which(bin_name) is not None


def check_environment_variable_exists(var_name: str, config: dict[str, Any] | None = None) -> bool:
    """检查环境变量是否存在
    
    Args:
        var_name: 环境变量名
        config: 配置字典，可能包含 env 覆盖
    """
    if config:
        env_overrides = config.get("env", {})
        if isinstance(env_overrides, dict) and var_name in env_overrides:
            return True
    
    return var_name in os.environ


def check_config_value(path: str, config: dict[str, Any]) -> bool:
    """检查配置路径的值是否为真值
    
    Args:
        path: 配置路径，使用点号分隔，如 "skills.entries.my-skill.enabled"
        config: 配置字典
    """
    parts = path.split(".")
    current = config
    
    for part in parts:
        if not isinstance(current, dict):
            return False
        current = current.get(part)
        if current is None:
            return False
    
    return bool(current)


def check_skill_eligible(
    skill: SkillDiscovery,
    config: dict[str, Any] | None = None,
) -> bool:
    """检查技能是否满足门控条件
    
    Args:
        skill: 技能发现对象
        config: 配置字典，用于检查 env 和 config 要求
    
    Returns:
        如果技能满足所有门控条件，返回 True；否则返回 False
    """
    if not skill.metadata.requires:
        return True
    
    requires = skill.metadata.requires
    
    if requires.bins:
        for bin_name in requires.bins:
            if not check_binary_exists(bin_name):
                return False
    
    if requires.env:
        for var_name in requires.env:
            if not check_environment_variable_exists(var_name, config):
                return False
    
    if requires.config and config:
        for config_path in requires.config:
            if not check_config_value(config_path, config):
                return False
    
    return True


def filter_eligible_skills(
    skills: dict[str, SkillDiscovery],
    config: dict[str, Any] | None = None,
) -> dict[str, SkillDiscovery]:
    """过滤出满足门控条件的技能
    
    Args:
        skills: 技能发现字典
        config: 配置字典
    
    Returns:
        满足门控条件的技能字典
    """
    return {
        name: skill
        for name, skill in skills.items()
        if check_skill_eligible(skill, config)
    }
