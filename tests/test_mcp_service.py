import pytest
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
