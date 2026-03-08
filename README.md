# ChatGuardian

基于 LLM 的群聊/私聊规则检测与提醒系统（MVP骨架）。

## 当前已实现（第三阶段）

- 抽象领域模型：消息事件、规则 DSL、参数提取、反馈、用户记忆。
- 消息内容链：`ChatMessage.contents` 支持文本/图片/Mention 片段，支持 `reply_from` 嵌套回复消息。
- Adapter 插件体系：支持 `onebot`、`telegram`、`wechat`、`feishu`，其中 `onebot`（`aiocqhttp`）已实现。
- 规则检测引擎：自动拼接上下文消息 + 规则分批并行调用 LLM。
- LLM 调用链：已接入 LangChain（`langchain_openai.ChatOpenAI`），支持 OpenAI 兼容 API 与本地/云端网关。
- 一句话规则生成：内置生成后端 + 外部自定义提示词后端（可选）。
- 通知链路：邮件通知抽象 + 外部 API Hook 调用抽象。
- 本人发言识别：触发参与话题/相关群友记忆写入。
- 建议系统：新规则建议 + 规则改进建议（基于记忆与反馈）。
- API + MCP 风格入口：`/rule-generation` 与 `/mcp/tools/generate-rule`。
- MVP WebUI 入口：`/ui`（轻量说明页，API联调入口）。

> 设计原则：只做抽象能力，不把任何示例场景写死。

## 目录结构

```
chat_guardian/
	api/
		app.py
		schemas.py
	adapters.py
	domain.py
	repositories.py
	services.py
	settings.py
	main.py
tests/
	test_api_smoke.py
	test_detection_engine.py
	test_rule_generation.py
```

## 本地运行

1. 安装依赖（后端）

```bash
poetry install
```

2. 构建前端（单端口部署）

```bash
cd frontend
npm ci --legacy-peer-deps
npm run build
```

> 若需本地调试，可运行 `npm run dev`（默认代理到 `http://localhost:8000`），生产构建产物将由后端以 `/app/*` 路由提供。

3. 准备环境变量

```bash
copy .env.example .env
```

> LLM 调用统一使用 LangChain，并支持两种后端：
> - `openai_compatible`：OpenAI 官方与兼容平台（如 DeepSeek）
> - `ollama`：本地 Ollama 服务

> OpenAI 兼容后端示例（OpenAI / DeepSeek）：
> - `CHAT_GUARDIAN_LLM_LANGCHAIN_BACKEND=openai_compatible`
> - `CHAT_GUARDIAN_LLM_LANGCHAIN_MODEL=gpt-4o-mini`（或 DeepSeek 模型名）
> - `CHAT_GUARDIAN_LLM_LANGCHAIN_API_KEY=your_key`
> - `CHAT_GUARDIAN_LLM_LANGCHAIN_API_BASE=https://api.deepseek.com/v1`（DeepSeek 示例）

> Ollama 后端示例：
> - `CHAT_GUARDIAN_LLM_LANGCHAIN_BACKEND=ollama`
> - `CHAT_GUARDIAN_LLM_LANGCHAIN_MODEL=qwen2.5:7b`
> - `CHAT_GUARDIAN_LLM_OLLAMA_BASE_URL=http://localhost:11434`

额外只读元信息可通过环境变量注入：

- `CHAT_GUARDIAN_APP_NAME`：项目名称（只读）
- `CHAT_GUARDIAN_ENVIRONMENT`：运行环境（dev/prod，仅影响只读逻辑如 CORS）

4. 启动服务

```bash
poetry run uvicorn chat_guardian.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
```

5. 访问

- Swagger: `http://127.0.0.1:8000/docs`
- Web UI（单端口构建版）: `http://127.0.0.1:8000/app/`
- 旧版 MVP 说明页: `http://127.0.0.1:8000/ui`

## 临时 Gradio UI（联调）

1. 启动 API（保持运行）

```bash
poetry run uvicorn chat_guardian.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
```

2. 访问内嵌 Gradio 面板（单端口）

- `http://127.0.0.1:8000/gradio`

## Docker 运行

```bash
docker compose up --build
```

> Docker 镜像构建时会自动打包前端产物并通过 FastAPI 提供 `/app/*` 路由，同时内置 `/health` 健康检查，便于容器编排监控。

## 核心 API

- `POST /rules`：创建或更新结构化检测规则。
- 检测触发：仅由 adapter 输入消息事件触发，不再提供手动 `/detect` 接口。
- `POST /feedback`：提交检测结果评分与意见。
- `GET /suggestions/new-rules/{user_id}`：生成新规则建议。
- `GET /suggestions/rule-improvements/{rule_id}`：生成规则改进建议。
- `POST /rule-generation`：一句话生成规则（内置/外部后端）。
- `POST /mcp/tools/generate-rule`：MCP 风格规则生成入口。
- `GET /llm/health`：返回当前 LLM 后端诊断信息，并可执行最小 ping 探活（`do_ping` 参数）。
- `POST /adapters/start`：按配置启动已启用 adapter（可反复调用）。
- `POST /adapters/stop`：停止已启用 adapter。

## 扩展点

- 消息平台：补全 `telegram` / `wechat` / `feishu` 插件实现。
- LLM：替换 `LLMClient` 实现（云端、本地模型统一适配）。
- 存储：替换 `*Repository`、`ChatHistoryStore` 等为 SQLAlchemy ORM 实现。
- 通知：新增 `Notifier` 实现（邮件以外渠道）。
- 外部自动化：通过 `ExternalHookDispatcher` 注入自定义 API。

## 测试

```bash
poetry run pytest -q
```
