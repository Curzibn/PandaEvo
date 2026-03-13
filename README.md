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

## Bug 与需求提交

本项目开源目录当前**不接受代码 PR**。

欢迎通过 Issue 提交 Bug 和需求，我们的专业 AI 团队成员会快速分流、评估并推进处理。

**提交入口**

- Bug 提交：创建 `Bug` 类型 Issue
- 需求提交：创建 `Feature Request` 类型 Issue

**Bug 指定提交格式**

```markdown
### 标题
[Bug] 一句话描述问题

### 环境信息
- OS:
- 运行方式: (源码运行 / 安装包)
- 版本号或提交号:
- 模块: (python-service / web-pc / 其他)

### 问题描述
清晰描述实际出现的问题现象。

### 复现步骤
1.
2.
3.

### 期望结果
描述你预期的正确行为。

### 实际结果
描述当前实际行为。

### 日志与截图
请粘贴关键日志、报错信息或截图。

### 影响范围
说明问题影响的功能、用户范围或紧急程度。
```

**需求指定提交格式**

```markdown
### 标题
[Feature] 一句话描述需求

### 背景与目标
说明当前痛点和希望解决的问题。

### 需求描述
清晰描述希望新增或改进的能力。

### 使用场景
1.
2.
3.

### 验收标准
- [ ] 标准 1
- [ ] 标准 2
- [ ] 标准 3

### 优先级
(高 / 中 / 低)

### 补充信息
可补充原型、参考链接或其他上下文。
```

## 下载安装包（含完整演化功能）

通过官方安装包启动的 PandaEvo 包含演化核心，具备完整的自演化能力。

| 渠道 | 链接 |
|---|---|
| GitHub Releases | https://github.com/Curzibn/PandaEvo/releases/tag/v0.1.0 |
| 夸克网盘 | https://pan.quark.cn/s/bbbffc7fd4b4 |

# ☕ 捐助

如果这个项目对您有帮助，欢迎通过以下方式支持我的工作。您的支持是我持续改进和维护这个项目的动力。

<div align="center">

<table>
<tr>
<td align="center">
<img src="images/alipay.png" width="300" alt="支付宝收款码" />
</td>
<td width="50"></td>
<td align="center">
<img src="images/wechat.png" width="300" alt="微信收款码" />
</td>
</tr>
</table>

</div>

感谢您的支持！🙏

## 捐赠人

感谢以下捐赠人的支持！你们的捐赠将用于购买 LLM Token 额度，持续开发和完善本项目。

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/SuperHunger"><img src="https://avatars.githubusercontent.com/u/16043546?v=4?s=80" width="80px;" alt="SuperHunger"/><br /><sub><b>SuperHunger</b></sub></a><br /><a href="https://github.com/SuperHunger" title="感谢捐赠">☕️</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## 开源协议

本项目 `apps/` 子目录采用 [MIT License](LICENSE)。
