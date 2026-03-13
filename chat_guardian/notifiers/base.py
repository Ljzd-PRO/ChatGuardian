from __future__ import annotations

from typing import Protocol

from chat_guardian.domain import ChatEvent, ChatMessage, RuleDecision


class Notifier(Protocol):
    """通知器协议，表示一种能够发送通知（邮件/短信/第三方 API 等）的实现。"""

    async def notify(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> bool: ...

    async def test(self) -> bool:
        """发送测试通知，验证该通知器是否可用。返回 True 表示成功，False 表示失败。"""
        ...
