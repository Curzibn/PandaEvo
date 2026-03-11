[English](README.en.md) | **中文**

# PandaEvo Apps

## 关于 PandaEvo

PandaEvo 是一个**可以演化自身的 Agent 平台**。

平台内的 Agent 能够理解需求、编写代码，平台本身也会在使用过程中持续进化，功能不断扩展与完善。

## 关于本目录

`apps/` 是 PandaEvo 的**运行层**，包含驱动整个 Agent 平台所需的后端服务与前端界面。演化核心（`core/`）独立于本目录之外，由人工维护，作为平台的稳定基座。

```
apps/
├── python-service/   # Agent 引擎（FastAPI 后端）
└── web-pc/           # 聊天界面（React 前端）
```

## python-service

基于 **FastAPI** 构建的 Agent 引擎，承担平台的全部智能计算。

**技术栈**

| 层级 | 技术 |
|---|---|
| 语言 | Python ≥ 3.11 |
| Web 框架 | FastAPI + Uvicorn |
| LLM 路由 | LiteLLM |
| 数据库 | PostgreSQL（asyncpg + SQLAlchemy async）|
| 工具协议 | MCP（Model Context Protocol）|
| 沙箱执行 | Docker |

**核心模块**

- **AgentRunner** — 单会话 ReAct 循环，驱动 LLM 与工具调用，通过 SSE 流式推送结果
- **OrchestratorAgent** — 多任务编排器，将用户请求分解为带依赖关系的子任务并行执行
- **CoderAgent** — 代码演化 Agent，自主在 Gitea 仓库中读写文件并提交 PR
- **Skills / Rules** — 从文件系统动态发现的 Markdown 知识片段，注入 LLM 系统提示
- **Sandbox** — 每会话独立 Docker 容器，安全执行 Shell 命令

## web-pc

基于 **React** 构建的聊天界面，为用户提供与 Agent 交互的完整体验。

**技术栈**

| 层级 | 技术 |
|---|---|
| 语言 | TypeScript 5.9 |
| 框架 | React 19 |
| 构建 | Vite 7 |
| UI 组件 | Ant Design 6 + @ant-design/x |
| 桌面集成 | Tauri v2 |

**核心页面**

- **SetupWizard** — 首次运行向导，引导用户配置 LLM 供应商
- **ChatPage** — 主聊天界面，支持流式输出、工具调用可视化、多 Agent 任务进度追踪
- **SettingsDrawer** — 设置面板，管理供应商、模型用途、MCP 服务器与 Skills

## 协作关系

```
用户
 │
 ▼
web-pc ──SSE 流式─→ python-service
                         │
                    CoderAgent
                         │
                    Gitea PR ──→ evo agent（core/）
                                      │
                                 审核 & 更新服务
```

前端通过 **SSE**（Server-Sent Events）与后端保持长连接，实时接收 token、工具调用、任务进度等事件。后端的 CoderAgent 在完成代码修改后向 Gitea 提交 PR，再由 evo agent 完成审核与热更新，实现一次完整的演化循环。

## 快速启动

> 以下命令仅启动运行层本身，**不含演化功能**。如需体验完整演化能力，请使用安装包启动。

**后端（python-service）**

```bash
cd python-service
uv sync
uv run uvicorn main:app --reload
```

**前端（web-pc）**

```bash
cd web-pc
pnpm install
pnpm dev
```

## 下载安装包（含完整演化功能）

通过官方安装包启动的 PandaEvo 包含演化核心，具备完整的自演化能力。

| 渠道 | 链接 |
|---|---|
| GitHub Releases | <!-- GITHUB_RELEASE_URL --> |
| 夸克网盘 | <!-- QUARK_DOWNLOAD_URL --> |
