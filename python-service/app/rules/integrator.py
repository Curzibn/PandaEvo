from __future__ import annotations

from app.rules.model import Rule

_SHOW_LEVEL_LABEL = False


def integrate_rules(base_prompt: str, rules: list[Rule]) -> str:
    if not rules:
        return base_prompt

    sections = [_format_rule(rule) for rule in rules]
    rules_text = "\n\n".join(sections)

    return f"""{base_prompt}

## 项目规则和约束

以下规则定义了项目的编码规范、架构原则和行为约束，请始终遵循：

{rules_text}"""


def _format_rule(rule: Rule) -> str:
    if _SHOW_LEVEL_LABEL:
        return f"### {rule.name} `[{rule.level.value}]`\n\n{rule.content}"
    return f"### {rule.name}\n\n{rule.content}"
