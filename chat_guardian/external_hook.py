from __future__ import annotations

import asyncio
import base64

import httpx
from loguru import logger

from chat_guardian.domain import ChatEvent, ChatMessage, RuleDecision
from chat_guardian.settings import settings


class ExternalHookDispatcher:
    """外部 Hook 派发器。"""

    def __init__(self, hook_endpoints: list[str]):
        self.hook_endpoints = hook_endpoints

    async def dispatch(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> None:
        if not self.hook_endpoints:
            logger.debug("ℹ️ 无外部 Hook 端点配置，跳过派发")
            return

        logger.debug(f"🔗 准备派发 Hook | 规则={decision.rule_id} | 端点数={len(self.hook_endpoints)}")

        payload = {
            "chat_id": event.chat_id,
            "message_id": event.message.message_id,
            "rule_id": decision.rule_id,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "parameters": decision.extracted_params,
            "context": [
                {
                    "message_id": message.message_id,
                    "sender_id": message.sender_id,
                    "text": str(message),
                    "contents": [
                        {
                            "type": item.type.value,
                            "text": item.text,
                            "image_data_base64": (
                                base64.b64encode(item.image_data).decode("ascii")
                                if item.image_data
                                else None
                            ),
                            "mention_user_id": item.mention_user.user_id if item.mention_user else None,
                        }
                        for item in message.contents
                    ],
                    "timestamp": message.timestamp.isoformat(),
                }
                for message in context_messages
            ],
        }

        async def send_to_endpoint(endpoint: str) -> str | Exception:
            try:
                async with httpx.AsyncClient(timeout=settings.hook_timeout_seconds) as client:
                    response = await client.post(endpoint, json=payload)
                    logger.debug(f"  ✓ Hook 已派发 | endpoint={endpoint} | status={response.status_code}")
                    return endpoint
            except Exception as e:
                logger.warning(f"  ⚠️ Hook 派发失败 | endpoint={endpoint} | 错误={e}")
                return e

        results = await asyncio.gather(*(send_to_endpoint(ep) for ep in self.hook_endpoints), return_exceptions=True)
        success_count = sum(1 for r in results if isinstance(r, str))
        logger.info(f"✅ Hook 派发完成 | 成功={success_count}/{len(self.hook_endpoints)}")
