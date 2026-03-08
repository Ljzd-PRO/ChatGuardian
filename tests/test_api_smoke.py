import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from chat_guardian.api.app import create_app
from chat_guardian.domain import ChatMessage, ChatEvent, ChatType, MessageContent, ContentType, UserInfo


def test_api_rule_and_detect_flow() -> None:
    app = create_app()
    client = TestClient(app)

    # 注册并登录以获取认证令牌
    client.post("/api/auth/register", json={"username": "admin", "password": "pass"})
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "pass"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_rule = {
        "rule_id": "rule-1",
        "name": "Topic monitor",
        "description": "generic topic monitor",
        "matcher": {"type": "chat", "chat_id": "chat-1"},
        "topic_hints": ["topic"],
        "score_threshold": 0.5,
        "enabled": False,
        "parameters": [{"key": "tag", "description": "topic tag", "required": False}],
    }
    response = client.post("/rules", json=create_rule, headers=headers)
    assert response.status_code == 200

    detect_payload = {
        "platform": "test",
        "chat_type": "group",
        "is_from_self": False,
        "message": {
            "message_id": "m-1",
            "chat_id": "chat-1",
            "sender_id": "u-1",
            "sender_name": "tester",
            "contents": [
                {"type": "text", "text": "this topic is interesting"},
                {"type": "mention", "mention_user_id": "u-2"},
            ],
            "reply_from": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    # Simulate adapter-driven detection by constructing domain event
    contents = [
        MessageContent(type=ContentType("text"), text="this topic is interesting"),
        MessageContent(type=ContentType("mention"), mention_user=UserInfo(user_id="u-2")),
    ]

    message = ChatMessage(
        message_id="m-1",
        chat_id="chat-1",
        sender_id="u-1",
        sender_name="tester",
        contents=contents,
        reply_from=None,
        timestamp=datetime.now(timezone.utc),
    )

    event = ChatEvent(
        chat_type=ChatType("group"),
        chat_id="chat-1",
        message=message,
        platform="test",
        is_from_self=False,
    )

    # call the container handler directly (adapter would invoke this)
    container = app.state.container
    asyncio.run(container.handle_adapter_event(event))


def test_llm_health_endpoint_without_ping() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/llm/health", params={"do_ping": False})
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert "llm" in payload
    assert payload["llm"]["backend"] in {"openai_compatible", "ollama"}
    assert "model" in payload["llm"]
    assert "scheduler" in payload
    assert "metrics" in payload["scheduler"]


def test_rule_list_and_delete_flow() -> None:
    app = create_app()
    client = TestClient(app)

    # 注册并登录以获取认证令牌
    client.post("/api/auth/register", json={"username": "admin", "password": "pass"})
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "pass"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    rule_payload = {
        "rule_id": "rule-to-delete",
        "name": "Rule to delete",
        "description": "temp rule",
        "matcher": {"type": "chat", "chat_id": "chat-del"},
        "topic_hints": ["tmp"],
        "score_threshold": 0.5,
        "enabled": True,
        "parameters": [],
    }

    create_resp = client.post("/rules", json=rule_payload, headers=headers)
    assert create_resp.status_code == 200

    list_resp = client.get("/rules/list", headers=headers)
    assert list_resp.status_code == 200
    rules = list_resp.json()
    assert any(item["rule_id"] == "rule-to-delete" for item in rules)

    delete_resp = client.post("/rules/delete/rule-to-delete", headers=headers)
    assert delete_resp.status_code == 200
    delete_data = delete_resp.json()
    assert delete_data["deleted"] is True

    list_after_resp = client.get("/rules/list", headers=headers)
    assert list_after_resp.status_code == 200
    rules_after = list_after_resp.json()
    assert all(item["rule_id"] != "rule-to-delete" for item in rules_after)
