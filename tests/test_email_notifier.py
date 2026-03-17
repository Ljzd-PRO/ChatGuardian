"""Unit tests for EmailNotifier.test() method.

Uses monkeypatching to replace aiosmtplib.SMTP with a controllable fake so
that no real network connections are made.
"""
from __future__ import annotations

import chat_guardian.notifiers.email as email_module
from chat_guardian.notifiers.email import EmailNotifier, NotificationConfig


class _FakeSMTP:
    """Controllable SMTP stub for unit testing."""

    def __init__(
            self,
            *,
            fail_on: str | None = None,
            recorded: list[str] | None = None,
    ):
        """
        Args:
            fail_on: If set, raise RuntimeError when this method name is called.
            recorded: If provided, method call names are appended to this list.
        """
        self._fail_on = fail_on
        self._recorded = recorded if recorded is not None else []

    def _record(self, name: str) -> None:
        self._recorded.append(name)
        if self._fail_on == name:
            raise RuntimeError(f"_FakeSMTP: forced failure on {name!r}")

    async def connect(self):
        self._record("connect")

    async def login(self, username: str, password: str):
        self._record("login")

    async def sendmail(self, sender: str, recipients: list[str], message: str):
        self._record("sendmail")

    async def quit(self):
        self._record("quit")


def _make_notifier(to_email: str = "test@example.com") -> EmailNotifier:
    return EmailNotifier(NotificationConfig(to_email=to_email))


def _patch_smtp(monkeypatch, smtp_instance: _FakeSMTP) -> None:
    """Replace email_module.SMTP constructor with one that returns *smtp_instance*."""

    def _fake_smtp_constructor(**kwargs):
        return smtp_instance

    monkeypatch.setattr(email_module, "SMTP", _fake_smtp_constructor)


def _patch_settings(monkeypatch, *, smtp_host="smtp.example.com", smtp_sender="sender@example.com",
                    smtp_username: str | None = None, smtp_password: str | None = None,
                    smtp_port: int = 587) -> None:
    monkeypatch.setattr(email_module.settings, "smtp_host", smtp_host)
    monkeypatch.setattr(email_module.settings, "smtp_port", smtp_port)
    monkeypatch.setattr(email_module.settings, "smtp_sender", smtp_sender)
    monkeypatch.setattr(email_module.settings, "smtp_username", smtp_username)
    monkeypatch.setattr(email_module.settings, "smtp_password", smtp_password)


async def test_email_test_returns_true_on_success(monkeypatch):
    """test() returns True when SMTP commands complete without error."""
    recorded: list[str] = []
    smtp = _FakeSMTP(recorded=recorded)
    _patch_settings(monkeypatch)
    _patch_smtp(monkeypatch, smtp)

    notifier = _make_notifier()
    ok = await notifier.test()

    assert ok is True
    assert "connect" in recorded
    assert "sendmail" in recorded
    assert "quit" in recorded


async def test_email_test_calls_login_when_credentials_provided(monkeypatch):
    """test() calls smtp.login() when smtp_username and smtp_password are set."""
    recorded: list[str] = []
    smtp = _FakeSMTP(recorded=recorded)
    _patch_settings(monkeypatch, smtp_username="user", smtp_password="pass")
    _patch_smtp(monkeypatch, smtp)

    ok = await _make_notifier().test()

    assert ok is True
    assert "login" in recorded


async def test_email_test_skips_login_when_no_credentials(monkeypatch):
    """test() skips smtp.login() when username/password are absent."""
    recorded: list[str] = []
    smtp = _FakeSMTP(recorded=recorded)
    _patch_settings(monkeypatch, smtp_username=None, smtp_password=None)
    _patch_smtp(monkeypatch, smtp)

    ok = await _make_notifier().test()

    assert ok is True
    assert "login" not in recorded


async def test_email_test_returns_false_when_missing_config(monkeypatch):
    """test() returns False when smtp_host is not configured."""
    _patch_settings(monkeypatch, smtp_host=None)
    ok = await _make_notifier().test()
    assert ok is False


async def test_email_test_returns_false_when_to_email_missing():
    """test() returns False when the NotificationConfig has no to_email."""
    notifier = EmailNotifier(NotificationConfig(to_email=None))
    ok = await notifier.test()
    assert ok is False


async def test_email_test_returns_false_on_smtp_exception(monkeypatch):
    """test() returns False when SMTP raises an exception during sendmail."""
    recorded: list[str] = []
    smtp = _FakeSMTP(fail_on="sendmail", recorded=recorded)
    _patch_settings(monkeypatch)
    _patch_smtp(monkeypatch, smtp)

    ok = await _make_notifier().test()

    assert ok is False


async def test_email_test_calls_quit_even_on_exception(monkeypatch):
    """test() must call smtp.quit() in the finally block even when sendmail fails."""
    recorded: list[str] = []
    smtp = _FakeSMTP(fail_on="sendmail", recorded=recorded)
    _patch_settings(monkeypatch)
    _patch_smtp(monkeypatch, smtp)

    await _make_notifier().test()

    assert "connect" in recorded
    assert "quit" in recorded


async def test_email_test_does_not_call_quit_when_connect_fails(monkeypatch):
    """If connect() itself fails, quit() must NOT be called (not connected)."""
    recorded: list[str] = []
    smtp = _FakeSMTP(fail_on="connect", recorded=recorded)
    _patch_settings(monkeypatch)
    _patch_smtp(monkeypatch, smtp)

    ok = await _make_notifier().test()

    assert ok is False
    # connect raised → connected=False → finally block must not call quit
    assert "quit" not in recorded
