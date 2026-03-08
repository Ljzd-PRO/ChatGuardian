"""
API 层请求与响应的 Pydantic 模型定义。

这些模型用于 FastAPI 路由的输入/输出验证与序列化。
"""

from __future__ import annotations

from typing import Any
from datetime import datetime

from pydantic import BaseModel


class DetectRequest(BaseModel):
    """
    /detect 路由的请求模型。

    Attributes:
        platform: 消息平台。
        chat_type: 聊天类型。
        is_from_self: 是否为自身消息。
        message: 消息负载。
    """

    platform: str
    chat_type: str
    is_from_self: bool = False
    message: dict[str, Any]


class DetectResponse(BaseModel):
    """
    /detect 路由的响应模型。

    Attributes:
        event_id: 检测事件 ID。
        triggered_rule_ids: 被触发的规则 ID 列表。
        notified_count: 通知数量。
    """

    event_id: str
    triggered_rule_ids: list[str]
    notified_count: int


class RuleGenerateRequest(BaseModel):
    """
    一句话生成规则的请求负载。

    Attributes:
        utterance: 用户的一句话描述。
        use_external: 是否调用外部生成后端。
        override_system_prompt: 可选系统提示词覆盖。
    """

    utterance: str
    use_external: bool = False
    override_system_prompt: str | None = None


class SuggestResponse(BaseModel):
    """
    建议返回模型，包含若干建议文本。

    Attributes:
        suggestions: 建议文本列表。
    """

    suggestions: list[str]


class AuthRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    expires_at: datetime
    username: str


class AuthStatusResponse(BaseModel):
    setup_required: bool
    authenticated: bool
    username: str | None = None
    using_default_credentials: bool = False
