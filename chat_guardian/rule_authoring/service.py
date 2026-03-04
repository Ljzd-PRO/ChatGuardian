from __future__ import annotations

from loguru import logger

from chat_guardian.domain import DetectionRule
from chat_guardian.rule_authoring.base import RuleGenerationBackend


class RuleAuthoringService:
    def __init__(self, internal_backend: RuleGenerationBackend, external_backend: RuleGenerationBackend | None):
        self.internal_backend = internal_backend
        self.external_backend = external_backend

    async def generate_rule(
            self,
            utterance: str,
            use_external: bool,
            override_system_prompt: str | None = None,
    ) -> DetectionRule:
        logger.debug(f"📝 开始规则生成 | use_external={use_external} | 文本长度={len(utterance)}")

        if use_external:
            if self.external_backend is None:
                logger.error("❌ 外部生成后端未配置")
                raise ValueError("External generation backend is not configured")
            logger.info("🌐 使用外部后端生成规则...")
            rule = await self.external_backend.generate(utterance, override_system_prompt)
        else:
            logger.info("⚙️ 使用内部后端生成规则...")
            rule = await self.internal_backend.generate(utterance, override_system_prompt)

        logger.success(f"✅ 规则生成完成 | rule_id={rule.rule_id} | name={rule.name}")
        return rule
