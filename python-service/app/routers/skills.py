from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import (
    _cfg,  # noqa: SLF001
    get_all_skill_configs,
    get_skill_config,
    get_service_data_dir,
    get_workspace_root,
)
from app.skills.discovery import discover_skills_with_priority
from app.skills.gating import check_skill_eligible, filter_eligible_skills
from app.skills.loader import activate_skill, execute_skill

router = APIRouter(prefix="/skills", tags=["skills"])


def _determine_source(path: Path, workspace: Path, data_dir: Path) -> Literal["workspace", "user", "data_dir"]:
    """判断技能来源"""
    path_str = str(path)
    workspace_str = str(workspace)
    data_dir_str = str(data_dir)
    user_home_str = str(Path.home())
    
    if workspace_str in path_str:
        return "workspace"
    elif user_home_str in path_str:
        return "user"
    elif data_dir_str in path_str:
        return "data_dir"
    else:
        return "workspace"


class SkillRequiresOut(BaseModel):
    bins: list[str] | None = None
    env: list[str] | None = None
    config: list[str] | None = None


class SkillInfo(BaseModel):
    name: str
    description: str
    license: str | None = None
    compatibility: str | None = None
    source: Literal["workspace", "user", "data_dir"]
    priority: int
    path: str
    eligible: bool
    enabled: bool
    disable_model_invocation: bool
    requires: SkillRequiresOut | None = None
    metadata: dict[str, str] | None = None


class SkillDetail(SkillInfo):
    content: str
    resources: dict[str, Any] | None = None
    env: dict[str, str] | None = None
    api_key: str | None = None
    config: dict[str, Any] | None = None


class SkillConfigUpdate(BaseModel):
    enabled: bool | None = None
    env: dict[str, str] | None = None
    api_key: str | None = None
    config: dict[str, Any] | None = None


class SkillsConfigOut(BaseModel):
    enabled: bool
    auto_match: bool
    max_skills: int


@router.get("", response_model=list[SkillInfo])
async def list_skills() -> list[SkillInfo]:
    """获取所有发现的技能列表（只返回配置文件中配置的技能）"""
    workspace = get_workspace_root()
    data_dir = get_service_data_dir()
    discovered = discover_skills_with_priority()
    
    config = _cfg.get("skills", {})
    eligible_skills = filter_eligible_skills(discovered, config)
    all_configs = get_all_skill_configs()
    
    configured_skill_names = set(all_configs.keys())
    
    result: list[SkillInfo] = []
    for name, skill in discovered.items():
        if name not in configured_skill_names:
            continue
        
        skill_config = all_configs.get(name)
        enabled = skill_config.enabled if skill_config else True
        
        requires_out = None
        if skill.metadata.requires:
            requires_out = SkillRequiresOut(
                bins=skill.metadata.requires.bins,
                env=skill.metadata.requires.env,
                config=skill.metadata.requires.config,
            )
        
        source = _determine_source(skill.path, workspace, data_dir)
        
        priority_map: dict[Path, int] = {}
        for dir_path, priority in _get_skill_directories_with_priority():
            priority_map[dir_path] = priority
        
        skill_dir = skill.path.parent
        priority = 999
        for dir_path, dir_priority in priority_map.items():
            try:
                if skill_dir.is_relative_to(dir_path):
                    priority = dir_priority
                    break
            except ValueError:
                continue
        
        eligible = check_skill_eligible(skill, config)
        
        result.append(
            SkillInfo(
                name=skill.name,
                description=skill.description,
                license=skill.metadata.license,
                compatibility=skill.metadata.compatibility,
                source=source,
                priority=priority,
                path=str(skill.path),
                eligible=eligible,
                enabled=enabled,
                disable_model_invocation=skill.metadata.disable_model_invocation,
                requires=requires_out,
                metadata=skill.metadata.metadata,
            )
        )
    
    return sorted(result, key=lambda x: (x.priority, x.name))


def _get_skill_directories_with_priority() -> list[tuple[Path, int]]:
    """获取技能目录列表（带优先级）"""
    from app.skills.discovery import get_skill_directories
    return get_skill_directories()


@router.get("/{name}", response_model=SkillDetail)
async def get_skill(name: str) -> SkillDetail:
    """获取单个技能的详细信息（只返回配置文件中配置的技能）"""
    discovered = discover_skills_with_priority()
    skill_discovery = discovered.get(name.lower())
    
    if not skill_discovery:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    
    all_configs = get_all_skill_configs()
    if name.lower() not in all_configs:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' is not configured and cannot be accessed via API")
    
    try:
        activated = activate_skill(skill_discovery)
        executed = execute_skill(activated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load skill: {str(e)}")
    
    workspace = get_workspace_root()
    data_dir = get_service_data_dir()
    source = _determine_source(skill_discovery.path, workspace, data_dir)
    
    priority_map: dict[Path, int] = {}
    for dir_path, priority in _get_skill_directories_with_priority():
        priority_map[dir_path] = priority
    
    skill_dir = skill_discovery.path.parent
    priority = 999
    for dir_path, dir_priority in priority_map.items():
        try:
            if skill_dir.is_relative_to(dir_path):
                priority = dir_priority
                break
        except ValueError:
            continue
    
    config = _cfg.get("skills", {})
    eligible = check_skill_eligible(skill_discovery, config)
    all_configs = get_all_skill_configs()
    skill_config = all_configs.get(name.lower())
    enabled = skill_config.enabled if skill_config else True
    
    requires_out = None
    if skill_discovery.metadata.requires:
        requires_out = SkillRequiresOut(
            bins=skill_discovery.metadata.requires.bins,
            env=skill_discovery.metadata.requires.env,
            config=skill_discovery.metadata.requires.config,
        )
    
    env_config = skill_config.env if skill_config else None
    api_key_config = skill_config.api_key if skill_config else None
    custom_config = skill_config.config if skill_config else None
    
    detail = SkillDetail(
        name=skill_discovery.name,
        description=skill_discovery.description,
        license=skill_discovery.metadata.license,
        compatibility=skill_discovery.metadata.compatibility,
        source=source,
        priority=priority,
        path=str(skill_discovery.path),
        eligible=eligible,
        enabled=enabled,
        disable_model_invocation=skill_discovery.metadata.disable_model_invocation,
        requires=requires_out,
        metadata=skill_discovery.metadata.metadata,
        content=executed.content,
        resources=executed.resources if executed.resources else None,
    )
    
    detail_dict = detail.model_dump()
    if env_config:
        detail_dict["env"] = env_config
    if api_key_config:
        detail_dict["api_key"] = api_key_config
    if custom_config:
        detail_dict["config"] = custom_config
    
    return SkillDetail(**detail_dict)


@router.put("/{name}/config", status_code=204)
async def update_skill_config(name: str, body: SkillConfigUpdate) -> None:
    """更新技能的配置"""
    discovered = discover_skills_with_priority()
    if name.lower() not in discovered:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    
    import yaml
    from pathlib import Path
    
    config_dev_path = Path(__file__).parent.parent / "config-dev.yaml"
    config_data = {}
    if config_dev_path.exists():
        with config_dev_path.open(encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
    
    if "skills" not in config_data:
        config_data["skills"] = {}
    if "entries" not in config_data["skills"]:
        config_data["skills"]["entries"] = {}
    
    skill_name_lower = name.lower()
    if skill_name_lower not in config_data["skills"]["entries"]:
        config_data["skills"]["entries"][skill_name_lower] = {}
    
    entry = config_data["skills"]["entries"][skill_name_lower]
    
    if body.enabled is not None:
        entry["enabled"] = body.enabled
    if body.env is not None:
        entry["env"] = body.env
    if body.api_key is not None:
        entry["api_key"] = body.api_key
    if body.config is not None:
        entry["config"] = body.config
    
    with config_dev_path.open("w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


@router.get("/config", response_model=SkillsConfigOut)
async def get_skills_config() -> SkillsConfigOut:
    """获取全局技能配置"""
    skills_config = _cfg.get("skills", {})
    return SkillsConfigOut(
        enabled=skills_config.get("enabled", True),
        auto_match=skills_config.get("auto_match", True),
        max_skills=skills_config.get("max_skills", 3),
    )
