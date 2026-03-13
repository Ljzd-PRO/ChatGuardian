from __future__ import annotations

import json
from dataclasses import dataclass

from aiosmtplib import SMTP
from loguru import logger

from chat_guardian.domain import ChatEvent, ChatMessage, RuleDecision
from chat_guardian.notifiers.base import Notifier
from chat_guardian.settings import settings


@dataclass(slots=True)
class NotificationConfig:
    """通知配置（目前仅包含邮件接收方）。"""

    to_email: str | None


class EmailNotifier(Notifier):
    """基于 SMTP 的邮件通知实现。"""

    def __init__(self, config: NotificationConfig):
        self.config = config

    async def test(self) -> bool:
        """发送测试邮件，验证邮件通知器配置是否正确。"""
        if not self.config.to_email or not settings.smtp_host or not settings.smtp_sender:
            logger.warning(
                f"⚠️ 邮件通知测试失败：配置不完整 | to_email={bool(self.config.to_email)} "
                f"| smtp_host={bool(settings.smtp_host)}")
            return False

        subject = "[ChatGuardian] Test Notification"
        body = "This is a test notification from ChatGuardian. If you received this email, your email notification settings are configured correctly."

        try:
            smtp = SMTP(hostname=settings.smtp_host, port=settings.smtp_port, use_tls=False)
            await smtp.connect()
            logger.debug("  ✓ SMTP 测试连接成功")

            if settings.smtp_username and settings.smtp_password:
                await smtp.login(settings.smtp_username, settings.smtp_password)
                logger.debug("  ✓ SMTP 测试认证成功")

            await smtp.sendmail(
                settings.smtp_sender,
                [self.config.to_email],
                (
                    f"From: {settings.smtp_sender}\r\n"
                    f"To: {self.config.to_email}\r\n"
                    f"Subject: {subject}\r\n\r\n"
                    f"{body}"
                ),
            )
            await smtp.quit()
            logger.success(f"✅ 测试邮件已发送 | 收件人={self.config.to_email}")
            return True
        except Exception as e:
            logger.error(f"❌ 测试邮件发送失败: {e}")
            return False

    async def notify(self, event: ChatEvent, decision: RuleDecision, _context_messages: list[ChatMessage]) -> bool:
        """发送邮件通知。

        在未配置 SMTP 或接收邮箱时，返回 False 表示未发送。
        """
        if not self.config.to_email or not settings.smtp_host or not settings.smtp_sender:
            logger.warning(
                f"⚠️ 邮件通知未配置 | to_email={bool(self.config.to_email)} | smtp_host={bool(settings.smtp_host)}")
            return False

        logger.debug(f"📧 准备发送邮件通知 | 收件人={self.config.to_email} | 规则={decision.rule_id}")

        subject = f"[ChatGuardian] Rule Triggered: {decision.rule_id}"
        content = {
            "chat_id": event.chat_id,
            "message_id": event.message.message_id,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "params": decision.extracted_params,
        }
        body = json.dumps(content, ensure_ascii=False, indent=2)

        try:
            smtp = SMTP(hostname=settings.smtp_host, port=settings.smtp_port, use_tls=False)
            await smtp.connect()
            logger.debug(f"  ✓ SMTP 连接成功")

            if settings.smtp_username and settings.smtp_password:
                await smtp.login(settings.smtp_username, settings.smtp_password)
                logger.debug(f"  ✓ SMTP 认证成功")

            await smtp.sendmail(
                settings.smtp_sender,
                [self.config.to_email],
                (
                    f"From: {settings.smtp_sender}\r\n"
                    f"To: {self.config.to_email}\r\n"
                    f"Subject: {subject}\r\n\r\n"
                    f"{body}"
                ),
            )
            await smtp.quit()
            logger.success(f"✅ 邮件已发送 | 收件人={self.config.to_email} | 规则={decision.rule_id}")
            return True
        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")
            return False


def build_email_notifier_from_settings() -> EmailNotifier | None:
    if not settings.email_notifier_enabled:
        return None

    if not settings.email_notifier_to_email:
        logger.warning("⚠️ Email 通知器已启用但未配置收件人，跳过注册")
        return None

    return EmailNotifier(NotificationConfig(to_email=settings.email_notifier_to_email))
