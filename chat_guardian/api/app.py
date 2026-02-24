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
    DetectRequest,
    DetectResponse,
    FeedbackPayload,
    MessageContentPayload,
    MessagePayload,
    RuleGenerateRequest,
    RulePayload,
    SuggestResponse,
)
from chat_guardian.domain import (
    ChatEvent,
    ChatMessage,
    ChatType,
    ContentType,
    DetectionRule,
    Feedback,
    MessageContent,
    RuleParameterSpec,
    SessionMatchMode,
    SessionTarget,
)
from chat_guardian.repositories import (
    InMemoryChatHistoryStore,
    InMemoryDetectionResultRepository,
    InMemoryFeedbackRepository,
    InMemoryMemoryRepository,
    InMemoryRuleRepository,
)
from chat_guardian.services import (
    ContextWindowService,
    DetectionEngine,
    EmailNotifier,
    ExternalHookDispatcher,
    ExternalPromptRuleGenerationBackend,
    InternalRuleGenerationBackend,
    MockLLMClient,
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
        self.chat_history_store = InMemoryChatHistoryStore()
        self.rule_repository = InMemoryRuleRepository()
        self.feedback_repository = InMemoryFeedbackRepository()
        self.memory_repository = InMemoryMemoryRepository()
        self.detection_result_repository = InMemoryDetectionResultRepository()

        self.llm_client = MockLLMClient()
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


def _from_payload(payload: RulePayload) -> DetectionRule:
    """将 API 的 `RulePayload` 转换为领域对象 `DetectionRule`。"""
    return DetectionRule(
        rule_id=payload.rule_id,
        name=payload.name,
        description=payload.description,
        target_session=SessionTarget(
            mode=SessionMatchMode(payload.target_session.mode),
            query=payload.target_session.query,
        ),
        topic_hints=payload.topic_hints,
        score_threshold=payload.score_threshold,
        enabled=payload.enabled,
        parameters=[
            RuleParameterSpec(
                key=item.key,
                description=item.description,
                required=item.required,
            )
            for item in payload.parameters
        ],
    )


def _to_payload(rule: DetectionRule) -> RulePayload:
    """将领域对象 `DetectionRule` 转换成 API 可序列化的 `RulePayload`。"""
    return RulePayload(
        rule_id=rule.rule_id,
        name=rule.name,
        description=rule.description,
        target_session={"mode": rule.target_session.mode.value, "query": rule.target_session.query},
        topic_hints=rule.topic_hints,
        score_threshold=rule.score_threshold,
        enabled=rule.enabled,
        parameters=[
            {
                "key": item.key,
                "description": item.description,
                "required": item.required,
            }
            for item in rule.parameters
        ],
    )


def _convert_content_item(item: MessageContentPayload) -> MessageContent:
    return MessageContent(
        type=ContentType(item.type),
        text=item.text,
        image_url=item.image_url,
        mention_user_id=item.mention_user_id,
    )


def _convert_message_payload(payload: MessagePayload) -> ChatMessage:
    reply_from = _convert_message_payload(payload.reply_from) if payload.reply_from else None
    return ChatMessage(
        message_id=payload.message_id,
        chat_id=payload.chat_id,
        sender_id=payload.sender_id,
        sender_name=payload.sender_name,
        contents=[_convert_content_item(item) for item in payload.contents],
        reply_from=reply_from,
        timestamp=payload.timestamp,
    )


def create_app() -> FastAPI:
    """创建并返回 FastAPI 应用实例。"""
    app = FastAPI(title="ChatGuardian API", version="0.1.0")
    container = AppContainer()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "time": datetime.utcnow().isoformat()}

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

    @app.post("/rules", response_model=RulePayload)
    async def upsert_rule(payload: RulePayload) -> RulePayload:
        saved = await container.rule_repository.upsert(_from_payload(payload))
        return _to_payload(saved)

    @app.post("/detect", response_model=DetectResponse)
    async def detect(payload: DetectRequest) -> DetectResponse:
        message = _convert_message_payload(payload.message)
        await container.chat_history_store.append_message(message)

        event = ChatEvent(
            chat_type=ChatType(payload.chat_type),
            chat_id=payload.message.chat_id,
            message=message,
            platform=payload.platform,
            is_from_self=payload.is_from_self,
        )

        await container.self_message_service.process_if_self_message(event)
        engine_output = await container.detection_engine.process_event(event)
        triggered = [decision.rule_id for decision in engine_output.result.decisions if decision.triggered]

        return DetectResponse(
            event_id=engine_output.result.event_id,
            triggered_rule_ids=triggered,
            notified_count=engine_output.notified_count,
        )

    @app.post("/feedback")
    async def submit_feedback(payload: FeedbackPayload) -> dict[str, str]:
        await container.feedback_repository.add(
            Feedback(
                rule_id=payload.rule_id,
                event_id=payload.event_id,
                score=payload.score,
                comment=payload.comment,
            )
        )
        return {"status": "accepted"}

    @app.get("/suggestions/new-rules/{user_id}", response_model=SuggestResponse)
    async def suggest_new_rules(user_id: str) -> SuggestResponse:
        suggestions = await container.suggestion_service.suggest_new_rules(user_id)
        return SuggestResponse(suggestions=suggestions)

    @app.get("/suggestions/rule-improvements/{rule_id}", response_model=SuggestResponse)
    async def suggest_rule_improvements(rule_id: str) -> SuggestResponse:
        suggestions = await container.suggestion_service.suggest_rule_improvements(rule_id)
        return SuggestResponse(suggestions=suggestions)

    @app.post("/rule-generation", response_model=RulePayload)
    async def generate_rule(payload: RuleGenerateRequest) -> RulePayload:
        try:
            generated = await container.rule_authoring_service.generate_rule(
                utterance=payload.utterance,
                use_external=payload.use_external,
                override_system_prompt=payload.override_system_prompt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return _to_payload(generated)

    @app.post("/mcp/tools/generate-rule", response_model=RulePayload)
    async def mcp_generate_rule(payload: RuleGenerateRequest) -> RulePayload:
        return await generate_rule(payload)

    return app
