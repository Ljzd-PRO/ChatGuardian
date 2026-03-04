"""
FastAPI 应用与路由定义。

此模块负责把内部服务装配为可被 HTTP 调用的 API，并提供一个极简的 WebUI 入口用于调试。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, date

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

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
    ChatHistoryStore,
    DetectionResultRepository,
    FeedbackRepository,
    MemoryRepository,
    RuleRepository,
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
from chat_guardian.settings import settings


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
        self.chat_history_store = ChatHistoryStore(
            pending_queue_limit=settings.pending_queue_limit,
            history_list_limit=settings.history_list_limit,
            database_url=settings.database_url,
        )
        self.rule_repository = RuleRepository(database_url=settings.database_url)
        self.feedback_repository = FeedbackRepository(database_url=settings.database_url)
        self.memory_repository = MemoryRepository(database_url=settings.database_url)
        self.detection_result_repository = DetectionResultRepository(database_url=settings.database_url)

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

    async def handle_adapter_event(self, event: ChatEvent) -> None:
        """Adapter 统一消息入口：先处理 self-memory，再进入检测触发流程。"""
        await self.self_message_service.process_if_self_message(event)
        await self.detection_engine.ingest_event(event)


def create_app() -> FastAPI:
    """创建并返回 FastAPI 应用实例。应用启动时自动启动所有 enabled adapters。"""
    container = AppContainer()
    app = FastAPI(title="ChatGuardian API", version="0.1.0", lifespan=_app_lifespan)
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "time": datetime.utcnow().isoformat()}

    @app.get("/llm/health")
    async def llm_health(do_ping: bool = True) -> dict[str, object]:
        diagnostics = container.llm_client.diagnostics()
        scheduler_diagnostics = container.detection_engine.batch_scheduler.diagnostics()
        result: dict[str, object] = {
            "status": "ok",
            "time": datetime.utcnow().isoformat(),
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

    @app.get("/ui", response_class=HTMLResponse)
    async def webui() -> str:
        return """
<!doctype html>
<html lang="zh-CN">
<head><meta charset="UTF-8"/><title>ChatGuardian MVP</title></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:24px auto;line-height:1.6;">
    <h1>ChatGuardian MVP</h1>
    <p>当前版本提供规则管理、检测、反馈、建议、MCP规则生成API。建议通过 API 客户端联调。</p>
    <ul>
        <li>规则管理：POST /rules</li>
        <li>消息检测：POST /detect</li>
        <li>反馈打分：POST /feedback</li>
        <li>新规则建议：GET /suggestions/new-rules/{user_id}</li>
        <li>规则改进建议：GET /suggestions/rule-improvements/{rule_id}</li>
        <li>一句话生成规则：POST /rule-generation 或 /mcp/tools/generate-rule</li>
    </ul>
</body>
</html>
"""

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
                    "trigger_time": r.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "confidence": round(r.decision.confidence, 2),
                    "result": "Triggered (Suppressed)" if r.trigger_suppressed else "Triggered",
                    "rule_name": rule.name,
                    "messages": [
                        {"sender": m.sender_name or m.sender_id, "content": str(m)}
                        for m in r.context_messages
                    ],
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
                                    "chat_type": chat_type,
                                    "chat_id": chat_id,
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
            "llm_status": llm_diag,
        }

    # ── Logs ─────────────────────────────────────────────────────────────────

    _log_buffer: "deque[dict]"

    from collections import deque
    _log_buffer = deque(maxlen=500)

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

    @app.get("/api/settings")
    async def get_settings():
        s = settings
        return {
            "app_name": s.app_name,
            "environment": s.environment,
            "llm_langchain_backend": s.llm_langchain_backend,
            "llm_langchain_model": s.llm_langchain_model,
            "llm_langchain_api_base": s.llm_langchain_api_base,
            "llm_langchain_api_key": s.llm_langchain_api_key,
            "llm_langchain_temperature": s.llm_langchain_temperature,
            "llm_timeout_seconds": s.llm_timeout_seconds,
            "llm_max_parallel_batches": s.llm_max_parallel_batches,
            "llm_rules_per_batch": s.llm_rules_per_batch,
            "context_message_limit": s.context_message_limit,
            "detection_cooldown_seconds": s.detection_cooldown_seconds,
            "detection_min_new_messages": s.detection_min_new_messages,
            "email_notifier_enabled": s.email_notifier_enabled,
            "email_notifier_to_email": s.email_notifier_to_email,
            "smtp_host": s.smtp_host,
            "smtp_port": s.smtp_port,
            "smtp_username": s.smtp_username,
            "smtp_sender": s.smtp_sender,
            "bark_notifier_enabled": s.bark_notifier_enabled,
            "bark_device_key": s.bark_device_key,
            "bark_server_url": s.bark_server_url,
            "bark_group": s.bark_group,
            "enabled_adapters": s.enabled_adapters,
        }

    @app.post("/api/settings")
    async def update_settings(payload: dict):
        """Persist provided settings keys to the .env file."""
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        env_path = os.path.abspath(env_path)

        existing: dict[str, str] = {}
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        existing[k.strip()] = v.strip()

        for key, value in payload.items():
            env_key = f"CHAT_GUARDIAN_{key.upper()}"
            existing[env_key] = str(value)

        with open(env_path, "w") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

        return {"status": "saved"}

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
                "smtp_sender": s.smtp_sender,
                "to_email": s.email_notifier_to_email,
            },
            "bark": {
                "enabled": s.bark_notifier_enabled,
                "device_key": s.bark_device_key,
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
            return FileResponse(os.path.join(_frontend_dist, "index.html"))

        @app.get("/app")
        async def serve_frontend_root():
            return FileResponse(os.path.join(_frontend_dist, "index.html"))

    return app
