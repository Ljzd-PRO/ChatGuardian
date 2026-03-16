from __future__ import annotations

from typing import Protocol

from chat_guardian.domain import ChatEvent, ChatMessage, RuleDecision


def format_notification_text(event: ChatEvent, decision: RuleDecision) -> str:
    """构造简短清晰的人类可读通知文本（纯文本、非 JSON、非 Markdown）。"""
    params = decision.extracted_params or {}
    if params:
        params_text = "; ".join(f"{key}={value}" for key, value in params.items())
    else:
        params_text = "无"

    return "\n".join(
        [
            f"规则: {decision.rule_id}",
            f"会话: {event.chat_id}",
            f"消息ID: {event.message.message_id}",
            f"置信度: {decision.confidence:.2f}",
            f"原因: {decision.reason}",
            f"参数: {params_text}",
        ]
    )


class Notifier(Protocol):
    """通知器协议，表示一种能够发送通知（邮件/短信/第三方 API 等）的实现。"""

    async def notify(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> bool: ...

    async def test(self) -> bool:
        """发送测试通知，验证该通知器是否可用。返回 True 表示成功，False 表示失败。"""
        ...
