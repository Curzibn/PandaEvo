from __future__ import annotations

from pathlib import Path
from typing import Any

from app.context.frontmatter import parse_frontmatter, parse_frontmatter_str
from app.skills.model import (
    Skill,
    SkillActivated,
    SkillDiscovery,
    SkillExecuted,
    SkillMetadata,
)


def load_skill_resources(skill_dir: Path, resource_paths: list[str] | None = None) -> dict[str, Any]:
    resources: dict[str, Any] = {}
    
    resource_dirs = ["scripts", "references", "assets"]
    for resource_dir_name in resource_dirs:
        resource_dir = skill_dir / resource_dir_name
        if not resource_dir.exists() or not resource_dir.is_dir():
            continue
        
        resources[resource_dir_name] = {}
        for resource_file in resource_dir.rglob("*"):
            if not resource_file.is_file():
                continue
            
            rel_path = str(resource_file.relative_to(resource_dir))
            
            if resource_paths is not None:
                if rel_path not in resource_paths:
                    continue
            
            try:
                if resource_file.suffix in [".md", ".txt", ".py", ".sh", ".json", ".yaml", ".yml"]:
                    content = resource_file.read_text(encoding="utf-8", errors="replace")
                    resources[resource_dir_name][rel_path] = content
                else:
                    resources[resource_dir_name][rel_path] = f"[Binary file: {rel_path}]"
            except OSError:
                resources[resource_dir_name][rel_path] = f"[Error reading: {rel_path}]"
    
    return resources


def discover_skill(path: Path) -> SkillDiscovery | None:
    if not path.exists() or not path.is_file():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        frontmatter, _ = parse_frontmatter_str(content)
        if not frontmatter:
            return None

        metadata = SkillMetadata.from_dict(frontmatter)
        if not metadata.name or not metadata.description:
            return None

        try:
            metadata.validate()
        except ValueError:
            return None

        return SkillDiscovery(
            name=metadata.name,
            description=metadata.description,
            path=path,
            metadata=metadata,
        )
    except Exception:
        return None


def activate_skill(discovery: SkillDiscovery) -> SkillActivated:
    try:
        _, content = parse_frontmatter(discovery.path)
        return SkillActivated(
            discovery=discovery,
            content=content,
        )
    except Exception:
        raise ValueError(f"Failed to activate skill: {discovery.name}")


def execute_skill(
    activated: SkillActivated,
    resource_paths: list[str] | None = None,
) -> SkillExecuted:
    skill_dir = activated.path.parent
    resources = load_skill_resources(skill_dir, resource_paths)
    return SkillExecuted(
        activated=activated,
        resources=resources,
    )


def load_skill(path: Path) -> Skill | None:
    if not path.exists() or not path.is_file():
        return None

    try:
        discovery = discover_skill(path)
        if not discovery:
            return None
        
        activated = activate_skill(discovery)
        executed = execute_skill(activated)
        
        return Skill(
            metadata=executed.metadata,
            content=executed.content,
            path=executed.path,
            resources=executed.resources,
        )
    except Exception:
        return None
