# Python Service 模块架构文档

## 功能概述

Python Service 是 PandaEvo 的**核心后端 API 服务**，基于 FastAPI 构建。其核心职责是：提供会话管理、LLM 对话编排、工具调用、MCP 服务器集成、技能与规则系统等能力，作为前端 web-pc 与底层 LLM、工具、MCP 服务之间的统一网关。

支持多模型提供商（通过 litellm）、多会话并发、任务编排（Orchestrator + Worker）、以及通过 MCP 协议扩展外部工具能力。

---

## 技术栈

| 层 | 技术 |
|---|---|
| HTTP 框架 | FastAPI |
| ASGI 服务器 | Uvicorn |
| 数据库 | PostgreSQL + SQLAlchemy（异步） |
| LLM 接入 | litellm（支持 OpenAI、Anthropic 等任意兼容提供商） |
| MCP 协议 | mcp（Model Context Protocol）客户端 |
| 语言 | Python ≥ 3.11 |
| 依赖管理 | uv（通过 pyproject.toml） |

---

## 模块结构

```
python-service/
├── main.py                    # FastAPI 应用入口，路由注册，生命周期管理
├── pyproject.toml             # 项目元数据与依赖声明
├── config.yaml                # 配置文件（可被 config-dev.yaml 覆盖）
├── Dockerfile                 # 容器构建文件
├── migrations/                # 数据库迁移脚本（SQL）
│   └── 20260307000000_init_sessions.sql
└── app/
    ├── __init__.py
    ├── config.py              # 配置读取（YAML + 环境变量）
    ├── logger.py              # 日志配置
    ├── db/                    # 数据库层
    │   ├── __init__.py        # engine, async_session, models 导出
    │   ├── models.py          # SQLAlchemy ORM 模型
    │   └── migration.py       # 迁移执行逻辑
    ├── providers/             # LLM 提供商管理
    │   ├── __init__.py
    │   ├── store.py           # ProviderLike 协议，数据库查询
    │   └── llm.py             # litellm 封装
    ├── routers/               # HTTP 路由
    │   ├── sessions.py        # 会话管理（创建、列表、删除、对话流）
    │   ├── providers.py       # 提供商 CRUD
    │   ├── mcp.py             # MCP 服务器管理
    │   ├── skills.py          # 技能管理
    │   ├── fs.py              # 文件系统操作（文件树、上传、下载）
    │   └── reload.py          # 配置重载
    ├── sessions/              # 会话存储抽象
    │   └── store.py           # SessionData, SessionSummary, session_store
    ├── orchestrator.py        # 任务编排器（规划 → 执行 → 汇总）
    ├── worker.py              # Worker 执行器（单任务执行）
    ├── agent.py               # Agent 对话循环（ReAct 式）
    ├── evolution.py           # Evolution Agent（转发到 evolution-core）
    ├── tools/                 # 工具系统
    │   ├── __init__.py        # TOOLS_REGISTRY, dispatch, get_tool_schemas
    │   ├── base.py            # ToolDef 基类
    │   ├── read_file.py       # 文件读取工具
    │   ├── write_file.py      # 文件写入工具
    │   ├── edit_file.py       # 文件编辑工具
    │   ├── list_dir.py        # 目录列表工具
    │   ├── search_files.py    # 文件搜索工具
    │   ├── exec_shell.py      # Shell 执行工具
    │   ├── web_fetch.py       # Web 抓取工具
    │   └── _utils.py          # 路径安全校验（safe_path）
    ├── mcp/                   # MCP 客户端集成
    │   ├── __init__.py        # 公开接口导出
    │   ├── client.py          # MCPClient, StdioMCPClient, HttpMCPClient
    │   ├── manager.py         # MCP 服务器生命周期管理
    │   └── adapter.py         # MCPToolAdapter（将 MCP 工具适配为 ToolDef）
    ├── skills/                # 技能系统
    │   ├── __init__.py        # 公开接口导出
    │   ├── discovery.py       # 技能发现（扫描 .PandaEvo/skills/）
    │   ├── loader.py          # 技能加载与执行
    │   ├── matcher.py         # 技能匹配（基于用户输入）
    │   ├── integrator.py      # 技能集成（注入到系统提示词）
    │   ├── snapshot.py        # 技能快照（缓存）
    │   └── model.py           # 技能数据模型
    └── rules/                 # 规则系统
        ├── __init__.py        # 公开接口导出
        ├── discovery.py       # 规则发现（扫描 .PandaEvo/rules/）
        ├── matcher.py         # 规则匹配（基于用户输入、文件路径）
        ├── integrator.py      # 规则集成（注入到系统提示词）
        └── snapshot.py        # 规则快照（缓存）
```

---

## 配置系统（config.py）

配置采用**三层合并**机制：`config.yaml`（基础）→ `config-dev.yaml`（开发覆盖，可选）→ 环境变量（运行时覆盖）。

### 配置项

| 路径 | 说明 | 环境变量覆盖 |
|---|---|---|
| `database.url` | PostgreSQL 连接字符串 | `DATABASE_URL` |
| `workspace.root` | 工作区根目录 | — |
| `service.data_dir` | 服务数据目录（默认 `~/.PandaEvo`） | — |
| `env` | 环境标识（`prod` / `dev`） | — |
| `mcp.builtin.enabled` | 是否启用内置 MCP 服务器 | — |
| `mcp.builtin.disabled` | 禁用的内置服务器列表 | — |
| `mcp.servers` | 外部 MCP 服务器配置列表 | — |
| `skills.enabled` | 是否启用技能系统 | — |
| `skills.auto_match` | 是否自动匹配技能 | — |
| `skills.max_skills` | 最大技能数量 | — |
| `skills.entries.{name}` | 特定技能配置（enabled, env, api_key, config） | — |
| `rules.enabled` | 是否启用规则系统 | — |
| `rules.auto_match` | 是否自动匹配规则 | — |
| `evolution_core.url` | evolution-core 服务地址 | — |

---

## 数据库模型（db/models.py）

### User

用户表（当前为单用户设计，`user_id` 可为 `NULL`）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `created_at` | DateTime | 创建时间 |

### Session

会话表，存储对话会话元数据。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `user_id` | UUID | 外键（可为 NULL） |
| `model` | Text | 当前使用的模型 ID |
| `title` | Text | 会话标题（可为 NULL，自动生成） |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### Message

消息表，存储会话中的所有消息。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `session_id` | UUID | 外键（级联删除） |
| `role` | Text | 角色（`user` / `assistant` / `tool`） |
| `content` | Text | 消息内容 |
| `created_at` | DateTime | 创建时间 |

索引：`(session_id, created_at)` 复合索引。

### LlmProvider

LLM 提供商表，存储 API 凭据与基础配置。模型与用途通过 `provider_models` 关联表管理。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `name` | Text | 提供商名称（唯一） |
| `api_key` | Text | API Key |
| `api_base` | Text | API Base URL（可为 NULL） |
| `enabled` | Boolean | 是否启用 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### ProviderModel

Provider 与模型的关联表，每个 model 可单独绑定用途（purpose）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `provider_id` | UUID | 外键（级联删除） |
| `model_id` | Text | 模型 ID（如 `dashscope/qwen-plus`） |
| `purpose` | Text | 用途（`chat` / `title` / `worker`，可为 NULL） |
| `created_at` | DateTime | 创建时间 |

唯一约束：`(provider_id, model_id)` 组合唯一；`purpose` 非空时全局唯一（每种用途仅一个 model）。

### McpServer

MCP 服务器配置表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `name` | Text | 服务器名称（唯一） |
| `command` | Text | 命令（stdio 传输） |
| `args` | JSONB | 命令参数列表 |
| `env` | JSONB | 环境变量（可为 NULL） |
| `url` | Text | HTTP URL（http 传输，可为 NULL） |
| `headers` | JSONB | HTTP 请求头（可为 NULL） |
| `enabled` | Boolean | 是否启用 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

### Plan

任务计划表（存储编排器生成的计划）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `session_id` | UUID | 外键（级联删除） |
| `tasks` | JSONB | 任务列表 |
| `status` | Text | 状态（`running` / `completed` / `failed`） |
| `created_at` | DateTime | 创建时间 |

---

## 核心模块职责

### main.py

FastAPI 应用入口，负责：

1. **生命周期管理**（`lifespan`）：
   - 启动时：初始化日志、执行数据库迁移、初始化 MCP 服务器
   - 关闭时：关闭 MCP 服务器、释放数据库连接池

2. **路由注册**：
   - `/providers` → `providers_router`
   - `/sessions` → `sessions_router`
   - `/fs` → `fs_router`
   - `/mcp` → `mcp_router`
   - `/skills` → `skills_router`
   - `/reload` → `reload_router`
   - `/health` → 健康检查端点

### orchestrator.py

任务编排器，实现"规划 → 执行 → 汇总"三阶段流程：

1. **规划阶段**：调用 LLM（使用 `orchestrator_model`）将用户请求拆解为 1～5 个子任务，每个任务包含 `id`、`title`、`prompt`、`type`（`analysis` / `evolution`）、`depends_on`（依赖关系）
2. **执行阶段**：按拓扑排序将任务分批并发执行
   - `type="evolution"` → 转发到 `EvolutionAgent`
   - `type="analysis"` → 调用 `run_worker`
3. **汇总阶段**：调用 LLM 将所有子任务结果综合为最终回答

所有事件通过 async generator 流式返回，前端通过 SSE 接收。

### worker.py

Worker 执行器，封装单任务执行：

- 调用 `AgentRunner().run()` 执行对话循环
- 将 agent 事件包装为 `worker_event`（`task_id` + `event`）
- 任务完成时 yield `worker_done`（`task_id` + `result`）

### agent.py

Agent 对话循环（ReAct 式），实现为 async generator：

1. **系统提示词构建**：
   - 工作区根目录、结构快照（深度 2）
   - 可用工具列表（TOOLS_REGISTRY）
   - 规则集成（若启用）：匹配规则并注入
   - 技能集成（若启用）：匹配技能并注入

2. **主循环**（最多 `_MAX_ROUNDS=10` 轮）：
   - 调用 `llm_provider.stream_complete()` 流式请求 LLM
   - 累积 `token`、`thinking`、`tool_calls`
   - `finish_reason == "tool_calls"` → 调度工具 → 追加 tool 消息 → 继续
   - `finish_reason == 其他` → yield `done` → return

3. **工具调度**：
   - 调用 `tools.dispatch(name, args)` 执行工具
   - 工具结果追加为 `role: tool` 消息

### providers/

LLM 提供商管理模块：

- **`store.py`**：提供 Provider 查询函数
  - `get_provider_for_model(db, model_id)`: 查询包含指定 model 的启用 Provider
  - `get_model_for_purpose(db, purpose)`: 查询绑定指定用途的 model，返回 `ResolvedModel`（model_id, api_key, api_base）
  - 所有查询通过 JOIN `provider_models` 表

- **`llm.py`**：litellm 封装，提供统一的 LLM 调用接口
  - `LLMProvider.stream_complete()`: 流式完成（返回 async generator）
  - `LLMProvider.complete()`: 非流式完成（返回完整响应）

**设计原则**：
- Provider 名称唯一，仅存储 API 凭据
- 用途（purpose）绑定在 model 级别，通过 `provider_models` 表管理
- 每种用途（chat、title、worker）全局仅能绑定一个 model
- 查询时通过 JOIN 和 `selectinload` 确保异步环境下的关系加载

### tools/

工具系统，提供 LLM 可调用的函数能力：

#### 内置工具

| 工具名 | 模块 | 功能 |
|---|---|---|
| `read_file` | `read_file.py` | 读取文件内容（支持行偏移和限制） |
| `write_file` | `write_file.py` | 写入文件 |
| `edit_file` | `edit_file.py` | 编辑文件（search_replace） |
| `list_dir` | `list_dir.py` | 列出目录树 |
| `search_files` | `search_files.py` | 搜索文件（按名称或内容） |
| `exec_shell` | `exec_shell.py` | 执行 Shell 命令 |
| `web_fetch` | `web_fetch.py` | 抓取网页内容 |

#### MCP 工具适配

`mcp/adapter.py` 将 MCP 服务器的工具适配为 `ToolDef`，命名规则：`mcp_{server_name}_{tool_name}`。

#### 路径安全

所有文件系统工具通过 `tools/_utils.safe_path(rel)` 校验，确保路径不逃逸工作区根目录。

### mcp/

MCP（Model Context Protocol）客户端集成：

- **StdioMCPClient**：通过 stdio 进程通信
- **HttpMCPClient**：通过 HTTP 请求通信
- **manager.py**：管理 MCP 服务器生命周期（启动、停止、重连），工具自动注册到 `TOOLS_REGISTRY`

### skills/

技能系统，支持从 `.PandaEvo/skills/` 目录发现和执行技能：

- **discovery.py**：扫描技能目录，读取 `SKILL.md` 元数据
- **loader.py**：加载技能内容，执行技能逻辑
- **matcher.py**：基于用户输入匹配相关技能
- **integrator.py**：将匹配的技能注入到系统提示词
- **snapshot.py**：缓存技能快照（避免重复扫描）

### rules/

规则系统，支持从 `.PandaEvo/rules/` 目录发现和应用规则：

- **discovery.py**：扫描规则目录，读取规则文件
- **matcher.py**：基于用户输入和访问的文件路径匹配规则
- **integrator.py**：将匹配的规则注入到系统提示词
- **snapshot.py**：缓存规则快照

---

## HTTP API

### `GET /health`

健康检查端点。

**响应**

```json
{"ok": true}
```

### `GET /providers`

列出所有 LLM 提供商。

**响应**

```json
[
  {
    "name": "openai",
    "api_base": null,
    "models": [{"id": "gpt-4", "label": "GPT-4", "purpose": "chat"}]
  }
]
```

### `POST /providers`

创建 LLM 提供商。

**请求体**

```json
{
  "name": "openai",
  "api_key": "...",
  "api_base": null,
  "models": [{"id": "gpt-4", "purpose": "chat"}]
}
```

`models` 中每个 model 可指定 `purpose`（`chat` / `title` / `worker`），每种用途全局仅能绑定一个 model。

### `PUT /providers/{name}`

更新 LLM 提供商。

**请求体**

```json
{
  "api_key": "...",
  "api_base": null,
  "models": [{"id": "gpt-4", "purpose": "chat"}]
}
```

`models` 会完整替换现有模型列表及用途绑定。

### `DELETE /providers/{name}`

删除 LLM 提供商。删除时会级联删除所有关联的 `provider_models` 记录。

### `GET /sessions`

列出所有会话摘要。

**响应**

```json
[
  {
    "id": "uuid",
    "model": "gpt-4",
    "title": "会话标题",
    "created_at": "2026-03-10T...",
    "message_count": 5
  }
]
```

### `POST /sessions`

创建新会话。

**请求体**

```json
{
  "model": "gpt-4"
}
```

**响应**

```json
{
  "id": "uuid",
  "model": "gpt-4",
  "messages": [],
  "created_at": "2026-03-10T..."
}
```

### `POST /sessions/{session_id}/chat`

发送消息并流式返回响应（SSE）。

**请求体**

```json
{
  "content": "用户消息内容"
}
```

**响应** `Content-Type: text/event-stream`

事件类型：

| `type` | 说明 | 其他字段 |
|---|---|---|
| `plan` | 任务计划 | `tasks` |
| `worker_start` | Worker 开始 | `task_id` |
| `worker_event` | Worker 事件 | `task_id`, `event` |
| `worker_done` | Worker 完成 | `task_id`, `result` |
| `thinking` | LLM 思考过程 | `content` |
| `token` | LLM token | `content` |
| `tool_call` | 工具调用 | `id`, `name`, `args` |
| `tool_result` | 工具结果 | `id`, `content` |
| `done` | 本轮完成 | `new_message` |

### `GET /sessions/{session_id}`

获取会话详情（含所有消息）。

### `DELETE /sessions/{session_id}`

删除会话（级联删除所有消息）。

### `POST /sessions/{session_id}/title`

生成会话标题。

**请求体**

```json
{
  "content": "首条用户消息内容"
}
```

### `GET /mcp/servers`

列出所有 MCP 服务器。

### `POST /mcp/servers`

添加 MCP 服务器。

### `DELETE /mcp/servers/{name}`

删除 MCP 服务器。

### `POST /mcp/servers/{name}/reconnect`

重连 MCP 服务器。

### `GET /skills`

列出所有可用技能。

### `GET /fs/tree`

获取文件树。

**查询参数**

- `path`：目录路径（默认 `.`）
- `depth`：深度（默认 `2`）

### `POST /fs/upload`

上传文件。

### `GET /fs/download`

下载文件。

**查询参数**

- `path`：文件路径

---

## 数据库迁移

迁移脚本位于 `migrations/` 目录，SQL 格式。

`app/db/migration.py` 在应用启动时自动执行所有未应用的迁移（通过检查 `schema_migrations` 表）。

---

## 容器构建（Dockerfile）

单阶段构建：

1. 基于 `python:3.11-slim`
2. 安装 Node.js（用于某些工具依赖）
3. 安装 `uv`
4. 解析 `pyproject.toml` 生成 `requirements.txt`，用 `uv` 安装依赖
5. 拷贝源码
6. 暴露端口 `10600`
7. 启动命令：`uvicorn main:app --host 0.0.0.0 --port 10600`

---

## 在项目中的位置

### 服务拓扑

Python Service 是 PandaEvo 六个 Docker 服务之一，运行于 `10600` 端口。

```
desktop（Tauri 桌面引导器）
  └─ 管理生命周期、健康监控
        ↓
web-pc（:10601）── HTTP API ──► python-service（:10600）
  └─ React SPA                        ├─ 会话管理
                                      ├─ LLM 对话编排
                                      ├─ 工具调用
                                      ├─ MCP 集成
                                      └─ 技能/规则系统
                                              ↓
                                    evolution-core（:10602）
                                      └─ 代码审查（evolution 任务）
```

### Desktop 集成

desktop bootstrap 模块对 python-service 有以下依赖：

| 位置 | 行为 |
|---|---|
| `config.rs` | 定义 `ports::PYTHON_SERVICE = 10600` |
| `runner_prod.rs` | Phase 5 `health_wait`：等待 10600 健康 |
| `runner_dev.rs` | Phase 4 `evolution_start`：与 evolution-core、web-pc 一同 `--build` 启动 |
| `watchdog.rs` | 每 30 秒检查 `/health`，异常时触发恢复 |

### web-pc 集成

web-pc 通过 HTTP API 与 python-service 通信：

- 开发环境：Vite proxy 将 `/api` 转发到 `http://python-service:10600`
- 生产环境：nginx 反向代理 `/api` 到 `http://python-service:10600`
