from __future__ import annotations

import fnmatch
import re

from app.config import get_rules_auto_match
from app.rules.model import Rule


def _extract_manual_rule(user_input: str) -> str | None:
    """从用户输入中提取 /rule-name 语法的规则名
    
    Args:
        user_input: 用户输入字符串
    
    Returns:
        规则名称（小写），如果未找到则返回 None
    """
    match = re.search(r"/rule-(\w+(?:-\w+)*)", user_input)
    if match:
        return match.group(1).lower()
    
    match = re.search(r"/(\w+(?:-\w+)*)", user_input)
    if match:
        potential_name = match.group(1).lower()
        if potential_name.startswith("rule"):
            return potential_name[4:] if potential_name.startswith("rule-") else potential_name
    return None


def _match_by_globs(rule: Rule, file_paths: list[str]) -> bool:
    """使用 fnmatch 匹配文件路径，支持 ** 递归模式
    
    Args:
        rule: 规则对象
        file_paths: 文件路径列表
    
    Returns:
        如果任一文件路径匹配任一 glob 模式，返回 True
    """
    if not rule.metadata.globs or not file_paths:
        return False
    
    for pattern in rule.metadata.globs:
        for fp in file_paths:
            if _match_glob_pattern(pattern, fp):
                return True
    
    return False


def _match_glob_pattern(pattern: str, file_path: str) -> bool:
    """匹配单个 glob 模式与文件路径，支持 ** 递归
    
    Args:
        pattern: glob 模式（如 "**/*.py", "src/**/*.ts"）
        file_path: 文件路径（相对路径）
    
    Returns:
        如果匹配返回 True
    """
    if "**" not in pattern:
        return fnmatch.fnmatch(file_path, pattern)
    
    pattern_parts = pattern.split("/")
    path_parts = file_path.split("/")
    
    pattern_idx = 0
    path_idx = 0
    
    while pattern_idx < len(pattern_parts) and path_idx < len(path_parts):
        part = pattern_parts[pattern_idx]
        
        if part == "**":
            pattern_idx += 1
            if pattern_idx >= len(pattern_parts):
                return True
            
            next_part = pattern_parts[pattern_idx]
            while path_idx < len(path_parts):
                if fnmatch.fnmatch(path_parts[path_idx], next_part):
                    pattern_idx += 1
                    path_idx += 1
                    break
                path_idx += 1
            else:
                return False
        else:
            if not fnmatch.fnmatch(path_parts[path_idx], part):
                return False
            pattern_idx += 1
            path_idx += 1
    
    return pattern_idx >= len(pattern_parts) and path_idx >= len(path_parts)


def _match_by_keywords(rule: Rule, user_input: str) -> bool:
    """关键词匹配：description 与 user_input 有词汇重叠且超过阈值
    
    Args:
        rule: 规则对象
        user_input: 用户输入字符串
    
    Returns:
        如果匹配成功返回 True
    """
    if not rule.metadata.description or not user_input:
        return False
    
    desc_lower = rule.metadata.description.lower()
    input_lower = user_input.lower()
    
    desc_words = set(desc_lower.split())
    input_words = set(input_lower.split())
    
    overlap = len(desc_words & input_words)
    if overlap >= 2:
        return True
    
    for word in input_words:
        if len(word) > 4 and word in desc_lower:
            return True
    
    return False


def match_rules(
    all_rules: dict[str, Rule],
    user_input: str | None = None,
    accessed_files: list[str] | None = None,
    manual_rule_name: str | None = None,
) -> list[Rule]:
    """按优先级顺序匹配规则：
    
    1. Always Apply（alwaysApply: true）
    2. 手动触发（/rule-name）
    3. 文件匹配（globs）
    4. 关键词匹配（description 与 user_input 词汇重叠）
    
    同一条规则不重复添加（已收录的跳过）。
    
    Args:
        all_rules: 所有发现的规则字典
        user_input: 用户输入（用于关键词匹配和手动触发提取）
        accessed_files: 访问的文件路径列表（用于 globs 匹配）
        manual_rule_name: 手动指定的规则名称（如果已提取）
    
    Returns:
        匹配的规则列表，按优先级排序
    """
    matched: list[Rule] = []
    matched_names: set[str] = set()
    
    if manual_rule_name is None and user_input:
        manual_rule_name = _extract_manual_rule(user_input)
    
    for name, rule in all_rules.items():
        if name in matched_names:
            continue
        
        if rule.metadata.always_apply:
            matched.append(rule)
            matched_names.add(name)
            continue
        
        if manual_rule_name and name == manual_rule_name.lower():
            matched.append(rule)
            matched_names.add(name)
            continue
        
        if accessed_files and _match_by_globs(rule, accessed_files):
            matched.append(rule)
            matched_names.add(name)
            continue
        
        if user_input and get_rules_auto_match() and _match_by_keywords(rule, user_input):
            matched.append(rule)
            matched_names.add(name)
            continue
    
    return matched
