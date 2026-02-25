from datetime import datetime, timezone

from fastapi.testclient import TestClient

from chat_guardian.api.app import create_app


def test_api_rule_and_detect_flow() -> None:
    app = create_app()
    client = TestClient(app)

    create_rule = {
        "rule_id": "rule-1",
        "name": "Topic monitor",
        "description": "generic topic monitor",
        "target_session": {"mode": "exact", "query": "chat-1"},
        "topic_hints": ["topic"],
        "score_threshold": 0.5,
        "enabled": False,
        "parameters": [{"key": "tag", "description": "topic tag", "required": False}],
    }
    response = client.post("/rules", json=create_rule)
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
    response = client.post("/detect", json=detect_payload)
    assert response.status_code == 200
    data = response.json()
    assert "event_id" in data


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
