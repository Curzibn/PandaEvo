from __future__ import annotations

from app.skills.model import Skill, SkillActivated, SkillDiscovery


def format_skill_content(skill: Skill | SkillActivated) -> str:
    parts: list[str] = []

    parts.append(f"### {skill.name}")
    parts.append("")
    parts.append(skill.content)

    if isinstance(skill, Skill) and skill.resources:
        for resource_type, resource_files in skill.resources.items():
            if resource_files:
                parts.append("")
                parts.append(f"#### {resource_type.capitalize()}")
                for file_path, file_content in resource_files.items():
                    parts.append(f"**{file_path}:**")
                    parts.append("```")
                    parts.append(file_content)
                    parts.append("```")

    return "\n".join(parts)


def integrate_skills_discovery(base_prompt: str, skills: list[SkillDiscovery]) -> str:
    """集成技能发现阶段（仅元数据列表）"""
    if not skills:
        return base_prompt
    
    skill_items: list[str] = []
    for skill in skills:
        skill_items.append(f'  <skill name="{skill.name}" description="{skill.description}"/>')
    
    skills_xml = "\n".join(skill_items)
    
    return f"""{base_prompt}

## 可用技能

以下技能可用于辅助完成任务：

<skills>
{skills_xml}
</skills>

技能会在需要时自动激活。你也可以通过输入 `/技能名称` 手动激活特定技能。"""


def integrate_skill_content(base_prompt: str, skill: SkillActivated) -> str:
    """集成单个技能的完整内容"""
    skill_content = format_skill_content(skill)
    
    return f"""{base_prompt}

## 激活的技能：{skill.name}

{skill_content}"""


def integrate_skills(base_prompt: str, skills: list[Skill | SkillActivated]) -> str:
    """集成技能（支持旧版 Skill 和新版 SkillActivated）"""
    if not skills:
        return base_prompt

    skill_sections: list[str] = []
    for skill in skills:
        skill_sections.append(format_skill_content(skill))

    if skill_sections:
        skills_text = "\n\n".join(skill_sections)
        return f"""{base_prompt}

## 可用技能（工作指导）

以下技能是**工作方法和指导原则**，不是可调用的工具。它们告诉你**如何完成任务**，而不是**可以调用什么**。请按照技能中的步骤和策略来执行任务：

{skills_text}

**重要区分**：
- **技能（SKILL）**：指导性的工作方法，告诉你如何完成任务，**不能直接调用**
- **工具（Tools）**：可执行的函数，可以通过 function calling 机制直接调用

当技能中提到某个工具时（如 `web_fetch`、`mcp_user-bisheng_read_url`），请使用"可用工具"部分列出的对应工具名称来调用。"""

    return base_prompt
