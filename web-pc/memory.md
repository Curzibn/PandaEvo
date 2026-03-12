# 前端模块记忆（web-pc）

## 模块概况

- 定位：PandaEvo 前端单页应用，唯一职责是提供用户界面
- 技术栈：React 19 + TypeScript 5.9 + Vite 7 + Ant Design 6 + Ant Design X + Tauri API
- 样式方案：antd-style（CSS-in-JS），使用 `createStyles(({ token, css }) => (...))`
- HTTP 客户端：原生 Fetch API
- 部署：多阶段 Dockerfile（builder + nginx），开发端口 10601，生产端口由 Nginx 提供

## 架构决策

- [2026-03-11] 状态管理仅用 React Hooks（useState/useContext），不引入 Redux/Zustand 等库
- [2026-03-11] 所有 API 调用集中在 `src/api/`，禁止在组件中直接写 `fetch()`
- [2026-03-11] 样式全部通过 antd-style `createStyles` 管理，禁止 CSS 文件和硬编码颜色/尺寸
- [2026-03-11] SSE 使用 Fetch API `ReadableStream` + `TextDecoder` 解析 `data: {json}\n\n` 格式
- [2026-03-11] `streamChat()` 默认发送 `route_mode: "auto"`，由后端决定 `direct/orchestrator` 执行路径
- [2026-03-12] 设置中心统一放在 `SettingsDrawer`，固定为四个面板：大模型、用途、MCP 服务器、技能
- [2026-03-12] 对话模型列表优先使用 purpose=`chat` 绑定结果；未配置时回退到全部 provider 模型
- [2026-03-12] 会话导出采用双通道：Tauri 环境调用系统保存对话框，浏览器环境走下载链接
- [2026-03-12] 前端启动后建立 `/ws` 连接，收到 `reload` 事件触发页面刷新

## 开发约定

- 组件文件：PascalCase 命名，Props 接口统一命名为 `interface Props`
- 页面组件放 `src/components/`，子组件放 `src/components/{feature}/`
- API 客户端分文件：`chat.ts`（会话/流式对话/文件树与上传下载/导出）、`providers.ts`（提供商）、`purposes.ts`（用途模型绑定）、`mcp.ts`（MCP 服务器管理）、`skills.ts`（技能配置）
- 持久化状态用 `localStorage`，多组件共享用 Context API 或 Props 提升
- 流式 API 函数必须返回 `AbortController` 以支持取消

## SSE 事件类型（后端 → 前端）

| 事件 | 前端处理 |
|---|---|
| `plan` | 任务计划卡片 |
| `route` | 路由决策展示（`direct`/`orchestrator`） |
| `worker_start`/`worker_event`/`worker_done` | Worker 生命周期标记 |
| `thinking` | Thinking 组件 |
| `token` | 实时追加到消息内容 |
| `tool_call`/`tool_result` | 折叠展示工具调用 |
| `done` | 流结束，含执行状态（`success/failed/partial`）与 PR 链接 |

## 架构边界

- 不含后端业务逻辑（业务在 python-service）
- 不直接访问数据库（所有数据通过 API）
- 不管理 Docker 容器（desktop 模块负责）
- evolution 类型任务由后端透传到 evolution-core，前端无需感知
