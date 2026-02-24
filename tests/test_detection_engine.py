from datetime import datetime

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
    def __init__(self):
        self.batch_sizes: list[int] = []

    async def evaluate(self, messages, rules):
        self.batch_sizes.append(len(rules))
        return [
            RuleDecision(
                rule_id=rule.rule_id,
                triggered=False,
                confidence=0.1,
                reason="test",
            )
            for rule in rules
        ]

    async def extract_self_participation(self, event, context):
        return []


class FakeNotifier:
    async def notify(self, event, decision, context_messages):
        return True


async def test_rules_are_split_into_batches() -> None:
    old_batch_size = settings.llm_rules_per_batch
    old_parallel = settings.llm_max_parallel_batches
    settings.llm_rules_per_batch = 2
    settings.llm_max_parallel_batches = 3

    history = InMemoryChatHistoryStore()
    rules_repo = InMemoryRuleRepository()
    results_repo = InMemoryDetectionResultRepository()
    llm = FakeLLM()

    for index in range(5):
        await rules_repo.upsert(
            DetectionRule(
                rule_id=f"r-{index}",
                name=f"rule-{index}",
                description="d",
                target_session=SessionTarget(mode=SessionMatchMode.EXACT, query="g-1"),
                topic_hints=["topic"],
            )
        )

    engine = DetectionEngine(
        rules=rules_repo,
        context_service=ContextWindowService(history),
        llm_client=llm,
        result_repository=results_repo,
        notifiers=[FakeNotifier()],
        hook_dispatcher=ExternalHookDispatcher([]),
    )

    message = ChatMessage(
        message_id="m1",
        chat_id="g-1",
        sender_id="u1",
        sender_name="user",
        contents=[MessageContent(type=ContentType.TEXT, text="hello")],
        reply_from=None,
        timestamp=datetime.utcnow(),
    )
    await history.append_message(message)

    event = ChatEvent(chat_type=ChatType.GROUP, chat_id="g-1", message=message, platform="test")
    await engine.process_event(event)

    assert sorted(llm.batch_sizes) == [1, 2, 2]

    settings.llm_rules_per_batch = old_batch_size
    settings.llm_max_parallel_batches = old_parallel
