import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import chat_guardian.repositories as _repos
from chat_guardian.api.app import create_app
from chat_guardian.domain import (
    ChatMessage, ChatEvent, ChatType, MessageContent, ContentType, UserInfo,
    DetectionResult, RuleDecision, UserMemoryFact,
)


def _register_and_login(client: TestClient) -> dict[str, str]:
    """注册并登录管理员，返回认证 headers。"""
    username = "admin"
    password = "pass"

    # 测试在持久化数据库上运行时，管理员凭据可能已存在且密码未知；
    # 直接重置为固定值，确保登录流程稳定可复现。
    client.app.state.container.admin_credential_repository.set_credentials(username, password)

    register_resp = client.post(
        "/api/auth/register",
        json={"username": username, "password": password},
    )
    assert register_resp.status_code in (200, 400), (
        f"Unexpected status from /api/auth/register: {register_resp.status_code}, "
        f"body={register_resp.text}"
    )

    login_resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login_resp.status_code == 200, (
        f"Login failed: status={login_resp.status_code}, body={login_resp.text}"
    )
    login_data = login_resp.json()
    assert "token" in login_data, f"Login response missing token field: {login_data}"
    token = login_data["token"]
    return {"Authorization": f"Bearer {token}"}


def test_api_rule_and_detect_flow() -> None:
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

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
    headers = _register_and_login(client)

    response = client.get("/llm/health", params={"do_ping": False}, headers=headers)
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
    headers = _register_and_login(client)

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


def test_change_password_can_optionally_change_username() -> None:
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post(
        "/api/auth/change-password",
        json={
            "username": "admin",
            "old_password": "pass",
            "new_password": "newpass123",
            "new_username": "newadmin",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    old_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "newpass123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login",
        json={"username": "newadmin", "password": "newpass123"},
    )
    assert new_login.status_code == 200, new_login.text


def test_register_rejects_password_shorter_than_4(tmp_path, monkeypatch) -> None:
    _setup_isolated_db(tmp_path, monkeypatch)
    app = create_app()
    client = TestClient(app)

    resp = client.post(
        "/api/auth/register",
        json={"username": "admin", "password": "123"},
    )
    assert resp.status_code == 400
    assert "at least 4 characters" in resp.text


def test_change_password_rejects_new_password_shorter_than_4() -> None:
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post(
        "/api/auth/change-password",
        json={
            "username": "admin",
            "old_password": "pass",
            "new_password": "123",
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "at least 4 characters" in resp.text


def test_agent_chat_accepts_json_body(monkeypatch) -> None:
    events: list[list[dict[str, str]]] = []

    class StubAdminAgent:
        def __init__(self, operations):
            pass

        async def stream(self, messages, is_disconnected=None):
            events.append(messages)
            yield {"type": "done"}

    monkeypatch.setattr("chat_guardian.api.app.AdminAgent", StubAdminAgent)

    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post(
        "/api/agent/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert any("done" in line for line in resp.text.splitlines())
    assert events and events[0][0]["content"] == "hello"


def test_logs_restart_endpoint_returns_restarting_status(monkeypatch) -> None:
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)
    monkeypatch.setattr("chat_guardian.api.app.os.kill", lambda _pid, _sig: None)

    resp = client.post("/api/logs/restart", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "restarting"


def test_update_settings_rejects_enabling_mcp_http_without_auth_key() -> None:
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post(
        "/api/settings",
        json={"mcp_http_enabled": True, "mcp_http_auth_key": ""},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "auth key" in resp.text


def _make_detection_result(rule_id: str, result_id: str, triggered: bool = True) -> DetectionResult:
    """Helper to build a minimal DetectionResult for testing."""
    return DetectionResult(
        result_id=result_id,
        event_id=f"evt-{result_id}",
        rule_id=rule_id,
        adapter="test",
        chat_type="group",
        chat_id="chat-test",
        message_id=f"msg-{result_id}",
        decision=RuleDecision(
            rule_id=rule_id,
            triggered=triggered,
            confidence=0.9,
            reason="test trigger reason",
        ),
        context_messages=[],
        generated_at=datetime.now(timezone.utc),
        trigger_suppressed=False,
    )


def _setup_isolated_db(tmp_path, monkeypatch) -> None:
    """Point the app at a fresh per-test SQLite file so tests don't share state."""
    db_path = str(tmp_path / "test.sqlite")
    monkeypatch.setattr("chat_guardian.settings.settings.database_url", f"sqlite:///{db_path}")
    # Clear the DB manager cache so the new URL creates a fresh manager
    monkeypatch.setattr(_repos, "_DB_MANAGERS", {})


# ── User Profile endpoints ─────────────────────────────────────────────────

def test_delete_user_profile_not_found() -> None:
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.delete("/api/user_profiles/nonexistent-user", headers=headers)
    assert resp.status_code == 404, resp.text


def test_delete_user_profile_success(tmp_path, monkeypatch) -> None:
    _setup_isolated_db(tmp_path, monkeypatch)
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    # Seed a profile directly into the repository
    profile = UserMemoryFact(user_id="test-user-del", user_name="Test User")
    container = app.state.container
    asyncio.run(container.memory_repository.upsert_profile(profile))

    resp = client.delete("/api/user_profiles/test-user-del", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("status") == "deleted"

    # Confirm it's gone
    resp2 = client.delete("/api/user_profiles/test-user-del", headers=headers)
    assert resp2.status_code == 404


# ── Rule Stats endpoints ───────────────────────────────────────────────────

def test_get_rule_stat_not_found(tmp_path, monkeypatch) -> None:
    _setup_isolated_db(tmp_path, monkeypatch)
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.get("/api/rule_stats/nonexistent-rule", headers=headers)
    assert resp.status_code == 404, resp.text


def test_get_rule_stat_success(tmp_path, monkeypatch) -> None:
    _setup_isolated_db(tmp_path, monkeypatch)
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    # Create a rule and seed a detection result
    rule_payload = {
        "rule_id": "rule-stat-test",
        "name": "Stat Test Rule",
        "description": "for stats",
        "matcher": {"type": "chat", "chat_id": "chat-s"},
        "topic_hints": ["test"],
        "score_threshold": 0.5,
        "enabled": True,
        "parameters": [],
    }
    client.post("/rules", json=rule_payload, headers=headers)

    container = app.state.container
    result = _make_detection_result("rule-stat-test", "res-1")
    asyncio.run(container.detection_result_repository.add(result))

    resp = client.get("/api/rule_stats/rule-stat-test", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rule_id"] == "rule-stat-test"
    assert len(data["records"]) == 1
    assert data["records"][0]["result_id"] == "res-1"


def test_delete_rule_records_selective(tmp_path, monkeypatch) -> None:
    _setup_isolated_db(tmp_path, monkeypatch)
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    # Create rule and seed two results
    rule_payload = {
        "rule_id": "rule-del-selective",
        "name": "Del Selective",
        "description": "",
        "matcher": {"type": "chat", "chat_id": "chat-d"},
        "topic_hints": [],
        "score_threshold": 0.5,
        "enabled": True,
        "parameters": [],
    }
    client.post("/rules", json=rule_payload, headers=headers)

    container = app.state.container
    r1 = _make_detection_result("rule-del-selective", "res-a")
    r2 = _make_detection_result("rule-del-selective", "res-b")
    asyncio.run(container.detection_result_repository.add(r1))
    asyncio.run(container.detection_result_repository.add(r2))

    # Delete only res-a
    resp = client.request(
        "DELETE",
        "/api/rule_stats/rule-del-selective/records",
        json={"record_ids": ["res-a"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["deleted"] == 1

    # Confirm res-b still exists
    stat_resp = client.get("/api/rule_stats/rule-del-selective", headers=headers)
    records = stat_resp.json()["records"]
    assert len(records) == 1
    assert records[0]["result_id"] == "res-b"


def test_delete_rule_records_clear_all(tmp_path, monkeypatch) -> None:
    _setup_isolated_db(tmp_path, monkeypatch)
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    rule_payload = {
        "rule_id": "rule-del-all",
        "name": "Del All",
        "description": "",
        "matcher": {"type": "chat", "chat_id": "chat-da"},
        "topic_hints": [],
        "score_threshold": 0.5,
        "enabled": True,
        "parameters": [],
    }
    client.post("/rules", json=rule_payload, headers=headers)

    container = app.state.container
    r1 = _make_detection_result("rule-del-all", "res-c")
    r2 = _make_detection_result("rule-del-all", "res-d")
    asyncio.run(container.detection_result_repository.add(r1))
    asyncio.run(container.detection_result_repository.add(r2))

    # Clear all (record_ids=null)
    resp = client.request(
        "DELETE",
        "/api/rule_stats/rule-del-all/records",
        json={"record_ids": None},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["deleted"] == 2

    stat_resp = client.get("/api/rule_stats/rule-del-all", headers=headers)
    assert stat_resp.json()["records"] == []


def test_delete_rule_records_invalid_body_rejected(tmp_path, monkeypatch) -> None:
    """A non-object body (e.g., bare string) must return 422, not silently clear all records."""
    _setup_isolated_db(tmp_path, monkeypatch)
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    rule_payload = {
        "rule_id": "rule-del-invalid",
        "name": "Del Invalid",
        "description": "",
        "matcher": {"type": "chat", "chat_id": "chat-di"},
        "topic_hints": [],
        "score_threshold": 0.5,
        "enabled": True,
        "parameters": [],
    }
    client.post("/rules", json=rule_payload, headers=headers)

    container = app.state.container
    r = _make_detection_result("rule-del-invalid", "res-e")
    asyncio.run(container.detection_result_repository.add(r))

    # Sending a bare string instead of an object must be rejected
    resp = client.request(
        "DELETE",
        "/api/rule_stats/rule-del-invalid/records",
        content=b'"delete everything"',
        headers={**headers, "content-type": "application/json"},
    )
    assert resp.status_code == 422, resp.text

    # The record should still be there
    stat_resp = client.get("/api/rule_stats/rule-del-invalid", headers=headers)
    assert len(stat_resp.json()["records"]) == 1
