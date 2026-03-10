"""
Tests for MatcherUnion discriminated union serialization/deserialization.

Ensures all Matcher subclasses can be round-tripped through JSON,
that AND/OR nesting works, and that DetectionRule accepts the full union.
"""
from datetime import datetime

from chat_guardian.domain import (
    ChatEvent,
    ChatMessage,
    ChatType,
    ContentType,
    DetectionRule,
    MessageContent,
    UserInfo,
)
from chat_guardian.matcher import (
    AndMatcher,
    MatchAdapter,
    MatchAll,
    MatchChatInfo,
    MatchChatType,
    MatchMention,
    MatchSender,
    OrMatcher,
)


def _make_event(
        chat_type: ChatType = ChatType.GROUP,
        chat_id: str = "c-1",
        sender_id: str = "u-1",
        sender_name: str = "user",
        platform: str = "onebot",
) -> ChatEvent:
    msg = ChatMessage(
        message_id="m-1",
        chat_id=chat_id,
        sender_id=sender_id,
        sender_name=sender_name,
        contents=[MessageContent(type=ContentType.TEXT, text="hello")],
        reply_from=None,
        timestamp=datetime(2026, 1, 1),
    )
    return ChatEvent(
        chat_type=chat_type,
        chat_id=chat_id,
        message=msg,
        platform=platform,
    )


def _round_trip(rule: DetectionRule) -> DetectionRule:
    """Serialize to JSON dict and deserialize back."""
    return DetectionRule.model_validate(rule.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Leaf matcher deserialization
# ---------------------------------------------------------------------------

def test_matchall_from_dict() -> None:
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {"type": "all"},
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, MatchAll)
    assert rule.matcher.matches(_make_event())


def test_match_chat_info_from_dict() -> None:
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {"type": "chat", "chat_id": "c-1"},
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, MatchChatInfo)
    assert rule.matcher.matches(_make_event(chat_id="c-1"))
    assert not rule.matcher.matches(_make_event(chat_id="other"))


def test_match_sender_from_dict() -> None:
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {"type": "sender", "user_id": "u-1"},
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, MatchSender)
    assert rule.matcher.matches(_make_event(sender_id="u-1"))
    assert not rule.matcher.matches(_make_event(sender_id="u-99"))


def test_match_chat_type_from_dict() -> None:
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {"type": "chat_type", "chat_type": "group"},
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, MatchChatType)
    assert rule.matcher.matches(_make_event(chat_type=ChatType.GROUP))
    assert not rule.matcher.matches(_make_event(chat_type=ChatType.PRIVATE))


def test_match_adapter_from_dict() -> None:
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {"type": "adapter", "adapter_name": "onebot"},
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, MatchAdapter)
    assert rule.matcher.matches(_make_event(platform="onebot"))
    assert not rule.matcher.matches(_make_event(platform="telegram"))


def test_match_mention_from_dict() -> None:
    msg = ChatMessage(
        message_id="m-1",
        chat_id="c-1",
        sender_id="u-1",
        sender_name="user",
        contents=[
            MessageContent(
                type=ContentType.MENTION,
                mention_user=UserInfo(user_id="u-2"),
            )
        ],
        reply_from=None,
        timestamp=datetime(2026, 1, 1),
    )
    event = ChatEvent(
        chat_type=ChatType.GROUP,
        chat_id="c-1",
        message=msg,
        platform="onebot",
    )
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {"type": "mention", "user_id": "u-2"},
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, MatchMention)
    assert rule.matcher.matches(event)


# ---------------------------------------------------------------------------
# Compound matcher deserialization
# ---------------------------------------------------------------------------

def test_and_matcher_from_dict() -> None:
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {
            "type": "and",
            "matchers": [
                {"type": "chat", "chat_id": "c-1"},
                {"type": "sender", "user_id": "u-1"},
            ],
        },
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, AndMatcher)
    assert len(rule.matcher.matchers) == 2
    assert isinstance(rule.matcher.matchers[0], MatchChatInfo)
    assert isinstance(rule.matcher.matchers[1], MatchSender)
    assert rule.matcher.matches(_make_event(chat_id="c-1", sender_id="u-1"))
    assert not rule.matcher.matches(_make_event(chat_id="c-1", sender_id="u-99"))


def test_or_matcher_from_dict() -> None:
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {
            "type": "or",
            "matchers": [
                {"type": "sender", "user_id": "u-1"},
                {"type": "sender", "user_id": "u-2"},
            ],
        },
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, OrMatcher)
    assert rule.matcher.matches(_make_event(sender_id="u-1"))
    assert rule.matcher.matches(_make_event(sender_id="u-2"))
    assert not rule.matcher.matches(_make_event(sender_id="u-99"))


def test_nested_and_or() -> None:
    """AND( chat_id, OR( sender_u1, sender_u2 ) ) — complex nesting."""
    rule = DetectionRule.model_validate({
        "rule_id": "r",
        "name": "n",
        "description": "d",
        "matcher": {
            "type": "and",
            "matchers": [
                {"type": "chat", "chat_id": "c-1"},
                {
                    "type": "or",
                    "matchers": [
                        {"type": "sender", "user_id": "u-1"},
                        {"type": "sender", "user_id": "u-2"},
                    ],
                },
            ],
        },
        "topic_hints": [],
    })
    assert isinstance(rule.matcher, AndMatcher)
    assert isinstance(rule.matcher.matchers[1], OrMatcher)
    # Matching cases
    assert rule.matcher.matches(_make_event(chat_id="c-1", sender_id="u-1"))
    assert rule.matcher.matches(_make_event(chat_id="c-1", sender_id="u-2"))
    # Non-matching cases
    assert not rule.matcher.matches(_make_event(chat_id="other", sender_id="u-1"))
    assert not rule.matcher.matches(_make_event(chat_id="c-1", sender_id="u-99"))


# ---------------------------------------------------------------------------
# Round-trip serialization
# ---------------------------------------------------------------------------

def test_round_trip_nested() -> None:
    """Serialize nested AND/OR matcher to JSON and restore it."""
    original = DetectionRule(
        rule_id="r",
        name="n",
        description="d",
        matcher=AndMatcher(
            matchers=[
                MatchChatInfo(chat_id="c-1"),
                OrMatcher(
                    matchers=[
                        MatchSender(user_id="u-1"),
                        MatchSender(user_id="u-2"),
                    ]
                ),
            ]
        ),
        topic_hints=[],
    )
    restored = _round_trip(original)
    assert isinstance(restored.matcher, AndMatcher)
    assert isinstance(restored.matcher.matchers[1], OrMatcher)
    assert len(restored.matcher.matchers[1].matchers) == 2


def test_round_trip_via_api() -> None:
    """Full round-trip through the FastAPI /rules endpoint."""
    from fastapi.testclient import TestClient
    from chat_guardian.api.app import create_app

    app = create_app()
    client = TestClient(app)

    # Register and login to get auth headers
    client.post("/api/auth/register", json={"username": "admin", "password": "pass"})
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "pass"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "rule_id": "matcher-test-rule",
        "name": "Matcher Test",
        "description": "Tests nested AND/OR via API",
        "matcher": {
            "type": "and",
            "matchers": [
                {"type": "chat", "chat_id": "c-1"},
                {
                    "type": "or",
                    "matchers": [
                        {"type": "sender", "user_id": "u-1"},
                        {"type": "sender", "user_id": "u-2"},
                    ],
                },
            ],
        },
        "topic_hints": ["test"],
        "score_threshold": 0.5,
        "enabled": True,
        "parameters": [],
    }

    resp = client.post("/rules", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["matcher"]["type"] == "and"
    assert data["matcher"]["matchers"][1]["type"] == "or"
    assert len(data["matcher"]["matchers"][1]["matchers"]) == 2

    # Verify it persists correctly in list endpoint
    list_resp = client.get("/rules/list", headers=headers)
    assert list_resp.status_code == 200
    found = next(
        (r for r in list_resp.json() if r["rule_id"] == "matcher-test-rule"), None
    )
    assert found is not None
    assert found["matcher"]["type"] == "and"
