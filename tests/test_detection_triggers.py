from datetime import datetime

import asyncio

from chat_guardian.domain import (
    ChatEvent,
    ChatMessage,
    ChatType,
    ContentType,
    DetectionRule,
    MessageContent,
    RuleDecision,
    SessionMatchMode,
    SessionTarget,
)
from chat_guardian.repositories import (
    InMemoryChatHistoryStore,
    InMemoryDetectionResultRepository,
    InMemoryRuleRepository,
)
from chat_guardian.services import ContextWindowService, DetectionEngine, ExternalHookDispatcher
from chat_guardian.settings import settings


class FakeLLM:
    async def evaluate(self, messages, rules):
        return [
            RuleDecision(
                rule_id=rule.rule_id,
                triggered=False,
                confidence=0.2,
                reason="test",
            )
            for rule in rules
        ]

    async def extract_self_participation(self, event, context):
        return []


class FakeNotifier:
    async def notify(self, event, decision, context_messages):
        return True


def _build_event(message_id: str, second: int) -> ChatEvent:
    message = ChatMessage(
        message_id=message_id,
        chat_id="g-1",
        sender_id="u-1",
        sender_name="user",
        contents=[MessageContent(type=ContentType.TEXT, text=f"hello-{message_id}")],
        reply_from=None,
        timestamp=datetime.utcfromtimestamp(second),
    )
    return ChatEvent(
        chat_type=ChatType.GROUP,
        chat_id="g-1",
        message=message,
        platform="onebot",
        is_from_self=False,
    )


async def test_ingest_event_respects_min_new_messages_threshold() -> None:
    old_min_new = settings.detection_min_new_messages
    old_cooldown = settings.detection_cooldown_seconds
    old_timeout = settings.detection_wait_timeout_seconds
    settings.detection_min_new_messages = 3
    settings.detection_cooldown_seconds = 0.0
    settings.detection_wait_timeout_seconds = 0.2

    store = InMemoryChatHistoryStore(pending_queue_limit=100, history_list_limit=100)
    rules_repo = InMemoryRuleRepository()
    results_repo = InMemoryDetectionResultRepository()

    await rules_repo.upsert(
        DetectionRule(
            rule_id="r-1",
            name="rule",
            description="d",
            target_session=SessionTarget(mode=SessionMatchMode.EXACT, query="g-1"),
            topic_hints=["hello"],
        )
    )

    engine = DetectionEngine(
        rules=rules_repo,
        context_service=ContextWindowService(store),
        llm_client=FakeLLM(),
        result_repository=results_repo,
        notifiers=[FakeNotifier()],
        hook_dispatcher=ExternalHookDispatcher([]),
    )

    output_1 = await engine.ingest_event(_build_event("m-1", 1))
    output_2 = await engine.ingest_event(_build_event("m-2", 2))
    output_3 = await engine.ingest_event(_build_event("m-3", 3))

    assert output_1 is None
    assert output_2 is None
    assert output_3 is not None
    assert len(results_repo.results) == 1

    settings.detection_min_new_messages = old_min_new
    settings.detection_cooldown_seconds = old_cooldown
    settings.detection_wait_timeout_seconds = old_timeout


async def test_ingest_event_forces_detection_on_timeout() -> None:
    old_min_new = settings.detection_min_new_messages
    old_cooldown = settings.detection_cooldown_seconds
    old_timeout = settings.detection_wait_timeout_seconds
    settings.detection_min_new_messages = 3
    settings.detection_cooldown_seconds = 0.0
    settings.detection_wait_timeout_seconds = 0.05

    store = InMemoryChatHistoryStore(pending_queue_limit=100, history_list_limit=100)
    rules_repo = InMemoryRuleRepository()
    results_repo = InMemoryDetectionResultRepository()

    await rules_repo.upsert(
        DetectionRule(
            rule_id="r-1",
            name="rule",
            description="d",
            target_session=SessionTarget(mode=SessionMatchMode.EXACT, query="g-1"),
            topic_hints=["hello"],
        )
    )

    engine = DetectionEngine(
        rules=rules_repo,
        context_service=ContextWindowService(store),
        llm_client=FakeLLM(),
        result_repository=results_repo,
        notifiers=[FakeNotifier()],
        hook_dispatcher=ExternalHookDispatcher([]),
    )

    output = await engine.ingest_event(_build_event("m-1", 1))
    assert output is None

    await asyncio.sleep(0.12)
    assert len(results_repo.results) == 1

    settings.detection_min_new_messages = old_min_new
    settings.detection_cooldown_seconds = old_cooldown
    settings.detection_wait_timeout_seconds = old_timeout
