# 后端模块记忆（python-service）

## 模块概况

- 定位：PandaEvo 核心后端 API，承接 web-pc 请求并编排 LLM、工具与 MCP 能力
- 技术栈：FastAPI + Uvicorn + PostgreSQL + SQLAlchemy Async + litellm + MCP
- 依赖管理：`uv` + `pyproject.toml`（统一使用 `>=` 下限约束）
- 关键依赖：`fastapi`、`sqlalchemy[asyncio]`、`asyncpg`、`litellm`、`mcp`、`httpx`、`docker`
- 运行端口：`10600`
- 配置合并：`config.yaml` → `config-dev.yaml` → 环境变量

## 架构决策

- [2026-03-10] 会话请求支持 `direct` 与 `orchestrator` 双路，由 `route_mode`/`multi`/策略开关共同决策
- [2026-03-10] Orchestrator 任务类型固定为 `analysis`/`coder`/`evolution`，支持代码任务与审查任务分流
- [2026-03-10] Agent 使用 ReAct 循环（最多 10 轮）并以事件流输出 token、tool、checkpoint、done
- [2026-03-10] MCP 工具统一经 adapter 注入 `TOOLS_REGISTRY`，工具命名规则 `mcp_{server}_{tool}`
- [2026-03-12] Provider 与 Purpose 解耦：`provider_models` 仅维护模型归属，`purpose_models` 维护用途候选与排序
- [2026-03-10] 文件系统访问必须通过 `safe_path()`，禁止越界到工作区外

## 模块职责

- `app/routers/`：HTTP API 编排层（providers/purposes/sessions/mcp/fs/skills/reload）
- `app/providers/`：模型提供商查询与调用封装
- `app/sessions/`：会话与消息持久化访问层
- `app/orchestrator.py`、`app/worker.py`、`app/agent.py`：任务规划、子任务执行与单轮对话执行核心
- `app/mcp/`、`app/tools/`：外部工具接入与统一工具运行时
- `app/coder`、`app/context`、`app/gateway`、`app/repo_sync`、`app/sandbox`、`app/security`：代码任务、上下文、网关、仓库同步、隔离运行与安全能力

## 数据模型约束（PostgreSQL）

- `sessions` + `messages`：会话主数据；`messages` 使用 `(session_id, created_at)` 索引
- `llm_providers`：提供商凭据与可用性；`name` 唯一
- `provider_models`：`provider_id + model_id` 唯一，不承载用途字段
- `purpose_models`：用途绑定表，字段 `purpose/provider_id/model_id/sort_order`，按 `sort_order` 决定候选优先级
- `mcp_servers`：MCP 连接配置（stdio/http）
- `plans`：orchestrator 计划快照及状态（running/completed/failed）

## 接口事实（需与前端联调保持一致）

- 健康与配置：`GET /health`、`POST /reload`
- Provider：`GET/POST /providers`、`PUT/DELETE /providers/{name}`
- Purpose：`GET/PUT /purposes/{purpose}`（purpose in `chat,title,worker`）
- Session：`GET/POST /sessions`、`GET/DELETE /sessions/{id}`、`PATCH /sessions/{id}/model`、`GET /sessions/{id}/export`、`POST /sessions/{id}/chat`、`POST /sessions/{id}/title`
- MCP：`GET/POST /mcp/servers`、`PUT/DELETE /mcp/servers/{name}`、`POST /mcp/servers/{name}/reconnect`
- FS/Skills：`GET /fs/tree`、`POST /fs/upload`、`GET /fs/download`、`GET /skills`

## 运行约束与经验

- 聊天流包含 `route` 事件与最终 `done` 事件；orchestrator 模式会持久化 `plan` 并回写状态
- `@path` 引用会在入站消息阶段展开为文件内容，路径校验失败或非文件会原样保留
- MCP 配置来源区分 `builtin`/`yaml`/`db`，仅 `db` 来源允许 API 修改或删除
- 新增路由必须在 `main.py` 显式 `include_router`，新增数据结构变更必须配套 SQL migration
