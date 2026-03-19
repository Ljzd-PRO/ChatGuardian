from __future__ import annotations

from typing import Protocol

from chat_guardian.domain import ChatEvent, ChatMessage, RuleDecision

DEFAULT_NOTIFICATION_TEMPLATE = (
    "Rule: {rule_id}\n"
    "Chat: {chat_id}\n"
    "Message ID: {message_id}\n"
    "Confidence: {confidence:.2f}\n"
    "Reason: {reason}\n"
    "Params: {params_text}"
)


def format_notification_text(event: ChatEvent, decision: RuleDecision) -> str:
    """构造通知文本。若 settings.notification_text_template 已配置则使用自定义模板，
    支持 Python .format() 插值，可用变量：
    {rule_id}, {chat_id}, {message_id}, {confidence}, {reason}, {params_text}
    """
    from chat_guardian.settings import settings  # 局部导入避免循环引用

    params = decision.extracted_params or {}
    if params:
        params_text = "; ".join(f"{key}={value}" for key, value in params.items())
    else:
        params_text = "-"

    template = settings.notification_text_template or DEFAULT_NOTIFICATION_TEMPLATE

    try:
        return template.format(
            chat_type=event.chat_type,
            chat_id=event.chat_id,
            platform=event.platform,
            message=str(event.message),
            message_id=event.message.message_id,
            rule_id=decision.rule_id,
            confidence=decision.confidence,
            reason=decision.reason or "",
            extracted_params=decision.extracted_params or {},
            params_text=params_text,
        )
    except (KeyError, ValueError, IndexError):
        # 模板格式错误时回退到默认模板
        return DEFAULT_NOTIFICATION_TEMPLATE.format(
            chat_type=event.chat_type,
            chat_id=event.chat_id,
            platform=event.platform,
            message=str(event.message),
            message_id=event.message.message_id,
            rule_id=decision.rule_id,
            confidence=decision.confidence,
            reason=decision.reason or "",
            extracted_params=decision.extracted_params or {},
            params_text=params_text,
        )


def get_default_notification_template() -> str:
    """Return built-in default notification text template."""
    return DEFAULT_NOTIFICATION_TEMPLATE


class Notifier(Protocol):
    """通知器协议，表示一种能够发送通知（邮件/短信/第三方 API 等）的实现。"""

    async def notify(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> bool: ...

    async def test(self) -> bool:
        """发送测试通知，验证该通知器是否可用。返回 True 表示成功，False 表示失败。"""
        ...
