---
name: web-pc-development
description: Guide development of the PandaEvo web-pc module, a React-based frontend SPA built with TypeScript, Vite, and Ant Design. Covers component structure, API integration, SSE streaming, state management, and deployment. Use when working on any file under web-pc/, adding new UI components, extending API integration, modifying chat flow, or debugging build/deployment issues.
---

# Web PC 模块开发指南

## 模块定位与边界

Web PC 是 PandaEvo 的**前端单页应用（SPA）**，唯一职责：提供用户界面，包括会话管理、LLM 对话、文件浏览、设置管理等功能，通过 HTTP API 与 python-service 后端通信。

**严格边界**：

- 不包含后端业务逻辑——业务逻辑在 python-service
- 不直接访问数据库——所有数据通过 API 获取
- 不包含 Docker 容器管理——由 desktop 模块管理
- 不包含代码审查逻辑——evolution 类型任务由后端转发到 evolution-core
- 状态管理使用 React Hooks，不引入 Redux/Zustand 等状态管理库

---

## 技术栈

| 层 | 技术 | 约束 |
|---|---|---|
| 前端框架 | React 19 | 使用函数组件 + Hooks，禁止类组件 |
| 语言 | TypeScript 5.9 | 严格类型检查，禁止 `any`（除非必要） |
| 构建工具 | Vite 7 | 使用 Vite 插件，不自定义 Webpack 配置 |
| UI 组件库 | Ant Design 6 | 优先使用 Ant Design 组件，自定义组件使用 `antd-style` |
| 聊天组件 | @ant-design/x | Bubble、Conversations、Sender、Think |
| Markdown 渲染 | @ant-design/x-markdown | 统一使用此组件渲染 Markdown |
| 样式方案 | antd-style | CSS-in-JS，使用 `createStyles`，支持主题 token |
| HTTP 客户端 | Fetch API | 不使用 axios，统一使用原生 Fetch |
| 部署服务器 | Nginx | 生产环境使用 Nginx，不自定义 Node.js 服务器 |

---

## 模块结构

```
web-pc/
├── package.json               # 依赖声明
├── vite.config.ts             # Vite 配置
├── tsconfig.json              # TypeScript 配置
├── Dockerfile                 # 容器构建
├── nginx.conf                 # Nginx 配置
├── index.html                 # HTML 入口
└── src/
    ├── main.tsx               # React 入口
    ├── App.tsx                # 根组件
    ├── api/                   # API 客户端
    └── components/            # UI 组件
```

---

## 核心设计模式

### 1. API 客户端统一管理

所有 API 调用集中在 `src/api/` 目录：

- `chat.ts`：会话、对话、文件相关 API
- `providers.ts`：提供商相关 API

**禁止**在组件中直接写 `fetch()`，必须通过 API 客户端函数调用。

### 2. SSE 流式处理

`streamChat()` 函数使用 Fetch API 的 `ReadableStream` 处理 SSE：

```typescript
const reader = res.body.getReader()
const decoder = new TextDecoder()
let buf = ''
while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buf += decoder.decode(value, { stream: true })
  // 解析 SSE 格式：data: {json}\n\n
}
```

**新增流式 API 时**：
1. 在 `src/api/` 创建对应函数
2. 使用相同的 SSE 解析逻辑
3. 返回 `AbortController` 支持取消

### 3. 组件状态管理

使用 React Hooks 进行本地状态管理：

- **会话列表**：`useState<ConvItem[]>`
- **当前会话**：`useState<string>`
- **消息列表**：`useState<Record<string, Message[]>>`
- **流式状态**：`useState<boolean>`

**禁止**引入 Redux、Zustand 等状态管理库，复杂状态通过 Context API 或组件提升处理。

### 4. 类型安全

所有 API 响应、事件、组件 Props 必须定义 TypeScript 类型：

```typescript
export interface Session {
  id: string
  model: string
  messages: Message[]
  created_at: string
}
```

**禁止**使用 `any`，除非确实无法推断类型（如动态 JSON 解析）。

---

## 组件开发规范

### 组件文件组织

- **页面组件**：`src/components/`（如 `ChatPage.tsx`）
- **子组件**：`src/components/{feature}/`（如 `settings/SettingsDrawer.tsx`）
- **API 客户端**：`src/api/`

### 组件命名

- **文件名**：PascalCase（如 `ChatPage.tsx`）
- **组件名**：与文件名一致（如 `export default function ChatPage()`）
- **Props 接口**：`Props`（如 `interface Props { ... }`）

### 样式定义

使用 `antd-style` 的 `createStyles`：

```typescript
const useStyle = createStyles(({ token, css }) => ({
  container: css`
    padding: ${token.paddingLG}px;
    background: ${token.colorBgContainer};
  `,
}))
```

**禁止**使用 CSS 文件或内联样式（`style={{}}` 仅用于动态样式）。

### 事件处理

- **流式事件**：通过回调函数传递（如 `onToken`、`onDone`）
- **用户交互**：使用 Ant Design 组件的 `onClick`、`onChange` 等
- **错误处理**：使用 `try/catch` 或 Promise `.catch()`

---

## API 集成规范

### API 函数签名

所有 API 函数应遵循以下模式：

```typescript
export async function apiFunction(...args): Promise<ResponseType> {
  const res = await fetch(`${BASE}/endpoint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...args }),
  })
  if (!res.ok) throw new Error('Failed to ...')
  return res.json()
}
```

### 错误处理

- **网络错误**：抛出 `Error`，由调用方处理
- **业务错误**：后端返回错误信息，前端显示 `message.error()`
- **流式错误**：通过 `onError` 回调传递

### 流式 API

流式 API 函数应：

1. 返回 `AbortController` 支持取消
2. 通过回调函数传递事件（`onToken`、`onDone` 等）
3. 正确处理 SSE 格式（`data: {json}\n\n`）

---

## SSE 事件处理规范

### 事件类型映射

后端事件类型与前端处理函数一一对应：

| 后端事件 | 前端回调 | UI 展示 |
|---|---|---|
| `plan` | `onPlan` | 任务计划卡片 |
| `worker_start` | `onWorkerStart` | Worker 开始标记 |
| `worker_event` | `onWorkerEvent` | Worker 内部事件 |
| `worker_done` | `onWorkerDone` | Worker 完成标记 |
| `thinking` | `onThinking` | Thinking 组件 |
| `token` | `onToken` | 实时追加到消息 |
| `tool_call` | `onToolCall` | 工具调用卡片 |
| `tool_result` | `onToolResult` | 工具结果 |
| `done` | `onDone` | 标记完成 |

### 消息流式渲染

- **流式渲染中**：`loading=true`，消息内容通过 `onToken` 实时追加
- **流式完成**：`loading=false`，消息内容固定，停止追加
- **工具调用**：折叠展示，点击展开查看参数和结果

**新增事件类型时**：
1. 在 `src/api/chat.ts` 定义类型
2. 在 `streamChat()` 中添加解析逻辑
3. 在 `ChatPage.tsx` 中添加 UI 展示逻辑

---

## 状态管理规范

### 本地状态

使用 `useState` 管理组件本地状态：

```typescript
const [sessions, setSessions] = useState<SessionSummary[]>([])
const [activeKey, setActiveKey] = useState<string>('')
```

### 持久化

需要持久化的状态使用 `localStorage`：

```typescript
useEffect(() => {
  const saved = localStorage.getItem('activeSessionId')
  if (saved) setActiveKey(saved)
}, [])

useEffect(() => {
  if (activeKey) localStorage.setItem('activeSessionId', activeKey)
}, [activeKey])
```

### 状态提升

多个组件共享的状态通过 Props 传递或 Context API：

- **简单共享**：通过 Props 传递
- **复杂共享**：使用 `createContext` + `useContext`

---

## 样式规范

### 使用 antd-style

所有样式使用 `antd-style` 的 `createStyles`：

```typescript
const useStyle = createStyles(({ token, css }) => ({
  container: css`
    padding: ${token.paddingLG}px;
    background: ${token.colorBgContainer};
  `,
}))

function Component() {
  const { styles } = useStyle()
  return <div className={styles.container}>...</div>
}
```

### 主题 Token

优先使用 Ant Design 的主题 token：

- `token.colorPrimary`
- `token.colorBgContainer`
- `token.paddingLG`
- `token.borderRadius`

**禁止**硬编码颜色值或尺寸。

### 响应式设计

使用 Ant Design 的响应式工具：

- `Grid` 组件的 `xs`、`sm`、`md`、`lg`、`xl` 属性
- `useBreakpoint()` Hook

---

## 构建与部署规范

### 开发环境

```bash
npm run dev
```

启动 Vite 开发服务器，端口 10601，自动代理 `/api` 到 `http://python-service:10600`。

### 生产构建

```bash
npm run build
```

生成 `dist/` 目录，包含：
- `index.html`
- `assets/`（JS、CSS 文件）

### 容器构建

Dockerfile 采用多阶段构建：

1. **Stage 1（builder）**：安装依赖、构建应用
2. **Stage 2（nginx）**：拷贝构建产物、配置 Nginx

**修改构建流程时**：
1. 修改 `Dockerfile`（如需要）
2. 修改 `vite.config.ts`（如需要）
3. 同步更新 `ARCHITECTURE.md`「容器构建」节

### Nginx 配置

`nginx.conf` 负责：

- 静态文件服务（SPA 路由支持）
- API 代理（`/api` → `http://python-service:10600`）
- WebSocket 代理（`/ws` → `http://python-service:10600`，预留）

**修改 Nginx 配置时**：
1. 修改 `nginx.conf`
2. 同步更新 `ARCHITECTURE.md`「Nginx 配置」节

---

## 常见开发场景

### 添加新 API 端点

1. 在 `src/api/chat.ts` 或 `src/api/providers.ts` 添加函数
2. 定义 TypeScript 类型（请求/响应）
3. 在组件中调用函数
4. 下载类能力统一在 API 层封装（如 `exportSession(sessionId)`），组件层仅处理触发与反馈

### 添加新 UI 组件

1. 在 `src/components/` 创建组件文件
2. 使用 `antd-style` 定义样式
3. 定义 Props 接口
4. 导出组件

### 修改聊天流程

`ChatPage.tsx` 是核心组件，修改时注意：

- **消息状态**：`loading`、`content` 的管理
- **流式渲染**：`onToken` 回调的处理
- **工具调用**：`tool_group` 消息的展示

### 添加新事件类型

1. 在 `src/api/chat.ts` 定义事件类型
2. 在 `streamChat()` 中添加解析逻辑
3. 在 `ChatPage.tsx` 中添加 UI 展示逻辑

### 修改设置向导

`SetupWizard.tsx` 负责首次配置，修改时注意：

- **预设列表**：`PRESETS` 常量，当前包含 5 个预设：
  - 阿里云百炼（`dashscope`）：使用官方 URL `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - OpenAI（`openai`）：使用官方 URL `https://api.openai.com/v1`
  - Anthropic（`anthropic`）：使用官方 URL `https://api.anthropic.com/v1`
  - Google（`google`）：使用官方 URL `https://generativelanguage.googleapis.com/v1beta`
  - 自定义（`''`）：允许用户手动输入 API Base URL
- **API Base URL 显示逻辑**：前 4 个预设选择时自动隐藏 API Base URL 输入框（使用预设的官方 URL），自定义选项显示输入框
- **表单验证**：Ant Design Form 的 `rules`
- **提交逻辑**：调用 `createProvider()` API，非自定义预设使用预设的 `api_base`，自定义使用用户输入

---

## 架构文档同步规范

**当以下变更发生后，必须同步更新 `ARCHITECTURE.md` 和本 SKILL.md**：

| 变更类型 | 需更新的内容 |
|---|---|
| 新增/删除组件 | ARCHITECTURE.md「核心组件」节；SKILL.md「组件开发规范」节 |
| 新增 API 端点 | ARCHITECTURE.md「API 客户端」节；SKILL.md「添加新 API 端点」场景 |
| 新增事件类型 | ARCHITECTURE.md「SSE 事件处理」节；SKILL.md「添加新事件类型」场景 |
| 修改构建流程 | ARCHITECTURE.md「容器构建」节；SKILL.md「构建与部署规范」节 |
| 修改 Nginx 配置 | ARCHITECTURE.md「Nginx 配置」节；SKILL.md「Nginx 配置」节 |
| 新增依赖 | ARCHITECTURE.md「技术栈」表；SKILL.md「技术栈」表 |
| 修改状态管理 | ARCHITECTURE.md「状态管理」节；SKILL.md「状态管理规范」节 |

更新原则：**先改代码，后改文档**，在同一次提交中完成，保持文档与代码一致。
