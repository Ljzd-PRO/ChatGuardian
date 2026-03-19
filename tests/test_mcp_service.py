import pytest
from types import SimpleNamespace
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from chat_guardian.mcp import ChatGuardianMCPService, ChatGuardianOperations
from chat_guardian.settings import settings


class _DummyTokenManager:
    def __init__(self):
        self.revoked = []

    def issue(self, username: str) -> str:  # pragma: no cover - simple stub
        return f"token-{username}"

    def revoke(self, token: str) -> None:  # pragma: no cover - simple stub
        self.revoked.append(token)


class _DummyContainer:
    def __init__(self):
        self.admin_username = "admin"
        self.admin_password = "secret"
        self.using_default_credentials = False
        self.token_manager = _DummyTokenManager()


class _DummySettingsRepository:
    def __init__(self):
        self.last_saved = None

    def save(self, payload):
        self.last_saved = payload


class _DummyAdapterManager:
    def __init__(self):
        self.adapters = []

    async def stop_all(self):
        return None


class _DummyMCPRuntimeService:
    def __init__(self):
        self.stop_calls = 0
        self.start_calls = 0

    async def stop_http_server(self):
        self.stop_calls += 1

    async def start_http_server(self, **_kwargs):
        self.start_calls += 1
        return None


@pytest.fixture
def mcp_service():
    container = _DummyContainer()
    ops = ChatGuardianOperations(container=container, env_only_keys=[])
    svc = ChatGuardianMCPService(container=container, operations=ops)
    yield svc


@pytest.mark.asyncio
async def test_tool_health_returns_status(mcp_service: ChatGuardianMCPService):
    async with Context(fastmcp=mcp_service.server):
        result = await mcp_service.call_tool("health")
    _, meta = result.to_mcp_result()
    assert meta["status"] == "ok"
    assert "time" in meta


@pytest.mark.asyncio
async def test_tool_auth_login_and_status_error(mcp_service: ChatGuardianMCPService):
    async with Context(fastmcp=mcp_service.server):
        resp = await mcp_service.call_tool("auth_login", {"username": "admin", "password": "secret"})
    _, meta = resp.to_mcp_result()
    assert meta["token"].startswith("token-admin")

    async with Context(fastmcp=mcp_service.server):
        with pytest.raises(ToolError):
            await mcp_service.call_tool("auth_status", {"username": None})


@pytest.mark.asyncio
async def test_start_http_server_rejects_non_loopback(mcp_service: ChatGuardianMCPService):
    with pytest.raises(ValueError):
        await mcp_service.start_http_server(host="0.0.0.0")


@pytest.mark.asyncio
async def test_get_settings_keeps_raw_prompt_values() -> None:
    old_rule = settings.rule_detection_system_prompt
    old_profile = settings.user_profile_system_prompt
    old_admin = settings.admin_agent_system_prompt
    settings.rule_detection_system_prompt = None
    settings.user_profile_system_prompt = ""
    settings.admin_agent_system_prompt = None

    try:
        ops = ChatGuardianOperations(container=_DummyContainer(), env_only_keys=[])
        current = await ops.get_settings()

        assert current.rule_detection_system_prompt is None
        assert current.user_profile_system_prompt == ""
        assert current.admin_agent_system_prompt is None
    finally:
        settings.rule_detection_system_prompt = old_rule
        settings.user_profile_system_prompt = old_profile
        settings.admin_agent_system_prompt = old_admin


def test_get_default_prompts_contains_three_templates() -> None:
    ops = ChatGuardianOperations(container=_DummyContainer(), env_only_keys=[])
    defaults = ops.get_default_prompts()

    assert set(defaults.keys()) == {
        "rule_detection_system_prompt",
        "user_profile_system_prompt",
        "admin_agent_system_prompt",
    }
    assert all(isinstance(value, str) and value.strip() for value in defaults.values())


def test_get_default_notification_template_contains_template() -> None:
    ops = ChatGuardianOperations(container=_DummyContainer(), env_only_keys=[])
    defaults = ops.get_default_notification_template()

    assert set(defaults.keys()) == {"notification_text_template"}
    assert isinstance(defaults["notification_text_template"], str)
    assert "{rule_id}" in defaults["notification_text_template"]


@pytest.mark.asyncio
async def test_update_mcp_auth_key_does_not_restart_http_server() -> None:
    previous = {
        "mcp_http_enabled": settings.mcp_http_enabled,
        "mcp_http_transport": settings.mcp_http_transport,
        "mcp_http_host": settings.mcp_http_host,
        "mcp_http_port": settings.mcp_http_port,
        "mcp_http_path": settings.mcp_http_path,
        "mcp_http_auth_key": settings.mcp_http_auth_key,
    }
    settings.mcp_http_enabled = True
    settings.mcp_http_transport = "streamable-http"
    settings.mcp_http_host = "127.0.0.1"
    settings.mcp_http_port = 18080
    settings.mcp_http_path = "/mcp"
    settings.mcp_http_auth_key = "old-key"

    runtime_mcp = _DummyMCPRuntimeService()
    container = SimpleNamespace(
        settings_repository=_DummySettingsRepository(),
        mcp_service=runtime_mcp,
        adapter_manager=_DummyAdapterManager(),
    )
    ops = ChatGuardianOperations(container=container, env_only_keys=[])

    try:
        result = await ops.update_settings(
            {
                "mcp_http_enabled": True,
                "mcp_http_transport": "streamable-http",
                "mcp_http_host": "127.0.0.1",
                "mcp_http_port": 18080,
                "mcp_http_path": "/mcp",
                "mcp_http_auth_key": "new-key",
            }
        )
        assert result["status"] == "saved"
        assert settings.mcp_http_auth_key == "new-key"
        assert runtime_mcp.stop_calls == 0
        assert runtime_mcp.start_calls == 0
    finally:
        settings.mcp_http_enabled = previous["mcp_http_enabled"]
        settings.mcp_http_transport = previous["mcp_http_transport"]
        settings.mcp_http_host = previous["mcp_http_host"]
        settings.mcp_http_port = previous["mcp_http_port"]
        settings.mcp_http_path = previous["mcp_http_path"]
        settings.mcp_http_auth_key = previous["mcp_http_auth_key"]
