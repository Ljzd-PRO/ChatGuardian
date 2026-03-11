"""
FastAPI 应用与路由定义。

此模块负责把内部服务装配为可被 HTTP 调用的 API，并提供一个极简的 WebUI 入口用于调试。
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import uuid as _uuid
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse

from chat_guardian.agent import AdminAgent, TOOL_DISPLAY_NAMES
from chat_guardian.adapters import AdapterManager, build_adapters_from_settings
from chat_guardian.api.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    RuleGenerateRequest,
    SuggestResponse,
)
from chat_guardian.domain import (
    ChatEvent,
    DetectionRule,
    Feedback,
)
from chat_guardian.notifiers import (
    build_notifiers_from_settings,
)
from chat_guardian.mcp import (
    ChatGuardianMCPService,
    ChatGuardianOperations,
    OperationError,
    normalize_mcp_transport,
)
from chat_guardian.repositories import (
    AdminCredentialRepository,
    AgentSessionRepository,
    ChatHistoryStore,
    DetectionResultRepository,
    FeedbackRepository,
    MemoryRepository,
    RuleRepository,
    SettingsRepository,
)
from chat_guardian.rule_authoring import (
    ExternalPromptRuleGenerationBackend,
    InternalRuleGenerationBackend,
    RuleAuthoringService,
)
from chat_guardian.services import (
    build_llm_client,
    ContextWindowService,
    DetectionEngine,
    ExternalHookDispatcher,
    UserMemoryService,
    SuggestionService,
)
from chat_guardian.settings import settings, Settings

ENV_ONLY_KEYS = frozenset({"database_url", "app_name", "environment"})


class AgentChatRequest(BaseModel):
    messages: list[dict[str, str]]
    session_id: str | None = None


class CreateSessionRequest(BaseModel):
    title: str = ""


class UpdateSessionTitleRequest(BaseModel):
    title: str


class SaveMessageRequest(BaseModel):
    role: Literal['user', 'assistant']
    content: str
    tool_calls: list | None = None
    elapsed_ms: int | None = None


class DeleteMessagePairRequest(BaseModel):
    user_message_id: int


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """应用生命周期管理：启动时自动启动 adapters，关闭时自动停止。"""
    import signal
    import threading
    from loguru import logger
    container = app.state.container
    mcp_service = getattr(container, "mcp_service", None)
    mcp_http_task: asyncio.Task | None = None

    # 安装信号处理器以记录用户主动停止程序的操作（仅在主线程中有效）
    _prev_sigint = signal.getsignal(signal.SIGINT)
    _prev_sigterm = signal.getsignal(signal.SIGTERM)
    _shutdown_by_signal = False

    def _on_sigint(sig: int, frame: object) -> None:
        nonlocal _shutdown_by_signal
        _shutdown_by_signal = True
        logger.warning("👋 接收到 CTRL+C 中断信号，用户正在停止程序...")
        if callable(_prev_sigint):
            _prev_sigint(sig, frame)  # type: ignore[arg-type]

    def _on_sigterm(sig: int, frame: object) -> None:
        nonlocal _shutdown_by_signal
        _shutdown_by_signal = True
        logger.warning("⚡ 接收到 SIGTERM 终止信号，程序即将停止...")
        if callable(_prev_sigterm):
            _prev_sigterm(sig, frame)  # type: ignore[arg-type]

    _is_main_thread = threading.current_thread() is threading.main_thread()
    if _is_main_thread:
        signal.signal(signal.SIGINT, _on_sigint)
        signal.signal(signal.SIGTERM, _on_sigterm)

    # 启动
    if container.adapter_manager.adapters:
        adapter_names = [adapter.name for adapter in container.adapter_manager.adapters]
        logger.info(f"🚀 应用启动，自动启动 adapters: {adapter_names}")
        await container.adapter_manager.start_all()
    if mcp_service and settings.mcp_http_enabled:
        transport = normalize_mcp_transport(settings.mcp_http_transport)
        try:
            mcp_http_task = await mcp_service.start_http_server(
                transport=transport,
                host=settings.mcp_http_host,
                port=settings.mcp_http_port,
                path=settings.mcp_http_path,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("⚠️ 启动 MCP HTTP 传输失败: {}", exc)
    try:
        yield
    finally:
        # 关闭
        if _shutdown_by_signal:
            logger.info("🛑 用户停止了程序，正在关闭应用...")
        else:
            logger.info("🛑 应用关闭，停止所有 adapters")
        await container.adapter_manager.stop_all()
        if mcp_service:
            await mcp_service.stop_http_server()
        if mcp_http_task:
            mcp_http_task.cancel()
            with suppress(asyncio.CancelledError):
                await mcp_http_task
        logger.info("✅ 应用程序已成功停止")

        if _is_main_thread:
            signal.signal(signal.SIGINT, _prev_sigint)
            signal.signal(signal.SIGTERM, _prev_sigterm)


class AppContainer:
    def __init__(self):
        """简单的应用容器，实例化仓储与服务。

        该容器用于在 `create_app` 中创建单例服务实例，便于路由直接使用。
        """
        # 首先从数据库加载配置，确保后续服务使用最新配置
        self.settings_repository = SettingsRepository(
            database_url=settings.database_url, disallow_keys=ENV_ONLY_KEYS
        )
        db_settings = self.settings_repository.load_all()
        for key, value in db_settings.items():
            if hasattr(settings, key):
                try:
                    setattr(settings, key, value)
                except Exception as exc:
                    from loguru import logger
                    logger.warning(f"⚠️ 配置项 '{key}' 加载失败，已使用默认值: {exc}")

        self.chat_history_store = ChatHistoryStore(
            pending_queue_limit=settings.pending_queue_limit,
            history_list_limit=settings.history_list_limit,
            database_url=settings.database_url,
        )
        self.rule_repository = RuleRepository(database_url=settings.database_url)
        self.feedback_repository = FeedbackRepository(database_url=settings.database_url)
        self.memory_repository = MemoryRepository(database_url=settings.database_url)
        self.detection_result_repository = DetectionResultRepository(database_url=settings.database_url)
        self.admin_credential_repository = AdminCredentialRepository(database_url=settings.database_url)
        self.agent_session_repository = AgentSessionRepository(database_url=settings.database_url)

        self.llm_client = build_llm_client()
        self.context_service = ContextWindowService(self.chat_history_store)

        self.rule_authoring_service = RuleAuthoringService(
            internal_backend=InternalRuleGenerationBackend(),
            external_backend=(
                ExternalPromptRuleGenerationBackend(settings.external_rule_generation_endpoint)
                if settings.external_rule_generation_endpoint
                else None
            ),
        )

        self.suggestion_service = SuggestionService(self.memory_repository, self.feedback_repository)
        self.user_memory_service = UserMemoryService(self.llm_client, self.memory_repository,
                                self.context_service)
        notifiers = build_notifiers_from_settings()

        self.detection_engine = DetectionEngine(
            rules=self.rule_repository,
            context_service=self.context_service,
            llm_client=self.llm_client,
            result_repository=self.detection_result_repository,
            notifiers=notifiers,
            hook_dispatcher=ExternalHookDispatcher(hook_endpoints=[]),
        )

        self.adapter_manager = AdapterManager(build_adapters_from_settings(settings))
        for adapter in self.adapter_manager.adapters:
            adapter.register_handler(self.handle_adapter_event)

    async def handle_adapter_event(self, event: ChatEvent) -> None:
        """Adapter 统一消息入口：先处理用户画像，再进入检测触发流程。"""
        await self.user_memory_service.process_user_memory(event)
        await self.detection_engine.ingest_event(event)


class TokenManager:
    """简单的内存 Bearer Token 管理器，默认 24 小时过期。"""

    def __init__(self, ttl_hours: int = 24):
        self._tokens: dict[str, datetime] = {}
        self._ttl = timedelta(hours=ttl_hours)

    def create_token(self) -> str:
        token = secrets.token_urlsafe(32)
        self._tokens[token] = datetime.now(timezone.utc) + self._ttl
        return token

    def validate(self, token: str) -> bool:
        expiry = self._tokens.get(token)
        if expiry is None:
            return False
        if datetime.now(timezone.utc) > expiry:
            del self._tokens[token]
            return False
        return True

    def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)


def create_app() -> FastAPI:
    """创建并返回 FastAPI 应用实例。应用启动时自动启动所有 enabled adapters。"""
    container = AppContainer()
    operations = ChatGuardianOperations(container=container, env_only_keys=ENV_ONLY_KEYS)
    token_manager = TokenManager()
    app = FastAPI(title="ChatGuardian API", version="0.1.0", lifespan=_app_lifespan)
    app.state.container = container

    # CORS: allow all origins in development; restrict in production via settings
    cors_origins = ["*"] if settings.environment != "prod" else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _to_http_error(exc: OperationError) -> HTTPException:
        """将内部 OperationError 转换为 HTTPException。"""
        return HTTPException(status_code=exc.status_code, detail=str(exc))

    PUBLIC_PATH_PREFIXES = ("/app/", "/app/assets", "/assets", "/mcp")
    PUBLIC_PATHS = {
        "/",
        "/auth/login",
        "/health",
        "/app",
    }

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Bearer Token 认证中间件，公共路径与 /api/auth/ 前缀路径放行。"""
        path = request.url.path
        # Allow CORS preflight requests through
        if request.method == "OPTIONS":
            return await call_next(request)
        if path in PUBLIC_PATHS:
            return await call_next(request)
        if path.startswith("/api/auth/"):
            return await call_next(request)
        for prefix in PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
        token = auth_header[7:]
        if not token_manager.validate(token):
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
        return await call_next(request)

    # ── Auth endpoints ────────────────────────────────────────────────────────

    @app.get("/api/auth/setup-required")
    async def auth_setup_required():
        """检查管理员凭据是否需要配置。"""
        return {"setup_required": not container.admin_credential_repository.is_configured()}

    @app.post("/api/auth/register")
    async def auth_register(payload: RegisterRequest):
        """一次性管理员凭据注册。"""
        if container.admin_credential_repository.is_configured():
            raise HTTPException(status_code=400, detail="Admin credentials already configured")
        if not payload.username.strip() or not payload.password.strip():
            raise HTTPException(status_code=400, detail="Username and password must not be empty")
        container.admin_credential_repository.set_credentials(payload.username.strip(), payload.password)
        return {"status": "ok"}

    @app.post("/api/auth/login")
    async def auth_login(payload: LoginRequest):
        """管理员登录。"""
        if not container.admin_credential_repository.is_configured():
            raise HTTPException(status_code=400, detail="Admin credentials not configured")
        if not container.admin_credential_repository.verify(payload.username, payload.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token = token_manager.create_token()
        return {"token": token}

    @app.post("/api/auth/change-password")
    async def auth_change_password(payload: ChangePasswordRequest):
        """修改管理员密码。"""
        if not container.admin_credential_repository.change_password(
            payload.username, payload.old_password, payload.new_password
        ):
            raise HTTPException(status_code=400, detail="Invalid current credentials")
        return {"status": "ok"}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "time": datetime.utcnow().isoformat()}
        """
        健康检查接口，确认 API 进程是否正常运行。

        Returns:
            dict[str, str]: 字段说明：
                - ``status``：固定返回 ``"ok"`` 表示服务存活。
                - ``time``：当前 UTC 时间的 ISO8601 字符串，便于探测端确认时间。
        """
        return await operations.health()

    @app.get("/llm/health")
    async def llm_health(do_ping: bool = True) -> dict[str, object]:
        """
        返回 LLM 与批处理调度器的诊断信息。

        Args:
            do_ping: 是否执行一次最小化的 LLM ping 探活。

        Returns:
            dict[str, object]: 字段说明：
                - ``status``：``"ok"`` 或 ``"degraded"``（当 ping 失败时）。
                - ``time``：当前 UTC 时间 ISO8601 字符串。
                - ``llm``：``LLMClient.diagnostics()`` 返回的诊断字典。
                - ``scheduler``：批处理调度器诊断信息。
                - ``ping``：当 ``do_ping`` 为 True 时包含：
                    - ``ok``：布尔值，ping 是否成功。
                    - ``latency_ms``：往返耗时毫秒。
                    - ``error``：异常信息字符串或 ``None``。
        """
        return await operations.llm_health(do_ping=do_ping)

    @app.post("/adapters/start")
    async def start_adapters() -> dict[str, str | list[str]]:
        """
        启动所有已启用的 adapter。

        Returns:
            dict[str, str | list[str]]: 字段说明：
                - ``status``：固定返回 ``"started"``。
                - ``enabled_adapters``：已启用的 adapter 名称列表。
        """
        return await operations.start_adapters()

    @app.post("/adapters/stop")
    async def stop_adapters() -> dict[str, str | list[str]]:
        """
        停止所有已启用的 adapter。

        Returns:
            dict[str, str | list[str]]: 字段说明：
                - ``status``：固定返回 ``"stopped"``。
                - ``enabled_adapters``：已启用的 adapter 名称列表。
        """
        return await operations.stop_adapters()

    @app.post("/rules", response_model=DetectionRule)
    async def upsert_rule(payload: DetectionRule) -> DetectionRule:
        """
        创建或更新检测规则。

        Args:
            payload: `DetectionRule` 对象，包含规则定义。

        Returns:
            DetectionRule: 保存后的规则（包含生成的 ``rule_id`` 等字段）。
        """
        return await operations.upsert_rule(payload)

    @app.get("/rules/list", response_model=list[DetectionRule])
    async def list_rules() -> list[DetectionRule]:
        """
        列出所有规则。

        Returns:
            list[DetectionRule]: 规则列表。
        """
        return await operations.list_rules()

    @app.post("/rules/delete/{rule_id}")
    async def delete_rule(rule_id: str) -> dict[str, str | bool]:
        """
        删除指定规则。

        Args:
            rule_id: 规则标识。

        Returns:
            dict[str, str | bool]: 字段说明：
                - ``status``：固定返回 ``"deleted"``。
                - ``rule_id``：被删除的规则 ID。
                - ``deleted``：布尔值，恒为 True。

        Raises:
            HTTPException: 404 当规则不存在。
        """
        try:
            return await operations.delete_rule(rule_id)
        except OperationError as exc:
            raise _to_http_error(exc) from exc

    @app.post("/feedback")
    async def submit_feedback(payload: Feedback) -> dict[str, str]:
        """
        提交检测结果的反馈。

        Args:
            payload: `Feedback` 对象，包含评分与备注。

        Returns:
            dict[str, str]: 字段说明：
                - ``status``：固定返回 ``"accepted"``。
        """
        return await operations.submit_feedback(payload)

    @app.get("/suggestions/new-rules/{user_id}", response_model=SuggestResponse)
    async def suggest_new_rules(user_id: str) -> SuggestResponse:
        """
        基于用户记忆生成新的规则建议。

        Args:
            user_id: 目标用户 ID。

        Returns:
            SuggestResponse: 包含 ``suggestions`` 列表（每条为字符串）。
        """
        return await operations.suggest_new_rules(user_id)

    @app.get("/suggestions/rule-improvements/{rule_id}", response_model=SuggestResponse)
    async def suggest_rule_improvements(rule_id: str) -> SuggestResponse:
        """
        针对指定规则生成改进建议。

        Args:
            rule_id: 规则 ID。

        Returns:
            SuggestResponse: 包含 ``suggestions`` 列表。
        """
        return await operations.suggest_rule_improvements(rule_id)

    @app.post("/rule-generation", response_model=DetectionRule)
    async def generate_rule(payload: RuleGenerateRequest) -> DetectionRule:
        """
        根据用户输入的一句话生成结构化检测规则。

        Args:
            payload: `RuleGenerateRequest`，包含 ``utterance``（描述文本）、``use_external``（是否调用外部端点）、
                ``override_system_prompt``（可选的系统提示词覆盖）。

        Returns:
            DetectionRule: 生成的规则。

        Raises:
            HTTPException: 400 当输入无法生成合法规则时。
        """
        try:
            return await operations.generate_rule(payload)
        except OperationError as exc:
            raise _to_http_error(exc) from exc

    @app.post("/mcp/tools/generate-rule", response_model=DetectionRule)
    async def mcp_generate_rule(payload: RuleGenerateRequest) -> DetectionRule:
        """
        MCP 入口的规则生成，逻辑等同于 ``POST /rule-generation``。

        Args:
            payload: `RuleGenerateRequest`。

        Returns:
            DetectionRule: 生成的规则。
        """
        return await generate_rule(payload)

    @app.get("/api/rule_stats")
    async def get_rule_stats():
        """
        汇总规则触发统计数据，仅包含已触发的结果。

        Returns:
            dict: 字段说明：
                - ``stats``：固定返回 ``"ok"``。
                - ``data``：以规则名为键的统计字典，包含：
                    - ``count``：触发次数。
                    - ``description``：规则描述。
                    - ``records``：按时间倒序的触发记录列表，每条含 ``result_id``、``event_id``、
                      ``rule_id``、``adapter``、``chat_type``、``chat_id``、``message_id``、
                      ``trigger_time``（ISO8601）、``confidence``、``result``、``trigger_suppressed``、
                      ``suppression_reason``、``rule_name``、``messages``、``extracted_params``、``reason``。
        """
        return await operations.get_rule_stats()

    @app.get("/api/queues")
    async def get_queues():
        """
        获取待处理与历史消息队列的扁平化视图。

        Returns:
            dict: 字段说明：
                - ``pending``：待处理消息列表，每条包含平台、chat_type/chat_id、message_id、sender_name、content、timestamp。
                - ``history``：历史消息列表，字段与 ``pending`` 相同。
        """
        return await operations.get_queues()

    @app.delete("/api/queues/history")
    async def delete_history_messages(payload=Body(default={"items": []})):
        """
        删除历史消息，可按条目或清空全部。

        Request Body:
            clear_all: 可选，True 时清空全部历史。
            items: 可选，待删除消息的列表，元素包含 ``platform``/``adapter``、``chat_type``、``chat_id``、``message_id``。

        Returns:
            dict: 当 ``clear_all`` 为 True 返回 ``{"cleared": <count>}``，否则返回 ``{"deleted": <count>}``。
        """
        return await operations.delete_history_messages(payload=payload)

    @app.get("/api/adapters/status")
    async def get_adapters_status():
        """
        查询所有 adapter 的运行状态。

        Returns:
            list[dict]: 每个元素包含：
                - ``name``：adapter 名称。
                - ``running``：当前是否运行。
        """
        return await operations.get_adapters_status()

    # ── Dashboard ────────────────────────────────────────────────────────────

    @app.get("/api/dashboard")
    async def get_dashboard():
        """
        获取仪表盘概览数据。

        Returns:
            dict: 字段说明：
                - ``total_rules``：规则总数。
                - ``enabled_rules``：启用的规则数。
                - ``triggers_today``：今日触发次数。
                - ``trigger_rate``：累计触发占比。
                - ``messages_today``：今日处理的消息数。
                - ``llm_status``：LLM 诊断信息。
        """
        return await operations.get_dashboard()

    # ── Logs ─────────────────────────────────────────────────────────────────

    _log_buffer: deque[dict] = deque(maxlen=500)
    operations.log_buffer = _log_buffer

    try:
        from loguru import logger as _loguru_logger

        def _sink(message):
            record = message.record
            _log_buffer.append(
                {
                    "timestamp": record["time"].isoformat(),
                    "level": record["level"].name,
                    "message": record["message"],
                }
            )

        _loguru_logger.add(_sink, format="{message}")
    except Exception:
        pass

    @app.get("/api/logs")
    async def get_logs(limit: int = 100):
        """
        拉取最近的运行日志。

        Args:
            limit: 最多返回的日志条数，默认 100。

        Returns:
            list[dict]: 每条包含 ``timestamp``、``level``、``message``。
        """
        return await operations.get_logs(limit=limit)

    @app.delete("/api/logs")
    async def clear_logs():
        """
        清空内存日志缓冲区。

        Returns:
            dict[str, int]: 字段 ``cleared`` 表示删除的条数。
        """
        return await operations.clear_logs()

    # ── User Profiles ─────────────────────────────────────────────────────────

    @app.get("/api/user_profiles")
    async def list_user_profiles():
        """
        列出所有用户画像。

        Returns:
            list: 用户画像列表（`UserProfile` dict 格式）。
        """
        return await operations.list_user_profiles()

    @app.get("/api/user_profiles/{user_id}")
    async def get_user_profile(user_id: str):
        """
        获取指定用户的画像。

        Args:
            user_id: 用户 ID。

        Returns:
            dict: 用户画像。

        Raises:
            HTTPException: 404 当用户不存在。
        """
        try:
            return await operations.get_user_profile(user_id)
        except OperationError as exc:
            raise _to_http_error(exc) from exc

    # ── Settings ──────────────────────────────────────────────────────────────

    @app.get("/api/settings")
    async def get_settings_api() -> dict:
        """返回当前所有可配置项（不含 database_url）。"""
        return await operations.get_settings()

    @app.post("/api/settings")
    async def update_settings_api(payload: dict) -> dict:
        """批量更新配置项，保存到数据库并立即生效。database_url 不可通过此接口修改。"""
        try:
            return await operations.update_settings(payload)
        except OperationError as exc:
            raise _to_http_error(exc) from exc

    # ── Notifications config ──────────────────────────────────────────────────

    @app.get("/api/notifications/config")
    async def get_notifications_config():
        """
        获取通知配置（邮件与 Bark）。

        Returns:
            dict: 字段 ``email`` 与 ``bark``，各自包含启用状态与配置字段。
        """
        return operations.get_notifications_config()

    # ── LLM config ────────────────────────────────────────────────────────────

    @app.get("/api/llm/config")
    async def get_llm_config():
        """
        返回当前 LLM 配置摘要。

        Returns:
            dict: 字段说明：
                - ``backend``：LangChain 后端类型。
                - ``model``：模型名称。
                - ``api_base``：API 基础地址。
                - ``temperature``：采样温度。
                - ``timeout_seconds``：超时时间。
                - ``max_parallel_batches``：最大并行批次数。
                - ``rules_per_batch``：每批处理规则数。
                - ``ollama_base_url``：Ollama 基础地址。
        """
        return operations.get_llm_config()

    container.operations = operations
    container.mcp_service = ChatGuardianMCPService(container=container, operations=operations)
    app.state.mcp_service = container.mcp_service
    if settings.mcp_http_enabled:
        logger.info(
            "🌐 MCP HTTP 传输已启用，将在启动时监听 {}:{}{}",
            settings.mcp_http_host,
            settings.mcp_http_port,
            settings.mcp_http_path,
        )

    # ── Admin Agent ──────────────────────────────────────────────────────────

    admin_agent = AdminAgent(operations=operations)

    @app.post("/api/agent/chat")
    async def agent_chat(request: Request, payload: AgentChatRequest):
        """管理智能体流式对话接口。返回 Server-Sent Events 流。"""

        async def event_generator():
            try:
                async for event in admin_agent.stream(
                    payload.messages,
                    is_disconnected=request.is_disconnected,
                ):
                    if await request.is_disconnected():
                        logger.info("Client disconnected, stopping agent stream")
                        return
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            except asyncio.CancelledError:
                logger.info("Agent chat stream cancelled (client disconnect)")
            except Exception as exc:
                logger.error(f"Agent chat stream error: {exc}")
                yield f"data: {json.dumps({'type': 'error', 'content': str(exc)}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/agent/capabilities")
    async def agent_capabilities():
        """返回管理智能体的能力列表和工具展示名称映射。"""
        return {
            "tool_display_names": TOOL_DISPLAY_NAMES,
            "capabilities": [
                {
                    "category": "query",
                    "items": [
                        "get_dashboard",
                        "get_rules_list",
                        "get_rule_stats",
                        "get_adapters_status",
                        "get_queues",
                        "get_system_logs",
                        "get_user_profiles",
                        "get_user_profile",
                        "get_settings",
                        "get_notifications_config",
                        "get_llm_config",
                        "check_llm_health",
                        "check_system_health",
                    ],
                },
                {
                    "category": "management",
                    "items": [
                        "create_or_update_rule",
                        "delete_rule",
                        "generate_rule_from_description",
                        "start_adapters",
                        "stop_adapters",
                        "update_settings",
                        "clear_message_history",
                        "clear_system_logs",
                    ],
                },
            ],
        }

    # ── Agent Session endpoints ───────────────────────────────────────────────
    agent_session_repo = container.agent_session_repository

    @app.get("/api/agent/sessions")
    async def list_agent_sessions():
        """列出所有 AI 助手会话。"""
        return agent_session_repo.list_sessions()

    @app.post("/api/agent/sessions")
    async def create_agent_session(payload: CreateSessionRequest):
        """创建新的 AI 助手会话。"""
        session_id = _uuid.uuid4().hex[:16]
        return agent_session_repo.create_session(session_id, payload.title)

    @app.delete("/api/agent/sessions/{session_id}")
    async def delete_agent_session(session_id: str):
        """删除 AI 助手会话及其所有消息。"""
        ok = agent_session_repo.delete_session(session_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True}

    @app.patch("/api/agent/sessions/{session_id}")
    async def update_agent_session_title(session_id: str, payload: UpdateSessionTitleRequest):
        """更新 AI 助手会话标题。"""
        ok = agent_session_repo.update_session_title(session_id, payload.title)
        if not ok:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True}

    @app.get("/api/agent/sessions/{session_id}/messages")
    async def get_agent_session_messages(session_id: str):
        """获取指定会话的所有消息。"""
        return agent_session_repo.get_messages(session_id)

    @app.post("/api/agent/sessions/{session_id}/messages")
    async def save_agent_message(session_id: str, payload: SaveMessageRequest):
        """向指定会话添加消息。"""
        return agent_session_repo.add_message(
            session_id=session_id,
            role=payload.role,
            content=payload.content,
            tool_calls=payload.tool_calls,
            elapsed_ms=payload.elapsed_ms,
        )

    @app.delete("/api/agent/sessions/{session_id}/message-pair")
    async def delete_agent_message_pair(session_id: str, payload: DeleteMessagePairRequest):
        """删除指定会话中的一组问答对。"""
        ok = agent_session_repo.delete_message_pair(session_id, payload.user_message_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Message pair not found")
        return {"ok": True}

    # ── Static frontend ───────────────────────────────────────────────────────

    _frontend_dist = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    )
    if os.path.exists(_frontend_dist):
        _assets_dir = os.path.join(_frontend_dist, "assets")
        if os.path.exists(_assets_dir):
            app.mount("/app/assets", StaticFiles(directory=_assets_dir), name="assets")

        @app.get("/app/{full_path:path}")
        async def serve_frontend(full_path: str):
            """返回构建后的前端页面（任意子路径）。"""
            return FileResponse(os.path.join(_frontend_dist, "index.html"))

        @app.get("/app")
        async def serve_frontend_root():
            """返回前端入口页面。"""
            return FileResponse(os.path.join(_frontend_dist, "index.html"))

        @app.get("/", include_in_schema=False)
        async def redirect_to_frontend():
            """根路径重定向到 /app。"""
            return RedirectResponse(url="/app")

    return app
