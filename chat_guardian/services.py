"""
核心服务与基础实现。

此模块包含：
- 服务接口（Repository、LLM 客户端等）的协议定义；
- 开发阶段可用的内置实现（LangChain LLM、内存存储、外部 Hook 派发器）；
- 检测引擎、上下文窗口与记忆写入。

说明：
- 通知器实现已迁移至 `chat_guardian.notifiers`；

所有对外依赖（如真实 LLM、消息平台、持久化）均通过协议抽象，便于替换。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Coroutine, Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from loguru import logger

from chat_guardian.adapters.utils import compress_image
from chat_guardian.domain import (
    ActiveGroupStat,
    ChatEvent,
    ChatMessage,
    ChatType,
    DetectionResult,
    DetectionRule,
    FrequentContactStat,
    InterestTopicStat,
    RelatedTopicStat,
    RuleDecision,
    UserMemoryFact,
)
from chat_guardian.models import RuleBatchSchedulerDiagnosticsModel, DiagnosticsModel
from chat_guardian.models import RuleBatchSchedulerMetricsModel
from chat_guardian.notifiers import Notifier
from chat_guardian.prompts import (
    RULE_DETECTION_SYSTEM_PROMPT,
    USER_PROFILE_SYSTEM_PROMPT,
    resolve_prompt,
)
from chat_guardian.repositories import (
    ChatHistoryStore,
    DetectionResultRepository,
    MemoryRepository,
    RuleRepository,
)
from chat_guardian.settings import settings


def _extract_json_payload(raw_text: str) -> dict:
    """从模型输出文本中提取 JSON 对象。"""
    try:
        parsed = json.loads(raw_text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*}", raw_text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _resolve_llm_display_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.llm_display_timezone)
    except ZoneInfoNotFoundError:
        logger.warning(f"⚠️ 无效时区配置: {settings.llm_display_timezone}，回退为 UTC")
        return ZoneInfo("UTC")


def _format_human_timestamp(value: datetime, tz: ZoneInfo) -> str:
    normalized = value if value.tzinfo else value.replace(tzinfo=ZoneInfo("UTC"))
    localized = normalized.astimezone(tz)
    return localized.strftime("%Y-%m-%d %H:%M:%S %Z")


def _messages_to_markdown(messages: list[ChatMessage]) -> str:
    tz = _resolve_llm_display_timezone()
    lines: list[str] = []
    for message in messages:
        display_name = message.sender_name or "无名称"
        human_time = _format_human_timestamp(message.timestamp, tz)
        lines.append("- [{time}] ({name}|{sender_id}): {message}".format(
            time=human_time,
            name=display_name,
            sender_id=message.sender_id,
            message=str(message),
        ))
    return "\n".join(lines)


def _guess_image_mime_type(image_bytes: bytes) -> str:
    """根据常见文件头猜测图片 MIME，无法识别时回退为 image/jpeg。"""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes.startswith(b"BM"):
        return "image/bmp"
    return "image/jpeg"


async def _build_image_content_blocks(messages: list[ChatMessage]) -> tuple[list[dict[str, Any]], int]:
    """从消息列表中提取图片并转换为可通过 LLM 的 base64 image blocks。"""
    if not settings.enable_image_parsing:
        return [], 0

    image_blocks: list[dict[str, Any]] = []

    for message in messages:
        for item in message.contents:
            if item.type.value != "image" or not item.image_data:
                continue

            if len(image_blocks) >= settings.max_images:
                break

            image_bytes = item.image_data

            # 如果启用了图片压缩，进行压缩处理
            if settings.enable_image_compression:
                compressed_bytes = compress_image(
                    image_bytes,
                    max_width=settings.image_compression_max_width,
                    max_height=settings.image_compression_max_height,
                    quality=85,
                )
                if compressed_bytes is not None:
                    image_bytes = compressed_bytes

            encoded = base64.b64encode(image_bytes).decode("ascii")
            mime_type = _guess_image_mime_type(image_bytes)

            image_blocks.append(
                {
                    "type": "image",
                    "id": item.generate_short_id(image_bytes),
                    "base64": encoded,
                    "mime_type": mime_type,
                }
            )

        if len(image_blocks) >= settings.max_images:
            break

    return image_blocks, len(image_blocks)


async def _build_rule_detection_content_blocks(
        messages: list[ChatMessage],
        rules_payload: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str, int]:
    """构建规则检测用的多模态 HumanMessage content blocks。

    Returns:
        (content_blocks, text_payload, image_block_count)
    """
    messages_payload = _messages_to_markdown(messages)
    text_payload = """
## 聊天消息
{messages_payload}

## 规则列表
{rules_payload}
""".format(
        messages_payload=messages_payload,
        rules_payload=json.dumps(rules_payload, ensure_ascii=False, indent=4),
    )

    image_blocks, image_block_count = await _build_image_content_blocks(messages)
    content_blocks: list[dict[str, Any]] = [{"type": "text", "text": text_payload}, *image_blocks]

    return content_blocks, text_payload, image_block_count


class LangChainLLMClient:
    """基于 LangChain 的 LLM 客户端实现。

    说明：
    - 底层使用 `langchain_openai.ChatOpenAI`（兼容 OpenAI API 及同协议网关）；
    - 通过 JSON 协议返回规则判断与记忆提取结果；
    - 当模型输出异常时，回退为安全默认值（不触发）。
    """

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
            f"🤖 LLM 客户端已初始化 | backend={backend} | model={model_name} | api_key_configured={api_key_configured}")

    async def evaluate(self, messages: list[ChatMessage], rules: list[DetectionRule]) -> Optional[list[RuleDecision]]:
        if not rules:
            logger.debug(f"📋 规则列表为空，返回空决策")
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
        content_blocks, text_payload, image_block_count = await _build_rule_detection_content_blocks(
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
                    SystemMessage(
                        content=detection_system_prompt,
                    ),
                    HumanMessage(content=content_blocks),
                ]
            )
            logger.debug(f"💬 LLM 输入 | 文本长度={len(text_payload)} | 图片块数={image_block_count}")
            content = self._response_text(response.content)
            parsed = _extract_json_payload(content)
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
        """从目标用户发言及上下文中提取参与画像数据。

        Args:
            event: 触发检测的消息事件（来自目标用户自身）。
            context: 构建好的上下文消息列表。
            existing_topics: 用户画像中已有话题及关键词列表，用于去重。

        Returns:
            包含 topics、interactions 的原始字典；失败时返回 None。
        """
        if existing_topics is None:
            existing_topics = []
        logger.debug(
            f"💬 开始提取用户 {event.message.sender_id} 的参与画像 | "
            f"上下文消息数={len(context)} | 已有话题数={len(existing_topics)}"
        )
        context_markdown = _messages_to_markdown(context)
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
        image_blocks, image_block_count = await _build_image_content_blocks(context)
        content_blocks: list[dict[str, Any]] = [{"type": "text", "text": payload}, *image_blocks]
        try:
            profile_system_prompt = resolve_prompt(
                settings.user_profile_system_prompt,
                USER_PROFILE_SYSTEM_PROMPT,
            )
            response = await self.model.ainvoke(
                [
                    SystemMessage(
                        content=profile_system_prompt,
                    ),
                    HumanMessage(content=content_blocks),
                ]
            )
            logger.debug(f"💬 用户画像 LLM 输入 | 文本长度={len(payload)} | 图片块数={image_block_count}")
            content = self._response_text(response.content)
            parsed = _extract_json_payload(content)

            topics = parsed.get("topics", [])
            interactions = parsed.get("interactions", [])
            if not isinstance(topics, list):
                topics = []
            if not isinstance(interactions, list):
                interactions = []

            logger.info(
                f"✅ 参与画像提取完成 | 话题数={len(topics)} | 互动数={len(interactions)}"
            )
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

    def diagnostics(self) -> "DiagnosticsModel":
        """返回当前 LLM 运行时诊断信息。"""
        return DiagnosticsModel(
            backend=self.backend,
            model=self.model_name,
            client_class=self.model.__class__.__name__,
            api_base=self.api_base,
            api_key_configured=self.api_key_configured,
        )

    async def ping(self) -> tuple[bool, str | None, float]:
        """执行最小模型调用探活。

        Returns:
            (是否成功, 失败原因, 延迟毫秒)
        """
        logger.debug(f"🔔 LLM ping 开始...")
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
    """创建 LangChain LLM 客户端实例。

    支持的后端（llm_langchain_backend）：
    - ``openai_compatible``：OpenAI API 或同协议网关，可通过 llm_langchain_api_base 指定端点；
    - ``ollama``：本地 Ollama 服务；
    - ``gemini``：Google Gemini，使用 langchain-google-genai；
    - ``anthropic``：Anthropic Claude，使用 langchain-anthropic；
    - ``openrouter``：OpenRouter（OpenAI 兼容端点 https://openrouter.ai/api/v1）。
    """
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

    elif backend == "ollama":
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

    elif backend == "gemini":
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

    elif backend == "anthropic":
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

    elif backend == "openrouter":
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


class RuleBatchScheduler:
    """规则批处理调度器。

    能力：
    - 按批大小切分规则并并发调度；
    - 单批超时控制与失败重试；
    - 全局速率限制（每秒最大批次数）；
    - 幂等请求 ID（相同请求复用结果，避免重复调用 LLM）。
    """

    def __init__(
            self,
            llm_client: LangChainLLMClient,
            batch_size: int,
            max_parallel_batches: int,
            batch_timeout_seconds: float,
            max_retries: int,
            rate_limit_per_second: float,
            idempotency_cache_size: int,
    ):
        self.llm_client = llm_client
        self.batch_size = max(1, batch_size)
        self.max_parallel_batches = max(1, max_parallel_batches)
        self.batch_timeout_seconds = max(0.1, batch_timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.rate_limit_per_second = max(0.0, rate_limit_per_second)
        self.idempotency_cache_size = max(16, idempotency_cache_size)

        self._parallel_semaphore = asyncio.Semaphore(self.max_parallel_batches)
        self._idempotency_lock = asyncio.Lock()
        self._inflight: dict[str, asyncio.Task[list[RuleDecision]]] = {}
        self._completed: dict[str, list[RuleDecision]] = {}

        self._rate_lock = asyncio.Lock()
        self._next_available_time = 0.0
        self._metrics = RuleBatchSchedulerMetricsModel(
            total_requests=0,
            total_batches=0,
            total_llm_calls=0,
            successful_batches=0,
            fallback_batches=0,
            retry_attempts=0,
            batch_timeouts=0,
            idempotency_completed_hits=0,
            idempotency_inflight_hits=0,
            rate_limit_wait_count=0,
            rate_limit_wait_ms=0.0,
        )

    async def evaluate_rules(
            self,
            messages: list[ChatMessage],
            rules: list[DetectionRule],
            request_id: str,
    ) -> list[RuleDecision]:
        """执行规则批调度并返回合并后的决策结果。"""
        if not rules:
            logger.debug(f"📋 规则列表为空，跳过批调度")
            return []

        logger.debug(f"📦 开始规则批调度 | 请求ID={request_id} | 规则数={len(rules)} | 批大小={self.batch_size}")
        batches = [rules[i: i + self.batch_size] for i in range(0, len(rules), self.batch_size)]
        self._metrics.total_requests += 1
        self._metrics.total_batches += len(batches)
        logger.info(f"  📊 批分割完成 | 批次数={len(batches)} | 最大并行={self.max_parallel_batches}")

        async def run_batch(index: int, batch_rules: list[DetectionRule]) -> list[RuleDecision]:
            batch_request_id = self._build_batch_request_id(request_id, messages, batch_rules, index)
            logger.debug(
                f"  🔄 执行批次 {index + 1}/{len(batches)} | 批ID={batch_request_id} | 规则数={len(batch_rules)}")
            return await self._run_idempotent(batch_request_id, lambda: self._execute_batch(messages, batch_rules))

        nested_results = await asyncio.gather(*(run_batch(index, batch) for index, batch in enumerate(batches)))
        decisions = [decision for sublist in nested_results for decision in sublist]
        logger.success(f"✅ 批调度完成 | 总决策数={len(decisions)} | 触发={sum(1 for d in decisions if d.triggered)}")
        return sorted(decisions, key=lambda item: item.rule_id)

    @staticmethod
    def _build_batch_request_id(
            request_id: str,
            messages: list[ChatMessage],
            rules: list[DetectionRule],
            batch_index: int,
    ) -> str:
        message_part = "|".join(message.message_id for message in messages)
        rule_part = "|".join(rule.rule_id for rule in rules)
        digest = hashlib.sha1(f"{request_id}:{batch_index}:{message_part}:{rule_part}".encode("utf-8")).hexdigest()
        return f"rb:{digest}"

    async def _run_idempotent(
            self,
            request_id: str,
            executor: Callable[[], Coroutine[Any, Any, list[RuleDecision]]],
    ) -> list[RuleDecision]:
        async with self._idempotency_lock:
            cached = self._completed.get(request_id)
            if cached is not None:
                self._metrics.idempotency_completed_hits += 1
                logger.debug(f"♻️ 幂等缓存命中 (已完成) | request_id={request_id} | 缓存大小={len(self._completed)}")
                return cached

            task = self._inflight.get(request_id)
            if task is None:
                logger.debug(f"🌀 创建新任务 | request_id={request_id}")
                task = asyncio.create_task(executor())
                self._inflight[request_id] = task
            else:
                self._metrics.idempotency_inflight_hits += 1
                logger.debug(f"♻️ 幂等缓存命中 (飞行中) | request_id={request_id}")

        result = await task

        async with self._idempotency_lock:
            await self._inflight.pop(request_id, None)
            self._completed[request_id] = result
            while len(self._completed) > self.idempotency_cache_size:
                first_key = next(iter(self._completed))
                self._completed.pop(first_key, None)
                logger.debug(f"🗑️ 缓存溢出，移除旧项: {first_key}")

        return result

    async def _execute_batch(
            self,
            messages: list[ChatMessage],
            rules: list[DetectionRule],
    ) -> list[RuleDecision]:
        async with self._parallel_semaphore:
            last_error: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    await self._acquire_rate_limit_slot()
                    self._metrics.total_llm_calls += 1
                    logger.debug(f"🔄 执行第 {attempt + 1}/{self.max_retries + 1} 次 LLM 调用 | 规则数={len(rules)}")
                    decisions = await asyncio.wait_for(
                        self.llm_client.evaluate(messages=messages, rules=rules),
                        timeout=self.batch_timeout_seconds,
                    )
                    self._metrics.successful_batches += 1
                    logger.info(
                        f"✅ LLM 批次执行成功 | 决策数={len(decisions)} | 触发={sum(1 for d in decisions if d.triggered)}")
                    return decisions
                except asyncio.TimeoutError as e:
                    last_error = e
                    self._metrics.batch_timeouts += 1
                    logger.warning(f"⚠️ 批次超时 (attempt {attempt + 1}): 超时={self.batch_timeout_seconds}s")
                    if attempt < self.max_retries:
                        self._metrics.retry_attempts += 1
                        logger.info(f"  🔄 将在 100ms 后重试...")
                        await asyncio.sleep(0.1)
                except Exception as e:
                    last_error = e
                    logger.error(f"❌ 批次执行异常 (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries:
                        self._metrics.retry_attempts += 1
                        await asyncio.sleep(0.1)

            self._metrics.fallback_batches += 1
            logger.error(f"❌ 批次执行失败，使用备用决策 | 最后错误={last_error}")
            return self._fallback_decisions(rules, last_error)

    async def _acquire_rate_limit_slot(self) -> None:
        if self.rate_limit_per_second <= 0:
            return

        interval = 1.0 / self.rate_limit_per_second
        async with self._rate_lock:
            now = time.monotonic()
            if now < self._next_available_time:
                wait_seconds = self._next_available_time - now
                self._metrics.rate_limit_wait_count += 1
                self._metrics.rate_limit_wait_ms += wait_seconds * 1000
                await asyncio.sleep(wait_seconds)
            now2 = time.monotonic()
            self._next_available_time = now2 + interval

    def diagnostics(self) -> "RuleBatchSchedulerDiagnosticsModel":
        """返回批调度器的运行配置与统计信息。"""
        # 已在文件顶部导入，无需重复
        return RuleBatchSchedulerDiagnosticsModel(
            batch_size=self.batch_size,
            max_parallel_batches=self.max_parallel_batches,
            batch_timeout_seconds=self.batch_timeout_seconds,
            max_retries=self.max_retries,
            rate_limit_per_second=self.rate_limit_per_second,
            idempotency_cache_size=self.idempotency_cache_size,
            idempotency_completed_cache_entries=len(self._completed),
            idempotency_inflight_entries=len(self._inflight),
            metrics=self._metrics,
        )

    @staticmethod
    def _fallback_decisions(rules: list[DetectionRule], error: Exception | None) -> list[RuleDecision]:
        reason = f"LLM batch failed: {error}" if error else "LLM batch failed"
        return [
            RuleDecision(
                rule_id=rule.rule_id,
                triggered=False,
                confidence=0.0,
                reason=reason,
                extracted_params={},
            )
            for rule in rules
        ]


class ContextWindowService:
    """上下文窗口服务，用于拉取事件前的若干条消息并与当前消息组合成上下文。

    主要用于在调用 LLM 进行判断时提供必要的上下文信息。
    """

    def __init__(self, store: ChatHistoryStore):
        self.store = store

    async def build_context(self, event: ChatEvent) -> list[ChatMessage]:
        previous = await self.store.recent_history_messages(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            before_message_id=event.message.message_id,
            limit=settings.context_message_limit,
        )
        return [*previous, event.message]


@dataclass(slots=True)
class EngineOutput:
    event_id: str
    results: list[DetectionResult]
    triggered_rule_ids: list[str]
    notified_count: int


@dataclass(slots=True)
class ChannelRuntimeState:
    """单会话运行时状态（用于触发策略控制）。"""

    last_detection_at: datetime | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cooldown_task: asyncio.Task[None] | None = None
    timeout_task: asyncio.Task[None] | None = None


class DetectionEngine:
    """核心检测引擎。

    该引擎负责：
    - 从规则仓库中筛选出适用规则；
    - 调用上下文服务获取消息上下文；
    - 将规则按批次并行提交给 LLMClient 进行判断；
    - 将检测结果写入结果仓储并触发通知/外部 Hook。
    """

    def __init__(
            self,
            rules: RuleRepository,
            context_service: ContextWindowService,
            llm_client: LangChainLLMClient,
            result_repository: DetectionResultRepository,
            notifiers: list[Notifier],
            hook_dispatcher: "ExternalHookDispatcher",
            batch_scheduler: RuleBatchScheduler | None = None,
    ):
        self.rules = rules
        self.context_service = context_service
        self.llm_client = llm_client
        self.result_repository = result_repository
        self.notifiers = notifiers
        self.hook_dispatcher = hook_dispatcher
        self.batch_scheduler = batch_scheduler or RuleBatchScheduler(
            llm_client=llm_client,
            batch_size=settings.llm_rules_per_batch,
            max_parallel_batches=settings.llm_max_parallel_batches,
            batch_timeout_seconds=settings.llm_batch_timeout_seconds,
            max_retries=settings.llm_batch_max_retries,
            rate_limit_per_second=settings.llm_batch_rate_limit_per_second,
            idempotency_cache_size=settings.llm_batch_idempotency_cache_size,
        )
        self._runtime_states: dict[tuple[str, str, str], ChannelRuntimeState] = {}

    @staticmethod
    def _channel_key(platform: str, chat_type: str, chat_id: str) -> tuple[str, str, str]:
        return platform, chat_type, chat_id

    def _state_of(self, platform: str, chat_type: str, chat_id: str) -> ChannelRuntimeState:
        key = self._channel_key(platform, chat_type, chat_id)
        if key not in self._runtime_states:
            self._runtime_states[key] = ChannelRuntimeState()
        return self._runtime_states[key]

    async def ingest_event(self, event: ChatEvent) -> EngineOutput | None:
        """接收新消息事件并按策略决定是否触发检测。

        流程：
        1) 先入 pending 队列；
        2) 满足最小新消息数时尝试触发；
        3) 若不足最小数量，依赖等待超时强制触发。
        """
        if settings.detection_min_new_messages > 1 and settings.detection_wait_timeout_seconds <= 0:
            raise ValueError("When detection_min_new_messages > 1, detection_wait_timeout_seconds must be > 0")

        logger.debug(f"📥 接收事件 | 平台={event.platform} | 会话={event.chat_id} | 消息ID={event.message.message_id}")

        await self.context_service.store.enqueue_message(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            message=event.message,
        )
        logger.debug(f"  ✓ 消息已入队")

        state = self._state_of(event.platform, event.chat_type.value, event.chat_id)
        await self._ensure_timeout_task(event.platform, event.chat_type.value, event.chat_id, state)

        min_new = max(1, settings.detection_min_new_messages)
        pending = await self.context_service.store.pending_size(event.platform, event.chat_type.value, event.chat_id)
        logger.info(f"📊 队列状态 | 待处理={pending} | 最小触发={min_new}")

        if pending < min_new:
            logger.debug(f"⏳ 消息不足，等待更多消息或超时触发...")
            return None

        logger.info(f"🚀 满足最小条件，触发检测...")
        return await self._try_trigger(
            platform=event.platform,
            chat_type=event.chat_type.value,
            chat_id=event.chat_id,
            force_all_pending=False,
        )

    async def _process_event_with_context(self, event: ChatEvent, context_messages: list[ChatMessage]) -> EngineOutput:
        logger.debug(
            f"🔍 开始处理事件 | 会话={event.chat_id} | 消息ID={event.message.message_id} | 上下文数={len(context_messages)}")

        active_rules = [rule for rule in await self.rules.list_enabled() if rule.matcher.matches(event)]
        logger.info(f"📋 适用规则 | 总数={len(active_rules)}")

        # 若上下文中含有自身账号发送的消息，则跳过 LLM 分析
        self_ids = set(settings.detection_self_sender_ids)
        if self_ids:
            self_in_ctx = any(msg.sender_id in self_ids for msg in context_messages if msg.sender_id)
            if self_in_ctx:
                logger.info(f"⏭️ 上下文含有自身消息，跳过 LLM 分析 | 会话={event.chat_id}")
                return EngineOutput(
                    event_id=f"evt-{event.message.message_id}",
                    results=[],
                    triggered_rule_ids=[],
                    notified_count=0,
                )

        scheduler_request_id = f"{event.platform}:{event.chat_id}:{event.message.message_id}"
        decisions = await self.batch_scheduler.evaluate_rules(
            messages=context_messages,
            rules=active_rules,
            request_id=scheduler_request_id,
        )

        event_id = f"evt-{event.message.message_id}"
        all_results: list[DetectionResult] = []
        triggered_rule_ids: list[str] = []
        notify_count = 0

        for decision in decisions:
            suppressed = False
            suppression_reason: str | None = None

            if decision.triggered and context_messages:
                earliest_message_id = context_messages[0].message_id
                is_in_last = await self.result_repository.contains_message_in_last_triggered(decision.rule_id,
                                                                                             earliest_message_id)
                if is_in_last:
                    logger.warning(f"⚠️ 规则 {decision.rule_id} 抑制: 上下文与最后触发重叠")
                    await self.result_repository.merge_into_last_triggered(decision.rule_id, context_messages)
                    suppressed = True
                    suppression_reason = "context overlaps with last triggered result"

            if suppressed:
                logger.debug(f"  ↩️ 抑制结果已合并至最近记录 | rule_id={decision.rule_id}")
                continue

            result = DetectionResult(
                result_id=f"{event_id}:{decision.rule_id}:{len(all_results)}",
                event_id=event_id,
                rule_id=decision.rule_id,
                adapter=event.platform,
                chat_type=event.chat_type.value,
                chat_id=event.chat_id,
                message_id=event.message.message_id,
                decision=decision,
                context_messages=list(context_messages),
                generated_at=datetime.now(timezone.utc),
                trigger_suppressed=suppressed,
                suppression_reason=suppression_reason,
            )
            await self.result_repository.add(result)
            all_results.append(result)
            logger.debug(
                f"  📍 生成结果 | rule_id={decision.rule_id} | triggered={decision.triggered} | suppressed={suppressed}")

            if not decision.triggered or suppressed:
                continue

            triggered_rule_ids.append(decision.rule_id)
            logger.success(f"🎯 规则触发! | rule_id={decision.rule_id} | confidence={decision.confidence:.2f}")

            for notifier in self.notifiers:
                sent = await notifier.notify(event, decision, context_messages)
                notify_count += 1 if sent else 0
                logger.debug(f"  📢 通知器 {notifier.__class__.__name__} 已派发")

            await self.hook_dispatcher.dispatch(event, decision, context_messages)
            logger.debug(f"  🔗 Hook 已派发")

        logger.info(
            f"✅ 事件处理完成 | 事件ID={event_id} | 结果数={len(all_results)} | 触发数={len(triggered_rule_ids)} | 通知数={notify_count}")
        return EngineOutput(
            event_id=event_id,
            results=all_results,
            triggered_rule_ids=triggered_rule_ids,
            notified_count=notify_count,
        )

    async def _try_trigger(
            self,
            platform: str,
            chat_type: str,
            chat_id: str,
            force_all_pending: bool,
    ) -> EngineOutput | None:
        """尝试触发一次检测。

        行为：在会话锁内检查冷却期；若处于冷却则安排冷却完成后的重试；
        否则从 pending 中取出消息并执行检测。

        Args:
            platform: 平台标识。
            chat_type: 聊天类型字符串。
            chat_id: 会话 ID。
            force_all_pending: 是否强制将 pending 中全部消息取出（用于超时触发）。

        Returns:
            若执行了检测返回 `EngineOutput`，否则返回 None（表示未触发）。
        """
        state = self._state_of(platform, chat_type, chat_id)
        async with state.lock:
            now = datetime.now(timezone.utc)
            cooldown = max(0.0, settings.detection_cooldown_seconds)

            logger.debug(f"🔒 获取会话锁 | 会话={chat_id} | force_all={force_all_pending}")

            if state.last_detection_at and cooldown > 0:
                due = state.last_detection_at + timedelta(seconds=cooldown)
                if now < due:
                    remaining = (due - now).total_seconds()
                    logger.info(f"⏸️ 处于冷却期 | 剩余时间={remaining:.2f}s | 安排延迟触发")
                    await self._ensure_cooldown_task(platform, chat_type, chat_id, state, remaining)
                    return None

            logger.debug(f"🎯 检查冷却期通过，开始处理待选消息...")
            output = await self._drain_pending_and_detect(platform, chat_type, chat_id, force_all_pending)
            if output is None:
                logger.debug(f"⏭️ 无消息可处理，返回")
                return None

            state.last_detection_at = datetime.now(timezone.utc)
            logger.success(f"✅ 检测完成 | 事件ID={output.event_id} | 触发规则数={len(output.triggered_rule_ids)}")

            pending = await self.context_service.store.pending_size(platform, chat_type, chat_id)
            min_new = max(1, settings.detection_min_new_messages)
            if pending >= min_new and cooldown > 0:
                logger.debug(f"📅 安排冷却期 | 冷却秒数={cooldown}s")
                await self._ensure_cooldown_task(platform, chat_type, chat_id, state, cooldown)
            await self._ensure_timeout_task(platform, chat_type, chat_id, state)
            return output

    async def _drain_pending_and_detect(
            self,
            platform: str,
            chat_type: str,
            chat_id: str,
            force_all_pending: bool,
    ) -> EngineOutput | None:
        """从 pending 中取出一批消息写入历史并以最后一条为锚触发检测。

        当 `force_all_pending` 为 False 时，最多只取 `detection_min_new_messages` 条；
        否则取出队列内所有消息。

        返回与 `process_event` 相同的 `EngineOutput`，或在没有消息可处理时返回 None。
        """
        min_new = max(1, settings.detection_min_new_messages)
        max_count = None if force_all_pending else min_new

        logger.debug(f"📤 开始从队列中取出消息 | max_count={max_count} | force_all={force_all_pending}")

        pending_messages = await self.context_service.store.pop_pending_messages(
            platform=platform,
            chat_type=chat_type,
            chat_id=chat_id,
            max_count=max_count,
        )
        if not pending_messages:
            logger.debug(f"⏭️ 无待处理消息")
            return None

        logger.info(f"📋 取出消息 | 数量={len(pending_messages)}")

        await self.context_service.store.append_history_messages(
            platform=platform,
            chat_type=chat_type,
            chat_id=chat_id,
            messages=pending_messages,
        )
        logger.debug(f"  ✓ 消息已追加到历史记录")

        anchor_message = pending_messages[-1]
        event = ChatEvent(
            chat_type=ChatType(chat_type),
            chat_id=chat_id,
            message=anchor_message,
            platform=platform,
        )
        context_messages = await self.context_service.build_context(event)
        logger.debug(f"  ✓ 构建上下文 | 上下文消息数={len(context_messages)}")

        return await self._process_event_with_context(event, context_messages)

    async def _ensure_cooldown_task(
            self,
            platform: str,
            chat_type: str,
            chat_id: str,
            state: ChannelRuntimeState,
            delay_seconds: float,
    ) -> None:
        """安排一个冷却到期后的重试任务。

        若已有未完成的冷却任务则不重复创建。
        """
        if state.cooldown_task and not state.cooldown_task.done():
            logger.debug(f"⏳ 冷却任务已存在，跳过创建")
            return

        logger.debug(f"⏲️ 创建冷却任务 | 延迟={delay_seconds:.2f}s | 会话={chat_id}")

        async def _run() -> None:
            try:
                await asyncio.sleep(max(0.0, delay_seconds))
                logger.info(f"🕐 冷却期已到期，触发重试 | 会话={chat_id}")
                await self._try_trigger(platform, chat_type, chat_id, force_all_pending=False)
            except Exception as e:
                logger.error(f"❌ 冷却任务异常: {e}")
            finally:
                state.cooldown_task = None

        state.cooldown_task = asyncio.create_task(_run())

    async def _ensure_timeout_task(
            self,
            platform: str,
            chat_type: str,
            chat_id: str,
            state: ChannelRuntimeState,
    ) -> None:
        """根据当前 pending 状态与配置，安排或取消等待超时强制触发的任务。

        - 若 pending==0 或 最小新消息 <=1 或 超时时间 <=0，则取消已有超时任务。
        - 否则创建一个在 `detection_wait_timeout_seconds` 后执行的任务（若尚未存在）。
        """
        pending = await self.context_service.store.pending_size(platform, chat_type, chat_id)
        min_new = max(1, settings.detection_min_new_messages)
        timeout_seconds = settings.detection_wait_timeout_seconds

        if pending == 0 or min_new <= 1 or timeout_seconds <= 0:
            if state.timeout_task and not state.timeout_task.done():
                logger.debug(f"❌ 取消超时任务 | 原因: pending={pending}, min_new={min_new}, timeout={timeout_seconds}")
                state.timeout_task.cancel()
            state.timeout_task = None
            return

        if state.timeout_task and not state.timeout_task.done():
            logger.debug(f"⏰ 超时任务已存在，跳过创建")
            return

        logger.debug(f"⏲️ 创建超时任务 | 超时秒数={timeout_seconds}s | pending={pending} | 会话={chat_id}")

        async def _run() -> None:
            try:
                await asyncio.sleep(timeout_seconds)
                logger.info(f"🕒 等待超时，强制触发 | 会话={chat_id}")
                await self._try_trigger(platform, chat_type, chat_id, force_all_pending=True)
            except Exception as e:
                logger.error(f"❌ 超时任务异常: {e}")
            finally:
                state.timeout_task = None

        state.timeout_task = asyncio.create_task(_run())


class UserMemoryService:
    """基于配置的用户 ID 列表更新用户画像的服务。"""

    def __init__(self, llm_client: LangChainLLMClient, memory_repository: MemoryRepository,
                 context_service: ContextWindowService):
        self.llm_client = llm_client
        self.memory_repository = memory_repository
        self.context_service = context_service
        self._user_msg_counts: dict[str, int] = {}
        # 记录每个用户最后评估的上下文消息ID
        self._last_context_msg_ids: dict[str, set[str]] = {}
        # 记录每个用户最后提取到的话题名称
        self._last_topics: dict[str, set[str]] = {}
        # 记录每个用户最后提取到的高频联系人及其相关话题 user_id -> target_uid -> topics
        self._last_interactions: dict[str, dict[str, set[str]]] = {}

    async def process_user_memory(self, event: ChatEvent) -> int:
        """按配置的用户 ID 列表提取并累积用户画像。

        Returns:
            更新的画像数量（0 表示未更新，1 表示已更新）。
        """
        user_id = event.message.sender_id
        configured_targets = {str(uid).strip() for uid in settings.memory_target_user_ids if str(uid).strip()}
        if not configured_targets:
            logger.debug("ℹ️ 用户画像未启用，memory_target_user_ids 为空")
            return 0
        if user_id not in configured_targets:
            logger.debug(f"ℹ️ 非画像目标用户，跳过处理 | 发送者={user_id}")
            return 0

        # 判断是否达到处理的最小消息数限制
        min_new = max(1, getattr(settings, "user_memory_min_new_messages", 1))
        self._user_msg_counts[user_id] = self._user_msg_counts.get(user_id, 0) + 1
        current_count = self._user_msg_counts[user_id]

        if current_count < min_new:
            logger.debug(f"⏳ 用户 {user_id} 消息数不足，当前={current_count}，最小触发={min_new}")
            return 0

        # 达到条件，重置计数器
        self._user_msg_counts[user_id] = 0

        logger.debug(
            f"💾 用户画像检测 | 发送者={user_id} | 消息ID={event.message.message_id} | 触发消息数={current_count}")

        context_messages = await self.context_service.build_context(event)
        logger.debug(f"  ✓ 构建上下文 | 消息数={len(context_messages)}")

        existing_profile = await self.memory_repository.get_profile(user_id)
        existing_topics = [
            {
                "name": topic_name,
                "keywords": list(topic_stat.keywords),
            }
            for topic_name, topic_stat in (existing_profile.interests.items() if existing_profile else [])
        ]
        logger.debug(f"  ✓ 已有话题 | 数量={len(existing_topics)}")

        extract = await self.llm_client.extract_self_participation(event, context_messages, existing_topics)
        if extract is None:
            logger.warning(f"⚠️ 参与画像提取失败，跳过更新 | 用户={user_id}")
            return 0
        logger.debug(f"  ✓ LLM 提取完成 | 话题数={len(extract.get('topics', []))}")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        profile = existing_profile or UserMemoryFact(
            user_id=user_id,
            user_name=event.message.sender_name,
        )
        # 始终使用最新的 sender_name 作为昵称来源（若为空则回退 user_id）
        profile.user_name = event.message.sender_name or profile.user_name

        current_msg_ids = {msg.message_id for msg in context_messages}
        last_msg_ids = self._last_context_msg_ids.get(user_id, set())
        has_overlap = bool(current_msg_ids & last_msg_ids)
        last_topics = self._last_topics.get(user_id, set())
        last_interactions = self._last_interactions.get(user_id, {})

        new_extracted_topics = set()

        # 累积话题兴趣
        for topic_data in extract.get("topics", []):
            if not isinstance(topic_data, dict):
                continue
            name = str(topic_data.get("name", "")).strip()
            if not name:
                continue
            
            new_extracted_topics.add(name)
            participation_count = 1  # 每次检测到一次该话题，参与次数+1
            
            if has_overlap and name in last_topics:
                logger.debug(f"⚠️ 用户 {user_id} 画像抑制: 话题 '{name}' 已在最近上下文提取过，跳过参与次数增加")
                participation_count = 0

            keywords = [str(k).strip() for k in topic_data.get("keywords", []) if str(k).strip()]

            if name in profile.interests:
                stat = profile.interests[name]
                stat.score += participation_count
                stat.last_active = now_str
                existing_kw = set(stat.keywords)
                stat.keywords.extend(kw for kw in keywords if kw not in existing_kw)
                if event.chat_id not in stat.related_chat:
                    stat.related_chat.append(event.chat_id)
            else:
                profile.interests[name] = InterestTopicStat(
                    score=participation_count,
                    last_active=now_str,
                    related_chat=[event.chat_id],
                    keywords=keywords,
                )
            logger.debug(f"    ✓ 更新话题: {name} | 参与次数+={participation_count}")

        # 累积活跃群聊
        for group_stat in profile.active_groups:
            if group_stat.group_id == event.chat_id:
                group_stat.frequency += 1
                group_stat.last_talk = today_str
                break
        else:
            profile.active_groups.append(ActiveGroupStat(
                group_id=event.chat_id,
                frequency=1,
                last_talk=today_str,
            ))

        # 累积常联系群友
        sender_name_by_id: dict[str, str] = {}
        for message in context_messages:
            sender_id = str(message.sender_id or "").strip()
            sender_name = str(message.sender_name or "").strip()
            if sender_id and sender_name:
                sender_name_by_id[sender_id] = sender_name

        new_extracted_interactions: dict[str, set[str]] = {}
        for interaction in extract.get("interactions", []):
            if not isinstance(interaction, dict):
                continue
            uid = str(interaction.get("user_id", "")).strip()
            uname = sender_name_by_id.get(uid, "")
            interact_topics = [str(t).strip() for t in interaction.get("topics", []) if str(t).strip()]
            if not uid:
                continue

            new_extracted_interactions[uid] = set(interact_topics)
            is_interaction_suppressed = False
            if has_overlap and uid in last_interactions:
                is_interaction_suppressed = True
                logger.debug(f"⚠️ 用户 {user_id} 画像抑制: 与 '{uid}' 的互动已在最近上下文提取过，跳过互动次数增加")

            if uid not in profile.frequent_contacts:
                profile.frequent_contacts[uid] = FrequentContactStat(
                    name=uname,
                    interaction_count=0,
                    last_interact=now_str,
                )
            contact = profile.frequent_contacts[uid]
            if uname:
                contact.name = uname
            
            if not is_interaction_suppressed:
                contact.interaction_count += 1
            contact.last_interact = now_str
            if event.chat_id not in contact.related_groups:
                contact.related_groups.append(event.chat_id)

            for topic in interact_topics:
                is_topic_suppressed = False
                if is_interaction_suppressed and topic in last_interactions.get(uid, set()):
                    is_topic_suppressed = True
                    logger.debug(f"⚠️ 用户 {user_id} 画像抑制: 与 '{uid}' 的互动话题 '{topic}' 已提取过，跳过参与次数增加")

                if topic in contact.related_topics:
                    if not is_topic_suppressed:
                        contact.related_topics[topic].score += 1
                    contact.related_topics[topic].last_talk = now_str
                else:
                    contact.related_topics[topic] = RelatedTopicStat(
                        score=0 if is_topic_suppressed else 1,
                        last_talk=now_str
                    )
            logger.debug(f"    ✔️ 更新互动: uid={uid} | 话题={interact_topics}")
            
        # 更新抑制状态
        if has_overlap:
            self._last_context_msg_ids[user_id].update(current_msg_ids)
            self._last_topics[user_id].update(new_extracted_topics)
            if user_id not in self._last_interactions:
                self._last_interactions[user_id] = {}
            for uid, topics in new_extracted_interactions.items():
                if uid not in self._last_interactions[user_id]:
                    self._last_interactions[user_id][uid] = set()
                self._last_interactions[user_id][uid].update(topics)
        else:
            self._last_context_msg_ids[user_id] = current_msg_ids
            self._last_topics[user_id] = new_extracted_topics
            self._last_interactions[user_id] = new_extracted_interactions

        await self.memory_repository.upsert_profile(profile)
        logger.success(f"✅ 用户画像已更新 | 用户={user_id} | 话题总数={len(profile.interests)}")
        return 1


class ExternalHookDispatcher:
    """外部 Hook 派发器。

    当规则触发时，将检测结果与上下文通过 POST 方式异步发送到配置好的外部端点。
    """

    def __init__(self, hook_endpoints: list[str]):
        self.hook_endpoints = hook_endpoints

    async def dispatch(self, event: ChatEvent, decision: RuleDecision, context_messages: list[ChatMessage]) -> None:
        """异步将 payload 派发到所有配置的 endpoint，忽略单点失败。"""
        if not self.hook_endpoints:
            logger.debug(f"ℹ️ 无外部 Hook 端点配置，跳过派发")
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
