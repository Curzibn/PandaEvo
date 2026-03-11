from __future__ import annotations

from pathlib import Path

from app.context.frontmatter import parse_frontmatter
from app.rules.model import Rule, RuleMetadata


def load_rule(path: Path) -> Rule | None:
    """加载单个规则文件，解析 frontmatter 和内容
    
    Args:
        path: 规则文件路径
    
    Returns:
        Rule 对象，如果加载失败则返回 None
    """
    try:
        frontmatter, content = parse_frontmatter(path)
        if not content.strip():
            return None
        name = path.stem
        metadata = RuleMetadata.from_dict(frontmatter)
        return Rule(name=name, path=path, metadata=metadata, content=content)
    except Exception:
        return None
