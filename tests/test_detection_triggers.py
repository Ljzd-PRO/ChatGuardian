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
)
from chat_guardian.matcher import MatchChatInfo
from chat_guardian.repositories import (
    ChatHistoryStore,
    DetectionResultRepository,
    RuleRepository,
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


class CountingNotifier:
    def __init__(self):
        self.count = 0

    async def notify(self, event, decision, context_messages):
        self.count += 1
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

    store = ChatHistoryStore(pending_queue_limit=100, history_list_limit=100)
    rules_repo = RuleRepository()
    results_repo = DetectionResultRepository()

    await rules_repo.upsert(
        DetectionRule(
            rule_id="r-1",
            name="rule",
            description="d",
            matcher=MatchChatInfo(chat_id="g-1"),
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

    store = ChatHistoryStore(pending_queue_limit=100, history_list_limit=100)
    rules_repo = RuleRepository()
    results_repo = DetectionResultRepository()

    await rules_repo.upsert(
        DetectionRule(
            rule_id="r-1",
            name="rule",
            description="d",
            matcher=MatchChatInfo(chat_id="g-1"),
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


class TriggeringLLM:
    async def evaluate(self, messages, rules):
        return [
            RuleDecision(
                rule_id=rule.rule_id,
                triggered=True,
                confidence=0.9,
                reason="trigger",
            )
            for rule in rules
        ]

    async def extract_self_participation(self, event, context):
        return []


async def test_trigger_dedup_merges_context_and_skips_retrigger() -> None:
    old_min_new = settings.detection_min_new_messages
    old_cooldown = settings.detection_cooldown_seconds
    old_timeout = settings.detection_wait_timeout_seconds
    settings.detection_min_new_messages = 1
    settings.detection_cooldown_seconds = 0.0
    settings.detection_wait_timeout_seconds = 1.0

    store = ChatHistoryStore(pending_queue_limit=100, history_list_limit=100)
    rules_repo = RuleRepository()
    results_repo = DetectionResultRepository()
    notifier = CountingNotifier()

    await rules_repo.upsert(
        DetectionRule(
            rule_id="r-1",
            name="rule",
            description="d",
            matcher=MatchChatInfo(chat_id="g-1"),
            topic_hints=["hello"],
        )
    )

    engine = DetectionEngine(
        rules=rules_repo,
        context_service=ContextWindowService(store),
        llm_client=TriggeringLLM(),
        result_repository=results_repo,
        notifiers=[notifier],
        hook_dispatcher=ExternalHookDispatcher([]),
    )

    first_output = await engine.ingest_event(_build_event("m-1", 1))
    second_output = await engine.ingest_event(_build_event("m-2", 2))

    assert first_output is not None
    assert second_output is not None
    assert first_output.triggered_rule_ids == ["r-1"]
    assert second_output.triggered_rule_ids == []
    assert notifier.count == 1

    by_rule = await results_repo.list_by_rule("r-1")
    assert len(by_rule) == 2
    assert by_rule[0].trigger_suppressed is False
    assert by_rule[1].trigger_suppressed is True
    assert await results_repo.contains_message_in_last_triggered("r-1", "m-2") is True

    settings.detection_min_new_messages = old_min_new
    settings.detection_cooldown_seconds = old_cooldown
    settings.detection_wait_timeout_seconds = old_timeout
