"""API smoke tests for POST /api/notifications/test/{notifier_type}."""
from __future__ import annotations

from fastapi.testclient import TestClient

from chat_guardian.api.app import create_app


def _register_and_login(client: TestClient) -> dict[str, str]:
    username, password = "admin", "pass"
    client.app.state.container.admin_credential_repository.set_credentials(username, password)
    client.post("/api/auth/register", json={"username": username, "password": password})
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# ── helpers ───────────────────────────────────────────────────────────────────

class _SuccessNotifier:
    async def test(self) -> bool:
        return True


class _FailNotifier:
    async def test(self) -> bool:
        return False


# ── unknown type ──────────────────────────────────────────────────────────────

def test_notification_test_unknown_type_returns_400() -> None:
    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post("/api/notifications/test/unknown_type", headers=headers)
    assert resp.status_code == 400


# ── email ─────────────────────────────────────────────────────────────────────

def test_notification_test_email_not_enabled_returns_400(monkeypatch) -> None:
    """400 when email notifier is disabled / build_email_notifier_from_settings returns None."""
    import chat_guardian.api.app as app_module

    monkeypatch.setattr(app_module, "build_email_notifier_from_settings", lambda: None)

    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post("/api/notifications/test/email", headers=headers)
    assert resp.status_code == 400


def test_notification_test_email_returns_200_on_success(monkeypatch) -> None:
    """200 {ok: true} when EmailNotifier.test() returns True."""
    import chat_guardian.api.app as app_module

    monkeypatch.setattr(app_module, "build_email_notifier_from_settings", lambda: _SuccessNotifier())

    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post("/api/notifications/test/email", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_notification_test_email_returns_502_on_failure(monkeypatch) -> None:
    """502 when EmailNotifier.test() returns False."""
    import chat_guardian.api.app as app_module

    monkeypatch.setattr(app_module, "build_email_notifier_from_settings", lambda: _FailNotifier())

    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post("/api/notifications/test/email", headers=headers)
    assert resp.status_code == 502


# ── bark ──────────────────────────────────────────────────────────────────────

def test_notification_test_bark_not_enabled_returns_400(monkeypatch) -> None:
    """400 when bark notifier is disabled / build_bark_notifier_from_settings returns None."""
    import chat_guardian.api.app as app_module

    monkeypatch.setattr(app_module, "build_bark_notifier_from_settings", lambda: None)

    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post("/api/notifications/test/bark", headers=headers)
    assert resp.status_code == 400


def test_notification_test_bark_returns_200_on_success(monkeypatch) -> None:
    """200 {ok: true} when BarkNotifier.test() returns True."""
    import chat_guardian.api.app as app_module

    monkeypatch.setattr(app_module, "build_bark_notifier_from_settings", lambda: _SuccessNotifier())

    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post("/api/notifications/test/bark", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_notification_test_bark_returns_502_on_failure(monkeypatch) -> None:
    """502 when BarkNotifier.test() returns False."""
    import chat_guardian.api.app as app_module

    monkeypatch.setattr(app_module, "build_bark_notifier_from_settings", lambda: _FailNotifier())

    app = create_app()
    client = TestClient(app)
    headers = _register_and_login(client)

    resp = client.post("/api/notifications/test/bark", headers=headers)
    assert resp.status_code == 502
