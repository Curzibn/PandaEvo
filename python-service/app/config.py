from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


_ROOT = Path(__file__).parent.parent
_cfg: dict[str, Any] = _merge(
    _load_yaml(_ROOT / "config.yaml"),
    _load_yaml(_ROOT / "config-dev.yaml"),
)


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL") or _cfg["database"]["url"]


def get_workspace_root() -> Path:
    raw: str = _cfg.get("workspace", {}).get("root", "")
    if raw:
        return Path(raw).resolve()
    return Path.cwd()


def get_web_fs_root() -> Path:
    raw: str = os.environ.get("WEB_FS_ROOT", "") or _cfg.get("workspace", {}).get("web_fs_root", "")
    if raw:
        return Path(raw).resolve()
    return Path("/apps/workspace").resolve()


def get_service_data_dir() -> Path:
    raw: str = _cfg.get("service", {}).get("data_dir", "")
    if raw:
        return Path(raw).resolve()
    return Path.home() / ".pandaevo"


def get_env() -> str:
    return _cfg.get("env", "prod")


@dataclass
class MCPServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None

    @property
    def transport(self) -> str:
        return "http" if self.url else "stdio"


@dataclass
class MCPBuiltinConfig:
    enabled: bool = True
    disabled: list[str] = field(default_factory=list)


def load_mcp_builtin_config() -> MCPBuiltinConfig:
    block = _cfg.get("mcp", {}).get("builtin", {})
    if not isinstance(block, dict):
        return MCPBuiltinConfig()
    return MCPBuiltinConfig(
        enabled=bool(block.get("enabled", True)),
        disabled=[s for s in block.get("disabled", []) if isinstance(s, str)],
    )


def _parse_mcp_server(s: dict) -> MCPServerConfig | None:
    name = s.get("name", "").strip()
    if not name:
        return None

    url = s.get("url") or None
    command = s.get("command") or None

    if url:
        headers = s.get("headers")
        if headers is not None and not isinstance(headers, dict):
            headers = None
        return MCPServerConfig(name=name, url=str(url), headers=headers)

    if not command or not isinstance(command, str):
        return None

    args = s.get("args", [])
    if not isinstance(args, list):
        args = []

    env = s.get("env")
    if env is not None and not isinstance(env, dict):
        env = None

    return MCPServerConfig(name=name, command=command, args=args, env=env)


def load_mcp_servers() -> list[MCPServerConfig]:
    servers = []
    for s in _cfg.get("mcp", {}).get("servers", []):
        if not isinstance(s, dict):
            continue
        cfg = _parse_mcp_server(s)
        if cfg:
            servers.append(cfg)
    return servers


def get_skills_enabled() -> bool:
    return _cfg.get("skills", {}).get("enabled", True)


def get_skills_auto_match() -> bool:
    return _cfg.get("skills", {}).get("auto_match", True)


def get_skills_max_skills() -> int:
    return _cfg.get("skills", {}).get("max_skills", 3)


@dataclass
class SkillEntryConfig:
    enabled: bool = True
    env: dict[str, str] | None = None
    api_key: str | None = None
    config: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SkillEntryConfig:
        if not data:
            return cls()
        return cls(
            enabled=data.get("enabled", True),
            env=data.get("env"),
            api_key=data.get("api_key"),
            config=data.get("config"),
        )


def get_skill_config(skill_name: str) -> SkillEntryConfig | None:
    """获取特定技能的配置"""
    entries = _cfg.get("skills", {}).get("entries", {})
    if not isinstance(entries, dict):
        return None
    entry_data = entries.get(skill_name)
    if entry_data is None:
        return None
    return SkillEntryConfig.from_dict(entry_data)


def get_all_skill_configs() -> dict[str, SkillEntryConfig]:
    """获取所有技能的配置"""
    entries = _cfg.get("skills", {}).get("entries", {})
    if not isinstance(entries, dict):
        return {}
    return {
        name: SkillEntryConfig.from_dict(data)
        for name, data in entries.items()
        if isinstance(data, dict)
    }


def get_rules_enabled() -> bool:
    return _cfg.get("rules", {}).get("enabled", True)


def get_rules_auto_match() -> bool:
    return _cfg.get("rules", {}).get("auto_match", True)


def get_evolution_core_url() -> str:
    return _cfg.get("evolution_core", {}).get("url", "")


def get_gitea_url() -> str:
    return os.environ.get("GITEA_URL") or _cfg.get("gitea", {}).get("url", "http://gitea:3000")


def get_gitea_token() -> str:
    return os.environ.get("GITEA_TOKEN", "")


def get_gitea_org() -> str:
    return os.environ.get("GITEA_ORG") or _cfg.get("gitea", {}).get("org", "pandaevo")


def get_repo_sync_enabled() -> bool:
    return bool(_cfg.get("repo_sync", {}).get("enabled", True))


def get_repo_sync_root() -> Path:
    raw: str = os.environ.get("REPO_SYNC_ROOT", "") or _cfg.get("repo_sync", {}).get("root", "")
    if raw:
        return Path(raw).resolve()
    return Path("/apps/repos").resolve()


def get_repo_sync_repos() -> list[str]:
    repos = _cfg.get("repo_sync", {}).get("repos", ["python-service", "web-pc"])
    if not isinstance(repos, list):
        return ["python-service", "web-pc"]
    clean = [str(repo).strip() for repo in repos if str(repo).strip()]
    return clean or ["python-service", "web-pc"]


def get_repo_sync_branch() -> str:
    return str(_cfg.get("repo_sync", {}).get("branch", "main") or "main").strip() or "main"


def get_enforce_code_tasks_via_orchestrator() -> bool:
    return bool(_cfg.get("orchestrator", {}).get("enforce_code_tasks_via_orchestrator", False))


def get_auto_trigger_evolution_after_pr() -> bool:
    return bool(_cfg.get("orchestrator", {}).get("auto_trigger_evolution_after_pr", True))


@dataclass
class SandboxConfig:
    image: str = "pandaevo/sandbox:latest"
    mem_limit: str = "512m"
    nano_cpus: int = 500000000
    pids_limit: int = 64
    network_mode: str = "none"
    idle_timeout_s: int = 3600

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SandboxConfig:
        if not data:
            return cls()
        return cls(
            image=data.get("image", "pandaevo/sandbox:latest"),
            mem_limit=data.get("mem_limit", "512m"),
            nano_cpus=data.get("nano_cpus", 500000000),
            pids_limit=data.get("pids_limit", 64),
            network_mode=data.get("network_mode", "none"),
            idle_timeout_s=data.get("idle_timeout_s", 3600),
        )


def get_sandbox_config() -> SandboxConfig:
    return SandboxConfig.from_dict(_cfg.get("sandbox"))
