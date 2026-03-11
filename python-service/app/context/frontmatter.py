from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def parse_frontmatter_str(content: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER_RE.match(content)
    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            frontmatter = {}
        return frontmatter, match.group(2).strip()
    return {}, content.strip()


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    return parse_frontmatter_str(path.read_text(encoding="utf-8"))
