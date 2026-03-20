from datetime import datetime

from chat_guardian.domain import (
    ChatMessage,
    ContentType,
    DetectionRule,
    MessageContent,
    RuleDecision,
)
from chat_guardian.matcher import MatchChatInfo
from chat_guardian.rule_batch import RuleBatchScheduler


class FlakyLLM:
    def __init__(self):
        self.calls = 0

    async def evaluate(self, messages, rules):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("first attempt fails")
        return [
            RuleDecision(
                rule_id=rule.rule_id,
                triggered=False,
                confidence=0.2,
                reason="ok",
            )
            for rule in rules
        ]


class CountingLLM:
    def __init__(self):
        self.calls = 0

    async def evaluate(self, messages, rules):
        self.calls += 1
        return [
            RuleDecision(
                rule_id=rule.rule_id,
                triggered=False,
                confidence=0.1,
                reason="ok",
            )
            for rule in rules
        ]


def _build_messages() -> list[ChatMessage]:
    return [
        ChatMessage(
            message_id="m-1",
            chat_id="chat-1",
            sender_id="u-1",
            sender_name="user",
            timestamp=datetime.utcnow(),
            contents=[MessageContent(type=ContentType.TEXT, text="hello")],
        )
    ]


def _build_rules(count: int) -> list[DetectionRule]:
    return [
        DetectionRule(
            rule_id=f"r-{index}",
            name=f"rule-{index}",
            description="d",
            matcher=MatchChatInfo(chat_id="chat-1"),
            topic_hints=["hello"],
        )
        for index in range(count)
    ]


async def test_scheduler_retry_eventually_succeeds() -> None:
    llm = FlakyLLM()
    scheduler = RuleBatchScheduler(
        llm_client=llm,
        batch_size=2,
        max_parallel_batches=1,
        batch_timeout_seconds=5,
        max_retries=1,
        rate_limit_per_second=0,
        idempotency_cache_size=128,
    )

    decisions = await scheduler.evaluate_rules(
        messages=_build_messages(),
        rules=_build_rules(2),
        request_id="req-1",
    )

    assert len(decisions) == 2
    assert llm.calls == 2
    metrics = scheduler.diagnostics().metrics
    assert metrics.retry_attempts == 1


async def test_scheduler_idempotent_request_reuses_cached_result() -> None:
    llm = CountingLLM()
    scheduler = RuleBatchScheduler(
        llm_client=llm,
        batch_size=2,
        max_parallel_batches=2,
        batch_timeout_seconds=5,
        max_retries=0,
        rate_limit_per_second=0,
        idempotency_cache_size=128,
    )

    messages = _build_messages()
    rules = _build_rules(4)

    first = await scheduler.evaluate_rules(messages=messages, rules=rules, request_id="req-idempotent")
    second = await scheduler.evaluate_rules(messages=messages, rules=rules, request_id="req-idempotent")

    assert len(first) == 4
    assert len(second) == 4
    assert llm.calls == 2
    metrics = scheduler.diagnostics().metrics
    assert metrics.idempotency_completed_hits >= 2
