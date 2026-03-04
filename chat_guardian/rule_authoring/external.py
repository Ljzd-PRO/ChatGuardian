from __future__ import annotations

import httpx
from loguru import logger

from chat_guardian.domain import DetectionRule, RuleParameterSpec
from chat_guardian.rule_authoring.base import RuleGenerationBackend
from chat_guardian.rule_authoring.utils import build_rule_matcher
from chat_guardian.settings import settings


class ExternalPromptRuleGenerationBackend(RuleGenerationBackend):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule:
        logger.debug(f"🌐 外部规则生成器: 向 {self.endpoint} 发起请求 | 文本长度={len(utterance)}")

        payload = {"utterance": utterance, "system_prompt": override_system_prompt}
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                logger.debug(f"  ✓ 外部服务响应 | status={response.status_code}")

                raw = response.json()

            parameters = [
                RuleParameterSpec(
                    key=item["key"],
                    description=item.get("description", ""),
                    required=item.get("required", True),
                )
                for item in raw.get("parameters", [])
            ]

            rule = DetectionRule(
                rule_id=raw["rule_id"],
                name=raw["name"],
                description=raw["description"],
                matcher=build_rule_matcher(
                    chat_id=(str(raw["chat_id"]).strip() if raw.get("chat_id") else None),
                    users=[str(item) for item in raw.get("participant_ids", []) if str(item).strip()],
                ),
                topic_hints=raw.get("topic_hints", []),
                score_threshold=raw.get("score_threshold", 0.6),
                enabled=raw.get("enabled", True),
                parameters=parameters,
            )
            logger.success(f"✅ 外部规则已生成 | rule_id={rule.rule_id}")
            return rule
        except Exception as e:
            logger.error(f"❌ 外部规则生成失败: {e}")
            raise
