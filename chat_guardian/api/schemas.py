"""
API 层请求与响应的 Pydantic 模型定义。

这些模型用于 FastAPI 路由的输入/输出验证与序列化。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DetectRequest(BaseModel):
    """
    /detect 路由的请求模型。

    Attributes:
        platform: 消息平台。
        chat_type: 聊天类型。
        message: 消息负载。
    """

    platform: str
    chat_type: str
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


class LoginRequest(BaseModel):
    """登录请求模型。"""

    username: str
    password: str


class RegisterRequest(BaseModel):
    """管理员注册请求模型。"""

    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求模型。"""

    username: str
    old_password: str
    new_password: str
    new_username: str | None = None
