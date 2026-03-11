# Web PC 模块架构文档

## 功能概述

Web PC 是 PandaEvo 的**前端单页应用（SPA）**，基于 React + TypeScript + Vite + Ant Design 构建。其核心职责是：提供用户界面，包括会话管理、LLM 对话、文件浏览、设置管理等功能，通过 HTTP API 与 python-service 后端通信。

支持流式响应（SSE）、多会话管理、文件树浏览、工具调用可视化、任务编排可视化等特性。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端框架 | React 19 |
| 语言 | TypeScript 5.9 |
| 构建工具 | Vite 7 |
| UI 组件库 | Ant Design 6 |
| 聊天组件 | @ant-design/x（Bubble、Conversations、Sender、Think） |
| Markdown 渲染 | @ant-design/x-markdown、react-markdown |
| 样式方案 | antd-style（CSS-in-JS） |
| HTTP 客户端 | Fetch API（原生） |
| 部署服务器 | Nginx（Alpine） |

---

## 模块结构

```
web-pc/
├── package.json               # 依赖声明
├── vite.config.ts             # Vite 配置（开发代理、端口）
├── tsconfig.json              # TypeScript 配置
├── Dockerfile                 # 容器构建文件（多阶段：builder + nginx）
├── nginx.conf                 # Nginx 配置（生产环境）
├── index.html                 # HTML 入口
├── src/
│   ├── main.tsx               # React 应用入口
│   ├── App.tsx                # 根组件（路由、设置向导）
│   ├── index.css              # 全局样式
│   ├── api/
│   │   ├── chat.ts            # 会话、对话、文件 API
│   │   └── providers.ts       # 提供商 API
│   ├── components/
│   │   ├── ChatPage.tsx       # 主聊天页面（会话列表、消息流、文件树）
│   │   ├── SetupWizard.tsx    # 首次设置向导（配置 LLM Provider）
│   │   └── settings/
│   │       ├── SettingsDrawer.tsx  # 设置抽屉
│   │       └── ProvidersPanel.tsx  # 提供商管理面板
│   └── assets/                # 静态资源
└── dist/                      # 构建产物（gitignore）
```

---

## 核心组件

### App.tsx

根组件，负责：

1. **初始化检查**：启动时调用 `fetchProviders()`，若没有 `category="chat"` 的提供商，显示 `SetupWizard`
2. **路由分发**：
   - `needsSetup=true` → 显示 `SetupWizard`
   - `needsSetup=false` → 显示 `ChatPage`
3. **全局配置**：Ant Design 的 `ConfigProvider`（中文 locale、主题配置）

### ChatPage.tsx

主聊天页面，包含三个区域：

#### 左侧边栏（会话列表）

- **会话列表**：使用 `@ant-design/x` 的 `Conversations` 组件
- **模型选择器**：当前会话使用的模型
- **设置按钮**：打开设置抽屉
- **文件树开关**：显示/隐藏右侧文件树

会话列表按日期分组（今天、昨天、更早），支持创建、删除、切换会话。

#### 中间区域（聊天内容）

- **消息列表**：使用 `@ant-design/x` 的 `Bubble` 组件
- **消息类型**：
  - `user`：用户消息
  - `assistant`：AI 回复（支持 Markdown、thinking、tool_calls）
  - `tool_group`：工具调用组（折叠展示）
  - `task_plan`：任务计划（多任务编排时显示）
- **输入框**：使用 `@ant-design/x` 的 `Sender` 组件
- **流式渲染**：`token` 事件实时追加到当前 assistant 消息

#### 右侧边栏（文件树，可选）

- **文件树**：使用 Ant Design 的 `Tree` 组件
- **文件操作**：上传、下载
- **文件树数据**：通过 `/api/fs/tree` 获取

### SetupWizard.tsx

首次设置向导，Modal 形式：

1. **预设选择**：提供 5 个预设选项：
   - 阿里云百炼（`dashscope`）：使用官方 URL，自动填充模型列表
   - OpenAI（`openai`）：使用官方 URL，自动填充模型列表
   - Anthropic（`anthropic`）：使用官方 URL，自动填充模型列表
   - Google（`google`）：使用官方 URL，自动填充模型列表
   - 自定义：允许手动输入所有配置项
2. **表单填写**：
   - Provider 名称
   - API Key
   - API Base URL：前 4 个预设选择时自动隐藏（使用预设的官方 URL），自定义选项显示
   - 模型列表（标签输入）
3. **提交**：调用 `createProvider()` API，非自定义预设使用预设的 `api_base`，自定义使用用户输入，成功后关闭向导

### SettingsDrawer.tsx

设置抽屉，包含：

- **提供商管理**：`ProvidersPanel` 组件
- **其他设置项**（预留）

### ProvidersPanel.tsx

提供商管理面板，包含：

- **提供商列表**：显示所有已配置的 Provider（名称、分类、API Base URL、模型列表）
- **添加/编辑**：使用 `ProviderFormModal` 组件，支持预设快速填充（与 `SetupWizard` 相同的 5 个预设）
- **删除**：支持删除 Provider

### ProviderFormModal.tsx

Provider 表单 Modal，用于添加或编辑 Provider：

- **预设选择**：仅在添加模式下显示，提供与 `SetupWizard` 相同的 5 个预设选项
- **表单字段**：Provider 名称、用途分类、API Key、API Base URL（预设选择时自动隐藏）、模型列表
- **编辑模式**：编辑时隐藏预设选择，始终显示 API Base URL 输入框

---

## API 客户端（api/chat.ts）

### 类型定义

| 类型 | 说明 |
|---|---|
| `Provider` | LLM 提供商（name, category, api_base, models） |
| `Session` | 会话（id, model, messages, created_at） |
| `SessionSummary` | 会话摘要（id, model, title, created_at, message_count） |
| `FileNode` | 文件树节点（name, type, children） |
| `PlanEvent` | 任务计划事件（type: "plan", tasks） |
| `ToolCallEvent` | 工具调用事件（type: "tool_call", id, name, args） |
| `ToolResultEvent` | 工具结果事件（type: "tool_result", id, content） |
| `WorkerStartEvent` | Worker 开始事件（type: "worker_start", task_id） |
| `WorkerEventWrapper` | Worker 事件包装（type: "worker_event", task_id, event） |
| `WorkerDoneEvent` | Worker 完成事件（type: "worker_done", task_id, result） |

### API 函数

| 函数 | 说明 |
|---|---|
| `listSessions()` | 获取会话列表 |
| `fetchProviders()` | 获取提供商列表 |
| `createSession(model)` | 创建新会话 |
| `getSession(sessionId)` | 获取会话详情 |
| `deleteSession(sessionId)` | 删除会话 |
| `switchModel(sessionId, model)` | 切换会话模型 |
| `generateTitle(sessionId, content)` | 生成会话标题 |
| `streamChat(...)` | 流式对话（SSE） |
| `fetchFileTree(path, depth)` | 获取文件树 |
| `uploadFile(file, dir)` | 上传文件 |
| `downloadFile(path)` | 下载文件 |

### streamChat 函数

核心流式对话函数，使用 Fetch API 的 `ReadableStream`：

1. 发起 `POST /api/sessions/{sessionId}/chat` 请求
2. 读取 `response.body`（ReadableStream）
3. 逐行解析 SSE 格式（`data: {json}\n\n`）
4. 根据 `event.type` 调用对应回调：
   - `token` → `onToken`
   - `thinking` → `onThinking`
   - `tool_call` → `onToolCall`
   - `tool_result` → `onToolResult`
   - `plan` → `onPlan`
   - `worker_start` → `onWorkerStart`
   - `worker_event` → `onWorkerEvent`
   - `worker_done` → `onWorkerDone`
   - `[DONE]` → `onDone`

返回 `AbortController`，支持取消请求。

---

## SSE 事件处理

### 事件类型映射

| 后端事件类型 | 前端处理 | UI 展示 |
|---|---|---|
| `plan` | `onPlan` | 任务计划卡片（多任务时） |
| `worker_start` | `onWorkerStart` | Worker 开始标记 |
| `worker_event` | `onWorkerEvent` | Worker 内部事件（token、tool_call 等） |
| `worker_done` | `onWorkerDone` | Worker 完成标记 |
| `thinking` | `onThinking` | Thinking 组件（@ant-design/x） |
| `token` | `onToken` | 实时追加到当前消息 |
| `tool_call` | `onToolCall` | 工具调用卡片（折叠） |
| `tool_result` | `onToolResult` | 工具结果（折叠） |
| `done` | `onDone` | 标记消息完成，停止流式渲染 |

### 消息状态管理

- **流式渲染中**：`loading=true`，消息内容实时追加
- **流式完成**：`loading=false`，消息内容固定
- **工具调用**：折叠展示，点击展开查看参数和结果

---

## 状态管理

使用 React Hooks 进行本地状态管理：

- **会话列表**：`conversations`（会话摘要列表）
- **当前会话**：`activeKey`（会话 ID）
- **消息列表**：`messages`（按会话 ID 索引的 Map）
- **文件树**：`fileTree`（FileNode 结构）
- **提供商列表**：`providers`（Provider 数组）
- **模型列表**：`allModels`（ModelItem 数组）
- **当前模型**：`selectedModel`（模型 ID）

持久化：
- `activeSessionId` 存储在 `localStorage`，页面刷新后恢复

---

## 开发环境配置（vite.config.ts）

### 开发服务器

- **端口**：10601
- **代理配置**：
  - `/api` → `http://python-service:10600`（HTTP API）
  - `/ws` → `ws://python-service:10600`（WebSocket，预留）

### 构建配置

- **入口**：`src/main.tsx`
- **输出**：`dist/`
- **插件**：`@vitejs/plugin-react-swc`（SWC 编译）

---

## 生产环境部署

### 容器构建（Dockerfile）

多阶段构建：

**Stage 1（builder）**
1. 基于 `node:20-alpine`
2. 拷贝 `package.json`，执行 `npm ci`
3. 拷贝源码，执行 `npm run build`
4. 生成 `dist/` 目录

**Stage 2（nginx）**
1. 基于 `nginx:alpine`
2. 拷贝 `dist/` 到 `/usr/share/nginx/html`
3. 拷贝 `nginx.conf` 到 `/etc/nginx/conf.d/default.conf`
4. 暴露端口 `10601`

### Nginx 配置（nginx.conf）

- **静态文件**：`/` → `/usr/share/nginx/html`（SPA 路由支持 `try_files`）
- **API 代理**：`/api` → `http://python-service:10600`
- **WebSocket 代理**：`/ws` → `http://python-service:10600`（预留）
- **健康检查**：`/health` → 返回 `200 "healthy\n"`

---

## 在项目中的位置

### 服务拓扑

Web PC 是 PandaEvo 六个 Docker 服务之一，运行于 `10601` 端口。

```
desktop（Tauri 桌面引导器）
  └─ 管理生命周期、健康监控
        ↓
web-pc（:10601）── HTTP API ──► python-service（:10600）
  └─ React SPA                        ├─ 会话管理
  └─ Nginx 反向代理                   ├─ LLM 对话编排
                                      ├─ 工具调用
                                      └─ MCP 集成
```

### Desktop 集成

desktop bootstrap 模块对 web-pc 有以下依赖：

| 位置 | 行为 |
|---|---|
| `config.rs` | 定义 `ports::WEB_PC = 10601` |
| `runner_prod.rs` | Phase 5 `health_wait`：等待 10601 健康 |
| `runner_dev.rs` | Phase 4 `evolution_start`：与 evolution-core、python-service 一同 `--build` 启动 |
| `watchdog.rs` | 不直接检查 web-pc（通过 python-service 间接监控） |

### python-service 集成

web-pc 通过 HTTP API 与 python-service 通信：

- **开发环境**：Vite proxy 将 `/api` 转发到 `http://python-service:10600`
- **生产环境**：nginx 反向代理 `/api` 到 `http://python-service:10600`

所有 API 请求统一使用 `/api` 前缀，由代理层转发到后端。

---

## UI 组件库使用

### Ant Design 组件

| 组件 | 用途 |
|---|---|
| `Conversations` | 会话列表（@ant-design/x） |
| `Bubble` | 消息气泡（@ant-design/x） |
| `Sender` | 输入框（@ant-design/x） |
| `Think` | Thinking 展示（@ant-design/x） |
| `XMarkdown` | Markdown 渲染（@ant-design/x-markdown） |
| `Tree` | 文件树 |
| `Drawer` | 设置抽屉 |
| `Modal` | 设置向导 |
| `Form` | 表单（提供商配置） |
| `Select` | 模型选择器 |
| `Upload` | 文件上传 |
| `Button` | 按钮 |
| `Tag` | 标签（模型列表） |

### 样式方案

使用 `antd-style` 的 `createStyles` 进行 CSS-in-JS 样式定义，支持主题 token 访问。

---

## 浏览器兼容性

- **现代浏览器**：Chrome、Firefox、Safari、Edge（最新 2 个版本）
- **特性要求**：
  - Fetch API
  - ReadableStream API（SSE 流式读取）
  - ES2020+ 语法支持

---

## 性能优化

- **代码分割**：Vite 自动进行路由级代码分割
- **构建优化**：生产构建启用压缩、Tree Shaking
- **静态资源**：通过 Nginx 提供静态文件服务
- **流式渲染**：SSE 流式接收，避免大响应阻塞
