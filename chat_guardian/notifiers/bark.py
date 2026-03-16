from __future__ import annotations
from dataclasses import dataclass, field

import httpx
from loguru import logger

from chat_guardian.domain import ChatEvent, ChatMessage, RuleDecision
from chat_guardian.notifiers.base import Notifier, format_notification_text
from chat_guardian.settings import settings


@dataclass(slots=True)
class BarkNotificationConfig:
    device_key: str | None
    device_keys: list[str] = field(default_factory=list)
    server_url: str = "https://api.day.app"
    group: str | None = None
    level: str | None = None
    title_prefix: str = "[ChatGuardian]"


def _normalize_device_keys(device_key: str | None, device_keys: list[str]) -> list[str]:
    keys: list[str] = []
    if device_key and device_key.strip():
        keys.append(device_key.strip())
    keys.extend(key.strip() for key in device_keys if key and key.strip())
    return list(dict.fromkeys(keys))


class BarkNotifier(Notifier):
    """基于 Bark HTTP API 的通知实现。"""

    def __init__(self, config: BarkNotificationConfig):
        self.config = config

    async def test(self) -> bool:
        """发送测试 Bark 推送，验证 Bark 通知器配置是否正确。"""
        keys = _normalize_device_keys(self.config.device_key, self.config.device_keys)

        if not keys:
            logger.warning("⚠️ Bark 通知测试失败：未配置 device_key/device_keys")
            return False

        endpoint = f"{self.config.server_url.rstrip('/')}/push"
        payload: dict[str, object] = {
            "title": "[ChatGuardian] Test Notification",
            "body": "This is a test notification from ChatGuardian. If you received this, your Bark notification settings are configured correctly.",
        }
        if len(keys) == 1:
            payload["device_key"] = keys[0]
        else:
            payload["device_keys"] = keys

        if self.config.group:
            payload["group"] = self.config.group

        logger.debug(f"📲 准备发送 Bark 测试通知 | endpoint={endpoint}")
        try:
            async with httpx.AsyncClient(timeout=settings.hook_timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)

            if response.status_code != 200:
                logger.error(f"❌ Bark 测试推送失败 | status={response.status_code} | body={response.text}")
                return False

            try:
                body = response.json()
            except ValueError:
                body = {}

            code = body.get("code") if isinstance(body, dict) else None
            if code not in (None, 200):
                logger.error(f"❌ Bark 测试推送返回异常 | code={code} | body={body}")
                return False

            logger.success("✅ Bark 测试推送成功")
            return True
        except httpx.HTTPError as e:
            logger.error(f"❌ Bark 测试推送异常: {e}")
            return False

    async def notify(self, event: ChatEvent, decision: RuleDecision, _context_messages: list[ChatMessage]) -> bool:
        keys = _normalize_device_keys(self.config.device_key, self.config.device_keys)

        if not keys:
            logger.warning("⚠️ Bark 通知未配置 device_key/device_keys")
            return False

        endpoint = f"{self.config.server_url.rstrip('/')}/push"
        payload: dict[str, object] = {
            "title": f"{self.config.title_prefix} Rule Triggered: {decision.rule_id}",
            "body": format_notification_text(event, decision),
        }
        if len(keys) == 1:
            payload["device_key"] = keys[0]
        else:
            payload["device_keys"] = keys

        if self.config.group:
            payload["group"] = self.config.group
        if self.config.level:
            payload["level"] = self.config.level

        logger.debug(f"📲 准备发送 Bark 通知 | endpoint={endpoint} | 规则={decision.rule_id}")
        try:
            async with httpx.AsyncClient(timeout=settings.hook_timeout_seconds) as client:
                response = await client.post(endpoint, json=payload)

            if response.status_code != 200:
                logger.error(f"❌ Bark 推送失败 | status={response.status_code} | body={response.text}")
                return False

            try:
                body = response.json()
            except ValueError:
                body = {}

            code = body.get("code") if isinstance(body, dict) else None
            if code not in (None, 200):
                logger.error(f"❌ Bark 推送返回异常 | code={code} | body={body}")
                return False

            logger.success(f"✅ Bark 推送成功 | 规则={decision.rule_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"❌ Bark 推送异常: {e}")
            return False


def build_bark_notifier_from_settings() -> BarkNotifier | None:
    if not settings.bark_notifier_enabled:
        return None

    keys = _normalize_device_keys(settings.bark_device_key, settings.bark_device_keys)

    if not keys:
        logger.warning("⚠️ Bark 通知器已启用但未配置 key，跳过注册")
        return None

    return BarkNotifier(
        BarkNotificationConfig(
            device_key=keys[0] if len(keys) == 1 else None,
            device_keys=keys if len(keys) > 1 else [],
            server_url=settings.bark_server_url,
            group=settings.bark_group,
            level=settings.bark_level,
        )
    )
