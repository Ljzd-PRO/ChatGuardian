from datetime import datetime

import chat_guardian.notifiers.bark as bark_module
from chat_guardian.domain import (
    ChatEvent,
    ChatMessage,
    ChatType,
    ContentType,
    MessageContent,
    RuleDecision,
)
from chat_guardian.notifiers.bark import BarkNotificationConfig, BarkNotifier


class _FakeResponse:
    def __init__(self, status_code: int = 200, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {"code": 200}
        self.text = "ok"

    def json(self):
        return self._body


class _RecorderClient:
    def __init__(self, recorder: list[dict]):
        self._recorder = recorder

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url: str, json: dict):
        self._recorder.append({"url": url, "json": json})
        return _FakeResponse()


def _build_event() -> ChatEvent:
    message = ChatMessage(
        message_id="m-1",
        chat_id="g-1",
        sender_id="u-1",
        sender_name="user-1",
        contents=[MessageContent(type=ContentType.TEXT, text="hello")],
        reply_from=None,
        timestamp=datetime.utcnow(),
    )
    return ChatEvent(chat_type=ChatType.GROUP, chat_id="g-1", message=message, platform="test")


def _build_decision() -> RuleDecision:
    return RuleDecision(rule_id="r-1", triggered=True, confidence=0.9, reason="matched", extracted_params={"k": "v"})


async def test_bark_notifier_uses_device_key_when_single_key(monkeypatch):
    recorded: list[dict] = []
    monkeypatch.setattr(
        bark_module.httpx,
        "AsyncClient",
        lambda timeout: _RecorderClient(recorded),
    )

    notifier = BarkNotifier(BarkNotificationConfig(device_key="single-key"))
    ok = await notifier.notify(_build_event(), _build_decision(), [])

    assert ok is True
    assert len(recorded) == 1
    payload = recorded[0]["json"]
    assert payload["device_key"] == "single-key"
    assert "device_keys" not in payload


async def test_bark_notifier_uses_device_keys_when_multiple_keys(monkeypatch):
    recorded: list[dict] = []
    monkeypatch.setattr(
        bark_module.httpx,
        "AsyncClient",
        lambda timeout: _RecorderClient(recorded),
    )

    notifier = BarkNotifier(BarkNotificationConfig(device_key=None, device_keys=["key-1", "key-2"]))
    ok = await notifier.notify(_build_event(), _build_decision(), [])

    assert ok is True
    assert len(recorded) == 1
    payload = recorded[0]["json"]
    assert payload["device_keys"] == ["key-1", "key-2"]
    assert "device_key" not in payload
