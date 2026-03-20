from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from chat_guardian.domain import ChatMessage, ContentType, DetectionRule, MessageContent
from chat_guardian.llm_client import LangChainLLMClient
from chat_guardian.matcher import MatchChatInfo
from chat_guardian.settings import settings


class _FakeModel:
    def __init__(self) -> None:
        self.last_messages = None

    async def ainvoke(self, messages):
        self.last_messages = messages
        return SimpleNamespace(
            content='{"decisions": [{"rule_id": "r-1", "triggered": false, "confidence": 0.1, "reason": "ok", "extracted_params": {}}]}'
        )


@pytest.mark.asyncio
async def test_rule_detection_prompt_uses_custom_setting() -> None:
    model = _FakeModel()
    client = LangChainLLMClient(
        chat_model=model,
        backend="openai_compatible",
        model_name="test-model",
        api_base=None,
        api_key_configured=False,
    )

    old_prompt = settings.rule_detection_system_prompt
    settings.rule_detection_system_prompt = "自定义规则检测提示词"

    try:
        message = ChatMessage(
            message_id="m-1",
            chat_id="c-1",
            sender_id="u-1",
            sender_name="tester",
            timestamp=datetime.now(timezone.utc),
            contents=[MessageContent(type=ContentType.TEXT, text="hello")],
        )
        rule = DetectionRule(
            rule_id="r-1",
            name="rule-1",
            description="desc",
            matcher=MatchChatInfo(chat_id="c-1"),
        )

        decisions = await client.evaluate([message], [rule])

        assert decisions is not None
        assert model.last_messages is not None
        assert model.last_messages[0].content == "自定义规则检测提示词"
    finally:
        settings.rule_detection_system_prompt = old_prompt
