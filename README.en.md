[中文](README.md) | **English**

# PandaEvo Apps

## About PandaEvo

PandaEvo is an **Agent platform that can evolve itself**.

Agents on the platform can understand requirements and write code, while the platform itself continuously evolves through use, with its capabilities expanding and improving over time.

## About This Directory

`apps/` is the **runtime layer** of PandaEvo, containing the backend service and frontend interface that power the entire Agent platform. The evolution core (`core/`) lives outside this directory, maintained manually as the platform's stable foundation.

```
apps/
├── python-service/   # Agent engine (FastAPI backend)
└── web-pc/           # Chat interface (React frontend)
```

## python-service

An Agent engine built on **FastAPI**, handling all intelligent computation for the platform.

**Tech Stack**

| Layer | Technology |
|---|---|
| Language | Python ≥ 3.11 |
| Web Framework | FastAPI + Uvicorn |
| LLM Routing | LiteLLM |
| Database | PostgreSQL (asyncpg + SQLAlchemy async) |
| Tool Protocol | MCP (Model Context Protocol) |
| Sandbox Execution | Docker |

**Core Modules**

- **AgentRunner** — Single-session ReAct loop that drives LLM and tool calls, streaming results over SSE
- **OrchestratorAgent** — Multi-task orchestrator that decomposes user requests into dependency-aware sub-tasks executed in parallel
- **CoderAgent** — Code evolution agent that autonomously reads, writes, and commits files to a Gitea repository via PR
- **Skills / Rules** — Markdown knowledge snippets dynamically discovered from the filesystem and injected into the LLM system prompt
- **Sandbox** — Per-session isolated Docker container for safe shell command execution

## web-pc

A chat interface built on **React**, providing users with a complete experience for interacting with agents.

**Tech Stack**

| Layer | Technology |
|---|---|
| Language | TypeScript 5.9 |
| Framework | React 19 |
| Build Tool | Vite 7 |
| UI Components | Ant Design 6 + @ant-design/x |
| Desktop Integration | Tauri v2 |

**Core Pages**

- **SetupWizard** — First-run wizard that guides users through configuring an LLM provider
- **ChatPage** — Main chat interface with streaming output, tool call visualization, and multi-agent task progress tracking
- **SettingsDrawer** — Settings panel for managing providers, model purposes, MCP servers, and Skills

## How They Work Together

```
User
 │
 ▼
web-pc ──SSE stream──→ python-service
                             │
                        CoderAgent
                             │
                        Gitea PR ──→ evo agent (core/)
                                          │
                                   Review & update service
```

The frontend maintains a persistent connection to the backend via **SSE** (Server-Sent Events), receiving tokens, tool calls, and task progress events in real time. After completing code changes, the CoderAgent submits a PR to Gitea, which the evo agent reviews and hot-reloads — completing one full evolution cycle.

## Quick Start

> The commands below start the runtime layer only, **without evolution capabilities**. For the full evolution experience, use the installer package instead.

**Backend (python-service)**

```bash
cd python-service
uv sync
uv run uvicorn main:app --reload
```

**Frontend (web-pc)**

```bash
cd web-pc
pnpm install
pnpm dev
```

## Bug and Feature Submission

This open-source `apps/` directory currently **does not accept code PRs**.

You are welcome to submit Bugs and Feature Requests via Issues. Our professional AI team members will triage, evaluate, and process them quickly.

**Submission channels**

- Bug report: create a `Bug` issue
- Feature request: create a `Feature Request` issue

**Required Bug template**

```markdown
### Title
[Bug] One-line problem summary

### Environment
- OS:
- Runtime mode: (source run / installer package)
- Version or commit:
- Module: (python-service / web-pc / other)

### Description
Clearly describe what is going wrong.

### Steps to Reproduce
1.
2.
3.

### Expected Result
Describe the expected behavior.

### Actual Result
Describe what actually happens.

### Logs and Screenshots
Attach key logs, error messages, or screenshots.

### Impact
Explain affected functions, user scope, or urgency.
```

**Required Feature Request template**

```markdown
### Title
[Feature] One-line request summary

### Background and Goal
Describe the current pain point and target outcome.

### Request Details
Clearly describe the capability you want to add or improve.

### Use Cases
1.
2.
3.

### Acceptance Criteria
- [ ] Criteria 1
- [ ] Criteria 2
- [ ] Criteria 3

### Priority
(High / Medium / Low)

### Additional Context
Add mockups, reference links, or other helpful context.
```

## Download Installer (Full Evolution Capabilities)

PandaEvo launched via the official installer includes the evolution core and full self-evolution capabilities.

| Channel | Link |
|---|---|
| GitHub Releases | https://github.com/Curzibn/PandaEvo/releases/tag/v0.1.0 |
| Quark Drive | https://pan.quark.cn/s/bbbffc7fd4b4 |

# ☕ Donation

If this project has been helpful to you, please consider supporting my work through the following methods. Your support is the motivation for me to continue improving and maintaining this project.

<div align="center">

<table>
<tr>
<td align="center">
<img src="images/alipay.png" width="300" alt="Alipay QR Code" />
</td>
<td width="50"></td>
<td align="center">
<img src="images/wechat.png" width="300" alt="WeChat QR Code" />
</td>
</tr>
</table>

</div>

Thank you for your support! 🙏

## Donors

Thanks to the following donors for their support. These donations are used to purchase LLM token credits for continuously developing and improving this project.

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/SuperHunger"><img src="https://avatars.githubusercontent.com/u/16043546?v=4?s=80" width="80px;" alt="SuperHunger"/><br /><sub><b>SuperHunger</b></sub></a><br /><a href="https://github.com/SuperHunger" title="Thank you for donation">☕️</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

## License

The `apps/` subproject is licensed under the [MIT License](LICENSE).
