from __future__ import annotations

import re

from loguru import logger

from chat_guardian.domain import DetectionRule, RuleParameterSpec
from chat_guardian.rule_authoring.base import RuleGenerationBackend
from chat_guardian.rule_authoring.utils import build_rule_matcher


class InternalRuleGenerationBackend(RuleGenerationBackend):
    """简单的内置规则生成器。"""

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule:
        logger.debug(f"🔧 内部规则生成器处理 | 文本长度={len(utterance)}")

        topics = self._extract_topics(utterance)
        logger.debug(f"  ✓ 提取主题 | 数量={len(topics)} | {topics[:3]}")

        users = self._extract_users(utterance)
        logger.debug(f"  ✓ 提取用户 | 数量={len(users)} | {users}")

        chat_id = self._extract_chat_id(utterance)
        logger.debug(f"  ✓ 提取会话 | chat_id={chat_id}")

        parameters = [RuleParameterSpec(key="label", description="LLM extracted label", required=False)]
        rule_id = f"rule-{abs(hash((utterance, override_system_prompt))) % 1000000}"
        rule_name = (utterance[:24] + "...") if len(utterance) > 24 else utterance

        matcher = build_rule_matcher(chat_id, users)

        rule = DetectionRule(
            rule_id=rule_id,
            name=rule_name,
            description=utterance,
            matcher=matcher,
            topic_hints=topics,
            score_threshold=0.6,
            enabled=True,
            parameters=parameters,
        )
        logger.success(f"✅ 内部规则已生成 | rule_id={rule_id}")
        return rule

    @staticmethod
    def _extract_topics(utterance: str) -> list[str]:
        terms = [term for term in re.split(r"[，,。\s]+", utterance) if term]
        filtered = [term for term in terms if len(term) >= 2 and not term.startswith("@")]
        return filtered[:6]

    @staticmethod
    def _extract_users(utterance: str) -> list[str]:
        return [item[1:] for item in re.findall(r"@[^\s，,。]+", utterance)]

    @staticmethod
    def _extract_chat_id(utterance: str) -> str | None:
        patterns = [r"(?:群|私聊|会话)([^，,。]+)", r"在([^，,。]+)里", r"([^，,。]+)中"]
        for pattern in patterns:
            match = re.search(pattern, utterance)
            if match:
                return match.group(1).strip()
        return None
