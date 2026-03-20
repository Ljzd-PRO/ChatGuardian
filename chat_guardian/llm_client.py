from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from loguru import logger

from chat_guardian.domain import ChatEvent, ChatMessage, DetectionRule, RuleDecision
from chat_guardian.models import DiagnosticsModel
from chat_guardian.prompts import (
    RULE_DETECTION_SYSTEM_PROMPT,
    USER_PROFILE_SYSTEM_PROMPT,
    resolve_prompt,
)
from chat_guardian.service_utils import (
    build_image_content_blocks,
    build_rule_detection_content_blocks,
    extract_json_payload,
    messages_to_markdown,
)
from chat_guardian.settings import settings


class LangChainLLMClient:
    """基于 LangChain 的 LLM 客户端实现。"""

    def __init__(
        self,
        chat_model: BaseChatModel,
        backend: str,
        model_name: str,
        api_base: str | None,
        api_key_configured: bool,
    ):
        self.model = chat_model
        self.backend = backend
        self.model_name = model_name
        self.api_base = api_base
        self.api_key_configured = api_key_configured
        logger.info(
            f"🤖 LLM 客户端已初始化 | backend={backend} | model={model_name} | api_key_configured={api_key_configured}"
        )

    async def evaluate(self, messages: list[ChatMessage], rules: list[DetectionRule]) -> Optional[list[RuleDecision]]:
        if not rules:
            logger.debug("📋 规则列表为空，返回空决策")
            return []

        logger.debug(f"🔍 LLM 评估开始 | 消息数={len(messages)} | 规则数={len(rules)}")
        rules_payload = [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "topic_hints": rule.topic_hints,
                "score_threshold": rule.score_threshold,
                "parameters": [
                    {
                        "key": parameter.key,
                        "description": parameter.description,
                        "required": parameter.required,
                    }
                    for parameter in rule.parameters
                ],
            }
            for rule in rules
        ]
        content_blocks, text_payload, image_block_count = await build_rule_detection_content_blocks(
            messages,
            rules_payload,
        )

        try:
            detection_system_prompt = resolve_prompt(
                settings.rule_detection_system_prompt,
                RULE_DETECTION_SYSTEM_PROMPT,
            )
            response = await self.model.ainvoke(
                [
                    SystemMessage(content=detection_system_prompt),
                    HumanMessage(content=content_blocks),
                ]
            )
            logger.debug(f"💬 LLM 输入 | 文本长度={len(text_payload)} | 图片块数={image_block_count}")
            content = self._response_text(response.content)
            parsed = extract_json_payload(content)
            decisions = self._parse_decisions(parsed, rules)
            triggered_count = sum(1 for d in decisions if d.triggered)
            logger.info(f"✅ LLM 评估完成 | 触发规则数={triggered_count} | 总规则数={len(rules)}")
            logger.debug(f"✅ 评估结果 | {decisions}")
            return decisions
        except Exception as e:
            logger.error(f"❌ LLM 评估异常: {e}")
            return [
                RuleDecision(
                    rule_id=rule.rule_id,
                    triggered=False,
                    confidence=0.0,
                    reason=f"LLM evaluate failed: {e}",
                    extracted_params={},
                )
                for rule in rules
            ]

    async def extract_self_participation(
        self,
        event: ChatEvent,
        context: list[ChatMessage],
        existing_topics: list[dict[str, Any]] | None = None,
    ) -> dict | None:
        if existing_topics is None:
            existing_topics = []
        logger.debug(
            f"💬 开始提取用户 {event.message.sender_id} 的参与画像 | "
            f"上下文消息数={len(context)} | 已有话题数={len(existing_topics)}"
        )
        context_markdown = messages_to_markdown(context)
        topic_lines: list[str] = []
        for topic in existing_topics:
            if not isinstance(topic, dict):
                continue
            name = str(topic.get("name", "")).strip()
            if not name:
                continue
            keywords = [str(k).strip() for k in topic.get("keywords", []) if str(k).strip()]
            if keywords:
                topic_lines.append("- {name}（关键词：{keywords}）".format(
                    name=name,
                    keywords="、".join(keywords),
                ))
            else:
                topic_lines.append("- {name}".format(name=name))

        existing_topics_markdown = "\n".join(topic_lines) if topic_lines else "- （无）"
        payload = """
## 目标用户
- 用户ID: {sender_id}
- 名称: {sender_name}
- 消息： {message}

## 上下文消息
{context_markdown}

## 已有话题
{existing_topics_markdown}
""".format(
            sender_id=event.message.sender_id,
            sender_name=event.message.sender_name or "",
            message=str(event.message),
            context_markdown=context_markdown or "- （无）",
            existing_topics_markdown=existing_topics_markdown,
        )
        image_blocks, image_block_count = await build_image_content_blocks(context)
        content_blocks: list[dict[str, Any]] = [{"type": "text", "text": payload}, *image_blocks]
        try:
            profile_system_prompt = resolve_prompt(
                settings.user_profile_system_prompt,
                USER_PROFILE_SYSTEM_PROMPT,
            )
            response = await self.model.ainvoke(
                [
                    SystemMessage(content=profile_system_prompt),
                    HumanMessage(content=content_blocks),
                ]
            )
            logger.debug(f"💬 用户画像 LLM 输入 | 文本长度={len(payload)} | 图片块数={image_block_count}")
            content = self._response_text(response.content)
            parsed = extract_json_payload(content)

            topics = parsed.get("topics", [])
            interactions = parsed.get("interactions", [])
            if not isinstance(topics, list):
                topics = []
            if not isinstance(interactions, list):
                interactions = []

            logger.info(f"✅ 参与画像提取完成 | 话题数={len(topics)} | 互动数={len(interactions)}")
            return {
                "topics": topics,
                "interactions": interactions,
            }
        except Exception as e:
            logger.error(f"❌ 参与画像提取异常: {e}")
            return None

    @staticmethod
    def _response_text(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            return "\n".join(text_parts)
        return str(content)

    @staticmethod
    def _parse_decisions(payload: dict, rules: list[DetectionRule]) -> list[RuleDecision]:
        raw_decisions = payload.get("decisions", [])
        indexed: dict[str, RuleDecision] = {}
        if isinstance(raw_decisions, list):
            for item in raw_decisions:
                if not isinstance(item, dict):
                    continue
                rule_id = str(item.get("rule_id", "")).strip()
                if not rule_id:
                    continue
                triggered = bool(item.get("triggered", False))
                try:
                    confidence = float(item.get("confidence", 0.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                confidence = min(1.0, max(0.0, confidence))
                reason = str(item.get("reason", "LLM response"))
                raw_params = item.get("extracted_params", {})
                extracted_params = raw_params if isinstance(raw_params, dict) else {}
                indexed[rule_id] = RuleDecision(
                    rule_id=rule_id,
                    triggered=triggered,
                    confidence=confidence,
                    reason=reason,
                    extracted_params={str(key): str(value) for key, value in extracted_params.items()},
                )

        decisions: list[RuleDecision] = []
        for rule in rules:
            decisions.append(
                indexed.get(
                    rule.rule_id,
                    RuleDecision(
                        rule_id=rule.rule_id,
                        triggered=False,
                        confidence=0.0,
                        reason="LLM response missing this rule",
                        extracted_params={},
                    ),
                )
            )
        return decisions

    def diagnostics(self) -> DiagnosticsModel:
        return DiagnosticsModel(
            backend=self.backend,
            model=self.model_name,
            client_class=self.model.__class__.__name__,
            api_base=self.api_base,
            api_key_configured=self.api_key_configured,
        )

    async def ping(self) -> tuple[bool, str | None, float]:
        logger.debug("🔔 LLM ping 开始...")
        start = datetime.now(timezone.utc)
        try:
            await asyncio.wait_for(self.model.ainvoke([HumanMessage(content="ping")]), timeout=2.0)
            elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            logger.success(f"✅ LLM ping 成功 | 延迟={elapsed_ms:.2f}ms")
            return True, None, elapsed_ms
        except Exception as exc:
            elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            logger.warning(f"⚠️ LLM ping 失败: {exc} | 延迟={elapsed_ms:.2f}ms")
            return False, str(exc), elapsed_ms


def build_llm_client() -> LangChainLLMClient:
    backend = settings.llm_langchain_backend.strip().lower()
    logger.info(f"🔧 正在构建 LLM 客户端 | backend={backend}")

    if backend == "openai_compatible":
        api_key = settings.llm_langchain_api_key or "chat-guardian-dev-placeholder-key"
        logger.info(f"  📡 OpenAI 兼容后端 | endpoint={settings.llm_langchain_api_base}")
        chat_model = ChatOpenAI(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            timeout=settings.llm_timeout_seconds,
            base_url=settings.llm_langchain_api_base,
            api_key=api_key,
        )
        logger.success(f"✅ OpenAI LLM 客户端已创建 | model={settings.llm_langchain_model}")
        return LangChainLLMClient(
            chat_model=chat_model,
            backend="openai_compatible",
            model_name=settings.llm_langchain_model,
            api_base=settings.llm_langchain_api_base,
            api_key_configured=bool(settings.llm_langchain_api_key),
        )

    if backend == "ollama":
        ollama_base = settings.llm_langchain_api_base or "http://localhost:11434"
        logger.info(f"  🦙 Ollama 后端 | base_url={ollama_base}")
        chat_model = ChatOllama(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            base_url=ollama_base,
        )
        logger.success(f"✅ Ollama LLM 客户端已创建 | model={settings.llm_langchain_model}")
        return LangChainLLMClient(
            chat_model=chat_model,
            backend="ollama",
            model_name=settings.llm_langchain_model,
            api_base=ollama_base,
            api_key_configured=False,
        )

    if backend == "gemini":
        api_key = settings.llm_langchain_api_key
        logger.info(f"  🌐 Google Gemini 后端 | model={settings.llm_langchain_model}")
        chat_model = ChatGoogleGenerativeAI(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            timeout=settings.llm_timeout_seconds,
            google_api_key=api_key,
        )
        logger.success(f"✅ Google Gemini LLM 客户端已创建 | model={settings.llm_langchain_model}")
        return LangChainLLMClient(
            chat_model=chat_model,
            backend="gemini",
            model_name=settings.llm_langchain_model,
            api_base=None,
            api_key_configured=bool(api_key),
        )

    if backend == "anthropic":
        api_key = settings.llm_langchain_api_key
        logger.info(f"  🔵 Anthropic 后端 | model={settings.llm_langchain_model}")
        chat_model = ChatAnthropic(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            timeout=settings.llm_timeout_seconds,
            api_key=api_key,
        )
        logger.success(f"✅ Anthropic LLM 客户端已创建 | model={settings.llm_langchain_model}")
        return LangChainLLMClient(
            chat_model=chat_model,
            backend="anthropic",
            model_name=settings.llm_langchain_model,
            api_base=None,
            api_key_configured=bool(api_key),
        )

    if backend == "openrouter":
        api_key = settings.llm_langchain_api_key or ""
        openrouter_base = "https://openrouter.ai/api/v1"
        logger.info(f"  🔀 OpenRouter 后端 | model={settings.llm_langchain_model}")
        chat_model = ChatOpenAI(
            model=settings.llm_langchain_model,
            temperature=settings.llm_langchain_temperature,
            timeout=settings.llm_timeout_seconds,
            base_url=openrouter_base,
            api_key=api_key,
        )
        logger.success(f"✅ OpenRouter LLM 客户端已创建 | model={settings.llm_langchain_model}")
        return LangChainLLMClient(
            chat_model=chat_model,
            backend="openrouter",
            model_name=settings.llm_langchain_model,
            api_base=openrouter_base,
            api_key_configured=bool(settings.llm_langchain_api_key),
        )

    logger.error(f"❌ 不支持的 LLM 后端: {settings.llm_langchain_backend}")
    raise ValueError(f"Unsupported llm_langchain_backend: {settings.llm_langchain_backend}")
