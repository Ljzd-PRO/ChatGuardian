from __future__ import annotations

from typing import Protocol

from chat_guardian.domain import DetectionRule


class RuleGenerationBackend(Protocol):
    """规则生成后端抽象：将一句话或文本转换为 DetectionRule。"""

    async def generate(self, utterance: str, override_system_prompt: str | None = None) -> DetectionRule: ...
