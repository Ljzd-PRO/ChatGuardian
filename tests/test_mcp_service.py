import pytest

from chat_guardian.mcp import ChatGuardianMCPService, ChatGuardianOperations
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context


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
