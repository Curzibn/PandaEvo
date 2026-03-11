---
name: python-service-development
description: Guide development of the PandaEvo python-service module, a FastAPI-based backend API service providing session management, LLM orchestration, tool calling, MCP integration, and skills/rules systems. Use when working on any file under python-service/, adding new tools, extending HTTP API, modifying orchestrator logic, integrating MCP servers, or debugging database migrations.
---

# Python Service 模块开发指南

## 模块定位与边界

Python Service 是 PandaEvo 的**核心后端 API 服务**，唯一职责：提供会话管理、LLM 对话编排、工具调用、MCP 服务器集成、技能与规则系统等能力，作为前端 web-pc 与底层 LLM、工具、MCP 服务之间的统一网关。

**严格边界**：

- 不包含前端 UI 代码——前端在 web-pc 模块
- 不直接管理 Docker 容器——由 desktop 模块管理（但通过 Docker SDK 管理会话级沙箱容器）
- 不包含代码审查逻辑——evolution 类型任务转发到 evolution-core
- 数据库访问统一通过 SQLAlchemy ORM，禁止直接 SQL
- 文件系统访问严格限制在工作区根目录内（通过 `safe_path` 校验，支持 per-session 隔离）

---

## 技术栈

| 层 | 技术 | 约束 |
|---|---|---|
| HTTP 框架 | FastAPI | 所有端点返回 `StreamingResponse`（SSE）或 `JSONResponse` |
| ASGI 服务器 | Uvicorn | 默认端口 10600 |
| 数据库 | PostgreSQL + SQLAlchemy（异步） | 使用 `AsyncSession`，禁止同步操作 |
| LLM 接入 | litellm | 通过 `app/providers/llm.py` 统一封装，不直接调用 litellm |
| MCP 协议 | mcp | 通过 `app/mcp/` 模块统一管理 |
| 容器隔离 | Docker SDK | 通过 `app/sandbox/` 模块管理会话级沙箱容器 |
| 语言 | Python ≥ 3.11 | 使用 `from __future__ import annotations` |
| 依赖管理 | uv | 依赖声明在 `pyproject.toml`，使用 `>=` 约束 |

---

## 模块结构

```
python-service/
├── main.py                    # FastAPI 应用入口
├── pyproject.toml             # 依赖声明
├── config.yaml                # 配置文件
├── migrations/                # SQL 迁移脚本
└── app/
    ├── config.py              # 配置读取
    ├── db/                    # 数据库层
    ├── providers/             # LLM 提供商
    ├── routers/               # HTTP 路由
    ├── sessions/              # 会话存储
    ├── orchestrator.py        # 任务编排器
    ├── worker.py              # Worker 执行器
    ├── agent.py               # Agent 对话循环
    ├── evolution.py           # Evolution Agent
    ├── tools/                 # 工具系统
    ├── mcp/                   # MCP 客户端
    ├── sandbox/               # 会话沙箱管理（Docker 容器隔离）
    ├── skills/                # 技能系统
    └── rules/                 # 规则系统
```

---

## 核心设计模式

### 1. 配置三层合并

配置读取顺序：`config.yaml`（基础）→ `config-dev.yaml`（开发覆盖，可选）→ 环境变量（运行时覆盖）。

所有配置通过 `app/config.py` 的函数读取，**禁止**在业务模块中直接读取环境变量或 YAML 文件。

### 2. 工具注册：Schema 与实现同文件

`app/tools/` 目录下每个工具文件包含：
- `ToolDef` 实例（定义工具名称、描述、Schema）
- `execute()` 函数（工具实现）

工具通过 `TOOLS_REGISTRY` 统一注册，通过 `dispatch()` 统一路由。

**添加新工具必须**：
1. 在 `app/tools/` 创建新文件，实现 `ToolDef` 和 `execute()`
2. 在 `app/tools/__init__.py` 的 `TOOLS_REGISTRY` 中注册
3. 文件系统操作必须通过 `safe_path()` 校验路径

### 3. Agentic Loop（ReAct 式）

`agent.py` 的 `AgentRunner.run()` 实现 ReAct 式对话循环：

```
while True:
    调用 litellm.stream_complete()
    ↓ 流式累积 token、thinking、tool_calls
    ↓
    finish_reason == "tool_calls" → 调度工具 → 追加 tool 消息 → 继续
    finish_reason == 其他        → yield done → return
```

工具调用结果通过 `role: tool` 消息追加到 `messages`，LLM 在下一轮看到工具返回值后继续推理。

### 4. 路由与任务编排：决策 → 规划 → 执行 → 汇总

`sessions.py` 与 `orchestrator.py` 协同实现四阶段流程：

1. **决策**：调用会话模型输出 `route=direct|orchestrator` 与 `reason`
2. **规划**：`route=orchestrator` 时调用 LLM 将请求拆解为子任务（1～5 个）
3. **执行**：按拓扑排序分批并发执行（`type="evolution"` 转发到 evolution-core）
4. **汇总**：默认调用 LLM 综合子任务结果；若仅单个轻量 `analysis` 任务则直接返回任务结果

所有事件通过 async generator 流式返回。

### 5. SSE 事件协议

所有流式端点以 `text/event-stream` 格式推送，每行格式：

```
data: {json}\n\n
```

事件类型（按时序）：

| type | 触发时机 | 关键字段 |
|---|---|---|
| `plan` | 任务计划生成 | `tasks` |
| `route` | 路由决策完成 | `route`, `reason` |
| `worker_start` | Worker 开始 | `task_id` |
| `worker_event` | Worker 内部事件 | `task_id`, `event` |
| `worker_done` | Worker 完成 | `task_id`, `result` |
| `thinking` | LLM 思考过程 | `content` |
| `token` | 每个 LLM token | `content` |
| `tool_call` | LLM 决定调用工具 | `id`, `name`, `args` |
| `tool_result` | 工具执行完毕 | `id`, `content` |
| `done` | 本轮 LLM 输出结束 | `new_message` |

### 6. 任务级容器隔离

每个会话拥有独立的 Docker 沙箱容器，实现文件系统隔离、Shell 隔离和资源限制。

**核心组件**：

- `app/sandbox/manager.py`：`SandboxManager` 单例，管理容器生命周期（懒创建、缓存、清理）
- `app/sandbox/sandbox.py`：`SessionSandbox` 类，封装单个容器的 exec/cleanup 操作
- `app/tools/_utils.py`：`session_ctx` ContextVar，从 chat 端点注入 session_id，工具层读取以定位 per-session workspace

**工作流程**：

1. 用户发起 chat 请求 → `app/routers/sessions.py` 的 `chat()` 端点设置 `session_ctx.set(session_id)`
2. Agent 调用工具 → `app/tools/_utils.safe_path()` 读取 `session_ctx.get()`，workspace root 变为 `/workspace/{session_id}/`
3. `exec_shell` 工具 → `SandboxManager.exec(session_id, command)` 路由到对应会话的容器执行
4. 会话删除 → `DELETE /sessions/{id}` 调用 `SandboxManager.cleanup(session_id)` 清理容器

**资源限制**（通过 `config.yaml` 的 `sandbox:` 配置块）：

- `mem_limit`：内存限制（默认 `512m`）
- `nano_cpus`：CPU 配额（默认 `500000000` = 0.5 CPU）
- `pids_limit`：进程数限制（默认 `64`）
- `network_mode`：网络模式（默认 `none`，完全隔离）
- `idle_timeout_s`：空闲超时（默认 `3600` 秒，自动清理）

**镜像层级**：

```
python:3.11-slim (upstream)
  └── PandaEvo/base (Python 3.11 + Node.js LTS + uv)
        ├── PandaEvo/python-service (+ pyproject deps + app code)
        └── PandaEvo/sandbox (纯运行时，无 app 代码)
```

`docker-compose.yaml` 使用 `additional_contexts: PandaEvo-base: service:base` 确保构建顺序正确。

### 7. 演化仓库同步链路

首次打包运行时，desktop bootstrap 会将安装包内置的 `python-service` 与 `web-pc` 初始化为独立 Git 仓库并推送到 Gitea。

python-service 每次启动会执行一次仓库同步：

1. 读取 `repo_sync.repos`（默认 `python-service`、`web-pc`）
2. 目标目录不存在时执行 clone
3. 目标目录已存在时执行 `git pull --ff-only`

同步入口：`main.py` 的 lifespan 调用 `app/repo_sync/service.py:startup_sync_repositories()`。

---

## 配置系统规范

### 配置文件结构

`config.yaml` 和 `config-dev.yaml` 使用 YAML 格式，支持嵌套对象。

### 环境变量覆盖

以下配置项支持环境变量覆盖：

- `DATABASE_URL` → `database.url`

其他配置项通过 YAML 文件管理，**不**支持环境变量覆盖。

### 演化仓库同步配置

`config.yaml` 新增 `repo_sync` 配置块：

```yaml
repo_sync:
  enabled: true
  root: "/apps/repos"
  repos: ["python-service", "web-pc"]
  branch: "main"
```

读取函数位于 `app/config.py`：
- `get_repo_sync_enabled()`
- `get_repo_sync_root()`
- `get_repo_sync_repos()`
- `get_repo_sync_branch()`

### 新增配置项

1. 在 `config.yaml` 添加配置项
2. 在 `app/config.py` 添加读取函数（如 `get_xxx()`）
3. 在业务模块中通过 `app.config` 导入使用

### Sandbox 配置

`config.yaml` 的 `sandbox:` 配置块控制会话容器的资源限制：

```yaml
sandbox:
  image: "PandaEvo/sandbox:latest"
  mem_limit: "512m"
  nano_cpus: 500000000
  pids_limit: 64
  network_mode: "none"
  idle_timeout_s: 3600
```

配置通过 `app/config.get_sandbox_config()` 读取，返回 `SandboxConfig` dataclass。

---

## 数据库规范

### ORM 模型

所有数据库表通过 SQLAlchemy ORM 模型定义（`app/db/models.py`），**禁止**直接写 SQL 创建表。

### 迁移脚本

迁移脚本位于 `migrations/` 目录，SQL 格式，命名规则：`{YYYYMMDDHHMMSS}_{description}.sql`。

迁移执行逻辑在 `app/db/migration.py`，启动时自动执行所有未应用的迁移。

### 查询规范

- 使用 `AsyncSession`，禁止同步 `Session`
- 使用 SQLAlchemy 查询 API，禁止直接 SQL（迁移脚本除外）
- 使用 `select()` 构建查询，禁止字符串拼接 SQL

---

## 工具系统规范

### Coder 仓库工具约定

- `app/coder/tools.py` 中的 Coder 工具不再内置固定仓库黑名单，仓库可操作范围由运行时权限和调用上下文决定。
- `app/coder/gitea.py:list_repos()` 采用 owner 自适应探测（org/user），并在 token 缺少读取 scope 时自动降级到无鉴权可见仓库查询。
- 仓库发现失败时必须返回可诊断信息（endpoint、状态码、错误原因），避免仅返回笼统失败。

### 路径安全与会话隔离

所有文件系统工具必须通过 `app/tools/_utils.safe_path(rel)` 校验：

```python
from app.tools._utils import safe_path

target = safe_path(user_input)  # 自动校验路径不逃逸工作区
```

**路径解析逻辑**：

- `safe_path()` 读取 `session_ctx.get()`（由 chat 端点注入）
- 若存在 session_id，workspace root 为 `/workspace/{session_id}/`
- 若不存在（非 chat 上下文），workspace root 为 `/workspace/`
- 所有路径解析后必须位于 workspace root 内，否则抛出 `PermissionError`

**禁止**直接使用 `Path(user_input)` 或 `os.path.join()` 处理用户输入路径。

### 工具实现

每个工具文件应包含：

```python
from app.tools.base import ToolDef

tool_name_tool = ToolDef(
    name="tool_name",
    description="工具描述",
    parameters={...},  # JSON Schema
)

async def execute(args: dict[str, Any]) -> str:
    # 工具实现
    # 返回字符串结果（成功）或 "Error: ..."（失败）
    pass
```

### MCP 工具适配

MCP 工具通过 `app/mcp/adapter.py` 自动适配为 `ToolDef`，命名规则：`mcp_{server_name}_{tool_name}`。

**无需手动注册**，MCP 服务器连接成功后自动注册到 `TOOLS_REGISTRY`。

---

## MCP 集成规范

### 服务器配置

MCP 服务器配置来源：
1. `config.yaml` 的 `mcp.servers` 列表（启动时加载）
2. 数据库 `mcp_servers` 表（运行时动态添加）

### 传输方式

- **stdio**：通过 `command` + `args` + `env` 启动子进程
- **http**：通过 `url` + `headers` 发起 HTTP 请求

### 生命周期管理

`app/mcp/manager.py` 负责：
- 启动时初始化所有配置的服务器
- 运行时动态添加/删除/重连服务器
- 工具自动注册/注销

**新增 MCP 服务器时**：
1. 在 `config.yaml` 添加配置，或通过 `/mcp/servers` API 添加
2. 服务器连接成功后工具自动可用，无需额外代码

---

## 技能与规则系统

### 技能系统

技能从 `.PandaEvo/skills/` 目录发现，每个技能目录包含 `SKILL.md` 文件。

- **发现**：`app/skills/discovery.py` 扫描目录
- **匹配**：`app/skills/matcher.py` 基于用户输入匹配
- **集成**：`app/skills/integrator.py` 注入到系统提示词
- **执行**：`app/skills/loader.py` 执行技能逻辑

### 规则系统

规则从 `.PandaEvo/rules/` 目录发现，每个规则文件为 `.mdc` 格式。

- **发现**：`app/rules/discovery.py` 扫描目录
- **匹配**：`app/rules/matcher.py` 基于用户输入和访问的文件路径匹配
- **集成**：`app/rules/integrator.py` 注入到系统提示词

### 配置控制

通过 `config.yaml` 控制启用/禁用：

- `skills.enabled` / `rules.enabled`：总开关
- `skills.auto_match` / `rules.auto_match`：是否自动匹配
- `skills.max_skills`：最大技能数量

---

## HTTP API 规范

### 路由组织

每个功能模块对应一个 router 文件（`app/routers/*.py`），在 `main.py` 统一注册。

### 流式响应

所有需要流式返回的端点使用 `StreamingResponse`：

```python
from fastapi.responses import StreamingResponse

@router.post("/chat")
async def chat(...):
    async def generate():
        async for event in agent.run(...):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
    )
```

### 错误处理

- 使用 FastAPI 的 `HTTPException` 抛出 HTTP 错误
- 工具执行错误返回 `"Error: ..."` 字符串，不抛出异常
- 数据库错误记录日志并返回 500

---

## 常见开发场景

### 添加新工具

1. 在 `app/tools/` 创建新文件（如 `new_tool.py`）
2. 实现 `ToolDef` 和 `execute()` 函数
3. 在 `app/tools/__init__.py` 的 `TOOLS_REGISTRY` 中注册
4. 若涉及文件系统操作，使用 `safe_path()` 校验路径

### 添加新 HTTP 端点

1. 在对应的 `app/routers/*.py` 添加路由函数
2. 若业务逻辑超过 10 行，抽取到对应职责模块
3. 流式响应使用 `StreamingResponse`，普通响应使用 `JSONResponse`
4. 会话导出类接口统一放在 `app/routers/sessions.py`，路径使用 `GET /sessions/{session_id}/export`，返回 `application/json` 附件下载

### 修改聊天路由策略

- `POST /sessions/{session_id}/chat` 支持两种路由控制：
  - 显式兼容参数：`multi=true|false`
  - 推荐参数：`route_mode=auto|direct|orchestrator`
- 当 `route_mode=auto` 且未显式传 `multi` 时，后端使用会话模型输出 `route + reason` 决策执行路径

### 添加新数据库表

1. 在 `app/db/models.py` 添加 ORM 模型
2. 创建迁移脚本（`migrations/{timestamp}_{description}.sql`）
3. 迁移脚本包含 `CREATE TABLE` 语句

### 模型与用途多对多关系

`provider_models` 表记录每个 Provider 下的模型列表（多对一关系）。

`purpose_models` 表实现用途与模型的**多对多**关系，每条记录包含：
- `purpose`：用途类型（`chat`/`title`/`worker`）
- `provider_id` + `model_id`：指向具体模型
- `sort_order`：用途内的优先级顺序（从 0 开始）

用途模型读写通过 `app/providers/store.py` 的 `get_models_for_purpose()` / `GET /api/purposes/{purpose}` / `PUT /api/purposes/{purpose}` 完成。

**fallback 逻辑**（标题生成和子智能体）：按 `sort_order` 依次尝试，全部失败则回退到当前会话的对话模型。

### 修改编排逻辑

`orchestrator.py` 的系统提示词（`_PLAN_SYSTEM`、`_SYNTHESIZE_SYSTEM`）内嵌于代码，直接修改文本即可。

### 修改 Agent 系统提示词

`agent.py` 的 `_build_system_prompt()` 函数动态构建系统提示词，修改此函数即可。

### 调试沙箱容器

**查看会话容器状态**：

```bash
docker ps --filter "name=PandaEvo-sandbox-"
```

**查看容器日志**：

```bash
docker logs PandaEvo-sandbox-{session_id}
```

**手动清理容器**：

```bash
docker stop PandaEvo-sandbox-{session_id}
docker rm PandaEvo-sandbox-{session_id}
```

**修改沙箱资源限制**：

修改 `config.yaml` 的 `sandbox:` 配置块，重启服务生效。

---

## 架构文档同步规范

**当以下变更发生后，必须同步更新 `ARCHITECTURE.md` 和本 SKILL.md**：

| 变更类型 | 需更新的内容 |
|---|---|
| 新增/删除工具 | ARCHITECTURE.md「工具系统」节；SKILL.md「添加新工具」场景 |
| 新增 HTTP 端点 | ARCHITECTURE.md「HTTP API」节 |
| 新增数据库表 | ARCHITECTURE.md「数据库模型」节；SKILL.md「添加新数据库表」场景 |
| 新增配置项 | ARCHITECTURE.md「配置系统」表；SKILL.md「配置系统规范」节 |
| 修改编排逻辑 | ARCHITECTURE.md「orchestrator.py」节；SKILL.md「修改编排逻辑」场景 |
| 修改 Agent 提示词 | ARCHITECTURE.md「agent.py」节；SKILL.md「修改 Agent 系统提示词」场景 |
| 新增模块文件 | ARCHITECTURE.md「模块结构」目录树；SKILL.md「模块结构」目录树 |
| 修改 Dockerfile | ARCHITECTURE.md「容器构建」节 |
| 修改沙箱配置 | ARCHITECTURE.md「任务级容器隔离」节；SKILL.md「Sandbox 配置」节 |
| 修改镜像层级 | ARCHITECTURE.md「镜像构建」节；SKILL.md「任务级容器隔离」节 |

更新原则：**先改代码，后改文档**，在同一次提交中完成，保持文档与代码一致。
