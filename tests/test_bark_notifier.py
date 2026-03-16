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
    def __init__(self, recorder: list[dict], response: _FakeResponse | None = None):
        self._recorder = recorder
        self._response = response or _FakeResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url: str, json: dict):
        self._recorder.append({"url": url, "json": json})
        return self._response


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
    assert isinstance(payload["body"], str)
    assert "规则: r-1" in payload["body"]
    assert "会话: g-1" in payload["body"]
    assert "消息ID: m-1" in payload["body"]
    assert "参数: k=v" in payload["body"]


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


# ── BarkNotifier.test() ──────────────────────────────────────────────────────

async def test_bark_test_single_key_success(monkeypatch):
    """test() sends push to single device_key and returns True on 200/200."""
    recorded: list[dict] = []
    monkeypatch.setattr(
        bark_module.httpx,
        "AsyncClient",
        lambda timeout: _RecorderClient(recorded, _FakeResponse(200, {"code": 200})),
    )

    notifier = BarkNotifier(BarkNotificationConfig(device_key="test-key"))
    ok = await notifier.test()

    assert ok is True
    assert len(recorded) == 1
    payload = recorded[0]["json"]
    assert payload["device_key"] == "test-key"
    assert "device_keys" not in payload


async def test_bark_test_multiple_keys_success(monkeypatch):
    """test() uses device_keys when multiple keys are configured."""
    recorded: list[dict] = []
    monkeypatch.setattr(
        bark_module.httpx,
        "AsyncClient",
        lambda timeout: _RecorderClient(recorded, _FakeResponse(200, {"code": 200})),
    )

    notifier = BarkNotifier(BarkNotificationConfig(device_key=None, device_keys=["k1", "k2"]))
    ok = await notifier.test()

    assert ok is True
    payload = recorded[0]["json"]
    assert payload["device_keys"] == ["k1", "k2"]
    assert "device_key" not in payload


async def test_bark_test_no_keys_returns_false():
    """test() returns False immediately when no device keys are configured."""
    notifier = BarkNotifier(BarkNotificationConfig(device_key=None, device_keys=[]))
    ok = await notifier.test()
    assert ok is False


async def test_bark_test_non_200_http_status_returns_false(monkeypatch):
    """test() returns False when the HTTP response status is not 200."""
    recorded: list[dict] = []
    monkeypatch.setattr(
        bark_module.httpx,
        "AsyncClient",
        lambda timeout: _RecorderClient(recorded, _FakeResponse(500, {})),
    )

    notifier = BarkNotifier(BarkNotificationConfig(device_key="key"))
    ok = await notifier.test()
    assert ok is False


async def test_bark_test_non_200_json_code_returns_false(monkeypatch):
    """test() returns False when JSON body contains a non-200 code."""
    recorded: list[dict] = []
    monkeypatch.setattr(
        bark_module.httpx,
        "AsyncClient",
        lambda timeout: _RecorderClient(recorded, _FakeResponse(200, {"code": 400, "message": "bad key"})),
    )

    notifier = BarkNotifier(BarkNotificationConfig(device_key="bad-key"))
    ok = await notifier.test()
    assert ok is False


async def test_bark_test_http_error_returns_false(monkeypatch):
    """test() returns False when an httpx.HTTPError is raised."""
    import httpx

    class _ErrorClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url: str, json: dict):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(bark_module.httpx, "AsyncClient", lambda timeout: _ErrorClient())

    notifier = BarkNotifier(BarkNotificationConfig(device_key="key"))
    ok = await notifier.test()
    assert ok is False
