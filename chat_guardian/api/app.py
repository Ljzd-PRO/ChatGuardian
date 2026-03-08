"""
FastAPI 应用与路由定义。

此模块负责把内部服务装配为可被 HTTP 调用的 API，并提供一个极简的 WebUI 入口用于调试。
"""

from __future__ import annotations

import os
import secrets
from collections import deque
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from chat_guardian.adapters import AdapterManager, build_adapters_from_settings
from chat_guardian.api.schemas import (
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
from chat_guardian.repositories import (
    AdminCredentialRepository,
    ChatHistoryStore,
    DetectionResultRepository,
    FeedbackRepository,
    MemoryRepository,
    RuleRepository,
    SettingsRepository,
    _verify_password,
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
    SelfMessageMemoryService,
    SuggestionService,
)
from chat_guardian.settings import admin_password_env, admin_username_env, settings, Settings

ENV_ONLY_KEYS = frozenset({"database_url", "app_name", "environment"})


class TokenManager:
    """Simple in-memory token manager for issuing and validating access tokens."""

    def __init__(self):
        self._tokens: dict[str, tuple[str, datetime]] = {}

    def issue(self, username: str, ttl_hours: int = 24) -> str:
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        self._tokens[token] = (username, expires_at)
        return token

    def validate(self, token: str) -> str | None:
        record = self._tokens.get(token)
        if not record:
            return None
        username, expires_at = record
        if expires_at < datetime.now(timezone.utc):
            self._tokens.pop(token, None)
            return None
        return username

    def revoke(self, token: str) -> None:
        self._tokens.pop(token, None)


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """应用生命周期管理：启动时自动启动 adapters，关闭时自动停止。"""
    import signal
    import threading
    from loguru import logger
    container = app.state.container

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
    try:
        yield
    finally:
        # 关闭
        if _shutdown_by_signal:
            logger.info("🛑 用户停止了程序，正在关闭应用...")
        else:
            logger.info("🛑 应用关闭，停止所有 adapters")
        await container.adapter_manager.stop_all()
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
        self.credential_repository = AdminCredentialRepository(database_url=settings.database_url)

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
        self.self_message_service = SelfMessageMemoryService(self.llm_client, self.memory_repository,
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

        self.token_manager = TokenManager()

        if (
            not self.credential_repository.is_configured()
            and admin_username_env
            and admin_password_env
        ):
            # 如果提供了环境变量，则在首次启动时写入数据库作为初始账号密码。
            self.credential_repository.set_credentials(admin_username_env, admin_password_env)

        creds = self.credential_repository.get_credentials()
        self.credentials_configured = creds is not None
        self.admin_username = creds[0] if creds else None
        if creds:
            # 判定是否仍在使用默认凭据（admin/admin）
            _, encoded = creds
            self.using_default_credentials = self.admin_username == "admin" and _verify_password(
                "admin", encoded
            )
        else:
            self.using_default_credentials = False

    async def handle_adapter_event(self, event: ChatEvent) -> None:
        """Adapter 统一消息入口：先处理 self-memory，再进入检测触发流程。"""
        await self.self_message_service.process_if_self_message(event)
        await self.detection_engine.ingest_event(event)


def create_app() -> FastAPI:
    """创建并返回 FastAPI 应用实例。应用启动时自动启动所有 enabled adapters。"""
    container = AppContainer()
    app = FastAPI(title="ChatGuardian API", version="0.1.0", lifespan=_app_lifespan)
    app.state.container = container

    if container.admin_username:
        logger.info("🔐 Admin username: {}", container.admin_username)
        logger.info("🔑 Admin password: {}", container.admin_password)
    else:
        logger.warning("🔒 No admin credentials configured. Initial setup required.")
    if container.using_default_credentials:
        logger.warning(
            "⚠️ Default credentials in use. Please update the administrator username/password for better security."
        )

    # CORS: allow all origins in development; restrict in production via settings
    cors_origins = ["*"] if settings.environment != "prod" else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    PUBLIC_PATH_PREFIXES = ("/app/assets", "/assets")
    PUBLIC_PATHS = {
        "/",
        "/auth/login",
        "/auth/setup-status",
        "/auth/setup",
        "/health",
        "/llm/health",
        "/app",
        "/app/",
        "/app/vite.svg",
    }
    # '/' serves a redirect to the frontend entry, so it must remain public.

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if (
            path in PUBLIC_PATHS
            or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)
            or (not container.credentials_configured and path in {"/auth/setup", "/auth/setup-status"})
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        token = auth_header.split(" ", 1)[1].strip()
        username = container.token_manager.validate(token)
        if not username:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)

        request.state.user = username
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

    @app.get("/llm/health")
    async def llm_health(do_ping: bool = True) -> dict[str, object]:
        diagnostics = container.llm_client.diagnostics()
        scheduler_diagnostics = container.detection_engine.batch_scheduler.diagnostics()
        result: dict[str, object] = {
            "status": "ok",
            "time": datetime.now(timezone.utc).isoformat(),
            "llm": diagnostics,
            "scheduler": scheduler_diagnostics,
        }

        if do_ping:
            ping_ok, ping_error, latency_ms = await container.llm_client.ping()
            result["ping"] = {
                "ok": ping_ok,
                "latency_ms": round(latency_ms, 2),
                "error": ping_error,
            }
            if not ping_ok:
                result["status"] = "degraded"

        return result

    @app.get("/auth/setup-status")
    async def auth_setup_status() -> dict[str, object]:
        return {
            "setup_required": not container.credentials_configured,
            "using_default_credentials": container.using_default_credentials,
        }

    @app.post("/auth/setup")
    async def auth_setup(request: Request, payload: dict = Body(...)) -> dict[str, object]:
        username = str((payload or {}).get("username") or "").strip()
        password = str((payload or {}).get("password") or "")
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required.")

        # 已配置账号时，需要登录态才能修改；首次配置可直接设置。
        if container.credentials_configured:
            auth_header = request.headers.get("Authorization") if request else None
            if not auth_header or not auth_header.lower().startswith("bearer "):
                raise HTTPException(status_code=401, detail="Unauthorized")
            token = auth_header.split(" ", 1)[1].strip()
            current_user = container.token_manager.validate(token)
            if not current_user:
                raise HTTPException(status_code=401, detail="Unauthorized")

        container.credential_repository.set_credentials(username, password)
        container.token_manager = TokenManager()
        container.credentials_configured = True
        container.admin_username = username
        container.using_default_credentials = username == "admin" and password == "admin"

        token = container.token_manager.issue(username)
        return {
            "token": token,
            "username": username,
            "setup_required": False,
        }

    @app.post("/auth/login")
    async def auth_login(payload: dict = Body(...)) -> dict[str, object]:
        username = str((payload or {}).get("username") or "").strip()
        password = str((payload or {}).get("password") or "")
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password are required.")

        if not container.credentials_configured:
            raise HTTPException(status_code=400, detail="Setup required")

        if container.credential_repository.verify(username, password):
            token = container.token_manager.issue(username)
            return {
                "token": token,
                "username": username,
                "using_default_credentials": container.using_default_credentials,
            }

        raise HTTPException(status_code=401, detail="Invalid credentials")

    @app.get("/auth/status")
    async def auth_status(request: Request) -> dict[str, object]:
        current_user = getattr(request.state, "user", None)
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return {
            "authenticated": True,
            "username": current_user,
            "using_default_credentials": container.using_default_credentials,
            "setup_required": not container.credentials_configured,
        }

    @app.post("/auth/logout")
    async def auth_logout(request: Request) -> dict[str, str]:
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            container.token_manager.revoke(token)
        return {"status": "logged_out"}

    @app.post("/adapters/start")
    async def start_adapters() -> dict[str, str | list[str]]:
        await container.adapter_manager.start_all()
        return {
            "status": "started",
            "enabled_adapters": [adapter.name for adapter in container.adapter_manager.adapters],
        }

    @app.post("/adapters/stop")
    async def stop_adapters() -> dict[str, str | list[str]]:
        await container.adapter_manager.stop_all()
        return {
            "status": "stopped",
            "enabled_adapters": [adapter.name for adapter in container.adapter_manager.adapters],
        }

    @app.post("/rules", response_model=DetectionRule)
    async def upsert_rule(payload: DetectionRule) -> DetectionRule:
        saved = await container.rule_repository.upsert(payload)
        return saved

    @app.get("/rules/list", response_model=list[DetectionRule])
    async def list_rules() -> list[DetectionRule]:
        rules = await container.rule_repository.list_all()
        return rules

    @app.post("/rules/delete/{rule_id}")
    async def delete_rule(rule_id: str) -> dict[str, str | bool]:
        deleted = await container.rule_repository.delete(rule_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
        return {"status": "deleted", "rule_id": rule_id, "deleted": True}

    @app.post("/feedback")
    async def submit_feedback(payload: Feedback) -> dict[str, str]:
        await container.feedback_repository.add(payload)
        return {"status": "accepted"}

    @app.get("/suggestions/new-rules/{user_id}", response_model=SuggestResponse)
    async def suggest_new_rules(user_id: str) -> SuggestResponse:
        suggestions = await container.suggestion_service.suggest_new_rules(user_id)
        return SuggestResponse(suggestions=suggestions)

    @app.get("/suggestions/rule-improvements/{rule_id}", response_model=SuggestResponse)
    async def suggest_rule_improvements(rule_id: str) -> SuggestResponse:
        suggestions = await container.suggestion_service.suggest_rule_improvements(rule_id)
        return SuggestResponse(suggestions=suggestions)

    @app.post("/rule-generation", response_model=DetectionRule)
    async def generate_rule(payload: RuleGenerateRequest) -> DetectionRule:
        try:
            generated = await container.rule_authoring_service.generate_rule(
                utterance=payload.utterance,
                use_external=payload.use_external,
                override_system_prompt=payload.override_system_prompt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return generated

    @app.post("/mcp/tools/generate-rule", response_model=DetectionRule)
    async def mcp_generate_rule(payload: RuleGenerateRequest) -> DetectionRule:
        return await generate_rule(payload)

    @app.get("/api/rule_stats")
    async def get_rule_stats():
        stats = {}
        for rule_id, results in container.detection_result_repository.results_by_rule.items():
            rule = await container.rule_repository.get(rule_id)
            if not rule:
                continue

            # Only include triggered results for the stats dashboard
            triggered_results = [r for r in results if r.decision.triggered]
            if not triggered_results:
                continue

            records = []
            for r in triggered_results:
                records.append({
                    "id": r.result_id,
                    "result_id": r.result_id,
                    "event_id": r.event_id,
                    "rule_id": r.rule_id,
                    "adapter": r.adapter,
                    "chat_type": r.chat_type,
                    "chat_id": r.chat_id,
                    "message_id": r.message_id,
                    "trigger_time": r.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "confidence": round(r.decision.confidence, 2),
                    "result": "Triggered (Suppressed)" if r.trigger_suppressed else "Triggered",
                    "trigger_suppressed": r.trigger_suppressed,
                    "suppression_reason": r.suppression_reason,
                    "rule_name": rule.name,
                    "messages": [
                        {"sender": m.sender_name or m.sender_id, "content": str(m)}
                        for m in r.context_messages
                    ],
                    "extracted_params": r.decision.extracted_params,
                    "reason": r.decision.reason,
                })

            stats[rule.name] = {
                "count": len(triggered_results),
                "description": rule.description,
                "records": sorted(records, key=lambda x: x["trigger_time"], reverse=True)
            }

        return {"stats": "ok", "data": stats}

    @app.get("/api/queues")
    async def get_queues():
        store = container.chat_history_store

        def _flatten_bucket(tree):
            rows: list[dict[str, str]] = []
            for adapter, by_type in tree.items():
                for chat_type, by_chat in by_type.items():
                    for chat_id, messages in by_chat.items():
                        for message in messages:
                            rows.append(
                                {
                                    "adapter": adapter,
                                    "platform": adapter,
                                    "chat_type": chat_type,
                                    "chat_id": chat_id,
                                    "message_id": message.message_id,
                                    "sender_name": message.sender_name or message.sender_id,
                                    "content": str(message),
                                    "timestamp": message.timestamp.isoformat(),
                                }
                            )
            return rows

        return {
            "pending": _flatten_bucket(store.pending),
            "history": _flatten_bucket(store.history),
        }

    @app.delete("/api/queues/history")
    async def delete_history_messages(payload=Body(default={"items": []})):
        store = container.chat_history_store
        clear_all = bool(payload.get("clear_all"))
        if clear_all:
            cleared = await store.clear_history()
            return {"cleared": cleared}

        items_raw = payload.get("items") or []
        items: list[tuple[str, str, str, str]] = []
        for item in items_raw:
            platform = (item or {}).get("platform") or (item or {}).get("adapter")
            chat_type = (item or {}).get("chat_type")
            chat_id = (item or {}).get("chat_id")
            message_id = (item or {}).get("message_id")
            if not all([platform, chat_type, chat_id, message_id]):
                continue
            items.append((str(platform), str(chat_type), str(chat_id), str(message_id)))
        deleted = await store.delete_history_messages(items)
        return {"deleted": deleted}

    @app.get("/api/adapters/status")
    async def get_adapters_status():
        return [
            {
                "name": adapter.name,
                "running": True  # Need to check if there's a task or similar, mock running for now.
            } for adapter in container.adapter_manager.adapters
        ]

    # ── Dashboard ────────────────────────────────────────────────────────────

    @app.get("/api/dashboard")
    async def get_dashboard():
        rules = await container.rule_repository.list_all()
        total_rules = len(rules)
        enabled_rules = sum(1 for r in rules if r.enabled)

        today = date.today()
        triggers_today = 0
        for results in container.detection_result_repository.results_by_rule.values():
            for r in results:
                if r.decision.triggered and r.generated_at.date() == today:
                    triggers_today += 1

        messages_today = sum(
            1 for r in container.detection_result_repository.results if r.generated_at.date() == today
        )
        total_results = sum(
            len(v) for v in container.detection_result_repository.results_by_rule.values()
        )
        triggered_total = sum(
            sum(1 for r in v if r.decision.triggered)
            for v in container.detection_result_repository.results_by_rule.values()
        )
        trigger_rate = round(triggered_total / total_results, 4) if total_results else 0.0

        llm_diag = container.llm_client.diagnostics()

        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "triggers_today": triggers_today,
            "trigger_rate": trigger_rate,
            "messages_today": messages_today,
            "llm_status": llm_diag,
        }

    # ── Logs ─────────────────────────────────────────────────────────────────

    _log_buffer: deque[dict] = deque(maxlen=500)

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
        return list(reversed(list(_log_buffer)[-limit:]))

    @app.delete("/api/logs")
    async def clear_logs():
        cleared = len(_log_buffer)
        _log_buffer.clear()
        return {"cleared": cleared}

    # ── User Profiles ─────────────────────────────────────────────────────────

    @app.get("/api/user_profiles")
    async def list_user_profiles():
        return list(container.memory_repository.profiles.values())

    @app.get("/api/user_profiles/{user_id}")
    async def get_user_profile(user_id: str):
        profile = await container.memory_repository.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
        return profile

    # ── Settings ──────────────────────────────────────────────────────────────

    SETTINGS_ALLOWLIST = set(Settings.model_fields.keys()) - ENV_ONLY_KEYS

    # 注意：这里仅排除 database_url。
    # GET /api/settings 需要向前端展示 app_name/environment 等只读信息，
    # 而 ENV_ONLY_KEYS/SETTINGS_ALLOWLIST 主要用于限制哪些字段可以通过 POST 更新。
    # 因此本函数刻意没有使用 ENV_ONLY_KEYS，以避免误隐藏这些只读展示字段。
    def _settings_subset() -> dict[str, object]:
        return settings.model_dump(exclude={"database_url"})

    @app.get("/api/settings")
    async def get_settings_api() -> dict:
        """返回当前所有可配置项（不含 database_url）。"""
        return _settings_subset()

    @app.post("/api/settings")
    async def update_settings_api(payload: dict) -> dict:
        """批量更新配置项，保存到数据库并立即生效。database_url 不可通过此接口修改。"""
        updates = {k: v for k, v in payload.items() if k in SETTINGS_ALLOWLIST}
        disallowed = set(payload.keys()) - set(SETTINGS_ALLOWLIST)
        if disallowed:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown or disallowed setting(s): {', '.join(sorted(disallowed))}",
            )

        # Build full settings object for validation while keeping database_url from env
        current = settings.model_dump()
        current.update(updates)
        current["database_url"] = settings.database_url

        try:
            validated = Settings.model_validate(current)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        adapter_related_keys = {
            "enabled_adapters",
            "onebot_host",
            "onebot_port",
            "onebot_access_token",
            "telegram_bot_token",
            "telegram_polling_timeout",
            "telegram_drop_pending_updates",
            "wechat_endpoint",
            "feishu_app_id",
            "virtual_adapter_chat_count",
            "virtual_adapter_members_per_chat",
            "virtual_adapter_messages_per_chat",
            "virtual_adapter_interval_min_seconds",
            "virtual_adapter_interval_max_seconds",
            "virtual_adapter_script_path",
        }
        update_keys = set(updates.keys())
        adapter_updates = adapter_related_keys & update_keys
        new_adapters = None
        if adapter_updates:
            try:
                new_adapters = build_adapters_from_settings(validated)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        validated_dict = validated.model_dump(exclude={"database_url"})
        # Persist only the allowlisted keys that were provided
        to_save = {k: validated_dict[k] for k in updates.keys()}
        container.settings_repository.save(to_save)

        for key, value in to_save.items():
            setattr(settings, key, value)

        if adapter_updates and new_adapters is not None:
            try:
                await container.adapter_manager.stop_all()
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to stop existing adapters: {exc}") from exc
            try:
                container.adapter_manager = AdapterManager(new_adapters)
                for adapter in container.adapter_manager.adapters:
                    adapter.register_handler(container.handle_adapter_event)
                # Adapters are intentionally left stopped here; users start them from the control panel.
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to rebuild adapters: {exc}") from exc

        return {"status": "saved", "settings": _settings_subset()}

    # ── Notifications config ──────────────────────────────────────────────────

    @app.get("/api/notifications/config")
    async def get_notifications_config():
        s = settings
        return {
            "email": {
                "enabled": s.email_notifier_enabled,
                "smtp_host": s.smtp_host,
                "smtp_port": s.smtp_port,
                "smtp_username": s.smtp_username,
                "smtp_password": s.smtp_password,
                "smtp_sender": s.smtp_sender,
                "to_email": s.email_notifier_to_email,
            },
            "bark": {
                "enabled": s.bark_notifier_enabled,
                "device_key": s.bark_device_key,
                "device_keys": s.bark_device_keys,
                "server_url": s.bark_server_url,
                "group": s.bark_group,
                "level": s.bark_level,
            },
        }

    # ── LLM config ────────────────────────────────────────────────────────────

    @app.get("/api/llm/config")
    async def get_llm_config():
        s = settings
        return {
            "backend": s.llm_langchain_backend,
            "model": s.llm_langchain_model,
            "api_base": s.llm_langchain_api_base,
            "temperature": s.llm_langchain_temperature,
            "timeout_seconds": s.llm_timeout_seconds,
            "max_parallel_batches": s.llm_max_parallel_batches,
            "rules_per_batch": s.llm_rules_per_batch,
            "ollama_base_url": s.llm_ollama_base_url,
        }

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
            candidate = os.path.abspath(os.path.join(_frontend_dist, full_path))
            if candidate.startswith(_frontend_dist) and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(os.path.join(_frontend_dist, "index.html"))

        @app.get("/app")
        async def serve_frontend_root():
            return FileResponse(os.path.join(_frontend_dist, "index.html"))

        @app.get("/", include_in_schema=False)
        async def redirect_to_frontend():
            return RedirectResponse(url="/app")

    return app
