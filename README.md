# ChatGuardian

基于 LLM 的群聊/私聊规则检测与提醒系统（MVP骨架）。

## 当前已实现（第二阶段）

- 抽象领域模型：消息事件、规则 DSL、参数提取、反馈、用户记忆。
- 消息内容链：`ChatMessage.contents` 支持文本/图片/Mention 片段，支持 `reply_from` 嵌套回复消息。
- Adapter 插件体系：支持 `onebot`、`telegram`、`wechat`、`feishu`，其中 `onebot`（`aiocqhttp`）已实现。
- 规则检测引擎：自动拼接上下文消息 + 规则分批并行调用 LLM。
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

1. 安装依赖

```bash
poetry install
```

2. 准备环境变量

```bash
copy .env.example .env
```

3. 启动服务

```bash
poetry run uvicorn chat_guardian.api.app:create_app --factory --reload --host 0.0.0.0 --port 8000
```

4. 访问

- Swagger: `http://127.0.0.1:8000/docs`
- MVP UI: `http://127.0.0.1:8000/ui`

## Docker 运行

```bash
docker compose up --build
```

## 核心 API

- `POST /rules`：创建或更新结构化检测规则。
- `POST /detect`：输入消息事件并触发检测主流程。
- `POST /feedback`：提交检测结果评分与意见。
- `GET /suggestions/new-rules/{user_id}`：生成新规则建议。
- `GET /suggestions/rule-improvements/{rule_id}`：生成规则改进建议。
- `POST /rule-generation`：一句话生成规则（内置/外部后端）。
- `POST /mcp/tools/generate-rule`：MCP 风格规则生成入口。
- `POST /adapters/start`：按配置启动已启用 adapter（可反复调用）。
- `POST /adapters/stop`：停止已启用 adapter。

## 扩展点

- 消息平台：补全 `telegram` / `wechat` / `feishu` 插件实现。
- LLM：替换 `LLMClient` 实现（云端、本地模型统一适配）。
- 存储：替换 `InMemory*Repository` 为 SQLAlchemy ORM 实现。
- 通知：新增 `Notifier` 实现（邮件以外渠道）。
- 外部自动化：通过 `ExternalHookDispatcher` 注入自定义 API。

## 测试

```bash
poetry run pytest -q
```
