"""
FastAPI 应用与路由定义。

此模块负责把内部服务装配为可被 HTTP 调用的 API，并提供一个极简的 WebUI 入口用于调试。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

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
from chat_guardian.repositories import (
    InMemoryChatHistoryStore,
    InMemoryDetectionResultRepository,
    InMemoryFeedbackRepository,
    InMemoryMemoryRepository,
    InMemoryRuleRepository,
)
from chat_guardian.services import (
    build_llm_client,
    ContextWindowService,
    DetectionEngine,
    EmailNotifier,
    ExternalHookDispatcher,
    ExternalPromptRuleGenerationBackend,
    InternalRuleGenerationBackend,
    NotificationConfig,
    RuleAuthoringService,
    SelfMessageMemoryService,
    SuggestionService,
)
from chat_guardian.settings import settings

class AppContainer:
    def __init__(self):
        """简单的应用容器，实例化所有内存仓储与服务。

        该容器用于在 `create_app` 中创建单例服务实例，便于路由直接使用。
        """
        self.chat_history_store = InMemoryChatHistoryStore(
            pending_queue_limit=settings.pending_queue_limit,
            history_list_limit=settings.history_list_limit,
        )
        self.rule_repository = InMemoryRuleRepository()
        self.feedback_repository = InMemoryFeedbackRepository()
        self.memory_repository = InMemoryMemoryRepository()
        self.detection_result_repository = InMemoryDetectionResultRepository()

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
        self.self_message_service = SelfMessageMemoryService(self.llm_client, self.memory_repository, self.context_service)
        self.detection_engine = DetectionEngine(
            rules=self.rule_repository,
            context_service=self.context_service,
            llm_client=self.llm_client,
            result_repository=self.detection_result_repository,
            notifiers=[EmailNotifier(NotificationConfig(to_email=None))],
            hook_dispatcher=ExternalHookDispatcher(hook_endpoints=[]),
        )

        self.adapter_manager = AdapterManager(build_adapters_from_settings(settings))
        for adapter in self.adapter_manager.adapters:
            adapter.register_handler(self.handle_adapter_event)

    async def handle_adapter_event(self, event: ChatEvent) -> None:
        """Adapter 统一消息入口：先处理 self-memory，再进入检测触发流程。"""
        await self.self_message_service.process_if_self_message(event)
        await self.detection_engine.ingest_event(event)


def _from_payload(payload: DetectionRule) -> DetectionRule:
    """将 API 的 `DetectionRule` 请求体规范化为领域对象。"""
    return DetectionRule.model_validate(payload.model_dump(mode="python"))


def _to_payload(rule: DetectionRule) -> DetectionRule:
    """将领域对象 `DetectionRule` 转换成 API 可序列化对象。"""
    return DetectionRule.model_validate(rule.model_dump(mode="python"))





def create_app() -> FastAPI:
    """创建并返回 FastAPI 应用实例。"""
    app = FastAPI(title="ChatGuardian API", version="0.1.0")
    container = AppContainer()
    # Expose the application container on app.state for testing and integrations.
    app.state.container = container

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
        saved = await container.rule_repository.upsert(_from_payload(payload))
        return _to_payload(saved)

    @app.get("/rules/list", response_model=list[DetectionRule])
    async def list_rules() -> list[DetectionRule]:
        rules = await container.rule_repository.list_all()
        return [_to_payload(rule) for rule in rules]

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

        return _to_payload(generated)

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
                "running": True # Need to check if there's a task or similar, mock running for now.
            } for adapter in container.adapter_manager.adapters
        ]

    return app

